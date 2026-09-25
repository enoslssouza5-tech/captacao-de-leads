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

  client.on("message_create", async (msg) => {
    if (!msg.fromMe || msg.isStatus || !ehIndividual(msg.to)) return;
    await post("/api/wa/event", { direcao: "saida", telefone: numero(msg.to), texto: msg.body || "", tipo: msg.type, ts: msg.timestamp });
  });
  client.on("message", async (msg) => {
    if (msg.fromMe || msg.isStatus || !ehIndividual(msg.from)) return;
    const audio = msg.type === "ptt" || msg.type === "audio";
    await post("/api/wa/event", { direcao: "entrada", telefone: numero(msg.from), texto: audio ? "[mensagem de audio]" : (msg.body || ""), tipo: msg.type, ts: msg.timestamp });
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
