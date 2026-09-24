"""Reautoriza o Gmail com permissao extra (gmail.modify) para excluir, arquivar e marcar como lida dentro do CRM.

Uso:
  cd crm
  py gmail_upgrade_auth.py nexora     (ou atlas)
Faca login com a conta correta. O token antigo e substituido; envio e leitura continuam funcionando.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEXORA_DIR = os.path.join(os.path.dirname(HERE), "_opensquad", "_memory", "nexora")
sys.path.insert(0, os.path.join(NEXORA_DIR, "scripts"))
sys.path.insert(0, NEXORA_DIR)

import token_store  # noqa: E402

conta = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
if conta not in ("nexora", "atlas"):
    sys.exit("Uso: py gmail_upgrade_auth.py nexora|atlas")
if conta == "atlas":
    os.makedirs(os.path.join(HERE, "atlas_gmail"), exist_ok=True)
    token_store.TOKEN_PATH = os.path.join(HERE, "atlas_gmail", "token.json")

import gmail_auth  # noqa: E402

gmail_auth.SCOPES += " https://www.googleapis.com/auth/gmail.modify"

if __name__ == "__main__":
    gmail_auth.main()
