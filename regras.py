"""Validador determinístico das regras de copy. A IA pode errar; este modulo nao.

Cada funcao devolve uma lista de violacoes (vazia = aprovada). Usado na geracao (com nova tentativa),
nos follow-ups e nos testes automatizados.
"""
import re

TRAVESSOES = ("—", "–", "‒", "―")        # — – ‒ ―
URL = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+|\{\{[A-Z_]+\}\}")
NUMERO = re.compile(r"\d[\d.,]*")
FRASE = re.compile(r"[^.!?\n]+[.!?]?")

LIMITES = {                                     # (max caracteres, max frases, max paragrafos)
    ("whatsapp", "primeiro"): (330, 4, 3),
    ("whatsapp", "followup"): (240, 3, 2),
    ("email", "primeiro"): (1100, 12, 9),
    ("email", "followup"): (420, 4, 3),
}
ROBOTICAS_PT = ("espero que esteja bem", "gostaria de me apresentar", "prezado", "prezada", "venho por meio", "sou especialista", "somos especialistas",
                "solucoes completas", "soluções completas", "alavancar", "sinergia", "otimizar seus resultados", "levar seu negocio ao proximo nivel",
                "levar seu negócio ao próximo nível")
PROMESSAS_PT = ("previa pronta", "prévia pronta", "ja preparei", "já preparei", "preparei um site", "preparei uma pagina", "preparei uma página", "resultado garantido",
                "garantimos", "garantia de", "100%", "sem risco nenhum", "dobrar suas vendas", "triplicar")
ROBOTICAS_EN = ("i hope this email finds you well", "i hope you are doing well", "dear sir", "to whom it may concern", "synergy", "game-changer", "cutting-edge",
                "revolutionize", "skyrocket")
PROMESSAS_EN = ("guarantee", "guaranteed results", "100%", "double your", "triple your", "risk-free", "no risk")
PALAVRAS_PT = ("você", "voce", "vocês", "vocês", "não", "nao", "empresa", "site", "página", "para", "com", "uma", "oi", "olá", "bom dia", "boa tarde", "obrigado")
STOP_EN = ("the", "and", "your", "you", "for", "with", "that", "this", "have", "are", "not")


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


def validar(conta, canal, tipo, texto, fatos=None, link_landing=False):
    """conta: atlas|nexora. canal: whatsapp|email. tipo: primeiro|followup. fatos: dados comprovados do lead."""
    v = []
    t = (texto or "").strip()
    if not t:
        return ["mensagem vazia"]
    baixo = t.lower()
    chars, frases, paragrafos = _estrutura(t)
    max_c, max_f, max_p = LIMITES[(canal, tipo)]
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
        if "vitória da conquista" in baixo or "vitoria da conquista" in baixo:
            v.append("cita Vitoria da Conquista (proibido)")
        if tipo == "primeiro" and "?" not in t:
            v.append("sem CTA em forma de pergunta curta")
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
        if link_landing and not re.search(r"(illustrative|example|sample)", baixo):
            v.append("link da landing nao descrito como exemplo ilustrativo")
        if link_landing and not re.search(r"(adjust|tailor|customi[sz]e|change|adapt)", baixo):
            v.append("nao diz que o exemplo e ajustavel as preferencias da empresa")

    if "%" in t and fatos is not None and "%" not in " ".join(str(x) for x in (fatos.values() if isinstance(fatos, dict) else [fatos])):
        v.append("percentual sem evidencia")
    if fatos is not None:
        perm = numeros_permitidos(fatos)
        extras = {n for n in _numeros(t) if n not in perm and n not in {"1", "2", "3", "15", "600"}}     # 600 e 15 sao a oferta da Nexora
        if extras:
            v.append("numero sem evidencia: %s" % ", ".join(sorted(extras)))
    return v


def resumo(violacoes):
    return "; ".join(violacoes)
