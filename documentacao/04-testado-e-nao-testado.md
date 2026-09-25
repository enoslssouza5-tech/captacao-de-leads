# 04. Testado e nao testado (atualizado em 2026-09-24)

## Executado e passou
- Suite automatizada: 131 testes, rodada duas vezes seguidas, todos OK (`py -m unittest discover -s tests`).
- Navegador real (Playwright), desktop e 390 px: 26 verificacoes, sem rolagem horizontal, barra inferior, alvos de toque, funil legivel.
- WhatsApp com processos reais (`tests/verificacao_real_whatsapp.py`): QR aparece, renova sozinho, "Gerar novo QR" nao deixa processo orfao, Node morto a forca sobe de novo sozinho, parar encerra Node e Chrome. 10 de 10.
- Seguranca: validacao de Host/Origin, POST so JSON, arquivos estaticos em lista permitida, so 127.0.0.1.
- Funil: so avanca; recusa e bounce vao para Perdido e bloqueiam; resposta automatica nao muda nada; pagamento fecha o lead.
- E-mail: limite de 20 por dia por conta, 45 s entre envios, descadastro, bloqueios, aprovacao manual Nexora, trava de envio unica.
- Copy: validador (Atlas sem travessao, "me chamo Enos", limites por canal; Nexora em ingles e link ilustrativo). Mensagem reprovada nao entra na fila.
- Robustez: backup diario e restauracao de banco corrompido, falha do `claude -p` com recuo, workers independentes, concorrencia.
- Desempenho: 3.000 leads, endpoints principais em ate cerca de 0,2 s.
- Windows: tarefa de inicializacao criada e removida (com nome de teste).

## NAO executado (precisa de voce)
- Escanear o QR com o celular e ver o WhatsApp autenticar e os eventos reais chegarem.
- Envio real de follow-up por e-mail (as chaves automaticas ficam desligadas por padrao).
- Autenticacao real do Gmail da Atlas.
- Instalar a inicializacao com o Windows (nao foi instalada).
