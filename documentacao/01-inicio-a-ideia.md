# 01. O início: a ideia

## Contexto antes do CRM

Você tinha duas frentes de prospecção, em empresas diferentes:

- **Nexora (EUA):** prospecção fria por e-mail para imobiliárias (real estate) e escritórios de advocacia (law firm). Já existia um pipeline pronto: captação de leads com Apify, auditoria do site, geração do e-mail com IA, aprovação em lote num painel próprio (porta 4318), envio pelo Gmail (teto de 20 por dia, 10 por segmento) e uma landing page personalizada por lead (`?empresa=slug`). Dias antes, esse trabalho tinha ganho: e-mails compactos que apontam a dor, domínios genéricos `nexora-realty.vercel.app` e `nexora-law-firm.vercel.app`, e 20 e-mails enviados.
- **Atlas (sua empresa, Brasil):** venda de landing pages e gestão de tráfego pago, prospectando por WhatsApp. Já existiam roteiros de primeira mensagem, quebra de objeções, follow-ups, mensagens para leads específicos (locadoras de equipamentos e outros contatos) e um squad `atlas-email` ainda sem painel.

O trabalho estava espalhado em scripts, um painel só para a Nexora e conversas soltas.

## O gatilho

Você me mandou um link do Notion com um guia de instalação do **DeskcommCRM**, um CRM de código aberto centrado em WhatsApp com agentes de IA. Perguntou para que serve e se dava para encaixar no projeto de disparo de e-mails.

Conclusão da análise do código dele (leitura parcial, sem executar o app):

| Você queria | O Deskcomm tem? |
|---|---|
| Captação de leads | Sim, Google Maps via Apify, só Brasil, até 100 por busca (Apify é pago por saldo) |
| Follow-up | Sim para conversas; a própria documentação diz que não há sequência de insistência para quem nunca respondeu |
| Atualizar status de quem respondeu ou recusou | Sim (agente move etapa, detecta opt-out, sentimento, Radar) |
| Tradução das mensagens | Não, só traduz a interface (PT, EN, ES) |
| E-mail de prospecção | Não, o e-mail dele é só transacional (login, convites); as campanhas são de WhatsApp |

## A ideia que nasceu

Não instalar o Deskcomm. **Construir um CRM próprio, gratuito e local**, com o design e as funções que você gostou nele, e acrescentar o que ele não tem:

- Dois "modelos" novos dentro dele: disparo de mensagens (WhatsApp) e disparo de e-mails, **para Atlas e para Nexora**.
- Duas fontes de captação por empresa: e-mail e WhatsApp (ficam quatro funis com o mesmo modelo).
- Aproveitar tudo o que o Nexora já tinha (não refazer).

## Seus pedidos ao longo da conversa (em ordem)

1. Reproduzir uma tela do Deskcomm para você ver de perto.
2. Reabrir o kanban dos disparos de e-mail da Nexora.
3. Duas telas, uma para Nexora e uma para Atlas.
4. Ser o mais automatizado possível: captação, follow-up, atualizar quem respondeu, negou ou está pendente, tradução funcional para a Nexora.
5. Análise contínua dos scripts de mensagem, aprofundando conforme as respostas dos clientes.
6. Corrigir as mensagens genéricas: a dor precisa fazer o cliente ver que está perdendo dinheiro, com análise profunda em todos os critérios.
7. O follow-up deve avisar quantos dias depois enviar e qual mensagem, sem você marcar nada.
8. Sistema financeiro, e saber se ele detecta pagamento sozinho.
9. Funis iguais para as duas empresas, movendo o card pelo conteúdo da mensagem.
10. Acesso ao seu WhatsApp para detectar tudo sozinho.
11. Referências visuais: Fluxa, LYA, Behance "Rectio", Dribbble.
12. Uma tela de Gmail idêntica à original, mas melhorada.
13. Esta documentação.

## Regras e preferências que você deixou

- Tudo gratuito, rodando na sua máquina.
- Respostas curtas e diretas, em português.
- Copy da Atlas: sem travessões ("-", "—", "–"), "me chamo Enos" (nunca "aqui é o Enos"), nunca prometer prévia que não existe.
- Copy da Nexora: em inglês, curta, aponta a dor, a causa e por que prejudica; o link é um exemplo ilustrativo ajustável.
- Nunca inventar prova, número ou percentual de perda.
- Aprovação manual do primeiro e-mail da Nexora continua (regra original do projeto).
