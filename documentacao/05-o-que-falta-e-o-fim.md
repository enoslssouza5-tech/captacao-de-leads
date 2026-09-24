# 05. O que falta e o fim do projeto

Você disse que sente que ainda falta muita coisa. Concordo. Este arquivo lista tudo o que enxergo, do mais urgente ao mais opcional, e descreve como seria o CRM "pronto".

## 1. Ações suas que destravam o que já existe

1. Conectar o WhatsApp (Conexões, escanear o QR) e observar se a detecção de envio e resposta funciona de verdade.
2. Autorizar permissão extra do Gmail: `py crm/gmail_upgrade_auth.py nexora` (excluir, arquivar, marcar lida).
3. Criar o Gmail da Atlas e autorizar: `py crm/atlas_gmail_auth.py`.
4. Decidir quando ligar o follow-up automático de e-mail (Conexões).
5. Definir cidades e categoria da captação diária da Atlas.
6. Enviar a referência de design (print do Behance "Rectio" e o que mais quiser).

## 2. Lacunas de produto

### Visual e experiência
- Design ainda genérico; não segue a referência do Rectio (não foi vista).
- Sem versão pensada para celular.
- Sem ícones, gráficos ao longo do tempo, animações, estados vazios cuidados.
- Sem atalhos de teclado (o Ctrl+Enter do primeiro protótipo saiu).
- Sem tela de configurações gerais.

### Funil e leads
- Cards da Nexora por e-mail são somente leitura (não dá arrastar nem criar lead da Nexora pelo CRM).
- Sem edição completa do lead, notas, etiquetas, histórico de atividades (linha do tempo).
- Sem ações em lote, mesclar duplicados, importar ou exportar (CSV).
- Sem agenda, tarefas manuais e lembretes (só os follow-ups automáticos).
- Sem tela de conversa de WhatsApp (o CRM só observa; o Deskcomm tem um inbox de chat completo).
- A Nexora ainda depende do painel antigo (porta 4318) para aprovar e enviar o primeiro e-mail: são dois lugares.

### Inteligência
- Análise de dor da Nexora: os 56 e-mails "prontos" continuam no formato antigo. É preciso rodar a reescrita.
- Sem teste A/B nem comparação entre versões de texto.
- Aprendizado depende de volume: hoje quase não há dados.
- Revisão semanal nunca foi executada (não há agendamento automático semanal).
- Follow-up de e-mail sai como novo e-mail com "Re:", não dentro da mesma conversa (falta guardar o identificador da mensagem original).
- Classificação por IA pode errar; não há tela para você corrigir e reclassificar.
- Tradução só existe dentro da classificação de respostas; não há botão de traduzir e-mail antes de enviar.

### Financeiro
- Baixa de pagamento manual. Detecção automática exigiria webhook (Mercado Pago, Asaas, Stripe) ou ler e-mails do banco.
- Sem propostas, contratos, recibos, recorrência, comissões.

### Infraestrutura
- O CRM só funciona com o computador ligado e o servidor aberto; não sobe sozinho com o Windows.
- Sem login (protegido só por escutar em 127.0.0.1); inadequado se algum dia for acessado de fora.
- Sem backup do `crm.sqlite3`.
- Sem testes automatizados; sem log de erros organizado (existe `crm/crm.log` simples).
- SQLite acessado por várias threads (funciona, mas sem fila de tarefas robusta; uma chamada de IA travada segura o ciclo).
- Captação depende da cota gratuita do Apify (US$ 5 por mês para as duas empresas).
- Dependência de `claude -p` instalado e logado; se ficar sem acesso, classificação e análise param (as respostas ficam "a classificar").

### Riscos
- **WhatsApp Web não oficial:** risco pequeno de restrição do número. Mitigação: só leitura, limite de 15 por dia, envio manual.
- **E-mail frio:** reputação do domínio e do Gmail. Mitigação: teto de 20 por dia, intervalo de 45 segundos, descadastro, bloqueio imediato, subida gradual na Atlas.
- **LGPD e CAN-SPAM:** rodapé de descadastro existe; a Nexora exige endereço postal verificado; a base legal para prospecção fria no Brasil precisa da sua avaliação.
- **Mensagem gerada por IA:** pode conter erro factual. Mitigação: regras de nunca inventar dado, aprovação humana antes do envio.

## 3. Comparação com o Deskcomm (o que ele tem e o CRM ainda não)

Inbox de conversas de WhatsApp com resposta assistida por IA, roteadores entre agentes, base de conhecimento (RAG), memória do agente, skills, agenda com Google Calendar, respostas rápidas, campanhas com pool de números, equipe e permissões, auditoria, LGPD (exportar e apagar dados), orçamento de IA, Meta Ads, integração com lojas. Vários não fazem sentido para o seu caso; o principal que falta é o **inbox de chat de WhatsApp**.

## 4. O fim: como seria o CRM pronto

Você abre o CRM de manhã e ele já fez tudo o que não precisa de você:

1. Captou leads das duas empresas e analisou a dor de cada um, com evidência real.
2. Escreveu as abordagens (e-mail e WhatsApp) e os follow-ups adaptados.
3. A Nexora e a Atlas enviaram e-mails aprovados e follow-ups dentro dos limites, sem estourar teto e sem contatar quem recusou.
4. Leu Gmail e WhatsApp, classificou, traduziu e moveu os cards.
5. A tela "Hoje" mostra só o que depende de você: enviar os WhatsApp do dia (um clique cada), responder quem se interessou e aprovar lotes.
6. Financeiro registra o que entrou e quanto falta para a meta.
7. Toda semana ele mostra o que funcionou (dor, hora, canal) e propõe ajustes nos roteiros, que você aprova.

### Critérios objetivos de "pronto"
- WhatsApp conectado e detectando envio e resposta por pelo menos uma semana sem falha.
- Gmail das duas empresas lendo e enviando, com as ações liberadas.
- Aprovação e envio da Nexora dentro do CRM (painel antigo aposentado).
- Reescrita dos e-mails da Nexora feita com a nova regra de dor e taxa de resposta acompanhada.
- Design aprovado por você segundo a referência.
- Sobe sozinho com o computador, com backup diário.
- Um conjunto mínimo de testes automatizados nos fluxos críticos (classificação, bloqueio, teto diário).
