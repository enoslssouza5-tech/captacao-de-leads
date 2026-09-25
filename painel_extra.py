"""Radar completo, aprendizado detalhado e financeiro detalhado. Supersets dos endpoints antigos (as chaves antigas continuam)."""
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone

import painel
import store

DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
AMOSTRA = 10


def _dt(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# ---------------- radar ----------------
def radar_completo(conta):
    base = store.radar(conta)
    agora = datetime.now(timezone.utc)
    c = store.crm()
    try:
        espera = painel.aguardando_resposta_nossa(c, conta)
        urgente, sem_retorno = [], []
        for i in espera:
            d = _dt(i["desde"])
            horas = (agora - d).total_seconds() / 3600 if d else 0
            item = {"ref": i["ref"], "nome": i["nome"], "canal": i["canal"], "desde": i["desde"], "horas": int(horas), "etapa": i["etapa"], "resumo": i["resumo"] or i["texto"][:100],
                    "classificacao": i["classificacao"]}
            if (i["etapa"] == "Negociando" and horas >= 4) or horas >= 48:
                urgente.append(item)
            elif horas >= 24:
                sem_retorno.append(item)
        atrasados = []
        for r in c.execute("SELECT * FROM tarefas WHERE conta=? AND status='pendente' AND due_date<? ORDER BY due_date", (conta, store.hoje())):
            dias = (datetime.now(timezone.utc).date() - datetime.fromisoformat(r["due_date"]).date()).days
            atrasados.append({"ref": r["lead_ref"], "nome": r["nome"], "canal": r["canal"], "passo": r["passo"], "dias_atraso": dias})
    finally:
        c.close()
    return {"urgente": urgente, "sem_retorno": sem_retorno, "followup_atrasado": atrasados, "esfriando": base["esfriando"], "devolvidos": base["devolvidos"],
            "total": len(urgente) + len(sem_retorno) + len(atrasados) + len(base["esfriando"]) + len(base["devolvidos"])}


# ---------------- aprendizado ----------------
def _abordagem_nexora():
    conn = store.nexora_ro()
    if not conn:
        return []
    try:
        rows = conn.execute("""SELECT COALESCE(ab_variant,'sem_variacao') v,
                                      SUM(CASE WHEN sent_at IS NOT NULL THEN 1 ELSE 0 END) contatados,
                                      SUM(CASE WHEN sent_at IS NOT NULL AND (status='respondido' OR responded_at IS NOT NULL) THEN 1 ELSE 0 END) respostas
                               FROM leads GROUP BY 1""").fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    out = []
    for r in rows:
        if r["contatados"]:
            out.append({"chave": {"A": "Variacao A (diagnostico)", "B": "Variacao B (oportunidade)"}.get(r["v"], r["v"]), "contatados": r["contatados"], "respostas": r["respostas"],
                        "taxa": painel.pct(r["respostas"], r["contatados"]) if r["contatados"] >= painel.AMOSTRA_MINIMA else None, "insuficiente": r["contatados"] < painel.AMOSTRA_MINIMA})
    return out


def aprendizado_completo(conta, tz_min=0):
    a = store.aprendizado(conta)
    c = store.crm()
    try:
        respondidos = {r["lead_ref"] for r in c.execute("SELECT DISTINCT lead_ref FROM respostas WHERE conta=? AND COALESCE(classificacao,'') NOT IN ('automatica','bounce')", (conta,))}
        envios = c.execute("SELECT lead_ref, enviado_em FROM envios WHERE conta=? AND passo=0", (conta,)).fetchall()
        horas, semana = Counter(), Counter()
        horas_r, semana_r = Counter(), Counter()
        for e in envios:
            d = _dt(e["enviado_em"])
            if not d:
                continue
            loc = d + timedelta(minutes=tz_min)
            horas[loc.hour] += 1
            semana[loc.weekday()] += 1
            if e["lead_ref"] in respondidos:
                horas_r[loc.hour] += 1
                semana_r[loc.weekday()] += 1
        n = len(envios)
        por_hora = [{"chave": "%02dh" % h, "hora": h, "envios": horas[h], "respostas": horas_r[h], "taxa": painel.pct(horas_r[h], horas[h]) if horas[h] else None} for h in range(24)]
        por_dia = [{"chave": DIAS[i], "envios": semana[i], "respostas": semana_r[i], "taxa": painel.pct(semana_r[i], semana[i]) if semana[i] else None} for i in range(7)]
        grupos = Counter()
        exemplos = {}
        for r in c.execute("SELECT resumo, traducao, texto FROM respostas WHERE conta=? AND classificacao='recusou'", (conta,)):
            chave = (r["resumo"] or r["traducao"] or r["texto"] or "sem detalhe").strip().lower()[:90]
            grupos[chave] += 1
            exemplos.setdefault(chave, (r["resumo"] or r["traducao"] or r["texto"] or "sem detalhe").strip()[:120])
        objecoes_top = [{"motivo": exemplos[k], "n": v} for k, v in grupos.most_common(5)]
    finally:
        c.close()
    a.update({"por_hora": por_hora, "por_dia_semana": por_dia, "amostra_minima": AMOSTRA, "insuficiente_horario": n < AMOSTRA,
              "por_abordagem": _abordagem_nexora() if conta == "nexora" else [], "objecoes_top": objecoes_top})
    return a


# ---------------- financeiro ----------------
def financeiro_completo(conta):
    f = store.financeiro(conta)
    mes = store.hoje()[:7]
    pagos = [p for p in f["pagamentos"] if p["status"] == "pago"]
    pagos_mes = [p for p in pagos if (p["pago_em"] or "")[:7] == mes]
    c = store.crm()
    try:
        meses = []
        d = datetime.now(timezone.utc).date().replace(day=1)
        for _ in range(6):
            meses.append(d.strftime("%Y-%m"))
            d = (d - timedelta(days=1)).replace(day=1)
        meses.reverse()
        futuros = []
        d = datetime.now(timezone.utc).date().replace(day=1)
        for _ in range(3):
            d = (d + timedelta(days=32)).replace(day=1)
            futuros.append(d.strftime("%Y-%m"))
        serie = []
        for m in meses + futuros:
            recebido = sum(p["valor_centavos"] for p in pagos if (p["pago_em"] or "")[:7] == m)
            a_receber = sum(p["valor_centavos"] for p in f["pagamentos"] if p["status"] == "a_receber" and (p["vencimento"] or "")[:7] == m)
            serie.append({"mes": m, "recebido": recebido, "a_receber": a_receber, "futuro": m in futuros})
        origens = Counter()
        for p in pagos:
            ref = p.get("lead_ref")
            origem = "Sem origem informada"
            if ref:
                lead = store.get_lead(c, ref)
                if lead:
                    origem = "%s (%s)" % ("WhatsApp" if lead.get("canal") == "whatsapp" else "E-mail", lead.get("fonte") or "sem fonte")
            origens[origem] += p["valor_centavos"]
    finally:
        c.close()
    f.update({
        "meta_pct": painel.pct(f["recebido_mes"], f["meta"]) if f["meta"] else None,
        "ticket_medio": int(sum(p["valor_centavos"] for p in pagos) / len(pagos)) if pagos else None,
        "fechamentos_mes": len(pagos_mes), "fechamentos_total": len(pagos),
        "serie": serie, "origens": [{"origem": k, "valor": v} for k, v in origens.most_common()],
    })
    return f
