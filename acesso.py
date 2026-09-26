"""Login para acesso externo (tunel). Acesso direto em 127.0.0.1 continua sem login.
Credencial em crm/acesso.json (fora do Git): usuario, sal, hash PBKDF2 e segredo da sessao. Nunca guarda a senha em texto."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

ARQ = os.environ.get("CRM_ACESSO", os.path.join(os.path.dirname(os.path.abspath(__file__)), "acesso.json"))
VALIDADE = 7 * 24 * 3600
MAX_FALHAS, BLOQUEIO = 5, 300
_falhas = {}
_trava = threading.Lock()
_ITER = 200_000


def _hash(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), _ITER).hex()


def definir(usuario, senha):
    sal = secrets.token_hex(16)
    with open(ARQ, "w", encoding="utf-8") as f:
        json.dump({"usuario": usuario, "sal": sal, "hash": _hash(senha, sal), "segredo": secrets.token_hex(32)}, f)


def _cfg():
    try:
        with open(ARQ, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def configurado():
    return _cfg() is not None


def bloqueado(ip):
    with _trava:
        n, ate = _falhas.get(ip, (0, 0))
        return n >= MAX_FALHAS and time.time() < ate


def verificar(ip, usuario, senha):
    """True/False. Apos 5 falhas seguidas do mesmo IP, bloqueia por 5 minutos."""
    c = _cfg()
    if not c or bloqueado(ip):
        return False
    ok_u = hmac.compare_digest(str(usuario or "").encode(), c["usuario"].encode())
    ok_s = hmac.compare_digest(_hash(str(senha or ""), c["sal"]), c["hash"])
    with _trava:
        if ok_u and ok_s:
            _falhas.pop(ip, None)
            return True
        n, ate = _falhas.get(ip, (0, 0))
        _falhas[ip] = (n + 1 if time.time() >= ate or n < MAX_FALHAS else 1, time.time() + BLOQUEIO)
    time.sleep(0.5)
    return False


def _assinar(c, exp):
    return hmac.new(c["segredo"].encode(), str(exp).encode(), hashlib.sha256).hexdigest()


def novo_token():
    c = _cfg()
    exp = int(time.time()) + VALIDADE
    return "%d.%s" % (exp, _assinar(c, exp))


def token_valido(token):
    c = _cfg()
    try:
        exp, ass = (token or "").split(".", 1)
        return bool(c) and int(exp) > time.time() and hmac.compare_digest(ass, _assinar(c, int(exp)))
    except ValueError:
        return False


PAGINA_LOGIN = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Entrar</title><style>
:root{color-scheme:dark light}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#14110f;color:#f3ede6;font:15px system-ui,sans-serif}
form{width:min(340px,86vw);display:grid;gap:14px}h1{font-size:22px;font-weight:600;margin:0 0 6px}
input{padding:12px 14px;border-radius:8px;border:1px solid #3a322b;background:#1d1815;color:inherit;font:inherit}
button{padding:12px;border:0;border-radius:8px;background:#ff7a1a;color:#1a1207;font:inherit;font-weight:600;cursor:pointer}
#e{color:#ff8a7a;min-height:1.2em;font-size:13px}</style></head><body>
<form id="f"><h1>Captação de Leads</h1><input name="u" placeholder="Login" autocomplete="username" required autofocus>
<input name="s" type="password" placeholder="Senha" autocomplete="current-password" required><div id="e"></div><button>Entrar</button></form>
<script>document.getElementById("f").onsubmit=async ev=>{ev.preventDefault();const f=ev.target,e=document.getElementById("e");e.textContent="";
const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({usuario:f.u.value,senha:f.s.value})});
if(r.ok)location.reload();else e.textContent=r.status===429?"Muitas tentativas. Aguarde alguns minutos.":"Login ou senha incorretos."}</script></body></html>"""
