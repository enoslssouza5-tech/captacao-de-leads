"""Validador determinístico das regras de copy. A IA pode errar; este modulo nao.

Cada funcao devolve uma lista de violacoes (vazia = aprovada). Usado na geracao (com nova tentativa),
nos follow-ups e nos testes automatizados.
"""
import re
import unicodedata

TRAVESSOES = ("—", "–", "‒", "―")        # — – ‒ ―
URL = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+|\{\{[A-Z_]+\}\}")
NUMERO = re.compile(r"\d[\d.,]*")
FRASE = re.compile(r"[^.!?\n]+[.!?]?")

LIMITES = {                                     # (max caracteres, max frases, max paragrafos)
    ("whatsapp", "primeiro"): (380, 4, 3),
    ("whatsapp", "followup"): (240, 3, 2),
    ("email", "primeiro"): (1100, 12, 9),      # Atlas; a Nexora tem limite proprio abaixo
    ("email", "followup"): (420, 4, 3),
}
ROBOTICAS_PT = ("espero que esteja bem", "gostaria de me apresentar", "prezado", "prezada", "venho por meio", "sou especialista", "somos especialistas",
                "solucoes completas", "soluções completas", "alavancar", "sinergia", "otimizar seus resultados", "levar seu negocio ao proximo nivel",
                "levar seu negócio ao próximo nível")
PROMESSAS_PT = ("previa pronta", "prévia pronta", "ja preparei", "já preparei", "preparei um site", "preparei uma pagina", "preparei uma página", "resultado garantido",
                "garantimos", "garantia de", "100%", "sem risco nenhum", "dobrar suas vendas", "triplicar")
LIMITES_NEXORA_PRIMEIRO = (750, 9, 6)          # e-mail curto: observacao, consequencia, solucao, exemplo, CTA
GENERICAS_PT = ("solucoes personalizadas", "soluções personalizadas", "solucoes sob medida", "soluções sob medida", "estrategias inovadoras", "estratégias inovadoras",
                "resultados incriveis", "resultados incríveis", "transformar seu negocio", "transformar seu negócio", "potencializar", "impulsionar", "elevar sua marca",
                "diferencial competitivo", "no cenario atual", "no cenário atual", "mundo digital", "cada vez mais competitivo", "e fundamental", "é fundamental",
                "posicionamento digital", "presenca digital forte", "presença digital forte", "jornada do cliente", "ecossistema", "robusto", "excelencia", "excelência",
                "inovador", "destaque se", "destaque-se", "de ponta", "expertise")
INSTITUCIONAL_PT = ("somos uma empresa", "a atlas e", "a atlas é", "nossa empresa", "nossos servicos", "nossos serviços", "nossa equipe", "nossa missao", "nossa missão",
                    "ha anos no mercado", "há anos no mercado")
SERVICOS_PT = ("landing page", "landing pages", "trafego pago", "tráfego pago", "gestao de trafego", "gestão de tráfego", "seo", "redes sociais", "social media",
               "criacao de sites", "criação de sites", "identidade visual", "branding", "google ads", "meta ads", "copywriting")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
STOP_PT = {"para", "como", "com", "uma", "que", "mais", "mas", "por", "dos", "das", "nos", "nas", "sua", "seu", "seus", "suas", "ele", "ela", "eles", "esta", "este", "isso",
           "essa", "esse", "entre", "quando", "onde", "sobre", "ainda", "muito", "muita", "pela", "pelo", "pelas", "pelos", "tem", "tudo", "cada", "estao", "fora", "quem",
           "empresa", "empresas", "cliente", "clientes", "hoje", "agora", "pode", "podem", "sendo", "porque", "tambem", "apenas", "ficaria", "horario", "semana", "projeto"}
ESCOPO_EN = ("responsive design", "lead capture form", "basic seo", "social media integration", "revisions", "up to 6 sections", "contracted scope")
INSTITUCIONAL_EN = ("we specialize in", "high-converting landing pages", "client acquisition", "our team of", "we are a full-service", "years of experience")
RODAPE_EN = re.compile(r"don'?t want future emails", re.I)
ROBOTICAS_EN = ("i hope this email finds you well", "i hope you are doing well", "dear sir", "to whom it may concern", "synergy", "game-changer", "cutting-edge",
                "revolutionize", "skyrocket")
PROMESSAS_EN = ("guarantee", "guaranteed results", "100%", "double your", "triple your", "risk-free", "no risk")
PALAVRAS_PT = ("você", "voce", "vocês", "vocês", "não", "nao", "empresa", "site", "página", "para", "com", "uma", "oi", "olá", "bom dia", "boa tarde", "obrigado")
STOP_EN = ("the", "and", "your", "you", "for", "with", "that", "this", "have", "are", "not")


def _palavras(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


def _significativas(texto):
    return {w for w in _palavras(texto) if len(w) >= 5 and w not in STOP_PT}


def _sem_urls(texto):
    return URL.sub(" ", texto)


def _numeros(texto):
    return {re.sub(r"[.,]+$", "", n).replace(".", "").replace(",", ".") for n in NUMERO.findall(_sem_urls(texto))}


def numeros_permitidos(fatos):
    """Conjunto de numeros que aparecem nos fatos comprovados (avaliacoes, nota, evidencias...). Aceita dicts, listas e textos."""
    perm = set()

    def coleta(v):
        if v is None:
            return
        if isinstance(v, (int, float)):
            perm.add(str(int(v)) if float(v).is_integer() else str(v))
            perm.add(str(v).replace(",", "."))
        elif isinstance(v, str):
            perm.update(_numeros(v))
        elif isinstance(v, dict):
            for x in v.values():
                coleta(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                coleta(x)

    coleta(fatos)
    return perm


def _estrutura(texto):
    paragrafos = [p for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]
    frases = [f for f in FRASE.findall(_sem_urls(texto)) if len(f.strip()) > 1]
    return len(texto.strip()), len(frases), len(paragrafos)


def validar(conta, canal, tipo, texto, fatos=None, link_landing=False, recentes=None):
    """conta: atlas|nexora. canal: whatsapp|email. tipo: primeiro|followup. fatos: dados comprovados do lead."""
    v = []
    t = (texto or "").strip()
    if conta == "nexora" and canal == "email" and tipo == "primeiro":
        t = RODAPE_EN.split(t)[0].strip()              # o rodape (descadastro, assinatura, endereco) e fixo e nao conta no tamanho
    if not t:
        return ["mensagem vazia"]
    baixo = t.lower()
    chars, frases, paragrafos = _estrutura(t)
    max_c, max_f, max_p = LIMITES_NEXORA_PRIMEIRO if (conta == "nexora" and canal == "email" and tipo == "primeiro") else LIMITES[(canal, tipo)]
    if chars > max_c:
        v.append("longa demais: %d caracteres (maximo %d)" % (chars, max_c))
    if frases > max_f:
        v.append("frases demais: %d (maximo %d)" % (frases, max_f))
    if paragrafos > max_p:
        v.append("blocos demais: %d (maximo %d)" % (paragrafos, max_p))

    if conta == "atlas":
        if any(c in t for c in TRAVESSOES):
            v.append("usa travessao")
        sem_url = _sem_urls(t)
        if "-" in sem_url:
            v.append("usa hifen ou traco como pontuacao (a regra da Atlas proibe qualquer traco)")
        if re.search(r"aqui (é|e) o enos", baixo):
            v.append("usa 'aqui e o Enos' (deve ser 'me chamo Enos')")
        if tipo == "primeiro" and "me chamo enos" not in baixo:
            v.append("primeira mensagem sem 'me chamo Enos'")
        for r in ROBOTICAS_PT:
            if r in baixo:
                v.append("linguagem robotica: '%s'" % r)
        for p in PROMESSAS_PT:
            if p in baixo:
                v.append("promessa que nao existe: '%s'" % p)
        if tipo == "primeiro" and "?" not in t:
            v.append("sem CTA em forma de pergunta curta")
        for g in GENERICAS_PT:
            if g in baixo:
                v.append("frase generica ou de propaganda: '%s'" % g)
        for g in INSTITUCIONAL_PT:
            if g in baixo:
                v.append("apresentacao institucional: '%s'" % g)
        if sum(1 for s in SERVICOS_PT if s in baixo) >= 3:
            v.append("lista de servicos (a mensagem deve falar so da dor do lead)")
        if EMOJI.search(t):
            v.append("emoji (soa artificial)")
        if t.count("!") > 1:
            v.append("exclamacoes demais")
        frases_norm = [" ".join(_palavras(f)) for f in FRASE.findall(_sem_urls(t)) if len(f.strip()) > 8]
        if len(frases_norm) != len(set(frases_norm)):
            v.append("repete a mesma frase")
        if tipo == "primeiro" and canal == "whatsapp" and isinstance(fatos, dict) and isinstance(fatos.get("dor"), str) and fatos["dor"].strip():
            if len(_significativas(t) & _significativas(fatos["dor"])) < 2:
                v.append("nao cita a dor especifica encontrada na analise do lead")
    else:
        pt = sum(1 for p in PALAVRAS_PT if re.search(r"\b%s\b" % re.escape(p), baixo))
        en = sum(1 for p in STOP_EN if re.search(r"\b%s\b" % p, baixo))
        if pt >= 2 and pt > en:
            v.append("nao esta em ingles")
        for r in ROBOTICAS_EN:
            if r in baixo:
                v.append("linguagem robotica: '%s'" % r)
        for p in PROMESSAS_EN:
            if p in baixo:
                v.append("promessa que nao existe: '%s'" % p)
        if tipo == "primeiro" and canal == "email":
            if sum(1 for s in ESCOPO_EN if s in baixo) >= 3:
                v.append("lista as funcionalidades da landing (longo demais; diga so o que ela resolve)")
            for g in INSTITUCIONAL_EN:
                if g in baixo:
                    v.append("explica a empresa Nexora ('%s'); comece pela observacao sobre o lead" % g)
        if link_landing and not re.search(r"(illustrative|example|sample)", baixo):
            v.append("link da landing nao descrito como exemplo ilustrativo")
        if link_landing and not re.search(r"(adjust|tailor|customi[sz]e|change|adapt)", baixo):
            v.append("nao diz que o exemplo e ajustavel as preferencias da empresa")

    if recentes:
        meu = set(_palavras(t))
        for r in recentes:
            outro = set(_palavras(r or ""))
            if meu and outro and len(meu & outro) / len(meu | outro) >= 0.85:
                v.append("parecida demais com outra mensagem ja usada")
                break
    if "%" in t and fatos is not None and "%" not in " ".join(str(x) for x in (fatos.values() if isinstance(fatos, dict) else [fatos])):
        v.append("percentual sem evidencia")
    if fatos is not None:
        perm = numeros_permitidos(fatos)
        extras = {n for n in _numeros(t) if n not in perm and n not in {"1", "2", "3", "15", "600"}}     # 600 e 15 sao a oferta da Nexora
        if extras:
            v.append("numero sem evidencia: %s" % ", ".join(sorted(extras)))
    return v


def parece_portugues(texto):
    """True se o texto parece estar em portugues (usado para impedir envio em portugues por uma conta em ingles)."""
    baixo = (texto or "").lower()
    pt = sum(1 for p in PALAVRAS_PT if re.search(r"\b%s\b" % re.escape(p), baixo))
    en = sum(1 for p in STOP_EN if re.search(r"\b%s\b" % p, baixo))
    return pt >= 2 and pt > en


def resumo(violacoes):
    return "; ".join(violacoes)
