"""Rotinas automaticas de longa duracao: captacao, analise profunda de dor, adaptacao de follow-up, revisao semanal."""
import json

import ia
import store


def _job(c, tipo, conta, status, detalhe=""):
    cur = c.execute("INSERT INTO jobs (tipo,conta,status,detalhe,created_at,updated_at) VALUES (?,?,?,?,?,?)", (tipo, conta, status, detalhe, store.now(), store.now()))
    c.commit()
    return cur.lastrowid


def _job_fim(c, jid, status, detalhe):
    c.execute("UPDATE jobs SET status=?, detalhe=?, updated_at=? WHERE id=?", (status, detalhe[:500], store.now(), jid))
    c.commit()


def conhecidos(c, conta):
    nomes = [r[0] for r in c.execute("SELECT nome FROM leads WHERE conta=?", (conta,))]
    if conta == "nexora":
        nomes += [l["nome"] for l in store.nexora_leads()]
    return nomes


def eh_celular(tel):
    d = "".join(ch for ch in (tel or "") if ch.isdigit())
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    return len(d) >= 10 and d[2] in "6789"


def inserir_lead_captado(c, conta, d):
    nome = (d.get("nome") or "").strip()
    if not nome:
        return False
    tel, email = d.get("telefone"), (d.get("email") or "").lower() or None
    if c.execute("SELECT 1 FROM leads WHERE conta=? AND lower(nome)=?", (conta, nome.lower())).fetchone():
        return False
    if email and c.execute("SELECT 1 FROM leads WHERE conta=? AND lower(email)=?", (conta, email)).fetchone():
        return False
    if tel and store.achar_lead_por_telefone(c, tel):
        return False
    for chave in (tel, email):
        if chave and c.execute("SELECT 1 FROM bloqueios WHERE conta=? AND chave=?", (conta, chave)).fetchone():
            return False
    canal = "whatsapp" if tel and conta == "atlas" else ("email" if email else None)
    if not canal:
        return False
    ts = store.now()
    fixo = 1 if canal == "whatsapp" and not eh_celular(tel) else 0
    c.execute("INSERT INTO leads (conta,canal,etapa,nome,telefone,email,cidade,site,fonte,nota_google,avaliacoes,sem_whatsapp,notas,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (conta, canal, "Novo", nome, tel, email, d.get("cidade"), d.get("site"), "apify:google-maps", d.get("nota_google"), d.get("avaliacoes"), fixo,
               "Telefone fixo: sem WhatsApp, contato so por ligacao" if fixo else None, ts, ts))
    return True


def captar_job(conta, cidade, categoria, quantidade):
    c = store.crm()
    jid = _job(c, "captacao", conta, "rodando", "%s em %s" % (categoria, cidade))
    try:
        achados = ia.captar(conta, cidade, categoria, quantidade, conhecidos(c, conta))
        novos = sum(1 for d in achados if inserir_lead_captado(c, conta, d))
        c.commit()
        _job_fim(c, jid, "ok", "%d encontrados, %d novos" % (len(achados), novos))
    except Exception as e:
        _job_fim(c, jid, "erro", str(e))
    finally:
        c.close()


def analisar_lead(lid):
    c = store.crm()
    r = c.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
    if not r:
        c.close()
        return
    jid = _job(c, "analise", r["conta"], "rodando", r["nome"])
    try:
        d = ia.analyze_lead({k: r[k] for k in ("nome", "cidade", "site", "telefone", "email", "avaliacoes", "nota_google", "fonte", "notas")})
        campo = "email" if r["canal"] == "email" else "mensagem"
        mensagem = d.get(campo)
        reprovada = (d.get("violacoes") or {}).get(campo)
        nota = r["notas"]
        if reprovada:                       # a mensagem quebra as regras de copy: nao entra na fila
            mensagem = None
            nota = ((nota or "") + "\nMensagem reprovada nas regras: " + "; ".join(reprovada)).strip()
        etapa = "Pronto" if (mensagem and r["etapa"] == "Novo") else r["etapa"]
        c.execute("UPDATE leads SET dor=?, tipo_dor=?, criterios_json=?, mensagem=?, assunto=COALESCE(?, assunto), etapa=?, notas=?, updated_at=? WHERE id=?",
                  (d.get("dor"), d.get("tipo_dor"), json.dumps({"criterios": d.get("criterios"), "evidencias": d.get("evidencias")}, ensure_ascii=False),
                   mensagem, d.get("assunto"), etapa, nota, store.now(), lid))
        c.commit()
        _job_fim(c, jid, "aviso" if reprovada else "ok", ("MENSAGEM REPROVADA: " + "; ".join(reprovada)) if reprovada else (d.get("dor") or ""))
    except Exception as e:
        c.execute("UPDATE leads SET dor=COALESCE(dor,'(analise falhou, tente de novo)') WHERE id=?", (lid,))
        c.commit()
        _job_fim(c, jid, "erro", str(e))
    finally:
        c.close()


def proximo_para_analise(c):
    r = c.execute("SELECT id FROM leads WHERE etapa='Novo' AND dor IS NULL AND NOT (sem_whatsapp=1 AND email IS NULL) ORDER BY id LIMIT 1").fetchone()
    return r["id"] if r else None


def adaptar_followup():
    """Reescreve com IA (adaptado a dor e ao historico) um follow-up ainda em texto padrao que vence em ate 2 dias."""
    c = store.crm()
    try:
        limite = (store.datetime.now(store.timezone.utc).date() + store.timedelta(days=2)).isoformat()
        t = c.execute("SELECT * FROM tarefas WHERE status='pendente' AND ia=0 AND due_date<=? ORDER BY due_date LIMIT 1", (limite,)).fetchone()
        if not t:
            return False
        lead = store.get_lead(c, t["lead_ref"])
        if not lead:
            c.execute("UPDATE tarefas SET ia=2 WHERE id=?", (t["id"],))
            c.commit()
            return True
        resumo = {k: lead.get(k) for k in ("nome", "cidade", "site", "avaliacoes", "dor", "tipo_dor", "sub") if lead.get(k)}
        hist = (lead.get("mensagem") or lead.get("nota") or "")
        try:
            texto = ia.generate_followup(resumo, t["passo"], t["canal"], t["conta"], hist)
            c.execute("UPDATE tarefas SET mensagem=?, ia=1 WHERE id=?", (texto, t["id"]))
        except Exception:
            c.execute("UPDATE tarefas SET ia=2 WHERE id=?", (t["id"],))
        c.commit()
        return True
    finally:
        c.close()


def revisar_semana(conta):
    c = store.crm()
    jid = _job(c, "revisao", conta, "rodando", "revisao semanal de scripts")
    try:
        dados = store.aprendizado(conta)
        dados["respostas_recentes"] = [dict(r) for r in c.execute("SELECT classificacao, texto, resumo FROM respostas WHERE conta=? ORDER BY id DESC LIMIT 25", (conta,))]
        props = ia.weekly_review(dados)
        for p in props[:4]:
            c.execute("INSERT INTO propostas (conta,titulo,evidencia,ajuste,created_at) VALUES (?,?,?,?,?)", (conta, p.get("titulo"), p.get("evidencia"), p.get("ajuste_sugerido"), store.now()))
        c.commit()
        _job_fim(c, jid, "ok", "%d propostas" % len(props[:4]))
    except Exception as e:
        _job_fim(c, jid, "erro", str(e))
    finally:
        c.close()
