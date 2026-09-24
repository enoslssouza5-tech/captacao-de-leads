# 04. O que foi testado e o que não foi

Seja crítico com este arquivo: "testado" quer dizer que foi executado de verdade nesta conversa. Não existe suíte de testes automatizados.

## Testado com dados e serviços reais

| O quê | Resultado |
|---|---|
| Leitura dos 108 leads da Nexora e mapeamento para o funil de 7 etapas | Funcionou (56 Pronto, 48 Contatado, 4 Perdido) |
| Leitura do Gmail real da Nexora | Funcionou: 5 na caixa de entrada, 51 enviados, 10 na lixeira, 2 em spam |
| Classificação de resposta com IA local | Funcionou em respostas reais |
| Pedido de descadastro real (uma imobiliária dos EUA) | Classificado como "recusou", lead movido para Perdido, e-mail suprimido no banco da Nexora |
| E-mails devolvidos reais (um escritório de advocacia e uma imobiliária) | Detectados, leads movidos para Perdido, endereços suprimidos |
| Resposta automática real (uma imobiliária dos EUA) | Identificada como resposta automática, follow-ups mantidos |
| Achado: respostas de leads estavam em spam | Corrigido, a leitura agora varre caixa de entrada e spam |
| Captação com Apify (Google Maps) | Funcionou: 3 locadoras reais de uma cidade do interior da Bahia, sem duplicar |
| Análise de dor com pesquisa na web | Funcionou num teste (uma imobiliária dos EUA): 5 critérios, evidências reais, mensagem sem travessão |
| Adaptação de follow-up por IA | Funcionou (follow-up em inglês para um lead da Nexora) |
| Tela "Caixa de e-mail" com o Gmail real | Funcionou: pastas, lista, leitura, ligação com o lead |
| Todas as telas das duas empresas | Renderizam sem erro de JavaScript (percorridas por navegador automatizado) |
| Bloqueio de contato que recusou | Funcionou (novo lead com o mesmo telefone foi barrado) |

## Testado só por simulação

| O quê | Como |
|---|---|
| Ciclo do WhatsApp | Eventos falsos enviados ao CRM: "saída" moveu o lead para Contatado e criou os 3 follow-ups; "entrada" foi classificada como "quer conversar" e moveu para Negociando; número desconhecido foi ignorado |
| Erro de permissão das ações do Gmail | Chamada com id falso retornou o aviso de autorização extra |

## Nunca executado

| O quê | Por quê |
|---|---|
| **Observador real do WhatsApp** | Precisa que você escaneie o QR em Conexões. Nunca conectou ao WhatsApp real. Risco de a biblioteca ou a estrutura do WhatsApp Web falhar |
| **Envio real de follow-up por e-mail** | A chave nasce desligada; enviaria e-mail a estranhos |
| **Envio de resposta e "Escrever" na tela de Gmail** | Também mandaria e-mail real |
| **Excluir, arquivar, marcar como lida, estrela** | Exigem a permissão gmail.modify, que ainda não foi autorizada |
| **Gmail da Atlas** | Ainda não existe. Leitura, envio e aprovação da Atlas nunca rodaram |
| **Envio dos e-mails aprovados da Atlas** | Depende do Gmail da Atlas |
| **Captação diária automática da Atlas** | Só a captação manual foi testada |
| **Revisão semanal por IA (propostas de ajuste)** | Nunca gerada |
| **Aprendizado com dados reais** | As tabelas existem, mas há poucos envios registrados para tirar conclusões |
| **Notificação do navegador** | Código escrito, nunca observada |
| **Financeiro com dados reais** | Só a estrutura e a tela foram vistas |
| **Reescrita dos 56 e-mails "prontos" da Nexora com a nova regra de dor** | Não rodei, consome tokens; a regra está escrita mas os e-mails ainda estão no formato antigo |
| **Uso em celular ou com outro navegador** | Só foi visto num navegador de desktop |

## Problemas encontrados e corrigidos durante os testes

1. Botões secundários ilegíveis no tema da Nexora (texto escuro em fundo escuro).
2. Botão "Captar leads" aparecendo em telas erradas (atributo `hidden` anulado por CSS).
3. Servidor caía com texto que não era UTF-8 (agora responde 400 sem cair).
4. Leitura do Gmail ignorava a pasta de spam, onde caíam respostas reais.
5. Adaptação de follow-up da Nexora atrasava a análise de leads da Atlas (agora as duas rodam a cada ciclo).
6. Números captados eram telefones fixos (sem WhatsApp): agora são marcados sozinhos como "sem WhatsApp" e não entram na fila.
7. Erro de sintaxe no JavaScript que deixava a tela em branco (parêntese faltando), corrigido.

## Efeitos reais que o CRM já causou (para você saber)

- Suprimiu 3 endereços da Nexora no banco original (1 descadastro e 2 e-mails devolvidos).
- Gastou uma pequena parte da cota gratuita do Apify (captação de 3 leads).
- Não enviou nenhum e-mail nem WhatsApp.
- Os leads de teste que criei foram apagados. Restam no banco da Atlas 3 leads reais (telefone fixo, marcados como "sem WhatsApp").
