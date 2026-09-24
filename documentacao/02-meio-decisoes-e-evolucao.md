# 02. O meio: decisões e evolução

## Linha do tempo

1. **Análise do Deskcomm** e decisão de não instalá-lo (exige VPS pago, Supabase e IA paga).
2. **Primeiro mockup** em HTML estático, só para você ver o estilo.
3. **Clone do repositório do Deskcomm** para ler o design: paleta sálvia sobre bege, fonte Atkinson, cantos de 8 px, tema claro e escuro.
4. **CRM v0:** servidor Python, leitura dos 108 leads reais da Nexora e Kanban.
5. **Sua crítica ao visual:** você mandou prints do Fluxa (tela "Hoje", um lead por vez) e do LYA (tabela de captação com nota de oportunidade). O visual virou escuro com laranja.
6. **Fase 1:** dados unificados, follow-ups D+3, D+7 e D+14, respostas, financeiro, pontuação.
7. **Você pediu automação total** (WhatsApp lido sozinho, funis iguais, mover card pelo conteúdo). Fases 2 a 6 foram feitas de uma vez.
8. **Testes reais** (ver arquivo 04) e **correções** de bugs achados neles.
9. **Tela de Gmail** estilo Gmail.
10. Esta documentação.

## Decisões importantes e o porquê

| Decisão | Motivo |
|---|---|
| CRM próprio em vez de instalar o Deskcomm | Você exigiu tudo gratuito; o Deskcomm precisa de VPS, Supabase e chave de IA paga; e ele não faz e-mail de prospecção |
| Python só com biblioteca padrão + SQLite, JavaScript puro | Zero instalação, roda no seu Windows, fácil de mexer |
| Só escuta em 127.0.0.1 | Sem login próprio; só a sua máquina acessa |
| IA via `claude -p` local | Sem custo de API extra; já era o padrão do Nexora |
| WhatsApp: observador **somente leitura** | Automatizar envio derruba o número; o limite de contatos novos é uma proteção da plataforma. Você aceitou o modelo "você envia, o CRM detecta" |
| Limite de 15 WhatsApp por dia (configurável) | Regra prática, não existe número oficial seguro; o risco vem do comportamento (denúncias, textos iguais, contatos novos sem resposta) |
| Funil único de 7 etapas para tudo | Você pediu funis iguais: Novo, Pronto, Contatado, Respondeu, Negociando, Fechado, Perdido |
| Classificação da resposta move o card | Interessado, dúvida, pendente vão para Respondeu; quer conversar vai para Negociando; recusou ou e-mail devolvido vai para Perdido e bloqueia o contato; resposta automática não muda nada |
| Follow-up D+3, D+7, D+14 | Você escolheu os três passos que propus |
| Texto do follow-up adaptado por IA perto do vencimento | Para não repetir mensagem genérica; o texto padrão fica como reserva |
| Follow-up automático de e-mail nasce **desligado** | Envia e-mail de verdade a estranhos e nunca foi testado com envio real; ligar é uma decisão sua em Conexões |
| Aprovação do 1º e-mail da Nexora continua no painel antigo (porta 4318) | Regra original do projeto; o CRM só lê esse banco |
| Captação da Atlas com a mesma fonte da Nexora (Apify Google Maps) | Pedido seu; cota gratuita de US$ 5 por mês é dividida entre as duas empresas |
| Financeiro com baixa manual | Detectar pagamento sozinho exige webhook (Mercado Pago, Asaas, Stripe) ou ler e-mail do banco; ficou para depois |

## Mudança de rumo mais importante

Primeiro eu propus WhatsApp semiautomático (você marca "enviei"). Depois você pediu que o CRM tivesse "acesso ao meu WhatsApp" para detectar o envio e as respostas sem você marcar nada. Então criei o **observador** (biblioteca whatsapp-web.js), que só lê e reporta eventos ao CRM. O envio continua manual. Isso usa o WhatsApp Web de forma não oficial, com um risco pequeno de restrição do número, já explicado a você.

## A crítica sobre mensagens genéricas

Você percebeu que a dor citada (ex.: "6 páginas levando a um formulário") não faz o dono sentir que perde clientes. Ficou definido:

- A escolha da dor deve cruzar **todos** os critérios e ordenar pelo dano real à receita: reputação x presença, existência e estado da página, caminho de conversão, clareza da oferta, captação fora do horário, anúncio sem página própria, concorrentes locais, autoridade local, confiança visual.
- Abrir com a dor mais forte que os fatos provem (ex.: muitas avaliações e nenhuma página de captação).
- Defeitos técnicos menores entram só como apoio.
- Nunca inventar número ou percentual de perda.
- Regra escrita em três lugares da Nexora: `bulk_rewrite_pronto.py`, `audit-checklist.md` (PARTE 7) e `step-03-geracao.md`. Para a Atlas ela está em `crm/ia.py` (função `analyze_lead`).

## Referências visuais recebidas

| Referência | O que aproveitamos | Situação |
|---|---|---|
| Deskcomm | Paleta e estrutura de menu, kanban, radar | Lido no código, não executado |
| Fluxa (print) | Tela "Hoje": um lead por vez, mensagem pronta, ações, saúde comercial, ritmo do dia | Aplicado |
| LYA (print) | Tabela de captação com nota, sinais e oportunidade, filtros, botão Abordar | Aplicado |
| Behance "Rectio" | Estilo de dashboard de geração de leads | **Não visto**: o Behance bloqueia navegador automatizado (erro 400) |
| Dribbble | Estilo geral de dashboards | Só a página de busca foi vista |
| Gmail | Tela de caixa de e-mail | Aplicado (pastas, lista, leitura, responder, escrever) |
