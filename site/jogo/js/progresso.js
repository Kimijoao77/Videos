// O que fica guardado no aparelho: troféus, ouro, experiência e nível do rei, o nível e as cópias de cada carta, os
// baús ganhos, a loja do dia, a trilha de troféus, estatísticas, o baralho, o nível do computador e o tutorial.
// Tudo no armazenamento do navegador; se ele não funcionar, o jogo segue com os valores padrão.
import { BARALHO, CARTAS, NIVEL_MAX, RARIDADES, TODAS, baralhoValido } from "./sim.js";

const CHAVE = "arena-progresso";
const PADRAO = {
  trofeus: 0, partidas: 0, vitorias: 0, derrotas: 0, empates: 0, sequencia: 0, melhorSeq: 0, coroas: 0, baralho: BARALHO.slice(), nivel: 1,
  tutorial: false, arena: null, ouro: 300, xp: 0, cartas: {}, baus: [null, null, null, null], cicloBau: 0, loja: null, presente: "", trilha: [],
  ouroGanho: 0, bausAbertos: 0,
};
let dados = { ...PADRAO };
try { dados = { ...PADRAO, ...JSON.parse(localStorage.getItem(CHAVE) || "{}") }; } catch (e) { /* sem armazenamento */ }
dados.baralho = baralhoValido(dados.baralho);
for (const k of TODAS) if (!dados.cartas[k]) dados.cartas[k] = { n: 1, c: 0 };
if (!Array.isArray(dados.baus) || dados.baus.length !== 4) dados.baus = [null, null, null, null];

function salvar() { try { localStorage.setItem(CHAVE, JSON.stringify(dados)); } catch (e) { /* ok */ } }
export const prog = () => dados;
export function mudar(campos) { Object.assign(dados, campos); salvar(); }

// ------------------------------------------------------------------ arenas por troféus
export const ARENAS = [
  { min: 0, nome: "Campo de Treino" }, { min: 200, nome: "Vila dos Camponeses" }, { min: 500, nome: "Floresta Sombria" },
  { min: 900, nome: "Castelo de Pedra" }, { min: 1400, nome: "Reino dos Dragões" }, { min: 2000, nome: "Lenda dos Reinos" },
];
export function arenaDe(t) { let a = ARENAS[0]; for (const x of ARENAS) if (t >= x.min) a = x; return a; }
export function proximaArena(t) { return ARENAS.find(x => x.min > t) || null; }

// ------------------------------------------------------------------ nível do rei (experiência ganha melhorando cartas e vencendo)
const XP_REI = [0, 20, 70, 150, 300, 550, 900, 1400, 2100, 3000];
const XP_MELHORIA = [4, 10, 25, 50, 100, 200, 400, 600, 800];
export function nivelRei(xp = dados.xp) { let n = 1; for (let i = 1; i < XP_REI.length; i++) if (xp >= XP_REI[i]) n = i + 1; return n; }
export function faixaXp(xp = dados.xp) {
  const n = nivelRei(xp);
  if (n >= XP_REI.length) return { n, de: 1, ate: 1, max: true };
  return { n, de: xp - XP_REI[n - 1], ate: XP_REI[n] - XP_REI[n - 1], max: false };
}

// ------------------------------------------------------------------ cartas: nível, cópias e melhorar
export const carta = (k) => dados.cartas[k] || { n: 1, c: 0 };
export function proximoNivel(k) {
  const { n } = carta(k), r = RARIDADES[CARTAS[k].raridade];
  if (n >= NIVEL_MAX) return null;
  return { copias: r.copias[n - 1], ouro: r.ouro[n - 1], xp: XP_MELHORIA[n - 1] };
}
export function podeMelhorar(k) { const p = proximoNivel(k); return !!p && carta(k).c >= p.copias && dados.ouro >= p.ouro; }
export function quaseMelhorar(k) { const p = proximoNivel(k); return !!p && carta(k).c >= p.copias; }
export function melhorar(k) {
  if (!podeMelhorar(k)) return null;
  const p = proximoNivel(k), c = dados.cartas[k], reiAntes = nivelRei();
  c.c -= p.copias; c.n++; dados.ouro -= p.ouro; dados.xp += p.xp;
  salvar();
  return { nivel: c.n, xp: p.xp, subiuRei: nivelRei() > reiAntes ? nivelRei() : 0 };
}
export const niveisDoBaralho = (b = dados.baralho) => Object.fromEntries(b.map(k => [k, carta(k).n]));
export const mediaNivel = (b = dados.baralho) => b.reduce((t, k) => t + carta(k).n, 0) / b.length;

// ------------------------------------------------------------------ baús: um abre por vez, cada tipo demora um tanto
export const BAUS = {
  madeira: { nome: "Baú de Madeira", seg: 15, ouro: [18, 36], cartas: 6, raro: 0.12, epico: 0 },
  prata: { nome: "Baú de Prata", seg: 60, ouro: [45, 80], cartas: 14, raro: 0.18, epico: 0.012 },
  ouro: { nome: "Baú de Ouro", seg: 180, ouro: [150, 240], cartas: 36, raro: 0.2, epico: 0.03, garanteRaro: 2 },
  magico: { nome: "Baú Mágico", seg: 480, ouro: [420, 600], cartas: 80, raro: 0.22, epico: 0.06, garanteRaro: 6, garanteEpico: 1 },
};
const CICLO = ["prata", "madeira", "prata", "ouro", "madeira", "prata", "prata", "madeira", "ouro", "prata", "madeira", "magico"];
export const agora = () => Date.now();
export function estadoBau(i) {
  const b = dados.baus[i];
  if (!b) return { vazio: true };
  if (b.ate == null) return { b, parado: true };
  const falta = Math.max(0, b.ate - agora());
  return { b, falta, pronto: falta <= 0, abrindo: falta > 0 };
}
export const alguemAbrindo = () => dados.baus.some((b, i) => b && b.ate != null && estadoBau(i).abrindo);
export function ganharBau(tipo = null) {
  const i = dados.baus.findIndex(b => !b);
  if (i < 0) return null;
  const t = tipo || CICLO[dados.cicloBau++ % CICLO.length];
  dados.baus[i] = { tipo: t, ate: null, arena: arenaDe(dados.trofeus).nome };
  salvar();
  return { i, tipo: t };
}
export function comecarAbrir(i) {
  const b = dados.baus[i];
  if (!b || b.ate != null || alguemAbrindo()) return false;
  b.ate = agora() + BAUS[b.tipo].seg * 1000;
  salvar();
  return true;
}
// sorteia o que vem num baú (ouro e cartas) e já guarda
export function conteudo(tipo, rnd = Math.random) {
  const B = BAUS[tipo];
  const ouro = Math.round(B.ouro[0] + rnd() * (B.ouro[1] - B.ouro[0]));
  const porRar = { comum: [], raro: [], epico: [] };
  for (const k of TODAS) porRar[CARTAS[k].raridade].push(k);
  const conta = {};
  let resta = B.cartas, ep = B.garanteEpico || 0, ra = B.garanteRaro || 0;
  for (let k = 0; k < B.cartas; k++) if (rnd() < B.epico) ep++; else if (rnd() < B.raro) ra++;
  ep = Math.min(ep, resta); resta -= ep; ra = Math.min(ra, resta); resta -= ra;
  const espalhar = (lista, n, grupos) => {
    if (!n) return;
    const esc = lista.slice().sort(() => rnd() - 0.5).slice(0, Math.max(1, Math.min(grupos, n)));
    esc.forEach((k, j) => { const q = Math.floor(n / esc.length) + (j < n % esc.length ? 1 : 0); if (q) conta[k] = (conta[k] || 0) + q; });
  };
  espalhar(porRar.comum, resta, tipo === "madeira" ? 2 : tipo === "prata" ? 3 : 4);
  espalhar(porRar.raro, ra, tipo === "magico" ? 3 : 2);
  espalhar(porRar.epico, ep, 1 + (ep > 2 ? 1 : 0));
  const ordem = { comum: 0, raro: 1, epico: 2 };
  const cartas = Object.entries(conta).map(([k, n]) => ({ k, n })).sort((a, b) => ordem[CARTAS[a.k].raridade] - ordem[CARTAS[b.k].raridade]);
  return { tipo, ouro, cartas };
}
export function receber(premio) {
  dados.ouro += premio.ouro || 0;
  dados.ouroGanho += premio.ouro || 0;
  for (const { k, n } of premio.cartas || []) dados.cartas[k].c += n;
  salvar();
}
export function abrirBau(i) {
  const e = estadoBau(i);
  if (!e.b || !e.pronto) return null;
  const premio = conteudo(e.b.tipo);
  dados.baus[i] = null; dados.bausAbertos++;
  receber(premio);
  return premio;
}

// ------------------------------------------------------------------ loja do dia (muda à meia-noite)
const hoje = () => { const d = new Date(); return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`; };
export const PRECO_BAU = { prata: 120, ouro: 400, magico: 1200 };
const PRECO = { comum: [10, 60], raro: [3, 150], epico: [1, 400] };        // [quantas, ouro]
export function lojaDoDia() {
  if (!dados.loja || dados.loja.dia !== hoje()) {
    let sem = [...hoje()].reduce((t, c) => t * 31 + c.charCodeAt(0) | 0, 7);
    const rnd = () => { sem = (sem * 1103515245 + 12345) | 0; return ((sem >>> 8) & 0xffff) / 65536; };
    const pega = (r) => { const l = TODAS.filter(k => CARTAS[k].raridade === r); return l[Math.floor(rnd() * l.length)]; };
    const ofertas = ["comum", "raro", "epico"].map(r => { const k = pega(r); return { k, n: PRECO[r][0], preco: PRECO[r][1], comprada: false }; });
    dados.loja = { dia: hoje(), ofertas };
    salvar();
  }
  return dados.loja;
}
export function comprarOferta(j) {
  const o = lojaDoDia().ofertas[j];
  if (!o || o.comprada || dados.ouro < o.preco) return false;
  dados.ouro -= o.preco; o.comprada = true; dados.cartas[o.k].c += o.n;
  salvar();
  return true;
}
export function comprarBau(tipo) {
  if (dados.ouro < PRECO_BAU[tipo]) return null;
  dados.ouro -= PRECO_BAU[tipo];
  const premio = conteudo(tipo);
  receber(premio);
  dados.bausAbertos++;
  return premio;
}
export const presenteDisponivel = () => dados.presente !== hoje();
export function pegarPresente() {
  if (!presenteDisponivel()) return null;
  dados.presente = hoje();
  const premio = { tipo: "presente", ouro: 60, cartas: [{ k: TODAS.filter(k => CARTAS[k].raridade === "comum")[Math.floor(Math.random() * 6)], n: 6 }] };
  receber(premio);
  return premio;
}

// ------------------------------------------------------------------ trilha de troféus (prêmios por chegar a tantos troféus)
export const TRILHA = [
  { t: 30, ouro: 100 }, { t: 80, bau: "prata" }, { t: 150, ouro: 200 }, { t: 200, bau: "ouro" }, { t: 300, ouro: 300 },
  { t: 400, bau: "prata" }, { t: 500, bau: "ouro" }, { t: 650, ouro: 500 }, { t: 800, bau: "ouro" }, { t: 900, bau: "magico" },
  { t: 1100, ouro: 800 }, { t: 1250, bau: "ouro" }, { t: 1400, bau: "magico" }, { t: 1700, ouro: 1500 }, { t: 2000, bau: "magico" },
];
export const trilhaPronta = (j) => dados.trofeus >= TRILHA[j].t && !dados.trilha.includes(j);
export const temTrilhaPronta = () => TRILHA.some((_, j) => trilhaPronta(j));
export function resgatarTrilha(j) {
  if (!trilhaPronta(j)) return null;
  const r = TRILHA[j];
  dados.trilha.push(j);
  const premio = r.bau ? conteudo(r.bau) : { tipo: "ouro", ouro: r.ouro, cartas: [] };
  receber(premio);
  return premio;
}

// ------------------------------------------------------------------ fim de partida
// resultado: "v" | "d" | "e". tipo: "bot0" | "bot1" | "bot2" | "online". Devolve troféus, ouro, experiência e o baú ganho.
export function registrar(resultado, tipo, minhasCoroas) {
  const ganho = { bot0: [10, -8, 6], bot1: [25, -15, 12], bot2: [40, -20, 20], online: [30, -20, 15] }[tipo] || [25, -15, 12];
  let delta = 0, ouro = 0, xp = 0, bau = null;
  const reiAntes = nivelRei();
  dados.partidas++; dados.coroas += minhasCoroas;
  if (resultado === "v") {
    dados.vitorias++; dados.sequencia++; dados.melhorSeq = Math.max(dados.melhorSeq, dados.sequencia);
    delta = ganho[0] + Math.min(10, (dados.sequencia - 1) * 2);
    ouro = ganho[2] + 2 * minhasCoroas; xp = 8;
    bau = ganharBau();
  } else if (resultado === "d") { dados.derrotas++; dados.sequencia = 0; delta = Math.max(-dados.trofeus, ganho[1]); ouro = minhasCoroas * 2; xp = 2; }
  else { dados.empates++; ouro = 4; xp = 4; }
  dados.trofeus += delta; dados.ouro += ouro; dados.ouroGanho += ouro; dados.xp += xp;
  salvar();
  return { delta, ouro, xp, bau, subiuRei: nivelRei() > reiAntes ? nivelRei() : 0 };
}
