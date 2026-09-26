/* Hoje: a tela operacional. Sem navegar pelo CRM para saber o que fazer. */
"use strict";
const CATS = [["responder", "Responder"], ["whatsapp", "Enviar WhatsApp"], ["aprovar_email", "Aprovar e-mail"], ["revisar", "Revisar lead"], ["followup", "Follow-up"]];

VIEWS.hoje = async function (raiz) {
  const [a, cx] = await Promise.all([api(`/api/acoes?conta=${S.conta}`), api("/api/conexoes")]);
  const waOk = cx.whatsapp.estado === "conectado";
  const emailAuto = cx.config[`auto_followup_email_${S.conta}`] === "1";
  cabecalho(raiz, "Hoje", new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }));
  const escolhida = CATS.some((c) => c[0] === S.sub) ? S.sub : (CATS.find((c) => a.resumo[c[0]] > 0) || CATS[0])[0];

  const frases = [];
  if (a.resumo.responder) frases.push(a.resumo.responder + (a.resumo.responder > 1 ? " respostas aguardando" : " resposta aguardando"));
  if (a.resumo.whatsapp) frases.push(a.resumo.whatsapp + " WhatsApp" + (a.resumo.whatsapp > 1 ? "s" : "") + " para enviar");
  if (a.resumo.aprovar_email) frases.push(a.resumo.aprovar_email + " e-mail" + (a.resumo.aprovar_email > 1 ? "s" : "") + " para aprovar");
  if (a.resumo.revisar) frases.push(a.resumo.revisar + " lead" + (a.resumo.revisar > 1 ? "s" : "") + " para revisar");
  raiz.append(el("div", { class: "hero fade" }, el("div", { class: "big" }, a.total), el("div", { class: "txt" }, a.total === 1 ? "ação hoje" : "ações hoje", frases.length ? el("div", { class: "faint", style: "font-size:13px" }, frases.join(" · ")) : "")));
  if (S.conta === "atlas" && !waOk) raiz.append(el("div", { class: "note", style: "margin-top:12px" }, "WhatsApp não conectado: o envio e as respostas não são detectados sozinhos. ", el("a", { href: "#/atlas/config", style: "text-decoration:underline" }, "Conectar")));

  raiz.append(el("div", { class: "cats" }, CATS.map(([k, rot]) => el("button", { class: "cat" + (k === escolhida ? " on" : "") + (a.resumo[k] ? "" : " zero"), onclick: () => ir("hoje", k) },
    el("span", { class: "n" }, a.resumo[k]), el("span", { class: "l" }, rot)))));

  const lista = a[escolhida] || [];
  const corpo = el("div", { class: "list fade" });
  if (escolhida === "aprovar_email" && lista.length) raiz.append(barraAprovacao(a));
  if (!lista.length) corpo.append(vazio(a.total ? "Nada nesta categoria" : "Tudo em dia", a.total ? "Escolha outra acima." : "O sistema está captando e analisando. Volte mais tarde ou veja o Radar."));
  for (const it of lista) corpo.append(linhaAcao(escolhida, it, { waOk, emailAuto }));
  raiz.append(corpo);
};

function barraAprovacao(a) {
  const ids = a.aprovar_ids || a.aprovar_email.map((i) => i.lead_id);
  const nexora = S.conta === "nexora";
  const b = el("div", { style: "display:flex;gap:8px;margin:14px 0 4px;flex-wrap:wrap;align-items:center" });
  b.append(botaoAcao(`Aprovar todos (${ids.length})`, async () => {
    if (!(await confirmar("Aprovar " + ids.length + " e-mails?", "Eles ficam prontos para envio. Nada é enviado até você mandar enviar."))) return;
    if (nexora) await post("/api/nexora/aprovar", { ids });
    else for (const id of ids) await post(`/api/leads/${id}/aprovar`);
    toast("Aprovados", "ok"); renderizar();
  }, "btn sm sec", "check"));
  if (nexora) b.append(botaoAcao("Enviar aprovados agora", enviarNexora, "btn sm", "send"));
  return b;
}

async function enviarNexora() {
  let plano;
  try { plano = await post("/api/nexora/enviar", {}, { silencioso: true }); } catch (e) { toast(e.message, "err"); return; }
  toast(`Envio iniciado: ${plano.a_enviar} e-mails, cerca de ${plano.minutos_estimados} min (45 s entre envios).`, "ok");
}

function linhaAcao(cat, it, ctx) {
  const abrir = () => abrirLead(it.ref);
  const lado = el("div", { class: "lado" });
  const t1 = el("div", { class: "t1" }, it.nome, canalIc(it.canal));
  const corpo = el("div", {}, t1);
  if (cat === "responder") {
    t1.append(clsPill(it.classificacao), pill("", it.etapa), el("span", { class: "faint", style: "font-weight:450;font-size:12.5px" }, "há " + quando(it.desde)));
    corpo.append(el("div", { class: "t2" }, it.resumo ? it.resumo + " — " : "", it.texto), S.conta === "nexora" && it.texto ? botaoTraduzir(it.texto, "en", "pt") : "");
    lado.append(botaoAcao("Responder", () => abrirConversa(it), "btn sm", "arrow"));
  } else if (cat === "whatsapp") {
    if (it.score != null) t1.append(pill(it.score >= 70 ? "ok" : "", "oportunidade " + it.score));
    if (it.dor) corpo.append(el("div", { class: "t2" }, it.dor));
    corpo.append(el("div", { class: "msg" }, it.mensagem || ""));
    if (it.link) lado.append(el("a", { class: "btn sm", href: it.link, target: "_blank", rel: "noopener", onclick: (e) => e.stopPropagation() }, icon("chat"), "Abrir no WhatsApp"));
    lado.append(botaoAcao("Copiar", () => copiar(it.mensagem || ""), "btn sm ghost", "copy"));
    if (!ctx.waOk) lado.append(botaoAcao("Enviei", async () => { await post(`/api/leads/${it.lead_id}/sent`); renderizar(); }, "btn sm ghost", "check"));
    lado.append(botaoAcao("Sem WhatsApp", async () => { await post(`/api/leads/${it.lead_id}/sem_whatsapp`); renderizar(); }, "btn sm ghost"));
  } else if (cat === "aprovar_email") {
    if (it.score != null) t1.append(pill(it.score >= 70 ? "ok" : "", "oportunidade " + it.score));
    corpo.append(el("div", { class: "t2" }, it.assunto || "(sem assunto)"), it.dor ? el("div", { class: "faint", style: "font-size:12.5px" }, nomeDor(it.dor)) : "");
    lado.append(botaoAcao("Aprovar", async () => {
      if (it.nexora) await post("/api/nexora/aprovar", { ids: [it.lead_id] }); else await post(`/api/leads/${it.lead_id}/aprovar`);
      toast("Aprovado", "ok"); renderizar();
    }, "btn sm", "check"), botaoAcao("Rejeitar", async () => {
      if (it.nexora) await post("/api/nexora/rejeitar", { ids: [it.lead_id], motivo: "rejeitado na tela Hoje" }); else await post(`/api/leads/${it.lead_id}/descartar`);
      renderizar();
    }, "btn sm danger"));
  } else if (cat === "revisar") {
    corpo.append(el("div", { class: "t2" }, it.motivo || "Sem mensagem"));
    lado.append(botaoAcao("Editar mensagem", () => editarMensagem(it), "btn sm", "star"), botaoAcao("Analisar de novo", async () => { await post(`/api/leads/${it.lead_id}/analisar`); toast("Análise iniciada, leva alguns minutos", "ok"); }, "btn sm ghost", "refresh"));
  } else {
    t1.append(pill(it.atrasado ? "err" : "warn", "follow-up " + it.passo + (it.atrasado ? " atrasado" : "")), it.ia ? pill("ok", "adaptado por IA") : "");
    corpo.append(el("div", { class: "msg" }, it.mensagem || ""));
    if (it.canal === "whatsapp") {
      if (it.link) lado.append(el("a", { class: "btn sm", href: it.link, target: "_blank", rel: "noopener", onclick: (e) => e.stopPropagation() }, icon("chat"), "Abrir no WhatsApp"));
      lado.append(botaoAcao("Copiar", () => copiar(it.mensagem || ""), "btn sm ghost", "copy"));
      if (!ctx.waOk) lado.append(botaoAcao("Enviei", async () => { await post(`/api/tarefas/${it.tarefa_id}/feita`); renderizar(); }, "btn sm ghost", "check"));
    } else lado.append(ctx.emailAuto ? pill("ok", "sai sozinho") : botaoAcao("Marcar como enviado", async () => { await post(`/api/tarefas/${it.tarefa_id}/feita`); renderizar(); }, "btn sm sec"), ctx.emailAuto ? "" : el("span", { class: "faint", style: "font-size:12px" }, "envio automático desligado"));
  }
  return el("div", { class: "item", onclick: abrir }, corpo, lado);
}

function abrirConversa(it) {
  if (it.canal === "whatsapp") ir("inbox", "whatsapp/" + it.ref);
  else { GM.busca = it.email || ""; GM.pasta = "INBOX"; GM.sel = null; ir("inbox", "email"); }
}

/* edicao de mensagem com validacao das regras de copy em tempo real */
async function editarMensagem(lead) {
  const canal = lead.canal, conta = S.conta;
  const atual0 = await api(`/api/lead?ref=${encodeURIComponent(lead.ref)}`).catch(() => null);   // carrega ANTES de abrir: nada apaga o que o usuario digitar
  const ta = el("textarea", { style: "min-height:150px" });
  ta.value = (atual0 && atual0.lead.mensagem) || "";
  const ass = canal === "email" ? el("input", { placeholder: "Assunto", value: (atual0 && atual0.lead.assunto) || lead.assunto || "" }) : null;
  const caixa = el("div", { style: "margin-top:10px;font-size:12.5px;min-height:20px" });
  let atual = [];
  let timer;
  const validar = async () => {
    const r = await post("/api/validar", { conta, canal, tipo: "primeiro", texto: ta.value }, { silencioso: true }).catch(() => null);
    if (!r) return;
    atual = r.violacoes;
    caixa.replaceChildren(...(atual.length ? atual.map((v) => el("div", { style: "color:var(--err)" }, "• " + v)) : [el("div", { style: "color:var(--ok)" }, "Dentro das regras de copy")]));
  };
  ta.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(validar, 350); });
  dialogo("Editar mensagem", el("div", {}, ass ? [el("label", {}, "Assunto"), ass] : "", el("label", {}, canal === "whatsapp" ? "Mensagem de WhatsApp" : "Corpo do e-mail"), ta, caixa), [
    el("button", { class: "btn ghost", onclick: fecharDialogo }, "Cancelar"),
    el("button", { class: "btn", onclick: async () => {
      if (atual.length && !(await confirmar("Salvar mesmo assim?", "A mensagem ainda quebra: " + atual.join("; "), "Salvar mesmo assim"))) return;
      await post(`/api/leads/${lead.lead_id}/editar`, Object.assign({ mensagem: ta.value, etapa: "Pronto" }, ass ? { assunto: ass.value } : {}));
      fecharDialogo(); toast("Mensagem salva, lead na fila", "ok"); renderizar();
    } }, "Salvar e enviar para a fila"),
  ]);
  validar();
}
