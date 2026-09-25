"""Monta crm/demo/captacao-de-leads-demo com a interface do CRM + API falsa (dados ficticios) para publicar na Vercel.

Uso: py demo/montar.py   (depois: cd demo/captacao-de-leads-demo e npx vercel --prod --yes)
"""
import os
import shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
CRM = os.path.dirname(AQUI)
DIST = os.path.join(AQUI, "captacao-de-leads-demo")

shutil.rmtree(DIST, ignore_errors=True)
os.makedirs(os.path.join(DIST, "js"))
os.makedirs(os.path.join(DIST, "css"))
for f in sorted(os.listdir(os.path.join(CRM, "js"))):
    shutil.copy(os.path.join(CRM, "js", f), os.path.join(DIST, "js", f))
shutil.copy(os.path.join(CRM, "css", "app.css"), os.path.join(DIST, "css", "app.css"))
shutil.copy(os.path.join(AQUI, "mock-api.js"), os.path.join(DIST, "js", "mock-api.js"))

with open(os.path.join(CRM, "index.html"), encoding="utf-8") as fh:
    html = fh.read()
html = html.replace("<title>Captação de Leads</title>", "<title>Captação de Leads (demonstração)</title>")
html = html.replace('<script src="/js/core.js"></script>', '<script src="/js/mock-api.js"></script>\n<script src="/js/core.js"></script>')
faixa = ('<div style="position:fixed;top:0;left:0;right:0;z-index:90;background:#f0b34a;color:#3a2a00;text-align:center;padding:5px;font:12.5px system-ui">'
         "Demonstração com dados fictícios. Nada aqui é real nem é salvo.</div>"
         "<style>.app{padding-top:28px}.side{padding-top:34px}@media(max-width:820px){.wrap{padding-top:28px}}</style>")
html = html.replace("</body>", faixa + "\n</body>")
with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(html)
print("pronto em", DIST)
