"""Gmail: leitura, classificacao, bloqueios, follow-up automatico, limite diario, intervalo entre envios."""
import base64
from datetime import datetime, timezone

from base import BaseCRM, msg_gmail, store, ndb, mail, ENV_FALSO


class TestGmailSync(BaseCRM):
    def _setup_nexora(self):
        ids = {}
        for nome, email in (("Interessado Imob", "int@imob.example"), ("Descadastro Imob", "unsub@imob.example"), ("Devolvido Imob", "gone@imob.example"),
                            ("Fora Imob", "ooo@imob.example"), ("Vago Imob", "vago@imob.example"), ("Duvida Imob", "duv@imob.example"), ("Recusa Imob", "nao@imob.example")):
            ids[nome] = self.nexora_lead(nome, email, enviado_ha_dias=4)
        self.get("/api/hoje?conta=nexora")           # gera os follow-ups da Nexora
        return ids

    def _etapa(self, ids, nome):
        cards = self.get("/api/board?conta=nexora&canal=email")[1]["cards"]
        for etapa, lst in cards.items():
            if any(c["nome"] == nome for c in lst):
                return etapa

    def test_leitura_classifica_move_funil_e_bloqueia(self):
        ids = self._setup_nexora()
        self.inbox = [
            msg_gmail("m1", "Int <int@imob.example>", "Re: idea", "Interested! Let's talk, call me tomorrow"),
            msg_gmail("m2", "Unsub <unsub@imob.example>", "Re: idea", "Please unsubscribe me"),
            msg_gmail("m3", "Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "Delivery Status Notification (Failure)", "Your message to gone@imob.example couldn't be delivered."),
            msg_gmail("m4", "Ooo <ooo@imob.example>", "Automatic reply: idea", "I am out of office until Monday. Automatic reply."),
            msg_gmail("m5", "Vago <vago@imob.example>", "Re: idea", "Ok, thanks."),
            msg_gmail("m6", "Duv <duv@imob.example>", "Re: idea", "How much does it cost and what's included?"),
            msg_gmail("m7", "Nao <nao@imob.example>", "Re: idea", "No thanks, we already have a website provider. Not interested."),
            msg_gmail("m8", "Estranho <estranho@outro.example>", "spam", "buy now"),
            msg_gmail("m9", "Nexora <nexora@teste.example>", "Re: idea", "mensagem do proprio remetente"),
        ]
        r = mail.sync("nexora")
        self.assertEqual(r, {"ok": True, "novas": 7})                # 7 leads; estranho e proprio ignorados
        self.assertEqual(self._etapa(ids, "Interessado Imob"), "Negociando")
        self.assertEqual(self._etapa(ids, "Descadastro Imob"), "Perdido")
        self.assertEqual(self._etapa(ids, "Devolvido Imob"), "Perdido")
        self.assertEqual(self._etapa(ids, "Fora Imob"), "Contatado")             # resposta automatica nao move
        self.assertEqual(self._etapa(ids, "Vago Imob"), "Respondeu")
        self.assertEqual(self._etapa(ids, "Duvida Imob"), "Respondeu")
        self.assertEqual(self._etapa(ids, "Recusa Imob"), "Perdido")
        _, supp = self.nexora_row(ids["Descadastro Imob"])
        self.assertIn("unsub@imob.example", supp)
        self.assertIn("gone@imob.example", supp)
        self.assertNotIn("nao@imob.example", supp)                               # recusa simples nao e supressao de e-mail
        cl = {r["lead_ref"]: r["classificacao"] for r in self.sql("SELECT lead_ref, classificacao FROM respostas")}
        self.assertEqual(cl["n%d" % ids["Interessado Imob"]], "reuniao")
        self.assertEqual(cl["n%d" % ids["Fora Imob"]], "automatica")
        # follow-ups: cancelados quando respondeu/recusou/devolveu; mantidos na resposta automatica
        def pend(nome):
            return len(self.sql("SELECT * FROM tarefas WHERE lead_ref=? AND status='pendente'", "n%d" % ids[nome]))
        self.assertEqual(pend("Interessado Imob"), 0)
        self.assertEqual(pend("Descadastro Imob"), 0)
        self.assertEqual(pend("Devolvido Imob"), 0)
        self.assertEqual(pend("Fora Imob"), 3)
        # traducao e resumo guardados
        r1 = self.sql("SELECT traducao, resumo FROM respostas WHERE lead_ref=?", "n%d" % ids["Interessado Imob"])[0]
        self.assertTrue(r1["traducao"].startswith("[pt]") and r1["resumo"])

    def test_segunda_leitura_nao_duplica(self):
        self._setup_nexora()
        self.inbox = [msg_gmail("m1", "Int <int@imob.example>", "Re", "Interested, thanks")]
        self.assertEqual(mail.sync("nexora")["novas"], 1)
        self.assertEqual(mail.sync("nexora")["novas"], 0)
        self.assertEqual(len(self.sql("SELECT * FROM respostas")), 1)

    def test_resposta_de_lead_do_atlas_por_email(self):
        lid = self.novo_lead(canal="email", telefone=None, email="cli@loca.example", nome="Loca Email")
        self.post("/api/leads/%d/sent" % lid)
        self.inbox = [msg_gmail("a1", "Cli <cli@loca.example>", "Re: ideia", "Tenho interesse sim, quero conversar")]
        self.assertEqual(mail.sync("atlas")["novas"], 1)
        self.assertEqual(self.lead_db(lid)["etapa"], "Negociando")

    def test_ia_fora_do_ar_registra_resposta_sem_perder_e_reclassifica_depois(self):
        import ia
        ids = self._setup_nexora()
        ia.executor = lambda p, t=None: (_ for _ in ()).throw(RuntimeError("fora"))
        self.inbox = [msg_gmail("m1", "Int <int@imob.example>", "Re", "Interested! Let's talk, call me")]
        self.assertEqual(mail.sync("nexora")["novas"], 1)
        self.assertIsNone(self.sql("SELECT classificacao FROM respostas")[0]["classificacao"])
        self.assertEqual(self._etapa(ids, "Interessado Imob"), "Respondeu")       # ja saiu de Contatado
        ia.executor = __import__("base").ia_falsa
        ia._estado.update(falhas=0, ate=0.0)
        mail.reclassificar()
        self.assertEqual(self.sql("SELECT classificacao FROM respostas")[0]["classificacao"], "reuniao")
        self.assertEqual(self._etapa(ids, "Interessado Imob"), "Negociando")


class TestFollowupEmail(BaseCRM):
    def _atlas_email_contatados(self, n, prefixo="Loca"):
        ids = []
        for i in range(n):
            lid = self.novo_lead(canal="email", telefone=None, email="%s%d@loca.example" % (prefixo.lower(), i), nome="%s %d" % (prefixo, i), assunto="Ideia")
            self.post("/api/leads/%d/sent" % lid)
            ids.append(lid)
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=? WHERE passo=1", (datetime.now(timezone.utc).date().isoformat(),))
        c.execute("DELETE FROM envios")            # contatos feitos "dias atras": nao contam no teto de hoje
        c.commit()
        c.close()
        return ids

    def _ligar(self, conta="atlas"):
        self.post("/api/config", {"chave": "auto_followup_email_" + conta, "valor": "1"})

    def test_desligado_nao_envia(self):
        self._atlas_email_contatados(3)
        self.assertEqual(mail.enviar_followups("atlas"), {"enviados": 0, "motivo": "desligado"})
        self.assertEqual(self.enviados, [])

    def test_limite_de_20_por_dia_e_intervalo_de_45s(self):
        self._atlas_email_contatados(25)
        self._ligar()
        r = mail.enviar_followups("atlas")
        self.assertEqual(r["enviados"], 20)
        self.assertEqual(len(self.enviados), 20)
        self.assertEqual(self.esperas, [45] * 19)         # 45s ENTRE envios (19 intervalos para 20 e-mails)
        # rodar de novo no mesmo dia nao passa de 20
        self.assertEqual(mail.enviar_followups("atlas")["enviados"], 0)
        self.assertEqual(len(self.enviados), 20)

    def test_limite_considera_o_que_ja_foi_enviado_hoje(self):
        self._atlas_email_contatados(15)
        c = store.crm()
        for i in range(8):
            store.registrar_envio(c, {"ref": "c9%d" % i, "conta": "atlas", "canal": "email"}, 0, "auto_email")
        c.commit()
        c.close()
        self._ligar()
        self.assertEqual(mail.enviar_followups("atlas")["enviados"], 12)

    def test_conteudo_do_email_tem_descadastro_e_re(self):
        self._atlas_email_contatados(1)
        self._ligar()
        mail.enviar_followups("atlas")
        import email
        m = email.message_from_bytes(self.enviados[0])
        corpo = m.get_payload(decode=True).decode("utf-8")
        self.assertTrue(m["Subject"].startswith("Re: "))
        self.assertIn("sair", corpo)
        self.assertIn("mailto:", m["List-Unsubscribe"])
        self.assertEqual(m["To"], "loca0@loca.example")

    def test_bloqueado_e_fora_de_contatado_nao_recebem(self):
        ids = self._atlas_email_contatados(3)
        c = store.crm()
        c.execute("INSERT INTO bloqueios (conta, chave, motivo, created_at) VALUES ('atlas','loca0@loca.example','recusou','x')")
        c.commit()
        c.close()
        self.post("/api/leads/%d/resposta" % ids[1], {"texto": "oi", "classificacao": "interessado"})   # respondeu: tarefas canceladas
        self._ligar()
        self.assertEqual(mail.enviar_followups("atlas")["enviados"], 1)
        self.assertIn("loca2@loca.example", self.enviados[0].decode("utf-8", "replace"))

    def test_nexora_sem_endereco_postal_verificado_nao_envia(self):
        self.nexora_lead("Lead N", "n@imob.example", enviado_ha_dias=4)
        self.get("/api/hoje?conta=nexora")
        self._ligar("nexora")
        env = dict(ENV_FALSO, NEXORA_POSTAL_ADDRESS_VERIFIED="false")
        mail.load_env = lambda: env
        self.assertEqual(mail.enviar_followups("nexora")["enviados"], 0)
        self.assertEqual(self.enviados, [])

    def test_nexora_teto_conta_os_envios_frios_do_dia(self):
        for i in range(12):                      # 12 e-mails frios enviados hoje pelo fluxo original
            self.nexora_lead("Frio %d" % i, "frio%d@imob.example" % i, status="enviado", enviado_ha_dias=0)
        for i in range(10):                      # 10 leads com follow-up vencido
            self.nexora_lead("FU %d" % i, "fu%d@imob.example" % i, enviado_ha_dias=4)
        self.get("/api/hoje?conta=nexora")
        self._ligar("nexora")
        self.assertEqual(mail.enviar_followups("nexora")["enviados"], 8)      # 20 - 12
        raw = self.enviados[0].decode("utf-8", "replace")
        self.assertIn("1 Test St", base64.b64decode("".join(raw.split("\n\n", 1)[1].split())).decode("utf-8") if "base64" in raw else raw)

    def test_nexora_followup_nao_vai_para_email_suprimido(self):
        lid = self.nexora_lead("Supr", "supr@imob.example", enviado_ha_dias=4)
        self.get("/api/hoje?conta=nexora")
        conn = ndb.connect()
        ndb.add_suppression(conn, "supr@imob.example", "teste")
        conn.commit()
        conn.close()
        self._ligar("nexora")
        self.assertEqual(mail.enviar_followups("nexora")["enviados"], 0)


class TestEmailAtlasAprovado(BaseCRM):
    def _pronto(self, i, aprovado=True, email=None):
        lid = self.novo_lead(canal="email", telefone=None, email=email or "p%d@loca.example" % i, nome="Pronto %d" % i, assunto="Ideia", mensagem="Corpo do e-mail")
        if aprovado:
            self.post("/api/leads/%d/aprovar" % lid)
        return lid

    def test_so_envia_aprovados_e_cria_followups(self):
        a = self._pronto(1)
        b = self._pronto(2, aprovado=False)
        r = mail.enviar_atlas_aprovados()
        self.assertEqual(r["enviados"], 1)
        self.assertEqual(self.lead_db(a)["etapa"], "Contatado")
        self.assertEqual(self.lead_db(b)["etapa"], "Pronto")
        self.assertEqual(len(self.sql("SELECT * FROM tarefas WHERE lead_ref=?", "c%d" % a)), 3)

    def test_teto_e_intervalo(self):
        for i in range(23):
            self._pronto(i)
        self.assertEqual(mail.enviar_atlas_aprovados()["enviados"], 20)
        self.assertEqual(self.esperas, [45] * 19)         # 45s ENTRE envios (19 intervalos para 20 e-mails)

    def test_bloqueado_vira_perdido_sem_enviar(self):
        lid = self._pronto(1, email="bloq@loca.example")
        c = store.crm()
        c.execute("INSERT INTO bloqueios (conta, chave, motivo, created_at) VALUES ('atlas','bloq@loca.example','bounce','x')")
        c.commit()
        c.close()
        self.assertEqual(mail.enviar_atlas_aprovados()["enviados"], 0)
        self.assertEqual(self.lead_db(lid)["etapa"], "Perdido")
        self.assertEqual(self.enviados, [])


if __name__ == "__main__":
    import unittest
    unittest.main()
