"""Historico de etapas, painel (indicadores, funil, serie), acoes do dia, conversas e operacao da Nexora dentro do CRM."""
import os
from datetime import datetime, timedelta, timezone

from base import BaseCRM, store, ndb, ENV_FALSO
import gmail_ui
import mail
import nexora_ops
import painel


def iso(dias):
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


class TestEventos(BaseCRM):
    def test_criacao_e_mudanca_de_etapa_sao_registradas_por_qualquer_caminho(self):
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/leads/%d/resposta" % lid, {"texto": "x", "classificacao": "reuniao"})
        self.post("/api/pagamentos", {"conta": "atlas", "valor": "10", "status": "pago", "lead_ref": "c%d" % lid})
        ev = [(e["tipo"], e["de_etapa"], e["para_etapa"]) for e in self.sql("SELECT tipo, de_etapa, para_etapa FROM eventos WHERE lead_ref=? ORDER BY id", "c%d" % lid)]
        self.assertEqual(ev, [("criado", None, "Pronto"), ("etapa", "Pronto", "Contatado"), ("etapa", "Contatado", "Negociando"), ("etapa", "Negociando", "Fechado")])

    def test_atualizar_sem_mudar_etapa_nao_gera_evento(self):
        lid = self.novo_lead()
        self.post("/api/leads/%d/editar" % lid, {"notas": "so uma nota"})
        self.post("/api/leads/%d/editar" % lid, {"etapa": "Pronto"})
        self.assertEqual(len(self.sql("SELECT * FROM eventos WHERE lead_ref=?", "c%d" % lid)), 1)


class TestPainel(BaseCRM):
    def test_sem_dados_nada_e_inventado(self):
        p = self.get("/api/painel?conta=atlas")[1]
        self.assertEqual(p["kpis"], {"leads": 0, "contatados": 0, "respostas": 0, "negociacoes": 0, "fechados": 0, "perdidos": 0})
        self.assertFalse(p["serie_suficiente"])
        self.assertEqual(p["dores"], [])
        self.assertTrue(all(c["insuficiente"] and c["taxa"] is None for c in p["canais"]))
        self.assertTrue(all(sum(v) == 0 for v in p["serie"].values()))
        self.assertEqual(len(p["datas"]), 30)

    def _lead_ate(self, nome, tel, etapa_final, dor="sem_site"):
        lid = self.novo_lead(nome=nome, telefone=tel, tipo_dor=dor)
        if etapa_final in ("Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"):
            self.post("/api/leads/%d/sent" % lid)
        if etapa_final in ("Respondeu", "Negociando", "Fechado"):
            self.post("/api/leads/%d/resposta" % lid, {"texto": "x", "classificacao": "interessado"})
        if etapa_final in ("Negociando", "Fechado"):
            self.post("/api/leads/%d/editar" % lid, {"etapa": "Negociando"})
        if etapa_final == "Fechado":
            self.post("/api/leads/%d/editar" % lid, {"etapa": "Fechado"})
        if etapa_final == "Perdido":
            self.post("/api/leads/%d/resposta" % lid, {"texto": "nao", "classificacao": "recusou"})
        return lid

    def test_funil_cumulativo_conversao_e_perdas(self):
        alvo = ["Pronto", "Pronto", "Contatado", "Contatado", "Contatado", "Respondeu", "Respondeu", "Negociando", "Fechado", "Perdido"]
        for i, e in enumerate(alvo):
            self._lead_ate("L%d" % i, "(77) 99%03d-5555" % i, e)
        p = self.get("/api/painel?conta=atlas")[1]
        n = {f["etapa"]: f["n"] for f in p["funil"]}
        self.assertEqual(n, {"Novo": 10, "Pronto": 10, "Contatado": 8, "Respondeu": 5, "Negociando": 2, "Fechado": 1})     # quem recusou tambem respondeu
        conv = {f["etapa"]: f["conv"] for f in p["funil"]}
        self.assertEqual((conv["Contatado"], conv["Respondeu"], conv["Negociando"], conv["Fechado"]), (80, 63, 40, 50))
        self.assertEqual(p["kpis"], {"leads": 10, "contatados": 8, "respostas": 5, "negociacoes": 2, "fechados": 1, "perdidos": 1})
        self.assertEqual(p["funil"][3]["perdidos"], 1)
        self.assertEqual(p["funil"][2]["perdidos"], 0)

    def test_serie_temporal_conta_no_dia_certo(self):
        a = self._lead_ate("A", "(77) 99111-0001", "Respondeu")
        c = store.crm()
        c.execute("UPDATE envios SET enviado_em=?", (iso(-2),))
        c.execute("UPDATE leads SET sent_at=?", (iso(-2),))
        c.execute("UPDATE eventos SET ts=? WHERE para_etapa='Contatado'", (iso(-2),))
        c.execute("UPDATE respostas SET created_at=?", (iso(-1),))
        c.commit()
        c.close()
        p = self.get("/api/painel?conta=atlas&dias=7")[1]
        self.assertEqual(len(p["datas"]), 7)
        self.assertEqual(p["serie"]["contatos"][-3], 1)
        self.assertEqual(p["serie"]["respostas"][-2], 1)
        self.assertEqual(sum(p["serie"]["leads"]), 1)

    def test_canais_e_dores_marcam_amostra_insuficiente(self):
        for i in range(3):
            self._lead_ate("W%d" % i, "(77) 99%03d-6666" % i, "Respondeu" if i == 0 else "Contatado")
        p = self.get("/api/painel?conta=atlas")[1]
        wa = next(c for c in p["canais"] if c["canal"] == "whatsapp")
        self.assertEqual((wa["contatados"], wa["respostas"], wa["insuficiente"], wa["taxa"]), (3, 1, True, None))
        self.assertTrue(p["dores"][0]["insuficiente"])
        for i in range(3, 8):
            self._lead_ate("W%d" % i, "(77) 99%03d-6666" % i, "Contatado")
        p = self.get("/api/painel?conta=atlas")[1]
        wa = next(c for c in p["canais"] if c["canal"] == "whatsapp")
        self.assertEqual((wa["contatados"], wa["insuficiente"], wa["taxa"]), (8, False, 13))       # 1 de 8 = 12,5 -> 13

    def test_nexora_usa_o_banco_original_e_marca_parcial(self):
        self.nexora_lead("N1", "n1@x.example", status="pronto")
        self.nexora_lead("N2", "n2@x.example", enviado_ha_dias=3)
        r = self.nexora_lead("N3", "n3@x.example", enviado_ha_dias=5)
        conn = ndb.connect()
        conn.execute("UPDATE leads SET status='respondido', responded_at=? WHERE id=?", (iso(-1), r))
        conn.commit()
        conn.close()
        p = self.get("/api/painel?conta=nexora")[1]
        self.assertEqual(p["kpis"]["leads"], 3)
        self.assertEqual((p["kpis"]["contatados"], p["kpis"]["respostas"]), (2, 1))
        self.assertTrue(p["parcial"])
        self.assertEqual(sum(p["serie"]["contatos"]), 2)
        self.assertEqual(sum(p["serie"]["respostas"]), 1)


class TestAcoesDoDia(BaseCRM):
    def _respondeu(self, nome, tel, cls="interessado"):
        lid = self.novo_lead(nome=nome, telefone=tel)
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/leads/%d/resposta" % lid, {"texto": "resposta de " + nome, "classificacao": cls})
        return lid

    def test_responder_lista_quem_esta_esperando_e_prioriza_negociacao(self):
        a = self._respondeu("Interessado", "(77) 99000-0001")
        b = self._respondeu("Negocia", "(77) 99000-0002", "reuniao")
        self._respondeu("Recusou", "(77) 99000-0003", "recusou")
        r = self.get("/api/acoes?conta=atlas")[1]
        self.assertEqual([x["nome"] for x in r["responder"]], ["Negocia", "Interessado"])
        self.assertEqual(r["resumo"]["responder"], 2)
        self.assertIn("resposta de Negocia", r["responder"][0]["texto"])

    def test_responder_some_quando_o_usuario_responde_no_whatsapp(self):
        lid = self._respondeu("Interessado", "(77) 99000-0001")
        self.assertEqual(self.get("/api/acoes?conta=atlas")[1]["resumo"]["responder"], 1)
        self.post("/api/wa/event", {"direcao": "saida", "telefone": "5577990000001", "texto": "Claro, te ligo amanha"})
        self.assertEqual(self.get("/api/acoes?conta=atlas")[1]["resumo"]["responder"], 0)
        self.post("/api/wa/event", {"direcao": "entrada", "telefone": "5577990000001", "texto": "Combinado"})        # nova resposta reabre
        self.post("/api/leads/%d/resposta" % lid, {"texto": "outra", "classificacao": "interessado"})
        self.assertEqual(self.get("/api/acoes?conta=atlas")[1]["resumo"]["responder"], 1)

    def test_responder_some_quando_o_usuario_responde_por_email_no_crm(self):
        lid = self.novo_lead(canal="email", telefone=None, email="cli@loca.example", nome="Cli Email")
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/leads/%d/resposta" % lid, {"texto": "quero saber mais", "classificacao": "duvida"})
        self.assertEqual(self.get("/api/acoes?conta=atlas")[1]["resumo"]["responder"], 1)
        gmail_ui._post = lambda at, path, body: {"id": "x"}
        try:
            gmail_ui.enviar("atlas", "Cli <cli@loca.example>", "Re: ideia", "Claro, segue.")
        finally:
            del gmail_ui._post
        self.assertEqual(self.get("/api/acoes?conta=atlas")[1]["resumo"]["responder"], 0)
        self.assertEqual(self.sql("SELECT passo, origem FROM envios WHERE lead_ref=? ORDER BY id DESC", "c%d" % lid)[0]["passo"], 99)

    def test_categorias_whatsapp_aprovar_revisar_e_followup(self):
        self.novo_lead(nome="Fila WA", telefone="(77) 99000-0010")
        self.novo_lead(canal="email", telefone=None, email="e@x.example", nome="Email para aprovar")
        rev = self.novo_lead(nome="Reprovado", telefone="(77) 99000-0011", etapa="Novo", mensagem=None, notas="Mensagem reprovada nas regras: longa demais")
        fu = self.novo_lead(nome="Com follow-up", telefone="(77) 99000-0012")
        self.post("/api/leads/%d/sent" % fu)
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=date('now') WHERE lead_ref=? AND passo=1", ("c%d" % fu,))
        c.commit()
        c.close()
        r = self.get("/api/acoes?conta=atlas")[1]
        self.assertEqual(r["resumo"], {"responder": 0, "whatsapp": 1, "aprovar_email": 1, "revisar": 1, "followup": 1})
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["revisar"][0]["nome"], "Reprovado")
        self.post("/api/leads/%d/aprovar" % r["aprovar_email"][0]["lead_id"])
        self.assertEqual(self.get("/api/acoes?conta=atlas")[1]["resumo"]["aprovar_email"], 0)

    def test_conversas_de_whatsapp_marcam_quem_aguarda_voce(self):
        a = self.novo_lead(nome="Ana", telefone="(77) 99000-0020")
        b = self.novo_lead(nome="Bia", telefone="(77) 99000-0021")
        self.post("/api/wa/event", {"direcao": "saida", "telefone": "5577990000020", "texto": "Bom dia Ana"})
        self.post("/api/wa/event", {"direcao": "entrada", "telefone": "5577990000020", "texto": "Oi, tudo bem?"})
        self.post("/api/wa/event", {"direcao": "saida", "telefone": "5577990000021", "texto": "Bom dia Bia"})
        c = self.get("/api/conversas?conta=atlas")[1]["conversas"]
        por_nome = {x["nome"]: x for x in c}
        self.assertTrue(por_nome["Ana"]["aguardando_voce"])
        self.assertFalse(por_nome["Bia"]["aguardando_voce"])
        self.assertEqual(por_nome["Ana"]["mensagens"], 2)


class TestNexoraNoCRM(BaseCRM):
    def setUp(self):
        super().setUp()
        self.subproc = []
        self._run = nexora_ops.subprocess.run
        nexora_ops.subprocess.run = lambda *a, **k: self.subproc.append(a) or type("R", (), {"returncode": 0})()
        nexora_ops.load_env = lambda: dict(ENV_FALSO)
        nexora_ops.LOCK_PATH = os.path.join(os.path.dirname(os.environ["CRM_NEXORA_DB"]), "send-now.lock")
        nexora_ops.LOG_PATH = os.path.join(os.path.dirname(os.environ["CRM_NEXORA_DB"]), "envio.log")
        if os.path.exists(nexora_ops.LOCK_PATH):
            os.remove(nexora_ops.LOCK_PATH)

    def tearDown(self):
        nexora_ops.subprocess.run = self._run
        if os.path.exists(nexora_ops.LOCK_PATH):
            os.remove(nexora_ops.LOCK_PATH)
        super().tearDown()

    def _aprovados(self, n_re, n_lf=0):
        ids = []
        for i in range(n_re):
            ids.append(self.nexora_lead("RE%d" % i, "re%d@x.example" % i, status="pronto", segmento="real_estate"))
        for i in range(n_lf):
            ids.append(self.nexora_lead("LF%d" % i, "lf%d@x.example" % i, status="pronto", segmento="law_firm"))
        return ids

    def test_aprovar_e_rejeitar_mudam_o_status_no_banco_original(self):
        a, b, c = self._aprovados(3)
        st, r = self.post("/api/nexora/aprovar", {"ids": [a, b]})
        self.assertEqual(r["aprovados"], 2)
        self.assertEqual(self.nexora_row(a)[0]["status"], "aprovado")
        st, r = self.post("/api/nexora/rejeitar", {"ids": [c], "motivo": "nao serve"})
        self.assertEqual(r["rejeitados"], 1)
        row = self.nexora_row(c)[0]
        self.assertEqual((row["status"], row["rejeicao_motivo"]), ("rejeitado", "nao serve"))
        self.assertEqual(self.post("/api/nexora/aprovar", {"ids": [a]})[1]["aprovados"], 0)         # ja aprovado: idempotente

    def test_nao_aprova_lead_que_ja_foi_enviado(self):
        env = self.nexora_lead("Ja enviado", "ja@x.example", status="enviado", enviado_ha_dias=1)
        self.assertEqual(self.post("/api/nexora/aprovar", {"ids": [env]})[1]["aprovados"], 0)
        self.assertEqual(self.nexora_row(env)[0]["status"], "enviado")

    def test_suprimir_bloqueia_o_email(self):
        a = self._aprovados(1)[0]
        self.post("/api/nexora/suprimir", {"id": a})
        row, supp = self.nexora_row(a)
        self.assertEqual(row["status"], "rejeitado")
        self.assertIn("re0@x.example", supp)

    def test_envio_bloqueado_sem_endereco_postal_verificado(self):
        ids = self._aprovados(2)
        self.post("/api/nexora/aprovar", {"ids": ids})
        nexora_ops.load_env = lambda: dict(ENV_FALSO, NEXORA_POSTAL_ADDRESS_VERIFIED="false")
        st, r = self.post("/api/nexora/enviar")
        self.assertEqual(st, 400)
        self.assertIn("POSTAL_ADDRESS_VERIFIED", r["erro"])
        self.assertEqual(self.subproc, [])

    def test_envio_sem_aprovados_e_recusado(self):
        self._aprovados(2)
        st, r = self.post("/api/nexora/enviar")
        self.assertEqual((st, r["erro"]), (400, "Nenhum lead aprovado aguardando envio."))

    def test_envio_em_andamento_bloqueia_outro(self):
        self.post("/api/nexora/aprovar", {"ids": self._aprovados(1)})
        open(nexora_ops.LOCK_PATH, "w").write("x")
        st, r = self.post("/api/nexora/enviar")
        self.assertEqual(st, 409)

    def test_teto_diario_ja_atingido_bloqueia(self):
        for i in range(20):
            self.nexora_lead("Frio%d" % i, "frio%d@x.example" % i, status="enviado", enviado_ha_dias=0)
        self.post("/api/nexora/aprovar", {"ids": self._aprovados(2)})
        st, r = self.post("/api/nexora/enviar")
        self.assertEqual(st, 400)
        self.assertIn("Limite diario", r["erro"])

    def test_teto_por_segmento_com_preenchimento_do_outro_segmento(self):
        ids = self._aprovados(25)
        self.post("/api/nexora/aprovar", {"ids": ids})
        plano = nexora_ops.planejar_envio()
        self.assertEqual(plano["a_enviar"], 20)                       # 10 do segmento + fallback ate o teto total
        self.assertEqual(plano["minutos_estimados"], 15.0)            # 20 x 45s

    def test_envio_valido_chama_o_mesmo_script_e_libera_a_trava(self):
        self.post("/api/nexora/aprovar", {"ids": self._aprovados(3)})
        st, r = self.post("/api/nexora/enviar")
        self.assertEqual(st, 200)
        self.assertEqual(r["a_enviar"], 3)
        self.esperar(lambda: self.subproc, msg="send_gmail.py nao foi chamado")
        self.assertTrue(self.subproc[0][0][1].endswith("send_gmail.py"))
        self.esperar(lambda: not os.path.exists(nexora_ops.LOCK_PATH), msg="trava nao foi liberada")

    def test_aprovar_aparece_em_acoes_e_some_depois(self):
        ids = self._aprovados(2)
        self.assertEqual(self.get("/api/acoes?conta=nexora")[1]["resumo"]["aprovar_email"], 2)
        self.post("/api/nexora/aprovar", {"ids": ids[:1]})
        self.assertEqual(self.get("/api/acoes?conta=nexora")[1]["resumo"]["aprovar_email"], 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
