# 03. O que foi criado

Tamanho aproximado: 2.300 linhas de código na pasta `crm/`.

## Arquivos

| Arquivo | Função |
|---|---|
| `server.py` | Servidor HTTP local (porta 4400), rotas da API, agendador em segundo plano (duas threads), gerenciador do processo do WhatsApp |
| `store.py` | Esquema do banco, funil, leitura dos leads da Nexora, follow-ups, respostas, radar, aprendizado, financeiro, estatísticas |
| `mail.py` | Gmail: ler respostas (caixa de entrada e spam), classificar, aplicar no banco da Nexora, enviar follow-ups de e-mail, enviar e-mails aprovados da Atlas |
| `gmail_ui.py` | Backend da tela estilo Gmail: pastas, conversas, leitura, envio, ações (excluir, arquivar, marcar lida, estrela) |
| `ia.py` | Tudo que usa IA local (`claude -p`): classificar resposta e traduzir, analisar dor, escrever follow-up, captar leads, revisão semanal |
| `pipeline.py` | Rotinas longas: captação, análise de dor, adaptação de follow-up, revisão semanal, inserção de leads captados sem duplicar |
| `app.js`, `gmail.js`, `index.html`, `styles.css`, `mail.css` | Interface (JavaScript puro, sem framework) |
| `wa-watcher/wa-watcher.js` | Observador do WhatsApp Web, somente leitura (Node, biblioteca whatsapp-web.js) |
| `atlas_gmail_auth.py` | Autoriza o Gmail da Atlas (quando existir) |
| `gmail_upgrade_auth.py` | Reautoriza com permissão extra (gmail.modify) para excluir, arquivar e marcar como lida |
| `iniciar-crm.bat` | Abre o CRM e liga o servidor |
| `crm.sqlite3` | Banco do CRM |

Alterações fora da pasta `crm/`, no Nexora:
- `_opensquad/_memory/nexora/scripts/bulk_rewrite_pronto.py`: prompt com a seleção de dor multicritério.
- `squads/nexora-email/pipeline/data/audit-checklist.md`: nova PARTE 7.
- `squads/nexora-email/pipeline/steps/step-03-geracao.md`: seção de seleção de dor.

## Telas (menu lateral, por empresa)

| Tela | O que faz |
|---|---|
| Hoje | Um lead por vez com a mensagem pronta; abas Novos contatos, Acompanhamentos, Respostas; saúde comercial e ritmo do dia; "Abrir no WhatsApp"; aprovar e enviar (e-mail Atlas) |
| Caixa de e-mail | Estilo Gmail: pastas, busca, conversas, leitura, responder, escrever, ligação com o lead |
| Captação | Tabela com avaliações, sinais, oportunidade 0 a 100 e status, filtros, "Captar leads", explicação de como ler |
| Radar | Responderam e estão sem retorno seu (mais de 24 horas), esfriando (sequência acabou sem resposta), e-mails devolvidos |
| Funil de e-mail / de WhatsApp | Kanban de 7 etapas; arrastar card muda a etapa (exceto e-mail da Nexora, que é só leitura) |
| Painel | KPIs, bloco "Atenção agora", funil geral em barras |
| Aprendizado | Taxa de resposta por canal, tipo de dor e hora de envio; propostas de ajuste da IA para você aprovar; biblioteca de objeções |
| Financeiro | Recebido no mês, a receber, meta, lançamentos, serviços e preços; vincular a um lead move para Fechado |
| Modelos e follow-ups | Textos padrão dos três follow-ups |
| Conexões | WhatsApp (QR, conectar, desconectar), Gmail das duas contas, chaves de automação, captação diária da Atlas, tarefas automáticas recentes |
| Janela do lead | Dor, critérios com impacto, mensagem, respostas com tradução e resumo, follow-ups |

Também: tema escuro e claro, cor por empresa (Atlas laranja, Nexora verde-água), notificação do navegador quando chega resposta (atualização a cada 15 segundos).

## Dados (tabelas em `crm.sqlite3`)

`leads`, `tarefas` (follow-ups), `respostas`, `bloqueios`, `modelos`, `servicos`, `pagamentos`, `metas`, `envios`, `propostas`, `config`, `jobs`, `gmail_vistos`.

Os 108 leads de e-mail da Nexora **não** são copiados: são lidos do banco antigo e traduzidos para as 7 etapas.

## Automações (rodam sozinhas com o servidor ligado)

Thread de leitura (a cada 45 segundos):
- Lê o Gmail a cada 5 minutos (caixa de entrada e spam) para Nexora e, quando existir, Atlas.
- Cruza remetente com lead, classifica a resposta com IA (interessado, dúvida, quer conversar, pendente, recusou, resposta automática, e-mail devolvido), traduz para português e resume.
- Move o card, cancela os follow-ups pendentes, bloqueia contato em caso de recusa ou devolução, e na Nexora grava a classificação e a supressão no banco original.
- Classifica respostas que ficaram sem classificação.
- Reescreve com IA um follow-up por vez, adaptado à dor e ao histórico.
- Analisa a dor de um lead novo por vez (pesquisa na web), escreve a mensagem e coloca o lead em "Pronto".
- Captação diária da Atlas, se você ligar (uma cidade por dia, rodízio).

Thread de envio (a cada 10 minutos):
- Envia follow-ups de e-mail vencidos (Nexora e Atlas), dentro do teto de 20 por dia, com 45 segundos entre envios e rodapé de descadastro. **Só se a chave estiver ligada.**
- Envia e-mails da Atlas que você aprovou (quando o Gmail da Atlas existir).

Eventos do WhatsApp (quando o observador estiver conectado):
- Você envia a mensagem: o lead vai para Contatado e os três follow-ups são criados; se já era um follow-up vencido, ele é marcado como feito.
- O lead responde: a resposta é registrada, classificada e o card se move.
- Números que não são leads são ignorados e nada é guardado.

## Regras de segurança embutidas

- O observador do WhatsApp tem as funções de envio bloqueadas no código.
- Follow-up de e-mail: só para lead em "Contatado", nunca para suprimido, nunca acima do teto diário, para ao chegar resposta.
- Na Nexora, envio real exige o endereço postal verificado (regra do projeto original).
- Contato que recusou, pediu para sair ou devolveu e-mail entra em bloqueio e não volta a ser captado.
- Lead duplicado (telefone, e-mail ou nome) é barrado.
