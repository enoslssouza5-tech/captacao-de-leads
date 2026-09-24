"""Gmail do CRM: leitura de respostas (Nexora e Atlas), classificacao com IA local, follow-up de e-mail
e envio dos e-mails aprovados da Atlas. Reaproveita os modulos do Nexora (gmail_api, token_store, db, env_loader)."""
import json
import os
import re
import sys
import time
from email.mime.text import MIMEText

HERE = os.path.dirname(os.path.abspath(__file__))
NEXORA_DIR = os.path.join(os.path.dirname(HERE), "_opensquad", "_memory", "nexora")
sys.path.insert(0, os.path.join(NEXORA_DIR, "scripts"))
import db as ndb  # noqa: E402
import gmail_api  # noqa: E402
import send_gmail  # noqa: E402
import token_store  # noqa: E402
from env_loader import load_env, load_client_credentials, is_postal_address_verified  # noqa: E402

import ia  # noqa: E402
import store  # noqa: E402

ATLAS_DIR = os.path.join(HERE, "atlas_gmail")
ATLAS_TOKEN = os.path.join(ATLAS_DIR, "token.json")
DELAY_SECONDS = 45
BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
EMAIL_RE = re.compile(r"[\w\.\-+]+@[\w\-]+\.[\w\.\-]+")


def _refresh_token(conta, env):
    if conta == "nexora":
        return token_store.load_refresh_token(env)
    if os.path.exists(ATLAS_TOKEN):
        with open(ATLAS_TOKEN, encoding="utf-8") as f:
            return json.load(f).get("refresh_token")
    return None


def access(conta):
    env = load_env()
    cid, cs = load_client_credentials(env)
    rt = _refresh_token(conta, env)
    if not (cid and cs and rt):
        return None, env
    return gmail_api.get_access_token(cid, cs, rt), env


def status():
    env = load_env()
    cid, cs = load_client_credentials(env)
    out = {}
    for conta in store.CONTAS:
        rt = _refresh_token(conta, env)
        addr = env.get("NEXORA_GMAIL_ADDRESS") if conta == "nexora" else None
        if conta == "atlas" and rt:
            p = os.path.join(ATLAS_DIR, "address.txt")
            if os.path.exists(p):
                addr = open(p, encoding="utf-8").read().strip()
        out[conta] = {"configurado": bool(cid and cs and rt), "endereco": addr, "credenciais_google": bool(cid and cs)}
    return out


def _body_of(msg):
    return (gmail_api.header(msg, "Subject") + "\n\n" + gmail_api.decode_body_text(msg)).strip()[:3000]


def _sender(msg):
    m = EMAIL_RE.search(gmail_api.header(msg, "From"))
    return m.group(0).lower() if m else ""


def _nexora_lead_by_email(email):
    for l in store.nexora_leads():
        if (l["email"] or "").lower() == email:
            return l
    return None


def _nexora_apply(lead_id, email, cat8, cls, texto):
    conn = ndb.connect()
    try:
        ts = ndb.now_iso()
        if cls in ("bounce",):
            ndb.add_suppression(conn, email, "bounce detectado pelo CRM")
        elif cls != "automatica":
            conn.execute("UPDATE leads SET status='respondido', responded_at=?, updated_at=? WHERE id=? AND status IN ('enviado','respondido')", (ts, ts, lead_id))
            ndb.set_response_classification(conn, lead_id, cat8, texto[:2000])
            if cat8 == "unsubscribe":
                ndb.add_suppression(conn, email, "unsubscribe classificado pelo CRM (automatico)")
            elif cls == "recusou":
                ndb.set_negotiation_status(conn, lead_id, "perdido")
            elif cls == "reuniao":
                ndb.set_negotiation_status(conn, lead_id, "em_negociacao")
            else:
                ndb.set_negotiation_status(conn, lead_id, "respondido")
        conn.commit()
    finally:
        conn.close()


def _lead_dict_crm(c, conta, email):
    r = c.execute("SELECT * FROM leads WHERE conta=? AND canal='email' AND lower(email)=?", (conta, email)).fetchone()
    return dict(r, ref="c%d" % r["id"], id="c%d" % r["id"], readonly=False) if r else None


def _classificar(texto):
    try:
        return ia.classify_reply(texto)
    except Exception:
        return None


def sync(conta):
    """Le a caixa de entrada, cruza com leads, classifica e move o funil. Retorna quantas respostas novas."""
    at, env = access(conta)
    if not at:
        return {"ok": False, "motivo": "conta Gmail nao configurada"}
    own = (env.get("NEXORA_GMAIL_ADDRESS") or "").lower() if conta == "nexora" else ""
    c = store.crm()
    vistos = {r[0] for r in c.execute("SELECT message_id FROM gmail_vistos WHERE conta=?", (conta,))}
    novos = 0
    for mid in gmail_api.list_inbox_message_ids(at, "in:inbox OR in:spam", 60):
        if mid in vistos:
            continue
        msg = gmail_api.get_message(at, mid)
        remetente, texto = _sender(msg), _body_of(msg)
        c.execute("INSERT OR IGNORE INTO gmail_vistos (conta, message_id) VALUES (?,?)", (conta, mid))
        if not remetente or remetente == own:
            continue
        if any(b in remetente for b in BOUNCE_SENDERS):
            lead = None
            for addr in EMAIL_RE.findall(texto.lower()):
                lead = _nexora_lead_by_email(addr) if conta == "nexora" else _lead_dict_crm(c, conta, addr)
                if lead:
                    break
            res = {"categoria8": "bounce", "classificacao": "bounce", "traducao": "", "resumo": "E-mail devolvido"}
        else:
            lead = _nexora_lead_by_email(remetente) if conta == "nexora" else _lead_dict_crm(c, conta, remetente)
            res = _classificar(texto) if lead else None
        if not lead:
            continue
        cls = res["classificacao"] if res else None
        if conta == "nexora" and res:
            _nexora_apply(int(lead["ref"][1:]), lead["email"], res["categoria8"], cls, texto)
        elif conta == "nexora":
            _nexora_apply(int(lead["ref"][1:]), lead["email"], "unclassified", "pendente", texto)
        store.registrar_resposta(c, lead, texto, cls, (res or {}).get("traducao", ""), (res or {}).get("resumo", ""), "gmail", mid)
        novos += 1
    c.commit()
    c.close()
    return {"ok": True, "novas": novos}


def reclassificar():
    c = store.crm()
    n = 0
    for r in store.pendentes_de_classificar(c, 3):
        res = _classificar(r["texto"] or "")
        if res:
            store.classificar_existente(c, r, res)
            if r["lead_ref"].startswith("n"):
                lead = store.get_lead(c, r["lead_ref"])
                if lead:
                    _nexora_apply(int(r["lead_ref"][1:]), lead["email"], res["categoria8"], res["classificacao"], r["texto"] or "")
            n += 1
    c.commit()
    c.close()
    return n


def _footer(conta, env):
    if conta == "nexora":
        return "\n\n--\n%s\nIf you'd rather not receive further emails, just reply \"unsubscribe\"." % (env.get("NEXORA_POSTAL_ADDRESS") or "")
    return "\n\n--\nSe não quiser mais receber mensagens, é só responder \"sair\"."


def _mime(conta, env, address, to, assunto, corpo):
    m = MIMEText(corpo + _footer(conta, env), "plain", "utf-8")
    nome = env.get("NEXORA_SENDER_NAME", "Nexora") if conta == "nexora" else "Enos | Atlas"
    m["Subject"], m["From"], m["To"] = assunto, "%s <%s>" % (nome, address), to
    m["List-Unsubscribe"] = "<mailto:%s?subject=unsubscribe>" % address
    return m.as_bytes()


def _address(conta, at, env):
    if conta == "nexora":
        return env["NEXORA_GMAIL_ADDRESS"]
    os.makedirs(ATLAS_DIR, exist_ok=True)
    p = os.path.join(ATLAS_DIR, "address.txt")
    addr = gmail_api.get_profile(at).get("emailAddress", "")
    with open(p, "w", encoding="utf-8") as f:
        f.write(addr)
    return addr


def _restante_email(c, conta):
    if conta == "nexora":
        nconn = ndb.connect()
        cold = sum(send_gmail.sent_today_counts(nconn).values())
        nconn.close()
        fu = c.execute("SELECT COUNT(*) FROM envios WHERE conta='nexora' AND canal='email' AND passo>0 AND substr(enviado_em,1,10)=?", (store.hoje(),)).fetchone()[0]
        return max(store.EMAIL_DAILY_CAP - cold - fu, 0)
    return max(store.EMAIL_DAILY_CAP - store.enviados_hoje(c, "atlas", "email"), 0)


def _suprimido(conta, email):
    email = (email or "").lower()
    if conta == "nexora":
        conn = ndb.connect()
        r = conn.execute("SELECT 1 FROM suppression WHERE email=?", (email,)).fetchone()
        conn.close()
        return bool(r)
    c = store.crm()
    r = c.execute("SELECT 1 FROM bloqueios WHERE conta='atlas' AND chave=?", (email,)).fetchone()
    c.close()
    return bool(r)


def enviar_followups(conta):
    c = store.crm()
    try:
        if store.cfg_get(c, "auto_followup_email_" + conta) != "1":
            return {"enviados": 0, "motivo": "desligado"}
        env = load_env()
        if conta == "nexora" and not is_postal_address_verified(env):
            return {"enviados": 0, "motivo": "endereco postal nao verificado"}
        at, env = access(conta)
        if not at:
            return {"enviados": 0, "motivo": "conta nao configurada"}
        addr = _address(conta, at, env)
        if conta == "nexora":
            store.sync_nexora_followups(c)
        limite = _restante_email(c, conta)
        enviados = 0
        for t in c.execute("SELECT * FROM tarefas WHERE conta=? AND canal='email' AND status='pendente' AND due_date<=? ORDER BY due_date, passo", (conta, store.hoje())).fetchall():
            if enviados >= limite:
                break
            lead = store.get_lead(c, t["lead_ref"])
            if not lead or lead["etapa"] != "Contatado" or not t["email"] or _suprimido(conta, t["email"]):
                c.execute("UPDATE tarefas SET status='cancelada' WHERE id=?", (t["id"],))
                continue
            assunto = "Re: " + (lead.get("assunto") or lead.get("nota") or "my note")
            try:
                gmail_api.send_message(at, _mime(conta, env, addr, t["email"], assunto, t["mensagem"]))
                store.concluir_tarefa(c, t["id"], "auto_email", 1)
                enviados += 1
            except Exception as e:
                c.execute("UPDATE tarefas SET status='erro', mensagem=mensagem || ? WHERE id=?", ("\n[erro de envio: %s]" % str(e)[:120], t["id"]))
            c.commit()
            time.sleep(DELAY_SECONDS)
        return {"enviados": enviados}
    finally:
        c.commit()
        c.close()


def enviar_atlas_aprovados():
    c = store.crm()
    try:
        at, env = access("atlas")
        if not at:
            return {"enviados": 0, "motivo": "conta nao configurada"}
        addr = _address("atlas", at, env)
        limite = _restante_email(c, "atlas")
        enviados = 0
        for r in c.execute("SELECT * FROM leads WHERE conta='atlas' AND canal='email' AND etapa='Pronto' AND aprovado=1 AND email IS NOT NULL ORDER BY id").fetchall():
            if enviados >= limite:
                break
            if _suprimido("atlas", r["email"]):
                c.execute("UPDATE leads SET etapa='Perdido', updated_at=? WHERE id=?", (store.now(), r["id"]))
                continue
            lead = dict(r, ref="c%d" % r["id"], id="c%d" % r["id"])
            try:
                gmail_api.send_message(at, _mime("atlas", env, addr, r["email"], r["assunto"] or "Uma ideia para o seu site", r["mensagem"] or ""))
                store.marcar_primeiro_envio(c, lead, "auto_email")
                enviados += 1
            except Exception as e:
                c.execute("UPDATE leads SET notas=COALESCE(notas,'') || ? WHERE id=?", ("\n[erro de envio: %s]" % str(e)[:120], r["id"]))
            c.commit()
            time.sleep(DELAY_SECONDS)
        return {"enviados": enviados}
    finally:
        c.commit()
        c.close()
