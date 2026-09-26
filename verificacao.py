"""Verificacao de contatos captados. WhatsApp: celular valido. E-mail: mesma ideia, sem servico pago.
Nunca descarta um lead so porque a internet falhou: sem resposta de DNS o e-mail e aceito e marcado como nao verificado."""
import os
import re
import socket
import subprocess

EMAIL_OK = re.compile(r"^[a-z0-9._%+\-]+@([a-z0-9\-]+\.)+[a-z]{2,}$")
DOMINIOS_FALSOS = {"example.com", "example.org", "test.com", "email.com", "seudominio.com", "dominio.com", "sentry.io", "wixpress.com", "domain.com"}
PREFIXOS_SEM_RESPOSTA = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster", "abuse", "bounce")


def verificar_email(email, dns=None):
    """Devolve (ok, motivo). Checa formato, dominio de exemplo, endereco que nao recebe resposta e se o dominio existe (MX ou A)."""
    if dns is None:
        dns = os.environ.get("CRM_VERIFICAR_DNS", "1") != "0"
    e = (email or "").strip().lower()
    if not e:
        return False, "sem e-mail"
    if not EMAIL_OK.match(e):
        return False, "e-mail com formato invalido"
    local, dominio = e.split("@", 1)
    if dominio in DOMINIOS_FALSOS:
        return False, "e-mail de exemplo (dominio falso)"
    if any(local.startswith(p) for p in PREFIXOS_SEM_RESPOSTA):
        return False, "endereco que nao recebe resposta (%s)" % local
    if dns:
        existe = dominio_existe(dominio)
        if existe is False:
            return False, "o dominio %s nao existe" % dominio
    return True, ""


def dominio_existe(dominio):
    """True/False, ou None quando nao foi possivel checar (rede fora). Tenta MX e depois A."""
    try:
        p = subprocess.run(["nslookup", "-type=MX", dominio], capture_output=True, text=True, timeout=8)
        saida = (p.stdout or "").lower()
        if "mail exchanger" in saida or "mx preference" in saida:
            return True
        if "non-existent domain" in saida or "nxdomain" in saida:
            return False
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        socket.getaddrinfo(dominio, None)
        return True
    except socket.gaierror as ex:
        return False if getattr(ex, "errno", None) in (11001, -2, -5) else None
