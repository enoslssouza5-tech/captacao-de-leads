// Observador SOMENTE LEITURA do WhatsApp Web para o CRM.
// Nunca envia mensagem: todas as funcoes de envio da biblioteca sao bloqueadas.
// Avisa o CRM: "voce enviou X para o numero Y" e "o numero Y respondeu X".
// Manda um batimento a cada 10s para o CRM saber que o processo esta vivo.
const path = require("path");

const CRM = process.env.CRM_URL || "http://127.0.0.1:4400";
const BATIMENTO_MS = Number(process.env.WA_BATIMENTO_MS || 10000);

const numero = (id) => (id || "").split("@")[0];
const ehIndividual = (id) => (id || "").endsWith("@c.us");
const BLOQUEADAS = ["sendMessage", "sendSeen", "sendPresenceAvailable", "sendPresenceUnavailable", "setStatus", "createGroup"];

function bloquearEnvio(client) {
  for (const fn of BLOQUEADAS) {
    client[fn] = () => { throw new Error("envio bloqueado: este observador e somente leitura"); };
  }
}

// Liga os eventos do cliente ao CRM. `post(rota, corpo)` e injetavel para teste.
function instalar(client, post, gerarQR) {
  let estado = "iniciando";
  const status = (novo, extra) => { estado = novo; return post("/api/wa/status", Object.assign({ estado: novo }, extra || {})); };
  bloquearEnvio(client);

  client.on("qr", async (qr) => {
    const img = gerarQR ? await gerarQR(qr) : qr;
    await status("qr", { qr: img });
  });
  client.on("authenticated", () => status("autenticando"));
  client.on("ready", () => status("conectado"));
  client.on("disconnected", (motivo) => status("desconectado", { motivo: String(motivo) }));
  client.on("auth_failure", (m) => status("falha", { motivo: String(m) }));

  // O WhatsApp atual identifica muitos contatos por "@lid" (id interno), nao pelo telefone. Resolve para o numero real.
  async function telefoneDe(msg, id) {
    if (ehIndividual(id)) return numero(id);
    if (!(id || "").endsWith("@lid")) return null;
    try {
      if (client.getContactLidAndPhone) {
        const r = await client.getContactLidAndPhone([id]);
        if (r && r[0] && r[0].pn) return numero(r[0].pn);
      }
    } catch (e) { /* tenta pelo contato */ }
    try {
      const c = msg.getContact ? await msg.getContact() : null;
      if (c && c.number && /^\d{8,15}$/.test(c.number)) return c.number;
    } catch (e) { /* sem resolucao */ }
    return null;
  }
  const diag = (motivo, msg, extra) => post("/api/wa/diag", Object.assign({ motivo, tipo: msg && msg.type, de_mim: !!(msg && msg.fromMe) }, extra || {}));

  client.on("message_create", async (msg) => {
    try {
      if (!msg.fromMe) return;
      if (msg.isStatus || msg.to === "status@broadcast") return diag("ignorado: status", msg);
      if ((msg.to || "").endsWith("@g.us")) return diag("ignorado: grupo", msg);
      if ((msg.to || "").endsWith("@newsletter")) return diag("ignorado: canal", msg);
      const tel = await telefoneDe(msg, msg.to);
      if (!tel) return diag("ignorado: nao consegui resolver o numero (id " + String(msg.to).split("@")[1] + ")", msg);
      await post("/api/wa/event", { direcao: "saida", telefone: tel, texto: msg.body || "", tipo: msg.type, ts: msg.timestamp });
    } catch (e) { await diag("erro ao tratar envio: " + e.message, msg); }
  });
  client.on("message", async (msg) => {
    try {
      if (msg.fromMe || msg.isStatus) return;
      if ((msg.from || "").endsWith("@g.us") || (msg.from || "").endsWith("@newsletter") || msg.from === "status@broadcast") return;
      const tel = await telefoneDe(msg, msg.from);
      if (!tel) return diag("ignorado: nao consegui resolver o numero de quem respondeu (id " + String(msg.from).split("@")[1] + ")", msg);
      const audio = msg.type === "ptt" || msg.type === "audio";
      await post("/api/wa/event", { direcao: "entrada", telefone: tel, texto: audio ? "[mensagem de audio]" : (msg.body || ""), tipo: msg.type, ts: msg.timestamp });
    } catch (e) { await diag("erro ao tratar resposta: " + e.message, msg); }
  });

  const timer = setInterval(() => post("/api/wa/status", { estado: "batimento", atual: estado }), BATIMENTO_MS);
  timer.unref && timer.unref();
  return { estado: () => estado, parar: () => clearInterval(timer) };
}

async function postar(rota, corpo) {
  try {
    await fetch(CRM + rota, { method: "POST", headers: { "Content-Type": "application/json", "X-CRM-Origem": "wa-watcher" }, body: JSON.stringify(corpo) });
  } catch (e) {
    console.error("CRM indisponivel:", e.message);
  }
}

if (require.main === module) {
  const { Client, LocalAuth } = require("whatsapp-web.js");
  const QRCode = require("qrcode");
  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(__dirname, ".session") }),
    puppeteer: { headless: true, args: ["--no-sandbox", "--disable-setuid-sandbox"] },
  });
  const gerarQR = (qr) => QRCode.toDataURL(qr, { errorCorrectionLevel: "L", margin: 4, width: 400 });
  instalar(client, postar, gerarQR);
  const sair = () => { client.destroy().catch(() => {}).finally(() => process.exit(0)); };
  process.on("SIGINT", sair);
  process.on("SIGTERM", sair);
  process.on("unhandledRejection", (e) => { console.error("Erro nao tratado:", e && e.message ? e.message : e); });
  client.initialize().catch((e) => { console.error("Erro ao iniciar:", e.message); process.exit(1); });
  console.log("Observador iniciado.");
}

module.exports = { instalar, bloquearEnvio, BLOQUEADAS };
