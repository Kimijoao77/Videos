// O adversário de computador: olha o estado de tempos em tempos e decide se solta uma carta.
// Funciona com qualquer baralho: cada carta tem um papel (tanque, apoio, enxame, defesa, magia). Defende quando tem
// tropa inimiga no campo dele, junta energia para atacar com um tanque na frente e usa magia quando vale a pena.
// nível 0 = fácil (lento e erra), 1 = normal, 2 = difícil (rápido e escolhe a resposta certa).
import { CARTAS, C, jogar, podeSoltar } from "./sim.js";

const TANQUE = ["gigante", "guerreiro", "cavaleiro"];
const APOIO = ["mago", "necromante", "dragao", "besteiros"];
const ENXAME = ["esqueletos", "bandidos"];
const DEFESA_PREDIO = ["catapulta"];
export const BARALHOS_BOT = [
  ["cavaleiro", "besteiros", "gigante", "mago", "bandidos", "dragao", "catapulta", "bola_fogo"],
  ["guerreiro", "esqueletos", "gigante", "necromante", "besteiros", "dragao", "flechas", "bola_fogo"],
  ["cavaleiro", "esqueletos", "guerreiro", "mago", "bandidos", "necromante", "catapulta", "flechas"],
];

export function criarBot(lado, nivel = 1) {
  return { lado, nivel, espera: 2.5, pista: Math.random() < 0.5 ? 3.5 : 14.5 };
}

export function pensar(bot, s, dt) {
  // difícil: além de reagir mais rápido, recebe 25% a mais de energia (o aviso está na tela de escolher o nível)
  if (bot.nivel === 2 && s.fase !== "fim") s.energia[bot.lado] = Math.min(10, s.energia[bot.lado] + dt / 2.8 * 0.25 * (s.fase === "extra" || s.tempo <= 60 ? 2 : 1));
  bot.espera -= dt;
  if (bot.espera > 0 || s.fase === "fim") return;
  const nv = bot.nivel;
  bot.espera = [2.4, 0.6, 0.3][nv] + Math.random() * [1.2, 0.5, 0.25][nv];
  const lado = bot.lado, en = s.energia[lado], mao = s.maos[lado];
  const meu = (y) => lado === 0 ? y : C - y;                   // y visto do meu lado (meu campo: 0 a 15)
  const tem = (k) => mao.includes(k) && CARTAS[k].custo <= en;
  const soltar = (carta, x, yy) => {
    const i = mao.indexOf(carta);
    if (i < 0 || CARTAS[carta].custo > en) return false;
    x = Math.min(17, Math.max(1, x)); yy = Math.min(14, Math.max(1, yy));
    for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, -1], [1.5, -1], [-1.5, -1], [0, -2]])
      if (podeSoltar(s, lado, carta, x + dx, meu(yy + dy)) && jogar(s, lado, i, x + dx, meu(yy + dy))) return true;
    return false;
  };
  const inimigos = s.ent.filter(e => e.lado !== lado && !e.predio && e.tn <= 0);
  const meus = s.ent.filter(e => e.lado === lado && !e.predio);
  const valor = (e) => CARTAS[e.k].custo / CARTAS[e.k].n;

  // fácil: às vezes só espera
  if (nv === 0 && Math.random() < 0.45) return;

  // 1) magias: vale quando pega bastante coisa ou termina uma torre
  for (const magia of mao.filter(k => CARTAS[k].tipo === "magia" && tem(k))) {
    if (nv === 0) break;
    const m = CARTAS[magia];
    let melhor = null, ganho = 0;
    for (const a of inimigos) {
      let v = 0;
      for (const b of inimigos) if (Math.hypot(a.x - b.x, a.y - b.y) <= m.area * 0.85 && b.hp <= m.dano * 1.2) v += valor(b);
      if (v > ganho) { ganho = v; melhor = a; }
    }
    if (melhor && ganho >= m.custo + (nv === 2 ? 0 : 0.5)) { if (jogar(s, lado, mao.indexOf(magia), melhor.x, melhor.y)) return; }
    const torre = s.ent.find(e => e.fixa && e.lado !== lado && e.hp <= m.dano * m.danoTorre);
    if (torre) { if (jogar(s, lado, mao.indexOf(magia), torre.x, torre.y)) return; }
  }

  // 2) defesa: tropa inimiga no meu campo
  const ameacas = inimigos.filter(e => meu(e.y) < 15.5).sort((a, b) => meu(a.y) - meu(b.y));
  if (ameacas.length) {
    const a = ameacas[0];
    const defesa = meus.filter(m => Math.hypot(m.x - a.x, m.y - a.y) < 6).length;
    const forca = ameacas.reduce((t, e) => t + valor(e), 0);
    if (nv === 0 ? meu(a.y) < 6 : (defesa * 2.5 < forca || meu(a.y) < 9)) {
      const voa = CARTAS[a.k].voa, muitos = ameacas.filter(e => Math.hypot(e.x - a.x, e.y - a.y) < 3).length >= 3, tanque = TANQUE.includes(a.k);
      let ordem = voa ? ["besteiros", "mago", "necromante", "dragao", "catapulta"]
        : muitos ? ["guerreiro", "mago", "dragao", "cavaleiro", "necromante", "bandidos", "besteiros"]
        : tanque ? ["esqueletos", "bandidos", "catapulta", "guerreiro", "cavaleiro", "besteiros", "mago", "necromante", "dragao"]
        : ["cavaleiro", "guerreiro", "esqueletos", "bandidos", "besteiros", "catapulta", "mago", "dragao", "necromante"];
      if (nv === 0) ordem = ordem.slice().sort(() => Math.random() - 0.5);
      for (const carta of ordem) {
        if (!tem(carta)) continue;
        const longe = CARTAS[carta].alc > 2;
        const x = DEFESA_PREDIO.includes(carta) ? (a.x < 9 ? 6 : 12) : a.x + (longe ? (a.x < 9 ? 2 : -2) : 0);
        const yy = DEFESA_PREDIO.includes(carta) ? 9 : Math.max(2, meu(a.y) - (longe ? 4 : nv === 2 ? 1.5 : 2));
        if (soltar(carta, x, yy)) return;
      }
    }
  }

  // 3) ataque: junta energia, solta um tanque e depois o apoio atrás dele
  const dobro = s.fase === "extra" || s.tempo <= 60;
  const frente = meus.filter(m => TANQUE.includes(m.k) && m.tn <= 0).sort((a, b) => meu(b.y) - meu(a.y))[0];
  if (frente && meu(frente.y) > 6 && meu(frente.y) < 26) {
    for (const carta of [...APOIO, ...ENXAME]) {
      if (tem(carta) && en >= CARTAS[carta].custo + (nv === 0 ? 2 : 0)) {
        if (soltar(carta, frente.x + (Math.random() - 0.5) * 2, Math.min(14, meu(frente.y) - 2.5))) return;
      }
    }
  }
  if (nv === 0 ? en >= 9.9 : (en >= (dobro ? 7 : 8.5) || en >= 9.8)) {
    if (Math.random() < 0.3) bot.pista = bot.pista < 9 ? 14.5 : 3.5;
    const fracas = s.ent.filter(e => e.k === "torre" && e.lado !== lado).sort((a, b) => a.hp - b.hp);
    if (fracas.length && fracas[0].hp < 1800) bot.pista = fracas[0].x;
    for (const carta of [...TANQUE, "dragao", ...APOIO, ...ENXAME, ...DEFESA_PREDIO]) {
      if (!tem(carta)) continue;
      const yy = carta === "gigante" ? 3 : DEFESA_PREDIO.includes(carta) ? 10 : en >= 9.5 ? 13 : 6;
      if (soltar(carta, bot.pista + (Math.random() - 0.5), yy)) return;
    }
  }
}
