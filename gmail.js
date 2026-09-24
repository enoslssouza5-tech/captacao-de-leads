/* Caixa de e-mail estilo Gmail. Usa helpers globais definidos em app.js ($, el, api, q, st, pill, render, abrirLead). */
const CORES = ["#e0573b", "#3b82e0", "#2fa36b", "#a05be0", "#d99a1c", "#e0439a", "#2aa6b8"];
const corDe = (t) => CORES[[...(t || "?")].reduce((a, c) => a + c.charCodeAt(0), 0) % CORES.length];
const dataMail = (ms) => {
  const d = new Date(ms), h = new Date();
  return d.toDateString() === h.toDateString() ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
};
const avatar = (nome) => el("div", { class: "avatar", style: `background:${corDe(nome)}` }, (nome || "?").trim().charAt(0).toUpperCase());

async function postJson(url, corpo) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  return { ok: r.ok, j: await r.json() };
}

async function acaoMail(id, acao) {
  const { ok, j } = await postJson("/api/gmail/acao", { conta: st.conta, id, acao });
  if (!ok) { alert(j.erro || "Não foi possível executar a ação."); return false; }
  return true;
}

async function viewGmail() {
  const v = $("#view");
  const g = st.gm;
  const pastas = await api(`/api/gmail/pastas?${q()}`);
  if (pastas.erro) return v.append(el("div", { class: "note" }, st.conta === "atlas" ? "Gmail da Atlas ainda não conectado. Quando criar a conta, rode py crm/atlas_gmail_auth.py e volte aqui." : pastas.erro));
  const folders = el("div", { class: "m-folders" },
    el("button", { class: "btn", onclick: () => { $("#formMail").reset(); $("#dlgMail").showModal(); } }, "Escrever"),
    pastas.pastas.map((p) => el("button", { class: "folder" + (g.pasta === p.id ? " on" : ""), onclick: () => { g.pasta = p.id; g.sel = null; g.busca = ""; render(); } }, p.nome, el("b", {}, p.nao_lidas ? String(p.nao_lidas) : ""))),
    el("a", { class: "folder", href: "https://mail.google.com/", target: "_blank", rel: "noopener", style: "margin-top:auto" }, "Abrir Gmail original"));
  const busca = el("input", { placeholder: "Buscar (ex.: from:nome, is:unread)", value: g.busca });
  busca.addEventListener("keydown", (e) => { if (e.key === "Enter") { g.busca = busca.value; g.sel = null; render(); } });
  const lista = el("div", { class: "m-list" }, el("div", { class: "m-search" }, busca, el("button", { class: "btn ghost sm", onclick: () => render() }, "Atualizar")), el("div", { class: "empty", style: "padding:16px" }, "Carregando..."));
  const leitura = el("div", { class: "m-read" }, el("div", { class: "empty" }, "Selecione uma conversa."));
  v.append(el("div", { class: "mail" }, folders, lista, leitura));
  const r = await api(`/api/gmail/conversas?${q()}&pasta=${g.pasta}&busca=${encodeURIComponent(g.busca)}`);
  lista.lastChild.remove();
  if (r.erro) return lista.append(el("div", { class: "note", style: "margin:12px" }, r.erro));
  if (!r.itens.length) lista.append(el("div", { class: "empty", style: "padding:16px" }, "Nenhuma conversa aqui."));
  for (const c of r.itens) {
    const item = el("div", { class: "m-item" + (c.nao_lida ? " unread" : "") + (g.sel === c.id ? " on" : ""), onclick: () => { g.sel = c.id; $$(".m-item").forEach((x) => x.classList.remove("on")); item.classList.add("on"); abrirConversa(c.id, leitura); } },
      avatar(c.pessoa),
      el("div", { style: "min-width:0" }, el("div", { class: "m-who" }, c.pessoa + (c.msgs > 1 ? ` (${c.msgs})` : "")), el("div", { class: "m-subj" }, c.assunto), el("div", { class: "m-snip" }, c.snippet),
        c.lead ? el("div", { style: "margin-top:4px" }, pill("acc", c.lead.etapa), " ", el("small", { style: "color:var(--subtle)" }, c.lead.nome)) : ""),
      el("div", { class: "m-date" }, dataMail(c.data)));
    lista.append(item);
  }
  if (g.sel) abrirConversa(g.sel, leitura);
}

async function abrirConversa(id, alvo) {
  alvo.replaceChildren(el("div", { class: "empty" }, "Carregando..."));
  const t = await api(`/api/gmail/conversa?${q()}&id=${id}`);
  if (t.erro) return alvo.replaceChildren(el("div", { class: "note" }, t.erro));
  const ms = t.mensagens, ultima = ms[ms.length - 1];
  const emLixeira = ultima.rotulos.includes("TRASH"), lida = !ultima.rotulos.includes("UNREAD");
  const enviada = (m) => m.rotulos.includes("SENT");
  const outra = ms.slice().reverse().find((m) => !enviada(m)) || ultima;
  const destino = enviada(ultima) && !outra.de.email ? "" : (enviada(ultima) ? (ultima.para.match(/[\w.+-]+@[\w.-]+/) || [""])[0] : outra.de.email);
  const bar = el("div", { class: "m-bar" },
    el("button", { class: "btn ghost sm", onclick: async () => { if (await acaoMail(id, "archive")) render(); } }, "Arquivar"),
    el("button", { class: "btn ghost sm", onclick: async () => { if (await acaoMail(id, emLixeira ? "untrash" : "trash")) { st.gm.sel = null; render(); } } }, emLixeira ? "Restaurar" : "Excluir"),
    el("button", { class: "btn ghost sm", onclick: async () => { if (await acaoMail(id, lida ? "unread" : "read")) render(); } }, lida ? "Marcar como não lida" : "Marcar como lida"),
    el("a", { class: "btn ghost sm", href: `https://mail.google.com/mail/u/0/#all/${id}`, target: "_blank", rel: "noopener" }, "Abrir no Gmail"));
  const msgEls = ms.map((m, i) => {
    const corpo = el("div", { class: "body" }, m.corpo);
    corpo.hidden = ms.length > 1 && i < ms.length - 1;
    const cab = el("header", { onclick: () => { corpo.hidden = !corpo.hidden; } }, avatar(m.de.nome),
      el("div", { style: "flex:1;min-width:0" }, el("b", {}, m.de.nome), el("div", { class: "m-snip" }, "para " + m.para)), el("span", { class: "m-date" }, new Date(m.data).toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })));
    return el("div", { class: "m-msg" }, cab, corpo, m.anexos.length ? el("div", { class: "m-snip", style: "padding:0 14px 10px" }, "Anexos: " + m.anexos.join(", ")) : "");
  });
  const resp = el("textarea", { placeholder: destino ? `Responder para ${destino}` : "Sem destinatário" });
  alvo.replaceChildren(
    el("h2", {}, ms[0].assunto || "(sem assunto)"),
    t.lead ? el("div", { class: "m-leadbox" }, pill("acc", t.lead.etapa), el("b", {}, t.lead.nome), el("span", { style: "flex:1" }), el("button", { class: "btn ghost sm", onclick: () => abrirLead(t.lead.ref) }, "Ver lead no CRM")) : "",
    bar, ...msgEls,
    el("div", { class: "m-reply" }, resp, el("div", { class: "row", style: "margin:0" }, el("button", { class: "btn", onclick: async () => {
      if (!resp.value.trim() || !destino) return;
      if (!confirm(`Enviar esta resposta para ${destino}?`)) return;
      const assunto = /^re:/i.test(ultima.assunto) ? ultima.assunto : "Re: " + ultima.assunto;
      const { ok, j } = await postJson("/api/gmail/send", { conta: st.conta, para: destino, assunto, corpo: resp.value, thread_id: id, in_reply_to: ultima.message_id, references: ultima.references });
      if (!ok) return alert(j.erro || "Falha ao enviar");
      resp.value = ""; abrirConversa(id, alvo);
    } }, "Enviar resposta"))));
}

document.addEventListener("DOMContentLoaded", () => {
  $("#cancelMail").addEventListener("click", () => $("#dlgMail").close());
  $("#formMail").addEventListener("submit", async () => {
    const d = Object.fromEntries(new FormData($("#formMail")));
    const { ok, j } = await postJson("/api/gmail/send", { conta: st.conta, ...d });
    if (!ok) alert(j.erro || "Falha ao enviar"); else { st.gm.pasta = "SENT"; render(); }
  });
});
