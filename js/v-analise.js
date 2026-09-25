/* Aprendizado (o que funciona) e Financeiro (dinheiro). Graficos primeiro; sem amostra, "dados insuficientes". Nada e inventado. */
"use strict";

VIEWS.aprendizado = async function (raiz) {
  const tz = -new Date().getTimezoneOffset();
  const [a, p] = await Promise.all([api(`/api/aprendizado?conta=${S.conta}&tz=${tz}`), api(`/api/painel?conta=${S.conta}&dias=${S.dias}`)]);
  cabecalho(raiz, "Aprendizado", "O que está funcionando, com dados reais", el("div", { class: "chips" }, [7, 30, 90].map((d) => el("button", { class: "chip" + (S.dias === d ? " on" : ""), onclick: () => { S.dias = d; renderizar(); } }, d + " dias"))));

  raiz.append(el("div", { class: "kpis tres fade" },
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Envios em 7 dias"), el("div", { class: "num" }, num(a.semana.envios))),
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Respostas novas em 7 dias"), el("div", { class: "num" }, num(a.semana.respostas_novas))),
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Envios rastreados"), el("div", { class: "num" }, num(a.total_envios)))));
  if (S.conta === "nexora") raiz.append(el("div", { class: "note info", style: "margin-top:16px" }, "Na Nexora, envios e respostas vêm do banco original. Horário e dia da semana só contam os envios feitos depois que o CRM começou a registrar."));

  const secao = (titulo, aux, conteudo) => el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, titulo), aux ? el("span", { class: "aux" }, aux) : ""), conteudo);
  const taxaItem = (x, min = 5) => ({ rotulo: x.chave, valor: x.taxa, texto: x.taxa != null ? x.taxa + "% (" + x.respostas + "/" + x.envios + ")" : null, insuficiente: (x.envios ?? x.contatados ?? 0) < min });

  raiz.append(el("div", { class: "grid2e" },
    secao("Conversão por etapa", "de cada etapa para a próxima", p.kpis.leads ? barrasH(p.funil.slice(1).map((f) => ({ rotulo: f.etapa, valor: f.conv, texto: f.conv != null ? f.conv + "% (" + f.n + ")" : null, insuficiente: f.n === 0 && f.conv == null })), { max: 100 }) : vazio("Sem leads ainda")),
    secao("Resposta por canal", "taxa de resposta", a.por_canal.length ? barrasH(a.por_canal.map((x) => taxaItem(x)), { max: 100 }) : vazio("Sem envios registrados"))));

  raiz.append(secao("Resposta por dia", "respostas recebidas no período", p.serie_suficiente ? graficoTempo(p.datas, [{ chave: "respostas", rotulo: "Respostas", valores: p.serie.respostas, cor: cssv("--ok") }, { chave: "contatos", rotulo: "Contatos", valores: p.serie.contatos, cor: cssv("--ac") }])
    : vazio("Dados insuficientes", "Precisa de pelo menos 5 contatos ou respostas no período.")));

  const hora = a.por_hora.filter((h) => h.envios);
  raiz.append(el("div", { class: "grid2e" },
    secao("Resposta por horário", "seu horário local", a.insuficiente_horario ? vazio("Dados insuficientes", "Precisa de pelo menos " + a.amostra_minima + " envios registrados (hoje há " + a.total_envios + ").")
      : barrasV(a.por_hora.map((h) => ({ rotulo: h.chave, valor: h.envios >= 3 && h.taxa != null ? h.taxa : 0, dica: h.envios ? h.taxa + "% de " + h.envios + " envio(s)" : "sem envios" })), { rotulo: "Taxa de resposta por horário" })),
    secao("Resposta por dia da semana", "taxa de resposta", a.insuficiente_horario ? vazio("Dados insuficientes") : barrasV(a.por_dia_semana.map((d) => ({ rotulo: d.chave, valor: d.envios >= 3 && d.taxa != null ? d.taxa : 0, dica: d.envios ? d.taxa + "% de " + d.envios + " envio(s)" : "sem envios" })), { mostrarTodos: true }))));

  raiz.append(el("div", { class: "grid2e" },
    secao("Resposta por dor", "o que abriu a conversa", a.por_dor.length ? barrasH(a.por_dor.map((x) => Object.assign(taxaItem(x), { rotulo: nomeDor(x.chave) })), { max: 100 }) : vazio("Sem envios registrados")),
    secao("Resposta por abordagem", S.conta === "nexora" ? "variação do texto" : "", a.por_abordagem.length ? barrasH(a.por_abordagem.map((x) => ({ rotulo: x.chave, valor: x.taxa, texto: x.taxa != null ? x.taxa + "% (" + x.respostas + "/" + x.contatados + ")" : null, insuficiente: x.insuficiente })), { max: 100 })
      : vazio("Sem variações testadas", S.conta === "atlas" ? "A Atlas ainda não testa versões diferentes da abertura." : ""))));

  raiz.append(secao("Objeções mais frequentes", "das recusas reais", a.objecoes_top.length ? el("div", { class: "list" }, a.objecoes_top.map((o) => el("div", { class: "item", style: "cursor:default" }, el("div", { class: "t1" }, o.motivo), pill("err", o.n + (o.n > 1 ? " vezes" : " vez")))))
    : vazio("Nenhuma recusa registrada", "As recusas classificadas entram aqui automaticamente.")));

  const props = el("div", {});
  if (a.propostas.length) props.append(el("div", { class: "list" }, a.propostas.map((x) => el("div", { class: "item", style: "cursor:default" }, el("div", {}, el("div", { class: "t1" }, x.titulo), el("div", { class: "faint", style: "font-size:12.5px;margin-top:2px" }, "Evidência: " + (x.evidencia || "")), el("div", { class: "t2", style: "-webkit-line-clamp:5" }, x.ajuste)),
    x.status === "pendente" ? el("div", { class: "lado" }, botaoAcao("Rejeitar", async () => { await post(`/api/propostas/${x.id}/rejeitar`); renderizar(); }, "btn sm ghost"), botaoAcao("Aprovar", async () => { await post(`/api/propostas/${x.id}/aprovar`); renderizar(); }, "btn sm")) : pill(x.status === "aprovada" ? "ok" : "", x.status)))));
  else props.append(vazio("Nenhuma proposta ainda", "A IA lê as respostas reais e sugere ajustes nos roteiros. Você aprova."));
  props.append(el("div", { style: "margin-top:14px" }, botaoAcao("Gerar revisão da semana", async () => { await post("/api/aprendizado/revisar", { conta: S.conta }); toast("Revisão iniciada, volte em 2 minutos", "ok"); }, "btn sm sec", "refresh")));
  raiz.append(secao("Ajustes propostos pela IA", "você decide", props));
};

VIEWS.financeiro = async function (raiz) {
  const [f, quadroW, quadroE] = await Promise.all([api(`/api/financeiro?conta=${S.conta}`), api(`/api/board?conta=${S.conta}&canal=whatsapp`).catch(() => ({ cards: {} })), api(`/api/board?conta=${S.conta}&canal=email`).catch(() => ({ cards: {} }))]);
  const m = f.moeda, fmt = (c) => money(c, m);
  cabecalho(raiz, "Financeiro", NOMES[S.conta] + " · " + m);
  raiz.append(el("div", { class: "kpis fade" },
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Receita do mês"), el("div", { class: "num" }, fmt(f.recebido_mes))),
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "A receber"), el("div", { class: "num" }, fmt(f.a_receber))),
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Meta do mês"), el("div", { class: "num" }, f.meta_pct != null ? f.meta_pct + "%" : "—"), el("div", { class: "delta" }, f.meta ? "de " + fmt(f.meta) : "não definida")),
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Ticket médio"), el("div", { class: "num" }, fmt(f.ticket_medio)), el("div", { class: "delta" }, f.ticket_medio == null ? "sem fechamentos" : "")),
    el("div", { class: "kpi" }, el("div", { class: "eyebrow" }, "Fechamentos no mês"), el("div", { class: "num" }, num(f.fechamentos_mes)), el("div", { class: "delta" }, f.fechamentos_total + " no total"))));

  const temDados = f.fechamentos_total > 0 || f.a_receber > 0;
  const secao = (t, aux, c) => el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, t), aux ? el("span", { class: "aux" }, aux) : ""), c);
  raiz.append(el("div", { class: "grid2" },
    secao("Recebido × a receber", "6 meses e os próximos 3", temDados ? el("div", {}, barrasEmpilhadas(f.serie, fmt), el("div", { class: "faint", style: "font-size:12px;margin-top:6px" }, "Barra cheia: recebido. Barra clara: a receber por vencimento.")) : vazio("Nenhum lançamento ainda", "Lance um recebimento abaixo.")),
    secao("Progresso da meta", "", f.meta ? el("div", { style: "display:flex;align-items:center;gap:18px" }, anel(Math.min(f.meta_pct, 100), 96, 8, f.meta_pct + "%"), el("div", {}, el("div", { style: "font-size:20px;font-weight:560" }, fmt(f.recebido_mes)), el("div", { class: "faint" }, "de " + fmt(f.meta)), el("div", { class: "faint", style: "margin-top:6px" }, f.meta > f.recebido_mes ? "Faltam " + fmt(f.meta - f.recebido_mes) : "Meta batida"))) : vazio("Meta não definida", "Defina abaixo."))));

  raiz.append(el("div", { class: "grid2e" },
    secao("Receita por mês", "só o recebido", temDados ? barrasV(f.serie.filter((x) => !x.futuro).map((x) => ({ rotulo: ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][+x.mes.slice(5) - 1], valor: x.recebido, dica: fmt(x.recebido) })), { mostrarTodos: true }) : vazio("Sem receita registrada")),
    secao("Origem dos negócios", "quanto cada origem já trouxe", f.origens.length ? barrasH(f.origens.map((o) => ({ rotulo: o.origem, valor: o.valor, texto: fmt(o.valor) }))) : vazio("Nenhum negócio fechado ainda", "Vincule o pagamento a um lead para ver a origem."))));

  const cli = el("input", { placeholder: "Cliente" }), desc = el("input", { placeholder: "Descrição" }), val = el("input", { placeholder: "Valor", inputmode: "decimal" }), venc = el("input", { type: "date" });
  const stt = el("select", {}, el("option", { value: "a_receber" }, "A receber"), el("option", { value: "pago" }, "Já recebido"));
  const vinc = el("select", {}, el("option", { value: "" }, "Sem vínculo"));
  [...Object.values(quadroW.cards).flat(), ...Object.values(quadroE.cards).flat()].filter((l) => ["Respondeu", "Negociando"].includes(l.etapa)).forEach((l) => vinc.append(el("option", { value: l.ref }, l.nome)));
  raiz.append(secao("Lançar recebimento", "ao marcar como pago um lead vinculado, ele vai para Fechado", el("div", {}, el("div", { class: "inl", style: "grid-template-columns:repeat(auto-fit,minmax(150px,1fr))" }, cli, desc, val, venc, vinc, stt),
    el("div", { style: "margin-top:12px" }, botaoAcao("Salvar lançamento", async () => {
      if (!val.value) return toast("Informe o valor", "err");
      await post("/api/pagamentos", { conta: S.conta, cliente: cli.value, descricao: desc.value, valor: val.value, vencimento: venc.value, status: stt.value, lead_ref: vinc.value });
      toast("Lançamento salvo", "ok"); renderizar();
    }, "btn sm", "plus")))));

  raiz.append(secao("Lançamentos", "", f.pagamentos.length ? el("div", { class: "list" }, f.pagamentos.map((p) => el("div", { class: "item", style: "cursor:default" }, el("div", {}, el("div", { class: "t1" }, p.cliente || "Sem cliente", pill(p.status === "pago" ? "ok" : "warn", p.status === "pago" ? "Pago" : "A receber" + (p.vencimento ? " até " + p.vencimento : ""))), el("div", { class: "t2" }, p.descricao || "")),
    el("div", { class: "lado" }, el("b", {}, fmt(p.valor_centavos)), p.status === "pago" ? "" : botaoAcao("Marcar pago", async () => { await post(`/api/pagamentos/${p.id}/pago`); renderizar(); }, "btn sm sec"))))) : vazio("Nenhum lançamento")));

  const sn = el("input", { placeholder: "Nome do serviço" }), sp = el("input", { placeholder: "Preço", inputmode: "decimal" }), mt = el("input", { placeholder: "Meta do mês", inputmode: "decimal", value: f.meta ? String(f.meta / 100) : "" });
  raiz.append(el("div", { class: "grid2e" },
    secao("Serviços e preços", "", el("div", {}, f.servicos.map((s) => el("div", { class: "sw" }, el("div", { class: "d" }, s.nome), el("b", {}, fmt(s.preco_centavos)))), el("div", { class: "inl", style: "margin-top:12px" }, sn, sp), el("div", { style: "margin-top:10px" }, botaoAcao("Adicionar serviço", async () => { if (!sn.value) return; await post("/api/servicos", { conta: S.conta, nome: sn.value, preco: sp.value }); renderizar(); }, "btn sm sec")))),
    secao("Meta do mês", "", el("div", {}, mt, el("div", { style: "margin-top:10px" }, botaoAcao("Definir meta", async () => { await post("/api/meta", { conta: S.conta, valor: mt.value }); toast("Meta definida", "ok"); renderizar(); }, "btn sm sec"))))));
  raiz.append(el("div", { class: "note info", style: "margin-top:24px" }, "A baixa é manual, com um clique. Detectar pagamento sozinho exige um webhook (Mercado Pago, Asaas ou Stripe) ou a leitura dos e-mails do banco, ainda não ligados."));
};
