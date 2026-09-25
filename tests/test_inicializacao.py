"""Inicializacao no Windows: cria e remove uma tarefa agendada de TESTE (nome proprio, nunca a real)."""
import os
import subprocess
import sys
import unittest

CRM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = "CRM-TESTE-INICIALIZACAO"


def ps(*args):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", *args], capture_output=True, text=True, timeout=120)


@unittest.skipUnless(sys.platform == "win32", "so no Windows")
class TestInicializacao(unittest.TestCase):
    def tearDown(self):
        ps("-File", os.path.join(CRM, "remover-inicializacao.ps1"), "-Nome", NOME)

    def test_tarefa_e_criada_com_reinicio_automatico_e_removida(self):
        r = ps("-File", os.path.join(CRM, "instalar-inicializacao.ps1"), "-Nome", NOME, "-SemIniciar")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        consulta = ps("-Command", "$t = Get-ScheduledTask -TaskName '%s'; "
                      "$s = $t.Settings; Write-Output ($t.Actions[0].Arguments + '|' + $s.RestartCount + '|' + $s.RestartInterval + '|' + $s.MultipleInstances + '|' + $t.Triggers[0].CimClass.CimClassName)" % NOME)
        self.assertEqual(consulta.returncode, 0, consulta.stderr)
        argumentos, tentativas, intervalo, instancias, gatilho = consulta.stdout.strip().split("|")
        self.assertEqual(argumentos, "server.py")
        self.assertEqual(int(tentativas), 999)
        self.assertEqual(intervalo, "PT1M")
        self.assertEqual(instancias, "IgnoreNew")                                    # nunca duas copias
        self.assertIn("LogonTrigger", gatilho)
        rm = ps("-File", os.path.join(CRM, "remover-inicializacao.ps1"), "-Nome", NOME)
        self.assertIn("removida", rm.stdout)
        self.assertNotEqual(ps("-Command", "Get-ScheduledTask -TaskName '%s' -ErrorAction Stop" % NOME).returncode, 0)

    def test_instalar_duas_vezes_nao_duplica(self):
        for _ in range(2):
            self.assertEqual(ps("-File", os.path.join(CRM, "instalar-inicializacao.ps1"), "-Nome", NOME, "-SemIniciar").returncode, 0)
        n = ps("-Command", "@(Get-ScheduledTask | Where-Object { $_.TaskName -eq '%s' }).Count" % NOME).stdout.strip()
        self.assertEqual(n, "1")


if __name__ == "__main__":
    unittest.main()
