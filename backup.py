"""Backup dos bancos SQLite (CRM e Nexora) usando a API de backup do SQLite (seguro com o banco em uso)."""
import os
import sqlite3
import time


def _copiar(origem, destino, somente_leitura):
    uri = "file:%s?mode=ro" % origem.replace("\\", "/") if somente_leitura else origem
    src = sqlite3.connect(uri, uri=somente_leitura)
    try:
        dst = sqlite3.connect(destino)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def fazer_backup(pasta, fontes, manter=14, forcar=False):
    """fontes: {nome: (caminho, somente_leitura)}. Um backup por dia por fonte (a menos que forcar)."""
    os.makedirs(pasta, exist_ok=True)
    hoje = time.strftime("%Y%m%d")
    feitos = []
    for nome, (caminho, ro) in fontes.items():
        if not os.path.exists(caminho):
            continue
        if not forcar and any(f.startswith("%s-%s" % (nome, hoje)) for f in os.listdir(pasta)):
            continue
        destino = os.path.join(pasta, "%s-%s.sqlite3" % (nome, time.strftime("%Y%m%d-%H%M%S")))
        _copiar(caminho, destino, ro)
        feitos.append(destino)
        antigos = sorted(f for f in os.listdir(pasta) if f.startswith(nome + "-"))
        for f in antigos[:-manter]:
            os.remove(os.path.join(pasta, f))
    return feitos


def listar(pasta):
    if not os.path.isdir(pasta):
        return []
    return sorted(os.listdir(pasta))


def integridade_ok(caminho):
    """True se o SQLite abre e passa em PRAGMA integrity_check."""
    try:
        conn = sqlite3.connect(caminho, timeout=10)
        try:
            return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def verificar_e_restaurar(caminho, pasta, nome):
    """Se o banco estiver corrompido: guarda o arquivo ruim ao lado (nunca apaga) e restaura o backup mais recente.
    Retorna {"acao": "ok" | "restaurado" | "sem_backup" | "inexistente", ...}."""
    if not os.path.exists(caminho):
        return {"acao": "inexistente"}
    if integridade_ok(caminho):
        return {"acao": "ok"}
    backups = sorted(f for f in listar(pasta) if f.startswith(nome + "-"))
    ruim = "%s.corrompido-%s" % (caminho, time.strftime("%Y%m%d-%H%M%S"))
    if not backups:
        return {"acao": "sem_backup", "arquivo": caminho}
    for ext in ("-wal", "-shm"):
        if os.path.exists(caminho + ext):
            os.replace(caminho + ext, ruim + ext)
    os.replace(caminho, ruim)
    for b in reversed(backups):                       # do mais novo para o mais antigo, ate achar um integro
        origem = os.path.join(pasta, b)
        if integridade_ok(origem):
            _copiar(origem, caminho, False)
            return {"acao": "restaurado", "backup": b, "arquivo_corrompido": ruim}
    os.replace(ruim, caminho)                         # nenhum backup integro: devolve o original
    return {"acao": "sem_backup", "arquivo": caminho}
