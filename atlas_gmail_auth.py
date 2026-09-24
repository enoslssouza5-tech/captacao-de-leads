"""Autoriza a conta Gmail da Atlas (mesmo cliente OAuth do Google Cloud usado pela Nexora).

Uso (quando o Gmail da Atlas existir):
  cd crm
  py atlas_gmail_auth.py
Faca login com o Gmail da Atlas no navegador que abrir. O token fica em crm/atlas_gmail/token.json.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEXORA_DIR = os.path.join(os.path.dirname(HERE), "_opensquad", "_memory", "nexora")
sys.path.insert(0, os.path.join(NEXORA_DIR, "scripts"))
sys.path.insert(0, NEXORA_DIR)

import token_store  # noqa: E402

os.makedirs(os.path.join(HERE, "atlas_gmail"), exist_ok=True)
token_store.TOKEN_PATH = os.path.join(HERE, "atlas_gmail", "token.json")

import gmail_auth  # noqa: E402

if __name__ == "__main__":
    gmail_auth.main()
