"""Dados do painel: indicadores, serie temporal, funil de conversao, canais, dores, acoes do dia e conversas.

Regra de honestidade: so mostra o que existe nos dados. Sem amostra suficiente, devolve `insuficiente: True`
e nunca estima nem inventa numeros. A Nexora nao guarda data de negociacao/fechamento no banco original, entao
essas series so contam o que o CRM registrou desde que passou a acompanhar (campo `parcial`).
"""
from datetime import datetime, timedelta, timezone

import store

ETAPAS_FUNIL = ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado"]
RANK = {e: i for i, e in enumerate(ETAPAS_FUNIL)}
AMOSTRA_MINIMA = 5


def pct(parte, total):
    """Percentual inteiro com arredondamento comum (62,5 vira 63; o round() do Python arredonda para o par)."""
    return int(parte * 100 / total + 0.5) if total else None


def _dia(iso):
    return iso[:10] if iso else None


def _leads_unificados(c, conta):
    """Uma linha por lead (CRM e Nexora) com a etapa mais avancada alcancada e as datas dos marcos conhecidos."""
    ev = {}
    for r in c.execute("SELECT lead_ref, para_etapa, MIN(ts) ts FROM eventos WHERE conta=? GROUP BY lead_ref, para_etapa", (conta,)):
        ev.setdefault(r["lead_ref"], {})[r["para_etapa"]] = r["ts"]
    resp = {r["lead_ref"]: r["ts"] for r in c.execute(
        "SELECT lead_ref, MIN(created_at) ts FROM respostas WHERE conta=? AND COALESCE(classificacao,'') NOT IN ('automatica','bounce') GROUP BY lead_ref", (conta,))}
    out = []
    for r in c.execute("SELECT * FROM leads WHERE conta=?", (conta,)):
        ref = "c%d" % r["id"]
        e = ev.get(ref, {})
        rank = RANK.get(r["etapa"], 0) if r["etapa"] != "Perdido" else 0
        for et in e:
            rank = max(rank, RANK.get(et, 0))
        if r["sent_at"]:
            rank = max(rank, 2)
        if resp.get(ref):
            rank = max(rank, 3)
        out.append({"ref": ref, "canal": r["canal"], "etapa": r["etapa"], "rank": rank, "criado": r["created_at"], "contatado": e.get("Contatado") or r["sent_at"],
                    "respondeu": resp.get(ref) or e.get("Respondeu"), "negociando": e.get("Negociando"), "fechado": e.get("Fechado"), "tipo_dor": r["tipo_dor"]})
    if conta == "nexora":
        for l in store.nexora_leads():
            neg, raw = l.get("neg"), l.get("status_raw")
            rank = 1
            if l.get("sent_at"):
                rank = 2
            if raw == "respondido" or l.get("responded_at") or neg in ("respondido", "em_negociacao", "fechado"):
                rank = 3
            if neg == "em_negociacao":
                rank = 4
            if neg == "fechado":
                rank = 5
            out.append({"ref": l["ref"], "canal": "email", "etapa": l["etapa"], "rank": rank, "criado": l.get("created_at"), "contatado": l.get("sent_at"),
                        "respondeu": l.get("responded_at"), "negociando": None, "fechado": None, "tipo_dor": l.get("tipo_dor")})
    return out


def _serie(leads, dias):
    hoje = datetime.now(timezone.utc).date()
    datas = [(hoje - timedelta(days=dias - 1 - i)).isoformat() for i in range(dias)]
    idx = {d: i for i, d in enumerate(datas)}
    campos = {"leads": "criado", "contatos": "contatado", "respostas": "respondeu", "negociacoes": "negociando", "fechamentos": "fechado"}
    serie = {k: [0] * dias for k in campos}
    for l in leads:
        for k, campo in campos.items():
            d = _dia(l.get(campo))
            if d in idx:
                serie[k][idx[d]] += 1
    return datas, serie


def painel(conta, dias=30):
    c = store.crm()
    try:
        leads = _leads_unificados(c, conta)
        n = [sum(1 for l in leads if l["rank"] >= k) for k in range(6)]
        perdidos = [sum(1 for l in leads if l["etapa"] == "Perdido" and l["rank"] == k) for k in range(6)]
        funil = []
        for k, etapa in enumerate(ETAPAS_FUNIL):
            ant = n[k - 1] if k else None
            funil.append({"etapa": etapa, "n": n[k], "conv": pct(n[k], ant), "perdidos": perdidos[k]})
        datas, serie = _serie(leads, dias)
        metade = dias // 2
        tendencia = {k: (sum(v[metade:]) - sum(v[:metade])) for k, v in serie.items()}
        canais = []
        for canal in ("whatsapp", "email"):
            ls = [l for l in leads if l["canal"] == canal]
            cont = sum(1 for l in ls if l["rank"] >= 2)
            resp = sum(1 for l in ls if l["rank"] >= 3)
            canais.append({"canal": canal, "leads": len(ls), "contatados": cont, "respostas": resp, "negociacoes": sum(1 for l in ls if l["rank"] >= 4),
                           "taxa": pct(resp, cont) if cont >= AMOSTRA_MINIMA else None, "insuficiente": cont < AMOSTRA_MINIMA})
        por_dor = {}
        for l in leads:
            if l["rank"] >= 2:
                d = l["tipo_dor"] or "sem_dado"
                b = por_dor.setdefault(d, {"dor": d, "contatados": 0, "respostas": 0})
                b["contatados"] += 1
                b["respostas"] += 1 if l["rank"] >= 3 else 0
        dores = sorted(por_dor.values(), key=lambda x: -x["contatados"])
        for d in dores:
            d["taxa"] = pct(d["respostas"], d["contatados"]) if d["contatados"] >= AMOSTRA_MINIMA else None
            d["insuficiente"] = d["contatados"] < AMOSTRA_MINIMA
        rd = store.radar(conta)
        return {
            "kpis": {"leads": n[0], "contatados": n[2], "respostas": n[3], "negociacoes": n[4], "fechados": n[5], "perdidos": sum(1 for l in leads if l["etapa"] == "Perdido")},
            "tendencia": tendencia, "datas": datas, "serie": serie, "funil": funil, "canais": canais, "dores": dores,
            "radar": {"sem_retorno": len(rd["sem_retorno"]), "esfriando": len(rd["esfriando"]), "devolvidos": len(rd["devolvidos"])},
            "serie_suficiente": sum(serie["contatos"]) + sum(serie["respostas"]) >= AMOSTRA_MINIMA,
            "parcial": conta == "nexora",
        }
    finally:
        c.close()


# ---------- acoes do dia ----------
def aguardando_resposta_nossa(c, conta):
    """Leads cuja ultima resposta e mais nova do que a ultima coisa que enviamos: a bola esta com a gente."""
    itens = []
    for r in c.execute("SELECT lead_ref, MAX(created_at) ts FROM respostas WHERE conta=? AND COALESCE(classificacao,'') NOT IN ('automatica','bounce') GROUP BY lead_ref", (conta,)):
        ref = r["lead_ref"]
        saida = c.execute("SELECT MAX(enviado_em) ts FROM envios WHERE lead_ref=?", (ref,)).fetchone()["ts"]
        if saida and saida >= r["ts"]:
            continue
        lead = store.get_lead(c, ref)
        if not lead or lead["etapa"] not in ("Respondeu", "Negociando"):
            continue
        ult = c.execute("SELECT texto, traducao, classificacao, resumo, canal FROM respostas WHERE lead_ref=? ORDER BY id DESC LIMIT 1", (ref,)).fetchone()
        itens.append({"categoria": "responder", "ref": ref, "nome": lead["nome"], "canal": lead.get("canal") or ult["canal"], "etapa": lead["etapa"], "desde": r["ts"],
                      "email": lead.get("email"), "telefone": lead.get("telefone"),
                      "classificacao": ult["classificacao"], "resumo": ult["resumo"], "texto": (ult["traducao"] or ult["texto"] or "")[:200], "prioridade": 0 if lead["etapa"] == "Negociando" else 1})
    itens.sort(key=lambda x: (x["prioridade"], x["desde"]))
    return itens


def acoes(conta):
    base = store.hoje_view(conta)
    c = store.crm()
    try:
        responder = aguardando_resposta_nossa(c, conta)
        wa = [dict(i, categoria="whatsapp") for i in base["itens"] if i["tipo"] == "primeiro" and i["canal"] == "whatsapp"]
        follow = [dict(i, categoria="followup") for i in base["itens"] if i["tipo"] == "followup"]
        aprovar = []
        for r in c.execute("SELECT * FROM leads WHERE conta=? AND canal='email' AND etapa='Pronto' AND aprovado=0 AND mensagem IS NOT NULL ORDER BY id", (conta,)):
            aprovar.append({"categoria": "aprovar_email", "ref": "c%d" % r["id"], "lead_id": r["id"], "nome": r["nome"], "canal": "email", "assunto": r["assunto"], "mensagem": r["mensagem"],
                            "dor": r["dor"], "score": store.score_crm(r)})
        if conta == "nexora":
            for l in store.nexora_leads():
                if l["etapa"] == "Pronto" and not l["aprovado"]:
                    aprovar.append({"categoria": "aprovar_email", "ref": l["ref"], "nome": l["nome"], "canal": "email", "assunto": l.get("assunto") or l.get("nota"), "score": l["score"],
                                    "dor": l.get("tipo_dor"), "nexora": True, "lead_id": int(l["ref"][1:])})
        revisar = []
        for r in c.execute("SELECT * FROM leads WHERE conta=? AND etapa='Novo' AND (notas LIKE '%reprovada%' OR (dor IS NOT NULL AND mensagem IS NULL)) ORDER BY id", (conta,)):
            revisar.append({"categoria": "revisar", "ref": "c%d" % r["id"], "lead_id": r["id"], "nome": r["nome"], "canal": r["canal"], "dor": r["dor"], "motivo": (r["notas"] or "").strip()[-160:] or "sem mensagem"})
        resumo = {"responder": len(responder), "whatsapp": len(wa), "aprovar_email": len(aprovar), "revisar": len(revisar), "followup": len(follow)}
        return {"resumo": resumo, "total": sum(resumo.values()), "responder": responder, "whatsapp": wa, "aprovar_email": aprovar[:40], "aprovar_ids": [x["lead_id"] for x in aprovar], "revisar": revisar, "followup": follow,
                "stats": base["stats"]}
    finally:
        c.close()


# ---------- conversas de WhatsApp ----------
def conversas_whatsapp(conta):
    c = store.crm()
    try:
        out = []
        for r in c.execute("""SELECT w.lead_ref, MAX(w.id) ult, COUNT(*) n FROM wa_mensagens w JOIN leads l ON ('c' || l.id) = w.lead_ref
                              WHERE l.conta=? GROUP BY w.lead_ref ORDER BY ult DESC""", (conta,)):
            lead = store.get_lead(c, r["lead_ref"])
            m = c.execute("SELECT direcao, texto, created_at FROM wa_mensagens WHERE id=?", (r["ult"],)).fetchone()
            resp = c.execute("SELECT classificacao FROM respostas WHERE lead_ref=? ORDER BY id DESC LIMIT 1", (r["lead_ref"],)).fetchone()
            out.append({"ref": r["lead_ref"], "nome": lead["nome"], "telefone": lead.get("telefone"), "etapa": lead["etapa"], "mensagens": r["n"], "ultima": m["texto"][:120],
                        "direcao": m["direcao"], "quando": m["created_at"], "classificacao": resp["classificacao"] if resp else None, "aguardando_voce": m["direcao"] == "entrada"})
        return out
    finally:
        c.close()
