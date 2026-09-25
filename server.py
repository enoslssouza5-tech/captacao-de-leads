"""CRM unificado (Nexora + Atlas, e-mail + WhatsApp). 100% local e gratuito.

- Leads de e-mail da Nexora: leitura do SQLite existente; respostas e follow-ups sao aplicados nele pelo modulo mail.
- WhatsApp: observador somente leitura (wa-watcher). Detecta envios e respostas sozinho. NUNCA envia mensagem.
- IA via `claude -p` local. Workers em segundo plano (workers.py) cuidam de Gmail, IA, captacao, envio e backup.

Uso: python server.py   (http://127.0.0.1:4400, so acessivel na propria maquina)
"""
import json
import os
import re
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import mail  # noqa: F401  (ajusta o sys.path para os modulos do Nexora)
import gmail_ui
import backup
import ia
import nexora_ops
import painel
import painel_extra
import pipeline
import regras
import store
import workers
from store import CONTAS, CANAIS, ETAPAS, CLASSES, crm, now
from workers import WAM, spawn, log

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "4400"))
STATIC = {"/": "index.html", "/index.html": "index.html"}
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}


def wa_evento(d):
    """Evento vindo do observador: envio detectado ou resposta recebida. So guarda conversa de numeros que sao leads."""
    c = crm()
    try:
        lead = store.achar_lead_por_telefone(c, d.get("telefone"))
        if not lead:
            return {"ignorado": True}
        c.execute("INSERT INTO wa_mensagens (lead_ref, direcao, texto, tipo, ts_msg, created_at) VALUES (?,?,?,?,?,?)",
                  (lead["ref"], d.get("direcao"), (d.get("texto") or "")[:4000], d.get("tipo"), d.get("ts"), now()))
        if d.get("direcao") == "saida":
            if lead["etapa"] in ("Novo", "Pronto"):
                store.marcar_primeiro_envio(c, lead, "whatsapp_auto")
            else:
                t = store.followup_devido_para(c, lead["ref"])
                if t:
                    store.concluir_tarefa(c, t["id"], "whatsapp_auto", 1)
                else:
                    store.registrar_envio(c, lead, 99, "whatsapp_manual")      # resposta/conversa do usuario: zera "aguardando voce"
            c.commit()
            return {"ok": True, "acao": "envio_detectado"}
        store.registrar_resposta(c, lead, d.get("texto") or "", None, origem="whatsapp")
        c.commit()
        spawn(mail.reclassificar)
        return {"ok": True, "acao": "resposta_registrada"}
    finally:
        c.close()


# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _seguro(self, escrita):
        """Bloqueia CSRF e DNS rebinding: so aceita Host local, Origin local (quando existir) e JSON nas escritas."""
        host = (self.headers.get("Host") or "").lower()
        porta = self.server.server_address[1]
        aceitos = {"127.0.0.1:%d" % porta, "localhost:%d" % porta}
        if host not in aceitos:
            self.send(403, {"erro": "host nao permitido"})
            return False
        origem = self.headers.get("Origin")
        if origem and origem.lower() not in {"http://" + a for a in aceitos}:
            self.send(403, {"erro": "origem nao permitida"})
            return False
        if escrita and not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            self.send(415, {"erro": "use application/json"})
            return False
        return True

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            return {}

    def do_GET(self):
        if not self._seguro(False):
            return
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        alvo = STATIC.get(u.path)
        if alvo is None and re.fullmatch(r"/(js/[a-z0-9\-]+\.js|css/[a-z0-9\-]+\.css)", u.path):
            alvo = u.path[1:]
        if alvo:
            arq = os.path.join(HERE, alvo)
            if not os.path.isfile(arq):
                return self.send(404, {"erro": "nao encontrado"})
            with open(arq, "rb") as fh:
                return self.send(200, fh.read(), MIME[os.path.splitext(alvo)[1]])
        conta, canal = q.get("conta"), q.get("canal")
        if u.path == "/api/ping":
            c = crm()
            ult = c.execute("SELECT COALESCE(MAX(id),0) FROM respostas").fetchone()[0]
            ult_cls = c.execute("SELECT texto, classificacao, lead_ref FROM respostas ORDER BY id DESC LIMIT 1").fetchone()
            c.close()
            return self.send(200, {"ultima_resposta": ult, "ultima": dict(ult_cls) if ult_cls else None, "wa": WAM.estado})
        if u.path == "/api/conexoes":
            c = crm()
            cfg = {k: store.cfg_get(c, k, d) for k, d in (("auto_followup_email_nexora", "0"), ("auto_followup_email_atlas", "0"), ("auto_analisar", "1"), ("captar_atlas", ""))}
            jobs = [dict(r) for r in c.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 12")]
            c.close()
            return self.send(200, {"whatsapp": WAM.publico(), "gmail": mail.status(), "config": cfg, "jobs": jobs})
        if u.path == "/api/nexora/envio":
            return self.send(200, nexora_ops.status_envio())
        if conta in CONTAS and u.path == "/api/painel":
            return self.send(200, painel.painel(conta, max(7, min(int(q.get("dias", 30)), 90))))
        if conta in CONTAS and u.path == "/api/acoes":
            return self.send(200, painel.acoes(conta))
        if conta in CONTAS and u.path == "/api/conversas":
            return self.send(200, {"conversas": painel.conversas_whatsapp(conta)})
        if u.path == "/api/saude":
            return self.send(200, workers.saude())
        if u.path == "/api/wa/conversa":
            c = crm()
            msgs = [dict(r) for r in c.execute("SELECT direcao, texto, tipo, ts_msg, created_at FROM wa_mensagens WHERE lead_ref=? ORDER BY id", (q.get("ref", ""),))]
            c.close()
            return self.send(200, {"mensagens": msgs})
        if u.path == "/api/lead":
            c = crm()
            l = store.get_lead(c, q.get("ref", ""))
            resp = [dict(r) for r in c.execute("SELECT * FROM respostas WHERE lead_ref=? ORDER BY id", (q.get("ref", ""),))]
            tar = [dict(r) for r in c.execute("SELECT * FROM tarefas WHERE lead_ref=? ORDER BY passo", (q.get("ref", ""),))]
            evs = [dict(r) for r in c.execute("SELECT tipo, de_etapa, para_etapa, ts FROM eventos WHERE lead_ref=? ORDER BY id", (q.get("ref", ""),))]
            wa = [dict(r) for r in c.execute("SELECT direcao, texto, tipo, created_at FROM wa_mensagens WHERE lead_ref=? ORDER BY id", (q.get("ref", ""),))]
            c.close()
            return self.send(200 if l else 404, {"lead": l, "respostas": resp, "tarefas": tar, "eventos": evs, "whatsapp": wa})
        if conta in CONTAS and u.path.startswith("/api/gmail/"):
            try:
                if u.path == "/api/gmail/pastas":
                    return self.send(200, gmail_ui.contagens(conta) or {"erro": "conta Gmail nao configurada"})
                if u.path == "/api/gmail/conversas":
                    return self.send(200, gmail_ui.conversas(conta, q.get("pasta", "INBOX"), q.get("busca", ""), q.get("pagina")))
                if u.path == "/api/gmail/conversa":
                    return self.send(200, gmail_ui.conversa(conta, q.get("id", "")))
            except Exception as e:
                return self.send(502, {"erro": str(e)})
        if conta in CONTAS:
            if u.path == "/api/board" and canal in CANAIS:
                return self.send(200, store.board(conta, canal))
            if u.path == "/api/aprendizado":
                return self.send(200, painel_extra.aprendizado_completo(conta, int(q.get("tz", 0))))
            simples = {"/api/hoje": store.hoje_view, "/api/stats": store.stats, "/api/captacao": store.captacao, "/api/financeiro": painel_extra.financeiro_completo,
                       "/api/radar": painel_extra.radar_completo}
            if u.path in simples:
                return self.send(200, simples[u.path](conta))
            if u.path == "/api/modelos":
                c = crm()
                r = [dict(x) for x in c.execute("SELECT passo, texto FROM modelos WHERE conta=? ORDER BY passo", (conta,))]
                c.close()
                return self.send(200, {"dias": store.FOLLOWUP_DIAS, "modelos": r})
        self.send(404, {"erro": "nao encontrado"})

    def do_POST(self):
        if not self._seguro(True):
            return
        u = urlparse(self.path)
        d = self.body()
        p = u.path.strip("/").split("/")
        if u.path == "/api/wa/event":
            return self.send(200, wa_evento(d))
        if u.path == "/api/wa/status":
            WAM.receber_status(d)
            return self.send(200, {"ok": True})
        if u.path == "/api/wa/start":
            if not os.path.exists(os.path.join(workers.WA_DIR, "node_modules")):
                return self.send(500, {"erro": "dependencias do observador nao instaladas (npm install em crm/wa-watcher)"})
            WAM.iniciar(manual=True)
            return self.send(200, {"ok": True})
        if u.path == "/api/wa/stop":
            WAM.parar()
            return self.send(200, {"ok": True})
        if u.path == "/api/wa/novo-qr":
            WAM.novo_qr()
            return self.send(200, {"ok": True})
        if u.path.startswith("/api/nexora/"):
            try:
                if u.path == "/api/nexora/aprovar":
                    return self.send(200, {"aprovados": nexora_ops.aprovar(d.get("ids", []))})
                if u.path == "/api/nexora/rejeitar":
                    return self.send(200, {"rejeitados": nexora_ops.rejeitar(d.get("ids", []), d.get("motivo", ""))})
                if u.path == "/api/nexora/suprimir":
                    nexora_ops.suprimir(d.get("id"), d.get("motivo") or "Solicitacao de remocao (opt-out).")
                    return self.send(200, {"ok": True})
                if u.path == "/api/nexora/enviar":
                    return self.send(200, nexora_ops.enviar_agora())
            except nexora_ops.Bloqueado as e:
                return self.send(e.codigo, {"erro": str(e)})
            return self.send(404, {"erro": "nao encontrado"})
        if u.path == "/api/gmail/send" and d.get("conta") in CONTAS:
            try:
                gmail_ui.enviar(d["conta"], d.get("para", ""), d.get("assunto", ""), d.get("corpo", ""), d.get("thread_id"), d.get("in_reply_to"), d.get("references"))
                return self.send(200, {"ok": True})
            except Exception as e:
                return self.send(502, {"erro": str(e)})
        if u.path == "/api/gmail/acao" and d.get("conta") in CONTAS:
            try:
                gmail_ui.acao(d["conta"], d.get("id", ""), d.get("acao", ""))
                return self.send(200, {"ok": True})
            except gmail_ui.SemPermissao as e:
                return self.send(403, {"erro": str(e)})
            except Exception as e:
                return self.send(502, {"erro": str(e)})
        if u.path == "/api/gmail/sync":
            conta = d.get("conta")
            if conta in CONTAS:
                spawn(mail.sync, conta)
            return self.send(200, {"ok": True})
        if u.path == "/api/validar":
            if d.get("conta") not in CONTAS or d.get("canal") not in CANAIS or d.get("tipo") not in ("primeiro", "followup"):
                return self.send(400, {"erro": "conta, canal e tipo invalidos"})
            return self.send(200, {"violacoes": regras.validar(d["conta"], d["canal"], d["tipo"], d.get("texto", ""), None, bool(d.get("link")))})
        if u.path == "/api/traduzir":
            try:
                para = "portugues do Brasil" if d.get("para") == "pt" else "ingles americano"
                return self.send(200, {"texto": ia.run_claude("Traduza para %s, devolvendo somente a traducao:\n\n%s" % (para, d.get("texto", "")))})
            except Exception as e:
                return self.send(502, {"erro": str(e)})
        c = crm()
        try:
            if u.path == "/api/config":
                store.cfg_set(c, d["chave"], d["valor"] if isinstance(d["valor"], str) else json.dumps(d["valor"], ensure_ascii=False))
                return self.send(200, {"ok": True})
            if u.path == "/api/captar" and d.get("conta") in CONTAS:
                spawn(pipeline.captar_job, d["conta"], d.get("cidade", ""), d.get("categoria", ""), int(d.get("quantidade", 10)))
                return self.send(200, {"ok": True})
            if u.path == "/api/aprendizado/revisar" and d.get("conta") in CONTAS:
                spawn(pipeline.revisar_semana, d["conta"])
                return self.send(200, {"ok": True})
            if len(p) == 4 and p[1] == "propostas" and p[2].isdigit():
                c.execute("UPDATE propostas SET status=? WHERE id=?", ("aprovada" if p[3] == "aprovar" else "rejeitada", int(p[2])))
                c.commit()
                return self.send(200, {"ok": True})
            if u.path == "/api/leads":
                if d.get("conta") not in CONTAS or d.get("canal") not in CANAIS or not d.get("nome"):
                    return self.send(400, {"erro": "conta, canal e nome sao obrigatorios"})
                if d["conta"] == "nexora" and d["canal"] == "email":
                    return self.send(400, {"erro": "e-mail da Nexora vem do pipeline existente"})
                for col in ("telefone", "email"):
                    chave = d.get(col)
                    if chave and c.execute("SELECT 1 FROM bloqueios WHERE conta=? AND chave=?", (d["conta"], chave)).fetchone():
                        return self.send(409, {"erro": "contato bloqueado (recusou antes)"})
                    if chave and c.execute("SELECT 1 FROM leads WHERE conta=? AND %s=?" % col, (d["conta"], chave)).fetchone():
                        return self.send(409, {"erro": "lead duplicado"})
                ts = now()
                cur = c.execute(
                    "INSERT INTO leads (conta,canal,etapa,nome,contato,telefone,email,cidade,site,fonte,nota_google,avaliacoes,dor,tipo_dor,assunto,mensagem,notas,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["conta"], d["canal"], d.get("etapa") if d.get("etapa") in ETAPAS else "Novo", d["nome"], d.get("contato"), d.get("telefone"), d.get("email"),
                     d.get("cidade"), d.get("site"), d.get("fonte"), d.get("nota_google"), d.get("avaliacoes"), d.get("dor"), d.get("tipo_dor"), d.get("assunto"),
                     d.get("mensagem"), d.get("notas"), ts, ts))
                c.commit()
                return self.send(201, {"id": cur.lastrowid})
            if len(p) == 4 and p[1] == "leads" and p[2].isdigit():
                lid, acao = int(p[2]), p[3]
                row = c.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
                if not row:
                    return self.send(404, {"erro": "lead nao encontrado"})
                lead = dict(row, ref="c%d" % lid, id="c%d" % lid)
                if acao == "sent":
                    store.marcar_primeiro_envio(c, lead, "manual")
                elif acao == "descartar":
                    c.execute("UPDATE leads SET etapa='Perdido', updated_at=? WHERE id=?", (now(), lid))
                    store.cancelar_tarefas(c, lead["ref"])
                elif acao == "sem_whatsapp":
                    c.execute("UPDATE leads SET sem_whatsapp=1, updated_at=? WHERE id=?", (now(), lid))
                elif acao == "aprovar":
                    c.execute("UPDATE leads SET aprovado=1, updated_at=? WHERE id=?", (now(), lid))
                elif acao == "analisar":
                    spawn(pipeline.analisar_lead, lid)
                elif acao == "resposta":
                    texto = (d.get("texto") or "").strip()
                    if not texto:
                        return self.send(400, {"erro": "texto vazio"})
                    cls = d.get("classificacao") if d.get("classificacao") in CLASSES else None
                    store.registrar_resposta(c, lead, texto, cls, origem="manual")
                    c.commit()
                    if cls is None:
                        spawn(mail.reclassificar)
                    return self.send(200, {"ok": True, "classificacao": cls})
                elif acao == "editar":
                    campos = {k: d[k] for k in ("etapa", "nome", "contato", "telefone", "email", "cidade", "site", "fonte", "mensagem", "assunto", "notas", "dor") if k in d}
                    if campos.get("etapa") and campos["etapa"] not in ETAPAS:
                        return self.send(400, {"erro": "etapa invalida"})
                    if campos:
                        c.execute("UPDATE leads SET %s, updated_at=? WHERE id=?" % ", ".join("%s=?" % k for k in campos), (*campos.values(), now(), lid))
                        if campos.get("etapa") == "Contatado" and lead["etapa"] != "Contatado":
                            store.marcar_primeiro_envio(c, lead, "manual")
                c.commit()
                return self.send(200, {"ok": True})
            if len(p) == 4 and p[1] == "tarefas" and p[2].isdigit() and p[3] == "feita":
                store.concluir_tarefa(c, int(p[2]), "manual")
                c.commit()
                return self.send(200, {"ok": True})
            if u.path == "/api/modelos" and d.get("conta") in CONTAS:
                c.execute("INSERT OR REPLACE INTO modelos (conta,passo,texto) VALUES (?,?,?)", (d["conta"], int(d["passo"]), d["texto"]))
                c.commit()
                return self.send(200, {"ok": True})
            if u.path == "/api/pagamentos" and d.get("conta") in CONTAS:
                valor = int(round(float(str(d.get("valor", "0")).replace(",", ".")) * 100))
                pago = d.get("status") == "pago"
                c.execute("INSERT INTO pagamentos (conta,lead_ref,cliente,descricao,valor_centavos,status,vencimento,pago_em,fonte,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (d["conta"], d.get("lead_ref"), d.get("cliente"), d.get("descricao"), valor, "pago" if pago else "a_receber", d.get("vencimento"), now() if pago else None, "manual", now()))
                if pago and (d.get("lead_ref") or "").startswith("c"):
                    c.execute("UPDATE leads SET etapa='Fechado', updated_at=? WHERE id=?", (now(), int(d["lead_ref"][1:])))
                c.commit()
                return self.send(201, {"ok": True})
            if len(p) == 4 and p[1] == "pagamentos" and p[2].isdigit() and p[3] == "pago":
                c.execute("UPDATE pagamentos SET status='pago', pago_em=? WHERE id=?", (now(), int(p[2])))
                pg = c.execute("SELECT lead_ref FROM pagamentos WHERE id=?", (int(p[2]),)).fetchone()
                if pg and (pg["lead_ref"] or "").startswith("c"):
                    c.execute("UPDATE leads SET etapa='Fechado', updated_at=? WHERE id=?", (now(), int(pg["lead_ref"][1:])))
                c.commit()
                return self.send(200, {"ok": True})
            if u.path == "/api/servicos" and d.get("conta") in CONTAS:
                c.execute("INSERT INTO servicos (conta,nome,preco_centavos) VALUES (?,?,?)", (d["conta"], d["nome"], int(round(float(str(d.get("preco", "0")).replace(",", ".")) * 100))))
                c.commit()
                return self.send(201, {"ok": True})
            if u.path == "/api/meta" and d.get("conta") in CONTAS:
                c.execute("INSERT OR REPLACE INTO metas (conta,mes,valor_centavos) VALUES (?,?,?)", (d["conta"], store.hoje()[:7], int(round(float(str(d.get("valor", "0")).replace(",", ".")) * 100))))
                c.commit()
                return self.send(200, {"ok": True})
            self.send(404, {"erro": "nao encontrado"})
        finally:
            c.close()


class Servidor(ThreadingHTTPServer):
    """Reserva a porta de forma exclusiva: um segundo servidor falha ao subir em vez de dividir a porta (Windows)."""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def criar_servidor(porta=PORT):
    return Servidor(("127.0.0.1", porta), H)


def verificar_bancos():
    """Antes de subir: confere a integridade do banco do CRM e restaura o ultimo backup bom se estiver corrompido."""
    r = backup.verificar_e_restaurar(store.CRM_DB, workers.BACKUP_DIR, "crm")
    if r["acao"] == "restaurado":
        log.error("BANCO DO CRM CORROMPIDO: restaurado de %s (o arquivo ruim ficou em %s)", r["backup"], r["arquivo_corrompido"])
    elif r["acao"] == "sem_backup":
        log.error("BANCO DO CRM CORROMPIDO e sem backup integro disponivel: %s", r["arquivo"])
    if os.path.exists(store.NEXORA_DB) and not backup.integridade_ok(store.NEXORA_DB):
        log.error("BANCO DA NEXORA com problema de integridade (nao mexo nele sozinho): %s", store.NEXORA_DB)


def main():
    workers.configurar_log()
    verificar_bancos()
    crm().close()
    try:
        srv = criar_servidor()          # 1) reserva a porta ANTES de ligar qualquer worker
    except OSError as e:
        log.error("porta %d ocupada (%s): ja existe um CRM rodando. Encerrando.", PORT, e)
        print("O CRM ja esta rodando em http://127.0.0.1:%d" % PORT)
        sys.exit(2)                     # codigo 2 = ja existe outra copia (o .bat nao tenta de novo)
    workers.iniciar_todos()             # 2) so entao inicia workers e o observador do WhatsApp
    print("CRM em http://127.0.0.1:%d" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        WAM.parar()


if __name__ == "__main__":
    main()
