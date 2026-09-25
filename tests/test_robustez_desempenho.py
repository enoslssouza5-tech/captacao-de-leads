"""Robustez (falhas de Gmail, internet, IA, banco corrompido, workers) e desempenho com muitos leads."""
import os
import sqlite3
import tempfile
import threading
import time
import urllib.error

from base import BaseCRM, store, ndb, gmail_api, ia, mail, ia_falsa
import backup
import workers


class TestBackupEIntegridade(BaseCRM):
    def test_backup_e_restauracao_de_banco_corrompido(self):
        d = tempfile.mkdtemp(prefix="crm-bk-")
        db = os.path.join(d, "teste.sqlite3")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany("INSERT INTO t (v) VALUES (?)", [("a",), ("b",), ("c",)])
        conn.commit()
        conn.close()
        bk = os.path.join(d, "bk")
        feitos = backup.fazer_backup(bk, {"teste": (db, False)})
        self.assertEqual(len(feitos), 1)
        self.assertEqual(backup.fazer_backup(bk, {"teste": (db, False)}), [])          # um por dia
        self.assertTrue(backup.integridade_ok(db))
        with open(db, "r+b") as f:                                                     # corrompe o arquivo
            f.seek(0)
            f.write(b"\x00" * 200)
        self.assertFalse(backup.integridade_ok(db))
        r = backup.verificar_e_restaurar(db, bk, "teste")
        self.assertEqual(r["acao"], "restaurado")
        self.assertTrue(os.path.exists(r["arquivo_corrompido"]))                       # o corrompido fica guardado, nao e apagado
        self.assertEqual(sqlite3.connect(db).execute("SELECT COUNT(*) FROM t").fetchone()[0], 3)

    def test_banco_saudavel_nao_e_tocado(self):
        d = tempfile.mkdtemp(prefix="crm-bk-")
        db = os.path.join(d, "ok.sqlite3")
        sqlite3.connect(db).execute("CREATE TABLE t (id INTEGER)").connection.commit()
        self.assertEqual(backup.verificar_e_restaurar(db, os.path.join(d, "bk"), "ok")["acao"], "ok")

    def test_corrompido_sem_backup_nao_apaga_nada(self):
        d = tempfile.mkdtemp(prefix="crm-bk-")
        db = os.path.join(d, "x.sqlite3")
        open(db, "wb").write(b"isso nao e um banco sqlite" * 50)
        r = backup.verificar_e_restaurar(db, os.path.join(d, "bk"), "x")
        self.assertEqual(r["acao"], "sem_backup")
        self.assertTrue(os.path.exists(db))

    def test_retencao_mantem_so_os_ultimos(self):
        d = tempfile.mkdtemp(prefix="crm-bk-")
        db = os.path.join(d, "a.sqlite3")
        sqlite3.connect(db).execute("CREATE TABLE t (id INTEGER)").connection.commit()
        bk = os.path.join(d, "bk")
        os.makedirs(bk)
        for i in range(20):
            open(os.path.join(bk, "a-2026010%02d-000000.sqlite3" % (i % 10) if i < 10 else "a-2026011%02d-000000.sqlite3" % (i - 10)), "w").close()
        backup.fazer_backup(bk, {"a": (db, False)}, manter=5, forcar=True)
        self.assertEqual(len([f for f in os.listdir(bk) if f.startswith("a-")]), 5)


class TestFalhasExternas(BaseCRM):
    def test_gmail_sem_internet_levanta_erro_claro_e_nao_corrompe_dados(self):
        self.nexora_lead("Lead", "l@x.example", enviado_ha_dias=3)
        gmail_api.list_inbox_message_ids = lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("sem internet"))
        with self.assertRaises(urllib.error.URLError):
            mail.sync("nexora")
        self.assertEqual(self.sql("SELECT * FROM respostas"), [])
        self.assertEqual(self.get("/api/board?conta=nexora&canal=email")[0], 200)     # o CRM segue de pe

    def test_gmail_desconectado_no_painel_de_email(self):
        mail.access = lambda conta: (None, {})
        st, r = self.get("/api/gmail/pastas?conta=atlas")
        self.assertEqual(st, 200)
        self.assertIn("erro", r)

    def test_falha_de_envio_marca_a_tarefa_e_nao_derruba_o_lote(self):
        ids = []
        for i in range(3):
            lid = self.novo_lead(canal="email", telefone=None, email="e%d@x.example" % i, nome="E%d" % i, assunto="Ideia")
            self.post("/api/leads/%d/sent" % lid)
            ids.append(lid)
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=date('now') WHERE passo=1")
        c.execute("DELETE FROM envios")
        c.commit()
        c.close()
        self.post("/api/config", {"chave": "auto_followup_email_atlas", "valor": "1"})
        chamadas = []

        def enviar(at, raw):
            chamadas.append(1)
            if len(chamadas) == 2:
                raise urllib.error.HTTPError("u", 500, "erro do Gmail", {}, None)
            return {"id": "ok"}
        gmail_api.send_message = enviar
        r = mail.enviar_followups("atlas")
        self.assertEqual(r["enviados"], 2)                                             # 2 sairam, 1 falhou, o lote continuou
        status = sorted(x["status"] for x in self.sql("SELECT status FROM tarefas WHERE passo=1"))
        self.assertEqual(status, ["erro", "feita", "feita"])

    def test_ia_fora_do_ar_entra_em_recuo_e_volta(self):
        def falha(p, t=None):
            raise RuntimeError("claude -p indisponivel")
        ia.executor = None
        orig = ia.subprocess.run
        ia.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(OSError("claude nao encontrado"))
        try:
            with self.assertRaises(RuntimeError):
                ia.run_claude("oi")
            self.assertFalse(ia.disponivel())                                           # entrou em recuo
            self.assertEqual(ia.estado_ia()["falhas_seguidas"], 1)
        finally:
            ia.subprocess.run = orig
        ia._estado.update(falhas=0, ate=0.0)
        self.assertTrue(ia.disponivel())

    def test_resposta_sem_json_da_ia_nao_derruba(self):
        ia.executor = lambda p, t=None: "desculpe, nao consegui"
        with self.assertRaises(RuntimeError):
            ia.classify_reply("oi")
        self.assertIsNone(mail._classificar("oi"))


class TestWorkers(BaseCRM):
    def test_loop_do_worker_sobrevive_a_excecoes_e_registra_a_saude(self):
        chamadas = []

        def passo():
            chamadas.append(1)
            if len(chamadas) == 1:
                raise RuntimeError("falha temporaria")
            if len(chamadas) >= 3:
                raise SystemExit
        orig = workers.time.sleep
        workers.time.sleep = lambda s: None
        try:
            try:
                workers._loop("teste_worker", 1, passo)
            except SystemExit:
                pass
        finally:
            workers.time.sleep = orig
        self.assertGreaterEqual(len(chamadas), 3)                                       # depois da falha, continuou rodando
        self.assertTrue(workers.SAUDE["teste_worker"]["ok"])
        workers.SAUDE.pop("teste_worker", None)

    def test_saude_expoe_a_falha_de_um_worker(self):
        workers.registrar("gmail_atlas", False, "invalid_grant: token revogado")
        s = self.get("/api/saude")[1]
        self.assertFalse(s["workers"]["gmail_atlas"]["ok"])
        self.assertIn("invalid_grant", s["workers"]["gmail_atlas"]["erro"])
        workers.SAUDE.pop("gmail_atlas", None)

    def test_erro_em_thread_de_fundo_vai_para_o_log_sem_derrubar(self):
        workers.configurar_log()
        feito = threading.Event()
        workers.spawn(lambda: (_ for _ in ()).throw(RuntimeError("erro proposital")))
        time.sleep(0.4)
        log = open(os.path.join(workers.LOG_DIR, "crm.log"), encoding="utf-8").read()
        self.assertIn("erro proposital", log)

    def test_backup_diario_pelo_passo_de_manutencao(self):
        d = tempfile.mkdtemp(prefix="crm-bk-")
        orig = workers.BACKUP_DIR
        workers.BACKUP_DIR = d
        try:
            workers.passo_manutencao()
        finally:
            workers.BACKUP_DIR = orig
        nomes = os.listdir(d)
        self.assertTrue(any(n.startswith("crm-") for n in nomes))


class TestConcorrencia(BaseCRM):
    def test_muitas_requisicoes_simultaneas_sem_banco_travado(self):
        erros, ok = [], []

        def cliente(n):
            for i in range(15):
                st, r = self.post("/api/leads", {"conta": "atlas", "canal": "whatsapp", "nome": "C%d-%d" % (n, i), "telefone": "(77) 9%04d-%04d" % (n, i), "etapa": "Pronto", "mensagem": "x"})
                if st >= 500:
                    erros.append((st, r))
                self.get("/api/painel?conta=atlas")
                st2, _ = self.get("/api/acoes?conta=atlas")
                if st2 >= 500:
                    erros.append(("acoes", st2))
                ok.append(1)
        fios = [threading.Thread(target=cliente, args=(n,)) for n in range(8)]
        [t.start() for t in fios]
        [t.join(120) for t in fios]
        self.assertEqual(erros, [])
        self.assertEqual(len(ok), 8 * 15)
        self.assertEqual(len(self.sql("SELECT * FROM leads")), 8 * 15)


class TestDesempenho(BaseCRM):
    N_LEADS = 3000

    def _popular(self):
        c = store.crm()
        etapas = ["Novo", "Pronto", "Contatado", "Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"]
        c.execute("BEGIN")
        for i in range(self.N_LEADS):
            e = etapas[i % len(etapas)]
            canal = "whatsapp" if i % 2 else "email"
            c.execute("INSERT INTO leads (conta,canal,etapa,nome,telefone,email,cidade,fonte,avaliacoes,tipo_dor,mensagem,created_at,updated_at,sent_at) VALUES ('atlas',?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (canal, e, "Empresa %d" % i, "(77) 9%04d-%04d" % (i // 10000, i % 10000), "e%d@x.example" % i, "Cidade", "apify", 50 + i % 200, ["sem_site", "site_velho", "sem_conversao"][i % 3], "Oi, me chamo Enos.",
                       store.now(), store.now(), store.now() if e not in ("Novo", "Pronto") else None))
        c.commit()
        rows = c.execute("SELECT id, etapa FROM leads").fetchall()
        for r in rows:
            ref = "c%d" % r["id"]
            if r["etapa"] in ("Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"):
                c.execute("INSERT INTO envios (lead_ref,conta,canal,passo,tipo_dor,enviado_em,origem) VALUES (?,?,?,?,?,?,?)", (ref, "atlas", "whatsapp", 0, "sem_site", store.now(), "teste"))
                for p in (1, 2, 3):
                    c.execute("INSERT OR IGNORE INTO tarefas (conta,canal,lead_ref,nome,passo,due_date,mensagem,status) VALUES ('atlas','whatsapp',?,?,?,date('now',?),?, 'pendente')", (ref, "E", p, "%d day" % (p * 3 - 4), "Oi"))
            if r["etapa"] in ("Respondeu", "Negociando", "Fechado", "Perdido"):
                for _ in range(3):
                    c.execute("INSERT INTO respostas (lead_ref,conta,texto,classificacao,origem,created_at) VALUES (?,?,?,?,?,?)", (ref, "atlas", "resposta", "interessado", "teste", store.now()))
        c.commit()
        c.close()

    def _tempo(self, caminho):
        t = time.time()
        st, _ = self.get(caminho)
        self.assertEqual(st, 200, caminho)
        return time.time() - t

    def test_telas_principais_respondem_rapido_com_milhares_de_leads(self):
        self._popular()
        limites = {"/api/painel?conta=atlas": 2.5, "/api/acoes?conta=atlas": 2.5, "/api/board?conta=atlas&canal=whatsapp": 2.5, "/api/radar?conta=atlas": 2.5,
                   "/api/aprendizado?conta=atlas": 2.5, "/api/captacao?conta=atlas": 2.5, "/api/stats?conta=atlas": 2.5, "/api/financeiro?conta=atlas": 2.5, "/api/conversas?conta=atlas": 2.5}
        lentos = {}
        for caminho, lim in limites.items():
            t = min(self._tempo(caminho) for _ in range(2))
            print("\n  %-42s %.2fs" % (caminho, t), end="")
            if t > lim:
                lentos[caminho] = round(t, 2)
        self.assertEqual(lentos, {}, "endpoints acima do limite com %d leads" % self.N_LEADS)


if __name__ == "__main__":
    import unittest
    unittest.main()
