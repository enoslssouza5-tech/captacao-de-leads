"""Radar completo, aprendizado detalhado, financeiro detalhado, proxima acao, validacao de copy e arquivos estaticos."""
import http.client
from datetime import datetime, timedelta, timezone

from base import BaseCRM, store, ndb


def iso(horas):
    return (datetime.now(timezone.utc) + timedelta(hours=horas)).isoformat()


class TestRadarCompleto(BaseCRM):
    def _espera(self, nome, tel, cls, horas):
        lid = self.novo_lead(nome=nome, telefone=tel)
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/leads/%d/resposta" % lid, {"texto": "oi " + nome, "classificacao": cls})
        c = store.crm()
        c.execute("UPDATE respostas SET created_at=? WHERE lead_ref=?", (iso(-horas), "c%d" % lid))
        c.execute("UPDATE envios SET enviado_em=? WHERE lead_ref=?", (iso(-horas - 5), "c%d" % lid))
        c.commit()
        c.close()
        return lid

    def test_categorias_do_radar(self):
        self._espera("Negociando 5h", "(77) 99010-0001", "reuniao", 5)          # negociando ha 5h: urgente
        self._espera("Interessado 30h", "(77) 99010-0002", "interessado", 30)     # 24 a 48h: sem retorno
        self._espera("Interessado 60h", "(77) 99010-0003", "interessado", 60)     # mais de 48h: urgente
        self._espera("Interessado 2h", "(77) 99010-0004", "interessado", 2)       # recente: nao aparece
        atras = self.novo_lead(nome="Atrasado", telefone="(77) 99010-0005")
        self.post("/api/leads/%d/sent" % atras)
        c = store.crm()
        c.execute("UPDATE tarefas SET due_date=date('now','-3 day') WHERE lead_ref=? AND passo=1", ("c%d" % atras,))
        c.commit()
        c.close()
        r = self.get("/api/radar?conta=atlas")[1]
        self.assertEqual(sorted(x["nome"] for x in r["urgente"]), ["Interessado 60h", "Negociando 5h"])
        self.assertEqual([x["nome"] for x in r["sem_retorno"]], ["Interessado 30h"])
        self.assertEqual([(x["nome"], x["dias_atraso"]) for x in r["followup_atrasado"]], [("Atrasado", 3)])
        self.assertEqual(r["total"], 4)

    def test_sem_dados_radar_vazio(self):
        r = self.get("/api/radar?conta=atlas")[1]
        self.assertEqual((r["urgente"], r["sem_retorno"], r["followup_atrasado"], r["esfriando"], r["devolvidos"], r["total"]), ([], [], [], [], [], 0))


class TestAprendizadoCompleto(BaseCRM):
    def test_por_hora_respeita_fuso_e_dia_da_semana(self):
        lid = self.novo_lead()
        self.post("/api/leads/%d/sent" % lid)
        self.post("/api/leads/%d/resposta" % lid, {"texto": "x", "classificacao": "interessado"})
        c = store.crm()
        c.execute("UPDATE envios SET enviado_em='2026-09-21T15:30:00+00:00'")       # segunda 15:30 UTC
        c.commit()
        c.close()
        utc = self.get("/api/aprendizado?conta=atlas&tz=0")[1]
        br = self.get("/api/aprendizado?conta=atlas&tz=-180")[1]                    # UTC-3
        self.assertEqual([h["hora"] for h in utc["por_hora"] if h["envios"]], [15])
        self.assertEqual([h["hora"] for h in br["por_hora"] if h["envios"]], [12])
        seg = next(d for d in br["por_dia_semana"] if d["chave"] == "Seg")
        self.assertEqual((seg["envios"], seg["respostas"], seg["taxa"]), (1, 1, 100))
        self.assertTrue(br["insuficiente_horario"])                                # 1 envio: dados insuficientes

    def test_objecoes_mais_frequentes_agrupadas(self):
        for i, motivo in enumerate(["Ja tem fornecedor", "Ja tem fornecedor", "Sem interesse agora"]):
            lid = self.novo_lead(nome="O%d" % i, telefone="(77) 99020-000%d" % i)
            self.post("/api/leads/%d/sent" % lid)
            self.post("/api/leads/%d/resposta" % lid, {"texto": motivo, "classificacao": "recusou"})
            c = store.crm()
            c.execute("UPDATE respostas SET resumo=? WHERE lead_ref=?", (motivo, "c%d" % lid))
            c.commit()
            c.close()
        top = self.get("/api/aprendizado?conta=atlas")[1]["objecoes_top"]
        self.assertEqual([(o["motivo"], o["n"]) for o in top], [("Ja tem fornecedor", 2), ("Sem interesse agora", 1)])

    def test_abordagem_ab_da_nexora(self):
        for i in range(6):
            lid = self.nexora_lead("AB%d" % i, "ab%d@x.example" % i, enviado_ha_dias=2, ab_variant="A" if i < 4 else "B")
        conn = ndb.connect()
        conn.execute("UPDATE leads SET status='respondido', responded_at=? WHERE email='ab0@x.example'", (iso(-1),))
        conn.commit()
        conn.close()
        ab = {x["chave"]: x for x in self.get("/api/aprendizado?conta=nexora")[1]["por_abordagem"]}
        self.assertEqual((ab["Variacao A (diagnostico)"]["contatados"], ab["Variacao A (diagnostico)"]["respostas"]), (4, 1))
        self.assertTrue(ab["Variacao B (oportunidade)"]["insuficiente"])           # so 2 contatados
        self.assertEqual(self.get("/api/aprendizado?conta=atlas")[1]["por_abordagem"], [])


class TestFinanceiroCompleto(BaseCRM):
    def test_indicadores_serie_e_origem(self):
        a = self.novo_lead(nome="Origem A", fonte="Google Maps", telefone="(77) 99030-0001")
        b = self.novo_lead(nome="Origem B", fonte="Indicacao", telefone="(77) 99030-0002")
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "A", "valor": "3000", "status": "pago", "lead_ref": "c%d" % a})
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "B", "valor": "1000", "status": "pago", "lead_ref": "c%d" % b})
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "C", "valor": "500", "status": "pago"})
        mes_que_vem = (datetime.now(timezone.utc).date().replace(day=1) + timedelta(days=32)).replace(day=15).isoformat()
        self.post("/api/pagamentos", {"conta": "atlas", "cliente": "D", "valor": "800", "status": "a_receber", "vencimento": mes_que_vem})
        self.post("/api/meta", {"conta": "atlas", "valor": "9000"})
        f = self.get("/api/financeiro?conta=atlas")[1]
        self.assertEqual((f["recebido_mes"], f["a_receber"], f["meta_pct"], f["fechamentos_mes"]), (450000, 80000, 50, 3))
        self.assertEqual(f["ticket_medio"], 150000)                                # (3000+1000+500)/3
        self.assertEqual(len(f["serie"]), 9)                                       # 6 meses passados/atual + 3 futuros
        hoje = next(m for m in f["serie"] if m["mes"] == store.hoje()[:7])
        self.assertEqual(hoje["recebido"], 450000)
        futuro = next(m for m in f["serie"] if m["mes"] == mes_que_vem[:7])
        self.assertEqual((futuro["a_receber"], futuro["futuro"]), (80000, True))
        origens = {o["origem"]: o["valor"] for o in f["origens"]}
        self.assertEqual(origens, {"WhatsApp (Google Maps)": 300000, "WhatsApp (Indicacao)": 100000, "Sem origem informada": 50000})

    def test_sem_dados_nao_inventa(self):
        f = self.get("/api/financeiro?conta=atlas")[1]
        self.assertEqual((f["ticket_medio"], f["meta_pct"], f["fechamentos_mes"], f["origens"]), (None, None, 0, []))


class TestCardsValidacaoEstaticos(BaseCRM):
    def test_proxima_acao_nos_cards(self):
        self.novo_lead(nome="Pronto WA", telefone="(77) 99040-0001")
        c = self.novo_lead(nome="Contatado", telefone="(77) 99040-0002")
        self.post("/api/leads/%d/sent" % c)
        self.novo_lead(nome="Email", canal="email", telefone=None, email="e@x.example")
        wa = self.get("/api/board?conta=atlas&canal=whatsapp")[1]["cards"]
        self.assertEqual(wa["Pronto"][0]["proxima"], "Enviar no WhatsApp")
        self.assertEqual(wa["Contatado"][0]["proxima"], "Follow-up em 3 dias")
        em = self.get("/api/board?conta=atlas&canal=email")[1]["cards"]
        self.assertEqual(em["Pronto"][0]["proxima"], "Aprovar o e-mail")

    def test_validar_copy_via_api(self):
        st, r = self.post("/api/validar", {"conta": "atlas", "canal": "whatsapp", "tipo": "primeiro", "texto": "Oi, aqui é o Enos - trabalho com sites"})
        self.assertEqual(st, 200)
        self.assertTrue(any("me chamo" in v for v in r["violacoes"]))
        st, r = self.post("/api/validar", {"conta": "atlas", "canal": "whatsapp", "tipo": "primeiro", "texto": "Oi, me chamo Enos. Vi que voces nao tem site. Posso te mostrar uma ideia?"})
        self.assertEqual(r["violacoes"], [])
        self.assertEqual(self.post("/api/validar", {"conta": "x"})[0], 400)

    def test_lead_traz_eventos_e_conversa(self):
        lid = self.novo_lead()
        self.post("/api/wa/event", {"direcao": "saida", "telefone": "5577998887766", "texto": "Bom dia"})
        r = self.get("/api/lead?ref=c%d" % lid)[1]
        self.assertEqual([e["para_etapa"] for e in r["eventos"]], ["Pronto", "Contatado"])
        self.assertEqual(r["whatsapp"][0]["texto"], "Bom dia")

    def test_arquivos_estaticos_e_travessia_de_diretorio(self):
        self.assertEqual(self.http("GET", "/js/nao-existe.js")[0], 404)
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        for caminho in ("/js/../server.py", "/js/..%2fserver.py", "/../server.py", "/store.py", "/crm.sqlite3"):
            c.request("GET", caminho)
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 404, caminho)


if __name__ == "__main__":
    import unittest
    unittest.main()
