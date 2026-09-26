@echo off
REM Abre um link publico (Cloudflare Tunnel) para o CRM. O link https://....trycloudflare.com aparece abaixo e muda a cada vez.
REM O acesso por esse link exige login (crm\acesso.json). Feche esta janela para derrubar o link.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:4400
