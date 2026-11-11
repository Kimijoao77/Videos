// Investimentos no computador (11/11/2026): os mesmos dados que o app Nexus usa, num painel largo.
// - Placar (testes de mentira, preços de verdade): radar-hyperliquid/saida/*.json, público, sem token.
// - Ping pong (o seu dinheiro): progresso/macros.json do repositório privado, que o app envia a cada sincronização.
// - Ideias (WhatsApp e YouTube): ideias/ do repositório privado, gravadas pelas tarefas das 5h.
// O token fica só neste navegador (o mesmo da Máquina no computador). Nada daqui grava no repositório.
import { temToken, salvarConfig, esquecer, configPC, baixarTexto, listar } from "./js/dados.js";

const BASE = window.PLACAR_BASE || "https://raw.githubusercontent.com/Kimijoao77/radar-hyperliquid/main/saida/";
const ARQS = ["copia_fiel", "grade", "cofres", "concentradas", "apostas", "listagens"];
const CDI_AO_ANO = 0.1365;            // Selic 13,75 % (Copom de 04/11/2026) menos 0,10: o mesmo do app
const ABAS = [["geral", "Visão geral"], ["pingpong", "Ping pong"], ["placar", "Placar"], ["ideias", "Ideias"]];
const BANCOS = { mp: "Mercado Pago", astro: "AstroPay", "99": "99Pay", "": "sem destino" };

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
const D = { placar: null, pp: null, ideias: null, yt: null, quando: null, erros: [], carregando: false };
let testeAberto = null, filtroYT = "todos", filtroEventos = "todos";

// ---------- gráficos (SVG à mão, com dica ao passar o mouse) ----------
let nGraf = 0;
/** Linha no tempo. series: [{nome, pts: [[ms, y]], ref?}] (a 1ª é a principal). fmt: formata o valor do eixo y. */
function grafLinha(series, { fmt = (v) => pct(v, 1), altura = 260, area = false, fmtDica, W = 800 } = {}) {
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
    ${xt.map(t => `<text x="${X(t).toFixed(1)}" y="${H - 8}" text-anchor="middle">${rotX(t)}</text>`).join("")}
    ${areaD ? `<path class="area" d="${areaD}"/>` : ""}
    ${series.slice().reverse().map(s => `<path class="linha${s.ref ? " ref" : ""}" d="${caminho(s.pts)}"/>`).join("")}
    ${u ? `<circle class="pto" cx="${X(u[0]).toFixed(1)}" cy="${Y(u[1]).toFixed(1)}" r="4.5"/>` : ""}
    <line class="mira" id="${id}-m" x1="0" x2="0" y1="${PT}" y2="${H - PB}" visibility="hidden"/>
    <rect id="${id}-h" x="${PL}" y="${PT}" width="${W - PL - PR}" height="${H - PT - PB}" fill="transparent"/>
  </svg>`;
  setTimeout(() => ligarDica(id, { W, X, x0, x1, PL, PR, series, fmtDica: fmtDica || fmt }), 0);
  const leg = series.length > 1 ? `<div class="iv-legenda">${series.map(s => `<span><i class="${s.ref ? "ref" : ""}"></i>${esc(s.nome)}</span>`).join("")}</div>` : "";
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
      itens: subs.map(x => ({ nome: x.apelido || `${x.w.slice(0, 6)}…${x.w.slice(-4)}`, r: x.retorno, sub: x.parou ? `parou: ${x.parou}` : `${(x.ordens || 0).toLocaleString("pt-BR")} ordens` })).sort((a, b) => b.r - a.r) });
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
        itens: gv.map(x => ({ nome: `${x.moeda} · ${x.nome}`, r: x.resultado.final / cap - 1, sub: `só segurar ${x.moeda}: ${pct(x.resultado.segurar_moeda || 0)} · ${x.resultado.ciclos || 0} ciclos` })).sort((a, b) => b.r - a.r) });
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
      itens: fs.flatMap(f => (f.abertas || []).map(a => ({ nome: a.nome, r: a.r, sub: `${f.nome} · ${a.dentro ? "dentro da faixa" : "fora da faixa"} · taxas ${pct(a.taxas)}` }))).sort((a, b) => b.r - a.r) });
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
  const yt = listar("ideias/youtube/videos").then(async (fs) => {
    const js = fs.filter(f => f.nome.endsWith(".json")).slice(-40);
    D.yt = (await Promise.all(js.map(f => json(f.caminho).catch(() => null)))).filter(Boolean).sort((a, b) => String(b.visto_em || "").localeCompare(String(a.visto_em || "")));
  }).catch(e => D.erros.push(`Ideias do YouTube: ${e.message}`));
  await Promise.all([placar, pp, ideias, yt]);
  D.quando = Date.now(); D.carregando = false;
  desenharAcoes(); irPara(tela.dataset.tela || location.hash.slice(1));
}

// ---------- telas ----------
const tile = (rot, valor, sub = "", classe = "", extra = "") => `<div class="iv-card iv-tile ${extra}"><small>${esc(rot)}</small><b class="${classe}">${valor}</b>${sub ? `<span>${sub}</span>` : ""}</div>`;
const erros = () => D.erros.length ? `<p class="iv-erro">${D.erros.map(esc).join("<br>")}</p>` : "";
const carregando = () => `<p class="iv-vazio">Carregando os dados do GitHub…</p>`;

function telaGeral() {
  if (!D.quando) { tela.innerHTML = carregando(); return; }
  const p = D.pp, t = D.placar || [], melhor = t[0];
  const ideiasHoje = D.ideias?.dias?.[0], ytTestar = (D.yt || []).filter(v => v.claude?.veredito === "testar");
  const falhas = (p?.eventos || []).filter(e => e.tipo === "falha" && Date.now() - Date.parse(e.quando) < 3 * 86400000);
  tela.innerHTML = `<div class="iv-titulo"><h1>Visão geral</h1><p>O seu dinheiro (ping pong) e os testes no papel, com os mesmos dados do app.</p></div>${erros()}
    <div class="iv-grade g4">
      ${tile("Saldo do ping pong", p?.saldo != null ? `<span class="num">${reais(p.saldo)}</span>` : "—", p?.quando ? `último ciclo em ${dataHora(Date.parse(p.quando))}` : "", "", "destaque")}
      ${tile("Lucro em 7 dias", p?.semana != null ? reais(p.semana, true) : "—", p?.aoMes != null ? `ritmo de ${pct(p.aoMes)} ao mês` : "", cls(p?.semana))}
      ${tile("Melhor teste do Placar", melhor ? pct(melhor.retorno) : "—", melhor ? `${esc(melhor.nome)}, em ${emDias(melhor.desde)}` : "", cls(melhor?.retorno))}
      ${tile("Ideias que passaram na régua", String((ideiasHoje?.ideias?.length || 0) + ytTestar.length), ideiasHoje ? `WhatsApp de ${diaBR(ideiasHoje.dia)} e vídeos para testar` : "")}
    </div>
    <div class="iv-grade g-21 iv-sec">
      <section class="iv-card"><h2>Saldo do ping pong</h2><p class="sub">Saldo no fim de cada dia (o que o app registrou).</p>
        ${p ? grafLinha([{ nome: "Saldo", pts: p.dias.map(d => [Date.parse(d.quando || d.dia + "T23:00:00-03:00"), d.saldo]) }], { fmt: (v) => reais(v).replace(",00", ""), fmtDica: (v) => reais(v), area: true, W: 820 }) : "<p class='iv-vazio'>Sem o registro do ping pong.</p>"}</section>
      <section class="iv-card"><h2>Atenção</h2><p class="sub">O que pede um olhar agora.</p>${atencao(falhas, t)}</section>
    </div>
    <section class="iv-card iv-sec"><h2>Placar: resultado de cada teste</h2><p class="sub">Dinheiro de mentira, preços de verdade. A maioria começou há poucos dias: ainda não prova nada.</p>
      ${grafRanking(t.map(x => ({ rot: x.nome, v: x.retorno, dias: diasDesde(x.desde) })))}</section>`;
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
  tela.innerHTML = `<div class="iv-titulo"><h1>Placar</h1><p>Cada teste começa com US$ 1.000 de mentira e segue os preços de verdade. O CDI tracejado é a renda fixa no mesmo período.</p></div>${erros()}
    <div class="iv-grade g-12">
      <div class="iv-testes" role="list">${t.map(x => `<button class="iv-teste" data-t="${x.id}" aria-pressed="${x.id === sel.id}"><span><b>${esc(x.nome)}</b><small>${esc(x.como)}</small><small>${emDias(x.desde)} · desde ${dataCurta(x.desde)}</small></span>${spark(x.curva)}<span class="r ${cls(x.retorno)}">${pct(x.retorno)}</span></button>`).join("")}</div>
      <div>
        <section class="iv-card"><h2>${esc(sel.nome)}</h2><p class="sub">${esc(sel.como)} · desde ${dataCurta(sel.desde)} · o CDI rendeu ${pct(ref)} no mesmo período</p>
          ${grafLinha([{ nome: sel.nome, pts: sel.curva, zero: true }, { nome: "CDI", ref: true, pts: [0, .25, .5, .75, 1].map(k => sel.desde + (Math.max(...sel.curva.map(p => p[0])) - sel.desde) * k).map(tt => [tt, cdi(sel.desde, tt)]) }], { altura: 320, W: 860 })}</section>
        <div class="iv-grade g4 iv-sec">${sel.numeros.map(([r, v]) => tile(r, `<span class="num">${esc(v)}</span>`, "", v.startsWith("+") ? "pos" : v.startsWith("−") ? "neg" : "")).join("")}</div>
        ${sel.itens.length ? `<section class="iv-card iv-sec"><h2>Por dentro</h2><table class="iv-tab"><thead><tr><th>Item</th><th class="n">Resultado</th></tr></thead><tbody>
          ${sel.itens.map(i => `<tr><td>${esc(i.nome)}${i.sub ? `<small>${esc(i.sub)}</small>` : ""}</td><td class="n ${cls(i.r)}">${pct(i.r)}</td></tr>`).join("")}</tbody></table></section>` : ""}
      </div>
    </div>`;
  tela.querySelectorAll("[data-t]").forEach(b => b.onclick = () => { testeAberto = b.dataset.t; telaPlacar(); });
}

function telaIdeias() {
  if (!D.quando) { tela.innerHTML = carregando(); return; }
  const dias = D.ideias?.dias || [], yt = D.yt || [];
  const VER = { testar: "testar", ja_testamos: "já testamos", info: "informação", nao_vale: "não vale" };
  const ys = yt.filter(v => filtroYT === "todos" || (filtroYT === "sem" ? !v.claude : v.claude?.veredito === filtroYT));
  tela.innerHTML = `<div class="iv-titulo"><h1>Ideias</h1><p>O que o buscador achou nos grupos de finanças do WhatsApp e nos vídeos do YouTube, pela régua de 45 % ao ano ou mais.</p></div>${erros()}
    <div class="iv-grade g2">
      <section class="iv-card"><h2>WhatsApp</h2><p class="sub">Leitura das 5h${D.ideias?.atualizado ? `, atualizada em ${dataHora(Date.parse(D.ideias.atualizado))}` : ""}.</p>
        ${dias.length ? dias.map(d => `<div class="iv-ideia"><h3>${diaBR(d.dia)} <small>${(d.mensagens || 0).toLocaleString("pt-BR")} mensagens lidas</small></h3>
          ${d.ideias?.length ? d.ideias.map(i => `<div class="iv-ideia"><h3>${esc(i.titulo)} <span class="iv-selo ${/golpe/i.test(i.rende) ? "golpe" : /aviso/i.test(i.rende) ? "aviso" : "testar"}">${esc(i.rende)}</span>${i.risco ? `<span class="iv-selo">risco ${["", "baixo", "médio", "alto", "muito alto"][i.risco] || i.risco}</span>` : ""}</h3>
            <p>${esc(i.resumo)}</p>${i.acao ? `<p><b>O que fazer:</b> ${esc(i.acao)}</p>` : ""}<small>${esc(i.grupo)}</small></div>`).join("") : `<p class="iv-nota">${esc(d.nada || "Nada novo.")}</p>`}</div>`).join("") : "<p class='iv-vazio'>Nenhuma leitura ainda.</p>"}</section>
      <section class="iv-card"><h2>YouTube</h2><p class="sub">Os vídeos que o Gemini separou e o veredito do Claude.</p>
        <div class="iv-filtros">${["todos", "testar", "ja_testamos", "info", "nao_vale", "sem"].map(k => `<button data-yt="${k}" aria-pressed="${filtroYT === k}">${{ todos: "Todos", sem: "Sem veredito", ...VER }[k]}</button>`).join("")}</div>
        ${ys.length ? ys.map(v => `<div class="iv-ideia"><h3>${v.id ? `<a href="https://www.youtube.com/watch?v=${encodeURIComponent(v.id)}" target="_blank" rel="noopener" style="color:inherit">${esc(v.titulo)}</a>` : esc(v.titulo)}
          ${v.claude ? `<span class="iv-selo ${v.claude.veredito}">${esc(VER[v.claude.veredito] || v.claude.veredito)}</span>` : `<span class="iv-selo">sem veredito</span>`}</h3>
          <small>${esc(v.canal || "")}${v.claude?.rende ? ` · ${esc(v.claude.rende)}` : ""}</small>
          <p>${esc(v.claude?.frase || v.gemini?.resumo || v.motivo || "")}</p></div>`).join("") : "<p class='iv-vazio'>Nenhum vídeo nesse filtro.</p>"}</section>
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
    if (!/^[\w.-]+\/[\w.-]+$/.test(r) || !tk) return pedirToken("Preencha o repositório (dono/nome) e o token.");
    try { const resp = await fetch(`https://api.github.com/repos/${r}`, { headers: { Authorization: `Bearer ${tk}`, Accept: "application/vnd.github+json" } });
      if (!resp.ok) return pedirToken(resp.status === 404 ? "Repositório não encontrado com este token." : "O GitHub recusou este token."); }
    catch { return pedirToken("Sem internet agora."); }
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
