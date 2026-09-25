"""Processos em segundo plano do CRM, separados por responsabilidade para que uma tarefa lenta
(analise de dor, captacao) nunca bloqueie a leitura de respostas ou o envio.

Cada worker registra sua saude em SAUDE (exposta em /api/saude) e nunca morre por excecao.
"""
import json
import logging
import logging.handlers
import os
import sys
import threading
import time
import traceback

import backup
import ia
import mail
import pipeline
import store
from store import CONTAS, crm
from wa import WAManager

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.environ.get("CRM_LOG_DIR") or os.path.join(HERE, "logs")
BACKUP_DIR = os.environ.get("CRM_BACKUP_DIR") or os.path.join(HERE, "backups")
WA_DIR = os.path.join(HERE, "wa-watcher")

log = logging.getLogger("crm")
SAUDE = {}                      # nome do worker -> {"ultima_execucao", "ok", "erro"}
_saude_lock = threading.Lock()

WAM = WAManager(
    cmd=["node", "wa-watcher.js"], cwd=WA_DIR, log_path=os.path.join(WA_DIR, "watcher.log"), flag_path=os.path.join(WA_DIR, ".linked"),
    marcadores=[os.path.join(WA_DIR, ".session"), os.path.join(WA_DIR, "wa-watcher.js")],
)


def configurar_log():
    os.makedirs(LOG_DIR, exist_ok=True)
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    h = logging.handlers.RotatingFileHandler(os.path.join(LOG_DIR, "crm.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.addHandler(logging.StreamHandler(sys.stdout))


def registrar(nome, ok, erro=None):
    with _saude_lock:
        SAUDE[nome] = {"ultima_execucao": store.now(), "ok": ok, "erro": (erro or "")[:300]}


def spawn(fn, *args):
    def run():
        try:
            fn(*args)
        except Exception:
            log.error("erro em thread %s: %s", getattr(fn, "__name__", fn), traceback.format_exc()[-500:])
    threading.Thread(target=run, daemon=True).start()


def _loop(nome, intervalo, passo):
    """Executa `passo` para sempre; qualquer excecao e registrada e o worker continua."""
    while True:
        try:
            passo()
            registrar(nome, True)
        except Exception:
            erro = traceback.format_exc()[-500:]
            log.error("worker %s: %s", nome, erro)
            registrar(nome, False, erro)
        time.sleep(intervalo)


# ---------- Gmail: leitura + classificacao pendente ----------
_ultimo_sync = {}


def passo_gmail():
    for conta in CONTAS:
        if time.time() - _ultimo_sync.get(conta, 0) < 300:
            continue
        if not mail.status()[conta]["configurado"]:
            continue
        _ultimo_sync[conta] = time.time()
        try:
            r = mail.sync(conta)
            registrar("gmail_" + conta, True)
            if r.get("novas"):
                log.info("gmail %s: %d respostas novas", conta, r["novas"])
        except Exception as e:
            registrar("gmail_" + conta, False, str(e))
            log.error("gmail %s falhou: %s", conta, e)
    mail.reclassificar()


# ---------- IA: follow-ups adaptados e analise de dor ----------
def passo_ia():
    if not ia.disponivel():
        return
    c = crm()
    try:
        auto = store.cfg_get(c, "auto_analisar", "1") == "1"
        prox = pipeline.proximo_para_analise(c) if auto else None
    finally:
        c.close()
    pipeline.adaptar_followup()
    if prox:
        pipeline.analisar_lead(prox)


# ---------- captacao diaria da Atlas ----------
def captacao_diaria():
    c = crm()
    try:
        raw = store.cfg_get(c, "captar_atlas", "")
        if not raw:
            return
        cfg = json.loads(raw)
        if not cfg.get("ativo") or cfg.get("ultima") == store.hoje() or not cfg.get("cidades"):
            return
        cidade = cfg["cidades"][cfg.get("indice", 0) % len(cfg["cidades"])]
        cfg["ultima"], cfg["indice"] = store.hoje(), cfg.get("indice", 0) + 1
        store.cfg_set(c, "captar_atlas", json.dumps(cfg, ensure_ascii=False))
    finally:
        c.close()
    log.info("captacao diaria: %s", cidade)
    pipeline.captar_job("atlas", cidade, cfg.get("categoria", "locacao de equipamentos para construcao"), int(cfg.get("quantidade", 10)))


# ---------- envio de e-mail ----------
def passo_envio():
    for conta in CONTAS:
        if mail.status()[conta]["configurado"]:
            r = mail.enviar_followups(conta)
            if r.get("enviados"):
                log.info("follow-ups de e-mail enviados (%s): %d", conta, r["enviados"])
    if mail.status()["atlas"]["configurado"]:
        r = mail.enviar_atlas_aprovados()
        if r.get("enviados"):
            log.info("e-mails da Atlas enviados: %d", r["enviados"])


# ---------- manutencao: backup diario ----------
def passo_manutencao():
    fontes = {"crm": (store.CRM_DB, False), "nexora": (store.NEXORA_DB, True)}
    feitos = backup.fazer_backup(BACKUP_DIR, fontes)
    if feitos:
        log.info("backup feito: %s", ", ".join(os.path.basename(f) for f in feitos))


def iniciar_todos():
    configurar_log()
    if os.environ.get("CRM_SEM_WORKERS"):          # servidor de teste: sem Gmail, IA, captacao, envio, backup nem WhatsApp
        log.info("workers desligados (CRM_SEM_WORKERS)")
        return
    if WAM.ja_vinculado():
        WAM.iniciar(manual=True)
    WAM.iniciar_supervisor()
    for nome, intervalo, passo in (("gmail", 60, passo_gmail), ("ia", 30, passo_ia), ("captacao", 1800, captacao_diaria),
                                   ("envio", 600, passo_envio), ("manutencao", 3600, passo_manutencao)):
        threading.Thread(target=_loop, args=(nome, intervalo, passo), daemon=True, name="w-" + nome).start()
    log.info("workers iniciados")


def saude():
    with _saude_lock:
        workers = dict(SAUDE)
    return {"workers": workers, "ia": ia.estado_ia(), "whatsapp": WAM.publico(), "gmail": mail.status(), "backups": backup.listar(BACKUP_DIR)[-4:]}
