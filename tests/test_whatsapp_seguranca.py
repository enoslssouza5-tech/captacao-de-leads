"""WhatsApp (eventos, integracao Node->Python, gerenciador do processo) e seguranca da API."""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

from base import BaseCRM, store, server, CRM_DIR
import wa

NODE = "node"
QTESTS = os.path.dirname(os.path.abspath(__file__))


def pid_vivo(pid):
    out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout
    return str(pid) in out


class TestEventosWhatsApp(BaseCRM):
    def _evento(self, direcao, tel, texto="oi", tipo="chat"):
        st, r = self.post("/api/wa/event", {"direcao": direcao, "telefone": tel, "texto": texto, "tipo": tipo, "ts": 1700000000})
        self.assertEqual(st, 200)
        return r

    def test_envio_detectado_move_lead_cria_followups_e_guarda_conversa(self):
        lid = self.novo_lead(telefone="(77) 99888-7766")
        r = self._evento("saida", "5577998887766", "Bom dia!")
        self.assertEqual(r["acao"], "envio_detectado")
        self.assertEqual(self.lead_db(lid)["etapa"], "Contatado")
        self.assertEqual(len(self.sql("SELECT * FROM tarefas WHERE lead_ref=?", "c%d" % lid)), 3)
        m = self.get("/api/wa/conversa?ref=c%d" % lid)[1]["mensagens"]
        self.assertEqual([(x["direcao"], x["texto"]) for x in m], [("saida", "Bom dia!")])

    def test_numero_fora_do_crm_e_ignorado_e_nada_e_guardado(self):
        self.novo_lead()
        r = self._evento("entrada", "5511900000000", "mensagem privada de outra pessoa")
        self.assertEqual(r, {"ignorado": True})
        self.assertEqual(self.sql("SELECT * FROM wa_mensagens"), [])
        self.assertEqual(self.sql("SELECT * FROM respostas"), [])

    def test_variacoes_do_numero_brasileiro_sao_reconhecidas(self):
        lid = self.novo_lead(telefone="(77) 99888-7766")
        for variante in ("5577998887766", "557798887766", "77998887766", "+55 77 9 9888-7766"):
            with self.subTest(variante=variante):
                self.assertEqual(self._evento("entrada", variante, "ok")["acao"], "resposta_registrada")

    def test_resposta_e_classificada_e_move_o_card(self):
        lid = self.novo_lead()
        self._evento("saida", "5577998887766")
        self._evento("entrada", "5577998887766", "Tenho interesse, quero conversar sobre orcamento")
        self.esperar(lambda: self.lead_db(lid)["etapa"] == "Negociando", msg="resposta nao classificada/movida")
        self.assertEqual(len(self.sql("SELECT * FROM tarefas WHERE lead_ref=? AND status='pendente'", "c%d" % lid)), 0)

    def test_recusa_no_whatsapp_bloqueia(self):
        lid = self.novo_lead()
        self._evento("saida", "5577998887766")
        self._evento("entrada", "5577998887766", "Nao tenho interesse, obrigado")
        self.esperar(lambda: self.lead_db(lid)["etapa"] == "Perdido")
        self.assertEqual([x["chave"] for x in self.sql("SELECT chave FROM bloqueios")], ["(77) 99888-7766"])

    def test_mensagem_enviada_com_followup_vencido_conclui_a_tarefa(self):
        lid = self.novo_lead()
        self._evento("saida", "5577998887766")
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=date('now','-1 day') WHERE lead_ref=? AND passo=1", ("c%d" % lid,))
        c.commit()
        c.close()
        self._evento("saida", "5577998887766", "Passando para saber se viu")
        t = {x["passo"]: x["status"] for x in self.sql("SELECT passo, status FROM tarefas WHERE lead_ref=?", "c%d" % lid)}
        self.assertEqual(t, {1: "feita", 2: "pendente", 3: "pendente"})
        self.assertEqual(self.sql("SELECT auto FROM tarefas WHERE passo=1")[0]["auto"], 1)

    def test_mensagem_enviada_sem_followup_vencido_nao_consome_tarefa(self):
        lid = self.novo_lead()
        self._evento("saida", "5577998887766")
        self._evento("saida", "5577998887766", "outra mensagem qualquer")
        self.assertEqual({x["status"] for x in self.sql("SELECT status FROM tarefas WHERE lead_ref=?", "c%d" % lid)}, {"pendente"})

    def test_fila_do_dia_respeita_limite_e_ignora_telefone_fixo(self):
        for i in range(20):
            self.novo_lead(nome="L%d" % i, telefone="(77) 99%03d-0000" % i)
        self.novo_lead(nome="Fixo", telefone="(77) 3221-0000", sem_whatsapp=0)
        itens = [i for i in self.get("/api/hoje?conta=atlas")[1]["itens"] if i["tipo"] == "primeiro" and i["canal"] == "whatsapp"]
        self.assertEqual(len(itens), 15)


class TestIntegracaoNodePython(BaseCRM):
    def test_observador_real_com_cliente_falso_alimenta_o_crm(self):
        lid = self.novo_lead(telefone="(77) 99888-7766")
        env = dict(os.environ, CRM_URL=self.base, NUM_LEAD="5577998887766", WA_BATIMENTO_MS="200")
        p = subprocess.run([NODE, os.path.join(QTESTS, "watcher_harness.js")], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertTrue(all(v == "bloqueado" for v in res["bloqueio"].values()), res["bloqueio"])   # nao consegue enviar nada
        msgs = self.get("/api/wa/conversa?ref=c%d" % lid)[1]["mensagens"]
        self.assertEqual([(m["direcao"], m["texto"]) for m in msgs],
                         [("saida", "Bom dia!"), ("entrada", "Tenho interesse, quero conversar"), ("entrada", "[mensagem de audio]")])   # sem numero desconhecido, grupo ou status
        self.esperar(lambda: self.lead_db(lid)["etapa"] == "Negociando", msg="lead nao chegou em Negociando")
        self.assertEqual(len(self.sql("SELECT * FROM envios WHERE lead_ref=? AND passo=0", "c%d" % lid)), 1)


class TestGerenciadorWhatsApp(BaseCRM):
    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp(prefix="wa-test-")
        self.orig = (wa.ESPERAS_REINICIO, wa.QR_VALIDADE_S, wa.SEM_SINAL_S, wa.MAX_RENOVACOES_QR)

    def tearDown(self):
        wa.ESPERAS_REINICIO, wa.QR_VALIDADE_S, wa.SEM_SINAL_S, wa.MAX_RENOVACOES_QR = self.orig
        if hasattr(self, "m"):
            self.m.parar()
        super().tearDown()

    def _mgr(self, modo="vivo"):
        self.m = wa.WAManager(cmd=[sys.executable, os.path.join(QTESTS, "fake_watcher.py"), modo], cwd=self.dir, log_path=os.path.join(self.dir, "w.log"),
                              flag_path=os.path.join(self.dir, ".linked"), marcadores=[os.path.join(self.dir, "NUNCA-EXISTE")])
        return self.m

    def test_parar_mata_o_processo_e_o_filho(self):
        m = self._mgr()
        m.iniciar()
        time.sleep(1.5)
        pai = m.proc.pid
        filho = int(open(os.path.join(self.dir, "w.log")).read().split("filho")[1].split()[0])
        self.assertTrue(pid_vivo(pai) and pid_vivo(filho))
        m.parar()
        time.sleep(1)
        self.assertFalse(pid_vivo(pai))
        self.assertFalse(pid_vivo(filho), "o filho (Chrome) ficou orfao")
        self.assertEqual(m.publico()["estado"], "parado")

    def test_processo_que_morre_e_reiniciado_e_o_erro_aparece(self):
        wa.ESPERAS_REINICIO = (0, 0)
        m = self._mgr("morre")
        m.iniciar()
        time.sleep(1)
        m.verificar()
        p = m.publico()
        self.assertEqual(p["estado"], "reiniciando")
        self.assertIn("already running", p["motivo"])        # o erro real do Chrome continua visivel durante o reinicio
        self.assertEqual(p["tentativas"], 1)
        time.sleep(1)
        m.verificar()
        m.verificar()
        self.assertEqual(m.tentativas, 2)
        time.sleep(1)
        m.verificar()
        self.assertFalse(m.querido)                           # desistiu apos esgotar tentativas
        self.assertEqual(m.publico()["estado"], "erro")

    def test_batimento_nao_apaga_o_qr(self):
        m = self._mgr()
        m.iniciar()
        m.receber_status({"estado": "qr", "qr": "data:image/png;base64,AAA"})
        m.receber_status({"estado": "batimento", "atual": "qr"})
        p = m.publico()
        self.assertEqual((p["estado"], p["qr"]), ("qr", "data:image/png;base64,AAA"))

    def test_qr_parado_e_renovado_e_depois_pede_acao_do_usuario(self):
        wa.QR_VALIDADE_S, wa.MAX_RENOVACOES_QR = 0.3, 1
        m = self._mgr()
        m.iniciar()
        m.receber_status({"estado": "qr", "qr": "data:image/png;base64,AAA"})
        pid1 = m.proc.pid
        time.sleep(0.5)
        m.verificar()                                          # 1a renovacao: reinicia sozinho
        self.assertNotEqual(m.proc.pid, pid1)
        m.receber_status({"estado": "qr", "qr": "data:image/png;base64,BBB"})
        time.sleep(0.5)
        m.verificar()                                          # estourou o limite: aguarda o usuario
        p = m.publico()
        self.assertEqual(p["estado"], "qr_expirado")
        self.assertIn("novo QR", p["motivo"])
        m.novo_qr()
        self.assertEqual(m.publico()["estado"], "iniciando")

    def test_qr_que_renova_nao_e_reiniciado(self):
        wa.QR_VALIDADE_S = 0.4
        m = self._mgr()
        m.iniciar()
        pid = m.proc.pid
        for i in range(4):
            m.receber_status({"estado": "qr", "qr": "data:image/png;base64,Q%d" % i})
            time.sleep(0.2)
            m.verificar()
        self.assertEqual(m.proc.pid, pid)

    def test_conexao_grava_marca_de_vinculo_e_zera_contadores(self):
        m = self._mgr()
        m.iniciar()
        m.tentativas = 3
        self.assertFalse(m.ja_vinculado())
        m.receber_status({"estado": "conectado"})
        self.assertTrue(m.ja_vinculado())
        self.assertEqual(m.tentativas, 0)

    def test_sem_batimento_reinicia(self):
        wa.SEM_SINAL_S = 0.3
        m = self._mgr()
        m.iniciar()
        pid = m.proc.pid
        time.sleep(0.5)
        m.verificar()
        self.assertNotEqual(m.proc.pid, pid)

    def test_orfaos_sao_encerrados_ao_iniciar(self):
        marcador = os.path.join(self.dir, "orfao-marker")
        orfao = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)  # %s" % marcador])
        time.sleep(0.5)
        m = wa.WAManager(cmd=[sys.executable, os.path.join(QTESTS, "fake_watcher.py")], cwd=self.dir, log_path=os.path.join(self.dir, "w.log"),
                         flag_path=os.path.join(self.dir, ".linked"), marcadores=[marcador])
        self.m = m
        self.assertTrue(pid_vivo(orfao.pid))
        m.iniciar()
        time.sleep(1)
        self.assertFalse(pid_vivo(orfao.pid), "processo orfao nao foi encerrado")


class TestSeguranca(BaseCRM):
    def test_origem_externa_e_bloqueada_em_get_e_post(self):
        for metodo, caminho in (("GET", "/api/stats?conta=atlas"), ("POST", "/api/leads")):
            st, _ = self.http(metodo, caminho, {"conta": "atlas", "canal": "whatsapp", "nome": "X"} if metodo == "POST" else None, headers={"Origin": "https://site-malicioso.example"})
            self.assertEqual(st, 403, metodo)
        self.assertEqual(self.sql("SELECT * FROM leads"), [])

    def test_origem_propria_e_aceita(self):
        st, _ = self.get("/api/stats?conta=atlas", headers={"Origin": self.base})
        self.assertEqual(st, 200)

    def test_host_estranho_e_bloqueado_contra_dns_rebinding(self):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        c.request("GET", "/api/stats?conta=atlas", headers={"Host": "atacante.example:%d" % self.porta})
        self.assertEqual(c.getresponse().status, 403)

    def test_post_sem_json_e_recusado_impede_form_cross_site(self):
        st, _ = self.post("/api/gmail/send", {"conta": "atlas", "para": "x@y.example", "assunto": "a", "corpo": "b"}, json_ct=False, headers={"Content-Type": "text/plain"})
        self.assertEqual(st, 415)

    def test_segunda_instancia_nao_consegue_usar_a_mesma_porta(self):
        with self.assertRaises(OSError):
            server.criar_servidor(self.porta)

    def test_servidor_so_escuta_em_localhost(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_json_invalido_nao_derruba_o_servidor(self):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        c.request("POST", "/api/leads", body=b"\xff\xfe nao e json", headers={"Content-Type": "application/json"})
        self.assertEqual(c.getresponse().status, 400)
        self.assertEqual(self.get("/api/stats?conta=atlas")[0], 200)


if __name__ == "__main__":
    import unittest
    unittest.main()
