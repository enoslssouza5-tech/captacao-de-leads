# 04. Testado e nao testado (atualizado em 2026-09-26)

## Executado e passou
- Suite automatizada: 165 testes, todos OK (`py -m unittest discover -s tests`).
- Navegador real (Playwright), desktop e 390 px: 26 verificacoes, sem rolagem horizontal, barra inferior, alvos de toque, funil legivel.
- WhatsApp com processos reais (`tests/verificacao_real_whatsapp.py`): QR aparece, renova sozinho, "Gerar novo QR" nao deixa processo orfao, Node morto a forca sobe de novo sozinho, parar encerra Node e Chrome. 10 de 10.
- Seguranca: validacao de Host/Origin, POST so JSON, arquivos estaticos em lista permitida, so 127.0.0.1.
- Funil: so avanca; recusa e bounce vao para Perdido e bloqueiam; resposta automatica nao muda nada; pagamento fecha o lead.
- E-mail: limite de 20 por dia por conta, 45 s entre envios, descadastro, bloqueios, aprovacao manual Nexora, trava de envio unica.
- Copy: validador (Atlas sem travessao, "me chamo Enos", limites por canal; Nexora em ingles e link ilustrativo). Mensagem reprovada nao entra na fila.
- Robustez: backup diario e restauracao de banco corrompido, falha do `claude -p` com recuo, workers independentes, concorrencia.
- Desempenho: 3.000 leads, endpoints principais em ate cerca de 0,2 s.
- Windows: tarefa de inicializacao criada e removida (com nome de teste).

- Evolucao 2026-09-26: observador do WhatsApp resolve IDs @lid e mostra o que viu em Configuracoes > Conexoes; deteccao de envio manual por e-mail (Gmail Enviados); detalhe do lead em texto humano; kanban por arrastar e soltar (e botao Mover no celular) com as regras do funil; copy Atlas curta com validador; e-mail Nexora curto com landing por `?empresa=slug`; traducao EN/PT local (so para compreensao, envio Nexora sempre em ingles). 38 verificacoes no navegador.

## NAO executado (precisa de voce)
- Enviar uma mensagem manual pelo WhatsApp conectado a um numero que seja lead e conferir Conexoes > "O que o observador viu" e o Kanban.
- Escanear o QR com o celular e ver o WhatsApp autenticar e os eventos reais chegarem.
- Envio real de follow-up por e-mail (as chaves automaticas ficam desligadas por padrao).
- Autenticacao real do Gmail da Atlas.
- Instalar a inicializacao com o Windows (nao foi instalada).
