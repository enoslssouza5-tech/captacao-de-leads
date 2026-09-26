"""Caixa de e-mail estilo Gmail dentro do CRM: pastas, conversas, leitura, resposta e acoes.
Leitura usa gmail.readonly; envio usa gmail.send; excluir/arquivar/marcar lida exigem o escopo gmail.modify
(autorizar com `py crm/gmail_upgrade_auth.py <nexora|atlas>`). Nada e enviado sem clique do usuario."""
import base64
import html
import json
import re
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from email.utils import parseaddr

import gmail_api
import mail
import store

BASE = gmail_api.GMAIL_BASE
PASTAS = [("INBOX", "Caixa de entrada"), ("STARRED", "Com estrela"), ("SENT", "Enviados"), ("DRAFT", "Rascunhos"), ("SPAM", "Spam"), ("TRASH", "Lixeira")]


class SemPermissao(Exception):
    pass


def _get(at, path):
    try:
        return gmail_api._request("GET", BASE + path, at)
    except urllib.error.HTTPError as e:
        raise RuntimeError("Gmail respondeu %s" % e.code) from e


def _post(at, path, body):
    try:
        return gmail_api._request("POST", BASE + path, at, body)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise SemPermissao("Esta ação precisa de autorização extra do Gmail. Rode: py crm/gmail_upgrade_auth.py <conta>") from e
        raise RuntimeError("Gmail respondeu %s" % e.code) from e


def _mapa_leads(conta):
    mapa = {}
    if conta == "nexora":
        for l in store.nexora_leads():
            if l.get("email"):
                mapa[l["email"].lower()] = {"ref": l["ref"], "nome": l["nome"], "etapa": l["etapa"]}
    c = store.crm()
    for r in c.execute("SELECT id, nome, email, etapa FROM leads WHERE conta=? AND email IS NOT NULL", (conta,)):
        mapa[r["email"].lower()] = {"ref": "c%d" % r["id"], "nome": r["nome"], "etapa": r["etapa"]}
    c.close()
    return mapa


def _hdr(msg, nome):
    return gmail_api.header(msg, nome)


def _pessoa(valor):
    nome, email = parseaddr(valor or "")
    return {"nome": nome or email, "email": (email or "").lower()}


def contagens(conta):
    at, _ = mail.access(conta)
    if not at:
        return None
    out = {}
    for rid, _nome in PASTAS:
        try:
            l = _get(at, "/labels/" + rid)
            out[rid] = {"total": l.get("threadsTotal", 0), "nao_lidas": l.get("threadsUnread", 0)}
        except RuntimeError:
            out[rid] = {"total": 0, "nao_lidas": 0}
    return {"pastas": [{"id": i, "nome": n, **out[i]} for i, n in PASTAS]}


def conversas(conta, pasta="INBOX", busca="", pagina=None):
    at, _ = mail.access(conta)
    if not at:
        return {"erro": "conta Gmail nao configurada"}
    params = {"maxResults": 25}
    if pasta in dict(PASTAS):
        params["labelIds"] = pasta
    if pasta in ("TRASH", "SPAM"):
        params["includeSpamTrash"] = "true"
    if busca:
        params["q"] = busca
    if pagina:
        params["pageToken"] = pagina
    lista = _get(at, "/threads?" + urllib.parse.urlencode(params))
    ids = [t["id"] for t in lista.get("threads", [])]
    mapa = _mapa_leads(conta)
    meta = "&".join("metadataHeaders=" + h for h in ("From", "To", "Subject", "Date"))

    def um(tid):
        try:
            return _get(at, "/threads/%s?format=metadata&%s" % (tid, meta))
        except RuntimeError:
            return None

    with ThreadPoolExecutor(8) as ex:
        threads = [t for t in ex.map(um, ids) if t]
    itens = []
    for t in threads:
        msgs = t.get("messages", [])
        if not msgs:
            continue
        ultima, primeira = msgs[-1], msgs[0]
        rotulos = {r for m in msgs for r in m.get("labelIds", [])}
        de = _pessoa(_hdr(ultima, "From"))
        outra = de if pasta != "SENT" else _pessoa(_hdr(ultima, "To"))
        lead = None
        for m in msgs:
            for campo in ("From", "To"):
                p = _pessoa(_hdr(m, campo))
                if p["email"] in mapa:
                    lead = mapa[p["email"]]
        itens.append({"id": t["id"], "assunto": _hdr(primeira, "Subject") or "(sem assunto)", "pessoa": outra["nome"], "email": outra["email"],
                      "snippet": html.unescape(ultima.get("snippet", "")), "data": int(ultima.get("internalDate", 0)), "msgs": len(msgs),
                      "nao_lida": "UNREAD" in rotulos, "estrela": "STARRED" in rotulos, "lead": lead})
    itens.sort(key=lambda x: -x["data"])
    return {"itens": itens, "proxima": lista.get("nextPageToken")}


def _texto(part):
    if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(part["body"]["data"] + "===").decode("utf-8", "replace")
    for sub in part.get("parts", []) or []:
        t = _texto(sub)
        if t:
            return t
    return None


def _html_para_texto(part):
    if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
        bruto = base64.urlsafe_b64decode(part["body"]["data"] + "===").decode("utf-8", "replace")
        bruto = re.sub(r"(?is)<(script|style).*?</\1>", "", bruto)
        bruto = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", bruto)
        return re.sub(r"\n{3,}", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", bruto))).strip()
    for sub in part.get("parts", []) or []:
        t = _html_para_texto(sub)
        if t:
            return t
    return None


def _anexos(part, acc):
    if part.get("filename"):
        acc.append(part["filename"])
    for sub in part.get("parts", []) or []:
        _anexos(sub, acc)
    return acc


def conversa(conta, tid):
    at, _ = mail.access(conta)
    if not at:
        return {"erro": "conta Gmail nao configurada"}
    t = _get(at, "/threads/%s?format=full" % tid)
    mapa = _mapa_leads(conta)
    msgs, lead = [], None
    for m in t.get("messages", []):
        pl = m.get("payload", {})
        corpo = _texto(pl) or _html_para_texto(pl) or m.get("snippet", "")
        de, para = _pessoa(_hdr(m, "From")), _hdr(m, "To")
        for p in [de] + [_pessoa(x) for x in para.split(",")]:
            if p["email"] in mapa:
                lead = mapa[p["email"]]
        msgs.append({"id": m["id"], "de": de, "para": para, "cc": _hdr(m, "Cc"), "data": int(m.get("internalDate", 0)), "assunto": _hdr(m, "Subject"),
                     "corpo": corpo[:20000], "rotulos": m.get("labelIds", []), "anexos": _anexos(pl, []), "message_id": _hdr(m, "Message-ID"),
                     "references": _hdr(m, "References")})
    return {"id": tid, "mensagens": msgs, "lead": lead}


def enviar(conta, para, assunto, corpo, thread_id=None, in_reply_to=None, references=None):
    at, env = mail.access(conta)
    if not at:
        raise RuntimeError("conta Gmail nao configurada")
    endereco = mail._address(conta, at, env)
    m = MIMEText(corpo, "plain", "utf-8")
    nome = env.get("NEXORA_SENDER_NAME", "Nexora") if conta == "nexora" else "Enos | Atlas"
    m["Subject"], m["From"], m["To"] = assunto, "%s <%s>" % (nome, endereco), para
    m["X-CRM-Origem"] = "crm"
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
        m["References"] = ((references or "") + " " + in_reply_to).strip()
    corpo_req = {"raw": base64.urlsafe_b64encode(m.as_bytes()).decode("ascii")}
    if thread_id:
        corpo_req["threadId"] = thread_id
    r = _post(at, "/messages/send", corpo_req)
    _registrar_resposta_manual(conta, para)
    return r


def _registrar_resposta_manual(conta, para):
    """Uma resposta enviada pelo usuario a um lead zera 'aguardando voce' e conta no teto diario de e-mails."""
    email = (parseaddr(para or "")[1] or "").lower()
    if not email:
        return
    c = store.crm()
    try:
        lead = None
        if conta == "nexora":
            lead = next((l for l in store.nexora_leads() if (l.get("email") or "").lower() == email), None)
        if not lead:
            r = c.execute("SELECT * FROM leads WHERE conta=? AND lower(email)=?", (conta, email)).fetchone()
            lead = dict(r, ref="c%d" % r["id"], conta=conta, canal="email") if r else None
        if lead:
            store.registrar_envio(c, dict(lead, conta=conta, canal="email"), 99, "resposta_manual")
            c.commit()
    finally:
        c.close()


ACOES = {
    "trash": ("trash", None), "untrash": ("untrash", None),
    "archive": ("modify", {"removeLabelIds": ["INBOX"]}), "inbox": ("modify", {"addLabelIds": ["INBOX"]}),
    "read": ("modify", {"removeLabelIds": ["UNREAD"]}), "unread": ("modify", {"addLabelIds": ["UNREAD"]}),
    "star": ("modify", {"addLabelIds": ["STARRED"]}), "unstar": ("modify", {"removeLabelIds": ["STARRED"]}),
}


def acao(conta, tid, nome):
    if nome not in ACOES:
        raise RuntimeError("acao invalida")
    at, _ = mail.access(conta)
    if not at:
        raise RuntimeError("conta Gmail nao configurada")
    rota, corpo = ACOES[nome]
    return _post(at, "/threads/%s/%s" % (tid, rota), corpo or {})
