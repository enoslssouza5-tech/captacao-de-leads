/* Nucleo: helpers de DOM, API, estado/rota, formatacao, icones, avisos e dialogos. JavaScript puro, sem dependencias. */
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const NOMES = { atlas: "Atlas", nexora: "Nexora" };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;            // so para SVG interno controlado; nunca dados do usuario
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat(Infinity)) if (c !== false && c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
}

/* ---------- icones (traco, 24x24) ---------- */
const IC = {
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
  today: '<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M8 3v4M16 3v4M3.5 10h17"/><path d="m9 15 2 2 4-4"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.9c1.9.7 3.1 2.4 3.5 5.1"/>',
  radar: '<circle cx="12" cy="12" r="9"/><path d="M12 12 18.5 5.5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><path d="M12 7a5 5 0 0 1 5 5"/>',
  inbox: '<path d="M3.5 13.5 6 5.5h12l2.5 8"/><path d="M3.5 13.5V18a1.5 1.5 0 0 0 1.5 1.5h14a1.5 1.5 0 0 0 1.5-1.5v-4.5H15a3 3 0 0 1-6 0Z"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/>',
  learn: '<path d="M3 7.5 12 3l9 4.5-9 4.5Z"/><path d="M7 10v5c0 1.7 2.2 3 5 3s5-1.3 5-3v-5"/>',
  wallet: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18M16 14.5h2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3v2.2M12 18.8V21M4.6 6.6l1.6 1.6M17.8 15.8l1.6 1.6M3 12h2.2M18.8 12H21M4.6 17.4l1.6-1.6M17.8 8.2l1.6-1.6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',
  more: '<circle cx="5" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="19" cy="12" r="1.5" fill="currentColor"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-3.8-3.8"/>',
  send: '<path d="M21 3 10 14"/><path d="m21 3-7 18-4-7-7-4Z"/>',
  check: '<path d="m4.5 12.5 5 5 10-11"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  mail: '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="m4 7.5 8 6 8-6"/>',
  chat: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4A2.5 2.5 0 0 1 4 13.5Z"/>',
  ext: '<path d="M14 4h6v6M20 4 11 13"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
  copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M15.5 8.5V6A2.5 2.5 0 0 0 13 3.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5"/>',
  alert: '<path d="M12 4 2.8 19.5h18.4Z"/><path d="M12 10v4.5M12 17.2v.1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  trash: '<path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/>',
  archive: '<rect x="3" y="4.5" width="18" height="4.5" rx="1.5"/><path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M10 13h4"/>',
  star: '<path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8Z"/>',
  bolt: '<path d="M13 2.5 5 13.5h6l-1 8 8-11h-6Z"/>',
  phone: '<path d="M6 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6.5 6.5l1.5-2 4 1.5v3a2 2 0 0 1-2 2A16 16 0 0 1 4 5.5a2 2 0 0 1 2-2Z"/>',
};
function icon(nome, cls) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "1.7");
  s.setAttribute("stroke-linecap", "round");
  s.setAttribute("stroke-linejoin", "round");
  s.setAttribute("aria-hidden", "true");
  s.setAttribute("class", "ic" + (cls ? " " + cls : ""));
  s.innerHTML = IC[nome] || "";
  return s;
}
function montarIcones(raiz = document) {
  $$("[data-ic]", raiz).forEach((n) => { if (!n.firstChild) n.replaceChildren(icon(n.dataset.ic)); });
}

/* ---------- API ---------- */
async function api(url) {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  let j = null;
  try { j = await r.json(); } catch (e) { /* corpo vazio */ }
  if (!r.ok) { const err = new Error((j && j.erro) || "Erro " + r.status); err.status = r.status; throw err; }
  return j;
}
async function post(url, body = {}, opts = {}) {
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(j.erro || "Erro " + r.status), { status: r.status });
    return j;
  } catch (e) {
    if (!opts.silencioso) toast(e.message, "err");
    throw e;
  }
}

/* ---------- estado e rota (#/conta/tela/sub) ---------- */
const S = { conta: "atlas", view: "hoje", sub: "", dias: 30 };
const TELAS = { hoje: "Hoje", leads: "Leads", radar: "Radar", inbox: "Inbox", painel: "Painel", aprendizado: "Aprendizado", financeiro: "Financeiro", config: "Configurações" };
function lerRota() {
  const p = (location.hash || "").replace(/^#\/?/, "").split("/").filter(Boolean);
  const conta = ["atlas", "nexora"].includes(p[0]) ? p[0] : (localStorage.getItem("crm.conta") || "atlas");
  const view = TELAS[p[1]] ? p[1] : (localStorage.getItem("crm.view") || "hoje");
  Object.assign(S, { conta, view: TELAS[view] ? view : "hoje", sub: p.slice(2).join("/") });
}
function ir(view, sub = "", conta = S.conta) {
  location.hash = "#/" + [conta, view, sub].filter(Boolean).join("/");
}

/* ---------- formatacao ---------- */
const nf = new Intl.NumberFormat("pt-BR");
const num = (n) => (n == null ? "—" : nf.format(n));
const money = (cents, moeda = S.conta === "nexora" ? "USD" : "BRL") =>
  cents == null ? "—" : new Intl.NumberFormat(moeda === "USD" ? "en-US" : "pt-BR", { style: "currency", currency: moeda, maximumFractionDigits: cents % 100 ? 2 : 0 }).format(cents / 100);
function quando(iso) {
  if (!iso) return "";
  const d = new Date(iso), s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "agora";
  if (s < 3600) return Math.floor(s / 60) + " min";
  if (s < 86400) return Math.floor(s / 3600) + " h";
  if (s < 86400 * 7) return Math.floor(s / 86400) + " d";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}
const dataHora = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "");
const soma = (o) => Object.values(o || {}).reduce((a, b) => a + b, 0);
const iniciais = (t) => (t || "?").trim().charAt(0).toUpperCase();
const CORES = ["#e0573b", "#3b82e0", "#2fa36b", "#a05be0", "#d99a1c", "#e0439a", "#2aa6b8"];
const corDe = (t) => CORES[[...(t || "?")].reduce((a, c) => a + c.charCodeAt(0), 0) % CORES.length];
const avatar = (nome) => el("div", { class: "av", style: "background:" + corDe(nome) }, iniciais(nome));

const CLS = { interessado: ["ok", "Interessado"], duvida: ["info", "Dúvida"], reuniao: ["ac", "Quer conversar"], pendente: ["warn", "Pendente"], recusou: ["err", "Recusou"], automatica: ["", "Resposta automática"], bounce: ["err", "E-mail devolvido"] };
const pill = (tipo, txt) => el("span", { class: "pill " + (tipo || "") }, txt);
const clsPill = (c) => (CLS[c] ? pill(CLS[c][0], CLS[c][1]) : pill("warn", "A classificar"));
const TIPO_DOR = { sem_site: "Sem site", site_desatualizado: "Site desatualizado", site_confuso: "Site confuso", sem_conversao: "Sem conversão", reputacao_sem_captacao: "Reputação sem captação",
  anuncio_sem_pagina: "Anúncio sem página", concorrente_a_frente: "Concorrente à frente", sem_landing: "Sem landing", landing_com_problema: "Landing com problema", landing_incerta: "Landing incerta", site_ok: "Site sem problema", sem_dado: "Sem classificação" };
const nomeDor = (d) => TIPO_DOR[d] || d || "Sem classificação";
const canalIc = (c) => icon(c === "whatsapp" ? "chat" : "mail");

/* ---------- avisos e dialogos ---------- */
function toast(msg, tipo = "") {
  const t = el("div", { class: "toast " + tipo, role: "status" }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), tipo === "err" ? 5200 : 2600);
}
function dialogo(titulo, corpo, botoes) {
  const d = $("#dlg");
  d.replaceChildren(el("h3", {}, titulo), corpo, el("div", { class: "row-b" }, botoes));
  if (!d.open) d.showModal();
  return d;
}
const fecharDialogo = () => { const d = $("#dlg"); if (d.open) d.close(); d.replaceChildren(); };
function confirmar(titulo, texto, rotulo = "Confirmar") {
  return new Promise((res) => {
    dialogo(titulo, el("p", { class: "muted" }, texto), [
      el("button", { class: "btn ghost", onclick: () => { fecharDialogo(); res(false); } }, "Cancelar"),
      el("button", { class: "btn", onclick: () => { fecharDialogo(); res(true); } }, rotulo),
    ]);
  });
}
const esqueleto = (n = 3, h = 56) => el("div", { class: "fade" }, Array.from({ length: n }, () => el("div", { class: "sk", style: `height:${h}px;margin-bottom:10px` })));
const vazio = (titulo, texto) => el("div", { class: "empty" }, el("b", {}, titulo), texto || "");
async function copiar(txt) { try { await navigator.clipboard.writeText(txt); toast("Copiado"); } catch (e) { toast("Não foi possível copiar", "err"); } }
function botaoAcao(rotulo, fn, cls = "btn sm", ic) {
  const b = el("button", { class: cls }, ic ? icon(ic) : "", rotulo);
  b.addEventListener("click", async (e) => {
    e.stopPropagation();
    b.disabled = true;
    try { await fn(e); } finally { b.disabled = false; }
  });
  return b;
}
const toggle = (on, fn) => el("button", { class: "toggle" + (on ? " on" : ""), role: "switch", "aria-checked": String(!!on), onclick: fn });
