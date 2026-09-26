"""Infraestrutura dos testes: banco temporario isolado, IA e Gmail simulados, servidor real em porta livre.
NUNCA toca em dados reais: CRM_DB e CRM_NEXORA_DB apontam para uma pasta temporaria.
"""
import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from urllib import error as urlerror
from urllib import request as urlreq

TMP = tempfile.mkdtemp(prefix="crm-test-")
os.environ["CRM_DB"] = os.path.join(TMP, "crm.sqlite3")
os.environ["CRM_NEXORA_DB"] = os.path.join(TMP, "nexora.sqlite3")
os.environ["CRM_TRADUCOES"] = os.path.join(TMP, "traducoes.sqlite3")
os.environ["CRM_VERIFICAR_DNS"] = "0"
CRM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CRM_DIR)

import store  # noqa: E402
import mail  # noqa: E402  (ajusta o sys.path para os modulos do Nexora)
import ia  # noqa: E402
import server  # noqa: E402
import workers  # noqa: E402
import db as ndb  # noqa: E402
import gmail_api  # noqa: E402

ndb.DB_PATH = os.environ["CRM_NEXORA_DB"]
ia.executor = lambda prompt, tools=None: "{}"          # trava de seguranca: substituida por ia_falsa em cada teste

ENV_FALSO = {"NEXORA_GMAIL_ADDRESS": "nexora@teste.example", "NEXORA_SENDER_NAME": "Nexora Teste", "NEXORA_POSTAL_ADDRESS": "1 Test St, Testville",
             "NEXORA_POSTAL_ADDRESS_VERIFIED": "true"}


def b64(txt):
    return base64.urlsafe_b64encode(txt.encode("utf-8")).decode("ascii")


def ia_falsa(prompt, tools=None):
    """Substitui o claude -p: respostas deterministicas por palavra-chave (so olha o texto do lead, nao as instrucoes)."""
    if "Voce classifica a resposta" in prompt:
        texto = prompt.split("RESPOSTA DO LEAD:\n", 1)[1].lower()
        regras = [
            (("couldn't be delivered", "delivery status", "mailer-daemon", "failure notice"), ("bounce", False)),
            (("out of office", "automatic reply", "resposta automatica", "fora do escritorio"), ("out_of_office", False)),
            (("unsubscribe", "remove me", "stop emailing", "descadastr", "pare de enviar"), ("unsubscribe", False)),
            (("not interested", "no thanks", "nao tenho interesse", "não tenho interesse", "ja temos", "já temos"), ("negative", False)),
            (("call me", "let's talk", "lets talk", "quero conversar", "me liga", "send pricing", "orcamento", "orçamento", "agendar"), ("positive", True)),
            (("how much", "quanto custa", "what's included", "como funciona"), ("question", False)),
            (("interested", "tenho interesse", "interessante", "gostei"), ("positive", False)),
        ]
        for chaves, (cat, reuniao) in regras:
            if any(k in texto for k in chaves):
                return json.dumps({"categoria": cat, "reuniao": reuniao, "traducao_pt": "[pt] " + texto[:60], "resumo": "resumo " + cat})
        return json.dumps({"categoria": "neutral", "reuniao": False, "traducao_pt": texto[:60], "resumo": "vago"})
    if prompt.startswith("Translate the text below"):
        direcao = "PT" if "to Brazilian Portuguese" in prompt[:160] else "EN"
        return "[%s] %s" % (direcao, prompt.split("TEXT:", 1)[1].strip())
    if "Escreva o follow-up" in prompt:
        return "Oi, so passando para saber se viu minha mensagem. Posso te mostrar uma ideia rapida?"
    if "Reescreva a mensagem abaixo" in prompt:
        return "Oi, me chamo Enos. Vi que voces tem 120 avaliacoes no Google, mas nao tem site proprio para receber orcamentos. Posso te mostrar uma ideia?"
    if "ANALISE PROFUNDA" in prompt:
        return json.dumps({"dor": "Tem 120 avaliacoes no Google e nao tem site proprio para receber orcamentos.", "criterios": [{"criterio": "Reputacao", "achado": "120 avaliacoes", "impacto": "alto"}],
                           "evidencias": ["120 avaliacoes no Google"], "tipo_dor": "sem_site",
                           "mensagem": "Oi, me chamo Enos. Vi que voces tem 120 avaliacoes no Google, mas nao tem site proprio para receber orcamentos. Posso te mostrar uma ideia?",
                           "assunto": "Uma ideia para o site", "email": "Oi, me chamo Enos. Vi 120 avaliacoes e nenhum site. Posso te mostrar uma ideia?"})
    if "Apify" in prompt:
        return json.dumps([{"nome": "Locadora Teste Um", "telefone": "+55 77 99111-2222", "email": None, "site": None, "cidade": "Cidade Teste", "avaliacoes": 90, "nota_google": 4.8}])
    return "{}"


def msg_gmail(mid, de, assunto, corpo, rotulos=None):
    return {"id": mid, "snippet": corpo[:80], "labelIds": rotulos or ["INBOX"],
            "payload": {"mimeType": "text/plain", "headers": [{"name": "From", "value": de}, {"name": "Subject", "value": assunto}],
                        "body": {"data": b64(corpo)}}}


class BaseCRM(unittest.TestCase):
    """Sobe um servidor de verdade (porta livre) com banco temporario e ferramentas externas simuladas."""

    @classmethod
    def setUpClass(cls):
        cls.srv = server.criar_servidor(0)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.porta

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.reset_bancos()
        ia.executor = ia_falsa
        ia._estado.update(falhas=0, ate=0.0, ultimo_erro="")
        self.enviados, self.esperas = [], []
        self.inbox = []
        self._gp = gmail_api.get_profile
        self._orig = (gmail_api.list_inbox_message_ids, gmail_api.get_message, gmail_api.send_message, mail.access, mail.load_env, mail.time)
        gmail_api.list_inbox_message_ids = lambda at, q="in:inbox", n=25: [m["id"] for m in self.inbox]
        gmail_api.get_message = lambda at, mid: next(m for m in self.inbox if m["id"] == mid)
        gmail_api.send_message = lambda at, raw: self.enviados.append(raw) or {"id": "x%d" % len(self.enviados)}
        def sem_rede(*a, **k):
            raise AssertionError("chamada de rede REAL ao Gmail durante o teste: %r" % (a[:2],))
        self._req = gmail_api._request
        gmail_api._request = sem_rede
        gmail_api.get_profile = lambda at: {"emailAddress": "atlas@teste.example"}
        mail.access = lambda conta: ("token-falso", dict(ENV_FALSO))
        mail.load_env = lambda: dict(ENV_FALSO)
        esperas = self.esperas

        class _Tempo:
            sleep = staticmethod(lambda s: esperas.append(s))

            def __getattr__(self, n):
                return getattr(time, n)

        mail.time = _Tempo()

    def tearDown(self):
        (gmail_api.list_inbox_message_ids, gmail_api.get_message, gmail_api.send_message, mail.access, mail.load_env, mail.time) = self._orig
        gmail_api._request = self._req
        gmail_api.get_profile = self._gp
        # espera threads de fundo (classificacao) terminarem ANTES de trocar a IA: nunca deixa uma thread atrasada chamar o claude real
        if mail._reclass_lock.acquire(timeout=20):
            mail._reclass_lock.release()
        ia.executor = ia_falsa

    # ---------- bancos ----------
    def reset_bancos(self):
        c = store.crm()
        for t in ("leads", "tarefas", "respostas", "bloqueios", "servicos", "pagamentos", "metas", "envios", "propostas", "config", "jobs", "gmail_vistos", "wa_mensagens"):
            c.execute("DELETE FROM " + t)
        c.commit()
        c.close()
        for ext in ("", "-wal", "-shm"):
            try:
                os.remove(os.environ["CRM_NEXORA_DB"] + ext)
            except OSError:
                pass
        ndb.connect().close()

    def nexora_lead(self, empresa="Nexora Teste Imob", email="lead@imob.example", status="enviado", enviado_ha_dias=None, segmento="real_estate", **extra):
        conn = ndb.connect()
        item = dict(lote_id="t1", segmento=segmento, empresa=empresa, email=email, assunto="An idea for " + empresa, corpo_texto="x", corpo_html="x",
                    landing_page_status="absent", review_count=100)
        item.update(extra)
        lid = ndb.insert_lead(conn, item)
        if status != "pronto":
            sent = time_iso(enviado_ha_dias or 0) if status in ("enviado", "respondido") else None
            conn.execute("UPDATE leads SET status=?, sent_at=? WHERE id=?", (status, sent, lid))
        conn.commit()
        conn.close()
        return lid

    def nexora_row(self, lid):
        conn = ndb.connect()
        r = conn.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
        supp = [x["email"] for x in conn.execute("SELECT email FROM suppression")]
        conn.close()
        return r, supp

    # ---------- HTTP ----------
    def http(self, metodo, caminho, corpo=None, headers=None, json_ct=True):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else (b"{}" if metodo == "POST" else None)
        req = urlreq.Request(self.base + caminho, data=dados, method=metodo)
        if metodo == "POST" and json_ct:
            req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urlreq.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urlerror.HTTPError as e:
            txt = e.read().decode("utf-8")
            return e.code, (json.loads(txt) if txt else {})

    def get(self, caminho, **kw):
        return self.http("GET", caminho, **kw)

    def post(self, caminho, corpo=None, **kw):
        return self.http("POST", caminho, corpo, **kw)

    def novo_lead(self, **campos):
        d = {"conta": "atlas", "canal": "whatsapp", "nome": "Empresa Teste", "telefone": "(77) 99888-7766", "etapa": "Pronto", "mensagem": "Bom dia! Me chamo Enos."}
        d.update(campos)
        st, r = self.post("/api/leads", d)
        self.assertEqual(st, 201, r)
        return r["id"]

    def lead_db(self, lid):
        c = store.crm()
        r = c.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
        c.close()
        return r

    def sql(self, consulta, *args):
        c = store.crm()
        r = c.execute(consulta, args).fetchall()
        c.close()
        return r

    def esperar(self, condicao, timeout=10, msg="condicao nao atendida"):
        fim = time.time() + timeout
        while time.time() < fim:
            if condicao():
                return
            time.sleep(0.1)
        self.fail(msg)


def time_iso(dias_atras):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=dias_atras)).isoformat()
