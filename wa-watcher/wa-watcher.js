// Observador SOMENTE LEITURA do WhatsApp Web para o CRM.
// Nunca envia mensagem: todas as funcoes de envio da biblioteca sao bloqueadas abaixo.
// Ele so avisa o CRM: "voce enviou X para o numero Y" e "o numero Y respondeu X".
const { Client, LocalAuth } = require("whatsapp-web.js");
const QRCode = require("qrcode");
const path = require("path");

const CRM = process.env.CRM_URL || "http://127.0.0.1:4400";

async function post(rota, corpo) {
  try {
    await fetch(CRM + rota, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  } catch (e) {
    console.error("CRM indisponivel:", e.message);
  }
}

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: path.join(__dirname, ".session") }),
  puppeteer: { headless: true, args: ["--no-sandbox", "--disable-setuid-sandbox"] },
});

for (const fn of ["sendMessage", "sendSeen", "sendPresenceAvailable"]) {
  client[fn] = () => { throw new Error("envio bloqueado: este observador e somente leitura"); };
}

const numero = (id) => (id || "").split("@")[0];
const ehIndividual = (id) => (id || "").endsWith("@c.us");

client.on("qr", async (qr) => {
  const img = await QRCode.toDataURL(qr, { margin: 1, width: 280 });
  await post("/api/wa/status", { estado: "qr", qr: img });
  console.log("QR atualizado, escaneie na tela Conexoes do CRM.");
});
client.on("authenticated", () => post("/api/wa/status", { estado: "autenticando" }));
client.on("ready", () => { console.log("WhatsApp conectado (somente leitura)."); post("/api/wa/status", { estado: "conectado" }); });
client.on("disconnected", (motivo) => { post("/api/wa/status", { estado: "desconectado", motivo: String(motivo) }); });
client.on("auth_failure", (m) => post("/api/wa/status", { estado: "falha", motivo: String(m) }));

client.on("message_create", async (msg) => {
  if (!msg.fromMe || msg.isStatus || !ehIndividual(msg.to)) return;
  await post("/api/wa/event", { direcao: "saida", telefone: numero(msg.to), texto: msg.body || "", tipo: msg.type, ts: msg.timestamp });
});

client.on("message", async (msg) => {
  if (msg.fromMe || msg.isStatus || !ehIndividual(msg.from)) return;
  const audio = msg.type === "ptt" || msg.type === "audio";
  await post("/api/wa/event", { direcao: "entrada", telefone: numero(msg.from), texto: audio ? "[mensagem de audio]" : (msg.body || ""), tipo: msg.type, ts: msg.timestamp });
});

client.initialize();
