/* Configuracoes: conexoes (WhatsApp com QR que se atualiza sozinho), Gmail, automacoes, follow-ups e saude do sistema. */
"use strict";
let waTimer = null;
const limparTimers = () => { clearInterval(waTimer); waTimer = null; };

VIEWS.config = async function (raiz) {
  const sub = ["conexoes", "automacoes", "followups", "sistema"].includes(S.sub) ? S.sub : "conexoes";
  cabecalho(raiz, "Configurações", NOMES[S.conta]);
  raiz.append(el("div", { class: "tabs" }, [["conexoes", "Conexões"], ["automacoes", "Automações"], ["followups", "Follow-ups"], ["sistema", "Sistema"]].map(([k, r]) => el("button", { class: "tab" + (sub === k ? " on" : ""), onclick: () => ir("config", k) }, r))));
  const cx = await api("/api/conexoes");
  if (sub === "conexoes") conexoes(raiz, cx);
  else if (sub === "automacoes") automacoes(raiz, cx);
  else if (sub === "followups") await followups(raiz);
  else await sistema(raiz, cx);
};

/* ---- WhatsApp ---- */
function blocoWhatsapp(w) {
  const ativo = ["qr", "iniciando", "autenticando", "reiniciando"].includes(w.estado);
  const rotulo = { conectado: ["ok", "Conectado"], qr: ["warn", "Aguardando leitura do QR"], iniciando: ["info", "Iniciando"], autenticando: ["info", "Autenticando"], reiniciando: ["warn", "Reiniciando"],
    qr_expirado: ["warn", "QR expirado"], erro: ["err", "Erro"], parado: ["", "Parado"], desconectado: ["err", "Desconectado"], falha: ["err", "Falha de autenticação"] }[w.estado] || ["", w.estado];
  const d = el("div", {}, el("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, pill(rotulo[0], rotulo[1]), w.vinculado ? pill("", "aparelho já vinculado") : ""));
  if (w.motivo) d.append(el("div", { class: "note", style: "margin:12px 0 0" }, w.motivo));
  if (w.estado === "qr" && w.qr) d.append(el("div", { style: "margin-top:16px" }, el("div", { class: "qrbox" }, el("img", { src: w.qr, alt: "QR Code do WhatsApp" })),
    el("div", { class: "faint", style: "margin-top:10px;font-size:13px;line-height:1.6" }, "No celular: WhatsApp, Aparelhos conectados, Conectar aparelho. ", el("br"), "QR atualizado há " + (w.qr_idade_s ?? 0) + " s. Ele se renova sozinho; a tela acompanha.")));
  else if (ativo) d.append(el("div", { class: "faint", style: "margin-top:14px" }, "Abrindo o WhatsApp Web, o QR aparece em até 40 segundos."), el("div", { class: "sk", style: "width:260px;height:260px;margin-top:12px" }));
  if (w.estado === "conectado") d.append(el("p", { class: "muted", style: "margin-top:14px" }, "O CRM observa o WhatsApp: detecta o que você envia e as respostas dos seus leads. Ele nunca envia mensagem e ignora conversas de números que não são leads."));
  const b = el("div", { style: "display:flex;gap:8px;margin-top:16px;flex-wrap:wrap" });
  if (w.estado === "conectado") b.append(botaoAcao("Desconectar", async () => { await post("/api/wa/stop"); renderizar(); }, "btn sec sm"));
  else {
    b.append(botaoAcao(ativo ? "Gerar novo QR" : "Conectar WhatsApp", async () => { await post(ativo ? "/api/wa/novo-qr" : "/api/wa/start"); renderizar(); }, "btn sm", "refresh"));
    if (ativo) b.append(botaoAcao("Parar", async () => { await post("/api/wa/stop"); renderizar(); }, "btn ghost sm"));
  }
  d.append(b);
  if (w.atividade && w.atividade.length) d.append(el("details", { open: "", style: "margin-top:16px;color:var(--tx3);font-size:12.5px" }, el("summary", { style: "cursor:pointer" }, "O que o observador viu (sem o texto das mensagens)"), w.atividade.slice().reverse().map((e) => el("div", {}, e))));
  if (w.eventos && w.eventos.length) d.append(el("details", { style: "margin-top:16px;color:var(--tx3);font-size:12.5px" }, el("summary", { style: "cursor:pointer" }, "Registro do observador"), w.eventos.map((e) => el("div", {}, e))));
  return { d, ativo };
}

function conexoes(raiz, cx) {
  const slot = el("div", { id: "wa-slot" });
  const secao = (t, c, aux) => el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, t), aux || ""), c);
  const pintar = (w) => { const r = blocoWhatsapp(w); slot.replaceChildren(r.d); return r.ativo; };
  const ativo = pintar(cx.whatsapp);
  raiz.append(secao("WhatsApp (somente leitura)", slot));
  limparTimers();
  waTimer = setInterval(async () => {
    if (S.view !== "config" || (S.sub && S.sub !== "conexoes")) return limparTimers();
    const c = await api("/api/conexoes").catch(() => null);
    if (!c) return;
    const a = pintar(c.whatsapp);
    if (!a && c.whatsapp.estado !== "qr_expirado") limparTimers();
  }, 3000);
  raiz.append(secao("Gmail", el("div", {}, ["nexora", "atlas"].map((c) => el("div", { class: "sw" }, el("div", { class: "d" }, el("b", {}, NOMES[c]), el("span", {}, cx.gmail[c].endereco || "não configurado")),
    cx.gmail[c].configurado ? [pill("ok", "lendo respostas"), botaoAcao("Ler agora", async () => { await post("/api/gmail/sync", { conta: c }); toast("Leitura iniciada", "ok"); }, "btn sm sec")]
      : pill("warn", c === "atlas" ? "rode py crm/atlas_gmail_auth.py" : "não configurado"))),
    el("p", { class: "faint", style: "font-size:12.5px;margin-top:12px" }, "As respostas (caixa de entrada e spam) são lidas a cada 5 minutos, classificadas por IA local, traduzidas, e o card muda de etapa sozinho. Descadastros e e-mails devolvidos bloqueiam o contato."))));
}

function automacoes(raiz, cx) {
  const sw = (chave, titulo, desc) => el("div", { class: "sw" }, el("div", { class: "d" }, el("b", {}, titulo), el("span", {}, desc)),
    toggle(cx.config[chave] === "1", async () => { await post("/api/config", { chave, valor: cx.config[chave] === "1" ? "0" : "1" }); renderizar(); }));
  raiz.append(el("div", {}, sw("auto_followup_email_" + S.conta, "Follow-up de e-mail sozinho", "Envia D+3, D+7 e D+14 dentro do teto de 20 por dia, 45 s entre envios, parando quando o lead responde ou pede para sair."),
    sw("auto_analisar", "Análise de dor automática", "A IA analisa cada lead novo (site, avaliações, concorrentes) e escreve a abordagem. Mensagens que quebram as regras não entram na fila.")));
  let capt = {};
  try { capt = JSON.parse(cx.config.captar_atlas || "{}"); } catch (e) { capt = {}; }
  if (S.conta === "atlas") {
    const cid = el("textarea", { placeholder: "Uma cidade por linha" }); cid.value = (capt.cidades || []).join("\n");
    const cat = el("input", { value: capt.categoria || "locação de equipamentos para construção" }), qtd = el("input", { type: "number", value: capt.quantidade || 10, min: 1, max: 30 });
    const salvar = (ativo) => post("/api/config", { chave: "captar_atlas", valor: JSON.stringify(Object.assign({}, capt, { cidades: cid.value.split("\n").map((s) => s.trim()).filter(Boolean), categoria: cat.value, quantidade: Number(qtd.value), ativo })) }).then(() => { toast("Salvo", "ok"); renderizar(); });
    raiz.append(el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, "Captação diária"), capt.ativo ? pill("ok", "ligada") : pill("", "desligada")),
      el("p", { class: "faint", style: "margin-top:0" }, "Uma cidade por dia, em rodízio. Usa a cota gratuita do Apify (US$ 5 por mês), então mantenha a quantidade baixa."), el("label", {}, "Cidades"), cid, el("div", { class: "inl" }, el("div", {}, el("label", {}, "Categoria"), cat), el("div", {}, el("label", {}, "Leads por dia"), qtd)),
      el("div", { class: "row-b", style: "justify-content:flex-start" }, botaoAcao(capt.ativo ? "Salvar e manter ligada" : "Salvar e ligar", () => salvar(true), "btn sm"), botaoAcao("Salvar e desligar", () => salvar(false), "btn sm sec"))));
  } else raiz.append(el("div", { class: "note info" }, "A captação da Nexora roda pela rotina agendada do Windows (Nexora-Prospeccao). A aprovação e o envio dos e-mails ficam na tela Hoje."));
}

async function followups(raiz) {
  const r = await api(`/api/modelos?conta=${S.conta}`);
  raiz.append(el("div", { class: "note info" }, "Estes são os textos padrão. Perto do vencimento a IA reescreve cada follow-up adaptado à dor do lead; se a versão da IA quebrar as regras, este texto é usado. Use {nome} para o nome da empresa."));
  for (const m of r.modelos) {
    const ta = el("textarea", { style: "min-height:90px" }); ta.value = m.texto;
    const aviso = el("div", { style: "font-size:12.5px;margin-top:6px" });
    const canal = S.conta === "atlas" ? "whatsapp" : "email";
    const validar = async () => { const v = await post("/api/validar", { conta: S.conta, canal, tipo: "followup", texto: ta.value.replace("{nome}", "Empresa") }, { silencioso: true }).catch(() => null); if (v) aviso.replaceChildren(...(v.violacoes.length ? v.violacoes.map((x) => el("div", { style: "color:var(--err)" }, "• " + x)) : [el("div", { style: "color:var(--ok)" }, "Dentro das regras")])); };
    let t; ta.addEventListener("input", () => { clearTimeout(t); t = setTimeout(validar, 350); });
    raiz.append(el("div", { class: "sec", style: "margin-top:24px" }, el("div", { class: "sec-h" }, el("h2", {}, "Follow-up " + m.passo), el("span", { class: "aux" }, r.dias[m.passo - 1] + " dias depois do primeiro contato")), ta, aviso,
      el("div", { style: "margin-top:10px" }, botaoAcao("Salvar", async () => { await post("/api/modelos", { conta: S.conta, passo: m.passo, texto: ta.value }); toast("Salvo", "ok"); }, "btn sm"))));
    validar();
  }
}

async function sistema(raiz, cx) {
  const s = await api("/api/saude");
  const linha = (nome, ok, det) => el("div", { class: "sw" }, el("div", { class: "d" }, el("b", {}, nome), el("span", {}, det || "")), pill(ok === true ? "ok" : ok === false ? "err" : "warn", ok === true ? "ok" : ok === false ? "com erro" : "aguardando"));
  const nomes = { gmail: "Leitura de respostas (Gmail)", ia: "IA: análise e follow-ups", captacao: "Captação diária", envio: "Envio de e-mails", manutencao: "Backup diário", gmail_nexora: "Gmail da Nexora", gmail_atlas: "Gmail da Atlas" };
  const w = Object.entries(s.workers).map(([k, v]) => linha(nomes[k] || k, v.ok, v.ok ? "última execução " + quando(v.ultima_execucao) + " atrás" : v.erro));
  raiz.append(el("div", {}, linha("Inteligência artificial (claude -p)", s.ia.falhas_seguidas ? false : true, s.ia.falhas_seguidas ? s.ia.falhas_seguidas + " falha(s) seguidas: " + s.ia.ultimo_erro : (s.ia.ultimo_ok ? "última resposta " + s.ia.ultimo_ok : "ainda não usada nesta sessão")),
    linha("WhatsApp", s.whatsapp.estado === "conectado" ? true : (["erro", "desconectado", "falha"].includes(s.whatsapp.estado) ? false : null), s.whatsapp.estado + (s.whatsapp.motivo ? ": " + s.whatsapp.motivo : "")),
    ...w));
  raiz.append(el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, "Backups do banco"), el("span", { class: "aux" }, "um por dia, mantém os 14 mais recentes")),
    s.backups.length ? el("div", { class: "muted" }, s.backups.map((b) => el("div", {}, b))) : vazio("Nenhum backup ainda")));
  raiz.append(el("div", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, "Tarefas automáticas recentes")),
    cx.jobs.length ? el("div", { class: "list" }, cx.jobs.map((j) => el("div", { class: "item", style: "cursor:default" }, el("div", {}, el("div", { class: "t1" }, j.tipo + " · " + NOMES[j.conta]), el("div", { class: "t2" }, j.detalhe || "")), pill(j.status === "ok" ? "ok" : j.status === "erro" ? "err" : "warn", j.status)))) : vazio("Nada executado ainda")));
}
