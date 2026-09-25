"""Auditoria SOMENTE LEITURA dos e-mails 'pronto' da Nexora contra as regras de copy (regras.py).

Uso: py auditoria_nexora.py
Mede apenas o corpo do e-mail (sem o rodape de descadastro e endereco).
"""
import re
import sqlite3
import statistics

import regras
import store

RODAPE = re.compile(r"\n\s*Don't want future emails", re.I)


def corpo(txt):
    return RODAPE.split((txt or "").replace("{{LANDING_URL}}", "https://x.example"))[0].strip()


def main():
    conn = sqlite3.connect("file:%s?mode=ro" % store.NEXORA_DB.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, empresa, corpo_texto, review_count FROM leads WHERE status IN ('pronto','aprovado') ORDER BY id").fetchall()
    cont, ruins = {}, []
    for r in rows:
        texto = corpo(r["corpo_texto"])
        viol = regras.validar("nexora", "email", "primeiro", texto, None, link_landing="x.example" in texto)
        if viol:
            ruins.append((r["id"], r["empresa"], viol))
        for v in viol:
            chave = re.sub(r"\d+", "N", v)
            cont[chave] = cont.get(chave, 0) + 1
    tam = [len(corpo(r["corpo_texto"])) for r in rows]
    print("E-mails prontos/aprovados: %d | com alguma violacao: %d" % (len(rows), len(ruins)))
    if tam:
        print("Tamanho do corpo em caracteres (min/mediana/max): %d / %d / %d" % (min(tam), statistics.median(tam), max(tam)))
    for k, n in sorted(cont.items(), key=lambda kv: -kv[1]):
        print("  %3d  %s" % (n, k))
    return len(ruins), len(rows)


if __name__ == "__main__":
    main()
