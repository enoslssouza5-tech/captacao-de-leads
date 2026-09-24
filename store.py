"""Nucleo de dados do CRM: esquema, funil unico, follow-ups, respostas, radar, aprendizado, financeiro."""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NEXORA_DB = os.path.join(ROOT, "_opensquad", "_memory", "nexora", "db", "nexora.sqlite3")
CRM_DB = os.path.join(HERE, "crm.sqlite3")
WA_DAILY_CAP = int(os.environ.get("WA_DAILY_CAP", "15"))
EMAIL_DAILY_CAP = int(os.environ.get("EMAIL_DAILY_CAP", "20"))

CONTAS = ("nexora", "atlas")
CANAIS = ("email", "whatsapp")
ETAPAS = ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"]
FOLLOWUP_DIAS = (3, 7, 14)
CLASSES = ("interessado", "duvida", "reuniao", "pendente", "recusou", "automatica", "bounce")

MODELOS_PADRAO = {
    ("atlas", 1): "Oi, {nome}, tudo bem? Passando só para saber se você conseguiu ver minha mensagem. Posso te mostrar o modelo pronto, sem compromisso?",
    ("atlas", 2): "{nome}, sei que a rotina é corrida. Separei um exemplo de página feito para empresas do seu segmento. Quer que eu envie por aqui?",
    ("atlas", 3): "{nome}, vou encerrar por aqui para não incomodar. Se em algum momento fizer sentido ter uma página que transforma visitas em orçamentos, é só me chamar. Abraço!",
    ("nexora", 1): "Hi, just circling back on my note about the page idea for {nome}. Happy to send the example again if that helps.",
    ("nexora", 2): "Hi, one more angle for {nome}: the example page is illustrative and can be adjusted to your preferences. Want me to tailor it further?",
    ("nexora", 3): "I'll close the loop here so I don't crowd your inbox. If a page like this ever becomes a priority for {nome}, just reply and I'll pick it up.",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def hoje():
    return datetime.now(timezone.utc).date().isoformat()


def _cols(c, tabela):
    return {r[1] for r in c.execute("PRAGMA table_info(%s)" % tabela)}


def crm():
    c = sqlite3.connect(CRM_DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS leads (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conta TEXT NOT NULL, canal TEXT NOT NULL, etapa TEXT NOT NULL DEFAULT 'Novo',
          nome TEXT NOT NULL, contato TEXT, telefone TEXT, email TEXT, cidade TEXT, site TEXT,
          fonte TEXT, nota_google REAL, avaliacoes INTEGER, dor TEXT, tipo_dor TEXT, criterios_json TEXT,
          assunto TEXT, mensagem TEXT, notas TEXT, aprovado INTEGER DEFAULT 0,
          sem_whatsapp INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, sent_at TEXT);
        CREATE TABLE IF NOT EXISTS tarefas (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conta TEXT NOT NULL, canal TEXT NOT NULL, lead_ref TEXT NOT NULL, nome TEXT, telefone TEXT, email TEXT,
          passo INTEGER NOT NULL, due_date TEXT NOT NULL, mensagem TEXT, ia INTEGER DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'pendente', done_at TEXT, auto INTEGER DEFAULT 0, UNIQUE(lead_ref, passo));
        CREATE TABLE IF NOT EXISTS respostas (
          id INTEGER PRIMARY KEY AUTOINCREMENT, lead_ref TEXT NOT NULL, conta TEXT NOT NULL, texto TEXT,
          traducao TEXT, classificacao TEXT, resumo TEXT, origem TEXT, message_id TEXT, canal TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS bloqueios (
          id INTEGER PRIMARY KEY AUTOINCREMENT, conta TEXT NOT NULL, chave TEXT NOT NULL, motivo TEXT, created_at TEXT,
          UNIQUE(conta, chave));
        CREATE TABLE IF NOT EXISTS modelos (conta TEXT NOT NULL, passo INTEGER NOT NULL, texto TEXT NOT NULL, PRIMARY KEY(conta, passo));
        CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, conta TEXT NOT NULL, nome TEXT NOT NULL, preco_centavos INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS pagamentos (
          id INTEGER PRIMARY KEY AUTOINCREMENT, conta TEXT NOT NULL, lead_ref TEXT, cliente TEXT, descricao TEXT,
          valor_centavos INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'a_receber', vencimento TEXT, pago_em TEXT,
          fonte TEXT DEFAULT 'manual', created_at TEXT);
        CREATE TABLE IF NOT EXISTS metas (conta TEXT NOT NULL, mes TEXT NOT NULL, valor_centavos INTEGER NOT NULL, PRIMARY KEY(conta, mes));
        CREATE TABLE IF NOT EXISTS envios (
          id INTEGER PRIMARY KEY AUTOINCREMENT, lead_ref TEXT NOT NULL, conta TEXT NOT NULL, canal TEXT NOT NULL,
          passo INTEGER NOT NULL DEFAULT 0, tipo_dor TEXT, enviado_em TEXT NOT NULL, origem TEXT);
        CREATE TABLE IF NOT EXISTS propostas (
          id INTEGER PRIMARY KEY AUTOINCREMENT, conta TEXT NOT NULL, titulo TEXT, evidencia TEXT, ajuste TEXT,
          status TEXT NOT NULL DEFAULT 'pendente', created_at TEXT);
        CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, conta TEXT, status TEXT, detalhe TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS gmail_vistos (conta TEXT NOT NULL, message_id TEXT NOT NULL, PRIMARY KEY(conta, message_id));
        """
    )
    for tab, col, tipo in (("leads", "tipo_dor", "TEXT"), ("leads", "criterios_json", "TEXT"), ("leads", "assunto", "TEXT"), ("leads", "aprovado", "INTEGER DEFAULT 0"),
                           ("tarefas", "ia", "INTEGER DEFAULT 0"), ("tarefas", "auto", "INTEGER DEFAULT 0"), ("respostas", "resumo", "TEXT"),
                           ("respostas", "origem", "TEXT"), ("respostas", "message_id", "TEXT"), ("respostas", "canal", "TEXT")):
        if col not in _cols(c, tab):
            c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tab, col, tipo))
    for (conta, passo), texto in MODELOS_PADRAO.items():
        c.execute("INSERT OR IGNORE INTO modelos (conta, passo, texto) VALUES (?,?,?)", (conta, passo, texto))
    c.commit()
    return c


def cfg_get(c, chave, padrao="0"):
    r = c.execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    return r[0] if r else padrao


def cfg_set(c, chave, valor):
    c.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?,?)", (chave, str(valor)))
    c.commit()


# ---------- Nexora (leitura do banco existente) ----------
def nexora_ro():
    if not os.path.exists(NEXORA_DB):
        return None
    c = sqlite3.connect("file:" + NEXORA_DB.replace("\\", "/") + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def score_nexora(reviews, lp):
    base = {"absent": 45, "present_with_issue": 35, "uncertain": 15, "present_without_issue": 5}.get(lp, 10)
    return int(min(100, base + min(reviews or 0, 300) / 300 * 55))


def score_crm(l):
    s = 10 + (40 if not l["site"] else 10) + min(l["avaliacoes"] or 0, 300) / 300 * 40 + (10 if l["telefone"] else 0)
    return int(min(100, s))


def etapa_nexora(r):
    neg, cl = r["status_negociacao"], r["resposta_classificacao"]
    if neg == "fechado":
        return "Fechado"
    if neg == "perdido" or r["status"] == "rejeitado" or cl in ("negative", "unsubscribe", "bounce"):
        return "Perdido"
    if neg == "em_negociacao":
        return "Negociando"
    if r["status"] == "respondido" or neg == "respondido":
        return "Respondeu"
    return {"pronto": "Pronto", "aprovado": "Pronto", "enviado": "Contatado"}.get(r["status"], "Pronto")


def nexora_leads():
    n = nexora_ro()
    if not n:
        return []
    out = []
    for r in n.execute("SELECT id, empresa, segmento, cidade_estado, email, status, status_negociacao, resposta_classificacao, review_count, "
                       "landing_page_status, selected_subject, assunto, sent_at, responded_at, site, fonte FROM leads ORDER BY id DESC"):
        lp = r["landing_page_status"]
        out.append({
            "id": "n%d" % r["id"], "ref": "n%d" % r["id"], "conta": "nexora", "canal": "email", "nome": r["empresa"], "sub": r["cidade_estado"] or "",
            "email": r["email"], "tag": "real estate" if r["segmento"] == "real_estate" else "law firm", "etapa": etapa_nexora(r),
            "nota": r["selected_subject"] or r["assunto"] or "", "readonly": True, "score": score_nexora(r["review_count"], lp),
            "avaliacoes": r["review_count"], "site": r["site"], "fonte": r["fonte"], "sent_at": r["sent_at"], "responded_at": r["responded_at"],
            "aprovado": r["status"] == "aprovado", "assunto": r["assunto"],
            "tipo_dor": {"absent": "sem_landing", "present_with_issue": "landing_com_problema", "uncertain": "landing_incerta"}.get(lp, "site_ok"),
            "sinais": [s for s in (("sem landing" if lp == "absent" else None), ("landing com problema" if lp == "present_with_issue" else None)) if s],
        })
    n.close()
    return out


# ---------- utilitarios ----------
def phone_key(tel):
    d = "".join(ch for ch in (tel or "") if ch.isdigit())
    if len(d) >= 12 and d.startswith("55"):
        d = d[2:]
    return (d[:2] + d[-8:]) if len(d) >= 10 else d


def wa_link(tel, msg):
    d = "".join(ch for ch in (tel or "") if ch.isdigit())
    if d and len(d) <= 11:
        d = "55" + d
    return "https://wa.me/%s?text=%s" % (d, quote(msg or "")) if d else ""


def get_lead(c, ref):
    if ref.startswith("n"):
        for l in nexora_leads():
            if l["id"] == ref:
                return l
        return None
    r = c.execute("SELECT * FROM leads WHERE id=?", (int(ref[1:]),)).fetchone()
    if not r:
        return None
    return dict(r, ref="c%d" % r["id"], id="c%d" % r["id"], score=score_crm(r), readonly=False)


# ---------- funil ----------
def board(conta, canal):
    cards = {e: [] for e in ETAPAS}
    if conta == "nexora" and canal == "email":
        for l in nexora_leads():
            cards[l["etapa"]].append(l)
        return {"etapas": ETAPAS, "cards": cards, "readonly": True}
    c = crm()
    for r in c.execute("SELECT * FROM leads WHERE conta=? AND canal=? ORDER BY id DESC", (conta, canal)):
        cards.setdefault(r["etapa"], []).append(dict(r, id="c%d" % r["id"], ref="c%d" % r["id"], sub=r["cidade"] or "", tag=r["fonte"] or "", score=score_crm(r), readonly=False))
    c.close()
    return {"etapas": ETAPAS, "cards": cards, "readonly": False}


def captacao(conta):
    c = crm()
    leads = []
    if conta == "nexora":
        leads += [l for l in nexora_leads() if l["etapa"] == "Pronto"]
    for r in c.execute("SELECT * FROM leads WHERE conta=? AND etapa IN ('Novo','Pronto') ORDER BY id DESC", (conta,)):
        sinais = (["sem site"] if not r["site"] else []) + (["com telefone"] if r["telefone"] else []) + ([r["tipo_dor"]] if r["tipo_dor"] else [])
        leads.append(dict(r, id="c%d" % r["id"], ref="c%d" % r["id"], sub=r["cidade"] or "", tag=r["fonte"] or "", score=score_crm(r), sinais=sinais, readonly=False))
    c.close()
    leads.sort(key=lambda x: -x["score"])
    return leads


# ---------- follow-ups ----------
def _modelo(c, conta, passo, nome):
    return c.execute("SELECT texto FROM modelos WHERE conta=? AND passo=?", (conta, passo)).fetchone()["texto"].replace("{nome}", nome)


def criar_followups(c, lead, base=None):
    base = base or datetime.now(timezone.utc).date()
    for i, dias in enumerate(FOLLOWUP_DIAS, 1):
        c.execute("INSERT OR IGNORE INTO tarefas (conta,canal,lead_ref,nome,telefone,email,passo,due_date,mensagem) VALUES (?,?,?,?,?,?,?,?,?)",
                  (lead["conta"], lead["canal"], lead["ref"], lead["nome"], lead.get("telefone"), lead.get("email"), i,
                   (base + timedelta(days=dias)).isoformat(), _modelo(c, lead["conta"], i, lead["nome"])))


def cancelar_tarefas(c, ref):
    c.execute("UPDATE tarefas SET status='cancelada' WHERE lead_ref=? AND status='pendente'", (ref,))


def sync_nexora_followups(c):
    ativos = set()
    for l in nexora_leads():
        if l["etapa"] == "Contatado" and l["sent_at"]:
            ativos.add(l["ref"])
            base = datetime.fromisoformat(l["sent_at"].replace("Z", "+00:00")).date()
            criar_followups(c, l, base)
        elif l["etapa"] in ("Respondeu", "Negociando", "Fechado", "Perdido"):
            cancelar_tarefas(c, l["ref"])
    c.commit()


def registrar_envio(c, lead, passo, origem):
    c.execute("INSERT INTO envios (lead_ref,conta,canal,passo,tipo_dor,enviado_em,origem) VALUES (?,?,?,?,?,?,?)",
              (lead["ref"], lead["conta"], lead["canal"], passo, lead.get("tipo_dor"), now(), origem))


def marcar_primeiro_envio(c, lead, origem):
    if lead["etapa"] not in ("Novo", "Pronto"):
        return False
    lid = int(lead["ref"][1:])
    c.execute("UPDATE leads SET etapa='Contatado', sent_at=?, updated_at=? WHERE id=?", (now(), now(), lid))
    lead = dict(lead, etapa="Contatado")
    criar_followups(c, lead)
    registrar_envio(c, lead, 0, origem)
    return True


def concluir_tarefa(c, tarefa_id, origem="manual", auto=0):
    t = c.execute("SELECT * FROM tarefas WHERE id=?", (tarefa_id,)).fetchone()
    if not t or t["status"] != "pendente":
        return
    c.execute("UPDATE tarefas SET status='feita', done_at=?, auto=? WHERE id=?", (now(), auto, tarefa_id))
    lead = get_lead(c, t["lead_ref"])
    registrar_envio(c, lead or {"ref": t["lead_ref"], "conta": t["conta"], "canal": t["canal"]}, t["passo"], origem)


def enviados_hoje(c, conta, canal):
    d = hoje()
    return (c.execute("SELECT COUNT(*) FROM envios WHERE conta=? AND canal=? AND substr(enviado_em,1,10)=?", (conta, canal, d)).fetchone()[0])


def hoje_view(conta):
    c = crm()
    if conta == "nexora":
        sync_nexora_followups(c)
    itens = []
    feitos = enviados_hoje(c, conta, "whatsapp")
    restante = max(WA_DAILY_CAP - feitos, 0)
    for r in c.execute("SELECT * FROM leads WHERE conta=? AND etapa='Pronto' AND sem_whatsapp=0 AND mensagem IS NOT NULL ORDER BY id", (conta,)):
        if r["canal"] == "whatsapp":
            if restante <= 0:
                continue
            restante -= 1
        itens.append({"tipo": "primeiro", "ref": "c%d" % r["id"], "lead_id": r["id"], "nome": r["nome"], "sub": r["cidade"] or "", "canal": r["canal"],
                      "telefone": r["telefone"], "email": r["email"], "assunto": r["assunto"], "mensagem": r["mensagem"],
                      "link": wa_link(r["telefone"], r["mensagem"]) if r["canal"] == "whatsapp" else "", "score": score_crm(r), "dor": r["dor"],
                      "aprovado": bool(r["aprovado"]), "passo": 0})
    for r in c.execute("SELECT * FROM tarefas WHERE conta=? AND status='pendente' AND due_date<=? ORDER BY due_date, id", (conta, hoje())):
        itens.append({"tipo": "followup", "ref": r["lead_ref"], "tarefa_id": r["id"], "nome": r["nome"], "sub": "Follow-up %d, previsto para %s" % (r["passo"], r["due_date"]),
                      "canal": r["canal"], "telefone": r["telefone"], "email": r["email"], "mensagem": r["mensagem"], "ia": bool(r["ia"]),
                      "link": wa_link(r["telefone"], r["mensagem"]) if r["canal"] == "whatsapp" else "", "passo": r["passo"], "atrasado": r["due_date"] < hoje()})
    stats = {"feitos": feitos, "cap": WA_DAILY_CAP, "pendentes": len(itens),
             "respostas_a_classificar": c.execute("SELECT COUNT(*) FROM respostas WHERE conta=? AND classificacao IS NULL", (conta,)).fetchone()[0],
             "followups_atrasados": sum(1 for i in itens if i.get("atrasado")),
             "interessados_sem_acao": c.execute("SELECT COUNT(*) FROM leads WHERE conta=? AND etapa='Respondeu'", (conta,)).fetchone()[0]
             + (sum(1 for l in nexora_leads() if l["etapa"] == "Respondeu") if conta == "nexora" else 0)}
    c.close()
    return {"itens": itens, "stats": stats}


# ---------- respostas (WhatsApp, Gmail, manual): move o card e cancela a sequencia ----------
def registrar_resposta(c, lead, texto, cls, traducao="", resumo="", origem="manual", message_id=None):
    ref, conta = lead["ref"], lead["conta"]
    c.execute("INSERT INTO respostas (lead_ref,conta,texto,traducao,classificacao,resumo,origem,message_id,canal,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (ref, conta, texto, traducao, cls, resumo, origem, message_id, lead.get("canal"), now()))
    if cls is not None:
        registrar_resposta_efeito(c, lead, cls)


def pendentes_de_classificar(c, limite=5):
    return c.execute("SELECT * FROM respostas WHERE classificacao IS NULL ORDER BY id LIMIT ?", (limite,)).fetchall()


def classificar_existente(c, resp_row, res):
    c.execute("UPDATE respostas SET classificacao=?, traducao=?, resumo=? WHERE id=?", (res["classificacao"], res["traducao"], res["resumo"], resp_row["id"]))
    lead = get_lead(c, resp_row["lead_ref"])
    if lead:
        registrar_resposta_efeito(c, lead, res["classificacao"])


def registrar_resposta_efeito(c, lead, cls):
    """Aplica so o efeito no funil de uma resposta ja gravada (usado ao classificar depois)."""
    tmp_ref = lead["ref"]
    if cls == "automatica":
        return
    cancelar_tarefas(c, tmp_ref)
    if tmp_ref.startswith("c"):
        nova = {"recusou": "Perdido", "bounce": "Perdido", "reuniao": "Negociando"}.get(cls, "Respondeu")
        c.execute("UPDATE leads SET etapa=?, updated_at=? WHERE id=? AND etapa<>'Fechado'", (nova, now(), int(tmp_ref[1:])))
        if cls in ("recusou", "bounce"):
            for chave in (lead.get("telefone"), lead.get("email")):
                if chave:
                    c.execute("INSERT OR IGNORE INTO bloqueios (conta,chave,motivo,created_at) VALUES (?,?,?,?)", (lead["conta"], chave, cls, now()))


def achar_lead_por_telefone(c, telefone):
    k = phone_key(telefone)
    if not k:
        return None
    for r in c.execute("SELECT * FROM leads WHERE telefone IS NOT NULL AND canal='whatsapp' ORDER BY id DESC"):
        if phone_key(r["telefone"]) == k:
            return dict(r, ref="c%d" % r["id"], id="c%d" % r["id"], readonly=False)
    return None


def followup_devido_para(c, ref):
    return c.execute("SELECT id FROM tarefas WHERE lead_ref=? AND status='pendente' AND due_date<=? ORDER BY passo LIMIT 1", (ref, hoje())).fetchone()


# ---------- radar ----------
def radar(conta):
    c = crm()
    lim24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    lim14 = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    sem_retorno, esfriando, devolvidos = [], [], []
    for r in c.execute("SELECT * FROM leads WHERE conta=? AND etapa IN ('Respondeu','Negociando') AND updated_at<? ORDER BY updated_at", (conta, lim24)):
        sem_retorno.append({"ref": "c%d" % r["id"], "nome": r["nome"], "canal": r["canal"], "desde": r["updated_at"], "etapa": r["etapa"]})
    for r in c.execute("SELECT * FROM leads WHERE conta=? AND etapa='Contatado' AND sent_at<? ORDER BY sent_at", (conta, lim14)):
        pend = c.execute("SELECT COUNT(*) FROM tarefas WHERE lead_ref=? AND status='pendente'", ("c%d" % r["id"],)).fetchone()[0]
        if not pend:
            esfriando.append({"ref": "c%d" % r["id"], "nome": r["nome"], "canal": r["canal"], "desde": r["sent_at"]})
    for r in c.execute("SELECT * FROM respostas WHERE conta=? AND classificacao='bounce' ORDER BY id DESC LIMIT 30", (conta,)):
        devolvidos.append({"ref": r["lead_ref"], "nome": (get_lead(c, r["lead_ref"]) or {}).get("nome", r["lead_ref"]), "desde": r["created_at"]})
    if conta == "nexora":
        for l in nexora_leads():
            if l["etapa"] in ("Respondeu", "Negociando") and l.get("responded_at") and l["responded_at"] < lim24:
                sem_retorno.append({"ref": l["ref"], "nome": l["nome"], "canal": "email", "desde": l["responded_at"], "etapa": l["etapa"]})
    c.close()
    return {"sem_retorno": sem_retorno, "esfriando": esfriando, "devolvidos": devolvidos}


# ---------- aprendizado ----------
def aprendizado(conta):
    c = crm()
    envios = c.execute("SELECT * FROM envios WHERE conta=? AND passo=0", (conta,)).fetchall()
    respondidas = {}
    for r in c.execute("SELECT lead_ref, classificacao, MIN(created_at) t FROM respostas WHERE conta=? AND classificacao NOT IN ('automatica','bounce') GROUP BY lead_ref", (conta,)):
        respondidas[r["lead_ref"]] = r["classificacao"]
    if conta == "nexora":
        for l in nexora_leads():
            if l["etapa"] in ("Respondeu", "Negociando", "Fechado", "Perdido") and l.get("sent_at") and l["ref"] not in respondidas:
                respondidas[l["ref"]] = "interessado" if l["etapa"] in ("Respondeu", "Negociando", "Fechado") else "recusou"

    def agrupar(chave):
        g = {}
        for e in envios:
            k = chave(e) or "sem_dado"
            b = g.setdefault(k, {"envios": 0, "respostas": 0, "interessados": 0})
            b["envios"] += 1
            cl = respondidas.get(e["lead_ref"])
            if cl:
                b["respostas"] += 1
                if cl in ("interessado", "duvida", "reuniao"):
                    b["interessados"] += 1
        return [{"chave": k, **v, "taxa": round(v["respostas"] / v["envios"] * 100) if v["envios"] else 0} for k, v in sorted(g.items(), key=lambda kv: -kv[1]["envios"])]

    def hora(e):
        try:
            return "%02dh" % datetime.fromisoformat(e["enviado_em"]).hour
        except ValueError:
            return None

    objecoes = [dict(r) for r in c.execute("SELECT texto, traducao, resumo, created_at FROM respostas WHERE conta=? AND classificacao='recusou' ORDER BY id DESC LIMIT 20", (conta,))]
    propostas = [dict(r) for r in c.execute("SELECT * FROM propostas WHERE conta=? ORDER BY id DESC LIMIT 20", (conta,))]
    seg = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    semana = {"envios": sum(1 for e in envios if e["enviado_em"] >= seg), "respostas_novas": c.execute("SELECT COUNT(*) FROM respostas WHERE conta=? AND created_at>=?", (conta, seg)).fetchone()[0]}
    out = {"por_canal": agrupar(lambda e: e["canal"]), "por_dor": agrupar(lambda e: e["tipo_dor"]), "por_hora": agrupar(hora),
           "objecoes": objecoes, "propostas": propostas, "semana": semana, "total_envios": len(envios)}
    c.close()
    return out


# ---------- financeiro ----------
def financeiro(conta):
    c = crm()
    mes = hoje()[:7]
    pags = [dict(r) for r in c.execute("SELECT * FROM pagamentos WHERE conta=? ORDER BY COALESCE(pago_em, vencimento, created_at) DESC", (conta,))]
    recebido = sum(p["valor_centavos"] for p in pags if p["status"] == "pago" and (p["pago_em"] or "")[:7] == mes)
    a_receber = sum(p["valor_centavos"] for p in pags if p["status"] == "a_receber")
    meta = c.execute("SELECT valor_centavos FROM metas WHERE conta=? AND mes=?", (conta, mes)).fetchone()
    servicos = [dict(r) for r in c.execute("SELECT * FROM servicos WHERE conta=? ORDER BY nome", (conta,))]
    c.close()
    return {"pagamentos": pags, "recebido_mes": recebido, "a_receber": a_receber, "meta": meta[0] if meta else 0, "servicos": servicos, "moeda": "USD" if conta == "nexora" else "BRL"}


def stats(conta):
    c = crm()
    out = {"whatsapp_hoje": enviados_hoje(c, conta, "whatsapp"), "wa_cap": WA_DAILY_CAP, "email_hoje": enviados_hoje(c, conta, "email"), "email_cap": EMAIL_DAILY_CAP}
    for canal in CANAIS:
        out[canal] = {r["etapa"]: r["n"] for r in c.execute("SELECT etapa, COUNT(*) n FROM leads WHERE conta=? AND canal=? GROUP BY etapa", (conta, canal))}
    out["respostas"] = {r["classificacao"] or "sem": r["n"] for r in c.execute("SELECT classificacao, COUNT(*) n FROM respostas WHERE conta=? GROUP BY 1", (conta,))}
    c.close()
    if conta == "nexora":
        cards = {}
        for l in nexora_leads():
            cards[l["etapa"]] = cards.get(l["etapa"], 0) + 1
        out["email"] = cards
    return out
