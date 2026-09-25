"""Regras de copy (validador), geracao com nova tentativa, analise de dor, captacao, follow-up adaptado e aprendizado."""
import json

from base import BaseCRM, store, ia, ia_falsa
import pipeline
import regras

BOA_ATLAS = "Oi, me chamo Enos. Vi que voces tem 120 avaliacoes no Google, mas hoje nao tem uma pagina propria para transformar isso em orcamento. Posso te mostrar uma ideia rapida?"
FATOS = {"lead": {"avaliacoes": 120}, "evidencias": ["120 avaliacoes no Google"]}


class TestValidadorAtlas(BaseCRM):
    def v(self, texto, tipo="primeiro", fatos=FATOS):
        return regras.validar("atlas", "whatsapp", tipo, texto, fatos)

    def test_mensagem_boa_passa(self):
        self.assertEqual(self.v(BOA_ATLAS), [])

    def test_violacoes_individuais(self):
        casos = {
            "usa travessao": BOA_ATLAS.replace("Oi,", "Oi —"),
            "hifen": BOA_ATLAS.replace("uma ideia", "uma ideia pos-venda"),
            "aqui e o Enos": BOA_ATLAS.replace("me chamo Enos", "aqui é o Enos"),
            "me chamo Enos": "Oi! Vi que voces tem 120 avaliacoes no Google, mas nao tem pagina propria. Posso te mostrar uma ideia?",
            "longa demais": BOA_ATLAS + " " + "Texto extra para estourar o limite de caracteres da primeira mensagem de WhatsApp. " * 3,
            "numero sem evidencia": BOA_ATLAS.replace("120", "450"),
            "percentual": BOA_ATLAS.replace("uma ideia rapida", "aumentar 300% suas vendas"),
            "promessa": BOA_ATLAS.replace("Posso te mostrar uma ideia rapida?", "Ja preparei uma previa pronta. Quer ver?"),
            "robotica": "Espero que esteja bem! " + BOA_ATLAS,
            "Vitoria": BOA_ATLAS.replace("Google", "Google de Vitória da Conquista"),
            "CTA": BOA_ATLAS.replace("Posso te mostrar uma ideia rapida?", "Te mostro uma ideia rapida."),
        }
        for chave, texto in casos.items():
            with self.subTest(chave):
                viol = self.v(texto)
                self.assertTrue(viol, "deveria reprovar: %s" % chave)

    def test_hifen_dentro_de_url_ou_email_e_permitido(self):
        self.assertEqual(self.v("Oi, me chamo Enos. Veja https://exemplo-site.com.br e fale em contato@x-y.com. Posso te mostrar uma ideia?", fatos={}), [])

    def test_followup_curto_passa_e_longo_falha(self):
        self.assertEqual(self.v("Oi, so passando para saber se viu minha mensagem. Posso te mostrar uma ideia rapida?", "followup"), [])
        self.assertTrue(self.v("Oi. " + "Muito texto de follow up que nao deveria existir aqui. " * 6, "followup"))

    def test_modelos_padrao_de_followup_respeitam_as_regras(self):
        for (conta, passo), texto in store.MODELOS_PADRAO.items():
            with self.subTest(conta=conta, passo=passo):
                canal = "whatsapp" if conta == "atlas" else "email"
                self.assertEqual(regras.validar(conta, canal, "followup", texto.replace("{nome}", "Empresa X"), None), [])


class TestValidadorNexora(BaseCRM):
    LINK = "Here is an illustrative example page you can adjust to your preferences: https://nexora-realty.vercel.app/?empresa=x"

    def v(self, texto, **kw):
        return regras.validar("nexora", "email", "primeiro", texto, kw.pop("fatos", {"lead": {"avaliacoes": 120}}), kw.pop("link", True))

    def test_email_bom_passa(self):
        t = "Your 120 Google reviews send buyers to a page that does not capture leads. That costs you inquiries every week.\n\nI build a focused page for $600 in 15 days.\n\n" + self.LINK
        self.assertEqual(self.v(t), [])

    def test_portugues_e_reprovado(self):
        self.assertIn("nao esta em ingles", self.v("Voce tem uma empresa com um site para vocês. Não temos uma página. " + self.LINK))

    def test_link_sem_descricao_de_exemplo_ilustrativo_ajustavel(self):
        viol = self.v("Your site loses leads. See https://nexora-realty.vercel.app/?empresa=x")
        self.assertTrue(any("exemplo ilustrativo" in x for x in viol))
        self.assertTrue(any("ajustavel" in x for x in viol))

    def test_promessa_e_numero_inventado(self):
        self.assertTrue(any("promessa" in x for x in self.v("We guarantee results. " + self.LINK)))
        self.assertTrue(any("numero sem evidencia" in x for x in self.v("You lose 47 leads a month. " + self.LINK)))

    def test_email_longo_demais(self):
        self.assertTrue(any("longa" in x for x in self.v(("Short sentence about your site. " * 60) + self.LINK)))


class TestGeracaoComRetentativa(BaseCRM):
    def _prompt_tipo(self, prompt):
        return "reescrita" if "Reescreva a mensagem abaixo" in prompt else ("analise" if "ANALISE PROFUNDA" in prompt else "outro")

    def test_analise_reescreve_mensagem_reprovada_e_aprova(self):
        chamadas = []
        ruim = "Oi, aqui é o Enos - trabalho com sites. " + "Texto longo demais para uma primeira mensagem de WhatsApp. " * 8

        def exe(prompt, tools=None):
            t = self._prompt_tipo(prompt)
            chamadas.append(t)
            if t == "analise":
                return json.dumps({"dor": "120 avaliacoes e nenhum site", "criterios": [], "evidencias": ["120 avaliacoes"], "tipo_dor": "sem_site",
                                   "mensagem": ruim, "assunto": "Ideia", "email": "Oi, me chamo Enos. Vi 120 avaliacoes e nenhum site. Posso te mostrar uma ideia?"})
            return BOA_ATLAS
        ia.executor = exe
        d = ia.analyze_lead({"nome": "X", "avaliacoes": 120})
        self.assertEqual(d["mensagem"], BOA_ATLAS)
        self.assertEqual(d["violacoes"], {})
        self.assertIn("reescrita", chamadas)

    def test_mensagem_que_nunca_passa_nao_entra_na_fila(self):
        ruim = "Oi, aqui é o Enos - somos especialistas em solucoes completas."
        ia.executor = lambda p, t=None: json.dumps({"dor": "x", "criterios": [], "evidencias": [], "tipo_dor": "sem_site", "mensagem": ruim, "assunto": "a", "email": ruim}) \
            if "ANALISE PROFUNDA" in p else ruim
        lid = self.novo_lead(etapa="Novo", mensagem=None, avaliacoes=120, telefone="(77) 99111-0000")
        pipeline.analisar_lead(lid)
        r = self.lead_db(lid)
        self.assertEqual(r["etapa"], "Novo")                 # nao foi para Pronto
        self.assertIsNone(r["mensagem"])
        self.assertIn("Mensagem reprovada nas regras", r["notas"])
        job = self.sql("SELECT status, detalhe FROM jobs WHERE tipo='analise'")[0]
        self.assertEqual(job["status"], "aviso")

    def test_analise_boa_coloca_lead_em_pronto_e_guarda_evidencias(self):
        ia.executor = ia_falsa
        lid = self.novo_lead(etapa="Novo", mensagem=None, avaliacoes=120, telefone="(77) 99111-0001")
        pipeline.analisar_lead(lid)
        r = self.lead_db(lid)
        self.assertEqual((r["etapa"], r["tipo_dor"]), ("Pronto", "sem_site"))
        self.assertEqual(regras.validar("atlas", "whatsapp", "primeiro", r["mensagem"], {"lead": {"avaliacoes": 120}, "e": ["120 avaliacoes no Google"]}), [])
        self.assertIn("120 avaliacoes", r["criterios_json"])

    def test_followup_reprovado_usa_texto_padrao(self):
        ruim = "Oi — passando aqui. " + "Muito texto. " * 40
        ia.executor = lambda p, t=None: ruim
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=date('now') WHERE passo=1")
        c.commit()
        c.close()
        pipeline.adaptar_followup()
        t = self.sql("SELECT mensagem, ia FROM tarefas WHERE passo=1")[0]
        self.assertEqual(t["ia"], 2)                                        # marcou falha e manteve o texto padrao
        self.assertTrue(t["mensagem"].startswith("Oi, Empresa Teste"))

    def test_followup_valido_e_adaptado_pela_ia(self):
        ia.executor = ia_falsa
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=date('now') WHERE passo=1")
        c.commit()
        c.close()
        pipeline.adaptar_followup()
        t = self.sql("SELECT mensagem, ia FROM tarefas WHERE passo=1")[0]
        self.assertEqual(t["ia"], 1)
        self.assertEqual(regras.validar("atlas", "whatsapp", "followup", t["mensagem"], {"lead": {}}), [])


class TestCaptacao(BaseCRM):
    def _cap(self, **kw):
        base = {"nome": "Locadora A", "telefone": "+55 77 99111-2222", "email": None, "site": None, "cidade": "Cidade Teste", "avaliacoes": 90, "nota_google": 4.8}
        base.update(kw)
        c = store.crm()
        r = pipeline.inserir_lead_captado(c, "atlas", base)
        c.commit()
        c.close()
        return r

    def test_insere_celular_como_whatsapp(self):
        self.assertTrue(self._cap())
        l = self.sql("SELECT canal, sem_whatsapp, etapa, fonte, cidade, avaliacoes FROM leads")[0]
        self.assertEqual((l["canal"], l["sem_whatsapp"], l["etapa"], l["fonte"], l["cidade"], l["avaliacoes"]), ("whatsapp", 0, "Novo", "apify:google-maps", "Cidade Teste", 90))

    def test_telefone_fixo_nao_vai_para_a_fila_do_whatsapp(self):
        self._cap(nome="Fixa", telefone="+55 75 3199-7744")
        self.assertEqual(self.sql("SELECT sem_whatsapp FROM leads")[0]["sem_whatsapp"], 1)

    def test_duplicados_por_nome_telefone_e_email(self):
        self.assertTrue(self._cap())
        self.assertFalse(self._cap(telefone="+55 77 99999-0000"))                     # mesmo nome
        self.assertFalse(self._cap(nome="Outro Nome", telefone="(77) 99111-2222"))      # mesmo telefone em outro formato
        self.assertTrue(self._cap(nome="B", telefone=None, email="b@x.example"))
        self.assertFalse(self._cap(nome="C", telefone=None, email="B@X.example"))       # mesmo email, caixa diferente
        self.assertEqual(len(self.sql("SELECT * FROM leads")), 2)

    def test_contato_bloqueado_nao_e_captado_de_novo(self):
        c = store.crm()
        c.execute("INSERT INTO bloqueios (conta, chave, motivo, created_at) VALUES ('atlas','+55 77 98888-0000','recusou','x')")
        c.commit()
        c.close()
        self.assertFalse(self._cap(nome="Bloqueada", telefone="+55 77 98888-0000"))

    def test_sem_telefone_e_sem_email_e_descartado(self):
        self.assertFalse(self._cap(nome="Sem contato", telefone=None, email=None))

    def test_captar_job_registra_resultado_e_insere(self):
        ia.executor = ia_falsa
        pipeline.captar_job("atlas", "Cidade Teste", "locacao", 5)
        self.assertEqual(len(self.sql("SELECT * FROM leads")), 1)
        j = self.sql("SELECT status, detalhe FROM jobs WHERE tipo='captacao'")[0]
        self.assertEqual((j["status"], j["detalhe"]), ("ok", "1 encontrados, 1 novos"))
        pipeline.captar_job("atlas", "Cidade Teste", "locacao", 5)                      # segunda rodada: tudo duplicado
        self.assertEqual(len(self.sql("SELECT * FROM leads")), 1)
        self.assertEqual(self.sql("SELECT detalhe FROM jobs WHERE tipo='captacao' ORDER BY id DESC")[0]["detalhe"], "1 encontrados, 0 novos")

    def test_captar_job_com_ia_fora_do_ar_registra_erro_sem_derrubar(self):
        ia.executor = lambda p, t=None: (_ for _ in ()).throw(RuntimeError("sem internet"))
        pipeline.captar_job("atlas", "X", "y", 3)
        j = self.sql("SELECT status, detalhe FROM jobs")[0]
        self.assertEqual(j["status"], "erro")
        self.assertIn("sem internet", j["detalhe"])


class TestAprendizado(BaseCRM):
    def test_sem_dados_nao_inventa_numeros(self):
        a = self.get("/api/aprendizado?conta=atlas")[1]
        self.assertEqual((a["total_envios"], a["por_canal"], a["por_dor"], a["objecoes"]), (0, [], [], []))

    def test_taxa_de_resposta_por_dor_e_por_canal(self):
        for i, (dor, resp) in enumerate([("sem_site", "interessado"), ("sem_site", None), ("sem_site", None), ("site_velho", "recusou")]):
            lid = self.novo_lead(nome="A%d" % i, telefone="(77) 99%03d-1111" % i, tipo_dor=dor)
            self.post("/api/leads/%d/sent" % lid)
            if resp:
                self.post("/api/leads/%d/resposta" % lid, {"texto": "x", "classificacao": resp})
        a = self.get("/api/aprendizado?conta=atlas")[1]
        dor = {x["chave"]: x for x in a["por_dor"]}
        self.assertEqual((dor["sem_site"]["envios"], dor["sem_site"]["respostas"], dor["sem_site"]["taxa"]), (3, 1, 33))
        self.assertEqual((dor["site_velho"]["envios"], dor["site_velho"]["respostas"]), (1, 1))
        self.assertEqual(a["por_canal"][0]["chave"], "whatsapp")
        self.assertEqual(len(a["objecoes"]), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
