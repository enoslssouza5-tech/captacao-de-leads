"""Evolucao: Kanban por arrastar (regras do funil), traducao da Nexora, verificacao de e-mail, deteccao de envio pelo Gmail,
copy curta da Atlas e da Nexora, e a tela de detalhes do lead."""
import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone

from base import BaseCRM, store, mail, ia, gmail_api, b64, ndb, ENV_FALSO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import regras  # noqa: E402
import verificacao  # noqa: E402
import pipeline  # noqa: E402

DOR = "A pagina do Google Maps com 84 avaliacoes oferece contato apenas por ligacao no telefone fixo, sem WhatsApp"
FATOS = {"dor": DOR, "lead": {"avaliacoes": 84}}
BOM = ("Me chamo Enos, falo de Vitória da Conquista, na Bahia.\n\nEu ajudo empresas de locação a receberem mais pedidos pela internet com tráfego pago, "
       "especialmente quando o único contato é telefone fixo, sem WhatsApp.\n\nFicaria ruim se agendarmos um horário essa semana para eu te apresentar um projeto?")


class TestCopyAtlas(unittest.TestCase):
    def val(self, t, fatos=FATOS, **k):
        return regras.validar("atlas", "whatsapp", "primeiro", t, fatos, **k)

    def test_modelo_curto_com_dor_real_passa(self):
        self.assertEqual(self.val(BOM), [])

    def test_reprova_generica_institucional_e_lista_de_servicos(self):
        v = " | ".join(self.val("Olá! Somos uma empresa de soluções personalizadas com landing pages, tráfego pago e SEO. Alavancamos seu negócio com estratégias inovadoras!!"))
        for trecho in ("generica", "institucional", "lista de servicos", "exclamacoes"):
            self.assertIn(trecho, v)

    def test_reprova_sem_dor_especifica(self):
        v = self.val("Me chamo Enos, falo de Vitória da Conquista.\n\nEu ajudo empresas de locação a vender mais.\n\nFicaria ruim se agendarmos um horário?")
        self.assertTrue(any("dor especifica" in x for x in v), v)

    def test_reprova_longa_e_com_muitos_paragrafos(self):
        longa = "\n\n".join(["Me chamo Enos e ajudo empresas de locação com tráfego pago todos os dias."] * 5) + "\n\nQuer conversar?"
        v = " | ".join(self.val(longa, None))
        self.assertIn("longa demais", v)
        self.assertIn("blocos demais", v)

    def test_reprova_repetida_e_travessao(self):
        self.assertTrue(any("parecida demais" in x for x in self.val(BOM, recentes=[BOM])))
        self.assertTrue(any("travessao" in x for x in self.val(BOM.replace("na Bahia", "na Bahia — hoje"))))

    def test_fato_nao_comprovado_reprova(self):
        v = self.val(BOM.replace("Eu ajudo", "Vi 300 avaliações e eu ajudo"))
        self.assertTrue(any("numero sem evidencia" in x for x in v), v)

    def test_cidade_e_permitida_na_abertura_da_mensagem_direta(self):
        self.assertFalse(any("Vitoria" in x for x in self.val(BOM)))


class TestCopyNexora(unittest.TestCase):
    CURTO = ("Hi there,\n\nYour probate page ends with a call to action and no form.\n\nAn heir who would rather write than call leaves without a way to reach back.\n\n"
             "A dedicated inquiry page with a short form could capture that, $600 fixed, delivered in 15 days.\n\n"
             "Here's an illustrative example you could adjust to fit your preferences, https://x.example/?empresa=y\n\nWorth a quick look?\n\n"
             "Don't want future emails like this? Just reply \"unsubscribe\" and we'll stop.\n\nNexora\n\n1528 Broadway, New York, NY 10036")

    def test_email_curto_passa_e_rodape_nao_conta(self):
        self.assertEqual(regras.validar("nexora", "email", "primeiro", self.CURTO, None, True), [])

    def test_email_longo_com_escopo_e_apresentacao_reprova(self):
        longo = self.CURTO.replace("Worth a quick look?", "We specialize in high-converting landing pages and client acquisition. It includes up to 6 sections, responsive design, a lead capture form, basic SEO and social media integration, and revisions as needed. " * 2 + "Worth a look?")
        v = " | ".join(regras.validar("nexora", "email", "primeiro", longo, None, True))
        self.assertIn("longo demais", v)
        self.assertIn("funcionalidades", v)
        self.assertIn("explica a empresa", v)

    def test_portugues_e_reconhecido(self):
        self.assertTrue(regras.parece_portugues("Claro, podemos conversar amanhã. Você prefere por telefone para a empresa?"))
        self.assertFalse(regras.parece_portugues("Of course, we can talk tomorrow. Would you prefer a call for your business?"))


class TestKanbanRegras(BaseCRM):
    def mover(self, ref, etapa):
        return self.post("/api/mover", {"ref": ref, "etapa": etapa})

    def test_pronto_para_contatado_cria_followups_e_registra_atividade(self):
        lid = self.novo_lead()
        st, r = self.mover("c%d" % lid, "Contatado")
        self.assertEqual(st, 200, r)
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")
        self.assertEqual(len(self.sql("SELECT * FROM tarefas WHERE lead_ref=?", "c%d" % lid)), 3)
        tipos = [x["tipo"] for x in self.sql("SELECT tipo FROM eventos WHERE lead_ref=?", "c%d" % lid)]
        self.assertIn("manual", tipos)
        self.assertIn("etapa", tipos)

    def test_pronto_exige_abordagem_e_nao_volta_depois_de_contatado(self):
        sem = self.novo_lead(etapa="Novo", mensagem=None, nome="Sem Msg")
        st, r = self.mover("c%d" % sem, "Pronto")
        self.assertEqual(st, 409)
        self.assertIn("abordagem", r["erro"].lower())
        lid = self.novo_lead(nome="Ja Contatado", telefone="(77) 99111-0001")
        self.mover("c%d" % lid, "Contatado")
        st, r = self.mover("c%d" % lid, "Pronto")
        self.assertEqual(st, 409)
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")

    def test_recusa_bloqueia_e_nao_pode_ser_reaberto_no_kanban(self):
        lid = self.novo_lead(telefone="(77) 99222-3333")
        self.mover("c%d" % lid, "Contatado")
        self.post("/api/leads/%d/resposta" % lid, {"texto": "nao tenho interesse, pare de enviar", "classificacao": "recusou"})
        self.assertEqual(self.lead_db(lid)["etapa"], "Perdido")
        st, r = self.mover("c%d" % lid, "Negociando")
        self.assertEqual(st, 409)
        self.assertIn("bloqueado", r["erro"].lower())
        self.assertEqual(self.lead_db(lid)["etapa"], "Perdido")

    def test_respondeu_nao_volta_a_contatado_e_fechado_e_definitivo(self):
        lid = self.novo_lead(telefone="(77) 99444-5555")
        self.mover("c%d" % lid, "Contatado")
        self.assertEqual(self.mover("c%d" % lid, "Negociando")[0], 200)
        self.assertEqual(self.mover("c%d" % lid, "Contatado")[0], 409)
        self.assertEqual(len([t for t in self.sql("SELECT status FROM tarefas WHERE lead_ref=?", "c%d" % lid) if t["status"] == "pendente"]), 0)
        self.assertEqual(self.mover("c%d" % lid, "Fechado")[0], 200)
        self.assertEqual(self.mover("c%d" % lid, "Negociando")[0], 409)

    def test_perdido_manual_cancela_followups(self):
        lid = self.novo_lead(telefone="(77) 99666-7777")
        self.mover("c%d" % lid, "Contatado")
        self.assertEqual(self.mover("c%d" % lid, "Perdido")[0], 200)
        self.assertEqual(len([t for t in self.sql("SELECT status FROM tarefas WHERE lead_ref=?", "c%d" % lid) if t["status"] == "pendente"]), 0)

    def test_etapa_invalida_e_lead_inexistente(self):
        self.assertEqual(self.mover("c999", "Novo")[0], 409)
        lid = self.novo_lead()
        self.assertEqual(self.mover("c%d" % lid, "Inventada")[0], 409)

    def test_nexora_pronto_e_contatado_dependem_do_envio_real(self):
        lid = self.nexora_lead("Imob Pronto", "p@imob.example", status="pronto")
        st, r = self.mover("n%d" % lid, "Contatado")
        self.assertEqual(st, 409)
        st, r = self.mover("n%d" % lid, "Negociando")
        self.assertEqual(st, 409)                                            # ainda nao foi enviado
        env = self.nexora_lead("Imob Enviada", "e@imob.example", status="enviado", enviado_ha_dias=2)
        self.assertEqual(self.mover("n%d" % env, "Negociando")[0], 200)
        self.assertEqual(self.nexora_row(env)[0]["status_negociacao"], "em_negociacao")
        self.assertEqual(self.mover("n%d" % env, "Fechado")[0], 200)
        self.assertEqual(self.mover("n%d" % env, "Respondeu")[0], 409)     # fechado e definitivo

    def test_nexora_descadastrado_fica_em_perdido(self):
        lid = self.nexora_lead("Imob Recusou", "r@imob.example", status="enviado", enviado_ha_dias=2)
        conn = ndb.connect()
        conn.execute("UPDATE leads SET resposta_classificacao='unsubscribe' WHERE id=?", (lid,))
        conn.commit()
        conn.close()
        st, r = self.mover("n%d" % lid, "Respondeu")
        self.assertEqual(st, 409)


class TestTraducao(BaseCRM):
    def setUp(self):
        super().setUp()
        import gmail_ui
        self._gui_post = gmail_ui._post
        gmail_ui._post = lambda at, path, body: self.enviados.append(body["raw"]) or {"id": "g%d" % len(self.enviados)}

    def tearDown(self):
        import gmail_ui
        gmail_ui._post = self._gui_post
        super().tearDown()

    def test_en_para_pt_e_pt_para_en_e_cache(self):
        chamadas = []
        base = ia.executor
        ia.executor = lambda p, t=None: chamadas.append(p) or base(p, t)
        st, r = self.post("/api/traduzir", {"texto": "Hi, I'm interested.", "de": "en", "para": "pt"})
        self.assertEqual(st, 200)
        self.assertEqual(r["traducao"], "[PT] Hi, I'm interested.")
        self.assertFalse(r["cache"])
        st, r = self.post("/api/traduzir", {"texto": "Claro, podemos conversar.", "de": "pt", "para": "en"})
        self.assertEqual(r["traducao"], "[EN] Claro, podemos conversar.")
        st, r = self.post("/api/traduzir", {"texto": "Hi, I'm interested.", "de": "en", "para": "pt"})
        self.assertTrue(r["cache"])
        self.assertEqual(len(chamadas), 2)                                    # a terceira veio do cache

    def test_idioma_invalido_e_ia_fora_do_ar(self):
        self.assertEqual(self.post("/api/traduzir", {"texto": "x", "de": "en", "para": "fr"})[0], 400)
        ia._estado.update(falhas=3, ate=time.time() + 60)
        st, r = self.post("/api/traduzir", {"texto": "novo texto ainda nao traduzido", "de": "en", "para": "pt"})
        self.assertEqual(st, 503)

    def test_nexora_nao_envia_em_portugues(self):
        st, r = self.post("/api/gmail/send", {"conta": "nexora", "para": "lead@x.example", "assunto": "Re: x",
                                              "corpo": "Claro, podemos conversar amanhã. Você prefere por telefone para a sua empresa?"})
        self.assertEqual(st, 400)
        self.assertIn("ingles", r["erro"].lower())
        self.assertEqual(self.enviados, [])
        st, r = self.post("/api/gmail/send", {"conta": "nexora", "para": "lead@x.example", "assunto": "Re: x",
                                              "corpo": "Of course, I'd be happy to discuss this tomorrow. Would you prefer a call?"})
        self.assertEqual(st, 200, r)
        self.assertEqual(len(self.enviados), 1)
        raw = base64_decode(self.enviados[0])
        self.assertIn("I'd be happy to discuss", raw)                         # o que sai e o ingles
        self.assertIn("X-CRM-Origem: crm", raw)

    def test_atlas_pode_enviar_em_portugues(self):
        st, r = self.post("/api/gmail/send", {"conta": "atlas", "para": "lead@x.example", "assunto": "Re: x", "corpo": "Claro, podemos conversar amanhã. Você prefere por telefone?"})
        self.assertEqual(st, 200, r)


def base64_decode(raw):
    import base64
    import email
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw + "==="))
    cab = " ".join("%s: %s" % (k, v) for k, v in msg.items())
    return cab + " " + msg.get_payload(decode=True).decode("utf-8", "replace")


class TestVerificacaoEmail(BaseCRM):
    def test_regras_de_verificacao(self):
        self.assertFalse(verificacao.verificar_email("a@@b", dns=False)[0])
        self.assertFalse(verificacao.verificar_email("x@example.com", dns=False)[0])
        self.assertFalse(verificacao.verificar_email("noreply@empresa.com", dns=False)[0])
        self.assertTrue(verificacao.verificar_email("contato@empresa.com.br", dns=False)[0])

    def test_captacao_descarta_email_invalido_e_mantem_lead_de_whatsapp(self):
        c = store.crm()
        try:
            orig = verificacao.verificar_email
            verificacao.verificar_email = lambda e, dns=True: (False, "o dominio nao existe") if "ruim" in e else (True, "")
            self.assertFalse(pipeline.inserir_lead_captado(c, "nexora", {"nome": "So Email Ruim", "email": "a@ruim.example"}))
            self.assertTrue(pipeline.inserir_lead_captado(c, "atlas", {"nome": "Com Zap", "telefone": "+55 77 99111-2222", "email": "a@ruim.example"}))
            c.commit()
            r = c.execute("SELECT email, notas, canal FROM leads WHERE nome='Com Zap'").fetchone()
            self.assertEqual(r["canal"], "whatsapp")
            self.assertIsNone(r["email"])
            self.assertIn("E-mail descartado", r["notas"])
        finally:
            verificacao.verificar_email = orig
            c.close()


class TestEnvioDetectadoNoGmail(BaseCRM):
    def enviada(self, mid, para, ha_horas=1, crm=False):
        ms = int((datetime.now(timezone.utc) - timedelta(hours=ha_horas)).timestamp() * 1000)
        hdrs = [{"name": "To", "value": para}, {"name": "Subject", "value": "Oi"}, {"name": "From", "value": "atlas@teste.example"}]
        if crm:
            hdrs.append({"name": "X-CRM-Origem", "value": "crm"})
        return {"id": mid, "internalDate": str(ms), "labelIds": ["SENT"], "payload": {"mimeType": "text/plain", "headers": hdrs, "body": {"data": b64("corpo")}}}

    def test_primeiro_envio_manual_leva_a_contatado_e_cria_d3_d7_d14(self):
        lid = self.novo_lead(canal="email", telefone=None, email="dono@locadora.example", nome="Locadora Email")
        self.inbox = [self.enviada("s1", "Dono <dono@locadora.example>")]
        r = mail.sync_enviados("atlas")
        self.assertEqual(r["detectados"], 1)
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")
        self.assertEqual(sorted(t["passo"] for t in self.sql("SELECT passo FROM tarefas WHERE lead_ref=?", "c%d" % lid)), [1, 2, 3])
        self.assertEqual(len(self.sql("SELECT * FROM envios WHERE lead_ref=? AND origem='gmail_manual'", "c%d" % lid)), 1)
        self.assertEqual(mail.sync_enviados("atlas")["detectados"], 0)       # a mesma mensagem nao conta duas vezes

    def test_ignora_envio_do_proprio_crm_antigo_e_de_quem_nao_e_lead(self):
        lid = self.novo_lead(canal="email", telefone=None, email="dono@locadora.example", nome="Locadora Email")
        self.inbox = [self.enviada("s1", "dono@locadora.example", crm=True), self.enviada("s2", "dono@locadora.example", ha_horas=24 * 10),
                      self.enviada("s3", "desconhecido@x.example")]
        self.assertEqual(mail.sync_enviados("atlas")["detectados"], 0)
        self.assertEqual(self.lead_db(lid)["etapa"], "Pronto")

    def test_followup_devido_e_concluido_por_envio_manual(self):
        lid = self.novo_lead(canal="email", telefone=None, email="dono@locadora.example", nome="Locadora Email")
        self.inbox = [self.enviada("s1", "dono@locadora.example", ha_horas=2)]
        mail.sync_enviados("atlas")
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=? WHERE lead_ref=? AND passo=1", ((datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(), "c%d" % lid))
        c.commit()
        c.close()
        self.inbox.append(self.enviada("s2", "dono@locadora.example", ha_horas=1))
        self.assertEqual(mail.sync_enviados("atlas")["detectados"], 1)
        self.assertEqual(self.sql("SELECT status FROM tarefas WHERE lead_ref=? AND passo=1", "c%d" % lid)[0]["status"], "feita")

    def test_nexora_envio_manual_de_lead_pronto_vira_enviado(self):
        lid = self.nexora_lead("Imob Manual", "manual@imob.example", status="pronto")
        self.inbox = [self.enviada("s1", "manual@imob.example")]
        self.assertEqual(mail.sync_enviados("nexora")["detectados"], 1)
        self.assertEqual(self.nexora_row(lid)[0]["status"], "enviado")


class TestDetalhesDoLead(BaseCRM):
    def test_lead_da_nexora_traz_dor_criterios_e_evidencias_dos_achados(self):
        achados = [{"tipo": "conversao", "pagina": "inicial", "elemento": "Unico formulario", "problema": "O unico formulario e o filtro de busca", "impacto": "Quem nao busca sai sem contato",
                    "confianca": "alta", "evidencia_textual": "city, list_price_min"}]
        lid = self.nexora_lead("Imob Achados", "a@imob.example", status="pronto", findings=achados)
        st, r = self.get("/api/lead?ref=n%d" % lid)
        l = r["lead"]
        self.assertIn("filtro de busca", l["dor"])
        j = json.loads(l["criterios_json"])
        self.assertEqual(j["criterios"][0]["criterio"], "Unico formulario")
        self.assertEqual(j["evidencias"], ["city, list_price_min"])


if __name__ == "__main__":
    unittest.main()
