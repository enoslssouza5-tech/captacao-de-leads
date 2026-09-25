"""Aprovacao, rejeicao e envio dos e-mails da Nexora DENTRO do CRM (substitui o painel antigo da porta 4318).

Preserva todas as protecoes do fluxo original:
- aprovacao e sempre um gesto humano (aqui: clique no CRM, nunca automatico);
- o envio chama o mesmo script `send_gmail.py` (teto de 20/dia, 10 por segmento com fallback, 45s entre envios,
  endereco postal verificado, supressoes, List-Unsubscribe);
- o mesmo arquivo de trava do painel antigo impede dois envios simultaneos entre os dois paineis.
"""
import os
import subprocess
import sys
import threading

import mail  # noqa: F401  (ajusta sys.path para os modulos do Nexora)
import db as ndb
import send_gmail
from env_loader import load_env, is_postal_address_verified

NEXORA_DIR = mail.NEXORA_DIR
SCRIPTS_DIR = os.path.join(NEXORA_DIR, "scripts")
LOCK_PATH = os.path.join(NEXORA_DIR, "logs", "send-now.lock")
LOG_PATH = os.path.join(NEXORA_DIR, "logs", "crm-envio-nexora.log")


class Bloqueado(Exception):
    """Envio ou acao recusada por uma protecao. `codigo` e o status HTTP sugerido."""

    def __init__(self, msg, codigo=400):
        super().__init__(msg)
        self.codigo = codigo


def aprovar(ids):
    conn = ndb.connect()
    try:
        n = 0
        for lid in ids:
            cur = conn.execute("UPDATE leads SET status='aprovado', updated_at=? WHERE id=? AND status='pronto'", (ndb.now_iso(), int(lid)))
            if cur.rowcount:
                ndb.log_activity(conn, int(lid), "aprovado", "Aprovado no CRM.")
                n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def rejeitar(ids, motivo=""):
    conn = ndb.connect()
    try:
        n = 0
        for lid in ids:
            cur = conn.execute("UPDATE leads SET status='rejeitado', rejeicao_motivo=?, updated_at=? WHERE id=? AND status IN ('pronto','aprovado')",
                               (motivo or "rejeitado no CRM", ndb.now_iso(), int(lid)))
            if cur.rowcount:
                ndb.log_activity(conn, int(lid), "rejeitado", motivo or "")
                n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def suprimir(lead_id, motivo="Solicitacao de remocao (opt-out)."):
    conn = ndb.connect()
    try:
        r = conn.execute("SELECT email FROM leads WHERE id=?", (int(lead_id),)).fetchone()
        if not r:
            raise Bloqueado("lead nao encontrado", 404)
        ndb.add_suppression(conn, r["email"], motivo)
        ndb.log_activity(conn, int(lead_id), "suprimido", motivo)
        conn.commit()
    finally:
        conn.close()


def planejar_envio():
    """Quantos e-mails sairiam agora, respeitando os mesmos tetos do send_gmail.py. Levanta Bloqueado se nao puder enviar."""
    env = load_env()
    if not is_postal_address_verified(env):
        raise Bloqueado("Envio bloqueado: NEXORA_POSTAL_ADDRESS_VERIFIED nao e 'true' no .env.")
    if os.path.exists(LOCK_PATH):
        raise Bloqueado("Ja existe um envio em andamento. Aguarde terminar.", 409)
    conn = ndb.connect()
    try:
        aprovados = conn.execute("SELECT segmento FROM leads WHERE status='aprovado' ORDER BY segmento, id").fetchall()
        hoje = send_gmail.sent_today_counts(conn)
    finally:
        conn.close()
    if not aprovados:
        raise Bloqueado("Nenhum lead aprovado aguardando envio.")
    restante_total = max(send_gmail.DAILY_CAP - sum(hoje.values()), 0)
    por_seg = {s: max(send_gmail.CAP_PER_SEGMENT - hoje.get(s, 0), 0) for s in ("real_estate", "law_firm")}
    a_enviar, sobra = 0, {s: 0 for s in por_seg}
    for r in aprovados:                      # 1a passada: teto por segmento
        if a_enviar >= restante_total:
            break
        if por_seg.get(r["segmento"], 0) <= 0:
            sobra[r["segmento"]] += 1
            continue
        a_enviar += 1
        por_seg[r["segmento"]] -= 1
    a_enviar += min(sum(sobra.values()), max(restante_total - a_enviar, 0))     # 2a passada: preenche o teto total com o outro segmento
    if a_enviar == 0:
        raise Bloqueado("Limite diario (total ou por segmento) ja atingido hoje.")
    return {"a_enviar": a_enviar, "aprovados": len(aprovados), "enviados_hoje": hoje, "minutos_estimados": round(a_enviar * send_gmail.DELAY_SECONDS / 60, 1)}


def _rodar_envio():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as logf:
            logf.write("\n--- envio pelo CRM em %s ---\n" % ndb.now_iso())
            logf.flush()
            subprocess.run([sys.executable, os.path.join(SCRIPTS_DIR, "send_gmail.py")], cwd=SCRIPTS_DIR, stdout=logf, stderr=subprocess.STDOUT)
    finally:
        try:
            os.remove(LOCK_PATH)
        except OSError:
            pass


def enviar_agora():
    """Dispara send_gmail.py em segundo plano. So por clique humano."""
    plano = planejar_envio()
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        f.write(ndb.now_iso())
    threading.Thread(target=_rodar_envio, daemon=True).start()
    return plano


def status_envio():
    linhas = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            linhas = [l.rstrip() for l in f.readlines()[-6:]]
    except OSError:
        pass
    return {"enviando": os.path.exists(LOCK_PATH), "log": linhas}
