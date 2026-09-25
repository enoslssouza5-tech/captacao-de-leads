@echo off
cd /d "%~dp0"
start "" http://127.0.0.1:4400
:inicio
py server.py
if errorlevel 2 exit /b 0
echo O CRM parou. Reiniciando em 5 segundos... (feche esta janela para sair)
timeout /t 5 /nobreak >nul
goto inicio
