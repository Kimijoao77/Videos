// Investimentos no computador (11/11/2026): os mesmos dados que o app Nexus usa, num painel largo.
// - Placar (testes de mentira, preços de verdade): radar-hyperliquid/saida/*.json, público, sem token.
// - Ping pong (o seu dinheiro): progresso/macros.json do repositório privado, que o app envia a cada sincronização.
// - Ideias (WhatsApp e YouTube): ideias/ do repositório privado, gravadas pelas tarefas das 5h.
// O token fica só neste navegador (o mesmo da Máquina no computador). Nada daqui grava no repositório.
import { temToken, salvarConfig, esquecer, configPC, baixarTexto } from "./js/dados.js";

const BASE = window.PLACAR_BASE || "https://raw.githubusercontent.com/Kimijoao77/radar-hyperliquid/main/saida/";
// 11/11: "ideias" = os testes que o Claude cria a partir das ideias dos vídeos (lab/ideias no radar-hyperliquid)
const ARQS = ["copia_fiel", "grade", "cofres", "concentradas", "apostas", "listagens", "ideias"];
const CDI_AO_ANO = 0.1365;            // Selic 13,75 % (Copom de 04/11/2026) menos 0,10: o mesmo do app
const ABAS = [["geral", "Visão geral"], ["pingpong", "Ping pong"], ["placar", "Placar"], ["ideias", "Ideias"]];
const BANCOS = { mp: "Mercado Pago", astro: "AstroPay", "99": "99Pay", "": "sem destino" };
const REGUA = 0.45;                   // a régua do João: só interessa o que rende 45 % ao ano ou mais
// Os horários do ping pong (ida do Arq às :45, volta meia hora depois)
const HORARIOS = [["17:45", "Mercado Pago"], ["20:45", "AstroPay"], ["23:45", "99Pay"]];
const MOEDAS = ["BTC", "ETH", "SOL", "HYPE"];
// O que é cada teste, em português simples (o mesmo do documento "Estratégias do Placar")
const INFO = {
  copia: { onde: "Hyperliquid", risco: 3, oque: "Segue carteiras com lucro consistente: quando elas mudam de posição, a cópia faz o mesmo 1 minuto depois, na mesma proporção do saldo.",
    ganha: "Quando as carteiras copiadas acertam.", perde: "Quando erram, e com o atraso de 1 minuto; uma carteira só pode carregar o resultado." },
  tendencia: { onde: "Hyperliquid", risco: 4, oque: "Fica sempre no mercado: comprado quando o preço sobe e vendido quando cai (médias de 2 e 7 dias, ou rompimento de 10 dias), com 2× a 3×.",
    ganha: "Em tendências longas, para cima ou para baixo.", perde: "Em mercado de lado; no histórico teve quedas de 48 % a 81 % no caminho." },
  dca: { onde: "Hyperliquid", risco: 3, oque: "Compra um pouco, compra mais a cada queda (cada compra 1,5 vez a anterior) e vende tudo um pouco acima do preço médio.",
    ganha: "Quase sempre, em sobe e desce.", perde: "Numa queda grande e sem volta: prende o dinheiro e, com 3×, pode zerar." },
  reversao: { onde: "Hyperliquid", risco: 3, oque: "Espera um movimento forte (5 % a 8 % em 24 h) e aposta na volta, com alvo pequeno.",
    ganha: "Quando o exagero do mercado se corrige.", perde: "Quando o movimento continua." },
  cofres: { onde: "Hyperliquid", risco: 2, oque: "O HLP é o cofre da própria Hyperliquid: faz o papel de banca e assume as liquidações. Deposita uma vez e rende sozinho.",
    ganha: "Com a diferença de compra e venda, taxas e liquidações.", perde: "Em liquidações grandes que dão errado; o dinheiro fica preso 4 dias." },
  cofres_risco: { onde: "Hyperliquid", risco: 4, oque: "Cofres de traders: você deposita e o dono opera com o dinheiro de todos (ele fica com 10 % do lucro).",
    ganha: "Quando o trader acerta.", perde: "Quando ele erra: estes cofres já caíram de 13 % a 51 % no passado." },
  concentradas: { onde: "Meteora (Solana)", risco: 4, oque: "Deixa SOL ou USDC numa faixa logo abaixo do preço de uma moeda nova e ganha parte da taxa de cada troca.",
    ganha: "Com as taxas, enquanto o preço fica na faixa.", perde: "Se a moeda despenca: você termina com ela no lugar do SOL." },
  apostas: { onde: "Bolsa de apostas", risco: 3, oque: "Só aposta quando a odd está acima da justa.", ganha: "No longo prazo, se a vantagem existir.", perde: "Em sequências ruins; a vantagem pode ter sido sorte da escolha." },
  listagens: { onde: "Hyperliquid", risco: 4, oque: "Vende (aposta na queda) uma moeda 24 h depois que ela estreia, com parada em +30 %.", ganha: "Quando a moeda nova murcha, o mais comum.", perde: "Quando ela dispara." },
};
const RISCO = ["", "baixo", "médio", "alto", "muito alto"];

const $ = (s, el = document) => el.querySelector(s);
const tela = $("#tela"), abas = $("#abas"), acoes = $("#acoes");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---------- formatos ----------
const pct = (x, casas = 2) => x == null || !Number.isFinite(x) ? "—" : (x >= 0 ? "+" : "−") + Math.abs(x * 100).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }) + "%";
const reais = (v, sinal = false) => v == null ? "—" : (sinal ? (v >= 0 ? "+" : "−") : (v < 0 ? "−" : "")) + "R$ " + Math.abs(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const cls = (v) => v > 0 ? "pos" : v < 0 ? "neg" : "";
const diaBR = (iso) => { const [a, m, d] = iso.slice(0, 10).split("-"); return `${d}/${m}`; };
const dataCurta = (ms) => new Date(ms).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "America/Sao_Paulo" });
const dataHora = (ms) => new Date(ms).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" });
const media = (v) => v.length ? v.reduce((a, x) => a + x, 0) / v.length : 0;
const cdi = (desde, ate = Date.now()) => Math.pow(1 + CDI_AO_ANO, Math.max(0, ate - desde) / (365 * 86400000)) - 1;
const diasDesde = (ms) => Math.max(1, Math.round((Date.now() - ms) / 86400000));
const emDias = (ms) => { const n = diasDesde(ms); return `${n} ${n === 1 ? "dia" : "dias"}`; };
/** Marcas "redondas" para o eixo y (1, 2, 2,5 ou 5 vezes uma potência de 10). */
function marcas(lo, hi, n = 5) {
  const passo0 = (hi - lo) / (n - 1) || 1, p = Math.pow(10, Math.floor(Math.log10(passo0)));
  const passo = [1, 2, 2.5, 5, 10].map(k => k * p).find(k => k >= passo0) || passo0;
  const a = Math.floor(lo / passo) * passo, out = [];
  for (let v = a; v <= hi + passo * 0.001; v += passo) out.push(Math.round(v / passo) * passo);
  return out;
}

// ---------- estado ----------
const D = { placar: null, pp: null, ideias: null, yt: null, mercado: null, quando: null, erros: [], carregando: false };
let testeAberto = null, filtroYT = "todos", filtroEventos = "todos";

// ---------- gráficos (SVG à mão, com dica ao passar o mouse) ----------
let nGraf = 0;
/** Linha no tempo. series: [{nome, pts: [[ms, y]], ref?}] (a 1ª é a principal). fmt: formata o valor do eixo y. */
function grafLinha(series, { fmt = null, altura = 260, area = false, fmtDica, W = 800, semLegenda = false, semEixoX = false } = {}) {
  const id = `g${++nGraf}`, H = altura, PL = 58, PR = 18, PT = 14, PB = 28;
  const todos = series.flatMap(s => s.pts);
  if (todos.length < 2) return `<p class="iv-vazio">O gráfico aparece quando houver mais pontos.</p>`;
  const xs = todos.map(p => p[0]), ys = todos.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (series.some(s => s.zero)) { y0 = Math.min(0, y0); y1 = Math.max(0, y1); }
  const pad = (y1 - y0) * 0.08 || Math.abs(y1) * 0.02 || 1; y0 -= pad; y1 += pad;
  const tk = marcas(y0, y1); y0 = Math.min(y0, tk[0]); y1 = Math.max(y1, tk.at(-1));
  const X = (x) => PL + (x - x0) / ((x1 - x0) || 1) * (W - PL - PR), Y = (y) => PT + (y1 - y) / ((y1 - y0) || 1) * (H - PT - PB);
  const ticks = tk;
  if (!fmt) { const passo = Math.abs((tk[1] ?? tk[0]) - tk[0]) || 0.01, casas = Math.max(0, Math.min(3, Math.ceil(-Math.log10(passo * 100) + 0.0001)));
    fmt = (v) => Math.abs(v) < passo / 1000 ? "0%" : pct(v, casas); }
  const curto_ = (x1 - x0) < 3 * 86400000, nx = curto_ ? 6 : Math.min(7, Math.max(2, Math.round((x1 - x0) / 86400000)));
  const rotX = (t) => curto_ ? new Date(t).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }).replace(",", "") : dataCurta(t);
  const xt = Array.from({ length: nx + 1 }, (_, i) => x0 + (x1 - x0) * i / nx).filter((t, i, a) => !i || rotX(t) !== rotX(a[i - 1]));
  const caminho = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join(" ");
  const pri = series[0];
  const areaD = area && pri.pts.length > 1 ? `${caminho(pri.pts)} L${X(pri.pts.at(-1)[0]).toFixed(1)} ${Y(y0).toFixed(1)} L${X(pri.pts[0][0]).toFixed(1)} ${Y(y0).toFixed(1)}Z` : "";
  const u = pri.pts.at(-1);
  const svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(pri.nome)}">
    ${ticks.map(t => `<line class="grid" x1="${PL}" x2="${W - PR}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/><text x="${PL - 8}" y="${(Y(t) + 4).toFixed(1)}" text-anchor="end">${esc(fmt(t))}</text>`).join("")}
    ${series.some(s => s.zero) && y0 < 0 && y1 > 0 ? `<line class="zero" x1="${PL}" x2="${W - PR}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}"/>` : ""}
    ${semEixoX ? "" : xt.map(t => `<text x="${X(t).toFixed(1)}" y="${H - 8}" text-anchor="middle">${rotX(t)}</text>`).join("")}
    ${areaD ? `<path class="area" d="${areaD}"/>` : ""}
    ${series.slice().reverse().map(s => `<path class="linha${s.ref ? " ref" : ""}" d="${caminho(s.pts)}"/>`).join("")}
    ${u ? `<circle class="pto" cx="${X(u[0]).toFixed(1)}" cy="${Y(u[1]).toFixed(1)}" r="4.5"/>` : ""}
    <line class="mira" id="${id}-m" x1="0" x2="0" y1="${PT}" y2="${H - PB}" visibility="hidden"/>
    <rect id="${id}-h" x="${PL}" y="${PT}" width="${W - PL - PR}" height="${H - PT - PB}" fill="transparent"/>
  </svg>`;
  const fd = fmtDica || ((v) => pct(v, 2));
  setTimeout(() => ligarDica(id, { W, X, x0, x1, PL, PR, series, fmtDica: fd }), 0);
  const leg = series.length > 1 && !semLegenda ? `<div class="iv-legenda">${series.map(s => `<span><i class="${s.ref ? "ref" : ""}"></i>${esc(s.nome)}</span>`).join("")}</div>` : "";
  return `<div class="iv-graf" id="${id}">${svg}</div>${leg}`;
}
function ligarDica(id, g) {
  const box = document.getElementById(id); if (!box) return;
  const svg = box.querySelector("svg"), h = document.getElementById(`${id}-h`), m = document.getElementById(`${id}-m`);
  let dica = null;
  const perto = (pts, t) => pts.reduce((b, p) => Math.abs(p[0] - t) < Math.abs(b[0] - t) ? p : b, pts[0]);
  h.addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect(), esc_ = g.W / r.width, xv = (e.clientX - r.left) * esc_;
    const t = g.x0 + (xv - g.PL) / (g.W - g.PL - g.PR) * (g.x1 - g.x0);
    const p0 = perto(g.series[0].pts, t), xx = g.X(p0[0]);
    m.setAttribute("x1", xx); m.setAttribute("x2", xx); m.setAttribute("visibility", "visible");
    if (!dica) { dica = document.createElement("div"); dica.className = "iv-dica"; box.appendChild(dica); }
    dica.innerHTML = `${dataHora(p0[0])}<br>${g.series.map(s => { const p = perto(s.pts, p0[0]); return `${esc(s.nome)}: <b>${esc(g.fmtDica(p[1]))}</b>`; }).join("<br>")}`;
    dica.style.left = `${xx / esc_}px`; dica.style.top = `${(e.clientY - r.top)}px`;
  });
  h.addEventListener("mouseleave", () => { m.setAttribute("visibility", "hidden"); dica?.remove(); dica = null; });
}
/** Barras verticais com zero no meio (ganho azul, perda vermelha). itens: [{rot, v, dica}] */
function grafBarras(itens, { fmt = (v) => reais(v, true), altura = 220, W = 600 } = {}) {
  if (!itens.length) return `<p class="iv-vazio">Sem dados ainda.</p>`;
  const id = `g${++nGraf}`, H = altura, PL = 66, PR = 12, PT = 14, PB = 28;
  const vs = itens.map(i => i.v), y0 = Math.min(0, ...vs), y1 = Math.max(0, ...vs), amp = (y1 - y0) || 1;
  const Y = (v) => PT + (y1 - v) / amp * (H - PT - PB), passo = (W - PL - PR) / itens.length, bw = Math.max(4, Math.min(42, passo - 2));
  const ticks = [y0, (y0 + y1) / 2, y1].filter((v, i, a) => a.indexOf(v) === i);
  const barras = itens.map((it, i) => {
    const cx = PL + passo * (i + .5), ya = Y(Math.max(0, it.v)), yb = Y(Math.min(0, it.v)), h = Math.max(1, yb - ya);
    return `<g data-i="${i}"><rect class="${it.v >= 0 ? "bar-pos" : "bar-neg"}" x="${(cx - bw / 2).toFixed(1)}" y="${ya.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3"/>
      <rect x="${(cx - passo / 2).toFixed(1)}" y="${PT}" width="${passo.toFixed(1)}" height="${H - PT - PB}" fill="transparent"/>
      ${itens.length <= 16 || i % Math.ceil(itens.length / 12) === 0 ? `<text x="${cx.toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(it.rot)}</text>` : ""}</g>`;
  }).join("");
  const svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Barras">
    ${ticks.map(t => `<line class="grid" x1="${PL}" x2="${W - PR}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/><text x="${PL - 8}" y="${(Y(t) + 4).toFixed(1)}" text-anchor="end">${esc(fmt(t))}</text>`).join("")}
    <line class="zero" x1="${PL}" x2="${W - PR}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}"/>${barras}</svg>`;
  setTimeout(() => {
    const box = document.getElementById(id); if (!box) return;
    let dica = null;
    box.querySelectorAll("g[data-i]").forEach(g => {
      g.addEventListener("mouseenter", () => {
        const it = itens[+g.dataset.i], r = box.querySelector("svg").getBoundingClientRect(), k = r.width / W;
        dica = document.createElement("div"); dica.className = "iv-dica";
        dica.innerHTML = it.dica || `${esc(it.rot)}: <b>${esc(fmt(it.v))}</b>`;
        dica.style.left = `${(PL + passo * (+g.dataset.i + .5)) * k}px`; dica.style.top = `${Y(Math.max(0, it.v)) * k}px`;
        box.appendChild(dica);
      });
      g.addEventListener("mouseleave", () => { dica?.remove(); dica = null; });
    });
  }, 0);
  return `<div class="iv-graf" id="${id}">${svg}</div>`;
}
/** Barras deitadas (uma por teste), zero no meio. */
function grafRanking(itens) {
  if (!itens.length) return `<p class="iv-vazio">Sem testes ainda.</p>`;
  const W = 1240, ROT = 230, VAL = 90, AL = 34, H = itens.length * AL + 8;
  const vs = itens.map(i => i.v), lo = Math.min(0, ...vs), hi = Math.max(0, ...vs), amp = (hi - lo) || 1e-9;
  const X = (v) => ROT + (v - lo) / amp * (W - ROT - VAL);
  return `<div class="iv-graf"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Resultado de cada teste">
    <line class="zero" x1="${X(0).toFixed(1)}" x2="${X(0).toFixed(1)}" y1="0" y2="${H}"/>
    ${itens.map((it, i) => { const y = 4 + i * AL, a = X(Math.min(0, it.v)), b = X(Math.max(0, it.v));
      return `<g><title>${esc(it.rot)}: ${esc(pct(it.v))} em ${it.dias} ${it.dias === 1 ? "dia" : "dias"}</title>
        <text x="${ROT - 12}" y="${y + 17}" text-anchor="end" style="fill:var(--tinta);font-size:13px">${esc(it.rot)}</text>
        <rect class="${it.v >= 0 ? "bar-pos" : "bar-neg"}" x="${a.toFixed(1)}" y="${y + 5}" width="${Math.max(2, b - a).toFixed(1)}" height="16" rx="3"/>
        <text class="rot" x="${(it.v >= 0 ? b + 8 : X(0) + 8).toFixed(1)}" y="${y + 17}" text-anchor="start">${esc(pct(it.v))}</text></g>`; }).join("")}
  </svg></div>`;
}
function spark(curva) {
  if (!curva || curva.length < 2) return `<svg viewBox="0 0 84 30"></svg>`;
  const xs = curva.map(p => p[0]), ys = curva.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys), y1 = Math.max(0, ...ys), dy = (y1 - y0) || 1e-9;
  const X = (x) => 2 + (x - x0) / ((x1 - x0) || 1) * 80, Y = (y) => 28 - (y - y0) / dy * 26;
  const u = curva.at(-1)[1];
  return `<svg viewBox="0 0 84 30" aria-hidden="true"><line class="zero" x1="0" x2="84" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}"/>
    <path d="${curva.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join(" ")}" style="stroke:var(${u >= 0 ? "--ganho" : "--perda"})"/></svg>`;
}

// ---------- Placar: os arquivos viram uma linha por teste (as mesmas contas do app) ----------
function curvaNoTempo(cs, cap) {
  const ts = [...new Set(cs.flatMap(c => c.map(p => p[0])))].sort((a, b) => a - b), k = cs.map(() => -1);
  return ts.map(t => [t, media(cs.map((c, i) => { while (k[i] + 1 < c.length && c[k[i] + 1][0] <= t) k[i]++; return k[i] >= 0 ? c[k[i]][1] / cap - 1 : 0; }))]);
}
function montarPlacar(d) {
  const out = [];
  const cv = d.copia_fiel?.variantes?.seletiva;
  if (cv?.carteiras) {
    const subs = cv.subcontas || [];
    out.push({ id: "copia", nome: "Copy trading", como: `${cv.carteiras} carteiras · até 3× · parada em −25%`, desde: d.copia_fiel.inicio, retorno: cv.retorno,
      curva: [[d.copia_fiel.inicio, 0], ...(cv.curva || [])],
      numeros: [["Resultado", pct(cv.retorno)], ["Carteiras no lucro", `${subs.filter(x => x.retorno > 0).length} de ${subs.length}`], ["Ordens copiadas", (cv.ordens || 0).toLocaleString("pt-BR")], ["Taxas pagas", pct(-(cv.taxas || 0) / Math.max(1, cv.capital))]],
      itens: subs.map(x => ({ nome: x.apelido || `${x.w.slice(0, 6)}…${x.w.slice(-4)}`, r: x.retorno, sub: x.parou ? `parou: ${x.parou}` : `${(x.ordens || 0).toLocaleString("pt-BR")} ordens` })).sort((a, b) => b.r - a.r),
      ops: (cv.ordens_recentes || []).map(o => ({ t: o.t, titulo: `${o.lado === "compra" ? "Comprou" : "Vendeu"} ${o.moeda}`, sub: `US$ ${Math.round(o.valor).toLocaleString("pt-BR")}${o.obs ? ` · ${o.obs}` : ""}` })) });
  }
  const g = d.grade?.ao_vivo;
  if (g?.length) {
    const cap = d.grade.capital, zero = { final: cap, curva: [], pior_queda: 0, ciclos: 0, segurar_moeda: 0, funding_pago: 0 };
    const todos = g.map(x => ({ ...x, resultado: x.resultado || zero })), ini = (x) => x.inicio || d.grade.inicio_ao_vivo;
    for (const [id, nome, sel] of [["tendencia", "Robôs de tendência", x => x.config?.tipo === "tendencia"], ["dca", "Robôs de grade e DCA", x => ["grade", "dca"].includes(x.config?.tipo)],
      ["reversao", "Robôs de reversão", x => x.config?.tipo === "reversao"]]) {
      const gv = todos.filter(sel); if (!gv.length) continue;
      const rs = gv.map(x => x.resultado.final / cap - 1), desde = Math.min(...gv.map(ini));
      out.push({ id, nome, como: `${gv.length} robôs: ${[...new Set(gv.map(x => x.moeda))].join(", ")}`, desde, retorno: media(rs),
        curva: [[desde, 0], ...curvaNoTempo(gv.map(x => [[ini(x), cap], ...(x.resultado.curva || [])]), cap)],
        numeros: [["Resultado (média)", pct(media(rs))], ["Melhor robô", pct(Math.max(...rs))], ["Pior robô", pct(Math.min(...rs))], ["Maior queda no caminho", pct(-Math.max(...gv.map(x => x.resultado.pior_queda || 0)))]],
        queda: Math.max(...gv.map(x => x.resultado.pior_queda || 0)),
        itens: gv.map(x => ({ nome: `${x.moeda} · ${x.nome}`, r: x.resultado.final / cap - 1, sub: `só segurar ${x.moeda}: ${pct(x.resultado.segurar_moeda || 0)} · ${x.resultado.ciclos || 0} ciclos` })).sort((a, b) => b.r - a.r),
        ops: gv.flatMap(x => (x.resultado.ops || []).map(o => ({ t: o.t, titulo: `${o.tipo === "venda" ? "Vendeu" : "Comprou"} ${x.moeda} a US$ ${Number(o.px).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`, sub: `${o.obs || ""}${o.lucro != null ? ` · lucro US$ ${o.lucro.toLocaleString("pt-BR")}` : ""}` }))) });
    }
  }
  for (const [id, nome, como, k] of [["cofres", "Cofre HLP", "O cofre da própria Hyperliquid", d.cofres?.carteira], ["cofres_risco", "Cofres de risco", "Cofres de traders de maior retorno", d.cofres?.risco]]) {
    if (!k?.capital) continue;
    out.push({ id, nome, como, desde: k.inicio, retorno: k.saldo / k.capital - 1,
      curva: k.curva?.length ? [[k.inicio, 0], ...k.curva.map(([t, v]) => [t, v / k.capital - 1])] : [[k.inicio, 0], [d.cofres.gerado, k.saldo / k.capital - 1]],
      numeros: [["Resultado", pct(k.saldo / k.capital - 1)], ["Cofres", String((k.itens || []).length)]],
      itens: (k.itens || []).map(i => ({ nome: i.nome, r: i.rendeu ?? 0, sub: [i.ao_ano != null ? `no passado ${pct(i.ao_ano, 0).replace("+", "")} ao ano` : "", i.apr != null ? `agora ${pct(i.apr, 0).replace("+", "")} ao ano` : "", i.queda != null ? `pior queda ${Math.round(i.queda * 100)}%` : ""].filter(Boolean).join(" · ") })).sort((a, b) => b.r - a.r) });
  }
  const cc = d.concentradas?.faixas;
  if (cc && d.concentradas.capital) {
    const cap = d.concentradas.capital, fs = Object.values(cc), rs = fs.map(f => f.patrimonio / cap - 1);
    out.push({ id: "concentradas", nome: "Pools concentradas", como: "Meteora: só SOL ou USDC abaixo do preço", desde: d.concentradas.inicio, retorno: media(rs),
      curva: [[d.concentradas.inicio, 0], ...curvaNoTempo(fs.map(f => f.curva || []), cap)],
      numeros: [["Resultado (média)", pct(media(rs))], ...fs.map(f => [f.nome.replace(/ \(.*\)/, ""), pct(f.patrimonio / cap - 1)])],
      itens: fs.flatMap(f => (f.abertas || []).map(a => ({ nome: a.nome, r: a.r, sub: `${f.nome} · ${a.dentro ? "dentro da faixa" : "fora da faixa"} · taxas ${pct(a.taxas)}` }))).sort((a, b) => b.r - a.r),
      ops: fs.flatMap(f => [...(f.abertas || []).map(a => ({ t: a.entrou, titulo: `Entrou em ${a.nome}`, sub: f.nome })), ...(f.fechadas || []).map(x => ({ t: x.saiu, titulo: `Saiu de ${x.nome}`, sub: `${f.nome} · ${x.motivo || ""} · ${pct(x.r)}` }))]) });
  }
  const av = d.apostas?.ao_vivo;
  if (av && d.apostas.capital && !d.apostas.desligado) {
    const cap = d.apostas.capital;
    out.push({ id: "apostas", nome: "Apostas esportivas", como: "Só com odd acima da justa", desde: av.inicio, retorno: av.saldo / cap - 1,
      curva: [[av.inicio, 0], ...(av.curva || []).map(([t, v]) => [t, v / cap - 1])],
      numeros: [["Resultado", pct(av.saldo / cap - 1)], ["Apostas terminadas", av.apostas ? `${av.acertos} acertos em ${av.apostas}` : "nenhuma ainda"]], itens: [] });
  }
  const lv = d.listagens?.ao_vivo;
  if (lv && d.listagens.capital) {
    const vs = Object.entries(lv.variantes || {}), rs = vs.map(([, v]) => v.retorno);
    out.push({ id: "listagens", nome: "Vender moeda nova", como: "Short 24 h depois da estreia", desde: lv.inicio, retorno: rs.length ? media(rs) : 0,
      curva: [[lv.inicio, 0], [d.listagens.gerado || Date.now(), rs.length ? media(rs) : 0]],
      numeros: [["Resultado (média)", pct(rs.length ? media(rs) : 0)], ["Operações ao vivo", String((lv.operacoes || []).length)]], itens: [] });
  }
  // testes das ideias dos vídeos: cada um traz a página dele (guia) e o vídeo de onde veio
  for (const ti of d.ideias?.testes || []) {
    if (!ti?.id || ti.capital == null || ti.desde == null) continue;
    const id = `ideia_${ti.id}`, cap = ti.capital || 1000, g = ti.guia || {}, m = ti.moeda || "US$";
    const dinheiro = (v) => `${m} ${Number(v).toLocaleString("pt-BR", { maximumFractionDigits: Math.abs(v) < 10 ? 4 : 2 })}`;
    INFO[id] = { onde: (g.onde || []).join(", ") || "simulação", risco: g.risco || 3, oque: ti.como || "", ganha: g.ganha || "Quando a ideia do vídeo funciona com os preços de verdade.",
      perde: g.perde || "Quando a ideia não funciona, ou os custos comem o ganho.", origem: ti.origem || {} };
    out.push({ id, ideia: true, nome: `${ti.nome || ti.id}${ti.parado ? " (parado)" : ""}`, como: `Ideia de vídeo · ${ti.como || ""}`, desde: ti.desde, retorno: ti.retorno ?? 0,
      curva: [[ti.desde, 0], ...(ti.curva || []).map(([t, v]) => [t, v / cap - 1])],
      numeros: [["Resultado", pct(ti.retorno ?? 0)], ["Saldo de mentira", dinheiro(ti.saldo ?? cap)], ["Taxas pagas", dinheiro(ti.taxas || 0)], ["Rendimentos e custos", dinheiro(ti.creditos || 0)]],
      itens: Object.entries(ti.posicoes || {}).map(([a, p]) => ({ nome: a, r: 0, sub: `${p.lado === "venda" ? "vendido" : "comprado"} · preço médio ${dinheiro(p.preco_medio)}` })),
      ops: (ti.ops || []).map(o => ({ t: o.t, titulo: `${{ compra: "Comprou", venda: "Vendeu", venda_descoberto: "Vendeu a descoberto", recompra: "Recomprou", credito: "Recebeu", custo: "Pagou" }[o.tipo] || o.tipo} ${o.ativo || dinheiro(Math.abs(o.valor || 0))}`,
        sub: [o.ativo && o.valor != null ? dinheiro(o.valor) : "", o.preco ? `preço ${dinheiro(o.preco)}` : "", o.obs].filter(Boolean).join(" · ") })),
      nota: [ti.nota, ti.erro ? `Erro: ${ti.erro}` : ""].filter(Boolean).join(" · ") });
  }
  return out.filter(t => Number.isFinite(t.retorno)).sort((a, b) => b.retorno - a.retorno);
}

// ---------- Ping pong: os dias do registro que o app envia ----------
function pingPong(m) {
  const dias = (m?.dias || []).filter(d => d.saldo != null).sort((a, b) => a.dia.localeCompare(b.dia));
  const com = dias.filter(d => d.lucro != null);
  const soma = (n) => { const s = com.slice(-n); return s.length ? s.reduce((a, d) => a + d.lucro, 0) : null; };
  const taxas = []; for (let i = 1; i < dias.length; i++) if (dias[i].lucro != null && dias[i - 1].saldo) taxas.push(dias[i].lucro / dias[i - 1].saldo);
  const t30 = taxas.slice(-30), diaria = t30.length >= 3 ? Math.exp(media(t30.map(x => Math.log(1 + x)))) - 1 : null;
  const porBanco = {};
  for (const d of dias) for (const c of d.ciclos || []) if (c.ganho != null) { const k = c.dest || ""; (porBanco[k] ||= { ganho: 0, ciclos: 0 }); porBanco[k].ganho += c.ganho; porBanco[k].ciclos++; }
  const saldo = m?.saldo?.valor ?? dias.at(-1)?.saldo ?? null;
  return { dias, saldo, quando: m?.saldo?.quando, atualizado: m?.atualizado, semana: soma(7), mes: soma(30), total: com.reduce((a, d) => a + d.lucro, 0),
    aoMes: diaria != null ? Math.pow(1 + diaria, 30) - 1 : null, aoAno: diaria != null ? Math.pow(1 + diaria, 365) - 1 : null,
    porBanco, eventos: (m?.eventos || []).slice().sort((a, b) => b.quando.localeCompare(a.quando)) };
}

// ---------- carregar ----------
async function carregar() {
  if (D.carregando) return;
  D.carregando = true; D.erros = []; desenharAcoes();
  const placar = Promise.all(ARQS.map(async k => { try { const r = await fetch(`${BASE}${k}.json?t=${Date.now()}`, { cache: "no-store" }); return [k, r.ok ? await r.json() : null]; } catch { return [k, null]; } }))
    .then(ps => { D.placar = montarPlacar(Object.fromEntries(ps)); if (!D.placar.length) D.erros.push("Não consegui baixar o Placar agora."); });
  const json = async (c) => { const t = await baixarTexto(c); return t ? JSON.parse(t) : null; };
  const pp = json("progresso/macros.json").then(m => { D.pp = pingPong(m); }).catch(e => D.erros.push(`Ping pong: ${e.message}`));
  const ideias = json("ideias/whatsapp/ultimas.json").then(x => { D.ideias = x; }).catch(e => D.erros.push(`Ideias do WhatsApp: ${e.message}`));
  // 11/11: um arquivo só (resumo.py) com todos os vídeos assistidos, o potencial do Gemini e o veredito do Claude
  const yt = json("ideias/youtube/resumo.json").then(r => { D.ytResumo = r; D.yt = r?.videos || []; }).catch(e => D.erros.push(`Ideias do YouTube: ${e.message}`));
  const mercado = fetch("https://api.hyperliquid.xyz/info", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: "metaAndAssetCtxs" }) })
    .then(r => r.ok ? r.json() : null).then(j => {
      if (!j) return;
      const [meta, ctx] = j;
      D.mercado = MOEDAS.map(m => { const i = meta.universe.findIndex(u => u.name === m); const c = ctx[i];
        return c ? { moeda: m, preco: +c.markPx, dia: +c.markPx / +c.prevDayPx - 1, funding: +c.funding * 24 * 365 } : null; }).filter(Boolean);
    }).catch(() => { D.mercado = null; });
  await Promise.all([placar, pp, ideias, yt, mercado]);
  D.quando = Date.now(); D.carregando = false;
  desenharAcoes(); irPara(tela.dataset.tela || location.hash.slice(1));
}

// ---------- telas ----------
const tile = (rot, valor, sub = "", classe = "", extra = "") => `<div class="iv-card iv-tile ${extra}"><small>${esc(rot)}</small><b class="${classe}">${valor}</b>${sub ? `<span>${sub}</span>` : ""}</div>`;
const erros = () => D.erros.length ? `<p class="iv-erro">${D.erros.map(esc).join("<br>")}</p>` : "";
const carregando = () => `<p class="iv-vazio">Carregando os dados do GitHub…</p>`;

/** Barra de comparação (ritmo ao ano do ping pong × régua × CDI). */
function bala(valor, alvo, ref) {
  const mx = Math.max(valor ?? 0, alvo, ref) * 1.15, w = (v) => `${Math.max(0, Math.min(100, v / mx * 100)).toFixed(1)}%`;
  return `<div class="iv-bala" role="img" aria-label="Ritmo ao ano comparado com a régua e o CDI">
    <div class="trilho"><span class="ref" style="left:${w(ref)}"></span><span class="alvo" style="left:${w(alvo)}"></span>
      ${valor != null ? `<span class="valor ${valor >= alvo ? "ok" : ""}" style="width:${w(valor)}"></span>` : ""}</div>
    <div class="marcas"><span style="left:${w(ref)}">CDI ${pct(ref, 0).replace("+", "")}</span><span style="left:${w(alvo)}">régua ${pct(alvo, 0).replace("+", "")}</span></div></div>`;
}
function proximoCiclo() {
  const agora = new Date(new Date().toLocaleString("en-US", { timeZone: "America/Sao_Paulo" }));
  for (const dia of [0, 1]) for (const [h, banco] of HORARIOS) {
    const [hh, mm] = h.split(":").map(Number), t = new Date(agora); t.setDate(t.getDate() + dia); t.setHours(hh, mm, 0, 0);
    if (t > agora) { const min = Math.round((t - agora) / 60000); return { h, banco, falta: min >= 60 ? `${Math.floor(min / 60)} h ${min % 60} min` : `${min} min` }; }
  }
  return null;
}
function tickers() {
  if (!D.mercado?.length) return "";
  return `<div class="iv-ticker">${D.mercado.map(m => `<div><b>${m.moeda}</b><span class="num">US$ ${m.preco.toLocaleString("pt-BR", { maximumFractionDigits: m.preco < 100 ? 3 : 0 })}</span>
    <span class="num ${cls(m.dia)}">${pct(m.dia)}</span><small title="Funding: o que quem está comprado paga por ano">funding ${pct(m.funding, 1)} a.a.</small></div>`).join("")}
    <p class="iv-nota">Preços da Hyperliquid agora · variação em 24 h</p></div>`;
}
function curvasPequenas(t) {
  return `<div class="iv-mini">${t.map(x => { const fim = Math.max(...x.curva.map(p => p[0]));
    return `<button class="iv-card iv-mini-c" data-ir-teste="${x.id}"><div class="cab"><b>${esc(x.nome)}</b><span class="num ${cls(x.retorno)}">${pct(x.retorno)}</span></div>
      ${grafLinha([{ nome: x.nome, pts: x.curva, zero: true }, { nome: "CDI", ref: true, pts: [0, .5, 1].map(k => x.desde + (fim - x.desde) * k).map(tt => [tt, cdi(x.desde, tt)]) }], { altura: 150, W: 360, semLegenda: true, semEixoX: true })}
      <small>${emDias(x.desde)} · risco ${RISCO[INFO[x.id]?.risco] || "—"}</small></button>`; }).join("")}</div>`;
}
function tabelaRanking(t) {
  if (!t.length) return `<p class="iv-vazio">Sem testes ainda.</p>`;
  const mx = Math.max(...t.map(x => Math.abs(x.retorno)), 1e-6);
  return `<table class="iv-tab iv-rank"><thead><tr><th>Teste</th><th class="barra-h">Resultado</th><th class="n">%</th><th class="n">CDI no período</th><th class="n">Diferença</th><th class="n">Tempo</th><th>Risco</th></tr></thead><tbody>
    ${t.map(x => { const c = cdi(x.desde), d = x.retorno - c, w = Math.abs(x.retorno) / mx * 50;
      return `<tr data-ir-teste="${x.id}" tabindex="0"><td><b>${esc(x.nome)}</b><small>${esc(INFO[x.id]?.onde || "")}</small></td>
        <td class="barra-h"><div class="iv-bh"><span class="zero"></span><span class="${x.retorno >= 0 ? "p" : "n"}" style="${x.retorno >= 0 ? `left:50%;width:${w}%` : `right:50%;width:${w}%`}"></span></div></td>
        <td class="n ${cls(x.retorno)}"><b>${pct(x.retorno)}</b></td><td class="n">${pct(c, 2)}</td><td class="n ${cls(Math.round(d * 1e4))}">${Math.abs(d) < 5e-5 ? "0,00 p.p." : pct(d, 2).replace("%", " p.p.")}</td>
        <td class="n">${emDias(x.desde)}</td><td><span class="iv-selo r${INFO[x.id]?.risco || 0}">${RISCO[INFO[x.id]?.risco] || "—"}</span></td></tr>`; }).join("")}</tbody></table>`;
}
function telaGeral() {
  if (!D.quando) { tela.innerHTML = carregando(); return; }
  const p = D.pp, t = D.placar || [], prox = proximoCiclo();
  const ideiasHoje = D.ideias?.dias?.[0], ytTestar = (D.yt || []).filter(v => ["testar", "apresentar", "automatizado"].includes(v.claude?.veredito));
  const falhas = (p?.eventos || []).filter(e => e.tipo === "falha" && Date.now() - Date.parse(e.quando) < 3 * 86400000);
  const ult = p?.dias?.filter(d => d.lucro != null).at(-1);
  tela.innerHTML = `${erros()}
    <section class="iv-hero">
      <div><small>Patrimônio no ping pong</small><b class="num">${p?.saldo != null ? reais(p.saldo) : "—"}</b>
        <span>${p?.semana != null ? `<em class="${cls(p.semana)}">${reais(p.semana, true)}</em> em 7 dias` : ""}${ult ? ` · último dia (${diaBR(ult.dia)}): <em class="${cls(ult.lucro)}">${reais(ult.lucro, true)}</em>` : ""}</span></div>
      <div><small>Ritmo ao ano, se continuar igual</small><b class="num ${p?.aoAno != null ? (p.aoAno >= REGUA ? "pos" : "") : ""}">${p?.aoAno != null ? pct(p.aoAno, 0) : "—"}</b>${bala(p?.aoAno ?? null, REGUA, CDI_AO_ANO)}</div>
      <div><small>Próxima ida do Arq</small><b class="num">${prox ? prox.h : "—"}</b><span>${prox ? `para o ${esc(prox.banco)}, em ${prox.falta}` : ""}</span>
        <span class="iv-dias">${HORARIOS.map(([h, b]) => `<i>${h} ${esc(b)}</i>`).join("")}</span></div>
    </section>
    ${tickers()}
    <div class="iv-grade g4 iv-sec">
      ${tile("Lucro em 30 dias", p?.mes != null ? reais(p.mes, true) : "—", p ? `${p.dias.filter(d => d.lucro != null).length} dias registrados` : "", cls(p?.mes))}
      ${tile("Melhor teste do Placar", t[0] ? pct(t[0].retorno) : "—", t[0] ? `${esc(t[0].nome)}, em ${emDias(t[0].desde)}` : "", cls(t[0]?.retorno))}
      ${tile("Testes no positivo", `${t.filter(x => x.retorno > 0).length} de ${t.length}`, `${t.filter(x => x.retorno > cdi(x.desde)).length} batendo o CDI no mesmo período`)}
      ${tile("Ideias que passaram na régua", String((ideiasHoje?.ideias?.length || 0) + ytTestar.length), ideiasHoje ? `WhatsApp de ${diaBR(ideiasHoje.dia)} e vídeos com potencial` : "")}
    </div>
    <div class="iv-grade g-21 iv-sec">
      <section class="iv-card"><h2>Saldo do ping pong</h2><p class="sub">Saldo no fim de cada dia (o que o app registrou).</p>
        ${p ? grafLinha([{ nome: "Saldo", pts: p.dias.map(d => [Date.parse(d.quando || d.dia + "T23:00:00-03:00"), d.saldo]) }], { fmt: (v) => reais(v).replace(",00", ""), fmtDica: (v) => reais(v), area: true, W: 820 }) : "<p class='iv-vazio'>Sem o registro do ping pong.</p>"}</section>
      <section class="iv-card"><h2>Atenção</h2><p class="sub">O que pede um olhar agora.</p>${atencao(falhas, t)}</section>
    </div>
    <section class="iv-card iv-sec"><h2>Placar: cada teste contra o CDI</h2><p class="sub">Dinheiro de mentira, preços de verdade. "Diferença" é quanto o teste ganhou a mais (ou a menos) que a renda fixa no mesmo período. Clique num teste para abrir.</p>
      ${tabelaRanking(t)}</section>
    <section class="iv-sec"><div class="iv-titulo-sec"><h2>As curvas lado a lado</h2><p>Linha cheia: o teste. Tracejada: o CDI.</p></div>${curvasPequenas(t)}</section>`;
  tela.querySelectorAll("[data-ir-teste]").forEach(el => { const ir = () => { testeAberto = el.dataset.irTeste; irPara("placar"); };
    el.onclick = ir; el.onkeydown = (e) => { if (e.key === "Enter") ir(); }; });
}
function atencao(falhas, t) {
  const itens = [];
  if (falhas.length) itens.push(`<li><span class="iv-selo falha">macros</span> ${falhas.length} ${falhas.length === 1 ? "falha" : "falhas"} de macro nos últimos 3 dias. A última: ${esc(falhas[0].macro)} (${dataHora(Date.parse(falhas[0].quando))}).</li>`);
  const neg = t.filter(x => x.retorno < 0);
  if (neg.length) itens.push(`<li><span class="iv-selo">Placar</span> ${neg.map(x => `${esc(x.nome)} (${pct(x.retorno)})`).join(", ")} no negativo.</li>`);
  const u = D.pp?.atualizado ? Date.parse(D.pp.atualizado) : null;
  if (u && Date.now() - u > 2 * 86400000) itens.push(`<li><span class="iv-selo aviso">app</span> O app não manda o registro do ping pong desde ${dataHora(u)}: abra o Nexus para sincronizar.</li>`);
  return itens.length ? `<ul style="margin:0;padding-left:18px;display:grid;gap:10px">${itens.join("")}</ul>` : `<p class="iv-vazio">Nada fora do normal.</p>`;
}

/** Calendário do lucro: um quadrado por dia, azul quando ganhou e vermelho quando perdeu (mais forte = mais). */
function calendario(dias) {
  if (!dias.length) return "";
  const porDia = Object.fromEntries(dias.map((d, i) => [d.dia, { ...d, r: d.lucro != null && dias[i - 1]?.saldo ? d.lucro / dias[i - 1].saldo : null }]));
  const ini = new Date(dias[0].dia + "T12:00:00"); ini.setDate(ini.getDate() - ini.getDay());
  const fim = new Date(); const cel = [];
  for (let d = new Date(ini); d <= fim; d.setDate(d.getDate() + 1)) cel.push(d.toISOString().slice(0, 10));
  const mx = Math.max(0.002, ...Object.values(porDia).map(d => Math.abs(d.r ?? 0)).filter(v => v < 0.01));
  const cor = (r) => r == null ? "" : `--k:${Math.min(1, Math.abs(r) / mx).toFixed(2)}`;
  return `<div class="iv-cal"><div class="sem">${["dom", "seg", "ter", "qua", "qui", "sex", "sáb"].map(x => `<span>${x}</span>`).join("")}</div>
    <div class="grade">${cel.map(c => { const d = porDia[c];
      return `<span class="c ${d?.r == null ? (d ? "s" : "v") : d.r >= 0 ? "p" : "n"}${Math.abs(d?.r ?? 0) > 0.01 ? " x" : ""}" style="${cor(d?.r)}" title="${diaBR(c)}${d ? ` · saldo ${reais(d.saldo)}${d.lucro != null ? ` · ${reais(d.lucro, true)} (${pct(d.r, 3)})` : ""}` : " · sem registro"}">${Number(c.slice(8))}</span>`; }).join("")}</div>
    <p class="iv-nota">Mais forte = dia melhor (ou pior). Contorno pontilhado: mais de 1% num dia, quase sempre dinheiro que entrou ou saiu.</p></div>`;
}
/** O que cada macro fez hoje (desde a meia-noite de Brasília). */
function hojeMacros(eventos) {
  const hoje = new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
  const ev = eventos.filter(e => e.quando.slice(0, 10) === hoje).slice().reverse();
  if (!ev.length) return `<p class="iv-vazio">Nenhuma macro rodou hoje ainda (ou o app ainda não sincronizou).</p>`;
  const runs = []; let atual = null;
  for (const e of ev) {
    if (e.tipo === "inicio" || !atual || atual.macro !== e.macro) { atual = { macro: e.macro, ini: e.quando, fim: null, falhas: 0, eventos: [] }; runs.push(atual); }
    atual.eventos.push(e); if (e.tipo === "fim") atual.fim = e.quando; if (e.tipo === "falha") atual.falhas++;
  }
  return `<ol class="iv-linha-tempo">${runs.slice().reverse().map(r => `<li class="${r.falhas ? "falhou" : r.fim ? "ok" : ""}"><b>${r.ini.slice(11, 16)}</b> ${esc(r.macro)}
    <span class="iv-selo ${r.falhas ? "falha" : r.fim ? "testar" : "aviso"}">${r.falhas ? `${r.falhas} ${r.falhas === 1 ? "falha" : "falhas"}` : r.fim ? `terminou ${r.fim.slice(11, 16)}` : "sem fim registrado"}</span>
    <small>${esc(r.eventos.filter(e => ["envio", "devolucao", "saldo", "saldo_ida", "guardou", "falha"].includes(e.tipo)).map(e => e.texto).slice(0, 3).join(" · "))}</small></li>`).join("")}</ol>`;
}
function projecaoPP(p) {
  if (p.aoMes == null || p.saldo == null) return `<p class="iv-vazio">A projeção aparece com 3 dias de lucro registrados.</p>`;
  const linhas = [[1, "1 mês"], [3, "3 meses"], [6, "6 meses"], [12, "1 ano"]];
  const cdiMes = Math.pow(1 + CDI_AO_ANO, 1 / 12) - 1, regMes = Math.pow(1 + REGUA, 1 / 12) - 1;
  return `<table class="iv-tab"><thead><tr><th>Daqui a</th><th class="n">No ritmo atual</th><th class="n">Na régua (45% a.a.)</th><th class="n">No CDI</th></tr></thead><tbody>
    ${linhas.map(([m, rot]) => `<tr><td>${rot}</td><td class="n"><b>${reais(p.saldo * Math.pow(1 + p.aoMes, m))}</b></td><td class="n">${reais(p.saldo * Math.pow(1 + regMes, m))}</td><td class="n">${reais(p.saldo * Math.pow(1 + cdiMes, m))}</td></tr>`).join("")}
    </tbody></table><p class="iv-nota">Conta simples: o ritmo dos últimos dias repetido, sem colocar nem tirar dinheiro. Ritmo de poucos dias muda muito.</p>`;
}
function rendArq(eventos) {
  const e = eventos.find(x => x.tipo === "rend_arq");
  return e ? `<p class="iv-nota">Arq (lido em ${dataHora(Date.parse(e.quando))}): ${esc(e.texto)}</p>` : "";
}
function telaPingPong() {
  if (!D.quando) { tela.innerHTML = carregando(); return; }
  const p = D.pp;
  if (!p) { tela.innerHTML = `${erros()}<p class="iv-vazio">Sem o registro do ping pong no GitHub ainda.</p>`; return; }
  const ult = p.dias.at(-1);
  const bancos = Object.entries(p.porBanco).filter(([k]) => k).sort((a, b) => b[1].ganho - a[1].ganho);
  const tipos = ["todos", "falha", "envio", "devolucao", "aviso"];
  const ev = p.eventos.filter(e => filtroEventos === "todos" || e.tipo === filtroEventos).slice(0, 80);
  tela.innerHTML = `<div class="iv-titulo"><h1>Ping pong</h1><p>Registro das macros que o app envia ao GitHub${p.atualizado ? `, atualizado em ${dataHora(Date.parse(p.atualizado))}` : ""}.</p></div>${erros()}
    <div class="iv-grade g4">
      ${tile("Saldo", reais(p.saldo), ult ? `fim do dia ${diaBR(ult.dia)}` : "", "", "destaque")}
      ${tile("Lucro em 7 dias", reais(p.semana, true), "", cls(p.semana))}
      ${tile("Lucro em 30 dias", reais(p.mes, true), `${p.dias.filter(d => d.lucro != null).length} dias com lucro registrado`, cls(p.mes))}
      ${tile("Ritmo", p.aoMes != null ? `${pct(p.aoMes)} <small style="display:inline;font-size:14px">ao mês</small>` : "—", p.aoAno != null ? `${pct(p.aoAno, 0)} ao ano, se continuar igual` : "precisa de 3 dias de lucro", cls(p.aoMes))}
    </div>
    <div class="iv-grade g-21 iv-sec">
      <section class="iv-card"><h2>Hoje nas macros</h2><p class="sub">Cada vez que uma macro rodou hoje, do mais recente para o mais antigo.</p>${hojeMacros(p.eventos)}${rendArq(p.eventos)}</section>
      <section class="iv-card"><h2>Calendário</h2><p class="sub">Lucro de cada dia, em % do saldo.</p>${calendario(p.dias)}</section>
    </div>
    <section class="iv-card iv-sec"><h2>Projeção</h2><p class="sub">Para onde o saldo vai se o ritmo continuar, comparado com a régua e o CDI.</p>${projecaoPP(p)}</section>
    <div class="iv-grade g2 iv-sec">
      <section class="iv-card"><h2>Lucro por dia</h2><p class="sub">Saldo do dia menos o do dia anterior, sem contar dinheiro que entrou ou saiu. Um dia acima de 1% quase sempre é dinheiro que entrou ou saiu sem registro no app (marcado "conferir" no dia a dia).</p>
        ${grafBarras(p.dias.filter(d => d.lucro != null).map(d => ({ rot: diaBR(d.dia), v: d.lucro, dica: `${diaBR(d.dia)}: <b>${reais(d.lucro, true)}</b>${d.fluxo ? `<br>entrou/saiu ${reais(d.fluxo, true)}` : ""}` })))}</section>
      <section class="iv-card"><h2>Ganho por banco</h2><p class="sub">Soma do que cada ida e volta rendeu.</p>
        ${bancos.length ? grafBarras(bancos.map(([k, b]) => ({ rot: BANCOS[k] || k, v: b.ganho, dica: `${esc(BANCOS[k] || k)}: <b>${reais(b.ganho, true)}</b><br>${b.ciclos} ciclos` }))) : "<p class='iv-vazio'>Sem ciclos com ganho ainda.</p>"}</section>
    </div>
    <div class="iv-grade g2 iv-sec">
      <section class="iv-card"><h2>Dia a dia</h2><div class="iv-rolar"><table class="iv-tab"><thead><tr><th>Dia</th><th class="n">Saldo</th><th class="n">Lucro</th><th class="n">No dia</th><th>Ciclos</th></tr></thead><tbody>
        ${p.dias.slice().reverse().map((d, i, arr) => { const ant = arr[i + 1]; const r = d.lucro != null && ant?.saldo ? d.lucro / ant.saldo : null;
          const estranho = r != null && Math.abs(r) > 0.01;
          return `<tr><td>${diaBR(d.dia)}${estranho ? ` <span class="iv-selo aviso" title="Mais de 1% num dia: quase sempre é dinheiro que entrou ou saiu sem ser registrado no app">conferir</span>` : ""}</td><td class="n">${reais(d.saldo)}</td><td class="n ${cls(d.lucro)}">${d.lucro != null ? reais(d.lucro, true) : "—"}</td><td class="n ${cls(r)}">${r != null ? pct(r, 3) : "—"}</td>
            <td>${(d.ciclos || []).map(c => esc(BANCOS[c.dest] || c.dest || "?")).join(", ")}${d.fluxo ? `<small>entrou/saiu ${reais(d.fluxo, true)}</small>` : ""}</td></tr>`; }).join("")}
      </tbody></table></div></section>
      <section class="iv-card"><h2>O que as macros fizeram</h2>
        <div class="iv-filtros">${tipos.map(k => `<button data-ev="${k}" aria-pressed="${filtroEventos === k}">${{ todos: "Tudo", falha: "Falhas", envio: "Envios", devolucao: "Devoluções", aviso: "Avisos" }[k]}</button>`).join("")}</div>
        <div class="iv-rolar"><table class="iv-tab"><thead><tr><th>Quando</th><th>Macro</th><th>O que houve</th></tr></thead><tbody>
        ${ev.map(e => `<tr><td style="white-space:nowrap">${dataHora(Date.parse(e.quando))}</td><td>${esc(e.macro)}</td><td>${e.tipo === "falha" ? `<span class="iv-selo falha">falha</span> ` : ""}${esc(e.texto)}</td></tr>`).join("") || `<tr><td colspan="3" class="iv-vazio">Nada desse tipo.</td></tr>`}
        </tbody></table></div></section>
    </div>`;
  tela.querySelectorAll("[data-ev]").forEach(b => b.onclick = () => { filtroEventos = b.dataset.ev; telaPingPong(); });
}

function telaPlacar() {
  if (!D.quando) { tela.innerHTML = carregando(); return; }
  const t = D.placar || [];
  if (!t.length) { tela.innerHTML = `${erros()}<p class="iv-vazio">O Placar não respondeu agora.</p>`; return; }
  const sel = t.find(x => x.id === testeAberto) || t[0]; testeAberto = sel.id;
  const ref = cdi(sel.desde);
  tela.innerHTML = `<div class="iv-titulo"><h1>Placar</h1><p>Cada teste começa com dinheiro de mentira (US$ 1.000, ou R$ nas ideias da bolsa) e segue os preços de verdade. O CDI tracejado é a renda fixa no mesmo período.</p></div>${erros()}
    <div class="iv-grade g-12">
      <div class="iv-testes" role="list">${t.map(x => `<button class="iv-teste" data-t="${x.id}" aria-pressed="${x.id === sel.id}"><span><b>${esc(x.nome)}</b><small>${esc(x.como)}</small><small>${emDias(x.desde)} · desde ${dataCurta(x.desde)}</small></span>${spark(x.curva)}<span class="r ${cls(x.retorno)}">${pct(x.retorno)}</span></button>`).join("")}</div>
      <div>
        <section class="iv-card"><h2>${esc(sel.nome)}</h2><p class="sub">${esc(sel.como)} · desde ${dataCurta(sel.desde)} · o CDI rendeu ${pct(ref)} no mesmo período</p>
          ${grafLinha([{ nome: sel.nome, pts: sel.curva, zero: true }, { nome: "CDI", ref: true, pts: [0, .25, .5, .75, 1].map(k => sel.desde + (Math.max(...sel.curva.map(p => p[0])) - sel.desde) * k).map(tt => [tt, cdi(sel.desde, tt)]) }], { altura: 320, W: 860 })}</section>
        ${INFO[sel.id] ? `<section class="iv-card iv-sec iv-sobre"><h2>Como funciona <span class="iv-selo r${INFO[sel.id].risco}">risco ${RISCO[INFO[sel.id].risco]}</span> <span class="iv-selo">${esc(INFO[sel.id].onde)}</span></h2>
          <p>${esc(INFO[sel.id].oque)}</p>${INFO[sel.id].origem?.video_id ? `<p>Ideia do vídeo <a href="https://www.youtube.com/watch?v=${encodeURIComponent(INFO[sel.id].origem.video_id)}" target="_blank" rel="noopener">${esc(INFO[sel.id].origem.titulo || "no YouTube")}</a> (${esc(INFO[sel.id].origem.canal || "")}${INFO[sel.id].origem.minuto ? `, a partir de ${esc(INFO[sel.id].origem.minuto)}` : ""}): o Gemini assistiu e o Claude transformou neste teste.</p>` : ""}${sel.nota ? `<p class="iv-nota">${esc(sel.nota)}</p>` : ""}<div class="iv-grade g2"><div><small>Ganha</small><p>${esc(INFO[sel.id].ganha)}</p></div><div><small>Perde</small><p>${esc(INFO[sel.id].perde)}</p></div></div>
          <p class="iv-nota">Contra o CDI no mesmo período: <b class="${cls(sel.retorno - ref)}">${pct(sel.retorno - ref).replace("%", " pontos")}</b>. Com ${emDias(sel.desde)} de teste, ainda é cedo para comparar com a régua de 45% ao ano.</p></section>` : ""}
        <div class="iv-grade g4 iv-sec">${sel.numeros.map(([r, v]) => tile(r, `<span class="num">${esc(v)}</span>`, "", v.startsWith("+") ? "pos" : v.startsWith("−") ? "neg" : "")).join("")}</div>
        ${sel.itens.length ? `<section class="iv-card iv-sec"><h2>Por dentro</h2><table class="iv-tab"><thead><tr><th>Item</th><th class="n">Resultado</th></tr></thead><tbody>
          ${sel.itens.map(i => `<tr><td>${esc(i.nome)}${i.sub ? `<small>${esc(i.sub)}</small>` : ""}</td><td class="n ${cls(i.r)}">${pct(i.r)}</td></tr>`).join("")}</tbody></table></section>` : ""}
        ${sel.ops?.length ? `<section class="iv-card iv-sec"><h2>Últimas operações</h2><div class="iv-rolar"><table class="iv-tab"><thead><tr><th>Quando</th><th>O quê</th></tr></thead><tbody>
          ${sel.ops.filter(o => o.t).sort((a, b) => b.t - a.t).slice(0, 25).map(o => `<tr><td style="white-space:nowrap">${dataHora(o.t)}</td><td>${esc(o.titulo)}${o.sub ? `<small>${esc(o.sub)}</small>` : ""}</td></tr>`).join("")}</tbody></table></div></section>` : ""}
      </div>
    </div>`;
  tela.querySelectorAll("[data-t]").forEach(b => b.onclick = () => { testeAberto = b.dataset.t; telaPlacar(); });
}

function telaIdeias() {
  if (!D.quando) { tela.innerHTML = carregando(); return; }
  const dias = D.ideias?.dias || [], yt = D.yt || [];
  const VER = { apresentar: "para você decidir", automatizado: "virou teste", testar: "testar", ja_testamos: "já testamos", info: "informação", descartado: "descartado", nao_vale: "não vale" };
  const grupo = (v) => v.claude?.veredito || (v.potencial ? "esperando" : v.potencial === false ? "sem_potencial" : "esperando");
  const FILTROS = { todos: "Todos", apresentar: "Para você decidir", automatizado: "Viraram teste", esperando: "Esperando o Claude", descartados: "Descartados" };
  const ys = yt.filter(v => filtroYT === "todos" ? v.potencial !== false || v.claude : filtroYT === "descartados" ? ["descartado", "nao_vale", "sem_potencial"].includes(grupo(v)) : filtroYT === "apresentar" ? ["apresentar", "testar"].includes(grupo(v)) : grupo(v) === filtroYT);
  const R = D.ytResumo, k = R?.contagem || {};
  tela.innerHTML = `<div class="iv-titulo"><h1>Ideias</h1><p>O que o buscador achou nos grupos de finanças do WhatsApp e nos vídeos do YouTube, pela régua de 45 % ao ano ou mais.</p></div>${erros()}
    <div class="iv-grade g2">
      <section class="iv-card"><h2>WhatsApp</h2><p class="sub">Leitura das 5h${D.ideias?.atualizado ? `, atualizada em ${dataHora(Date.parse(D.ideias.atualizado))}` : ""}.</p>
        ${dias.length ? dias.map(d => `<div class="iv-ideia"><h3>${diaBR(d.dia)} <small>${(d.mensagens || 0).toLocaleString("pt-BR")} mensagens lidas</small></h3>
          ${d.ideias?.length ? d.ideias.map(i => `<div class="iv-ideia"><h3>${esc(i.titulo)} <span class="iv-selo ${/golpe/i.test(i.rende) ? "golpe" : /aviso/i.test(i.rende) ? "aviso" : "testar"}">${esc(i.rende)}</span>${i.risco ? `<span class="iv-selo">risco ${["", "baixo", "médio", "alto", "muito alto"][i.risco] || i.risco}</span>` : ""}</h3>
            <p>${esc(i.resumo)}</p>${i.acao ? `<p><b>O que fazer:</b> ${esc(i.acao)}</p>` : ""}<small>${esc(i.grupo)}</small></div>`).join("") : `<p class="iv-nota">${esc(d.nada || "Nada novo.")}</p>`}</div>`).join("") : "<p class='iv-vazio'>Nenhuma leitura ainda.</p>"}</section>
      <section class="iv-card"><h2>YouTube</h2><p class="sub">Todo dia à 01h o Gemini assiste os vídeos novos dos canais e, com o que sobra do limite, os antigos. Às 5h o Claude confere os que têm potencial: descarta, vira teste no Placar ou vai para você decidir.${R ? ` ${(k.assistidos || 0).toLocaleString("pt-BR")} assistidos, ${(k.com_potencial || 0).toLocaleString("pt-BR")} com potencial, ${(R.na_fila || 0).toLocaleString("pt-BR")} na fila.` : ""}</p>
        <div class="iv-filtros">${Object.keys(FILTROS).map(f => `<button data-yt="${f}" aria-pressed="${filtroYT === f}">${FILTROS[f]}</button>`).join("")}</div>
        ${ys.length ? ys.map(v => `<div class="iv-ideia"><h3>${v.id ? `<a href="https://www.youtube.com/watch?v=${encodeURIComponent(v.id)}" target="_blank" rel="noopener" style="color:inherit">${esc(v.titulo)}</a>` : esc(v.titulo)}
          ${v.claude ? `<span class="iv-selo ${["apresentar", "automatizado"].includes(v.claude.veredito) ? "testar" : v.claude.veredito === "descartado" ? "nao_vale" : v.claude.veredito}">${esc(VER[v.claude.veredito] || v.claude.veredito)}</span>` : v.potencial === false ? `<span class="iv-selo">sem potencial</span>` : `<span class="iv-selo">esperando o Claude</span>`}${v.tipo === "novo" ? ` <span class="iv-selo">vídeo novo</span>` : ""}</h3>
          <small>${esc(v.canal || "")}${v.claude?.rende ? ` · ${esc(v.claude.rende)}` : ""}</small>
          <p>${esc(v.claude?.frase || v.por_que || "")}</p>${v.claude?.acao ? `<p><b>O que dá para fazer:</b> ${esc(v.claude.acao)}</p>` : ""}</div>`).join("") : "<p class='iv-vazio'>Nenhum vídeo nesse filtro.</p>"}</section>
    </div>`;
  tela.querySelectorAll("[data-yt]").forEach(b => b.onclick = () => { filtroYT = b.dataset.yt; telaIdeias(); });
}

const TELAS = { geral: telaGeral, pingpong: telaPingPong, placar: telaPlacar, ideias: telaIdeias };
function irPara(aba) {
  if (!TELAS[aba]) aba = "geral";
  tela.dataset.tela = aba;
  abas.querySelectorAll("button").forEach(b => b.setAttribute("aria-current", b.dataset.aba === aba ? "page" : "false"));
  if (location.hash.slice(1) !== aba) history.replaceState(null, "", `#${aba}`);
  TELAS[aba]();
}
function desenharAcoes() {
  acoes.innerHTML = `<small>${D.carregando ? "atualizando…" : D.quando ? `atualizado às ${new Date(D.quando).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}` : ""}</small>
    <button class="iv-bt" id="iv-atualizar" ${D.carregando ? "disabled" : ""}>Atualizar</button><a class="iv-bt" href="./">Máquina</a><button class="iv-bt" id="iv-sair">Sair</button>`;
  $("#iv-atualizar").onclick = carregar;
  $("#iv-sair").onclick = () => { esquecer(); location.hash = ""; location.reload(); };
}

function pedirToken(erro = "") {
  abas.hidden = true; acoes.innerHTML = "";
  const { repo = "Kimijoao77/Engfy" } = configPC();
  tela.innerHTML = `<section class="iv-entrar"><h1>Entrar</h1>
    <p>Cole o mesmo tipo de token do GitHub que o app usa (Perfil → Sincronização). Ele fica só neste navegador e aqui serve só para ler.</p>
    <label>Repositório<input id="iv-repo" value="${esc(repo)}" autocomplete="off" spellcheck="false"></label>
    <label>Token do GitHub<input id="iv-token" type="password" autocomplete="off" spellcheck="false" placeholder="github_pat_..."></label>
    ${erro ? `<p class="iv-erro">${esc(erro)}</p>` : ""}<button class="iv-bt forte" id="iv-ok">Entrar</button>
    <p class="iv-nota">Num computador que não é seu, toque em Sair quando terminar: o token é apagado deste navegador.</p></section>`;
  const ok = async () => {
    const r = $("#iv-repo").value.trim(), tk = $("#iv-token").value.trim();
    const aviso = (t) => { let e = $(".iv-erro", tela); if (!e) { e = document.createElement("p"); e.className = "iv-erro"; $("#iv-ok").before(e); } e.textContent = t; };
    if (!tk) return aviso("O campo do token está vazio: cole o código github_pat_... (Ctrl+V) e toque em Entrar.");
    if (!/^[\w.-]+\/[\w.-]+$/.test(r)) return aviso("O repositório tem que ser dono/nome, por exemplo Kimijoao77/Engfy.");
    try { const resp = await fetch(`https://api.github.com/repos/${r}`, { headers: { Authorization: `Bearer ${tk}`, Accept: "application/vnd.github+json" } });
      if (!resp.ok) return aviso(resp.status === 404 ? "Repositório não encontrado com este token: confira se o token tem acesso ao Kimijoao77/Engfy." : "O GitHub recusou este token: confira se copiou ele inteiro."); }
    catch { return aviso("Sem internet agora."); }
    salvarConfig(r, tk); iniciar();
  };
  $("#iv-ok").onclick = ok; $("#iv-token").onkeydown = (e) => { if (e.key === "Enter") ok(); };
}
function iniciar() {
  if (!temToken()) return pedirToken();
  abas.hidden = false;
  abas.innerHTML = ABAS.map(([k, n]) => `<button data-aba="${k}">${n}</button>`).join("");
  abas.querySelectorAll("button").forEach(b => b.onclick = () => irPara(b.dataset.aba));
  desenharAcoes(); irPara(location.hash.slice(1)); carregar();
  setInterval(() => { if (!document.hidden) carregar(); }, 10 * 60 * 1000);
}
window.addEventListener("hashchange", () => { if (temToken() && tela.dataset.tela !== location.hash.slice(1)) irPara(location.hash.slice(1)); });
iniciar();
