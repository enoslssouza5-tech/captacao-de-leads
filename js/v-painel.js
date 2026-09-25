/* Painel: "como esta minha operacao?" em ~5 segundos. So mostra o que existe nos dados. */
"use strict";
const VIEWS = {};

VIEWS.painel = async function (raiz) {
  const p = await api(`/api/painel?conta=${S.conta}&dias=${S.dias}`);
  const k = p.kpis, ser = p.serie;
  cabecalho(raiz, "Painel", `Operação ${NOMES[S.conta]}, últimos ${S.dias} dias`, el("div", { class: "chips" },
    [7, 30, 90].map((d) => el("button", { class: "chip" + (S.dias === d ? " on" : ""), onclick: () => { S.dias = d; renderizar(); } }, d + " dias"))));

  const cartao = (rotulo, valor, serie, tend) => el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, rotulo), el("div", { class: "num" }, num(valor)), tendenciaTxt(tend), spark(serie));
  raiz.append(el("div", { class: "kpis fade" },
    cartao("Leads", k.leads, ser.leads, p.tendencia.leads), cartao("Contatados", k.contatados, ser.contatos, p.tendencia.contatos),
    cartao("Respostas", k.respostas, ser.respostas, p.tendencia.respostas), cartao("Negociações", k.negociacoes, ser.negociacoes, p.tendencia.negociacoes),
    cartao("Fechados", k.fechados, ser.fechamentos, p.tendencia.fechamentos)));
  if (p.parcial) raiz.append(el("div", { class: "note info", style: "margin-top:16px" }, "Na Nexora, o banco original não guarda a data de negociação e fechamento. Esses dois números no gráfico só contam o que o CRM registrou desde que passou a acompanhar."));

  const desempenho = el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, "Desempenho"), el("span", { class: "aux" }, "contatos, respostas, negociações e fechamentos por dia")));
  if (p.serie_suficiente) {
    desempenho.append(graficoTempo(p.datas, [
      { chave: "contatos", rotulo: "Contatos", valores: ser.contatos, cor: cssv("--ac") },
      { chave: "respostas", rotulo: "Respostas", valores: ser.respostas, cor: cssv("--ok") },
      { chave: "negociacoes", rotulo: "Negociações", valores: ser.negociacoes, cor: cssv("--info") },
      { chave: "fechamentos", rotulo: "Fechamentos", valores: ser.fechamentos, cor: cssv("--warn") },
    ], { rotulo: "Desempenho ao longo do tempo" }));
  } else desempenho.append(vazio("Dados insuficientes para o gráfico", "Ele aparece quando houver pelo menos 5 contatos ou respostas no período. Nenhum número é estimado."));
  raiz.append(desempenho);

  const funil = el("div", {}, el("div", { class: "sec-h" }, el("h2", {}, "Funil de conversão"), el("span", { class: "aux" }, "quem já passou por cada etapa")),
    k.leads ? funilFluxo(p.funil) : vazio("Nenhum lead ainda", "Capte leads ou crie o primeiro pelo botão Novo lead."));
  const canais = el("div", {}, el("div", { class: "sec-h" }, el("h2", {}, "Canais"), el("span", { class: "aux" }, "taxa de resposta")),
    barrasH(p.canais.map((c) => ({ rotulo: (c.canal === "whatsapp" ? "WhatsApp" : "E-mail") + " · " + c.contatados, valor: c.taxa, texto: c.taxa != null ? c.taxa + "% (" + c.respostas + " de " + c.contatados + ")" : null, insuficiente: c.insuficiente })), { max: 100 }),
    el("div", { class: "faint", style: "font-size:12px;margin-top:8px" }, "A taxa só aparece com pelo menos 5 contatados no canal."));
  raiz.append(el("div", { class: "sec grid2" }, funil, canais));

  const dores = el("div", {}, el("div", { class: "sec-h" }, el("h2", {}, "Principais dores"), el("span", { class: "aux" }, "o que abriu a conversa")),
    p.dores.length ? barrasH(p.dores.slice(0, 6).map((d) => ({ rotulo: nomeDor(d.dor), valor: d.taxa, texto: d.taxa != null ? d.taxa + "% (" + d.respostas + "/" + d.contatados + ")" : null, insuficiente: d.insuficiente })), { max: 100 })
      : vazio("Sem contatos ainda", "As dores aparecem depois dos primeiros contatos."));
  const r = p.radar, itensRadar = [[r.sem_retorno, "resposta(s) esperando você", "alerta"], [r.esfriando, "lead(s) esfriando", "relogio"], [r.devolvidos, "e-mail(s) devolvido(s)", "email"]].filter((x) => x[0] > 0);
  const atencao = el("div", {}, el("div", { class: "sec-h" }, el("h2", {}, "Precisa de atenção"), el("a", { class: "aux", href: "#/" + S.conta + "/radar" }, "abrir Radar")),
    itensRadar.length ? el("div", { class: "list" }, itensRadar.map(([n, txt]) => el("div", { class: "item", onclick: () => ir("radar") }, el("div", { class: "t1" }, el("b", { style: "font-size:20px;font-weight:540" }, n), el("span", { class: "muted", style: "font-weight:500" }, txt)), icon("arrow"))))
      : vazio("Tudo em dia", "Nada esperando resposta ou esfriando."));
  raiz.append(el("div", { class: "sec grid2e" }, dores, atencao));
};
