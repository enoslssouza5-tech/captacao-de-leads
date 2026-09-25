/* Radar: centro de atencao. Hierarquia por urgencia, poucos textos. */
"use strict";
VIEWS.radar = async function (raiz) {
  const r = await api(`/api/radar?conta=${S.conta}`);
  cabecalho(raiz, "Radar", r.total ? r.total + " item(ns) pedindo atenção" : "Nada pedindo atenção");
  if (!r.total) return raiz.append(vazio("Tudo em dia", "Ninguém esperando resposta, nenhum follow-up atrasado e nenhum lead esfriando."));

  const grupo = (titulo, dica, itens, sev, render) => {
    if (!itens.length) return "";
    return el("div", { class: "sec fade", style: "margin-top:30px" }, el("div", { class: "sec-h" }, el("h2", {}, titulo), pill(sev === "urg" ? "err" : sev === "med" ? "warn" : "info", itens.length), el("span", { class: "aux" }, dica)),
      el("div", { class: "list" }, itens.slice(0, 40).map((i) => el("div", { class: "item", style: "grid-template-columns:auto minmax(0,1fr) auto", onclick: () => abrirLead(i.ref) }, el("div", { class: "sev " + sev }), render(i)[0], render(i)[1]))));
  };
  const resposta = (i) => [el("div", {}, el("div", { class: "t1" }, i.nome, canalIc(i.canal), clsPill(i.classificacao), el("span", { class: "faint", style: "font-weight:450;font-size:12.5px" }, "esperando há " + i.horas + " h")), el("div", { class: "t2" }, i.resumo || "")),
    el("div", { class: "lado" }, botaoAcao("Responder", () => abrirConversa(i), "btn sm", "arrow"))];
  raiz.append(
    grupo("Urgente", "negociando há mais de 4 h ou qualquer um há mais de 48 h", r.urgente, "urg", resposta),
    grupo("Respondeu e não foi respondido", "esperando você há mais de 24 h", r.sem_retorno, "med", resposta),
    grupo("Follow-up atrasado", "a data passou e nada foi enviado", r.followup_atrasado, "med", (i) => [el("div", {}, el("div", { class: "t1" }, i.nome, canalIc(i.canal), pill("warn", "follow-up " + i.passo)), el("div", { class: "t2" }, i.dias_atraso + " dia(s) de atraso")), el("div", { class: "lado" }, icon("arrow"))]),
    grupo("Esfriando", "sequência concluída há mais de 14 dias sem resposta", r.esfriando, "baixo", (i) => [el("div", {}, el("div", { class: "t1" }, i.nome, canalIc(i.canal)), el("div", { class: "t2" }, "contatado há " + quando(i.desde))), el("div", { class: "lado" }, icon("arrow"))]),
    grupo("Devolvido", "endereço inexistente, já bloqueado para novos envios", r.devolvidos, "baixo", (i) => [el("div", {}, el("div", { class: "t1" }, i.nome, pill("err", "e-mail devolvido")), el("div", { class: "t2" }, quando(i.desde) + " atrás")), el("div", { class: "lado" })]));
};
