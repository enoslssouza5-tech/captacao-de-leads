# 06. Contexto para outra IA (pode colar tudo isto)

Use este arquivo como base do seu prompt. Ele descreve o projeto, as regras, o estado atual e as perguntas abertas. Não contém senhas nem tokens.

---

## Papel e objetivo

Você vai ajudar a evoluir um CRM local e gratuito que unifica a prospecção de duas empresas do mesmo dono:

- **Atlas** (Brasil): vende landing pages premium e gestão de tráfego pago. Prospecta por WhatsApp e e-mail, em português do Brasil. Nicho atual: locação de equipamentos para construção civil.
- **Nexora** (EUA): prospecção fria por e-mail, em inglês, para imobiliárias (real estate) e escritórios de advocacia (law firm). Oferta: página de captação por US$ 600 em 15 dias, com landing page de exemplo personalizada por lead.

Meta: máximo de automação, custo zero, com o humano só onde há risco (aprovar o primeiro e-mail, enviar WhatsApp, responder quem se interessou).

## Regras que não podem ser quebradas

1. **Nunca enviar WhatsApp automaticamente.** O CRM só observa (somente leitura). O dono clica em "Abrir no WhatsApp" e envia. Limite de 10 a 15 contatos novos por dia.
2. Tudo gratuito e local: Python (só biblioteca padrão), SQLite, JavaScript puro, IA via `claude -p` local. Não propor VPS, Supabase, APIs pagas ou chaves de IA pagas.
3. Nunca inventar fato, número, prova, avaliação ou percentual de perda em mensagens.
4. Copy da Atlas: português do Brasil, sem travessões ("-", "—", "–") como pontuação, "me chamo Enos" (nunca "aqui é o Enos"), curta, humana, sem prometer prévia que não existe.
5. Copy da Nexora: inglês, curta, estrutura dor, causa, por que prejudica; o link da landing é "um exemplo ilustrativo, ajustável às preferências da empresa".
6. Respeitar limites de e-mail: teto de 20 por dia por conta, 45 segundos entre envios, rodapé de descadastro, bloqueio imediato de quem recusa ou devolve, endereço postal verificado na Nexora.
7. A aprovação manual do primeiro e-mail da Nexora é regra original do projeto.
8. Respostas ao dono: curtas, diretas, em português, sem emojis.

## Ambiente

- Windows 11, usando Git Bash e PowerShell. Cuidados: o Python do Windows não lê caminhos `/tmp` nem `/c/...` (usar `C:/...`); comandos com textos longos em heredoc podem falhar, preferir criar arquivos.
- Pasta do projeto: `C:\Users\enosl\Desktop\Projetos antigravity\Agentes de Marketing`.
- Rodar o CRM: `crm/iniciar-crm.bat` ou `py crm/server.py` (http://127.0.0.1:4400).

## Arquitetura (resumo)

- `crm/server.py`: HTTP e agendador (2 threads: leitura e envio).
- `crm/store.py`: banco, funil, follow-ups, radar, aprendizado, financeiro.
- `crm/mail.py`: leitura e envio pelo Gmail, cruzamento com leads, classificação.
- `crm/gmail_ui.py` e `crm/gmail.js`: tela estilo Gmail.
- `crm/ia.py` e `crm/pipeline.py`: IA (classificar, analisar dor, follow-up, captar, revisão semanal).
- `crm/wa-watcher/wa-watcher.js`: observador do WhatsApp (whatsapp-web.js), envia eventos ao CRM por HTTP.
- Interface: `crm/index.html`, `app.js`, `gmail.js`, `styles.css`, `mail.css`.
- Dados: `crm/crm.sqlite3` (CRM) e `_opensquad/_memory/nexora/db/nexora.sqlite3` (leads e e-mails da Nexora, lidos e atualizados nas respostas).
- Reaproveitado da Nexora: `gmail_api.py`, `token_store.py`, `db.py`, `env_loader.py`, `send_gmail.py` (em `_opensquad/_memory/nexora/scripts/`).
- Funil único: Novo, Pronto, Contatado, Respondeu, Negociando, Fechado, Perdido.
- Classificação de resposta: interessado, dúvida, quer conversar (reuniao), pendente, recusou, resposta automática, e-mail devolvido. A classificação move o card e cancela o follow-up.
- Follow-ups: D+3, D+7, D+14, texto padrão por empresa reescrito por IA perto do vencimento.

### Rotas principais da API (JSON)
GET: `/api/hoje`, `/api/board?conta=&canal=`, `/api/captacao`, `/api/radar`, `/api/aprendizado`, `/api/financeiro`, `/api/stats`, `/api/modelos`, `/api/lead?ref=`, `/api/conexoes`, `/api/ping`, `/api/gmail/pastas|conversas|conversa`.
POST: `/api/leads`, `/api/leads/<id>/(sent|descartar|sem_whatsapp|aprovar|analisar|resposta|editar)`, `/api/tarefas/<id>/feita`, `/api/wa/(event|status|start|stop)`, `/api/gmail/(sync|send|acao)`, `/api/captar`, `/api/aprendizado/revisar`, `/api/propostas/<id>/(aprovar|rejeitar)`, `/api/config`, `/api/pagamentos`, `/api/servicos`, `/api/meta`, `/api/modelos`, `/api/traduzir`.
Todas usam o parâmetro `conta` = `atlas` ou `nexora`.

## Estado atual (honesto)

Funcionando e testado com dados reais: leitura de Gmail (caixa de entrada e spam) da Nexora, classificação por IA, bloqueio de descadastro e e-mail devolvido, captação com Apify, análise de dor com web, adaptação de follow-up, todas as telas, tela de Gmail.

Testado só por simulação: o ciclo do WhatsApp (envio detectado, resposta classificada).

Nunca executado: observador real do WhatsApp, envio real de follow-up por e-mail, resposta e "Escrever" na tela de Gmail, excluir/arquivar/marcar lida (falta a permissão gmail.modify), qualquer coisa do Gmail da Atlas (a conta ainda não existe), revisão semanal, captação diária automática, notificações do navegador.

Pendências conhecidas: ver `05-o-que-falta-e-o-fim.md`.

## O que peço a você (edite conforme sua necessidade)

Escolha uma ou mais frentes. Para cada uma, me devolva: (a) o que você mudaria e por quê, (b) o plano em passos pequenos, (c) o código ou os prompts, respeitando as regras acima.

1. **Design:** refazer a interface seguindo a referência (anexar print do Behance "Rectio") e as telas Fluxa e LYA, com versão para celular. Manter JavaScript puro e as mesmas rotas de API.
2. **Análise de dor:** melhorar o prompt para que a abertura sempre ligue reputação a perda de receita, com um teste automático de qualidade (a primeira frase faz o dono sentir que perde cliente?), para Atlas (PT) e Nexora (EN).
3. **Mensagens e follow-ups:** roteiros por objeção, por tipo de dor e por canal, com variações para teste A/B.
4. **Inbox de conversa de WhatsApp** (visualização das conversas dos leads dentro do CRM, sem enviar).
5. **Financeiro:** detecção automática de pagamento (Mercado Pago, Asaas ou leitura de e-mail do banco) e documentos.
6. **Robustez:** testes automatizados dos fluxos críticos, backup, inicialização automática no Windows, fila de tarefas mais segura, correção manual de classificação.
7. **Unificar o envio da Nexora dentro do CRM** e aposentar o painel antigo (porta 4318), preservando a aprovação manual e os limites.

## Perguntas em aberto para decidir

- Qual referência visual exata seguir (o Behance não pôde ser aberto pela IA anterior)?
- O follow-up automático de e-mail deve ser ligado? Com que critérios de segurança?
- A Atlas terá domínio próprio para o e-mail (SPF e DKIM) ou usará Gmail simples?
- Como será a captação da Atlas além do Google Maps (o e-mail público de empresas brasileiras é raro)?
- Quanto de cota do Apify gastar por dia?
- Manter a aprovação manual da Nexora ou aprovar por regra (por exemplo, pontuação mínima)?
- O dono quer um inbox de WhatsApp dentro do CRM?
