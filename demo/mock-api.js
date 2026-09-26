/* Demonstracao publica: intercepta /api/* e responde com dados FICTICIOS. Nada real sai do computador do dono e nada e salvo. */
(function () {
  const agora = Date.now(), h = 3600 * 1000, d = 24 * h;
  const iso = (ms) => new Date(agora - ms).toISOString();
  const dia = (n) => new Date(agora + n * d).toISOString().slice(0, 10);
  const semente = (s) => () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  const ETAPAS = ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado", "Perdido"];

  const CONTAS = {
    atlas: {
      moeda: "BRL", idioma: "pt",
      leads: [
        ["c1", "Locadora Modelo Ltda", "whatsapp", "Pronto", 82, "sem_site", "120 avaliações e nenhum site", "Enviar no WhatsApp"],
        ["c2", "Constrular Máquinas", "whatsapp", "Contatado", 71, "site_desatualizado", "Site de 2016 sem WhatsApp", "Follow-up em 2 dias"],
        ["c3", "Alfa Equipamentos", "whatsapp", "Respondeu", 77, "sem_site", "Nota 4,9 e só perfil no Instagram", "Responder"],
        ["c4", "BetaLoc Ferramentas", "whatsapp", "Negociando", 85, "reputacao_sem_captacao", "300 avaliações sem página de orçamento", "Avançar a negociação"],
        ["c5", "Gama Locações", "whatsapp", "Fechado", 90, "sem_site", "Sem site, 210 avaliações", "Entregar e acompanhar"],
        ["c6", "Delta Máquinas", "whatsapp", "Perdido", 40, "site_confuso", "", ""],
        ["c7", "Loc Max Equipamentos", "whatsapp", "Novo", 74, null, "", "Analisar a dor"],
        ["c8", "Zeta Locações", "email", "Pronto", 66, "site_desatualizado", "Página lenta e sem celular", "Aprovar o e-mail"],
        ["c9", "Ômega Caçambas", "email", "Contatado", 62, "sem_conversao", "Só telefone, sem formulário", "Follow-up hoje"],
      ],
    },
    nexora: {
      moeda: "USD", idioma: "en",
      leads: [
        ["n1", "Northside Realty Group", "email", "Pronto", 78, "sem_landing", "Reviews with no capture page", "Aprovar o e-mail"],
        ["n2", "Harbor Law Offices", "email", "Pronto", 72, "landing_com_problema", "Intake form is a newsletter box", "Aprovar o e-mail"],
        ["n3", "Lakeview Homes Team", "email", "Contatado", 64, "sem_landing", "No dedicated seller page", "Follow-up em 3 dias"],
        ["n4", "Summit Injury Lawyers", "email", "Contatado", 69, "landing_com_problema", "Contact page hides the form", "Follow-up hoje"],
        ["n5", "Prairie Realty Partners", "email", "Respondeu", 81, "sem_landing", "Luxury buyers have no page", "Responder"],
        ["n6", "Cedar Point Law", "email", "Perdido", 55, "site_ok", "", ""],
      ],
    },
  };

  const conta = (p) => (CONTAS[p.q.conta] ? p.q.conta : "atlas");
  const parse = (url) => { const u = new URL(url, location.origin); return { path: u.pathname, q: Object.fromEntries(u.searchParams) }; };
  const cartao = (l) => ({ id: l[0], ref: l[0], nome: l[1], canal: l[2], etapa: l[3], score: l[4], tipo_dor: l[5], dor: l[6], proxima: l[7], sub: "Cidade Exemplo", tag: l[2] === "email" ? "e-mail" : "whatsapp", readonly: false, aprovado: false, telefone: l[2] === "whatsapp" ? "(00) 90000-000" + l[0].slice(1) : null, email: l[2] === "email" ? "contato@" + l[0] + ".example" : null, avaliacoes: 40 + l[4] });

  function serie(dias, base, seed) {
    const r = semente(seed);
    return Array.from({ length: dias }, (_, i) => (r() < base ? Math.round(1 + r() * 4 * (0.4 + i / dias)) : 0));
  }
  function painel(c, dias) {
    const datas = Array.from({ length: dias }, (_, i) => dia(-(dias - 1 - i)));
    const s = { leads: serie(dias, 0.7, 3), contatos: serie(dias, 0.75, 5), respostas: serie(dias, 0.35, 8), negociacoes: serie(dias, 0.12, 11), fechamentos: serie(dias, 0.06, 13) };
    const metade = Math.floor(dias / 2), sum = (a) => a.reduce((x, y) => x + y, 0);
    const tend = Object.fromEntries(Object.entries(s).map(([k, v]) => [k, sum(v.slice(metade)) - sum(v.slice(0, metade))]));
    const n = [124, 118, 86, 19, 6, 3], pct = (a, b) => (b ? Math.round((a * 100) / b) : null);
    return { kpis: { leads: 124, contatados: 86, respostas: 19, negociacoes: 6, fechados: 3, perdidos: 9 }, tendencia: tend, datas, serie: s,
      funil: ["Novo", "Pronto", "Contatado", "Respondeu", "Negociando", "Fechado"].map((e, i) => ({ etapa: e, n: n[i], conv: i ? pct(n[i], n[i - 1]) : null, perdidos: i === 2 ? 4 : i === 3 ? 2 : 0 })),
      canais: [{ canal: "whatsapp", leads: 70, contatados: 52, respostas: 12, negociacoes: 4, taxa: 23, insuficiente: false }, { canal: "email", leads: 54, contatados: 34, respostas: 7, negociacoes: 2, taxa: 21, insuficiente: false }],
      dores: [{ dor: "sem_site", contatados: 40, respostas: 11, taxa: 28, insuficiente: false }, { dor: "site_desatualizado", contatados: 30, respostas: 5, taxa: 17, insuficiente: false }, { dor: "sem_conversao", contatados: 12, respostas: 2, taxa: 17, insuficiente: false }, { dor: "site_confuso", contatados: 4, respostas: 1, taxa: null, insuficiente: true }],
      radar: { sem_retorno: 3, esfriando: 3, devolvidos: 1 }, serie_suficiente: true, parcial: c === "nexora" };
  }
  function acoes(c) {
    const nx = c === "nexora";
    const resp = nx ? "Interesting idea. Can you send the example page and pricing?" : "Tenho interesse, pode me ligar amanhã?";
    const it = (o) => Object.assign({ canal: "whatsapp", etapa: "Respondeu", desde: iso(5 * h), prioridade: 1 }, o);
    const responder = [it({ categoria: "responder", ref: nx ? "n5" : "c4", nome: nx ? "Prairie Realty Partners" : "BetaLoc Ferramentas", canal: nx ? "email" : "whatsapp", etapa: "Negociando", classificacao: "reuniao", resumo: "Quer conversar", texto: resp, email: "contato@exemplo.example" }),
      it({ categoria: "responder", ref: nx ? "n3" : "c3", nome: nx ? "Lakeview Homes Team" : "Alfa Equipamentos", canal: nx ? "email" : "whatsapp", classificacao: "duvida", resumo: "Pergunta o preço", texto: nx ? "How much does it cost?" : "Quanto custa e em quanto tempo entrega?", desde: iso(27 * h) })];
    const wa = nx ? [] : [{ categoria: "whatsapp", tipo: "primeiro", ref: "c1", lead_id: 1, nome: "Locadora Modelo Ltda", sub: "Cidade Exemplo", canal: "whatsapp", telefone: "(00) 90000-0001", score: 82, dor: "120 avaliações e nenhum site", mensagem: "Oi, me chamo Enos. Vi que vocês têm 120 avaliações no Google, mas ainda não têm um site para transformar isso em orçamento. Posso te mostrar uma ideia rápida?", link: "#" },
      { categoria: "whatsapp", tipo: "primeiro", ref: "c7", lead_id: 7, nome: "Loc Max Equipamentos", sub: "Cidade Exemplo", canal: "whatsapp", telefone: "(00) 90000-0007", score: 74, dor: "Nota 4,8 e só perfil no Instagram", mensagem: "Oi, me chamo Enos. Vi que vocês são bem avaliados, mas hoje não têm uma página própria para receber pedidos de orçamento. Posso te mostrar uma ideia?", link: "#" }];
    const aprovar = (nx ? [["n1", "Northside Realty Group", "An idea for your seller leads", 78], ["n2", "Harbor Law Offices", "Where do urgent searches land", 72]] : [["c8", "Zeta Locações", "Uma ideia para o site", 66]])
      .map((x, i) => ({ categoria: "aprovar_email", ref: x[0], lead_id: i + 1, nome: x[1], canal: "email", assunto: x[2], score: x[3], dor: nx ? "sem_landing" : "site_desatualizado", nexora: nx }));
    const follow = [{ categoria: "followup", tipo: "followup", ref: nx ? "n4" : "c2", tarefa_id: 1, nome: nx ? "Summit Injury Lawyers" : "Constrular Máquinas", canal: nx ? "email" : "whatsapp", passo: 1, ia: true, atrasado: false, mensagem: nx ? "Hi again, quick nudge on the page idea. Is capturing more inquiries a priority this quarter?" : "Oi, passando só para saber se você viu minha mensagem. Posso te mostrar uma ideia rápida?", link: nx ? "" : "#" }];
    const revisar = nx ? [] : [{ categoria: "revisar", ref: "c10", lead_id: 10, nome: "Épsilon Equipamentos", canal: "whatsapp", motivo: "Mensagem reprovada nas regras: longa demais" }];
    const resumo = { responder: responder.length, whatsapp: wa.length, aprovar_email: aprovar.length, revisar: revisar.length, followup: follow.length };
    return { resumo, total: Object.values(resumo).reduce((a, b) => a + b, 0), responder, whatsapp: wa, aprovar_email: aprovar, aprovar_ids: aprovar.map((x) => x.lead_id), revisar, followup: follow, stats: {} };
  }
  const radar = (c) => ({ urgente: [{ ref: c === "nexora" ? "n5" : "c4", nome: c === "nexora" ? "Prairie Realty Partners" : "BetaLoc Ferramentas", canal: c === "nexora" ? "email" : "whatsapp", horas: 6, etapa: "Negociando", resumo: "Quer conversar", classificacao: "reuniao" }],
    sem_retorno: [{ ref: "c3", nome: "Alfa Equipamentos", canal: "whatsapp", horas: 30, etapa: "Respondeu", resumo: "Pergunta o preço", classificacao: "duvida" }],
    followup_atrasado: [{ ref: "c2", nome: "Constrular Máquinas", canal: "whatsapp", passo: 1, dias_atraso: 2 }],
    esfriando: [{ ref: "c6", nome: "Delta Máquinas", canal: "whatsapp", desde: iso(16 * d) }], devolvidos: [{ ref: "n6", nome: "Cedar Point Law", desde: iso(2 * d) }], total: 5 });
  const aprend = () => ({ total_envios: 86, semana: { envios: 18, respostas_novas: 4 }, amostra_minima: 10, insuficiente_horario: false,
    por_canal: [{ chave: "whatsapp", envios: 52, respostas: 12, interessados: 8, taxa: 23 }, { chave: "email", envios: 34, respostas: 7, interessados: 4, taxa: 21 }],
    por_dor: [{ chave: "sem_site", envios: 40, respostas: 11, interessados: 7, taxa: 28 }, { chave: "site_desatualizado", envios: 30, respostas: 5, interessados: 3, taxa: 17 }, { chave: "sem_conversao", envios: 12, respostas: 2, interessados: 1, taxa: 17 }],
    por_hora: Array.from({ length: 24 }, (_, i) => ({ chave: String(i).padStart(2, "0") + "h", hora: i, envios: i >= 8 && i <= 18 ? 6 : 0, respostas: [9, 10, 15].includes(i) ? 3 : i % 5 === 0 ? 1 : 0, taxa: i >= 8 && i <= 18 ? ([9, 10, 15].includes(i) ? 50 : i % 5 === 0 ? 17 : 0) : null })),
    por_dia_semana: ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"].map((n, i) => ({ chave: n, envios: i < 5 ? 16 : 3, respostas: i < 5 ? [4, 3, 3, 2, 2][i] : 0, taxa: i < 5 ? [25, 19, 19, 13, 13][i] : 0 })),
    por_abordagem: [{ chave: "Variação A (diagnóstico)", contatados: 24, respostas: 6, taxa: 25, insuficiente: false }, { chave: "Variação B (oportunidade)", contatados: 10, respostas: 1, taxa: 10, insuficiente: false }],
    objecoes_top: [{ motivo: "Já tem alguém que cuida disso", n: 4 }, { motivo: "Sem interesse no momento", n: 3 }, { motivo: "Acha caro", n: 1 }],
    objecoes: [], propostas: [{ id: 1, titulo: "Abrir sempre com a contagem de avaliações", evidencia: "Sem site teve 28% de resposta contra 17%", ajuste: "Priorizar leads com muitas avaliações e sem site na abertura.", status: "pendente" }] });
  const fin = (c) => { const m = CONTAS[c].moeda, meses = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12"];
    return { moeda: m, recebido_mes: 240000, a_receber: 120000, meta: 600000, meta_pct: 40, ticket_medio: 180000, fechamentos_mes: 1, fechamentos_total: 3,
      serie: meses.map((x, i) => ({ mes: x, recebido: [0, 0, 120000, 180000, 300000, 240000, 0, 0, 0][i], a_receber: [0, 0, 0, 0, 0, 0, 120000, 60000, 0][i], futuro: i > 5 })),
      origens: [{ origem: "WhatsApp (Google Maps)", valor: 420000 }, { origem: "E-mail (indicação)", valor: 120000 }], servicos: [{ nome: "Landing page premium", preco_centavos: 240000 }, { nome: "Gestão de tráfego (mensal)", preco_centavos: 120000 }],
      pagamentos: [{ id: 1, cliente: "Gama Locações", descricao: "Landing page", valor_centavos: 240000, status: "pago", pago_em: iso(3 * d) }, { id: 2, cliente: "BetaLoc Ferramentas", descricao: "Tráfego, 1º mês", valor_centavos: 120000, status: "a_receber", vencimento: dia(5) }] }; };
  const gmailThreads = [
    { id: "t1", assunto: "Re: A page for Denver sellers", pessoa: "Sam Carter", email: "sam@northside.example", snippet: "Interesting idea. Can you send the example page and pricing?", data: agora - 2 * h, msgs: 2, nao_lida: true, estrela: false, lead: { ref: "n5", nome: "Prairie Realty Partners", etapa: "Respondeu" } },
    { id: "t2", assunto: "Automatic reply: Where do urgent searches land", pessoa: "Harbor Law Offices", email: "office@harbor.example", snippet: "I am out of the office until Monday.", data: agora - 20 * h, msgs: 1, nao_lida: false, estrela: false, lead: null },
    { id: "t3", assunto: "Delivery Status Notification (Failure)", pessoa: "Mail Delivery Subsystem", email: "mailer-daemon@example.com", snippet: "Your message could not be delivered.", data: agora - 30 * h, msgs: 1, nao_lida: false, estrela: false, lead: { ref: "n6", nome: "Cedar Point Law", etapa: "Perdido" } },
  ];
  const conversaGmail = (id) => { const t = gmailThreads.find((x) => x.id === id) || gmailThreads[0]; return { id: t.id, lead: t.lead, mensagens: [
    { id: "m1", de: { nome: "Nexora", email: "hello@nexora.example" }, para: t.email, cc: "", data: agora - 30 * h, assunto: t.assunto.replace(/^Re: /, ""), corpo: "Hi, your reviews are strong but there is no page that captures inquiries. This example is illustrative and can be adjusted to your preferences: https://exemplo.example/?empresa=demo", rotulos: ["SENT"], anexos: [], message_id: "<m1@x>", references: "" },
    { id: "m2", de: { nome: t.pessoa, email: t.email }, para: "hello@nexora.example", cc: "", data: t.data, assunto: t.assunto, corpo: t.snippet + "\n\nThank you,\n" + t.pessoa, rotulos: ["INBOX"], anexos: [], message_id: "<m2@x>", references: "<m1@x>" }] }; };
  const waMsgs = [{ direcao: "saida", texto: "Oi, me chamo Enos. Vi que vocês têm 300 avaliações, mas nenhuma página de orçamento. Posso te mostrar uma ideia?", created_at: iso(30 * h) }, { direcao: "entrada", texto: "Oi Enos, tenho interesse. Pode me ligar amanhã?", created_at: iso(6 * h) }];

  function responder(c, p) {
    const dados = CONTAS[c];
    const todos = dados.leads.map(cartao);
    switch (p.path) {
      case "/api/ping": return { ultima_resposta: 1, ultima: null, wa: "conectado" };
      case "/api/saude": return { workers: { gmail: { ok: true, ultima_execucao: iso(2 * 60 * 1000) }, ia: { ok: true, ultima_execucao: iso(40 * 1000) }, envio: { ok: true, ultima_execucao: iso(5 * 60 * 1000) }, manutencao: { ok: true, ultima_execucao: iso(3 * h) } }, ia: { disponivel: true, falhas_seguidas: 0, ultimo_erro: "", ultimo_ok: "hoje" }, whatsapp: { estado: "conectado", eventos: [] }, gmail: {}, backups: ["crm-20260924.sqlite3", "nexora-20260924.sqlite3"] };
      case "/api/conexoes": return { whatsapp: { estado: "conectado", qr: null, motivo: null, vinculado: true, qr_idade_s: null, eventos: [] }, gmail: { nexora: { configurado: true, endereco: "hello@nexora.example" }, atlas: { configurado: true, endereco: "contato@atlas.example" } },
        config: { auto_followup_email_nexora: "0", auto_followup_email_atlas: "0", auto_analisar: "1", captar_atlas: "" }, jobs: [{ tipo: "captacao", conta: c, status: "ok", detalhe: "10 encontrados, 8 novos" }, { tipo: "analise", conta: c, status: "ok", detalhe: "Locadora Modelo Ltda" }] };
      case "/api/board": { const cards = Object.fromEntries(ETAPAS.map((e) => [e, todos.filter((l) => l.etapa === e && l.canal === p.q.canal)])); return { etapas: ETAPAS, cards, readonly: c === "nexora" && p.q.canal === "email" }; }
      case "/api/captacao": return todos.filter((l) => ["Novo", "Pronto"].includes(l.etapa)).map((l) => Object.assign(l, { sinais: l.tipo_dor === "sem_site" || l.tipo_dor === "sem_landing" ? ["sem site"] : ["landing com problema"] })).sort((a, b) => b.score - a.score);
      case "/api/painel": return painel(c, Math.max(7, Math.min(90, +p.q.dias || 30)));
      case "/api/acoes": return acoes(c);
      case "/api/radar": return radar(c);
      case "/api/aprendizado": return aprend();
      case "/api/financeiro": return fin(c);
      case "/api/conversas": return { conversas: c === "atlas" ? [{ ref: "c4", nome: "BetaLoc Ferramentas", telefone: "(00) 90000-0004", etapa: "Negociando", mensagens: 2, ultima: waMsgs[1].texto, direcao: "entrada", quando: iso(6 * h), classificacao: "reuniao", aguardando_voce: true }, { ref: "c2", nome: "Constrular Máquinas", telefone: "(00) 90000-0002", etapa: "Contatado", mensagens: 1, ultima: waMsgs[0].texto, direcao: "saida", quando: iso(3 * d), classificacao: null, aguardando_voce: false }] : [] };
      case "/api/modelos": return { dias: [3, 7, 14], modelos: [1, 2, 3].map((n) => ({ passo: n, texto: c === "atlas" ? "Oi, {nome}, tudo bem? Passando só para saber se você conseguiu ver minha mensagem." : "Hi, just circling back on my note about the page idea for {nome}." })) };
      case "/api/lead": { const l = todos.find((x) => x.ref === p.q.ref) || todos[0];
        return { lead: Object.assign({ conta: c, mensagem: "Oi, me chamo Enos. Vi 120 avaliações e nenhum site. Posso te mostrar uma ideia?", corpo_texto: null,
          criterios_json: JSON.stringify({ criterios: [{ criterio: "Reputação online", achado: "Muitas avaliações positivas no Google.", impacto: "alto" }, { criterio: "Existência da página", achado: "Sem site próprio.", impacto: "alto" }, { criterio: "Caminho de conversão", achado: "Só telefone, sem WhatsApp no perfil.", impacto: "medio" }], evidencias: ["120 avaliações no Google (perfil público)", "Nenhum site listado no perfil"] }) }, l),
          respostas: [{ classificacao: "reuniao", created_at: iso(3 * h), origem: "whatsapp", texto: "Tenho interesse, pode me ligar amanhã?", traducao: "", resumo: "Quer conversar" }],
          tarefas: [{ passo: 1, due_date: dia(3), status: "pendente", mensagem: "Oi, passando só para saber se viu minha mensagem." }, { passo: 2, due_date: dia(7), status: "pendente", mensagem: "Separei um exemplo de página para o seu segmento." }, { passo: 3, due_date: dia(14), status: "pendente", mensagem: "Vou encerrar por aqui para não incomodar." }],
          eventos: [{ tipo: "criado", de_etapa: null, para_etapa: "Novo", ts: iso(6 * d) }, { tipo: "etapa", de_etapa: "Novo", para_etapa: "Pronto", ts: iso(5 * d) }, { tipo: "etapa", de_etapa: "Pronto", para_etapa: "Contatado", ts: iso(2 * d) }], whatsapp: waMsgs }; }
      case "/api/gmail/pastas": return { pastas: [{ id: "INBOX", nome: "Caixa de entrada", total: 12, nao_lidas: 1 }, { id: "STARRED", nome: "Com estrela", total: 0, nao_lidas: 0 }, { id: "SENT", nome: "Enviados", total: 51, nao_lidas: 0 }, { id: "DRAFT", nome: "Rascunhos", total: 0, nao_lidas: 0 }, { id: "SPAM", nome: "Spam", total: 2, nao_lidas: 2 }, { id: "TRASH", nome: "Lixeira", total: 4, nao_lidas: 0 }] };
      case "/api/gmail/conversas": return { itens: gmailThreads, proxima: null };
      case "/api/gmail/conversa": return conversaGmail(p.q.id);
      case "/api/nexora/envio": return { enviando: false, log: [] };
      default: return { ok: true };
    }
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async (url, opts) => {
    if (typeof url === "string" && url.startsWith("/api/")) {
      const p = parse(url);
      let corpo;
      if (opts && opts.method === "POST") {
        const b = opts.body ? JSON.parse(opts.body) : {};
        if (p.path === "/api/validar") corpo = { violacoes: [] };
        else if (p.path === "/api/nexora/enviar") corpo = { a_enviar: 2, minutos_estimados: 1.5 };
        else if (p.path === "/api/mover") {
          const alvo = Object.values(CONTAS).flatMap((x) => x.leads).find((l) => l[0] === b.ref);
          if (alvo) alvo[3] = b.etapa;
          corpo = { ok: true, demo: true };
        } else if (p.path === "/api/traduzir") corpo = { traducao: b.para === "pt" ? "(demonstração) Tradução para o português." : "(demo) English translation.", cache: false, de: b.de, para: b.para };
        else corpo = { ok: true, demo: true };
        void b;
      } else corpo = responder(conta(p), p);
      return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return realFetch(url, opts);
  };
})();
