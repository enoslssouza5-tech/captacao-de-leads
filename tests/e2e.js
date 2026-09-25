// Teste ponta a ponta da interface (navegador real, Chromium). Roda contra um servidor de TESTE isolado (banco temporario).
// Uso (pelo test_e2e_ui.py): node e2e.js <BASE_URL>
const path = require("path");
const { chromium } = require(path.join(__dirname, "..", "..", "node_modules", "playwright"));

const BASE = process.argv[2];
const R = { passou: [], falhou: [], erros_js: [] };
let DIAG = "";
const ok = (nome) => R.passou.push(nome);
const falha = (nome, det) => R.falhou.push(nome + (det ? " :: " + det : ""));
async function checa(nome, fn) { try { const r = await fn(); if (r === false) falha(nome, DIAG); else ok(nome); DIAG = ""; } catch (e) { falha(nome, String(e.message || e).split("\n")[0] + " | " + DIAG); DIAG = ""; } }

async function api(p, corpo) {
  const r = await fetch(BASE + p, corpo === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  return r.json();
}
const texto = async (page, sel = "#view") => { const t = await page.locator(sel).innerText(); DIAG = t.replace(/\s+/g, " ").slice(0, 260); return t; };
async function ir(page, hash) { await page.evaluate((h) => { location.hash = h; }, hash); await page.waitForFunction(() => !document.body.classList.contains("carregando"), null, { timeout: 15000 }); await page.waitForTimeout(250); }

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 860 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => R.erros_js.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) R.erros_js.push("console: " + m.text()); });
  page.on("dialog", (d) => d.accept());

  await page.goto(BASE + "/#/atlas/hoje");
  await page.waitForFunction(() => !document.body.classList.contains("carregando"), null, { timeout: 15000 });

  await checa("Hoje vazio mostra 0 ações e mensagem de tudo em dia", async () => /0\s*\n?ações hoje|0[\s\S]*ações hoje/.test(await texto(page)) && /Tudo em dia/.test(await texto(page)));

  // --- criar lead pela interface ---
  await ir(page, "#/atlas/leads");
  await checa("Novo lead pela interface", async () => {
    await page.getByRole("button", { name: /Novo lead/ }).click();
    const d = page.locator("#dlg");
    await d.locator("input").first().waitFor();
    await d.locator('input[name="nome"]').fill("Locadora E2E");
    await d.locator('input[name="telefone"]').fill("(77) 99111-2222");
    await d.locator('input[name="avaliacoes"]').fill("120");
    await d.getByRole("button", { name: "Salvar" }).click();
    await page.waitForTimeout(600);
    return /Locadora E2E/.test(await texto(page));
  });
  const leadId = (await api("/api/board?conta=atlas&canal=whatsapp")).cards.Novo[0].id.slice(1);
  await checa("Lead duplicado é recusado com aviso", async () => {
    const r = await fetch(BASE + "/api/leads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ conta: "atlas", canal: "whatsapp", nome: "Outro", telefone: "(77) 99111-2222" }) });
    return r.status === 409;
  });

  // --- lead pronto aparece em Hoje com link do WhatsApp ---
  await api(`/api/leads/${leadId}/editar`, { etapa: "Pronto", mensagem: "Oi, me chamo Enos. Vi 120 avaliacoes e nenhum site. Posso te mostrar uma ideia?", dor: "120 avaliacoes e nenhum site", tipo_dor: "sem_site" });
  await ir(page, "#/atlas/hoje/whatsapp");
  await checa("Hoje: lead pronto vira ação 'Enviar WhatsApp' com link wa.me e texto", async () => {
    const link = await page.locator('a:has-text("Abrir no WhatsApp")').first().getAttribute("href");
    return /^https:\/\/wa\.me\/5577991112222\?text=/.test(link) && decodeURIComponent(link).includes("me chamo Enos");
  });

  // --- envio detectado (o que o observador faz) ---
  await api("/api/wa/event", { direcao: "saida", telefone: "5577991112222", texto: "Oi, me chamo Enos. Vi 120 avaliacoes e nenhum site. Posso te mostrar uma ideia?", tipo: "chat" });
  await ir(page, "#/atlas/leads");
  await checa("Funil: envio detectado move o card para Contatado com próxima ação de follow-up", async () => {
    const t = await texto(page);
    return /Contatado\s*1/.test(t.replace(/\n/g, " ")) && /Follow-up em 3 dias/.test(t);
  });
  await checa("Hoje não lista mais o lead enviado", async () => { await ir(page, "#/atlas/hoje"); return /Tudo em dia|0\s+ações hoje/.test((await texto(page)).replace(/\n/g, " ")); });

  // --- resposta: quer conversar -> Negociando, aparece em Responder e no Radar ---
  await api(`/api/leads/${leadId}/resposta`, { texto: "Tenho interesse, pode me ligar amanhã?", classificacao: "reuniao" });
  await ir(page, "#/atlas/hoje/responder");
  await checa("Hoje: resposta que quer conversar aparece em Responder", async () => /Locadora E2E/.test(await texto(page)) && /Quer conversar/.test(await texto(page)));
  await checa("Painel: funil e indicadores refletem o lead (1 lead, 1 contatado, 1 resposta, 1 negociação)", async () => {
    await ir(page, "#/atlas/painel");
    const t = (await texto(page)).replace(/\n/g, " ");
    return /LEADS\s*1/.test(t) && /CONTATADOS\s*1/.test(t) && /RESPOSTAS\s*1/.test(t) && /NEGOCIAÇÕES\s*1/.test(t);
  });
  await checa("Conversa de WhatsApp mostra mensagens enviadas e recebidas", async () => {
    await ir(page, "#/atlas/inbox/whatsapp/c" + leadId);
    const t = await texto(page);
    return /Vi 120 avaliacoes/.test(t) && /Próxima ação/.test(t) && /Locadora E2E/.test(t);
  });

  // --- gaveta do lead ---
  await checa("Gaveta do lead abre com dor, mensagem e regras validadas", async () => {
    await ir(page, "#/atlas/leads");
    await page.locator(".kc", { hasText: "Locadora E2E" }).first().click();
    await page.locator(".drawer").waitFor();
    await page.waitForTimeout(600);
    const t = await texto(page, ".drawer");
    return /120 avaliacoes e nenhum site/.test(t) && /dentro das regras/.test(t);
  });
  await checa("Gaveta: abas Conversa, Follow-ups e Atividade", async () => {
    for (const [aba, esperado] of [["Conversa", /Tenho interesse/], ["Follow-ups", /Follow-up 1/], ["Atividade", /Contatado/]]) {
      await page.locator(".drawer .tab", { hasText: aba }).click();
      await page.waitForTimeout(200);
      if (!esperado.test(await texto(page, ".drawer"))) return false;
    }
    return true;
  });
  await page.keyboard.press("Escape");
  await checa("Esc fecha a gaveta", async () => (await page.locator(".drawer").count()) === 0);

  // --- Nexora e aprovação de e-mail (lead de e-mail da Atlas) ---
  const em = await api("/api/leads", { conta: "atlas", canal: "email", nome: "Email E2E", email: "cli@e2e.example", etapa: "Pronto", assunto: "Uma ideia", mensagem: "Oi, me chamo Enos. Vi que voces nao tem site. Posso te mostrar uma ideia?" });
  await ir(page, "#/atlas/hoje/aprovar_email");
  await checa("Hoje: e-mail para aprovar aparece e Aprovar remove da lista", async () => {
    if (!/Email E2E/.test(await texto(page))) return false;
    await page.getByRole("button", { name: "Aprovar", exact: true }).first().click();
    await page.waitForTimeout(900);
    return !/Email E2E/.test(await texto(page));
  });

  // --- financeiro ---
  await ir(page, "#/atlas/financeiro");
  await checa("Financeiro: lançamento pago vinculado fecha o lead e atualiza indicadores", async () => {
    await page.locator('input[placeholder="Cliente"]').fill("Locadora E2E");
    await page.locator('input[placeholder="Valor"]').fill("2400");
    const sels = page.locator("#view select");
    const n = await sels.count();
    const b = await api("/api/board?conta=atlas&canal=whatsapp");
    DIAG = "selects=" + n + " opcoes=" + (await sels.nth(0).locator("option").count()) + " board=" + JSON.stringify(Object.fromEntries(Object.entries(b.cards).map(([k, v]) => [k, v.length])));
    await sels.nth(n - 2).selectOption({ index: 1 });      // vincula ao lead em Negociando
    await sels.nth(n - 1).selectOption("pago");
    await page.getByRole("button", { name: /Salvar lançamento/ }).click();
    await page.waitForTimeout(1000);
    const t = (await texto(page)).replace(/\n/g, " ");
    return /RECEITA DO MÊS\s*R\$\s*2\.400/.test(t) && /FECHAMENTOS NO MÊS\s*1/.test(t);
  });
  await checa("Lead vinculado ao pagamento foi para Fechado", async () => (await api("/api/board?conta=atlas&canal=whatsapp")).cards.Fechado.length === 1);

  // --- validacao de copy no editor ---
  const rev = await api("/api/leads", { conta: "atlas", canal: "whatsapp", nome: "Revisar E2E", telefone: "(77) 99333-4444", etapa: "Novo", notas: "Mensagem reprovada nas regras: longa demais" });
  await ir(page, "#/atlas/hoje/revisar");
  await checa("Revisar: editor bloqueia texto fora das regras e aceita texto válido", async () => {
    await page.getByRole("button", { name: /Editar mensagem/ }).first().click();
    const ta = page.locator("#dlg textarea");
    await ta.fill("Oi, aqui é o Enos - trabalho com sites");
    await page.waitForTimeout(900);
    const ruim = await texto(page, "#dlg");
    await ta.fill("Oi, me chamo Enos. Vi que voces nao tem site. Posso te mostrar uma ideia?");
    await page.waitForTimeout(900);
    const bom = await texto(page, "#dlg");
    return /me chamo/.test(ruim) && /Dentro das regras/.test(bom);
  });
  await page.keyboard.press("Escape");

  // --- tema e conta ---
  await checa("Troca de empresa muda o acento (verde-água na Nexora, laranja na Atlas)", async () => {
    await ir(page, "#/nexora/painel");
    const nex = await page.evaluate(() => getComputedStyle(document.body).getPropertyValue("--ac").trim());
    await ir(page, "#/atlas/painel");
    const atl = await page.evaluate(() => getComputedStyle(document.body).getPropertyValue("--ac").trim());
    return nex.toLowerCase() === "#2fc4b8" && atl.toLowerCase() === "#ff6a2b";
  });
  await checa("Tema claro aplica e persiste", async () => {
    await page.locator("#tema").click();
    const t = await page.evaluate(() => [document.documentElement.dataset.theme, localStorage.getItem("crm.theme")]);
    await page.locator("#tema").click();
    return t[0] === "light" && t[1] === "light";
  });

  // --- configuracoes: WhatsApp parado no servidor de teste ---
  await ir(page, "#/atlas/config");
  await checa("Configurações: mostra estado do WhatsApp e botão para conectar", async () => /Conectar WhatsApp/.test(await texto(page)));
  await ir(page, "#/atlas/config/sistema");
  await checa("Configurações > Sistema carrega sem erro", async () => /Inteligência artificial/.test(await texto(page)));

  // --- celular ---
  await ctx.close();
  const mob = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const m = await mob.newPage();
  m.on("pageerror", (e) => R.erros_js.push("mobile: " + String(e)));
  await m.goto(BASE + "/#/atlas/hoje");
  await m.waitForFunction(() => !document.body.classList.contains("carregando"), null, { timeout: 15000 });
  await checa("Celular: barra inferior visível e menu lateral oculto", async () => (await m.locator("#tabbar").isVisible()) && !(await m.locator("#side").isVisible()));
  await checa("Celular: navegação pela barra inferior", async () => {
    await m.locator('#tabbar button[data-v="leads"]').tap();
    await m.waitForTimeout(700);
    return /Funil/.test(await m.locator("#view").innerText());
  });
  await checa("Celular: menu Mais abre com Painel, Financeiro e troca de empresa", async () => {
    await m.locator('#tabbar button[data-v="mais"]').tap();
    await m.waitForTimeout(400);
    const t = await m.locator("#overlay").innerText();
    await m.locator("#overlay .sheet").click({ position: { x: 5, y: 5 } });
    return /Painel/.test(t) && /Financeiro/.test(t) && /Atlas/.test(t) && /Nexora/.test(t);
  });
  const telas = ["hoje", "leads", "leads/captacao", "radar", "inbox/whatsapp", "painel", "aprendizado", "financeiro", "config", "config/sistema"];
  await checa("Celular: nenhuma tela tem rolagem horizontal acidental", async () => {
    const ruins = [];
    for (const conta of ["atlas", "nexora"]) for (const t of telas) {
      await ir(m, `#/${conta}/${t}`);
      const r = await m.evaluate(() => { const w = window.innerWidth; return document.documentElement.scrollWidth > w + 1 || [...document.querySelectorAll("#view *")].some((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.right > w + 1 && !e.closest(".board,.tabs,.cats,.ib-pastas"); }); });
      if (r) ruins.push(conta + "/" + t);
    }
    return ruins.length ? (falha("overflow em: " + ruins.join(", ")), true) : true;
  });
  await checa("Celular: funil rola na horizontal (colunas com 84% da largura)", async () => {
    await ir(m, "#/atlas/leads");
    const larg = await m.evaluate(() => document.querySelector(".col").getBoundingClientRect().width);
    return larg > 300 && larg < 340;
  });
  await checa("Celular: alvos de toque com pelo menos 36 px", async () => {
    await ir(m, "#/atlas/hoje");
    const baixos = await m.evaluate(() => [...document.querySelectorAll("#view button, #view a.btn")].filter((b) => b.getBoundingClientRect().height > 0 && b.getBoundingClientRect().height < 34).length);
    return baixos === 0;
  });
  await browser.close();
  console.log(JSON.stringify(R));
  process.exit(0);
})().catch((e) => { console.log(JSON.stringify(Object.assign(R, { falhou: R.falhou.concat(["FATAL: " + e.message]) }))); process.exit(0); });
