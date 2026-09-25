"""Processo falso do observador para testar o gerenciador (WAManager): cria um filho e fica vivo, ou morre."""
import subprocess
import sys
import time

modo = sys.argv[1] if len(sys.argv) > 1 else "vivo"
if modo == "morre":
    print("Error: The browser is already running for X. Use a different `userDataDir`", flush=True)
    sys.exit(1)
filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])   # simula o Chrome filho
print("filho", filho.pid, flush=True)
time.sleep(600)
