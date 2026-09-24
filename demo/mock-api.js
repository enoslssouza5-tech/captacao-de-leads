/* Demonstração pública: intercepta /api/* e responde com dados FICTÍCIOS. Nenhum dado real sai do computador do dono. */
(function () {
  const agora = Date.now(), h = 3600 * 1000, d = 24 * h;
  const iso = (ms) => new Date(agora - ms).toISOString();
  const day = (n) => new Date(agora + n * d).toISOString().slice(0, 10);
  const L = (id, nome, sub, tag, score, nota, extra) => Object.assign({ id, ref: id, nome, sub, tag, score, nota: nota || "", readonly: false, aprovado: false }, extra || {});

  const ETAPAS = ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"];
  const DADOS = {
    atlas: {
      moeda: "BRL",
      whatsapp: {
        Novo: [L("c11", "Loc Max Equipamentos", "Cidade Exemplo, BA", "apify:google-maps", 74)],
        Pronto: [L("c12", "Locadora Modelo Ltda", "Cidade Exemplo, BA", "apify:google-maps", 82, "", { dor: "120 avaliações e nenhum site" })],
        Contatado: [L("c13", "Constrular Máquinas", "Cidade Exemplo, BA", "indicação", 68), L("c14", "Alfa Equipamentos", "Cidade Exemplo, BA", "apify:google-maps", 71)],
        Respondeu: [L("c15", "BetaLoc Ferramentas", "Cidade Exemplo, BA", "apify:google-maps", 77)],
        Negociando: [L("c16", "Gama Locações", "Cidade Exemplo, BA", "indicação", 85)],
        Fechado: [L("c17", "Delta Máquinas", "Cidade Exemplo, BA", "indicação", 90)],
        Perdido: [L("c18", "Épsilon Equipamentos", "Cidade Exemplo, BA", "apify:google-maps", 40)],
      },
      email: { Novo: [], Pronto: [L("c21", "Zeta Locações", "Cidade Exemplo, BA", "apify:google-maps", 66)], Contatado: [], Respondeu: [], Negociando: [], Fechado: [], Perdido: [] },
    },
    nexora: {
      moeda: "USD",
      whatsapp: { Novo: [], Pronto: [], Contatado: [], Respondeu: [], Negociando: [], Fechado: [], Perdido: [] },
      email: {
        Novo: [],
        Pronto: [L("n1", "Northside Realty Group", "Denver, CO", "real estate", 78, "A page for Denver sellers", { readonly: true }), L("n2", "Harbor Law Offices", "Boston, MA", "law firm", 72, "Where do urgent searches land", { readonly: true })],
        Contatado: [L("n3", "Lakeview Homes Team", "Chicago, IL", "real estate", 64, "A Chicago page under your own name", { readonly: true }), L("n4", "Summit Injury Lawyers", "Austin, TX", "law firm", 69, "Your intake form is a newsletter box", { readonly: true })],
        Respondeu: [L("n5", "Prairie Realty Partners", "Omaha, NE", "real estate", 81, "A dedicated page for luxury buyers", { readonly: true })],
        Negociando: [], Fechado: [], Perdido: [L("n6", "Cedar Point Law", "Raleigh, NC", "law firm", 55, "", { readonly: true })],
      },
    },
  };

  const conta = () => new URLSearchParams(location.search).get("x") || "";
  const parse = (url) => { const u = new URL(url, location.origin); return { path: u.pathname, q: Object.fromEntries(u.searchParams) }; };
  const soma = (o) => Object.values(o).reduce((a, b) => a + b.length, 0);

  const gmailThreads = [
    { id: "t1", assunto: "Re: A page for Denver sellers", pessoa: "Sam Carter", email: "sam@northside.example", snippet: "Interesting idea. Can you send the example page and pricing?", data: agora - 2 * h, msgs: 2, nao_lida: true, estrela: false, lead: { ref: "n5", nome: "Prairie Realty Partners", etapa: "Respondeu" } },
    { id: "t2", assunto: "Automatic reply: Where do urgent searches land", pessoa: "Harbor Law Offices", email: "office@harbor.example", snippet: "I am out of the office until Monday.", data: agora - 20 * h, msgs: 1, nao_lida: false, estrela: false, lead: null },
    { id: "t3", assunto: "Delivery Status Notification (Failure)", pessoa: "Mail Delivery Subsystem", email: "mailer-daemon@example.com", snippet: "Your message could not be delivered.", data: agora - 30 * h, msgs: 1, nao_lida: false, estrela: false, lead: { ref: "n6", nome: "Cedar Point Law", etapa: "Perdido" } },
  ];
  const conversa = (id) => {
    const t = gmailThreads.find((x) => x.id === id) || gmailThreads[0];
    return { id: t.id, lead: t.lead, mensagens: [
      { id: "m1", de: { nome: "Nexora", email: "hello@nexora.example" }, para: t.email, cc: "", data: agora - 30 * h, assunto: t.assunto.replace(/^Re: /, ""), corpo: "Hi, a quick note about your site. An example page, adjustable to your preferences, is here: https://exemplo.example/?empresa=demo", rotulos: ["SENT"], anexos: [], message_id: "<m1@x>", references: "" },
      { id: "m2", de: { nome: t.pessoa, email: t.email }, para: "hello@nexora.example", cc: "", data: t.data, assunto: t.assunto, corpo: t.snippet + "\n\nThank you,\n" + t.pessoa, rotulos: ["INBOX"], anexos: [], message_id: "<m2@x>", references: "<m1@x>" },
    ] };
  };

  function respostas(c, p) {
    const dados = DADOS[c];
    const cards = (canal) => dados[canal];
    const todos = [...Object.values(dados.whatsapp).flat(), ...Object.values(dados.email).flat()];
    switch (p.path) {
      case "/api/ping": return { ultima_resposta: 1, ultima: null, wa: "conectado" };
      case "/api/conexoes": return { whatsapp: { estado: "conectado", qr: null, motivo: null }, gmail: { nexora: { configurado: true, endereco: "hello@nexora.example" }, atlas: { configurado: true, endereco: "contato@atlas.example" } },
        config: { auto_followup_email_nexora: "0", auto_followup_email_atlas: "0", auto_analisar: "1", captar_atlas: "" }, jobs: [{ tipo: "captacao", conta: c, status: "ok", detalhe: "10 encontrados, 8 novos" }, { tipo: "analise", conta: c, status: "ok", detalhe: "Locadora Modelo Ltda" }] };
      case "/api/board": return { etapas: ETAPAS, cards: cards(p.q.canal), readonly: c === "nexora" && p.q.canal === "email" };
      case "/api/stats": return { whatsapp_hoje: 6, wa_cap: 15, email_hoje: 8, email_cap: 20, email: Object.fromEntries(ETAPAS.map((e) => [e, cards("email")[e].length])), whatsapp: Object.fromEntries(ETAPAS.map((e) => [e, cards("whatsapp")[e].length])), respostas: { interessado: 3, reuniao: 2, recusou: 1, duvida: 1 } };
      case "/api/hoje": {
        const wa = c === "atlas";
        const itens = wa ? [
          { tipo: "primeiro", ref: "c12", lead_id: 12, nome: "Locadora Modelo Ltda", sub: "Cidade Exemplo, BA", canal: "whatsapp", telefone: "(00) 90000-0000", mensagem: "Bom dia! Me chamo Enos, da Atlas. Vi que vocês têm 120 avaliações no Google, mas ainda não têm um site para transformar essa fama em orçamentos. Posso te mostrar um modelo pronto, sem compromisso?", link: "#", score: 82, dor: "120 avaliações e nenhum site", passo: 0 },
          { tipo: "followup", ref: "c13", tarefa_id: 1, nome: "Constrular Máquinas", sub: "Follow-up 1, previsto para " + day(0), canal: "whatsapp", telefone: "(00) 90000-0001", mensagem: "Oi, tudo bem? Passando só para saber se você viu minha mensagem. Posso te mostrar o modelo pronto?", link: "#", passo: 1, ia: true, atrasado: false },
        ] : [
          { tipo: "followup", ref: "n3", tarefa_id: 2, nome: "Lakeview Homes Team", sub: "Follow-up 1, previsto para " + day(0), canal: "email", email: "team@lakeview.example", mensagem: "Hi again, quick nudge on the Chicago page idea. Is growing your seller leads a priority this quarter?", link: "", passo: 1, ia: true, atrasado: false },
        ];
        return { itens, stats: { feitos: 6, cap: 15, pendentes: itens.length, respostas_a_classificar: 0, followups_atrasados: 0, interessados_sem_acao: c === "atlas" ? 1 : 1 } };
      }
      case "/api/captacao": return todos.filter((l) => ["Novo", "Pronto"].includes(ETAPAS.find((e) => (cards("whatsapp")[e] || []).concat(cards("email")[e] || []).includes(l)))).map((l) => Object.assign({}, l, { avaliacoes: 60 + (l.score % 90), sinais: l.score > 70 ? ["sem site"] : ["landing com problema"], etapa: (cards("whatsapp").Pronto || []).includes(l) || (cards("email").Pronto || []).includes(l) ? "Pronto" : "Novo", dor: l.dor })).sort((a, b) => b.score - a.score);
      case "/api/radar": return { sem_retorno: todos.filter((l) => l.score > 75 && l.score < 85).slice(0, 2).map((l) => ({ ref: l.ref, nome: l.nome, canal: "email", desde: iso(30 * h), etapa: "Respondeu" })), esfriando: [{ ref: "c13", nome: "Constrular Máquinas", canal: "whatsapp", desde: iso(16 * d) }], devolvidos: [{ ref: "n6", nome: "Cedar Point Law", desde: iso(2 * d) }] };
      case "/api/aprendizado": return { total_envios: 48, semana: { envios: 18, respostas_novas: 4 },
        por_canal: [{ chave: "email", envios: 30, respostas: 3, interessados: 2, taxa: 10 }, { chave: "whatsapp", envios: 18, respostas: 4, interessados: 3, taxa: 22 }],
        por_dor: [{ chave: "sem_site", envios: 16, respostas: 4, interessados: 3, taxa: 25 }, { chave: "site_desatualizado", envios: 20, respostas: 2, interessados: 1, taxa: 10 }],
        por_hora: [{ chave: "09h", envios: 12, respostas: 3, interessados: 2, taxa: 25 }, { chave: "15h", envios: 14, respostas: 1, interessados: 0, taxa: 7 }],
        objecoes: [{ texto: "Já temos alguém que cuida disso.", traducao: "Já temos alguém que cuida disso.", resumo: "Já tem fornecedor", created_at: iso(3 * d) }],
        propostas: [{ id: 1, titulo: "Abrir sempre com a contagem de avaliações", evidencia: "Sem site teve 25% de resposta contra 10%", ajuste: "Priorizar leads com muitas avaliações e sem site na abertura.", status: "pendente" }] };
      case "/api/financeiro": return { moeda: dados.moeda, recebido_mes: 240000, a_receber: 120000, meta: 600000, servicos: [{ nome: "Landing page premium", preco_centavos: 240000 }, { nome: "Gestão de tráfego (mensal)", preco_centavos: 120000 }],
        pagamentos: [{ id: 1, cliente: "Delta Máquinas", descricao: "Landing page", valor_centavos: 240000, status: "pago", pago_em: iso(3 * d) }, { id: 2, cliente: "Gama Locações", descricao: "Tráfego, 1º mês", valor_centavos: 120000, status: "a_receber", vencimento: day(5) }] };
      case "/api/modelos": return { dias: [3, 7, 14], modelos: [1, 2, 3].map((n) => ({ passo: n, texto: c === "atlas" ? "Oi, {nome}, tudo bem? Passando só para saber se você conseguiu ver minha mensagem." : "Hi, just circling back on my note about the page idea for {nome}." })) };
      case "/api/lead": {
        const l = todos.find((x) => x.ref === p.q.ref) || todos[0];
        return { lead: Object.assign({ canal: "whatsapp", etapa: "Pronto", mensagem: "Bom dia! Me chamo Enos, da Atlas.", tipo_dor: "sem_site", dor: "120 avaliações e nenhum site",
          criterios_json: JSON.stringify({ criterios: [{ criterio: "Reputação online", achado: "Muitas avaliações positivas no Google.", impacto: "alto" }, { criterio: "Existência da página", achado: "Sem site próprio.", impacto: "alto" }, { criterio: "Caminho de conversão", achado: "Só telefone, sem WhatsApp no perfil.", impacto: "medio" }] }) }, l),
          respostas: [{ classificacao: "reuniao", created_at: iso(3 * h), origem: "whatsapp", texto: "Tenho interesse, pode me ligar amanhã?", traducao: "", resumo: "Quer conversar" }], tarefas: [{ passo: 1, due_date: day(3), status: "pendente" }, { passo: 2, due_date: day(7), status: "pendente" }, { passo: 3, due_date: day(14), status: "pendente" }] };
      }
      case "/api/gmail/pastas": return { pastas: [{ id: "INBOX", nome: "Caixa de entrada", total: 12, nao_lidas: 1 }, { id: "STARRED", nome: "Com estrela", total: 0, nao_lidas: 0 }, { id: "SENT", nome: "Enviados", total: 51, nao_lidas: 0 }, { id: "DRAFT", nome: "Rascunhos", total: 0, nao_lidas: 0 }, { id: "SPAM", nome: "Spam", total: 2, nao_lidas: 2 }, { id: "TRASH", nome: "Lixeira", total: 4, nao_lidas: 0 }] };
      case "/api/gmail/conversas": return { itens: gmailThreads, proxima: null };
      case "/api/gmail/conversa": return conversa(p.q.id);
      default: return { ok: true };
    }
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async (url, opts) => {
    if (typeof url === "string" && url.startsWith("/api/")) {
      const p = parse(url);
      const c = p.q.conta || (opts && opts.body ? (JSON.parse(opts.body).conta || "") : "") || "atlas";
      const corpo = (opts && opts.method === "POST") ? { ok: true, demo: true } : respostas(DADOS[c] ? c : "atlas", p);
      return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return realFetch(url, opts);
  };
})();
