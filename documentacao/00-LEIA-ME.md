# CRM Unificado Nexora e Atlas: documentação do projeto

Data desta documentação: 24/09/2026.

Esta pasta conta o projeto do começo ao fim, para você (e qualquer outra IA que for ajudar) entender o que foi pensado, o que foi construído, o que foi testado e o que ainda falta.

## Repositório no GitHub

https://github.com/enoslssouza5-tech/captacao-de-leads

- Nome do CRM: **Captação de Leads** (o GitHub não aceita acento nem espaço, então o repositório se chama `captacao-de-leads`).
- Visibilidade: **público**, para que qualquer pessoa ou IA consiga abrir o link. Antes de publicar, os nomes de empresas reais e contatos pessoais foram retirados dos documentos. Se quiser voltar a deixar privado, é só mudar nas configurações do repositório.
- Ficaram de fora, de propósito: o banco `crm.sqlite3` (dados reais de leads e respostas), a sessão do WhatsApp, tokens do Gmail, logs e `node_modules`.
- Este repositório contém só a pasta `crm/`. Para rodar completo, ele ainda depende da pasta `_opensquad/_memory/nexora/` (scripts e banco do Nexora) que fica no seu computador, no projeto "Agentes de Marketing".

## Demonstração online (dados fictícios)

https://captacao-de-leads-demo.vercel.app

- Mostra todas as telas do CRM (Atlas e Nexora) para qualquer pessoa ou IA abrir e navegar.
- Os dados são **fictícios** (empresas inventadas). Nada é real e nada é salvo; os botões só simulam.
- O CRM de verdade **não** está online: ele guarda seus leads reais e lê o seu Gmail, então só roda no seu computador (http://127.0.0.1:4400).
- Para atualizar a demonstração depois de mudar a interface: `py demo/montar.py`, entrar em `demo/captacao-de-leads-demo` e rodar `npx vercel --prod --yes`.

## Como ler

| Arquivo | Conteúdo |
|---|---|
| [01-inicio-a-ideia.md](01-inicio-a-ideia.md) | De onde veio a ideia, o problema, o que você pediu |
| [02-meio-decisoes-e-evolucao.md](02-meio-decisoes-e-evolucao.md) | Como o projeto evoluiu, decisões tomadas e por quê |
| [03-o-que-foi-criado.md](03-o-que-foi-criado.md) | Tudo que existe hoje: arquivos, telas, dados, automações |
| [04-testado-e-nao-testado.md](04-testado-e-nao-testado.md) | O que foi provado funcionando e o que nunca foi executado de verdade |
| [05-o-que-falta-e-o-fim.md](05-o-que-falta-e-o-fim.md) | Lacunas, riscos e como seria o CRM "pronto" |
| [06-contexto-para-outra-ia.md](06-contexto-para-outra-ia.md) | Resumo pronto para colar em outra IA, com regras, restrições e perguntas abertas |

## Resumo em cinco linhas

1. É um CRM local e gratuito, com duas telas (Atlas e Nexora), cada uma com e-mail e WhatsApp.
2. Roda em http://127.0.0.1:4400 (abrir com `crm/iniciar-crm.bat`), feito em Python (só biblioteca padrão) e JavaScript puro.
3. Capta leads, analisa a dor de cada um com IA, agenda follow-ups D+3, D+7 e D+14, lê as respostas do Gmail e do WhatsApp, classifica e move o card no funil.
4. O WhatsApp nunca envia sozinho: você clica em "Abrir no WhatsApp" e envia; o CRM só observa.
5. Muita coisa está construída mas não foi testada com o mundo real (principalmente o WhatsApp), e o visual ainda não segue a referência que você quer.

## Onde está cada coisa no computador

- Código do CRM: `crm/`
- Dados do CRM: `crm/crm.sqlite3` (não apagar)
- Banco antigo do Nexora, ainda usado: `_opensquad/_memory/nexora/db/nexora.sqlite3`
- Painel antigo do Nexora (aprova e envia o 1º e-mail): `squads/nexora-email/dashboard/` (porta 4318)
- Clone só de referência do Deskcomm: `crm-referencia-deskcomm/` (pode apagar quando quiser)
