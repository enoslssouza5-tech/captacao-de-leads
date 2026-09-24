"""IA local do CRM via `claude -p` (sem API paga). Todas as funcoes devolvem dados estruturados
ou levantam RuntimeError; quem chama decide o fallback."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

APIFY_TOOLS = ["WebFetch", "WebSearch", "mcp__claude_ai_APIFY__search-actors", "mcp__claude_ai_APIFY__fetch-actor-details",
               "mcp__claude_ai_APIFY__call-actor", "mcp__claude_ai_APIFY__get-actor-run", "mcp__claude_ai_APIFY__get-dataset-items"]

CAT_MAP = {"positive": "interessado", "question": "duvida", "neutral": "pendente", "negative": "recusou", "unsubscribe": "recusou",
           "out_of_office": "automatica", "bounce": "bounce", "unclassified": "pendente"}

REGRAS_ATLAS = ("Regras de escrita para a Atlas: portugues do Brasil, tom humano e direto, SEM travessoes ou hifens usados como pontuacao "
                "(nada de '-', '—' ou '–'), se apresente como 'me chamo Enos' (nunca 'aqui e o Enos'), nunca cite Vitoria da Conquista, "
                "nunca invente numeros, prova ou resultados, nunca diga que ja existe uma previa pronta.")


def run_claude(prompt: str, tools=None, timeout: int = 180) -> str:
    cmd = ["cmd.exe", "/c", CLAUDE_BIN, "-p", "--permission-mode", "dontAsk", "--output-format", "text", "--no-session-persistence"]
    if tools:
        cmd += ["--allowedTools", ",".join(tools)]
    proc = subprocess.run(cmd, cwd=ROOT, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("claude -p falhou: " + (proc.stderr or "")[:300])
    return proc.stdout.strip()


def extract_json(text: str):
    for open_c, close_c in (("{", "}"), ("[", "]")):
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


def analyze_lead(lead: dict) -> dict:
    """Analise profunda da dor com acesso a web (site do lead, Google, concorrentes)."""
    prompt = (
        "Voce e analista comercial da Atlas (landing pages premium e gestao de trafego pago). Faca uma ANALISE PROFUNDA do lead abaixo, "
        "pesquisando na web (site dele, Google Maps/avaliacoes, redes sociais, concorrentes da mesma cidade) quando necessario. "
        "Avalie TODOS estes criterios e ache o que mais faz o dono perder cliente ou dinheiro: reputacao (avaliacoes x presenca digital), "
        "existencia e estado da pagina (desatualizada, confusa, lenta, ruim no celular), caminho de conversao (telefone clicavel, WhatsApp, formulario), "
        "clareza da oferta, captacao fora do horario, anuncios sem pagina propria, comparacao com concorrentes locais, autoridade local (perfil Google, SEO local), "
        "confianca visual. Ordene por dano a receita; escolha 1 ou 2 dores que voce consiga PROVAR com dado real. Nunca invente numero nem percentual de perda.\n"
        + REGRAS_ATLAS +
        "\nDados do lead (JSON): " + json.dumps(lead, ensure_ascii=False) +
        '\nResponda SOMENTE um JSON com: "dor" (uma frase com a dor principal e o dado que a prova), "criterios" (lista de objetos '
        '{"criterio","achado","impacto"} com impacto alto/medio/baixo), "evidencias" (lista de fatos verificados), "tipo_dor" (rotulo curto: '
        'sem_site, site_desatualizado, site_confuso, sem_conversao, reputacao_sem_captacao, anuncio_sem_pagina, concorrente_a_frente ou outro), '
        '"mensagem" (primeira mensagem de WhatsApp curta que abre com a dor principal e oferece mostrar um modelo, sem promessas falsas), '
        '"assunto" e "email" (versao para e-mail, mesma abertura).'
    )
    return extract_json(run_claude(prompt, tools=["WebFetch", "WebSearch"], timeout=420))


def generate_followup(lead: dict, passo: int, canal: str, conta: str, historico: str) -> str:
    angulos = {1: "lembrete leve, sem repetir o primeiro texto, uma pergunta simples",
               2: "ANGULO NOVO: traga outro beneficio concreto ligado a dor do lead ou ofereca mostrar um exemplo",
               3: "encerramento educado: diga que vai parar de insistir e deixe a porta aberta, sem pressao"}
    idioma = "ingles americano" if conta == "nexora" else "portugues do Brasil"
    extra = REGRAS_ATLAS if conta == "atlas" else "Tone: short, polite, no hype, no fabricated claims; the page example is illustrative and adjustable."
    prompt = (f"Escreva o follow-up {passo} de 3 para um lead que nao respondeu. Canal: {canal}. Idioma: {idioma}. Objetivo do passo: {angulos[passo]}. "
              f"Maximo 60 palavras, sem assunto, sem assinatura longa. {extra}\n"
              f"Lead: {json.dumps(lead, ensure_ascii=False)}\nHistorico do que ja foi enviado:\n{historico[:1500]}\n"
              "Responda SOMENTE com o texto da mensagem.")
    return run_claude(prompt, timeout=120).strip()


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
