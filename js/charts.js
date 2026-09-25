/* Graficos em SVG puro (sem bibliotecas). Cada funcao devolve um elemento DOM. Sem dados suficientes, quem chama mostra "dados insuficientes". */
"use strict";
const SVGNS = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, ...kids) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
  for (const c of kids.flat()) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
}
const acento = () => getComputedStyle(document.body).getPropertyValue("--ac").trim() || "#ff6a2b";
const cssv = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();

/* Interpolacao monotonica (Fritsch-Carlson, como d3.curveMonotoneX): suaviza sem criar picos nem platos que os dados nao tem. */
function caminhoSuave(pts) {
  const n = pts.length;
  if (n < 2) return "";
  if (n === 2) return "M" + pts[0][0] + "," + pts[0][1] + " L" + pts[1][0] + "," + pts[1][1];
  const dx = [], m = [], t = new Array(n);
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0] || 1e-6; m[i] = (pts[i + 1][1] - pts[i][1]) / dx[i]; }
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], h = Math.hypot(a, b);
    if (h > 3) { const k = 3 / h; t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  let d = "M" + pts[0][0] + "," + pts[0][1];
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += " C" + (pts[i][0] + h) + "," + (pts[i][1] + h * t[i]) + " " + (pts[i + 1][0] - h) + "," + (pts[i + 1][1] - h * t[i + 1]) + " " + pts[i + 1][0] + "," + pts[i + 1][1];
  }
  return d;
}

/* ---- mini grafico de linha (sob os indicadores) ---- */
function spark(valores, cor) {
  const W = 120, H = 26, max = Math.max(...valores, 1);
  const pts = valores.map((v, i) => [(i / Math.max(valores.length - 1, 1)) * W, H - 2 - (v / max) * (H - 6)]);
  const s = svg("svg", { class: "spark", viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });
  if (valores.some((v) => v > 0)) s.append(svg("path", { d: caminhoSuave(pts), fill: "none", stroke: cor || acento(), "stroke-width": 1.6, "vector-effect": "non-scaling-stroke", opacity: ".9" }));
  else s.append(svg("line", { x1: 0, y1: H - 2, x2: W, y2: H - 2, stroke: cssv("--line2"), "stroke-width": 1, "stroke-dasharray": "3 4", "vector-effect": "non-scaling-stroke" }));
  return s;
}

/* ---- area/linhas multi-serie com legenda clicavel e tooltip ---- */
function graficoTempo(datas, series, opts = {}) {
  const wrap = el("div", { class: "chart" });
  const ativa = new Set(series.map((s) => s.chave));
  const legenda = el("div", { class: "legend" });
  const corpo = el("div");
  const tip = el("div", { class: "tip", hidden: true });
  wrap.append(legenda, corpo, tip);
  const W = 1000, H = 250, m = { t: 12, r: 8, b: 26, l: 30 };

  function desenhar() {
    corpo.replaceChildren();
    const vis = series.filter((s) => ativa.has(s.chave));
    const max = Math.max(1, ...vis.flatMap((s) => s.valores));
    const topo = Math.max(4, Math.ceil(max / 4) * 4);
    const x = (i) => m.l + (i / Math.max(datas.length - 1, 1)) * (W - m.l - m.r);
    const y = (v) => H - m.b - (v / topo) * (H - m.t - m.b);
    const g = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.rotulo || "Evolução ao longo do tempo" });
    const eixo = svg("g", { class: "axis" });
    for (let i = 0; i <= 4; i++) {
      const v = (topo / 4) * i;
      eixo.append(svg("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: cssv("--line"), "stroke-width": 1 }), svg("text", { x: m.l - 8, y: y(v) + 3.5, "text-anchor": "end" }, Math.round(v)));
    }
    const passo = Math.ceil(datas.length / 7);
    datas.forEach((d, i) => { if (i % passo === 0 || i === datas.length - 1) eixo.append(svg("text", { x: x(i), y: H - 6, "text-anchor": i === 0 ? "start" : i === datas.length - 1 ? "end" : "middle" }, d.slice(8) + "/" + d.slice(5, 7))); });
    g.append(eixo);
    vis.forEach((s, idx) => {
      const pts = s.valores.map((v, i) => [x(i), y(v)]);
      const id = "g" + Math.random().toString(36).slice(2, 7);
      const def = svg("defs", {}, svg("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 }, svg("stop", { offset: "0%", "stop-color": s.cor, "stop-opacity": idx === 0 ? ".28" : ".1" }), svg("stop", { offset: "100%", "stop-color": s.cor, "stop-opacity": "0" })));
      g.append(def, svg("path", { d: caminhoSuave(pts) + ` L${x(datas.length - 1)},${y(0)} L${x(0)},${y(0)} Z`, fill: `url(#${id})` }),
        svg("path", { d: caminhoSuave(pts), fill: "none", stroke: s.cor, "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }));
    });
    const guia = svg("line", { y1: m.t, y2: H - m.b, stroke: cssv("--line2"), "stroke-width": 1, opacity: 0 });
    const pontos = vis.map((s) => svg("circle", { r: 3.5, fill: s.cor, stroke: cssv("--bg"), "stroke-width": 2, opacity: 0 }));
    const area = svg("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" });
    g.append(guia, ...pontos, area);
    const mover = (ev) => {
      const r = g.getBoundingClientRect();
      const px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) / r.width * W;
      const i = Math.max(0, Math.min(datas.length - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (datas.length - 1))));
      guia.setAttribute("x1", x(i)); guia.setAttribute("x2", x(i)); guia.setAttribute("opacity", 1);
      vis.forEach((s, k) => { pontos[k].setAttribute("cx", x(i)); pontos[k].setAttribute("cy", y(s.valores[i])); pontos[k].setAttribute("opacity", 1); });
      tip.hidden = false;
      tip.replaceChildren(el("b", {}, new Date(datas[i] + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })), ...vis.map((s) => el("div", {}, el("span", {}, s.rotulo), el("b", { style: "display:inline;margin:0" }, s.valores[i]))));
      const cx = (x(i) / W) * r.width, larg = tip.offsetWidth;
      tip.style.left = Math.min(Math.max(cx - larg / 2, 0), r.width - larg) + "px";
      tip.style.top = "8px";
    };
    const sair = () => { tip.hidden = true; guia.setAttribute("opacity", 0); pontos.forEach((p) => p.setAttribute("opacity", 0)); };
    area.addEventListener("pointermove", mover); area.addEventListener("pointerleave", sair);
    area.addEventListener("touchmove", mover, { passive: true }); area.addEventListener("touchend", sair);
    corpo.append(g);
  }
  series.forEach((s) => legenda.append(el("button", { class: "", onclick: (e) => {
    if (ativa.has(s.chave)) { if (ativa.size > 1) ativa.delete(s.chave); } else ativa.add(s.chave);
    e.currentTarget.classList.toggle("off", !ativa.has(s.chave));
    desenhar();
  } }, el("i", { style: "background:" + s.cor }), s.rotulo, el("b", { class: "faint", style: "font-weight:600" }, s.valores.reduce((a, b) => a + b, 0)))));
  desenhar();
  return wrap;
}

/* ---- funil em fluxo: barras proporcionais ligadas por faixas curvas, conversao entre etapas ---- */
function funilFluxo(funil) {
  const W = 720, H = 210, cols = funil.length, larg = 64, gap = (W - cols * larg) / (cols - 1), max = Math.max(...funil.map((f) => f.n), 1);
  const cor = acento();
  const g = svg("svg", { viewBox: `0 0 ${W} ${H + 60}`, role: "img", "aria-label": "Funil de conversão" });
  const alt = (n) => Math.max(n ? 6 : 2, (n / max) * H);
  funil.forEach((f, i) => {
    const x = i * (larg + gap), h = alt(f.n), y = (H - h) / 2 + 10;
    if (i < cols - 1) {
      const p = funil[i + 1], h2 = alt(p.n), y2 = (H - h2) / 2 + 10, x2 = (i + 1) * (larg + gap);
      const c = (x + larg + x2) / 2;
      g.append(svg("path", { d: `M${x + larg},${y} C${c},${y} ${c},${y2} ${x2},${y2} L${x2},${y2 + h2} C${c},${y2 + h2} ${c},${y + h} ${x + larg},${y + h} Z`, fill: cor, opacity: ".16" }));
      if (p.conv != null) g.append(svg("text", { x: c, y: 12, "text-anchor": "middle", fill: cssv("--tx2"), "font-size": 11.5, "font-weight": 600 }, p.conv + "%"));
    }
    g.append(svg("rect", { x, y, width: larg, height: h, rx: 6, fill: cor, opacity: i === 0 ? ".42" : (.5 + .5 * (i / (cols - 1))).toFixed(2) }));
    g.append(svg("text", { x: x + larg / 2, y: H + 30, "text-anchor": "middle", fill: cssv("--tx"), "font-size": 20, "font-weight": 560 }, f.n),
      svg("text", { x: x + larg / 2, y: H + 48, "text-anchor": "middle", fill: cssv("--tx3"), "font-size": 11 }, f.etapa));
    if (f.perdidos) g.append(svg("text", { x: x + larg / 2, y: H + 62, "text-anchor": "middle", fill: cssv("--err"), "font-size": 10.5 }, "−" + f.perdidos + " perdido" + (f.perdidos > 1 ? "s" : "")));
  });
  return el("div", { class: "chart" }, g);
}

/* ---- barras horizontais ranqueadas; itens sem amostra ficam apagados e dizem "dados insuficientes" ---- */
function barrasH(itens, opts = {}) {
  const max = Math.max(...itens.map((i) => i.valor || 0), opts.max || 0, 1);
  return el("div", {}, itens.map((i) => el("div", { class: "bar-h" + (i.insuficiente ? " fraco" : "") },
    el("span", { class: i.insuficiente ? "faint" : "" }, i.rotulo),
    el("div", { class: "t" }, el("i", { style: `width:${i.insuficiente ? 0 : Math.max(2, ((i.valor || 0) / max) * 100)}%` })),
    el("span", { class: "v" }, i.insuficiente ? "dados insuficientes" : i.texto != null ? i.texto : i.valor))));
}

/* ---- barras verticais (horario, dia da semana) ---- */
function barrasV(itens, opts = {}) {
  const W = 720, H = 150, n = itens.length, bw = (W - 20) / n, max = Math.max(...itens.map((i) => i.valor || 0), 1);
  const g = svg("svg", { viewBox: `0 0 ${W} ${H + 24}`, role: "img", "aria-label": opts.rotulo || "Distribuição" });
  itens.forEach((it, i) => {
    const h = it.valor ? Math.max(3, (it.valor / max) * H) : 0, x = 10 + i * bw + bw * 0.18;
    g.append(svg("rect", { x, y: H - h, width: bw * 0.64, height: h, rx: 3, fill: acento(), opacity: it.valor ? (0.35 + 0.65 * (it.valor / max)).toFixed(2) : 0 }),
      svg("rect", { x, y: H, width: bw * 0.64, height: 0.1, fill: cssv("--line2") }));
    if (opts.mostrarTodos || i % (n > 12 ? 3 : 1) === 0) g.append(svg("text", { x: x + bw * 0.32, y: H + 16, "text-anchor": "middle", fill: cssv("--tx3"), "font-size": 10.5 }, it.rotulo));
    g.append(svg("title", {}, it.rotulo + ": " + (it.dica || it.valor)));
  });
  return el("div", { class: "chart" }, g);
}

/* ---- anel de progresso ---- */
function anel(pct, tam = 44, largura = 4, texto) {
  const r = (tam - largura) / 2, c = 2 * Math.PI * r, p = Math.max(0, Math.min(100, pct || 0));
  const cor = p >= 70 ? cssv("--ok") : p >= 45 ? cssv("--warn") : cssv("--tx3");
  const s = svg("svg", { width: tam, height: tam, viewBox: `0 0 ${tam} ${tam}` },
    svg("circle", { cx: tam / 2, cy: tam / 2, r, fill: "none", stroke: cssv("--line2"), "stroke-width": largura }),
    svg("circle", { cx: tam / 2, cy: tam / 2, r, fill: "none", stroke: cor, "stroke-width": largura, "stroke-linecap": "round", "stroke-dasharray": `${(p / 100) * c} ${c}`, transform: `rotate(-90 ${tam / 2} ${tam / 2})` }));
  return el("div", { class: "ring", style: `width:${tam}px;height:${tam}px` }, s, el("b", { style: `font-size:${Math.round(tam / 3.6)}px` }, texto != null ? texto : Math.round(p)));
}

/* ---- barras empilhadas por mes (recebido x a receber) ---- */
function barrasEmpilhadas(meses, fmt) {
  const W = 720, H = 170, n = meses.length, bw = (W - 20) / n, max = Math.max(...meses.map((m) => m.recebido + m.a_receber), 1);
  const g = svg("svg", { viewBox: `0 0 ${W} ${H + 26}`, role: "img", "aria-label": "Recebido e a receber por mês" });
  meses.forEach((m, i) => {
    const x = 10 + i * bw + bw * 0.2, w = bw * 0.6, hr = (m.recebido / max) * H, ha = (m.a_receber / max) * H;
    if (m.recebido) g.append(svg("rect", { x, y: H - hr, width: w, height: hr, rx: 4, fill: acento() }));
    if (m.a_receber) g.append(svg("rect", { x, y: H - hr - ha, width: w, height: ha, rx: 4, fill: acento(), opacity: ".3" }));
    g.append(svg("text", { x: x + w / 2, y: H + 17, "text-anchor": "middle", fill: m.futuro ? cssv("--tx3") : cssv("--tx2"), "font-size": 11 }, ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][+m.mes.slice(5) - 1]),
      svg("title", {}, `${m.mes}: recebido ${fmt(m.recebido)}${m.a_receber ? ", a receber " + fmt(m.a_receber) : ""}`));
  });
  return el("div", { class: "chart" }, g);
}

/* ---- tendencia (variacao entre a primeira e a segunda metade do periodo) ---- */
function tendenciaTxt(valor, unidade = "") {
  if (valor == null || valor === 0) return el("div", { class: "delta" }, "estável");
  return el("div", { class: "delta " + (valor > 0 ? "up" : "down") }, (valor > 0 ? "▲ +" : "▼ ") + valor + unidade + " vs. período anterior");
}
