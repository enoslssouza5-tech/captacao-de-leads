# 05. O que falta e o fim (atualizado em 2026-09-24)

## Acao humana necessaria
1. Escanear o QR do WhatsApp uma vez (Configuracoes, Conexoes).
2. Criar e autorizar o Gmail da Atlas: `py crm/atlas_gmail_auth.py`.
3. Opcional: `py crm/gmail_upgrade_auth.py <conta>` para excluir, arquivar e marcar como lido.
4. Opcional: `powershell -ExecutionPolicy Bypass -File crm/instalar-inicializacao.ps1` para subir com o Windows.
5. Ligar de proposito as chaves de follow-up automatico por e-mail (vem desligadas).

## Pendencias conhecidas
- 14 e-mails longos da Nexora (imobiliarias, mais de 1100 caracteres) e os 56 pendentes podem precisar ser reescritos com a nova regra de escolha de dor.
- O painel antigo da Nexora (porta 4318) ainda existe; aprovar, rejeitar e enviar ja funcionam no CRM com as mesmas protecoes.
- Series da Nexora sao marcadas como parciais (parte do historico vem do banco dela).

## Regras que nunca mudam
- O CRM nunca envia WhatsApp. Voce envia, ele observa.
- Nada de dado inventado. Sem evidencia, o grafico mostra "dados insuficientes".
- Este repositorio esta publico so temporariamente e sem dados reais. Torne-o privado quando terminar de usar com a outra IA.
