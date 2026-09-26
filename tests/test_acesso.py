"""Login do acesso externo: hash, sessao assinada, expiracao e bloqueio por tentativas."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CRM_ACESSO"] = os.path.join(tempfile.mkdtemp(), "acesso.json")
import acesso  # noqa: E402


class TestAcesso(unittest.TestCase):
    def setUp(self):
        acesso.definir("Fulano", "senha-de-teste")
        acesso._falhas.clear()

    def test_senha_nao_fica_em_texto(self):
        self.assertNotIn("senha-de-teste", open(acesso.ARQ, encoding="utf-8").read())

    def test_credencial_certa_e_erradas(self):
        self.assertTrue(acesso.verificar("1.1.1.1", "Fulano", "senha-de-teste"))
        self.assertFalse(acesso.verificar("1.1.1.1", "fulano", "senha-de-teste"))
        self.assertFalse(acesso.verificar("1.1.1.1", "Fulano", "outra"))

    def test_bloqueia_apos_cinco_falhas_mesmo_com_senha_certa(self):
        for _ in range(acesso.MAX_FALHAS):
            acesso.verificar("2.2.2.2", "Fulano", "errada")
        self.assertTrue(acesso.bloqueado("2.2.2.2"))
        self.assertFalse(acesso.verificar("2.2.2.2", "Fulano", "senha-de-teste"))
        self.assertTrue(acesso.verificar("3.3.3.3", "Fulano", "senha-de-teste"))       # outro IP nao e afetado

    def test_token_valido_adulterado_e_expirado(self):
        t = acesso.novo_token()
        self.assertTrue(acesso.token_valido(t))
        exp, ass = t.split(".")
        self.assertFalse(acesso.token_valido("%d.%s" % (int(exp) + 999, ass)))
        self.assertFalse(acesso.token_valido(""))
        self.assertFalse(acesso.token_valido("abc"))
        velho = "%d.%s" % (int(time.time()) - 1, acesso._assinar(acesso._cfg(), int(time.time()) - 1))
        self.assertFalse(acesso.token_valido(velho))

    def test_trocar_senha_invalida_sessoes_antigas(self):
        t = acesso.novo_token()
        acesso.definir("Fulano", "nova")
        self.assertFalse(acesso.token_valido(t))


if __name__ == "__main__":
    unittest.main()
