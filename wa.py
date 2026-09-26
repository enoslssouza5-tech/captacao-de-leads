"""Gerenciador do observador do WhatsApp (processo Node, somente leitura).

Resolve os defeitos encontrados na auditoria:
- processo orfao (Node + Chrome) segurando o perfil da sessao apos reiniciar o servidor;
- servidor nao percebia que o processo morreu (estado "iniciando" para sempre);
- "desconectar" matava so o Node e deixava o Chrome vivo;
- QR expirado sem aviso e sem renovacao.
"""
import logging
import os
import subprocess
import sys
import threading
import time

QR_VALIDADE_S = 75          # o WhatsApp troca o QR a cada ~20s; sem troca por tanto tempo = travado
SEM_SINAL_S = 60            # o observador manda batimento a cada 10s
MAX_RENOVACOES_QR = 4       # depois disso espera o usuario pedir novo QR
ESPERAS_REINICIO = (2, 5, 15, 30, 60)


def _agora():
    return time.time()


def _matar_arvore(pid):
    if not pid:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=20)
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except OSError:
            pass


def pids_orfaos(marcadores):
    """PIDs de processos (node/chrome) cuja linha de comando contem algum marcador (caminho da sessao ou wa-watcher)."""
    if sys.platform != "win32":
        return []
    filtro = " -or ".join("$_.CommandLine -like '*%s*'" % m.replace("'", "''") for m in marcadores)
    ps = "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne %d -and (%s) } | ForEach-Object { $_.ProcessId }" % (os.getpid(), filtro)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(x) for x in out.split() if x.isdigit()]


class WAManager:
    def __init__(self, cmd, cwd, log_path, flag_path, marcadores, ambiente=None):
        self.cmd, self.cwd, self.log_path, self.flag_path = cmd, cwd, log_path, flag_path
        self.marcadores = marcadores
        self.ambiente = ambiente or {}
        self.lock = threading.RLock()
        self.proc = None
        self.querido = False
        self.estado, self.qr, self.motivo = "parado", None, None
        self.qr_em = 0.0
        self.sinal_em = 0.0
        self.tentativas = 0
        self.renovacoes_qr = 0
        self.proxima_tentativa = 0.0
        self.atividade = []     # o que o observador viu de mensagens (sem texto)
        self.eventos = []       # historico curto de decisoes do gerenciador
        self._thread = None

    # ---------- utilitarios ----------
    def _log(self, msg):
        self.eventos.append("%s %s" % (time.strftime("%H:%M:%S"), msg))
        del self.eventos[:-30]

    def atividade_msg(self, texto):
        """Registro do que o observador viu (enviou/recebeu/ignorou), so com o final do numero. Ajuda a achar por que algo nao foi detectado."""
        with self.lock:
            self.atividade.append("%s %s" % (time.strftime("%H:%M:%S"), texto))
            del self.atividade[:-40]
        logging.getLogger("crm").info("whatsapp: %s", texto)

    def _ultimas_linhas_log(self, n=3):
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                linhas = [l.strip() for l in f.readlines() if l.strip()]
            erros = [l for l in linhas if "Error" in l or "erro" in l.lower()]
            return " | ".join((erros or linhas)[-n:])[:300]
        except OSError:
            return ""

    def ja_vinculado(self):
        return os.path.exists(self.flag_path)

    def limpar_orfaos(self):
        pids = pids_orfaos(self.marcadores)
        for pid in pids:
            _matar_arvore(pid)
        if pids:
            self._log("processos orfaos encerrados: %d" % len(pids))
        return len(pids)

    # ---------- ciclo de vida ----------
    def iniciar(self, manual=True):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return
            self.limpar_orfaos()
            if manual:
                self.tentativas = 0
                self.renovacoes_qr = 0
            self.querido = True
            self.qr, self.qr_em = None, 0.0
            if manual:
                self.motivo = None
            self.estado = "iniciando" if manual else "reiniciando"   # no reinicio automatico o ultimo erro continua visivel
            self.sinal_em = _agora()
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            log = open(self.log_path, "a", encoding="utf-8")
            env = dict(os.environ, **self.ambiente)
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            self.proc = subprocess.Popen(self.cmd, cwd=self.cwd, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags)
            self._log("observador iniciado (pid %s)" % self.proc.pid)

    def parar(self, definitivo=True):
        with self.lock:
            if definitivo:
                self.querido = False
            if self.proc:
                _matar_arvore(self.proc.pid)
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            self.proc = None
            self.limpar_orfaos()
            self.estado, self.qr = "parado", None
            self._log("observador parado")

    def novo_qr(self):
        """Reinicia o observador para gerar um QR novo (limpa o contador de renovacoes)."""
        self.parar(definitivo=False)
        self.iniciar(manual=True)

    # ---------- entrada de dados vindos do Node ----------
    def receber_status(self, d):
        with self.lock:
            self.sinal_em = _agora()
            estado = d.get("estado", self.estado)
            if estado == "batimento":      # so prova que o processo esta vivo; nao altera estado nem QR
                return
            if estado == "qr" and d.get("qr"):
                if d["qr"] != self.qr:
                    self.qr_em = _agora()
                self.qr = d["qr"]
            elif estado != "qr":
                self.qr = None
            self.estado = estado
            self.motivo = d.get("motivo")
            if estado == "conectado":
                self.tentativas = 0
                self.renovacoes_qr = 0
                os.makedirs(os.path.dirname(self.flag_path), exist_ok=True)
                open(self.flag_path, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))

    # ---------- supervisao (chamada a cada poucos segundos) ----------
    def verificar(self):
        with self.lock:
            if not self.querido:
                return
            vivo = self.proc is not None and self.proc.poll() is None
            if not vivo:
                if _agora() < self.proxima_tentativa:
                    return
                if self.tentativas >= len(ESPERAS_REINICIO):
                    self.estado = "erro"
                    self.motivo = "O observador caiu varias vezes. " + self._ultimas_linhas_log()
                    self.querido = False
                    self._log("desistiu apos %d tentativas" % self.tentativas)
                    return
                espera = ESPERAS_REINICIO[self.tentativas]
                self.motivo = "Observador parou (%s). Reiniciando." % (self._ultimas_linhas_log() or "sem detalhe")
                self.estado = "erro"
                self.tentativas += 1
                self.proxima_tentativa = _agora() + espera
                self._log("processo morto; reinicio em %ss (tentativa %d)" % (espera, self.tentativas))
                self.iniciar(manual=False)
                return
            if self.estado == "qr" and self.qr_em and _agora() - self.qr_em > QR_VALIDADE_S:
                if self.renovacoes_qr >= MAX_RENOVACOES_QR:
                    self.estado = "qr_expirado"
                    self.qr = None
                    self.motivo = "QR expirou. Clique em Gerar novo QR."
                    _matar_arvore(self.proc.pid)
                    self.proc = None
                    self.querido = False
                    self._log("QR expirado, aguardando o usuario")
                    return
                self.renovacoes_qr += 1
                self._log("QR parado ha mais de %ss; reiniciando (%d)" % (QR_VALIDADE_S, self.renovacoes_qr))
                _matar_arvore(self.proc.pid)
                self.proc = None
                self.limpar_orfaos()
                self.iniciar(manual=False)
                return
            if _agora() - self.sinal_em > SEM_SINAL_S:
                self._log("sem batimento ha mais de %ss; reiniciando" % SEM_SINAL_S)
                self.parar(definitivo=False)
                self.iniciar(manual=False)

    def _loop(self):
        while True:
            try:
                self.verificar()
            except Exception as e:  # o supervisor nunca pode morrer
                self._log("erro no supervisor: %s" % e)
            time.sleep(2)

    def iniciar_supervisor(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="wa-supervisor")
        self._thread.start()

    def publico(self):
        with self.lock:
            return {"estado": self.estado, "qr": self.qr, "motivo": self.motivo, "qr_idade_s": int(_agora() - self.qr_em) if self.qr_em else None,
                    "tentativas": self.tentativas, "pid": self.proc.pid if self.proc and self.proc.poll() is None else None,
                    "vinculado": self.ja_vinculado(), "eventos": self.eventos[-8:], "atividade": self.atividade[-12:]}
