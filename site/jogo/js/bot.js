// O adversário de computador: olha o estado a cada meio segundo e decide se solta uma carta.
// Defende quando tem tropa inimiga no campo dele, guarda energia para atacar com um tanque na frente e usa a bola de
// fogo quando acerta várias tropas ou acaba com uma torre.
import { CARTAS, C, jogar, podeSoltar } from "./sim.js";

export function criarBot(lado, nivel = 1) {
  return { lado, nivel, espera: 2.5, pista: Math.random() < 0.5 ? 3.5 : 14.5 };
}

export function pensar(bot, s, dt) {
  bot.espera -= dt;
  if (bot.espera > 0 || s.fase === "fim") return;
  bot.espera = (bot.nivel === 0 ? 1.6 : 0.55) + Math.random() * 0.5;
  const lado = bot.lado, en = s.energia[lado], mao = s.maos[lado];
  const meu = (y) => lado === 0 ? y : C - y;                   // y visto do meu lado (meu campo: 0 a 15)
  const soltar = (carta, x, yy) => {
    const i = mao.indexOf(carta);
    if (i < 0 || CARTAS[carta].custo > en) return false;
    x = Math.min(17, Math.max(1, x)); yy = Math.min(14, Math.max(1, yy));
    for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, -1], [1.5, -1], [-1.5, -1], [0, -2]])
      if (podeSoltar(s, lado, carta, x + dx, meu(yy + dy)) && jogar(s, lado, i, x + dx, meu(yy + dy))) return true;
    return false;
  };
  const tem = (c) => mao.includes(c) && CARTAS[c].custo <= en;
  const inimigos = s.ent.filter(e => e.lado !== lado && !e.predio && e.tn <= 0);
  const meus = s.ent.filter(e => e.lado === lado && !e.predio);

  // 1) bola de fogo: vale quando pega bastante coisa ou termina uma torre
  if (tem("bola_fogo")) {
    let melhor = null, valor = 0;
    for (const a of inimigos) {
      let v = 0;
      for (const b of inimigos) if (Math.hypot(a.x - b.x, a.y - b.y) <= 2.3 && b.hp <= 700) v += CARTAS[b.k].custo / CARTAS[b.k].n;
      if (v > valor) { valor = v; melhor = a; }
    }
    if (melhor && valor >= 4) { const i = mao.indexOf("bola_fogo"); if (jogar(s, lado, i, melhor.x, melhor.y + (lado === 0 ? -0.5 : 0.5) * 0)) return; }
    const torre = s.ent.find(e => e.fixa && e.lado !== lado && e.hp <= 190);
    if (torre) { const i = mao.indexOf("bola_fogo"); if (jogar(s, lado, i, torre.x, torre.y)) return; }
  }

  // 2) defesa: tropa inimiga no meu campo
  const ameacas = inimigos.filter(e => meu(e.y) < 15.5).sort((a, b) => meu(a.y) - meu(b.y));
  if (ameacas.length) {
    const a = ameacas[0];
    const defesa = meus.filter(m => Math.hypot(m.x - a.x, m.y - a.y) < 6).length;
    const forca = ameacas.reduce((t, e) => t + CARTAS[e.k].custo / CARTAS[e.k].n, 0);
    if (defesa * 2.5 < forca || meu(a.y) < 9) {
      const voa = CARTAS[a.k].voa, muitos = ameacas.length >= 3, tanque = a.k === "gigante";
      const ordem = voa ? ["besteiros", "mago", "dragao", "catapulta"]
        : muitos ? ["mago", "dragao", "cavaleiro", "bandidos", "besteiros"]
        : tanque ? ["bandidos", "catapulta", "cavaleiro", "besteiros", "mago", "dragao"]
        : ["cavaleiro", "bandidos", "besteiros", "catapulta", "mago", "dragao"];
      for (const carta of ordem) {
        if (!tem(carta)) continue;
        const longe = CARTAS[carta].alc > 2;
        const x = carta === "catapulta" ? (a.x < 9 ? 6 : 12) : a.x + (longe ? (a.x < 9 ? 2 : -2) : 0);
        const yy = carta === "catapulta" ? 9 : Math.max(2, meu(a.y) - (longe ? 4 : 2));
        if (soltar(carta, x, yy)) return;
      }
    }
  }

  // 3) ataque: junta energia, solta um tanque e depois o apoio atrás dele
  const dobro = s.fase === "extra" || s.tempo <= 60;
  const frente = meus.filter(m => (m.k === "gigante" || m.k === "cavaleiro") && m.tn <= 0).sort((a, b) => meu(b.y) - meu(a.y))[0];
  if (frente && meu(frente.y) > 6 && meu(frente.y) < 26) {
    for (const carta of ["mago", "besteiros", "dragao", "bandidos"]) {
      if (tem(carta) && en >= CARTAS[carta].custo + (bot.nivel === 0 ? 2 : 0)) {
        if (soltar(carta, frente.x + (Math.random() - 0.5) * 2, Math.min(14, meu(frente.y) - 2.5))) return;
      }
    }
  }
  if (en >= (dobro ? 7 : 8.5) || en >= 9.8) {
    if (Math.random() < 0.3) bot.pista = bot.pista < 9 ? 14.5 : 3.5;
    const fracas = s.ent.filter(e => e.k === "torre" && e.lado !== lado).sort((a, b) => a.hp - b.hp);
    if (fracas.length && fracas[0].hp < 1800) bot.pista = fracas[0].x;
    for (const carta of ["gigante", "cavaleiro", "dragao", "mago", "besteiros", "bandidos", "catapulta"]) {
      if (!tem(carta)) continue;
      const yy = carta === "gigante" ? 3 : carta === "catapulta" ? 10 : en >= 9.5 ? 13 : 6;
      if (soltar(carta, bot.pista + (Math.random() - 0.5), yy)) return;
    }
  }
}
