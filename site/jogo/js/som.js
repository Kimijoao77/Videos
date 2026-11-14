// Sons do jogo. Desde a versão com a trilha sonora: a música é gravada (musica/*.ogg, composta em ferramentas/trilha.py)
// e vários efeitos vêm de gravações livres (sons/*.ogg, pacote da Kenney, CC0); o resto continua feito na hora com a
// Web Audio. Se um arquivo não carregar, toca a versão feita na hora.
let ctx = null, mudo = false, ultimo = {};
const base = new URL("../", import.meta.url).href;            // a pasta do jogo (funciona no site e dentro do app)
const AMOSTRAS = {
  carta: ["carta1", "carta2", "carta3"], escolher: ["escolher1", "escolher2"], clique: ["clique1", "clique2"], moeda: ["moeda1", "moeda2"],
  bau: ["bau1"], golpe: ["golpe1", "golpe2", "golpe3"], lamina: ["lamina1"], metal: ["metal1", "metal2"], conquista: ["conquista1", "conquista2"], pagina: ["pagina1"],
};
const FAIXAS = { menu: "menu", batalha: "batalha", extra: "extra", vitoria: "vitoria", derrota: "derrota" };
const buffers = {}, pedidos = {};
function carregar(chave, url) {
  if (!ctx) return Promise.resolve(null);
  if (buffers[chave] !== undefined) return Promise.resolve(buffers[chave]);
  return (pedidos[chave] ||= fetch(base + url).then(r => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
    .then(b => ctx.decodeAudioData(b)).then(buf => (buffers[chave] = buf)).catch(() => (buffers[chave] = null)));
}
function preCarregar() {
  for (const [k, l] of Object.entries(AMOSTRAS)) l.forEach(n => carregar(`s:${n}`, `sons/${n}.ogg`));
  for (const f of Object.values(FAIXAS)) carregar(`m:${f}`, `musica/${f}.ogg`);
}
// toca uma gravação (uma das variações, ao acaso); devolve false se ainda não tem
function amostra(nome, vol = 0.5, atraso = 0, taxa = 1) {
  const l = AMOSTRAS[nome], buf = l && buffers[`s:${l[Math.floor(Math.random() * l.length)]}`];
  if (!buf) return false;
  const s = ctx.createBufferSource(), g = ctx.createGain();
  s.buffer = buf; s.playbackRate.value = taxa * (0.94 + Math.random() * 0.12); g.gain.value = vol;
  s.connect(g).connect(ctx.destination); s.start(ctx.currentTime + atraso);
  return true;
}
try { mudo = localStorage.getItem("arena-mudo") === "1"; } catch (e) { /* sem armazenamento */ }

export function ligarSom() {
  if (!ctx) { try { ctx = new (window.AudioContext || window.webkitAudioContext)(); preCarregar(); } catch (e) { ctx = null; } }
  if (ctx && ctx.state === "suspended") ctx.resume();
}
export function estaMudo() { return mudo; }
export function alternarMudo() {
  mudo = !mudo; try { localStorage.setItem("arena-mudo", mudo ? "1" : "0"); } catch (e) { /* ok */ }
  if (mudo) pararMusica(); else if (typeof iniciarMusica === "function") iniciarMusica(agitada);
  return mudo;
}

function tom(f0, f1, dur, tipo = "sine", vol = 0.2, atraso = 0) {
  const t = ctx.currentTime + atraso, o = ctx.createOscillator(), g = ctx.createGain();
  o.type = tipo; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + dur + 0.02);
}
function ruido(dur, freq, vol = 0.25, q = 1, atraso = 0) {
  const t = ctx.currentTime + atraso, n = Math.floor(ctx.sampleRate * dur), buf = ctx.createBuffer(1, n, ctx.sampleRate), d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 2);
  const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
  s.buffer = buf; f.type = "bandpass"; f.frequency.value = freq; f.Q.value = q; g.gain.value = vol;
  s.connect(f).connect(g).connect(ctx.destination); s.start(t);
}

export function tocar(nome, extra) {
  if (!ctx || mudo) return;
  const agora = ctx.currentTime, minimo = { atq: 0.07, morte: 0.08, impacto: 0.1, nasce: 0.05, escudo: 0.15, quebraEscudo: 0.08, empurrao: 0.12 }[nome] || 0;
  if (minimo && agora - (ultimo[nome] || 0) < minimo) return;
  ultimo[nome] = agora;
  switch (nome) {
    case "clique": if (!amostra("clique", 0.55)) tom(700, 900, 0.07, "triangle", 0.12); break;
    case "escolher": if (!amostra("escolher", 0.6)) tom(520, 780, 0.09, "triangle", 0.14); break;
    case "erro": tom(220, 150, 0.16, "square", 0.08); break;
    case "nasce": amostra("carta", 0.55); tom(300, 620, 0.14, "triangle", 0.1); ruido(0.12, 900, 0.07); break;
    case "atq":
      if (extra === "torre" || extra === "rei" || extra === "besteiros" || extra === "catapulta" || extra === "torre_arq") { ruido(0.07, 3200, 0.07, 3); tom(900, 500, 0.06, "triangle", 0.04); }
      else if (extra === "mago") tom(900, 1500, 0.14, "sine", 0.07);
      else if (extra === "mago_gelo") { tom(1800, 2400, 0.12, "sine", 0.06); ruido(0.1, 6000, 0.04, 3); }
      else if (extra === "paladino" || extra === "guerreiro" || extra === "gigante") { if (!amostra("golpe", 0.42, 0, 0.8)) { ruido(0.12, 900, 0.12, 1.2); tom(220, 110, 0.1, "triangle", 0.1); } }
      else if (extra === "assassino" || extra === "bandidos") { if (!amostra("lamina", 0.3, 0, 1.2)) { ruido(0.05, 4200, 0.08, 4); tom(1400, 700, 0.05, "triangle", 0.05); } }
      else if (extra === "cavaleiro") { if (!amostra("golpe", 0.36)) { ruido(0.06, 1800, 0.1, 2); tom(180, 90, 0.08, "triangle", 0.1); } }
      else if (extra === "barbaros") { if (!amostra("golpe", 0.38, 0, 0.9)) { ruido(0.1, 1200, 0.1, 1.5); tom(200, 100, 0.09, "triangle", 0.09); } }
      else if (extra === "cacadora") { tom(700, 260, 0.12, "triangle", 0.06); ruido(0.05, 3800, 0.05, 3); }
      else if (extra === "lobos" || extra === "raptores" || extra === "aranhas") { ruido(0.05, 2400, 0.08, 2.5); tom(420, 260, 0.05, "square", 0.03); }
      else if (extra === "vespas") { tom(240, 200, 0.12, "sawtooth", 0.04); ruido(0.04, 5200, 0.04, 4); }
      else if (extra === "touro" || extra === "triceratops") { ruido(0.25, 300, 0.22, 0.6); tom(120, 55, 0.22, "sine", 0.25); }
      else if (extra === "rex") { ruido(0.45, 220, 0.24, 0.5); tom(90, 45, 0.5, "sawtooth", 0.12); }
      else if (extra === "canhao") { ruido(0.3, 260, 0.3, 0.6); tom(140, 45, 0.25, "sine", 0.3); }
      else if (extra === "balao") break;
      else if (extra === "dragao") ruido(0.22, 700, 0.1, 0.7);
      else { ruido(0.06, 1800, 0.1, 2); tom(180, 90, 0.08, "triangle", 0.1); }
      break;
    case "impacto": ruido(0.18, 600, 0.14, 0.8); break;
    case "magia": tom(500, 1400, 0.5, "sawtooth", 0.05); break;
    case "explosao": ruido(0.6, 180, 0.5, 0.5); tom(120, 40, 0.5, "sine", 0.4); break;
    case "morte": tom(500, 200, 0.12, "triangle", 0.08); ruido(0.1, 1200, 0.06); break;
    case "torre": ruido(1.0, 140, 0.55, 0.4); tom(90, 35, 0.9, "sine", 0.45); ruido(0.5, 900, 0.15, 0.6, 0.15); break;
    case "tique": tom(1000, 1000, 0.04, "square", 0.05); break;
    case "extra": [0, 0.16, 0.32].forEach(a => tom(660, 660, 0.12, "square", 0.08, a)); break;
    case "vitoria": if (!vinheta("vitoria")) [523, 659, 784, 1047].forEach((f, i) => tom(f, f, 0.28, "triangle", 0.16, i * 0.14)); break;
    case "derrota": if (!vinheta("derrota")) [392, 330, 262, 196].forEach((f, i) => tom(f, f * 0.97, 0.34, "triangle", 0.14, i * 0.2)); break;
    case "contagem": tom(440, 440, 0.12, "triangle", 0.14); break;
    case "comeca": tom(660, 990, 0.3, "triangle", 0.18); break;
    case "moeda": if (!amostra("moeda", 0.6)) [1320, 1760].forEach((f, i) => tom(f, f, 0.09, "square", 0.05, i * 0.07)); break;
    case "bau": amostra("bau", 0.6); ruido(0.25, 500, 0.18, 0.7); [784, 988, 1175].forEach((f, i) => tom(f, f, 0.18, "triangle", 0.1, 0.15 + i * 0.08)); break;
    case "nivel": if (!amostra("conquista", 0.55)) [523, 659, 784, 1047, 1319].forEach((f, i) => tom(f, f * 1.01, 0.2, "triangle", 0.13, i * 0.07)); break;
    case "epico": amostra("conquista", 0.5); [659, 831, 988, 1319].forEach((f, i) => tom(f, f, 0.32, "sine", 0.1, i * 0.09)); ruido(0.5, 4000, 0.06, 2, 0.2); break;
    case "raio": ruido(0.35, 2600, 0.35, 0.6); tom(1800, 200, 0.3, "sawtooth", 0.08); break;
    case "gelo": [2100, 2600, 3100].forEach((f, i) => tom(f, f * 0.9, 0.25, "sine", 0.06, i * 0.05)); ruido(0.4, 5000, 0.08, 3); break;
    case "cura": [523, 784, 1047].forEach((f, i) => tom(f, f * 1.02, 0.4, "sine", 0.09, i * 0.08)); break;
    case "vs": tom(160, 80, 0.5, "sawtooth", 0.12); ruido(0.4, 300, 0.2, 0.5); break;
    case "fogos": ruido(0.45, 2600, 0.1, 1.1); ruido(0.3, 5200, 0.05, 2, 0.12); tom(900, 200, 0.25, "sine", 0.04); break;
    case "investida": ruido(0.5, 400, 0.12, 0.6); [330, 392, 494].forEach((f, i) => tom(f, f, 0.1, "square", 0.04, i * 0.06)); break;
    case "golpeForte": ruido(0.25, 600, 0.3, 0.7); tom(160, 60, 0.3, "sine", 0.3); break;
    case "salto": tom(300, 900, 0.25, "triangle", 0.08); ruido(0.2, 2500, 0.06, 2); break;
    case "pouso": ruido(0.3, 300, 0.3, 0.6); tom(140, 50, 0.25, "sine", 0.25); break;
    case "gera": [988, 1319].forEach((f, i) => tom(f, f, 0.12, "sine", 0.06, i * 0.07)); break;
    case "veneno": ruido(0.9, 900, 0.1, 0.8); [180, 170, 160].forEach((f, i) => tom(f, f * 0.8, 0.4, "sawtooth", 0.03, i * 0.12)); break;
    case "tornado": ruido(1.6, 500, 0.16, 0.5); ruido(1.2, 1400, 0.06, 1.2, 0.3); tom(160, 260, 1.2, "sawtooth", 0.025); break;
    case "terremoto": ruido(1.4, 90, 0.4, 0.4); tom(55, 38, 1.2, "sine", 0.35); ruido(0.6, 600, 0.1, 0.7, 0.4); break;
    case "cemiterio": [196, 185, 165, 147].forEach((f, i) => tom(f, f * 0.97, 0.5, "triangle", 0.06, i * 0.18)); ruido(1.0, 400, 0.05, 0.8); break;
    case "aviso": [880, 660].forEach((f, i) => tom(f, f, 0.12, "square", 0.05, i * 0.16)); break;
    case "meteoro": ruido(1.1, 120, 0.6, 0.4); tom(110, 30, 0.9, "sine", 0.5); ruido(0.5, 1800, 0.12, 0.8, 0.1); break;
    case "barril": ruido(0.25, 1400, 0.2, 0.9); tom(240, 120, 0.12, "triangle", 0.1); ruido(0.2, 500, 0.12, 0.7, 0.05); break;
    case "escudo": [784, 1175, 1568].forEach((f, i) => tom(f, f * 1.01, 0.3, "sine", 0.07, i * 0.05)); break;
    case "quebraEscudo": ruido(0.2, 5200, 0.1, 3); [1568, 1175].forEach((f, i) => tom(f, f * 0.8, 0.15, "triangle", 0.05, i * 0.04)); break;
    case "empurrao": ruido(0.3, 380, 0.2, 0.7); tom(170, 70, 0.2, "sine", 0.18); break;
    case "furia": [440, 554, 659, 880].forEach((f, i) => tom(f, f * 1.03, 0.18, "sawtooth", 0.05, i * 0.05)); ruido(0.3, 1800, 0.08, 1.5); break;
  }
}

// ------------------------------------------------------------------ música de fundo (feita na hora, sem arquivo)
// Uma melodia medieval em ré dórico: alaúde dedilhado, um bordão grave e um tambor leve. Mais agitada na partida.
let musicaLigada = true, tocandoMusica = false, agitada = false, timerMusica = null, proxNota = 0, passoMus = 0, ganhoMus = null;
try { musicaLigada = localStorage.getItem("arena-musica") !== "0"; } catch (e) { /* ok */ }
export function musicaEstaLigada() { return musicaLigada; }
export function alternarMusica() {
  musicaLigada = !musicaLigada;
  try { localStorage.setItem("arena-musica", musicaLigada ? "1" : "0"); } catch (e) { /* ok */ }
  if (musicaLigada) iniciarMusica(agitada); else pararMusica();
  return musicaLigada;
}
const ESCALA = [62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79];            // ré dórico
const FRASES = [[0, 2, 4, 3, 2, 1, 0, -1], [4, 5, 7, 5, 4, 2, 3, 1], [7, 6, 4, 5, 3, 4, 2, 0], [2, 4, 5, 7, 8, 7, 5, 4]];
const BAIXO = [50, 50, 48, 45, 50, 53, 48, 50];
const freq = (m) => 440 * Math.pow(2, (m - 69) / 12);
function alaude(f, t, vol, dur) {
  const o = ctx.createOscillator(), o2 = ctx.createOscillator(), g = ctx.createGain(), fl = ctx.createBiquadFilter();
  o.type = "triangle"; o2.type = "sawtooth"; o.frequency.value = f; o2.frequency.value = f * 1.002;
  fl.type = "lowpass"; fl.frequency.setValueAtTime(3200, t); fl.frequency.exponentialRampToValueAtTime(700, t + dur);
  const g2 = ctx.createGain(); g2.gain.value = 0.25;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.008); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g); o2.connect(g2).connect(g); g.connect(fl).connect(ganhoMus);
  o.start(t); o2.start(t); o.stop(t + dur + 0.05); o2.stop(t + dur + 0.05);
}
function bordao(f, t, dur) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = "sine"; o.frequency.value = f;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.11, t + 0.25); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(ganhoMus); o.start(t); o.stop(t + dur + 0.05);
}
function tambor(t, forte) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.frequency.setValueAtTime(forte ? 120 : 180, t); o.frequency.exponentialRampToValueAtTime(50, t + 0.18);
  g.gain.setValueAtTime(forte ? 0.32 : 0.14, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
  o.connect(g).connect(ganhoMus); o.start(t); o.stop(t + 0.25);
}
function agendar() {
  const passo = agitada ? 0.2 : 0.3;                       // colcheia
  while (proxNota < ctx.currentTime + 0.25) {
    const k = passoMus, compasso = Math.floor(k / 8), frase = FRASES[compasso % 4], nota = frase[k % 8];
    if (nota >= 0 && (agitada || k % 2 === 0 || Math.random() < 0.5)) alaude(freq(ESCALA[nota] + (compasso % 8 >= 4 ? 0 : -12)), proxNota, agitada ? 0.09 : 0.07, passo * 2.2);
    if (k % 8 === 0) bordao(freq(BAIXO[compasso % 8]), proxNota, passo * 8.2);
    if (agitada && k % 2 === 0) tambor(proxNota, k % 4 === 0);
    else if (!agitada && k % 8 === 0) tambor(proxNota, false);
    proxNota += passo; passoMus++;
  }
}
// a gravada: "menu", "batalha" ou "extra" (tempo extra e energia em dobro), sempre em laço
let querida = null, fonte = null;
const VOL_MUS = 0.42;
function tocarGravada(nome) {
  if (fonte && fonte.nome === nome) return true;
  const buf = buffers[`m:${nome}`];
  if (buf === null) return false;                              // não carregou: fica a feita na hora
  if (!buf) { carregar(`m:${nome}`, `musica/${nome}.ogg`).then(b => { if (querida === nome && b) { pararFeitaNaHora(); tocarGravada(nome); } else if (querida === nome) iniciarFeitaNaHora(); }); return true; }
  soltarFonte(0.8);
  const s = ctx.createBufferSource(), g = ctx.createGain(), t = ctx.currentTime;
  s.buffer = buf; s.loop = true;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(VOL_MUS, t + 0.9);
  s.connect(g).connect(ctx.destination); s.start(t);
  fonte = { nome, s, g };
  return true;
}
function soltarFonte(fade = 0.5) {
  if (!fonte) return;
  const { s, g } = fonte, t = ctx.currentTime;
  g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(Math.max(0.0001, g.gain.value), t); g.gain.exponentialRampToValueAtTime(0.0001, t + fade);
  s.stop(t + fade + 0.05);
  fonte = null;
}
// vinheta de fim de partida (vitória ou derrota), por cima de tudo
function vinheta(nome) {
  const buf = buffers[`m:${nome}`];
  if (!buf) return false;
  const s = ctx.createBufferSource(), g = ctx.createGain();
  s.buffer = buf; g.gain.value = 0.7; s.connect(g).connect(ctx.destination); s.start();
  return true;
}
function iniciarFeitaNaHora() {
  if (!ganhoMus) { ganhoMus = ctx.createGain(); ganhoMus.gain.value = 0.5; ganhoMus.connect(ctx.destination); }
  if (tocandoMusica) return;
  tocandoMusica = true; proxNota = ctx.currentTime + 0.1; passoMus = 0;
  timerMusica = setInterval(agendar, 90);
}
function pararFeitaNaHora() { tocandoMusica = false; clearInterval(timerMusica); }
// rapida: false = menu, true = batalha, "extra" = último minuto
export function iniciarMusica(rapida = false) {
  agitada = !!rapida;
  querida = rapida === "extra" ? "extra" : rapida ? "batalha" : "menu";
  if (!ctx || mudo || !musicaLigada) return;
  if (!tocarGravada(querida)) iniciarFeitaNaHora();
}
export function pararMusica() { querida = null; pararFeitaNaHora(); if (ctx) soltarFonte(0.4); }
