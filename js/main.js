/* Orquestracao: rota, navegacao (lateral e barra inferior), badges, tema, aviso de novas respostas e saude do sistema. */
"use strict";
let TOKEN = 0;

function cabecalho(raiz, titulo, sub, acoes) {
  if (raiz && raiz.dataset.token !== String(TOKEN)) return;          // renderizacao antiga: ignora
  $("#ttl").textContent = titulo;
  $("#sub").textContent = sub || "";
  $("#acoes").replaceChildren(...(acoes ? [acoes] : []));
  document.title = titulo + " · " + NOMES[S.conta] + " · Captação de Leads";
}

async function renderizar() {
  const meu = ++TOKEN;
  document.body.classList.add("carregando");
  limparTimers();
  document.body.dataset.conta = S.conta;
  $$("#conta button").forEach((b) => b.classList.toggle("on", b.dataset.c === S.conta));
  const ativo = S.view;
  $$(".nav[data-v]").forEach((b) => b.classList.toggle("on", b.dataset.v === ativo));
  $$("#tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.v === ativo || (b.dataset.v === "mais" && ["painel", "aprendizado", "financeiro", "config"].includes(ativo))));
  const viewEl = $("#view");
  const raiz = el("div", { class: "fade" });
  raiz.dataset.token = String(meu);
  $("#ttl").textContent = TELAS[S.view];
  $("#sub").textContent = NOMES[S.conta];
  $("#acoes").replaceChildren();
  if (!viewEl.firstChild) viewEl.replaceChildren(esqueleto(4, 60));
  try {
    await VIEWS[S.view](raiz);
  } catch (e) {
    if (meu !== TOKEN) return;
    raiz.replaceChildren(el("div", { class: "note" }, "Não foi possível carregar: " + e.message), botaoAcao("Tentar de novo", renderizar, "btn sm sec", "refresh"));
  }
  if (meu !== TOKEN) return;
  viewEl.replaceChildren(raiz);
  document.body.classList.remove("carregando");
  $("#main").scrollTo({ top: 0 });
  atualizarBadges();
}

async function atualizarBadges() {
  try {
    const [a, r] = await Promise.all([api(`/api/acoes?conta=${S.conta}`), api(`/api/radar?conta=${S.conta}`)]);
    const b = (id, n, hot) => { const e = $(id); if (!e) return; e.textContent = n || ""; e.classList.toggle("hot", !!hot && n > 0); };
    b("#b-hoje", a.total, true);
    b("#b-radar", r.total, r.urgente.length > 0);
    b("#b-inbox", a.resumo.responder, true);
    [["#t-hoje", a.total], ["#t-radar", r.total], ["#t-inbox", a.resumo.responder]].forEach(([id, n]) => { const e = $(id); if (e) { e.hidden = !n; e.textContent = n; } });
  } catch (e) { /* servidor reiniciando */ }
}

async function atualizarSaude() {
  try {
    const s = await api("/api/saude");
    const falhas = Object.entries(s.workers).filter(([, v]) => !v.ok).length + (s.ia.falhas_seguidas ? 1 : 0) + (["erro", "desconectado", "falha"].includes(s.whatsapp.estado) ? 1 : 0);
    const el_ = $("#saude");
    el_.className = "saude" + (falhas ? " atencao" : "");
    el_.lastChild.textContent = falhas ? falhas + " ponto(s) de atenção" : "Sistema saudável";
    el_.onclick = () => ir("config", "sistema");
  } catch (e) {
    const el_ = $("#saude"); el_.className = "saude ruim"; el_.lastChild.textContent = "Servidor indisponível";
  }
}

/* ---- aviso de novas respostas (atualiza a tela e notifica) ---- */
let ultimaResp = null;
async function pulso() {
  try {
    const p = await api("/api/ping");
    if (ultimaResp !== null && p.ultima_resposta > ultimaResp) {
      const cl = p.ultima && CLS[p.ultima.classificacao] ? CLS[p.ultima.classificacao][1] : "nova resposta";
      toast("Nova resposta: " + cl, "ok");
      if ("Notification" in window && Notification.permission === "granted") new Notification("Captação de Leads: " + cl, { body: ((p.ultima && p.ultima.texto) || "").slice(0, 120) });
      const digitando = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
      if (!$("#dlg").open && !$("#overlay").firstChild && !digitando && !["config", "financeiro"].includes(S.view)) renderizar(); else atualizarBadges();
    }
    ultimaResp = p.ultima_resposta;
  } catch (e) { /* servidor reiniciando */ }
}

function menuMais() {
  const item = (v, rot, ic) => el("button", { class: "nav", onclick: () => { $("#overlay").replaceChildren(); ir(v); } }, el("span", { "data-ic": ic }), rot);
  const conta = el("div", { class: "conta", style: "margin:0 0 12px" }, ["atlas", "nexora"].map((c) => el("button", { class: S.conta === c ? "on" : "", onclick: () => { $("#overlay").replaceChildren(); ir(S.view, "", c); } }, NOMES[c])));
  const folha = el("div", { class: "sheet", onclick: (e) => { if (e.target === folha) $("#overlay").replaceChildren(); } }, el("div", {}, conta, item("painel", "Painel", "chart"), item("aprendizado", "Aprendizado", "learn"), item("financeiro", "Financeiro", "wallet"), item("config", "Configurações", "settings"),
    el("button", { class: "nav", onclick: alternarTema }, el("span", { "data-ic": "sun" }), "Alternar tema")));
  $("#overlay").replaceChildren(folha);
  montarIcones(folha);
}

function alternarTema() {
  const d = document.documentElement, novo = d.dataset.theme === "light" ? "dark" : "light";
  d.dataset.theme = novo;
  localStorage.setItem("crm.theme", novo);
  document.querySelector('meta[name="theme-color"]').content = novo === "light" ? "#fbfaf8" : "#08080a";
  renderizar();
}

function iniciar() {
  document.documentElement.dataset.theme = localStorage.getItem("crm.theme") || "dark";
  montarIcones();
  lerRota();
  $$("#conta button").forEach((b) => b.addEventListener("click", () => { localStorage.setItem("crm.conta", b.dataset.c); ir(S.view, S.sub, b.dataset.c); }));
  $$(".nav[data-v]").forEach((b) => b.addEventListener("click", () => ir(b.dataset.v)));
  $$("#tabbar button").forEach((b) => b.addEventListener("click", () => (b.dataset.v === "mais" ? menuMais() : ir(b.dataset.v))));
  $("#tema").addEventListener("click", alternarTema);
  window.addEventListener("hashchange", () => { lerRota(); localStorage.setItem("crm.view", S.view); localStorage.setItem("crm.conta", S.conta); fecharGaveta(); renderizar(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharGaveta(); });
  document.addEventListener("click", () => { if ("Notification" in window && Notification.permission === "default") Notification.requestPermission(); }, { once: true });
  if (!location.hash) history.replaceState(null, "", "#/" + [S.conta, S.view].join("/"));
  renderizar();
  atualizarSaude(); pulso();
  setInterval(pulso, 15000);
  setInterval(atualizarSaude, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { atualizarBadges(); atualizarSaude(); } });
}
iniciar();
