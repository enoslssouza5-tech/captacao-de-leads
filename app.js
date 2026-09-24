const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const NOMES = { nexora: "Nexora", atlas: "Atlas" };
const TITULOS = { gmail: "Caixa de e-mail", hoje: "Hoje", captacao: "Captação", radar: "Radar", email: "Funil de e-mail", whatsapp: "Funil de WhatsApp", painel: "Painel", aprendizado: "Aprendizado", financeiro: "Financeiro", modelos: "Modelos e follow-ups", conexoes: "Conexões" };
const CLS = { interessado: ["ok", "Interessado"], duvida: ["info", "Dúvida"], reuniao: ["acc", "Quer conversar"], pendente: ["warn", "Pendente"], recusou: ["err", "Recusou"], automatica: ["info", "Resposta automática"], bounce: ["err", "E-mail devolvido"] };
const st = { conta: localStorage.getItem("crm.conta") || "atlas", view: localStorage.getItem("crm.view") || "hoje", tab: "todos", idx: 0, chip: "todos", ultimaResp: null, conex: null, gm: { pasta: "INBOX", busca: "", sel: null } };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat(Infinity)) if (c !== false && c != null) n.append(c instanceof Node ? c : document.createTextNode(c));
  return n;
}
const api = async (url) => (await fetch(url)).json();
const post = async (url, body = {}) => {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) alert(j.erro || "Erro");
  return j;
};
const q = () => `conta=${st.conta}`;
const money = (cents, moeda) => new Intl.NumberFormat(moeda === "USD" ? "en-US" : "pt-BR", { style: "currency", currency: moeda }).format((cents || 0) / 100);
const scoreEl = (s) => el("span", { class: "score " + (s >= 70 ? "" : s >= 45 ? "m" : "l") }, String(s));
const pill = (k, t) => el("span", { class: "pill " + k }, t);
const clsPill = (c) => (CLS[c] ? pill(CLS[c][0], CLS[c][1]) : pill("warn", "A classificar"));
const dataCurta = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "");
const soma = (o) => Object.values(o || {}).reduce((a, b) => a + b, 0);

/* ---------- HOJE ---------- */
async function viewHoje() {
  const [h, cx] = await Promise.all([api(`/api/hoje?${q()}`), api("/api/conexoes")]);
  st.conex = cx;
  const waOk = cx.whatsapp.estado === "conectado";
  const v = $("#view");
  const tabs = [["todos", "Todos", () => true], ["novos", "Novos contatos", (i) => i.tipo === "primeiro"], ["acomp", "Acompanhamentos", (i) => i.tipo === "followup"], ["resp", "Respostas", () => false]];
  v.append(el("div", { class: "tabs" }, tabs.map(([k, n, f]) => el("button", { class: "tab" + (st.tab === k ? " on" : ""), onclick: () => { st.tab = k; st.idx = 0; render(); } }, n, el("b", {}, k === "resp" ? String(h.stats.respostas_a_classificar || "") : String(h.itens.filter(f).length))))));
  if (!waOk && st.conta === "atlas") v.append(el("div", { class: "note" }, "WhatsApp não conectado: o envio não é detectado sozinho. Conecte em Conexões, ou marque \"Enviei\" manualmente."));
  if (st.tab === "resp") return viewRespostas(v);
  const lista = h.itens.filter(tabs.find((t) => t[0] === st.tab)[2]);
  const side = el("div", { class: "side" },
    el("h4", {}, "Saúde comercial"),
    ...[["Respostas a classificar", h.stats.respostas_a_classificar], ["Follow-ups atrasados", h.stats.followups_atrasados], ["Interessados sem ação", h.stats.interessados_sem_acao]].map(([n, c]) => el("div", { class: "srow" }, n, el("b", {}, String(c)))),
    el("h4", { style: "margin-top:20px" }, "Ritmo do dia"),
    el("div", { class: "grid2" }, el("div", { class: "mini" }, el("small", {}, "Pendentes"), el("b", {}, String(h.stats.pendentes))), el("div", { class: "mini" }, el("small", {}, "WhatsApp hoje"), el("b", {}, `${h.stats.feitos}/${h.stats.cap}`))));
  let work;
  if (!lista.length) work = el("div", { class: "work" }, el("h2", {}, "Nada pendente aqui"), el("p", { class: "sub" }, "A IA está captando e analisando novos leads. Eles aparecem aqui quando a mensagem estiver pronta."));
  else {
    if (st.idx >= lista.length) st.idx = 0;
    const it = lista[st.idx];
    const ehWa = it.canal === "whatsapp";
    const autoEmail = st.conex.config[`auto_followup_email_${st.conta}`] === "1";
    const feito = async () => { it.tipo === "primeiro" ? await post(`/api/leads/${it.lead_id}/sent`) : await post(`/api/tarefas/${it.tarefa_id}/feita`); render(); };
    const acoes = [];
    if (ehWa && it.link) acoes.push(el("a", { class: "btn sm", href: it.link, target: "_blank", rel: "noopener" }, "Abrir no WhatsApp"));
    if (!ehWa && it.tipo === "primeiro") acoes.push(it.aprovado ? pill("ok", "Aprovado, sai automático") : el("button", { class: "btn sm", onclick: async () => { await post(`/api/leads/${it.lead_id}/aprovar`); render(); } }, "Aprovar e enviar"));
    if (!ehWa && it.tipo === "followup") acoes.push(autoEmail ? pill("ok", "Envio automático ligado") : pill("warn", "Envio automático desligado (Conexões)"));
    work = el("div", { class: "work" },
      el("div", { class: "sub" }, `Lead ${st.idx + 1} de ${lista.length}`),
      el("div", { class: "prog" }, el("i", { style: `width:${((st.idx + 1) / lista.length) * 100}%` })),
      el("h2", { style: "cursor:pointer", onclick: () => abrirLead(it.ref) }, it.nome),
      el("div", { class: "sub" }, [it.sub, it.telefone, it.email].filter(Boolean).join(" · ")),
      el("div", { style: "margin:8px 0" },
        pill(it.tipo === "primeiro" ? "acc" : it.atrasado ? "err" : "warn", it.tipo === "primeiro" ? "Primeiro contato" : it.atrasado ? "Follow-up atrasado" : "Follow-up de hoje"),
        " ", pill("info", ehWa ? "WhatsApp" : "E-mail"), it.ia ? [" ", pill("ok", "Adaptado por IA")] : "", it.score ? [" ", scoreEl(it.score)] : ""),
      it.dor ? el("div", { class: "sub" }, "Dor: " + it.dor) : "",
      it.assunto ? el("div", { class: "sub" }, "Assunto: " + it.assunto) : "",
      el("div", { class: "msgbox" }, it.mensagem || "(sem mensagem)"),
      el("div", { class: "actions" },
        it.tipo === "primeiro" && ehWa ? el("button", { class: "btn ghost sm", onclick: async () => { await post(`/api/leads/${it.lead_id}/sem_whatsapp`); render(); } }, "Sem WhatsApp") : "",
        it.tipo === "primeiro" ? el("button", { class: "btn danger sm", onclick: async () => { await post(`/api/leads/${it.lead_id}/descartar`); render(); } }, "Descartar") : "",
        el("div", { class: "grow" },
          el("button", { class: "btn ghost sm", onclick: () => { st.idx = (st.idx + 1) % lista.length; render(); } }, "Pular"),
          el("button", { class: "btn ghost sm", onclick: () => navigator.clipboard.writeText(it.mensagem || "") }, "Copiar"),
          ...acoes,
          (ehWa && !waOk) || (!ehWa && it.tipo === "followup" && !autoEmail) ? el("button", { class: "btn ghost sm", onclick: feito }, "Enviei") : ""),
      ),
      ehWa && waOk ? el("div", { class: "sub", style: "margin-top:10px" }, "Ao enviar, o CRM detecta sozinho e agenda os follow-ups.") : "");
  }
  v.append(el("div", { class: "split" }, work, side));
}

async function viewRespostas(v) {
  const [r, e] = await Promise.all([api(`/api/board?${q()}&canal=whatsapp`), api(`/api/board?${q()}&canal=email`)]);
  const todos = [...Object.values(r.cards).flat(), ...Object.values(e.cards).flat()];
  const leads = todos.filter((l) => !l.readonly && ["Contatado", "Respondeu", "Negociando"].includes(l.etapa));
  const lista = todos.filter((l) => ["Respondeu", "Negociando", "Perdido"].includes(l.etapa));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Respostas recentes (detectadas sozinhas)"),
    lista.length ? lista.slice(0, 20).map((l) => el("div", { class: "srow", style: "cursor:pointer", onclick: () => abrirLead(l.ref || l.id) }, el("span", {}, l.nome), pill("info", l.etapa))) : el("div", { class: "empty" }, "Nenhuma resposta ainda. Elas aparecem aqui e o card muda de coluna sozinho.")));
  const sel = el("select", {}, leads.length ? leads.map((l) => el("option", { value: l.id.replace("c", "") }, `${l.nome} (${l.canal})`)) : el("option", { value: "" }, "Nenhum lead contatado"));
  const txt = el("textarea", { placeholder: "Só use se a resposta chegou por outro canal" });
  v.append(el("details", { class: "panel" }, el("summary", {}, "Registrar resposta manualmente"), el("label", {}, "Lead", sel), el("label", {}, "Resposta", txt),
    el("div", { class: "row" }, el("button", { class: "btn", onclick: async () => { if (!sel.value || !txt.value.trim()) return; await post(`/api/leads/${sel.value}/resposta`, { texto: txt.value }); txt.value = ""; render(); } }, "Classificar com IA"))));
}

/* ---------- LEAD (dialog) ---------- */
async function abrirLead(ref) {
  const r = await api(`/api/lead?ref=${encodeURIComponent(ref)}`);
  if (!r.lead) return;
  const l = r.lead;
  let crit = [];
  try { crit = JSON.parse(l.criterios_json || "{}").criterios || []; } catch (e) { crit = []; }
  const body = $("#leadBody");
  body.replaceChildren(
    el("h3", { style: "margin:0" }, l.nome),
    el("div", { class: "sub", style: "color:var(--subtle)" }, [l.cidade || l.sub, l.telefone, l.email, l.site].filter(Boolean).join(" · ")),
    el("div", { style: "margin:8px 0" }, pill("acc", l.etapa), " ", pill("info", l.canal === "whatsapp" ? "WhatsApp" : "E-mail"), l.score != null ? [" ", scoreEl(l.score)] : "", l.tipo_dor ? [" ", pill("warn", l.tipo_dor)] : ""),
    l.dor ? el("div", { class: "panel" }, el("h3", {}, "Dor identificada"), l.dor, crit.length ? el("table", { style: "margin-top:10px" }, el("tbody", {}, crit.map((c) => el("tr", {}, el("td", {}, c.criterio || ""), el("td", {}, c.achado || ""), el("td", {}, pill(c.impacto === "alto" ? "err" : c.impacto === "medio" ? "warn" : "info", c.impacto || ""))))) ) : "") : "",
    l.mensagem || l.nota ? el("div", { class: "panel" }, el("h3", {}, "Mensagem"), el("div", { class: "msgbox", style: "margin:0" }, l.mensagem || l.nota)) : "",
    r.respostas.length ? el("div", { class: "panel" }, el("h3", {}, "Respostas"), r.respostas.map((x) => el("div", { style: "margin-bottom:10px" }, clsPill(x.classificacao), " ", el("small", { style: "color:var(--subtle)" }, `${dataCurta(x.created_at)} via ${x.origem}`),
      el("div", { class: "msgbox", style: "margin:6px 0" }, x.texto), x.traducao && x.traducao !== x.texto ? el("div", { class: "sub", style: "color:var(--muted)" }, "Tradução: " + x.traducao) : "", x.resumo ? el("div", { class: "sub", style: "color:var(--subtle)" }, x.resumo) : ""))) : "",
    r.tarefas.length ? el("div", { class: "panel" }, el("h3", {}, "Follow-ups"), r.tarefas.map((t) => el("div", { class: "srow" }, el("span", {}, `Passo ${t.passo}, ${t.due_date}`), pill(t.status === "feita" ? "ok" : t.status === "pendente" ? "warn" : "info", t.status)))) : "",
    el("div", { class: "row" },
      !l.readonly && ref.startsWith("c") ? el("button", { class: "btn ghost", onclick: async () => { await post(`/api/leads/${ref.slice(1)}/analisar`); body.append(el("div", { class: "note" }, "Análise iniciada, leva alguns minutos. Reabra o lead depois.")); } }, "Analisar dor com IA") : "",
      el("button", { class: "btn", onclick: () => $("#dlgLead").close() }, "Fechar")));
  $("#dlgLead").showModal();
}

/* ---------- FUNIS ---------- */
function card(l) {
  const c = el("div", { class: "card", draggable: l.readonly ? "false" : "true", onclick: () => abrirLead(l.ref || l.id) },
    el("p", {}, l.nome), l.sub ? el("small", {}, l.sub) : "", l.nota ? el("small", {}, l.nota) : "",
    el("div", { class: "row2" }, l.score != null ? scoreEl(l.score) : "", l.tag ? pill("info", l.tag) : "", l.aprovado ? pill("ok", "aprovado") : ""));
  if (!l.readonly) c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", String((l.id + "").replace("c", ""))));
  return c;
}
async function viewFunil(canal) {
  const b = await api(`/api/board?${q()}&canal=${canal}`);
  const v = $("#view");
  if (b.readonly) v.append(el("div", { class: "note" }, "Funil de e-mail da Nexora: as respostas movem os cards sozinhas (lidas do Gmail). A aprovação e o envio do primeiro e-mail continuam no painel antigo (localhost:4318)."));
  const wrap = el("div", { class: "board" });
  for (const etapa of b.etapas) {
    const cards = b.cards[etapa] || [];
    const col = el("div", { class: "col" }, el("h3", {}, etapa, el("span", {}, String(cards.length))), el("div", { class: "cards" }, cards.length ? cards.slice(0, 60).map(card) : el("div", { class: "empty" }, "Nenhum lead")));
    if (!b.readonly) {
      col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("over"); });
      col.addEventListener("dragleave", () => col.classList.remove("over"));
      col.addEventListener("drop", async (e) => { e.preventDefault(); await post(`/api/leads/${e.dataTransfer.getData("text/plain")}/editar`, { etapa }); render(); });
    }
    wrap.append(col);
  }
  v.append(wrap);
}

/* ---------- CAPTAÇÃO ---------- */
async function viewCaptacao() {
  const leads = await api(`/api/captacao?${q()}`);
  const filtros = [["todos", "Todos", () => true], ["semsite", "Sem site", (l) => (l.sinais || []).some((s) => s.startsWith("sem "))], ["tel", "Com telefone", (l) => (l.sinais || []).includes("com telefone") || l.telefone], ["alta", "Oportunidade 70+", (l) => l.score >= 70]];
  const v = $("#view");
  v.append(el("details", { class: "panel" }, el("summary", { style: "cursor:pointer;font-weight:700" }, "Como ler esta tabela"),
    el("p", {}, el("b", {}, "Empresa: "), "o lead captado, com cidade e origem. "), el("p", {}, el("b", {}, "Avaliações: "), "quantas avaliações públicas a empresa tem no Google. Muitas avaliações mostram que a empresa já tem clientes e reputação. "),
    el("p", {}, el("b", {}, "Sinais: "), "os problemas achados, como sem site ou landing com problema. "),
    el("p", {}, el("b", {}, "Oportunidade (0 a 100): "), "nota de prioridade. Sobe quando há muitas avaliações (reputação forte) e a presença digital é fraca (sem site, ou site ruim). O lead 90 é aquele em que a empresa já é bem falada mas perde cliente por falta de página."),
    el("p", {}, el("b", {}, "Status: "), "Novo aguarda análise, Pronto tem mensagem escrita e entra na fila de Hoje. "),
    el("p", {}, "A IA analisa a dor de cada lead Novo sozinha. Use Abordar só se quiser escrever a mensagem à mão.")));
  v.append(el("div", { class: "chips" }, filtros.map(([k, n]) => el("button", { class: "chip" + (st.chip === k ? " on" : ""), onclick: () => { st.chip = k; render(); } }, n))));
  const rows = leads.filter(filtros.find((x) => x[0] === st.chip)[2]);
  v.append(el("table", {}, el("thead", {}, el("tr", {}, ["Empresa", "Avaliações", "Sinais", "Oportunidade", "Status", ""].map((h) => el("th", {}, h)))),
    el("tbody", {}, rows.length ? rows.slice(0, 200).map((l) => el("tr", { style: "cursor:pointer", onclick: () => abrirLead(l.ref || l.id) },
      el("td", {}, el("b", {}, l.nome), el("div", { class: "empty", style: "padding:0" }, [l.sub, l.tag].filter(Boolean).join(" · "))),
      el("td", {}, l.avaliacoes != null ? String(l.avaliacoes) : "sem dado"),
      el("td", {}, (l.sinais || []).map((s) => el("span", { class: "pill warn", style: "margin-right:4px" }, s))),
      el("td", {}, scoreEl(l.score)),
      el("td", {}, pill(l.etapa === "Pronto" ? "ok" : "info", l.etapa === "Novo" ? (l.dor ? "Analisado" : "Novo, aguardando IA") : l.etapa)),
      el("td", {}, l.readonly ? "" : !l.dor ? el("button", { class: "btn sm ghost", onclick: async (e) => { e.stopPropagation(); await post(`/api/leads/${(l.id + "").slice(1)}/analisar`); e.target.textContent = "Analisando..."; } }, "Analisar agora") : "")))
      : el("tr", {}, el("td", { colspan: "6", class: "empty" }, "Nenhum lead ainda. Use Captar leads no topo, ou ligue a captação diária em Conexões.")))));
}

/* ---------- RADAR ---------- */
async function viewRadar() {
  const r = await api(`/api/radar?${q()}`);
  const bloco = (titulo, dica, itens, quando) => el("div", { class: "panel" }, el("h3", {}, titulo), el("div", { class: "sub", style: "color:var(--subtle);margin-bottom:8px" }, dica),
    itens.length ? itens.slice(0, 30).map((i) => el("div", { class: "srow", style: "cursor:pointer", onclick: () => abrirLead(i.ref) }, el("span", {}, i.nome), el("span", { style: "color:var(--subtle)" }, quando + " " + dataCurta(i.desde)))) : el("div", { class: "empty" }, "Nada por aqui."));
  $("#view").append(bloco("Responderam e estão sem retorno seu", "Mais de 24 horas sem ação sua. É onde o dinheiro está.", r.sem_retorno, "desde"),
    bloco("Esfriando", "Sequência de follow-up concluída sem resposta há mais de 14 dias.", r.esfriando, "contatado em"),
    bloco("E-mails devolvidos", "Endereços que não existem. Já foram bloqueados.", r.devolvidos, "em"));
}

/* ---------- PAINEL ---------- */
async function viewPainel() {
  const s = await api(`/api/stats?${q()}`);
  const kpi = (n, t) => el("div", { class: "kpi" }, el("small", {}, t), el("b", {}, String(n)));
  $("#view").append(el("div", { class: "kpis" }, kpi(soma(s.email), "Leads no funil de e-mail"), kpi(soma(s.whatsapp), "Leads no funil de WhatsApp"), kpi(`${s.whatsapp_hoje}/${s.wa_cap}`, "WhatsApp hoje"), kpi(`${s.email_hoje}/${s.email_cap}`, "E-mails hoje"),
    kpi(s.respostas.interessado || 0, "Interessados"), kpi(s.respostas.reuniao || 0, "Querem conversar"), kpi(s.respostas.recusou || 0, "Recusas"), kpi(s.respostas.duvida || 0, "Dúvidas")));
  const radar = await api(`/api/radar?${q()}`);
  const etapas = ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"];
  const tot = Object.fromEntries(etapas.map((e) => [e, (s.email[e] || 0) + (s.whatsapp[e] || 0)]));
  const max = Math.max(1, ...Object.values(tot));
  const avisos = [];
  if (radar.sem_retorno.length) avisos.push(`${radar.sem_retorno.length} lead(s) responderam e estão há mais de 24 horas sem retorno seu. É onde está o dinheiro: abra o Radar.`);
  if (radar.esfriando.length) avisos.push(`${radar.esfriando.length} lead(s) concluíram a sequência de follow-up sem resposta.`);
  if (radar.devolvidos.length) avisos.push(`${radar.devolvidos.length} e-mail(s) devolvidos foram bloqueados automaticamente.`);
  $("#view").append(
    avisos.length ? el("div", { class: "insight" }, el("b", {}, "Atenção agora"), avisos.map((a) => el("div", {}, a))) : "",
    el("div", { class: "panel" }, el("h3", {}, "Funil geral (e-mail + WhatsApp)"),
      el("div", { class: "funnel" }, etapas.map((e) => el("div", { class: "fr" }, el("span", {}, e), el("div", { class: "fb", style: `width:${Math.max(2, (tot[e] / max) * 100)}%` }), el("b", {}, String(tot[e])))))));
}

/* ---------- APRENDIZADO ---------- */
async function viewAprendizado() {
  const a = await api(`/api/aprendizado?${q()}`);
  const v = $("#view");
  const tabela = (titulo, linhas) => el("div", { class: "panel" }, el("h3", {}, titulo),
    linhas.length ? el("table", {}, el("thead", {}, el("tr", {}, ["", "Envios", "Respostas", "Interessados", "Taxa de resposta"].map((h) => el("th", {}, h)))),
      el("tbody", {}, linhas.map((x) => el("tr", {}, el("td", {}, x.chave), el("td", {}, String(x.envios)), el("td", {}, String(x.respostas)), el("td", {}, String(x.interessados)), el("td", {}, `${x.taxa}%`, el("div", { class: "bar" }, el("i", { style: `width:${Math.min(100, x.taxa)}%` }))))))) : el("div", { class: "empty" }, "Ainda sem envios registrados."));
  v.append(el("div", { class: "kpis" }, el("div", { class: "kpi" }, el("small", {}, "Envios nos últimos 7 dias"), el("b", {}, String(a.semana.envios))), el("div", { class: "kpi" }, el("small", {}, "Respostas novas na semana"), el("b", {}, String(a.semana.respostas_novas)))));
  v.append(tabela("Por canal", a.por_canal), tabela("Por tipo de dor usada na abertura", a.por_dor), tabela("Por hora de envio", a.por_hora));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Ajustes propostos pela IA (você aprova)"),
    a.propostas.length ? a.propostas.map((p) => el("div", { class: "srow", style: "display:block" }, el("b", {}, p.titulo), el("div", { class: "sub", style: "color:var(--subtle)" }, "Evidência: " + (p.evidencia || "")), el("div", {}, p.ajuste),
      p.status === "pendente" ? el("div", { class: "row", style: "margin-top:6px" }, el("button", { class: "btn sm ghost", onclick: async () => { await post(`/api/propostas/${p.id}/rejeitar`); render(); } }, "Rejeitar"), el("button", { class: "btn sm", onclick: async () => { await post(`/api/propostas/${p.id}/aprovar`); render(); } }, "Aprovar")) : pill(p.status === "aprovada" ? "ok" : "info", p.status))) : el("div", { class: "empty" }, "Nenhuma proposta ainda."),
    el("div", { class: "row" }, el("button", { class: "btn", onclick: async (e) => { e.target.disabled = true; await post("/api/aprendizado/revisar", { conta: st.conta }); e.target.textContent = "Gerando, volte em 2 minutos"; } }, "Gerar revisão da semana"))));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Biblioteca de objeções (recusas reais)"),
    a.objecoes.length ? a.objecoes.map((o) => el("div", { class: "srow", style: "display:block" }, el("div", {}, o.traducao || o.texto), el("small", { style: "color:var(--subtle)" }, `${o.resumo || ""} ${dataCurta(o.created_at)}`))) : el("div", { class: "empty" }, "As recusas classificadas entram aqui automaticamente.")));
}

/* ---------- FINANCEIRO ---------- */
async function viewFinanceiro() {
  const f = await api(`/api/financeiro?${q()}`);
  const board = await api(`/api/board?${q()}&canal=whatsapp`);
  const m = f.moeda, v = $("#view");
  const pct = f.meta ? Math.min(100, (f.recebido_mes / f.meta) * 100) : 0;
  v.append(el("div", { class: "kpis" },
    el("div", { class: "kpi" }, el("small", {}, "Recebido no mês"), el("b", {}, money(f.recebido_mes, m)), el("div", { class: "bar" }, el("i", { style: `width:${pct}%` })), el("small", {}, f.meta ? `Meta ${money(f.meta, m)}` : "Sem meta definida")),
    el("div", { class: "kpi" }, el("small", {}, "A receber"), el("b", {}, money(f.a_receber, m)))));
  const cli = el("input", { placeholder: "Cliente" }), desc = el("input", { placeholder: "Descrição" }), val = el("input", { placeholder: "Valor", inputmode: "decimal" }), venc = el("input", { type: "date" });
  const vinc = el("select", {}, el("option", { value: "" }, "Sem vínculo"), Object.values(board.cards).flat().filter((l) => ["Negociando", "Respondeu"].includes(l.etapa)).map((l) => el("option", { value: l.ref }, l.nome)));
  const st_ = el("select", {}, el("option", { value: "a_receber" }, "A receber"), el("option", { value: "pago" }, "Já recebido"));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Lançar recebimento"), el("div", { class: "inline" }, cli, desc, val, venc, vinc, st_,
    el("button", { class: "btn", onclick: async () => { if (!val.value) return; await post("/api/pagamentos", { conta: st.conta, cliente: cli.value, descricao: desc.value, valor: val.value, vencimento: venc.value, status: st_.value, lead_ref: vinc.value }); render(); } }, "Salvar")),
    el("div", { class: "sub", style: "color:var(--subtle);margin-top:8px" }, "Ao marcar como pago um lead vinculado, o card vai para Fechado sozinho.")));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Recebimentos"), el("table", {}, el("thead", {}, el("tr", {}, ["Cliente", "Descrição", "Valor", "Situação", ""].map((h) => el("th", {}, h)))),
    el("tbody", {}, f.pagamentos.length ? f.pagamentos.map((p) => el("tr", {}, el("td", {}, p.cliente || ""), el("td", {}, p.descricao || ""), el("td", {}, money(p.valor_centavos, m)),
      el("td", {}, pill(p.status === "pago" ? "ok" : "warn", p.status === "pago" ? "Pago" : "A receber" + (p.vencimento ? " até " + p.vencimento : ""))),
      el("td", {}, p.status === "pago" ? "" : el("button", { class: "btn sm ghost", onclick: async () => { await post(`/api/pagamentos/${p.id}/pago`); render(); } }, "Marcar pago")))) : el("tr", {}, el("td", { colspan: "5", class: "empty" }, "Nenhum lançamento ainda."))))));
  const sn = el("input", { placeholder: "Nome do serviço" }), sp = el("input", { placeholder: "Preço", inputmode: "decimal" }), mt = el("input", { placeholder: "Meta do mês", inputmode: "decimal" });
  v.append(el("div", { class: "panel" }, el("h3", {}, "Serviços e preços"), f.servicos.map((s) => el("div", { class: "srow" }, s.nome, el("b", {}, money(s.preco_centavos, m)))),
    el("div", { class: "inline", style: "margin-top:10px" }, sn, sp, el("button", { class: "btn ghost", onclick: async () => { if (!sn.value) return; await post("/api/servicos", { conta: st.conta, nome: sn.value, preco: sp.value }); render(); } }, "Adicionar serviço")),
    el("div", { class: "inline", style: "margin-top:14px" }, mt, el("button", { class: "btn ghost", onclick: async () => { await post("/api/meta", { conta: st.conta, valor: mt.value }); render(); } }, "Definir meta do mês"))));
  v.append(el("div", { class: "note" }, "Baixa automática de pagamento ainda não está ligada: lance aqui com um clique. Ao vincular a um lead, ele vai para Fechado."));
}

/* ---------- MODELOS ---------- */
async function viewModelos() {
  const r = await api(`/api/modelos?${q()}`);
  const v = $("#view");
  v.append(el("div", { class: "note" }, "Estes são os textos padrão. Perto do vencimento, a IA reescreve cada follow-up adaptado à dor e ao histórico do lead, e o texto adaptado é o que vai valer. Use {nome} para o nome da empresa."));
  for (const m of r.modelos) {
    const ta = el("textarea", {}); ta.value = m.texto;
    v.append(el("div", { class: "panel" }, el("h3", {}, `Follow-up ${m.passo}: ${r.dias[m.passo - 1]} dias depois`), ta,
      el("div", { class: "row" }, el("button", { class: "btn", onclick: async () => { await post("/api/modelos", { conta: st.conta, passo: m.passo, texto: ta.value }); } }, "Salvar"))));
  }
}

/* ---------- CONEXÕES ---------- */
async function viewConexoes() {
  const cx = await api("/api/conexoes");
  const v = $("#view");
  const wa = cx.whatsapp;
  const cfg = async (chave, valor) => { await post("/api/config", { chave, valor }); render(); };
  v.append(el("div", { class: "panel" }, el("h3", {}, "WhatsApp (somente leitura)"),
    el("p", {}, "Estado: ", pill(wa.estado === "conectado" ? "ok" : wa.estado === "qr" ? "warn" : "info", wa.estado), wa.motivo ? " " + wa.motivo : ""),
    wa.qr ? el("div", {}, el("img", { src: wa.qr, alt: "QR do WhatsApp", style: "width:240px;background:#fff;padding:8px;border-radius:8px" }), el("p", { class: "sub" }, "No celular: WhatsApp, Aparelhos conectados, Conectar aparelho.")) : "",
    el("p", { style: "color:var(--subtle)" }, "O CRM só observa: detecta o que você enviou e as respostas dos seus leads. Ele nunca envia mensagem e ignora conversas de números que não são leads. Isso usa o WhatsApp Web de forma não oficial, então há um risco pequeno de restrição pela plataforma. Por isso o envio segue manual e limitado."),
    el("div", { class: "row" }, wa.estado === "parado" || wa.estado === "erro" || wa.estado === "desconectado" ? el("button", { class: "btn", onclick: async () => { await post("/api/wa/start"); setTimeout(render, 1500); } }, "Conectar WhatsApp") : el("button", { class: "btn ghost", onclick: async () => { await post("/api/wa/stop"); render(); } }, "Desconectar"))));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Gmail"),
    ...["nexora", "atlas"].map((c) => el("div", { class: "srow" }, el("span", {}, `${NOMES[c]}: ${cx.gmail[c].endereco || "não configurado"}`),
      el("span", {}, cx.gmail[c].configurado ? pill("ok", "lendo respostas") : pill("warn", c === "atlas" ? "rode py crm/atlas_gmail_auth.py" : "não configurado"), " ",
        cx.gmail[c].configurado ? el("button", { class: "btn sm ghost", onclick: async () => { await post("/api/gmail/sync", { conta: c }); } }, "Ler agora") : ""))),
    el("p", { style: "color:var(--subtle);margin-top:10px" }, "As respostas são lidas a cada 5 minutos, classificadas por IA local, traduzidas e o card muda de coluna sozinho. Pedidos de descadastro e e-mails devolvidos bloqueiam o contato automaticamente.")));
  const sw = (chave, rotulo, desc) => el("div", { class: "srow" }, el("span", {}, el("b", {}, rotulo), el("div", { class: "sub", style: "color:var(--subtle)" }, desc)),
    el("button", { class: "btn sm " + (cx.config[chave] === "1" ? "" : "ghost"), onclick: () => cfg(chave, cx.config[chave] === "1" ? "0" : "1") }, cx.config[chave] === "1" ? "Ligado" : "Desligado"));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Automações"),
    sw("auto_followup_email_nexora", "Follow-up de e-mail da Nexora", "Envia D+3, D+7 e D+14 sozinho, dentro do teto de 20 por dia, parando quando o lead responde ou pede para sair."),
    sw("auto_followup_email_atlas", "Follow-up de e-mail da Atlas", "Igual, quando o Gmail da Atlas estiver conectado."),
    sw("auto_analisar", "Análise de dor automática", "A IA analisa cada lead novo (site, avaliações, concorrentes) e escreve a abordagem.")));
  let capt = {};
  try { capt = JSON.parse(cx.config.captar_atlas || "{}"); } catch (e) { capt = {}; }
  const cid = el("textarea", { placeholder: "Uma cidade por linha" }); cid.value = (capt.cidades || []).join("\n");
  const cat = el("input", { value: capt.categoria || "locação de equipamentos para construção" }), qtd = el("input", { type: "number", value: capt.quantidade || 10 });
  v.append(el("div", { class: "panel" }, el("h3", {}, "Captação diária da Atlas"),
    el("div", { class: "sub", style: "color:var(--subtle)" }, "Uma cidade por dia, rotacionando a lista. A Nexora já capta todo dia pela rotina agendada do Windows. Usa a cota gratuita do Apify, então mantenha a quantidade baixa."),
    el("label", {}, "Cidades", cid), el("div", { class: "inline" }, el("label", {}, "Categoria", cat), el("label", {}, "Leads por dia", qtd)),
    el("div", { class: "row" }, el("button", { class: "btn ghost", onclick: () => cfg("captar_atlas", JSON.stringify({ ...capt, cidades: cid.value.split("\n").map((s) => s.trim()).filter(Boolean), categoria: cat.value, quantidade: Number(qtd.value), ativo: false })) }, "Salvar e deixar desligada"),
      el("button", { class: "btn", onclick: () => cfg("captar_atlas", JSON.stringify({ ...capt, cidades: cid.value.split("\n").map((s) => s.trim()).filter(Boolean), categoria: cat.value, quantidade: Number(qtd.value), ativo: true })) }, capt.ativo ? "Atualizar (ligada)" : "Salvar e ligar"))));
  v.append(el("div", { class: "panel" }, el("h3", {}, "Últimas tarefas automáticas"),
    cx.jobs.length ? cx.jobs.map((j) => el("div", { class: "srow" }, el("span", {}, `${j.tipo} (${j.conta}): ${j.detalhe || ""}`), pill(j.status === "ok" ? "ok" : j.status === "erro" ? "err" : "warn", j.status))) : el("div", { class: "empty" }, "Nada executado ainda.")));
}

/* ---------- CASCA ---------- */
async function render() {
  document.body.dataset.conta = st.conta;
  $$("#tenant button").forEach((b) => b.classList.toggle("on", b.dataset.c === st.conta));
  $$(".nav[data-v]").forEach((b) => b.classList.toggle("on", b.dataset.v === st.view));
  $("#ttl").textContent = TITULOS[st.view];
  $("#sub").textContent = NOMES[st.conta];
  $("#btnNovo").hidden = !["hoje", "captacao", "whatsapp", "email"].includes(st.view) || (st.conta === "nexora" && st.view === "email");
  $("#btnCaptar").hidden = st.view !== "captacao";
  $("#view").replaceChildren();
  const fn = { gmail: viewGmail, hoje: viewHoje, captacao: viewCaptacao, radar: viewRadar, email: () => viewFunil("email"), whatsapp: () => viewFunil("whatsapp"), painel: viewPainel, aprendizado: viewAprendizado, financeiro: viewFinanceiro, modelos: viewModelos, conexoes: viewConexoes }[st.view];
  await fn();
  const [s, h, cap, cx] = await Promise.all([api(`/api/stats?${q()}`), api(`/api/hoje?${q()}`), api(`/api/captacao?${q()}`), api("/api/conexoes")]);
  $("#n-email").textContent = soma(s.email) || "";
  $("#n-whatsapp").textContent = soma(s.whatsapp) || "";
  $("#n-hoje").textContent = h.stats.pendentes || "";
  $("#n-captacao").textContent = cap.length || "";
  $("#n-conexoes").textContent = cx.whatsapp.estado === "conectado" ? "" : "!";
}

$$("#tenant button").forEach((b) => b.addEventListener("click", () => { st.conta = b.dataset.c; localStorage.setItem("crm.conta", st.conta); st.idx = 0; render(); }));
$$(".nav[data-v]").forEach((b) => b.addEventListener("click", () => { st.view = b.dataset.v; localStorage.setItem("crm.view", st.view); render(); }));
$("#theme").addEventListener("click", () => { const d = document.documentElement; const n = d.dataset.theme === "light" ? "dark" : "light"; d.dataset.theme = n; localStorage.setItem("crm.theme", n); });
document.documentElement.dataset.theme = localStorage.getItem("crm.theme") || "dark";
$("#btnNovo").addEventListener("click", () => { $("#form").canal.value = st.view === "email" ? "email" : "whatsapp"; $("#dlg").showModal(); });
$("#btnCaptar").addEventListener("click", () => $("#dlgCaptar").showModal());
$("#cancel").addEventListener("click", () => $("#dlg").close());
$("#cancelCaptar").addEventListener("click", () => $("#dlgCaptar").close());
$("#form").addEventListener("submit", async () => {
  const d = Object.fromEntries(new FormData($("#form")));
  d.avaliacoes = d.avaliacoes ? Number(d.avaliacoes) : null;
  await post("/api/leads", { ...d, conta: st.conta, etapa: "Novo" });
  $("#form").reset(); render();
});
$("#formCaptar").addEventListener("submit", async () => {
  const d = Object.fromEntries(new FormData($("#formCaptar")));
  await post("/api/captar", { ...d, quantidade: Number(d.quantidade), conta: st.conta });
  alert("Captação iniciada em segundo plano. Os leads novos aparecem aqui e a IA analisa cada um sozinha.");
});

/* notificação e atualização automática quando chega resposta */
async function pulso() {
  try {
    const p = await api("/api/ping");
    if (st.ultimaResp !== null && p.ultima_resposta > st.ultimaResp) {
      const cl = p.ultima && CLS[p.ultima.classificacao] ? CLS[p.ultima.classificacao][1] : "nova resposta";
      if ("Notification" in window && Notification.permission === "granted") new Notification("CRM: " + cl, { body: (p.ultima && p.ultima.texto || "").slice(0, 120) });
      if (!["conexoes", "modelos", "financeiro"].includes(st.view) && !document.querySelector("dialog[open]")) render();
    }
    st.ultimaResp = p.ultima_resposta;
  } catch (e) { /* servidor reiniciando */ }
}
document.addEventListener("click", () => { if ("Notification" in window && Notification.permission === "default") Notification.requestPermission(); }, { once: true });
setInterval(pulso, 15000);
pulso();
render();
