"""Criacao de lead, funil, follow-ups D+3/D+7/D+14, respostas, bloqueio e financeiro."""
from datetime import datetime, timedelta, timezone

from base import BaseCRM, store


def dia(n):
    return (datetime.now(timezone.utc).date() + timedelta(days=n)).isoformat()


class TestLeads(BaseCRM):
    def test_cria_lead_e_rejeita_invalidos(self):
        lid = self.novo_lead()
        self.assertEqual(self.lead_db(lid)["etapa"], "Pronto")
        st, _ = self.post("/api/leads", {"conta": "atlas", "canal": "whatsapp"})               # sem nome
        self.assertEqual(st, 400)
        st, _ = self.post("/api/leads", {"conta": "xx", "canal": "whatsapp", "nome": "A"})     # conta invalida
        self.assertEqual(st, 400)
        st, _ = self.post("/api/leads", {"conta": "nexora", "canal": "email", "nome": "A"})    # e-mail da Nexora vem do pipeline
        self.assertEqual(st, 400)

    def test_duplicado_por_telefone_e_email(self):
        self.novo_lead(telefone="(77) 99000-1111", email="a@x.example")
        st, r = self.post("/api/leads", {"conta": "atlas", "canal": "whatsapp", "nome": "Outro", "telefone": "(77) 99000-1111"})
        self.assertEqual((st, r["erro"]), (409, "lead duplicado"))
        st, _ = self.post("/api/leads", {"conta": "atlas", "canal": "email", "nome": "Outro", "email": "a@x.example"})
        self.assertEqual(st, 409)

    def test_muda_etapa_e_rejeita_etapa_invalida(self):
        lid = self.novo_lead()
        st, _ = self.post("/api/leads/%d/editar" % lid, {"etapa": "Negociando"})
        self.assertEqual(st, 200)
        self.assertEqual(self.lead_db(lid)["etapa"], "Negociando")
        st, _ = self.post("/api/leads/%d/editar" % lid, {"etapa": "Inventada"})
        self.assertEqual(st, 400)
        self.assertEqual(self.lead_db(lid)["etapa"], "Negociando")

    def test_primeiro_envio_cria_followups_d3_d7_d14(self):
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")
        t = self.sql("SELECT passo, due_date, status FROM tarefas WHERE lead_ref=? ORDER BY passo", "c%d" % lid)
        self.assertEqual([(x["passo"], x["due_date"], x["status"]) for x in t], [(1, dia(3), "pendente"), (2, dia(7), "pendente"), (3, dia(14), "pendente")])
        self.assertEqual(len(self.sql("SELECT * FROM envios WHERE lead_ref=? AND passo=0", "c%d" % lid)), 1)

    def test_envio_repetido_nao_duplica_followups(self):
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/leads/%d/sent" % lid)
        self.assertEqual(len(self.sql("SELECT * FROM tarefas WHERE lead_ref=?", "c%d" % lid)), 3)


class TestRespostas(BaseCRM):
    def _contatado(self, **kw):
        lid = self.novo_lead(**kw)
        self.post("/api/leads/%d/sent" % lid)
        return lid

    def _responder(self, lid, cls):
        st, _ = self.post("/api/leads/%d/resposta" % lid, {"texto": "texto de teste", "classificacao": cls})
        self.assertEqual(st, 200)

    def test_classificacoes_movem_o_card(self):
        esperado = {"interessado": "Respondeu", "duvida": "Respondeu", "pendente": "Respondeu", "reuniao": "Negociando", "recusou": "Perdido", "bounce": "Perdido"}
        for i, (cls, etapa) in enumerate(esperado.items()):
            with self.subTest(cls=cls):
                lid = self._contatado(nome="E " + cls, telefone="(77) 99%03d-0000" % i)
                self._responder(lid, cls)
                self.assertEqual(self.lead_db(lid)["etapa"], etapa)

    def test_resposta_cancela_followups_pendentes(self):
        lid = self._contatado()
        self._responder(lid, "interessado")
        self.assertEqual({x["status"] for x in self.sql("SELECT status FROM tarefas WHERE lead_ref=?", "c%d" % lid)}, {"cancelada"})

    def test_resposta_automatica_nao_muda_nada(self):
        lid = self._contatado()
        self._responder(lid, "automatica")
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")
        self.assertEqual({x["status"] for x in self.sql("SELECT status FROM tarefas WHERE lead_ref=?", "c%d" % lid)}, {"pendente"})

    def test_recusa_bloqueia_contato_e_barra_novo_lead(self):
        lid = self._contatado(telefone="(77) 99777-0001", email="nao@x.example")
        self._responder(lid, "recusou")
        chaves = {x["chave"] for x in self.sql("SELECT chave FROM bloqueios")}
        self.assertEqual(chaves, {"(77) 99777-0001", "nao@x.example"})
        st, r = self.post("/api/leads", {"conta": "atlas", "canal": "whatsapp", "nome": "Volta", "telefone": "(77) 99777-0001"})
        self.assertEqual((st, r["erro"]), (409, "contato bloqueado (recusou antes)"))

    def test_lead_fechado_nao_regride_com_resposta(self):
        lid = self._contatado()
        self.post("/api/leads/%d/editar" % lid, {"etapa": "Fechado"})
        self._responder(lid, "duvida")
        self.assertEqual(self.lead_db(lid)["etapa"], "Fechado")

    def test_resposta_sem_classificacao_e_classificada_pela_ia(self):
        lid = self._contatado()
        self.post("/api/leads/%d/resposta" % lid, {"texto": "Tenho interesse, pode me ligar amanha? quero conversar"})
        self.esperar(lambda: self.lead_db(lid)["etapa"] == "Negociando", msg="IA nao classificou e moveu o card")
        r = self.sql("SELECT classificacao, traducao, resumo FROM respostas WHERE lead_ref=?", "c%d" % lid)[0]
        self.assertEqual(r["classificacao"], "reuniao")
        self.assertTrue(r["traducao"] and r["resumo"])

    def test_ia_indisponivel_deixa_resposta_pendente_sem_perder(self):
        import ia
        ia.executor = lambda p, t=None: (_ for _ in ()).throw(RuntimeError("fora do ar"))
        lid = self._contatado()
        self.post("/api/leads/%d/resposta" % lid, {"texto": "qualquer coisa"})
        import mail
        mail.reclassificar()
        r = self.sql("SELECT classificacao FROM respostas WHERE lead_ref=?", "c%d" % lid)[0]
        self.assertIsNone(r["classificacao"])
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")


class TestFinanceiro(BaseCRM):
    def test_pagamento_fecha_lead_e_atualiza_indicadores(self):
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/meta", {"conta": "atlas", "valor": "6000"})
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "X", "valor": "2400,50", "status": "pago", "lead_ref": "c%d" % lid})
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "Y", "valor": "1200", "status": "a_receber"})
        f = self.get("/api/financeiro?conta=atlas")[1]
        self.assertEqual((f["recebido_mes"], f["a_receber"], f["meta"], f["moeda"]), (240050, 120000, 600000, "BRL"))
        self.assertEqual(self.lead_db(lid)["etapa"], "Fechado")

    def test_marcar_pago_fecha_lead_vinculado(self):
        lid = self.novo_lead()
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "X", "valor": "100", "status": "a_receber", "lead_ref": "c%d" % lid})
        pid = self.sql("SELECT id FROM pagamentos")[0]["id"]
        self.post("/api/pagamentos/%d/pago" % pid)
        self.assertEqual(self.lead_db(lid)["etapa"], "Fechado")
        self.assertEqual(self.get("/api/financeiro?conta=atlas")[1]["a_receber"], 0)

    def test_moeda_da_nexora_e_dolar(self):
        self.assertEqual(self.get("/api/financeiro?conta=nexora")[1]["moeda"], "USD")


class TestRadar(BaseCRM):
    def test_respondeu_sem_retorno_esfriando_e_devolvido(self):
        # respondeu ha mais de 24h
        a = self.novo_lead(nome="Sem retorno", telefone="(77) 99001-0001")
        self.post("/api/leads/%d/sent" % a)
        self.post("/api/leads/%d/resposta" % a, {"texto": "oi", "classificacao": "interessado"})
        self.sql_exec("UPDATE respostas SET created_at=? WHERE lead_ref=?", store_iso(-1.5), "c%d" % a)      # o lead escreveu ha 36h
        self.sql_exec("UPDATE envios SET enviado_em=? WHERE lead_ref=?", store_iso(-3), "c%d" % a)
        # respondeu agora (nao deve aparecer)
        b = self.novo_lead(nome="Recente", telefone="(77) 99001-0002")
        self.post("/api/leads/%d/sent" % b)
        self.post("/api/leads/%d/resposta" % b, {"texto": "oi", "classificacao": "interessado"})
        # esfriando: contatado ha 20 dias sem tarefas pendentes
        c = self.novo_lead(nome="Esfriou", telefone="(77) 99001-0003")
        self.post("/api/leads/%d/sent" % c)
        self.sql_exec("UPDATE leads SET sent_at=? WHERE id=?", store_iso(-20), c)
        self.sql_exec("UPDATE tarefas SET status='cancelada' WHERE lead_ref=?", "c%d" % c)
        # devolvido
        d = self.novo_lead(nome="Devolvido", telefone="(77) 99001-0004")
        self.post("/api/leads/%d/sent" % d)
        self.post("/api/leads/%d/resposta" % d, {"texto": "falha", "classificacao": "bounce"})
        r = self.get("/api/radar?conta=atlas")[1]
        self.assertEqual([x["nome"] for x in r["sem_retorno"]], ["Sem retorno"])
        self.assertEqual(r["urgente"], [])
        self.assertEqual([x["nome"] for x in r["esfriando"]], ["Esfriou"])
        self.assertEqual([x["nome"] for x in r["devolvidos"]], ["Devolvido"])

    def sql_exec(self, consulta, *args):
        c = store.crm()
        c.execute(consulta, args)
        c.commit()
        c.close()


def store_iso(dias):
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


if __name__ == "__main__":
    import unittest
    unittest.main()
