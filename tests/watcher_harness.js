// Harness: liga o observador REAL (wa-watcher.js) a um cliente WhatsApp FALSO e posta no CRM de teste (HTTP real).
// Verifica tambem que o observador nao consegue enviar mensagem.
const { EventEmitter } = require("events");
const { instalar, BLOQUEADAS } = require("../wa-watcher/wa-watcher.js");

const CRM = process.env.CRM_URL;
const post = async (rota, corpo) => {
  const r = await fetch(CRM + rota, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  return r.status;
};

(async () => {
  const cliente = new EventEmitter();
  const obs = instalar(cliente, post, async (qr) => "data:image/png;base64,QR:" + qr);
  const resultado = { bloqueio: {} };

  for (const fn of BLOQUEADAS) {
    try { cliente[fn]("5577999999999@c.us", "oi"); resultado.bloqueio[fn] = "PERMITIU"; }
    catch (e) { resultado.bloqueio[fn] = "bloqueado"; }
  }

  cliente.emit("qr", "2@fake-qr-string");
  await new Promise((r) => setTimeout(r, 200));
  cliente.emit("ready");
  await new Promise((r) => setTimeout(r, 200));

  const esperar = () => new Promise((r) => setTimeout(r, 300));
  const alvo = process.env.NUM_LEAD || "5577998887766";
  cliente.emit("message_create", { fromMe: true, isStatus: false, to: alvo + "@c.us", body: "Bom dia!", type: "chat", timestamp: 1700000000 });
  await esperar();
  cliente.emit("message", { fromMe: false, isStatus: false, from: alvo + "@c.us", body: "Tenho interesse, quero conversar", type: "chat", timestamp: 1700000100 });
  await esperar();
  cliente.emit("message", { fromMe: false, isStatus: false, from: alvo + "@c.us", body: "", type: "ptt", timestamp: 1700000200 });
  await esperar();
  cliente.emit("message", { fromMe: false, isStatus: false, from: "5511900000000@c.us", body: "numero desconhecido", type: "chat", timestamp: 1700000300 });
  cliente.emit("message", { fromMe: false, isStatus: false, from: "12036300000@g.us", body: "grupo", type: "chat", timestamp: 1700000400 });       // grupo: ignorado no watcher
  cliente.emit("message", { fromMe: false, isStatus: true, from: "status@broadcast", body: "status", type: "chat", timestamp: 1700000500 });         // status: ignorado
  cliente.emit("message_create", { fromMe: true, isStatus: false, to: "12036300000@g.us", body: "grupo", type: "chat", timestamp: 1700000600 });     // grupo: ignorado
  await esperar();
  cliente.emit("disconnected", "LOGOUT");
  await esperar();
  obs.parar();
  console.log(JSON.stringify(resultado));
  process.exit(0);
})();
