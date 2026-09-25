"""Verificacao MANUAL com processos reais do observador do WhatsApp (Node + Chrome) contra o servidor em http://127.0.0.1:4400.
Nao envia nada e nao precisa do celular: valida ciclo de vida, renovacao do QR, limpeza de orfaos e reinicio automatico.
Uso: py tests/verificacao_real_whatsapp.py
"""
import json
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:4400"


def api(rota, corpo=None):
    req = urllib.request.Request(BASE + rota, data=json.dumps(corpo).encode() if corpo is not None else None, method="POST" if corpo is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def procs():
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*wa-watcher*' } | ForEach-Object { $_.Name + ':' + $_.ProcessId }")
    saida = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split()
    return [x for x in saida if x.startswith(("node.exe", "chrome.exe"))]


def esperar(cond, t, msg):
    fim = time.time() + t
    while time.time() < fim:
        if cond():
            return True
        time.sleep(1)
    print("  FALHOU:", msg)
    return False


res = []


def check(nome, ok):
    res.append(ok)
    print(("  OK     " if ok else "  FALHOU ") + nome)


print("1) iniciar e receber QR")
api("/api/wa/stop", {})
check("nenhum processo sobra depois de parar", esperar(lambda: not procs(), 20, "processos vivos: %s" % procs()))
api("/api/wa/start", {})
check("QR aparece em ate 90 s", esperar(lambda: api("/api/conexoes")["whatsapp"]["qr"], 90, "sem QR"))
w = api("/api/conexoes")["whatsapp"]
check("estado 'qr' e QR e uma imagem PNG", w["estado"] == "qr" and w["qr"].startswith("data:image/png;base64,"))

print("2) QR renova sozinho (nunca fica parado)")
primeiro = w["qr"]
check("QR muda em ate 100 s", esperar(lambda: api("/api/conexoes")["whatsapp"]["qr"] not in (None, primeiro), 100, "QR nao mudou"))

print("3) 'Gerar novo QR' reinicia sem deixar orfaos")
antes = set(procs())
api("/api/wa/novo-qr", {})
check("QR novo depois de reiniciar", esperar(lambda: api("/api/conexoes")["whatsapp"]["qr"], 90, "sem QR apos novo-qr"))
depois = set(procs())
check("nenhum processo antigo do observador continua vivo", not (antes & depois))

print("4) matar o Node a forca: o gerenciador reinicia sozinho")
pid_node = next(int(p.split(":")[1]) for p in procs() if p.startswith("node.exe"))
subprocess.run(["taskkill", "/F", "/PID", str(pid_node)], capture_output=True)
novo = lambda: any(p.startswith("node.exe") and int(p.split(":")[1]) != pid_node for p in procs())
check("gerenciador sobe um novo Node em ate 60 s", esperar(novo, 60, "sem novo Node"))
check("QR volta sozinho depois do reinicio automatico", esperar(lambda: api("/api/conexoes")["whatsapp"]["qr"], 120, "QR nao voltou"))

print("5) parar de vez")
api("/api/wa/stop", {})
check("Node e Chrome encerrados", esperar(lambda: not procs(), 30, "sobraram: %s" % procs()))
check("estado 'parado'", api("/api/conexoes")["whatsapp"]["estado"] == "parado")

print("\n%d de %d verificacoes passaram" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
