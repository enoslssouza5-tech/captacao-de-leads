"""Teste ponta a ponta da interface em navegador real (Chromium via Playwright), contra um servidor ISOLADO.

O servidor de teste usa bancos temporarios, sem workers (nada de Gmail, IA, captacao, envio, backup ou WhatsApp real).
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib import request as urlreq

HERE = os.path.dirname(os.path.abspath(__file__))
CRM = os.path.dirname(HERE)


def porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestInterfaceNoNavegador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="crm-e2e-")
        cls.porta = porta_livre()
        env = dict(os.environ, PORT=str(cls.porta), CRM_DB=os.path.join(cls.tmp, "crm.sqlite3"), CRM_NEXORA_DB=os.path.join(cls.tmp, "nexora.sqlite3"),
                   CRM_SEM_WORKERS="1", CRM_LOG_DIR=os.path.join(cls.tmp, "logs"), CRM_BACKUP_DIR=os.path.join(cls.tmp, "bk"))
        cls.log = open(os.path.join(cls.tmp, "server.log"), "w")
        cls.proc = subprocess.Popen([sys.executable, os.path.join(CRM, "server.py")], cwd=CRM, env=env, stdout=cls.log, stderr=subprocess.STDOUT)
        cls.base = "http://127.0.0.1:%d" % cls.porta
        for _ in range(60):
            try:
                urlreq.urlopen(cls.base + "/api/ping", timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("servidor de teste nao subiu")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        cls.log.close()

    def test_fluxos_da_interface_desktop_e_celular(self):
        p = subprocess.run(["node", os.path.join(HERE, "e2e.js"), self.base], capture_output=True, text=True, timeout=400)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = json.loads(p.stdout.strip().splitlines()[-1])
        print("\n  passou %d verificacoes no navegador" % len(r["passou"]))
        self.assertEqual(r["falhou"], [], "verificacoes que falharam:\n  " + "\n  ".join(r["falhou"]))
        self.assertEqual(r["erros_js"], [], "erros de JavaScript no navegador")

    def test_servidor_de_teste_nao_tocou_no_banco_real(self):
        real = os.path.join(CRM, "crm.sqlite3")
        antes = os.path.getmtime(real) if os.path.exists(real) else None
        urlreq.urlopen(self.base + "/api/stats?conta=atlas", timeout=5).read()
        depois = os.path.getmtime(real) if os.path.exists(real) else None
        self.assertEqual(antes, depois)


if __name__ == "__main__":
    unittest.main()
