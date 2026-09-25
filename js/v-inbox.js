/* Inbox: e-mail (Gmail integrado ao CRM) e conversas de WhatsApp (somente leitura; o envio e sempre seu). */
"use strict";
const GM = { pasta: "INBOX", busca: "", sel: null };

VIEWS.inbox = async function (raiz) {
  const [aba, alvo] = (S.sub || "email").split("/");
  const sub = aba === "whatsapp" ? "whatsapp" : "email";
  cabecalho(raiz, "Inbox", NOMES[S.conta]);
  raiz.append(el("div", { class: "tabs", style: "margin-bottom:0" }, [["email", "E-mail"], ["whatsapp", "WhatsApp"]].map(([k, r]) => el("button", { class: "tab" + (sub === k ? " on" : ""), onclick: () => ir("inbox", k) }, r))));
  if (sub === "whatsapp") await inboxWhatsapp(raiz, alvo); else await inboxEmail(raiz);
};

/* ---------------- e-mail ---------------- */
async function inboxEmail(raiz) {
  let pastas;
  try { pastas = await api(`/api/gmail/pastas?conta=${S.conta}`); } catch (e) { return raiz.append(el("div", { class: "note", style: "margin-top:18px" }, e.message)); }
  if (pastas.erro) return raiz.append(el("div", { class: "note", style: "margin-top:18px" }, S.conta === "atlas" ? "Gmail da Atlas ainda não conectado. Quando criar a conta, rode py crm/atlas_gmail_auth.py e volte aqui." : pastas.erro));
  const box = el("div", { class: "inbox fade" });
  const lista = el("div", { class: "ib-lista" }), leitura = el("div", { class: "ib-ler" });
  const busca = el("input", { placeholder: "Buscar (ex.: from:nome, is:unread)", value: GM.busca, "aria-label": "Buscar e-mails" });
  busca.addEventListener("keydown", (e) => { if (e.key === "Enter") { GM.busca = busca.value; GM.sel = null; renderizar(); } });
  box.append(el("div", { class: "ib-pastas" }, botaoAcao("Escrever", escreverEmail, "btn", "plus"),
    pastas.pastas.map((p) => el("button", { class: "pasta" + (GM.pasta === p.id ? " on" : ""), onclick: () => { GM.pasta = p.id; GM.sel = null; GM.busca = ""; renderizar(); } }, p.nome, el("b", {}, p.nao_lidas || ""))),
    el("a", { class: "pasta", href: "https://mail.google.com/", target: "_blank", rel: "noopener", style: "margin-top:auto" }, "Abrir Gmail", icon("ext"))), lista, leitura);
  lista.append(el("div", { class: "ib-busca" }, busca), esqueleto(4, 64));
  raiz.append(box);
  box.classList.toggle("lendo", !!GM.sel);
  const r = await api(`/api/gmail/conversas?conta=${S.conta}&pasta=${GM.pasta}&busca=${encodeURIComponent(GM.busca)}`).catch((e) => ({ erro: e.message }));
  lista.replaceChildren(el("div", { class: "ib-busca" }, busca));
  if (r.erro) return lista.append(el("div", { class: "note", style: "margin:12px" }, r.erro));
  if (!r.itens.length) lista.append(vazio("Nenhuma conversa aqui"));
  for (const c of r.itens) {
    const it = el("div", { class: "msg-i" + (c.nao_lida ? " nl" : "") + (GM.sel === c.id ? " on" : ""), onclick: () => { GM.sel = c.id; box.classList.add("lendo"); $$(".msg-i", lista).forEach((x) => x.classList.remove("on")); it.classList.add("on"); it.classList.remove("nl"); lerConversa(c.id, leitura, box); } },
      avatar(c.pessoa), el("div", { style: "min-width:0" }, el("div", { class: "w" }, c.pessoa + (c.msgs > 1 ? ` (${c.msgs})` : "")), el("div", { class: "s" }, c.assunto), el("div", { class: "p" }, c.snippet),
        c.lead ? el("div", { style: "margin-top:4px" }, pill("ac", c.lead.etapa), " ", el("span", { class: "faint", style: "font-size:12px" }, c.lead.nome)) : ""),
      el("div", { class: "faint", style: "font-size:12px;white-space:nowrap" }, dataMail(c.data)));
    lista.append(it);
  }
  if (GM.sel) lerConversa(GM.sel, leitura, box); else leitura.append(vazio("Selecione uma conversa"));
}
const dataMail = (ms) => { const d = new Date(ms), h = new Date(); return d.toDateString() === h.toDateString() ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }); };

async function acaoMail(id, acao) {
  try { await post("/api/gmail/acao", { conta: S.conta, id, acao }, { silencioso: true }); return true; }
  catch (e) { toast(e.status === 403 ? "Precisa de autorização extra do Gmail: rode py crm/gmail_upgrade_auth.py " + S.conta : e.message, "err"); return false; }
}

async function lerConversa(id, alvo, box) {
  alvo.replaceChildren(esqueleto(3, 70));
  let t;
  try { t = await api(`/api/gmail/conversa?conta=${S.conta}&id=${id}`); } catch (e) { return alvo.replaceChildren(el("div", { class: "note" }, e.message)); }
  const ms = t.mensagens, ultima = ms[ms.length - 1];
  const emLixeira = ultima.rotulos.includes("TRASH"), lida = !ultima.rotulos.includes("UNREAD"), enviada = (m) => m.rotulos.includes("SENT");
  const outra = ms.slice().reverse().find((m) => !enviada(m)) || ultima;
  const destino = enviada(ultima) ? ((ultima.para.match(/[\w.+-]+@[\w.-]+/) || [""])[0]) : outra.de.email;
  const resp = el("textarea", { placeholder: destino ? "Responder para " + destino : "Sem destinatário", "aria-label": "Resposta" });
  let extra = "";
  if (t.lead) {
    const lr = await api(`/api/lead?ref=${encodeURIComponent(t.lead.ref)}`).catch(() => null);
    const ult = lr && lr.respostas.slice(-1)[0];
    extra = el("div", { class: "leadbox" }, pill("ac", t.lead.etapa), el("b", {}, t.lead.nome), ult ? clsPill(ult.classificacao) : "", el("span", { style: "flex:1" }), el("button", { class: "btn ghost sm", onclick: () => abrirLead(t.lead.ref) }, "Ver lead"));
  }
  alvo.replaceChildren(
    el("button", { class: "btn ghost sm so-mobile", onclick: () => { GM.sel = null; box.classList.remove("lendo"); renderizar(); } }, icon("back"), "Voltar"),
    el("h2", {}, ms[0].assunto || "(sem assunto)"), extra,
    el("div", { style: "display:flex;gap:6px;flex-wrap:wrap;margin:10px 0" },
      botaoAcao("Arquivar", async () => { if (await acaoMail(id, "archive")) { GM.sel = null; renderizar(); } }, "btn sec sm", "archive"),
      botaoAcao(emLixeira ? "Restaurar" : "Excluir", async () => { if (await acaoMail(id, emLixeira ? "untrash" : "trash")) { GM.sel = null; renderizar(); } }, "btn sec sm", "trash"),
      botaoAcao(lida ? "Marcar não lida" : "Marcar lida", async () => { if (await acaoMail(id, lida ? "unread" : "read")) renderizar(); }, "btn sec sm"),
      el("a", { class: "btn ghost sm", href: `https://mail.google.com/mail/u/0/#all/${id}`, target: "_blank", rel: "noopener" }, icon("ext"), "Gmail")),
    ms.map((m, i) => {
      const corpo = el("div", { class: "corpo" }, m.corpo);
      corpo.hidden = ms.length > 1 && i < ms.length - 1;
      return el("div", { class: "mail-b" }, el("header", { onclick: () => { corpo.hidden = !corpo.hidden; } }, avatar(m.de.nome),
        el("div", { style: "flex:1;min-width:0" }, el("b", {}, m.de.nome), el("div", { class: "faint", style: "font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" }, "para " + m.para)), el("span", { class: "faint", style: "font-size:12px" }, dataHora(new Date(m.data).toISOString()))),
        corpo, m.anexos.length ? el("div", { class: "faint", style: "padding:0 0 8px 44px;font-size:12px" }, "Anexos: " + m.anexos.join(", ")) : "");
    }),
    el("div", { class: "resp" }, resp, el("div", { class: "row-b", style: "margin:0" }, botaoAcao("Enviar resposta", async () => {
      if (!resp.value.trim() || !destino) return;
      if (!(await confirmar("Enviar esta resposta?", "Para " + destino + ". Será enviada do seu Gmail agora.", "Enviar"))) return;
      const assunto = /^re:/i.test(ultima.assunto) ? ultima.assunto : "Re: " + ultima.assunto;
      await post("/api/gmail/send", { conta: S.conta, para: destino, assunto, corpo: resp.value, thread_id: id, in_reply_to: ultima.message_id, references: ultima.references });
      toast("Resposta enviada", "ok"); resp.value = ""; lerConversa(id, alvo, box);
    }, "btn sm", "send"))));
}

function escreverEmail() {
  const para = el("input", { type: "email", placeholder: "destinatario@exemplo.com" }), ass = el("input", { placeholder: "Assunto" }), corpo = el("textarea", { style: "min-height:180px" });
  dialogo("Nova mensagem", el("div", {}, el("label", {}, "Para"), para, el("label", {}, "Assunto"), ass, el("label", {}, "Mensagem"), corpo), [
    el("button", { class: "btn ghost", onclick: fecharDialogo }, "Cancelar"),
    el("button", { class: "btn", onclick: async () => {
      if (!para.value || !ass.value || !corpo.value) return toast("Preencha todos os campos", "err");
      await post("/api/gmail/send", { conta: S.conta, para: para.value, assunto: ass.value, corpo: corpo.value });
      fecharDialogo(); toast("Enviado", "ok"); GM.pasta = "SENT"; renderizar();
    } }, "Enviar")]);
}

/* ---------------- WhatsApp (somente leitura) ---------------- */
async function inboxWhatsapp(raiz, alvoRef) {
  const [{ conversas }, cx] = await Promise.all([api(`/api/conversas?conta=${S.conta}`), api("/api/conexoes")]);
  const box = el("div", { class: "inbox fade" }), lista = el("div", { class: "ib-lista" }), leitura = el("div", { class: "ib-ler" });
  const ok = cx.whatsapp.estado === "conectado";
  const lateral = el("div", { class: "ib-pastas" }, el("div", { class: "eyebrow", style: "padding:6px 10px" }, "Conexão"),
    el("div", { style: "padding:0 10px 10px" }, pill(ok ? "ok" : "warn", ok ? "conectado" : cx.whatsapp.estado), el("div", { class: "faint", style: "font-size:12px;margin-top:8px;line-height:1.45" }, ok ? "O CRM só observa. O envio é sempre feito por você no seu WhatsApp." : "Conecte em Configurações para detectar envios e respostas sozinho.")),
    ok ? "" : el("a", { class: "btn sec sm", href: "#/" + S.conta + "/config", style: "margin:0 10px" }, "Conectar"));
  box.append(lateral, lista, leitura);
  raiz.append(box);
  if (alvoRef) box.classList.add("lendo");
  if (!conversas.length) lista.append(vazio("Nenhuma conversa ainda", ok ? "Quando você enviar a primeira mensagem, ela aparece aqui." : "Conecte o WhatsApp para acompanhar."));
  for (const c of conversas) {
    const it = el("div", { class: "msg-i" + (c.aguardando_voce ? " nl" : "") + (alvoRef === c.ref ? " on" : ""), onclick: () => ir("inbox", "whatsapp/" + c.ref) },
      avatar(c.nome), el("div", { style: "min-width:0" }, el("div", { class: "w" }, c.nome), el("div", { class: "p" }, (c.direcao === "saida" ? "Você: " : "") + c.ultima),
        el("div", { style: "margin-top:4px;display:flex;gap:6px" }, pill("", c.etapa), c.aguardando_voce ? pill("ac", "aguardando você") : "", c.classificacao ? clsPill(c.classificacao) : "")),
      el("div", { class: "faint", style: "font-size:12px" }, quando(c.quando)));
    lista.append(it);
  }
  if (!alvoRef) return leitura.append(vazio("Selecione uma conversa"));
  const r = await api(`/api/lead?ref=${encodeURIComponent(alvoRef)}`).catch(() => null);
  if (!r) return leitura.append(vazio("Conversa não encontrada"));
  const l = r.lead, msgs = r.whatsapp || [], link = l.telefone ? "https://wa.me/" + wapp(l.telefone) : "";
  const ultCls = (r.respostas || []).filter((x) => x.origem === "whatsapp").slice(-1)[0];
  const proxima = msgs.length && msgs[msgs.length - 1].direcao === "entrada" ? "Responder no WhatsApp" : (r.tarefas.find((t) => t.status === "pendente") ? "Follow-up " + r.tarefas.find((t) => t.status === "pendente").passo + " em " + new Date(r.tarefas.find((t) => t.status === "pendente").due_date + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "Aguardar resposta");
  leitura.append(el("button", { class: "btn ghost sm so-mobile", onclick: () => ir("inbox", "whatsapp") }, icon("back"), "Voltar"),
    el("div", { style: "display:flex;gap:12px;align-items:center" }, avatar(l.nome), el("div", { style: "flex:1;min-width:0" }, el("h2", { style: "margin:0" }, l.nome), el("div", { class: "faint", style: "font-size:13px" }, l.telefone || "")),
      el("button", { class: "btn ghost sm", onclick: () => abrirLead(alvoRef) }, "Ver lead")),
    el("div", { style: "display:flex;gap:6px;margin:12px 0;flex-wrap:wrap" }, pill("ac", l.etapa), ultCls ? clsPill(ultCls.classificacao) : "", pill("info", "Próxima ação: " + proxima)),
    el("div", { class: "thread", style: "margin:16px 0" }, msgs.length ? msgs.map((m) => el("div", { class: "bolha " + (m.direcao === "saida" ? "out" : "in") }, m.texto, el("small", {}, dataHora(m.created_at)))) : el("div", { class: "faint" }, "Nenhuma mensagem detectada ainda.")),
    link ? el("a", { class: "btn", href: link + (l.mensagem && !msgs.length ? "?text=" + encodeURIComponent(l.mensagem) : ""), target: "_blank", rel: "noopener" }, icon("chat"), "Abrir no WhatsApp") : "",
    el("div", { class: "faint", style: "font-size:12px;margin-top:10px" }, "O CRM não envia mensagens. Você envia no WhatsApp e o envio é detectado aqui."));
}
