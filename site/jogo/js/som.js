// Sons do jogo, todos feitos na hora com a Web Audio (sem arquivos): soltar carta, flecha, golpe, explosão, torre caindo...
let ctx = null, mudo = false, ultimo = {};
try { mudo = localStorage.getItem("arena-mudo") === "1"; } catch (e) { /* sem armazenamento */ }

export function ligarSom() { if (!ctx) { try { ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { ctx = null; } } if (ctx && ctx.state === "suspended") ctx.resume(); }
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
  const agora = ctx.currentTime, minimo = { atq: 0.07, morte: 0.08, impacto: 0.1, nasce: 0.05 }[nome] || 0;
  if (minimo && agora - (ultimo[nome] || 0) < minimo) return;
  ultimo[nome] = agora;
  switch (nome) {
    case "clique": tom(700, 900, 0.07, "triangle", 0.12); break;
    case "escolher": tom(520, 780, 0.09, "triangle", 0.14); break;
    case "erro": tom(220, 150, 0.16, "square", 0.08); break;
    case "nasce": tom(300, 620, 0.14, "triangle", 0.16); ruido(0.12, 900, 0.1); break;
    case "atq":
      if (extra === "torre" || extra === "rei" || extra === "besteiros" || extra === "catapulta") { ruido(0.07, 3200, 0.07, 3); tom(900, 500, 0.06, "triangle", 0.04); }
      else if (extra === "mago") tom(900, 1500, 0.14, "sine", 0.07);
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
    case "vitoria": [523, 659, 784, 1047].forEach((f, i) => tom(f, f, 0.28, "triangle", 0.16, i * 0.14)); break;
    case "derrota": [392, 330, 262, 196].forEach((f, i) => tom(f, f * 0.97, 0.34, "triangle", 0.14, i * 0.2)); break;
    case "contagem": tom(440, 440, 0.12, "triangle", 0.14); break;
    case "comeca": tom(660, 990, 0.3, "triangle", 0.18); break;
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
export function iniciarMusica(rapida = false) {
  agitada = rapida;
  if (!ctx || mudo || !musicaLigada) return;
  if (!ganhoMus) { ganhoMus = ctx.createGain(); ganhoMus.gain.value = 0.5; ganhoMus.connect(ctx.destination); }
  if (tocandoMusica) return;
  tocandoMusica = true; proxNota = ctx.currentTime + 0.1; passoMus = 0;
  timerMusica = setInterval(agendar, 90);
}
export function pararMusica() { tocandoMusica = false; clearInterval(timerMusica); }
