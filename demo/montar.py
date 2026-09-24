"""Monta crm/demo/captacao-de-leads-demo com a interface do CRM + API falsa (dados fictícios) para publicar na Vercel.

Uso: py demo/montar.py   (depois: cd demo/captacao-de-leads-demo e npx vercel --prod --yes)
"""
import os
import shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
CRM = os.path.dirname(AQUI)
DIST = os.path.join(AQUI, "captacao-de-leads-demo")

shutil.rmtree(DIST, ignore_errors=True)
os.makedirs(DIST)
for f in ("app.js", "gmail.js", "styles.css", "mail.css"):
    shutil.copy(os.path.join(CRM, f), DIST)
shutil.copy(os.path.join(AQUI, "mock-api.js"), DIST)

with open(os.path.join(CRM, "index.html"), encoding="utf-8") as fh:
    html = fh.read()
html = html.replace("<title>Nexora e Atlas CRM</title>", "<title>Captação de Leads (demonstração)</title>")
html = html.replace('<script src="/gmail.js"></script>', '<script src="/mock-api.js"></script>\n<script src="/gmail.js"></script>')
faixa = ('<div style="position:fixed;bottom:0;left:0;right:0;z-index:50;background:#f5b73b;color:#3a2a00;text-align:center;padding:6px;font:13px system-ui">'
         "Demonstração com dados fictícios. Nada aqui é real nem é salvo.</div>")
html = html.replace("</body>", faixa + "\n</body>")
with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(html)
print("dist pronto em", DIST)
