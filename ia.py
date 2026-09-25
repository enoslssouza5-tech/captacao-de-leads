"""IA local do CRM via `claude -p` (sem API paga). Todas as funcoes devolvem dados estruturados
ou levantam RuntimeError; quem chama decide o fallback."""
import json
import os
import subprocess
import time

import regras

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

APIFY_TOOLS = ["WebFetch", "WebSearch", "mcp__claude_ai_APIFY__search-actors", "mcp__claude_ai_APIFY__fetch-actor-details",
               "mcp__claude_ai_APIFY__call-actor", "mcp__claude_ai_APIFY__get-actor-run", "mcp__claude_ai_APIFY__get-dataset-items"]

CAT_MAP = {"positive": "interessado", "question": "duvida", "neutral": "pendente", "negative": "recusou", "unsubscribe": "recusou",
           "out_of_office": "automatica", "bounce": "bounce", "unclassified": "pendente"}

REGRAS_ATLAS = (
    "Regras de escrita da Atlas (obrigatorias): portugues do Brasil, humano, direto, especifico. NUNCA use travessao nem hifen (nada de '-', '—' ou '–'; "
    "escreva 'email' e nao 'e-mail'). Apresente-se como 'me chamo Enos' (nunca 'aqui e o Enos'). Sem linguagem robotica ('espero que esteja bem', 'gostaria de me apresentar', "
    "'solucoes completas'). Nunca cite Vitoria da Conquista. Nunca invente numero, avaliacao, prova, resultado ou percentual. Nunca diga que ja existe site, previa ou modelo pronto "
    "para a empresa. So use fatos comprovados pelos dados fornecidos."
)
ESTRUTURA_PRIMEIRA = (
    "A primeira mensagem tem que ser lida em poucos segundos: no maximo 4 frases curtas e 300 caracteres. Estrutura obrigatoria: (1) observacao especifica e verdadeira sobre a empresa, "
    "(2) a consequencia em uma frase, (3) proposta simples, (4) pergunta curta como CTA. Nao explique a empresa toda, nao liste varios problemas, nao abra com introducao artificial. "
    "Exemplo so da ESTRUTURA (nao copie o texto): 'Oi, me chamo Enos. Vi que voces tem bastante avaliacao no Google, mas hoje nao tem uma pagina propria para transformar essa procura em orcamento. "
    "Eu trabalho justamente essa parte. Posso te mostrar uma ideia rapida?'"
)


class MensagemReprovada(RuntimeError):
    def __init__(self, violacoes):
        super().__init__("; ".join(violacoes))
        self.violacoes = violacoes


_estado = {"falhas": 0, "ate": 0.0, "ultimo_erro": "", "ultimo_ok": None}
executor = None  # em testes, substitui a chamada real ao claude -p: executor(prompt, tools) -> str


def disponivel() -> bool:
    """False durante o recuo apos falhas seguidas (evita martelar um claude -p fora do ar)."""
    return time.time() >= _estado["ate"]


def estado_ia() -> dict:
    return {"disponivel": disponivel(), "falhas_seguidas": _estado["falhas"], "ultimo_erro": _estado["ultimo_erro"], "ultimo_ok": _estado["ultimo_ok"]}


def _falhou(msg: str):
    _estado["falhas"] += 1
    _estado["ultimo_erro"] = msg[:300]
    _estado["ate"] = time.time() + min(600, 30 * 2 ** min(_estado["falhas"] - 1, 5))


def run_claude(prompt: str, tools=None, timeout: int = 180) -> str:
    if executor is not None:
        return executor(prompt, tools)
    cmd = ["cmd.exe", "/c", CLAUDE_BIN, "-p", "--permission-mode", "dontAsk", "--output-format", "text", "--no-session-persistence"]
    if tools:
        cmd += ["--allowedTools", ",".join(tools)]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        _falhou("claude -p indisponivel: %s" % e)
        raise RuntimeError("claude -p indisponivel: %s" % e) from e
    if proc.returncode != 0:
        _falhou("claude -p falhou: " + (proc.stderr or "")[:200])
        raise RuntimeError("claude -p falhou: " + (proc.stderr or "")[:300])
    _estado.update(falhas=0, ate=0.0, ultimo_erro="", ultimo_ok=time.strftime("%Y-%m-%d %H:%M:%S"))
    return proc.stdout.strip()


def extract_json(text: str):
    """Extrai o primeiro JSON valido (objeto ou lista) da resposta, respeitando qual delimitador aparece primeiro."""
    ordem = sorted((("{", "}"), ("[", "]")), key=lambda par: text.find(par[0]) if text.find(par[0]) != -1 else 10**9)
    for open_c, close_c in ordem:
        a, b = text.find(open_c), text.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except ValueError:
                continue
    raise RuntimeError("resposta da IA sem JSON valido")


def classify_reply(texto: str) -> dict:
    prompt = (
        "Voce classifica a resposta de um lead a uma abordagem comercial (site/landing page e trafego pago). Responda SOMENTE um JSON com as chaves: "
        '"categoria" (positive, question, neutral, negative, unsubscribe, out_of_office, bounce ou unclassified), '
        '"reuniao" (true se o lead aceitou ou pediu conversa, ligacao, reuniao, orcamento ou proposta), '
        '"traducao_pt" (traducao para portugues do Brasil, ou o mesmo texto se ja estiver em portugues), '
        '"resumo" (uma frase em portugues). Regras: unsubscribe = pediu para parar de receber; negative = recusou ou ja tem solucao sem interesse; '
        "neutral = resposta vaga ou pediu retorno depois; out_of_office = resposta automatica; bounce = e-mail devolvido. "
        "Na duvida, use unclassified, nunca arredonde para positive.\n\nRESPOSTA DO LEAD:\n" + texto[:3000]
    )
    d = extract_json(run_claude(prompt, timeout=120))
    cat = d.get("categoria") if d.get("categoria") in CAT_MAP else "unclassified"
    cls = CAT_MAP[cat]
    if d.get("reuniao") and cls in ("interessado", "duvida", "pendente"):
        cls = "reuniao"
    return {"categoria8": cat, "classificacao": cls, "traducao": d.get("traducao_pt") or "", "resumo": d.get("resumo") or ""}


def _corrigir(conta, canal, tipo, texto, fatos, tentativas=2, link=False):
    """Valida com o validador deterministico e pede reescrita a IA ate `tentativas` vezes. Devolve (texto, violacoes)."""
    viol = regras.validar(conta, canal, tipo, texto, fatos, link)
    n = 0
    while viol and n < tentativas:
        prompt = ("Reescreva a mensagem abaixo corrigindo EXATAMENTE estes problemas: " + regras.resumo(viol) + ". Mantenha somente fatos verdadeiros dos dados comprovados. "
                  + (REGRAS_ATLAS if conta == "atlas" else "Write in American English, short, no hype, no invented claims.")
                  + (" " + ESTRUTURA_PRIMEIRA if tipo == "primeiro" and conta == "atlas" else "")
                  + "\nMensagem atual: " + str(texto) + "\nDados comprovados: " + json.dumps(fatos, ensure_ascii=False)[:1500]
                  + "\nResponda SOMENTE com a mensagem corrigida.")
        texto = run_claude(prompt, timeout=120).strip().strip('"')
        viol = regras.validar(conta, canal, tipo, texto, fatos, link)
        n += 1
    return texto, viol


def analyze_lead(lead: dict) -> dict:
    """Analise profunda da dor (com web) + primeira mensagem de WhatsApp e de email, ja validadas pelas regras."""
    prompt = (
        "Voce e analista comercial da Atlas (landing pages premium e gestao de trafego pago). Faca uma ANALISE PROFUNDA do lead abaixo, "
        "pesquisando na web (site dele, Google Maps/avaliacoes, redes sociais, concorrentes da mesma cidade) quando necessario. "
        "Avalie TODOS estes criterios e ache o que mais faz o dono perder cliente ou dinheiro: reputacao (avaliacoes x presenca digital), "
        "existencia e estado da pagina (desatualizada, confusa, lenta, ruim no celular), caminho de conversao (telefone clicavel, WhatsApp, formulario), "
        "clareza da oferta, captacao fora do horario, anuncios sem pagina propria, comparacao com concorrentes locais, autoridade local (perfil Google, SEO local), "
        "confianca visual. Ordene por dano a receita e escolha a dor MAIS FORTE que voce consiga PROVAR com dado real. Nunca transforme hipotese em fato. "
        "Nunca invente numero nem percentual de perda.\n" + REGRAS_ATLAS + "\n" + ESTRUTURA_PRIMEIRA +
        "\nDados do lead (JSON): " + json.dumps(lead, ensure_ascii=False) +
        '\nResponda SOMENTE um JSON com: "dor" (uma frase com a dor principal e o dado que a prova), "criterios" (lista de objetos '
        '{"criterio","achado","impacto"} com impacto alto/medio/baixo), "evidencias" (lista de fatos verificados, cada um com a fonte), "tipo_dor" (rotulo curto: '
        'sem_site, site_desatualizado, site_confuso, sem_conversao, reputacao_sem_captacao, anuncio_sem_pagina, concorrente_a_frente ou outro), '
        '"mensagem" (primeira mensagem de WhatsApp na estrutura acima), "assunto" (assunto curto de email) e "email" (primeiro email, ate 5 frases, mesma abertura).'
    )
    d = extract_json(run_claude(prompt, tools=["WebFetch", "WebSearch"], timeout=420))
    fatos = {"lead": {k: lead.get(k) for k in ("avaliacoes", "nota_google")}, "evidencias": d.get("evidencias"), "criterios": d.get("criterios")}
    d["violacoes"] = {}
    for campo, canal in (("mensagem", "whatsapp"), ("email", "email")):
        texto, viol = _corrigir("atlas", canal, "primeiro", d.get(campo), fatos)
        d[campo] = texto
        if viol:
            d["violacoes"][campo] = viol
    return d


def generate_followup(lead: dict, passo: int, canal: str, conta: str, historico: str) -> str:
    angulos = {1: "lembrete leve, sem repetir o primeiro texto, uma pergunta simples",
               2: "ANGULO NOVO: traga outro beneficio concreto ligado a dor do lead ou ofereca mostrar um exemplo",
               3: "encerramento educado: diga que vai parar de insistir e deixe a porta aberta, sem pressao"}
    idioma = "ingles americano" if conta == "nexora" else "portugues do Brasil"
    extra = REGRAS_ATLAS if conta == "atlas" else "Tone: short, polite, no hype, no fabricated claims; the page example is illustrative and adjustable."
    prompt = (f"Escreva o follow-up {passo} de 3 para um lead que nao respondeu. Canal: {canal}. Idioma: {idioma}. Objetivo do passo: {angulos[passo]}. "
              f"Maximo 2 frases curtas (ate 200 caracteres), sem assunto, sem assinatura longa. {extra}\n"
              f"Lead: {json.dumps(lead, ensure_ascii=False)}\nHistorico do que ja foi enviado:\n{historico[:1500]}\n"
              "Responda SOMENTE com o texto da mensagem.")
    texto = run_claude(prompt, timeout=120).strip().strip('"')
    fatos = {"lead": {k: lead.get(k) for k in ("avaliacoes", "nota_google")}, "dor": lead.get("dor")}
    texto, viol = _corrigir(conta, canal, "followup", texto, fatos)
    if viol:
        raise MensagemReprovada(viol)
    return texto


def captar(conta: str, cidade: str, categoria: str, quantidade: int, ja_conhecidos: list) -> list:
    pais = "Brasil" if conta == "atlas" else "Estados Unidos"
    prompt = (
        f"Use o Apify (Google Maps scraper) para encontrar ate {quantidade} empresas da categoria '{categoria}' em {cidade}, {pais}. "
        "Escolha o Actor pela busca na Store, limite o gasto ao minimo (maxCrawledPlaces pequeno). Devolva SOMENTE um JSON (lista) com objetos: "
        '{"nome","telefone","email","site","cidade","avaliacoes" (numero),"nota_google" (numero)}; use null quando nao houver dado; '
        "nunca invente e-mail nem telefone. Ignore estas empresas ja conhecidas: " + json.dumps(ja_conhecidos[:200], ensure_ascii=False)
    )
    return extract_json(run_claude(prompt, tools=APIFY_TOOLS, timeout=600))


def weekly_review(dados: dict) -> list:
    prompt = ("Voce e o curador de scripts de prospeccao. Com base nas metricas e nas respostas reais abaixo, proponha de 1 a 4 ajustes concretos nos roteiros "
              "(abertura, dor usada, follow-ups, resposta a objecoes). Nao invente dados. Responda SOMENTE um JSON (lista) de objetos "
              '{"titulo","evidencia","ajuste_sugerido"}.\n' + json.dumps(dados, ensure_ascii=False)[:9000])
    return extract_json(run_claude(prompt, timeout=240))
