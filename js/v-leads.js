/* Leads: funil (kanban compacto), captacao (lista visual com oportunidade) e gaveta de detalhes do lead. */
"use strict";
const ETAPAS = ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"];
const LF = { canal: "todos", busca: "", chip: "todos" };

VIEWS.leads = async function (raiz) {
  const sub = S.sub === "captacao" ? "captacao" : "funil";
  const acoes = [botaoAcao("Novo lead", novoLead, "btn sm", "plus"), botaoAcao("Captar", captarDialog, "btn sm sec", "search")];
  cabecalho(raiz, "Leads", NOMES[S.conta], el("div", { style: "display:flex;gap:8px;align-items:center" }, acoes));
  raiz.append(el("div", { class: "tabs" }, [["funil", "Funil"], ["captacao", "Captação"]].map(([k, r]) => el("button", { class: "tab" + (sub === k ? " on" : ""), onclick: () => ir("leads", k === "funil" ? "" : k) }, r))));
  if (sub === "funil") await funil(raiz); else await captacao(raiz);
};

async function funil(raiz) {
  const [wa, em] = await Promise.all([api(`/api/board?conta=${S.conta}&canal=whatsapp`), api(`/api/board?conta=${S.conta}&canal=email`)]);
  const todos = {};
  ETAPAS.forEach((e) => { todos[e] = [...(wa.cards[e] || []).map((c) => Object.assign(c, { canal: "whatsapp" })), ...(em.cards[e] || []).map((c) => Object.assign(c, { canal: "email" }))]; });
  const busca = el("input", { placeholder: "Buscar empresa", value: LF.busca, style: "max-width:240px" });
  busca.addEventListener("input", () => { LF.busca = busca.value; pintar(); });
  raiz.append(el("div", { style: "display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap;align-items:center" },
    el("div", { class: "chips" }, [["todos", "Todos"], ["email", "E-mail"], ["whatsapp", "WhatsApp"]].map(([k, r]) => el("button", { class: "chip" + (LF.canal === k ? " on" : ""), onclick: () => { LF.canal = k; renderizar(); } }, r))), busca));
  if (S.conta === "nexora") raiz.append(el("div", { class: "note info" }, "E-mails da Nexora: aprovação e envio agora acontecem na tela Hoje. As respostas movem os cards sozinhas."));
  const quadro = el("div", { class: "board fade" });
  raiz.append(quadro);
  function pintar() {
    quadro.replaceChildren();
    for (const etapa of ETAPAS) {
      const cards = todos[etapa].filter((c) => (LF.canal === "todos" || c.canal === LF.canal) && (!LF.busca || c.nome.toLowerCase().includes(LF.busca.toLowerCase())));
      const col = el("div", { class: "col" }, el("div", { class: "col-h" }, etapa, el("span", { class: "n" }, cards.length)), el("div", { class: "cards" }, cards.length ? cards.slice(0, 80).map(cartaoKanban) : el("div", { class: "faint", style: "padding:8px 4px;font-size:12.5px" }, "Vazio")));
      col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("over"); });
      col.addEventListener("dragleave", () => col.classList.remove("over"));
      col.addEventListener("drop", async (e) => {
        e.preventDefault(); col.classList.remove("over");
        const id = e.dataTransfer.getData("text/plain");
        if (id.startsWith("c")) { await post(`/api/leads/${id.slice(1)}/editar`, { etapa }); renderizar(); }
        else toast("Leads de e-mail da Nexora mudam de etapa pelas respostas e aprovações", "err");
      });
      quadro.append(col);
    }
  }
  pintar();
}

function cartaoKanban(l) {
  const c = el("div", { class: "kc" + (l.score >= 70 ? " p-alta" : ""), draggable: l.readonly ? "false" : "true", onclick: () => abrirLead(l.ref || l.id) },
    el("div", { class: "nm" }, l.nome), el("div", { class: "mt" }, canalIc(l.canal), l.score != null ? el("span", {}, "oportunidade " + l.score) : "", l.aprovado ? pill("ok", "aprovado") : ""),
    l.proxima ? el("div", { class: "pr" }, l.proxima) : "");
  c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", String(l.ref || l.id)));
  return c;
}

async function captacao(raiz) {
  const leads = await api(`/api/captacao?conta=${S.conta}`);
  const filtros = [["todos", "Todos", () => true], ["semsite", "Sem site", (l) => (l.sinais || []).some((s) => /sem (site|landing)/.test(s))], ["tel", "Com telefone", (l) => l.telefone || (l.sinais || []).includes("com telefone")], ["alta", "Oportunidade 70+", (l) => l.score >= 70]];
  raiz.append(el("div", { class: "chips", style: "margin-bottom:6px" }, filtros.map(([k, r]) => el("button", { class: "chip" + (LF.chip === k ? " on" : ""), onclick: () => { LF.chip = k; renderizar(); } }, r))),
    el("details", { style: "margin:10px 0 18px;color:var(--tx3);font-size:13px" }, el("summary", { style: "cursor:pointer" }, "Como ler a oportunidade"),
      el("p", {}, "De 0 a 100. Sobe quando a empresa tem muitas avaliações (reputação forte) e a presença digital é fraca (sem site, ou site ruim). 70 ou mais indica alguém bem falado que perde cliente por falta de página. Novo aguarda a análise da IA; Pronto já tem mensagem escrita.")));
  const linhas = leads.filter(filtros.find((f) => f[0] === LF.chip)[2]);
  const corpo = el("div", { class: "fade" });
  if (!linhas.length) corpo.append(vazio("Nenhum lead captado ainda", "Use Captar para buscar empresas ou ligue a captação diária em Configurações."));
  for (const l of linhas.slice(0, 120)) {
    const evid = [l.avaliacoes != null ? l.avaliacoes + " avaliações" : null, ...(l.sinais || []).filter((s) => !["com telefone"].includes(s))].filter(Boolean).join(" · ");
    corpo.append(el("div", { class: "lead-row", onclick: () => abrirLead(l.ref || l.id) },
      anel(l.score), el("div", {}, el("div", { style: "font-weight:600" }, l.nome), el("div", { class: "ev" }, [l.sub, l.tag].filter(Boolean).join(" · "))),
      el("div", {}, el("div", { class: "dor" }, l.dor || (l.tipo_dor ? nomeDor(l.tipo_dor) : "Aguardando análise da IA")), evid ? el("div", { class: "ev" }, evid) : ""),
      el("div", { style: "display:flex;gap:8px;align-items:center" }, pill(l.etapa === "Pronto" ? "ok" : "", l.etapa === "Novo" ? (l.dor ? "Analisado" : "Novo") : l.etapa),
        !l.readonly && !l.dor ? botaoAcao("Analisar", async () => { await post(`/api/leads/${String(l.id).slice(1)}/analisar`); toast("Análise iniciada", "ok"); }, "btn sm ghost") : "")));
  }
  raiz.append(corpo);
}

function novoLead() {
  const f = (n, r, extra = {}) => el("div", {}, el("label", {}, r), el("input", Object.assign({ name: n }, extra)));
  const canal = el("select", { name: "canal" }, el("option", { value: "whatsapp" }, "WhatsApp"), el("option", { value: "email" }, "E-mail"));
  if (S.conta === "nexora") canal.value = "email";
  const form = el("div", {}, el("label", {}, "Canal"), canal, f("nome", "Empresa", { required: true }), el("div", { class: "inl" }, f("telefone", "Telefone com DDD"), f("email", "E-mail", { type: "email" })),
    el("div", { class: "inl" }, f("cidade", "Cidade"), f("site", "Site (vazio se não tem)")), el("div", { class: "inl" }, f("avaliacoes", "Nº de avaliações", { type: "number", min: 0 }), f("fonte", "Fonte")),
    el("div", { class: "note info", style: "margin:14px 0 0" }, "Sem mensagem, a IA analisa a dor e escreve a abordagem sozinha em poucos minutos."));
  dialogo("Novo lead", form, [el("button", { class: "btn ghost", onclick: fecharDialogo }, "Cancelar"), el("button", { class: "btn", onclick: async () => {
    const d = {}; $$("input,select", form).forEach((i) => { if (i.name && i.value) d[i.name] = i.name === "avaliacoes" ? Number(i.value) : i.value; });
    if (!d.nome) return toast("Informe o nome da empresa", "err");
    try { await post("/api/leads", Object.assign(d, { conta: S.conta, etapa: "Novo" })); fecharDialogo(); toast("Lead criado", "ok"); renderizar(); } catch (e) { /* toast ja mostrado */ }
  } }, "Salvar")]);
}

function captarDialog() {
  const form = el("div", {}, el("label", {}, "Cidade"), el("input", { name: "cidade", placeholder: S.conta === "atlas" ? "Ex: Feira de Santana, BA" : "Ex: Austin, TX" }), el("label", {}, "Categoria"),
    el("input", { name: "categoria", placeholder: S.conta === "atlas" ? "locação de equipamentos para construção" : "real estate agency" }), el("label", {}, "Quantidade máxima"), el("input", { name: "quantidade", type: "number", value: 10, min: 1, max: 30 }),
    el("div", { class: "note info", style: "margin:14px 0 0" }, "Usa a cota gratuita do Apify. Mantenha a quantidade baixa."));
  dialogo("Captar leads", form, [el("button", { class: "btn ghost", onclick: fecharDialogo }, "Cancelar"), el("button", { class: "btn", onclick: async () => {
    const d = {}; $$("input", form).forEach((i) => (d[i.name] = i.value));
    if (!d.cidade || !d.categoria) return toast("Preencha cidade e categoria", "err");
    await post("/api/captar", { conta: S.conta, cidade: d.cidade, categoria: d.categoria, quantidade: Number(d.quantidade) || 10 });
    fecharDialogo(); toast("Captação iniciada em segundo plano. Os leads aparecem aqui e a IA analisa cada um.", "ok");
  } }, "Captar")]);
}

/* ---------- gaveta do lead ---------- */
async function abrirLead(ref, aba = "resumo") {
  const ov = $("#overlay");
  ov.replaceChildren(el("div", { class: "veil", onclick: fecharGaveta }), el("aside", { class: "drawer", role: "dialog", "aria-label": "Detalhes do lead" }, el("div", { class: "drawer-b" }, esqueleto(4, 60))));
  let r;
  try { r = await api(`/api/lead?ref=${encodeURIComponent(ref)}`); } catch (e) { fecharGaveta(); return toast("Lead não encontrado", "err"); }
  const l = r.lead, crmLead = ref.startsWith("c");
  let crit = [], evid = [];
  try { const j = JSON.parse(l.criterios_json || "{}"); crit = j.criterios || []; evid = j.evidencias || []; } catch (e) { /* sem analise */ }
  const valid = l.mensagem && crmLead ? await post("/api/validar", { conta: l.conta, canal: l.canal, tipo: "primeiro", texto: l.mensagem }, { silencioso: true }).catch(() => null) : null;

  const painel = { resumo: () => abaResumo(l, crit, evid, valid), conversa: () => abaConversa(l, r), followups: () => abaFollowups(r), atividade: () => abaAtividade(r) };
  const corpo = el("div", { class: "drawer-b" });
  const abas = el("div", { class: "tabs", style: "margin:14px 0 0" });
  const pintar = (k) => {
    $$(".tab", abas).forEach((t) => t.classList.toggle("on", t.dataset.k === k));
    corpo.replaceChildren(painel[k]());
  };
  [["resumo", "Resumo"], ["conversa", "Conversa"], ["followups", "Follow-ups"], ["atividade", "Atividade"]].forEach(([k, rot]) => abas.append(el("button", { class: "tab" + (k === aba ? " on" : ""), "data-k": k, onclick: () => pintar(k) }, rot)));
  const link = l.telefone && (l.canal === "whatsapp") ? "https://wa.me/" + wapp(l.telefone) : "";
  const rodape = el("div", { class: "drawer-f" });
  if (crmLead) {
    if (l.canal === "whatsapp" && l.mensagem && link) rodape.append(el("a", { class: "btn", href: link + "?text=" + encodeURIComponent(l.mensagem), target: "_blank", rel: "noopener" }, icon("chat"), "Abrir no WhatsApp"));
    rodape.append(botaoAcao("Analisar dor", async () => { await post(`/api/leads/${ref.slice(1)}/analisar`); toast("Análise iniciada", "ok"); }, "btn sec sm", "refresh"),
      botaoAcao("Editar mensagem", async () => { fecharGaveta(); editarMensagem({ ref, lead_id: ref.slice(1), canal: l.canal, assunto: l.assunto }); }, "btn sec sm", "star"));
    const mover = el("select", { style: "width:auto;min-height:34px;padding:4px 10px", "aria-label": "Mover para etapa" }, el("option", { value: "" }, "Mover para…"), ETAPAS.map((e) => el("option", { value: e }, e)));
    mover.addEventListener("change", async () => { if (mover.value) { await post(`/api/leads/${ref.slice(1)}/editar`, { etapa: mover.value }); fecharGaveta(); renderizar(); } });
    rodape.append(mover, botaoAcao("Descartar", async () => { await post(`/api/leads/${ref.slice(1)}/descartar`); fecharGaveta(); renderizar(); }, "btn danger sm"));
  } else if (l.etapa === "Pronto" && !l.aprovado) {
    rodape.append(botaoAcao("Aprovar e-mail", async () => { await post("/api/nexora/aprovar", { ids: [Number(ref.slice(1))] }); toast("Aprovado", "ok"); fecharGaveta(); renderizar(); }, "btn sm", "check"),
      botaoAcao("Rejeitar", async () => { await post("/api/nexora/rejeitar", { ids: [Number(ref.slice(1))], motivo: "rejeitado no CRM" }); fecharGaveta(); renderizar(); }, "btn danger sm"));
  }
  const cab = el("div", { class: "drawer-h" }, el("div", { style: "display:flex;gap:14px;align-items:flex-start" },
    l.score != null ? anel(l.score, 46) : "", el("div", { style: "flex:1;min-width:0" }, el("div", { style: "font-size:19px;font-weight:620;letter-spacing:-.01em" }, l.nome),
      el("div", { class: "faint", style: "font-size:13px;margin-top:2px" }, [l.cidade || l.sub, l.telefone, l.email].filter(Boolean).join(" · "))),
    el("button", { class: "btn ghost sm", "aria-label": "Fechar", onclick: fecharGaveta }, icon("x"))),
    el("div", { style: "display:flex;gap:6px;margin-top:10px;flex-wrap:wrap" }, pill("ac", l.etapa), pill("", l.canal === "whatsapp" ? "WhatsApp" : "E-mail"), l.tipo_dor ? pill("warn", nomeDor(l.tipo_dor)) : "", l.aprovado ? pill("ok", "aprovado") : ""), abas);
  ov.replaceChildren(el("div", { class: "veil", onclick: fecharGaveta }), el("aside", { class: "drawer", role: "dialog", "aria-label": "Detalhes do lead" }, cab, corpo, rodape));
  pintar(aba);
}
const wapp = (t) => { const d = String(t).replace(/\D/g, ""); return d.length <= 11 ? "55" + d : d; };
function fecharGaveta() { $("#overlay").replaceChildren(); }

function abaResumo(l, crit, evid, valid) {
  const d = el("div", { class: "fade" });
  if (l.dor) d.append(el("div", { class: "sec-h", style: "margin-top:18px" }, el("h2", {}, "Dor principal")), el("div", { style: "font-size:15px;line-height:1.5" }, l.dor));
  else d.append(el("div", { class: "note info", style: "margin-top:18px" }, "Ainda sem análise de dor."));
  if (crit.length) d.append(el("div", { class: "sec-h", style: "margin-top:22px" }, el("h2", {}, "Critérios analisados")), crit.map((c) => el("div", { class: "crit" }, el("b", {}, c.criterio || ""), pill(c.impacto === "alto" ? "err" : c.impacto === "medio" ? "warn" : "info", c.impacto || ""), el("div", { class: "a", style: "grid-column:1/-1" }, c.achado || ""))));
  if (evid.length) d.append(el("div", { class: "sec-h", style: "margin-top:22px" }, el("h2", {}, "Evidências")), el("ul", { class: "muted", style: "margin:0;padding-left:18px" }, evid.map((e) => el("li", {}, typeof e === "string" ? e : JSON.stringify(e)))));
  const texto = l.mensagem || l.corpo_texto || l.nota;
  if (texto) {
    d.append(el("div", { class: "sec-h", style: "margin-top:22px" }, el("h2", {}, l.canal === "email" ? "E-mail" : "Mensagem"),
      valid ? (valid.violacoes.length ? pill("err", valid.violacoes.length + " problema(s) nas regras") : pill("ok", "dentro das regras")) : ""),
      l.assunto ? el("div", { class: "muted", style: "margin-bottom:6px" }, "Assunto: " + l.assunto) : "", el("div", { class: "item" }, el("div", { style: "grid-column:1/-1" }, el("div", { class: "msg", style: "margin-top:0" }, texto))),
      valid && valid.violacoes.length ? el("div", { style: "color:var(--err);font-size:12.5px;margin-top:8px" }, valid.violacoes.map((v) => el("div", {}, "• " + v))) : "",
      el("div", { style: "margin-top:10px" }, botaoAcao("Copiar", () => copiar(texto), "btn ghost sm", "copy")));
  }
  if (l.notas) d.append(el("div", { class: "sec-h", style: "margin-top:22px" }, el("h2", {}, "Notas")), el("div", { class: "muted", style: "white-space:pre-wrap" }, l.notas));
  return d;
}

function abaConversa(l, r) {
  const itens = [];
  (r.whatsapp || []).forEach((m) => itens.push({ t: m.created_at, dir: m.direcao === "saida" ? "out" : "in", txt: m.texto, via: "WhatsApp" }));
  (r.respostas || []).filter((x) => x.origem !== "whatsapp").forEach((m) => itens.push({ t: m.created_at, dir: "in", txt: m.texto, via: m.origem === "gmail" ? "E-mail" : "Manual", cls: m.classificacao, resumo: m.resumo, trad: m.traducao }));
  itens.sort((a, b) => (a.t > b.t ? 1 : -1));
  if (!itens.length) return vazio("Nenhuma mensagem ainda", "Envios e respostas detectados aparecem aqui.");
  const ultResp = (r.respostas || []).filter((x) => x.origem === "whatsapp").slice(-1)[0];
  return el("div", { class: "thread fade", style: "margin-top:18px" }, itens.map((m) => el("div", { class: "bolha " + m.dir }, m.txt,
    el("small", {}, [m.via, dataHora(m.t)].join(" · ")), m.cls ? clsPill(m.cls) : "", m.trad && m.trad !== m.txt ? el("small", {}, "Tradução: " + m.trad) : "", m.resumo ? el("small", {}, m.resumo) : "")),
    ultResp ? el("div", { style: "margin-top:8px" }, "Última classificação: ", clsPill(ultResp.classificacao)) : "");
}

function abaFollowups(r) {
  if (!r.tarefas.length) return vazio("Sem follow-ups", "Eles são criados quando o primeiro contato é detectado.");
  return el("div", { class: "fade", style: "margin-top:12px" }, r.tarefas.map((t) => el("div", { class: "crit" }, el("b", {}, "Follow-up " + t.passo + " · " + new Date(t.due_date + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })),
    pill(t.status === "feita" ? "ok" : t.status === "pendente" ? "warn" : "", t.status), el("div", { class: "a", style: "grid-column:1/-1;white-space:pre-wrap" }, t.mensagem || ""))));
}

function abaAtividade(r) {
  if (!r.eventos.length) return vazio("Sem histórico", "As mudanças de etapa passam a ser registradas daqui em diante.");
  const nomeEv = (e) => (e.tipo === "criado" ? "Lead criado em " + e.para_etapa : e.de_etapa + " → " + e.para_etapa);
  return el("div", { class: "tl fade", style: "margin-top:16px" }, r.eventos.map((e) => el("div", {}, el("b", {}, nomeEv(e)), el("span", { class: "faint", style: "margin-left:8px" }, dataHora(e.ts)))));
}
