// As regras do jogo, sem nada de tela: arena, torres, energia, cartas, alvo, caminho, projéteis e fim de partida.
// Quem manda é o dono da sala (ou o próprio aparelho, contra o bot): ele roda passo() 20 vezes por segundo e manda
// fotos do estado (foto()) para o outro jogador. Lado 0 fica embaixo (y pequeno), lado 1 em cima.
// Unidade: 1 = 1 casa. A arena tem 18 casas de largura (x) e 32 de comprimento (y), com o rio no meio.

export const L = 18, C = 32, RIO0 = 15, RIO1 = 17, PONTES = [3.5, 14.5], MEIA_PONTE = 0.95;
export const DT = 0.05, T_PARTIDA = 180, T_EXTRA = 60, ENERGIA_MAX = 10, T_ENERGIA = 2.8;

// tipo: tropa | predio | magia · n: quantos nascem · cad: segundos entre golpes · vel: casas/s · alc: alcance (borda a
// borda) · visao: até onde enxerga inimigo · ar: acerta quem voa · soPredio: só ataca construção · area: raio do dano
export const CARTAS = {
  cavaleiro: { nome: "Cavaleiro", custo: 3, tipo: "tropa", n: 1, hp: 1450, dano: 165, cad: 1.2, vel: 1.0, alc: 0.5, raio: 0.5, visao: 5.5, massa: 6,
    texto: "Forte e barato. Aguenta pancada na frente das outras tropas." },
  besteiros: { nome: "Besteiros", custo: 3, tipo: "tropa", n: 2, modelo: "besteiro", hp: 300, dano: 105, cad: 1.1, vel: 1.0, alc: 5, raio: 0.4, visao: 5.5, ar: true, proj: "virote", massa: 3,
    texto: "Dois atiradores de besta. Acertam de longe, inclusive quem voa." },
  gigante: { nome: "Gigante", custo: 5, tipo: "tropa", n: 1, hp: 3300, dano: 210, cad: 1.5, vel: 0.75, alc: 0.5, raio: 0.8, visao: 7, soPredio: true, massa: 18,
    texto: "Muita vida. Ignora as tropas e vai direto nas construções." },
  mago: { nome: "Mago", custo: 5, tipo: "tropa", n: 1, hp: 600, dano: 235, cad: 1.4, vel: 1.0, alc: 5.5, raio: 0.45, visao: 5.5, ar: true, proj: "magia", area: 1.5, massa: 4,
    texto: "Bolas de energia que acertam todos em volta do alvo." },
  bandidos: { nome: "Bandidos", custo: 2, tipo: "tropa", n: 3, modelo: "bandido", hp: 190, dano: 85, cad: 1.0, vel: 1.5, alc: 0.5, raio: 0.35, visao: 5.5, massa: 2,
    texto: "Três bandidos rápidos e fracos. Bons para cercar." },
  dragao: { nome: "Dragão", custo: 4, tipo: "tropa", n: 1, hp: 1000, dano: 135, cad: 1.5, vel: 1.5, alc: 3.5, raio: 0.6, visao: 5.5, ar: true, voa: true, proj: "fogo", area: 1.2, massa: 5,
    texto: "Voa por cima do rio e cospe fogo em área." },
  catapulta: { nome: "Catapulta", custo: 3, tipo: "predio", n: 1, hp: 800, dano: 130, cad: 0.9, vel: 0, alc: 5.5, raio: 0.65, visao: 5.5, ar: true, proj: "pedra", vida: 30, massa: 999,
    texto: "Torre de defesa que atira pedras. Dura 30 segundos." },
  bola_fogo: { nome: "Bola de Fogo", custo: 4, tipo: "magia", dano: 570, area: 2.5, danoTorre: 0.35,
    texto: "Dano em área em qualquer lugar da arena." },
  esqueletos: { nome: "Esqueletos", custo: 1, tipo: "tropa", n: 3, modelo: "esqueleto", hp: 75, dano: 70, cad: 1.0, vel: 1.4, alc: 0.5, raio: 0.32, visao: 5.5, massa: 1,
    texto: "Três esqueletos baratinhos. Distraem e cercam o inimigo." },
  guerreiro: { nome: "Guerreiro Esqueleto", custo: 4, tipo: "tropa", n: 1, hp: 1500, dano: 190, cad: 1.5, vel: 1.0, alc: 0.6, raio: 0.55, visao: 5.5, giro: 1.6, massa: 7,
    texto: "Gira o machado e acerta todo mundo em volta dele." },
  necromante: { nome: "Necromante", custo: 5, tipo: "tropa", n: 1, hp: 700, dano: 110, cad: 1.6, vel: 1.0, alc: 5, raio: 0.45, visao: 5.5, ar: true, proj: "sombra", massa: 4,
    invoca: { carta: "esqueletos", n: 2, cada: 7 },
    texto: "Atira magia de longe e chama dois esqueletos a cada 7 segundos." },
  flechas: { nome: "Chuva de Flechas", custo: 3, tipo: "magia", dano: 250, area: 3.8, danoTorre: 0.4,
    texto: "Muitas flechas numa área grande. Acaba com tropas fracas." },
};
export const BARALHO = ["cavaleiro", "besteiros", "gigante", "mago", "bandidos", "dragao", "catapulta", "bola_fogo"];
export const TODAS = ["cavaleiro", "besteiros", "gigante", "mago", "bandidos", "dragao", "catapulta", "bola_fogo", "esqueletos", "guerreiro", "necromante", "flechas"];
// um baralho válido tem 8 cartas diferentes que existem; se não, usa o padrão
export function baralhoValido(b) {
  return Array.isArray(b) && b.length === 8 && new Set(b).size === 8 && b.every(k => CARTAS[k]) ? b.slice() : BARALHO.slice();
}
const TORRE = { hp: 2600, dano: 105, cad: 0.8, alc: 7.5, raio: 1.3, ar: true, proj: "flecha", massa: 999 };
const REI = { hp: 4200, dano: 105, cad: 1.0, alc: 7.0, raio: 1.85, ar: true, proj: "flecha", massa: 999 };
const VEL_PROJ = { flecha: 14, magia: 10, fogo: 9, virote: 16, pedra: 12, sombra: 10 };
const T_NASCER = 1.0;

// gerador de números da partida (a mesma semente dá o mesmo embaralhamento)
function rng(s) {
  return () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

export function criarPartida(semente = 1, baralhos = [BARALHO, BARALHO]) {
  const r = rng(semente);
  const s = { tk: 0, tempo: T_PARTIDA, fase: "jogo", venc: -1, coroas: [0, 0], energia: [5, 5], ent: [], proj: [], ev: [], prox: 1, r,
    maos: [[], []], filas: [[], []], reiAtivo: [false, false] };
  for (const lado of [0, 1]) {
    const b = baralhoValido(baralhos[lado]);
    for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; }
    s.maos[lado] = b.slice(0, 4);
    s.filas[lado] = b.slice(4);
    const y = (v) => lado === 0 ? v : C - v;
    for (const [k, x, yy] of [["torre", 3.5, 6.5], ["torre", 14.5, 6.5], ["rei", 9, 3]]) {
      const c = k === "rei" ? REI : TORRE;
      s.ent.push({ id: s.prox++, k, lado, x, y: y(yy), hp: c.hp, hpMax: c.hp, cd: 0, alvo: 0, est: 1, tn: 0, a: lado === 0 ? 0 : Math.PI, predio: true, fixa: true, c });
    }
  }
  return s;
}

export function dadosDe(e) { return e.c; }

// onde o lado pode soltar a carta (magia vale em qualquer lugar)
export function podeSoltar(s, lado, carta, x, y) {
  if (x < 0.5 || x > L - 0.5 || y < 0.5 || y > C - 0.5) return false;
  if (CARTAS[carta].tipo === "magia") return true;
  const yy = lado === 0 ? y : C - y;                       // do ponto de vista de quem joga, o campo dele é y < 15
  if (yy <= RIO0 - 0.5) return !sobreTorre(s, x, y);
  // torre inimiga caída abre o bolsão daquele lado
  const inim = 1 - lado;
  const caiuEsq = !s.ent.some(e => e.k === "torre" && e.lado === inim && e.x < 9);
  const caiuDir = !s.ent.some(e => e.k === "torre" && e.lado === inim && e.x > 9);
  if (yy >= RIO1 + 0.5 && yy <= 21 && ((x < 9 && caiuEsq) || (x > 9 && caiuDir))) return !sobreTorre(s, x, y);
  return false;
}
function sobreTorre(s, x, y) {
  return s.ent.some(e => e.fixa && Math.hypot(e.x - x, e.y - y) < e.c.raio + 0.3);
}

// joga a carta i da mão do lado, em (x, y). Devolve true se valeu.
export function jogar(s, lado, i, x, y) {
  if (s.fase === "fim") return false;
  const carta = s.maos[lado][i];
  if (!carta) return false;
  const c = CARTAS[carta];
  if (s.energia[lado] < c.custo) return false;
  x = Math.round(x * 2) / 2; y = Math.round(y * 2) / 2;
  if (!podeSoltar(s, lado, carta, x, y)) return false;
  s.energia[lado] -= c.custo;
  s.filas[lado].push(carta);
  s.maos[lado][i] = s.filas[lado].shift();
  if (c.tipo === "magia") {
    const rei = s.ent.find(e => e.k === "rei" && e.lado === lado) || { x: 9, y: lado === 0 ? 3 : C - 3 };
    const d = Math.hypot(x - rei.x, y - rei.y);
    s.proj.push({ id: s.prox++, tipo: "bola", lado, x: rei.x, y: rei.y, x0: rei.x, y0: rei.y, tx: x, ty: y, t: 0, dur: Math.max(0.9, d / 13), carta });
    s.ev.push(["magia", lado, x, y]);
    return true;
  }
  nascer(s, carta, lado, x, y, c.n);
  return true;
}

function nascer(s, carta, lado, x, y, n) {
  const c = CARTAS[carta], dir = lado === 0 ? 1 : -1;
  const lugares = n === 1 ? [[0, 0]] : n === 2 ? [[-0.55, 0], [0.55, 0]] : [[0, 0.5 * dir], [-0.6, -0.35 * dir], [0.6, -0.35 * dir]];
  for (const [dx, dy] of lugares) {
    const e = { id: s.prox++, k: carta, lado, x: Math.min(L - 0.4, Math.max(0.4, x + dx)), y: Math.min(C - 0.4, Math.max(0.4, y + dy)), hp: c.hp, hpMax: c.hp, cd: 0, alvo: 0, est: 0,
      tn: T_NASCER, a: lado === 0 ? 0 : Math.PI, predio: c.tipo === "predio", fixa: false, c, vida: c.vida || 0, inv: c.invoca ? c.invoca.cada * 0.5 : 0 };
    s.ent.push(e);
    s.ev.push(["nasce", e.id]);
  }
}

const ladoDoRio = (y) => y < RIO0 ? 0 : y > RIO1 ? 1 : -1;
const pontePerto = (x) => Math.abs(x - PONTES[0]) < Math.abs(x - PONTES[1]) ? PONTES[0] : PONTES[1];

// para onde andar agora para chegar em (tx, ty): quem anda no chão tem de passar por uma ponte
function rumo(e, tx, ty) {
  if (e.c.voa) return [tx, ty];
  const de = ladoDoRio(e.y), para = ladoDoRio(ty);
  if (de === para && de !== -1) return [tx, ty];
  if (de === -1) {                                          // já está em cima da ponte: segue reto até sair
    if (para === -1) return [tx, ty];
    const bx = pontePerto(e.x);
    return [Math.min(bx + 0.5, Math.max(bx - 0.5, e.x)), para === 1 ? RIO1 + 0.4 : RIO0 - 0.4];
  }
  let bx = PONTES[0], melhor = 1e9;
  for (const p of PONTES) { const custo = Math.abs(e.x - p) + Math.abs(tx - p); if (custo < melhor) { melhor = custo; bx = p; } }
  const entrada = de === 0 ? RIO0 - 0.15 : RIO1 + 0.15;
  if (Math.abs(e.x - bx) < 0.75 && Math.abs(e.y - entrada) < 0.6) return [bx, de === 0 ? RIO1 + 0.4 : RIO0 - 0.4];
  return [bx, entrada];
}

function dano(s, alvo, v, autor) {
  if (alvo.hp <= 0) return;
  alvo.hp -= v;
  if (alvo.k === "rei") s.reiAtivo[alvo.lado] = true;
  s.ev.push(["dano", alvo.id, Math.round(v)]);
}

function danoArea(s, lado, x, y, raio, v, ar, fatorTorre = 1) {
  for (const o of s.ent) {
    if (o.lado === lado || o.hp <= 0 || o.tn > 0) continue;
    if (o.c.voa && !ar) continue;
    if (Math.hypot(o.x - x, o.y - y) <= raio + o.c.raio * 0.6) dano(s, o, o.fixa ? v * fatorTorre : v);
  }
}

function escolherAlvo(s, e) {
  const c = e.c;
  let melhor = null, dm = 1e9;
  // 1) uma tropa inimiga à vista (quem só ataca construção pula esta parte)
  if (!c.soPredio) {
    for (const o of s.ent) {
      if (o.lado === e.lado || o.hp <= 0 || o.tn > 0 || o.predio) continue;
      if (o.c.voa && !c.ar) continue;
      const d = Math.hypot(o.x - e.x, o.y - e.y) - o.c.raio - c.raio;
      if (d <= (e.fixa || e.predio ? c.alc : c.visao) && d < dm) { dm = d; melhor = o; }
    }
    if (melhor) return melhor;
  }
  if (e.fixa || e.predio) {                                 // torre e catapulta também atiram em construção ao alcance
    for (const o of s.ent) {
      if (o.lado === e.lado || o.hp <= 0 || o.tn > 0 || !o.predio || o.fixa) continue;
      const d = Math.hypot(o.x - e.x, o.y - e.y) - o.c.raio - c.raio;
      if (d <= c.alc && d < dm) { dm = d; melhor = o; }
    }
    return melhor;
  }
  // 2) a construção inimiga mais perto (pelo caminho de verdade: passando pela ponte)
  for (const o of s.ent) {
    if (o.lado === e.lado || o.hp <= 0 || o.tn > 0 || !o.predio) continue;
    let d = Math.hypot(o.x - e.x, o.y - e.y);
    if (!c.voa && ladoDoRio(o.y) !== ladoDoRio(e.y) && ladoDoRio(e.y) !== -1) {
      let via = 1e9;
      for (const p of PONTES) via = Math.min(via, Math.hypot(p - e.x, 16 - e.y) + Math.hypot(o.x - p, o.y - 16));
      d = via;
    }
    if (o.k === "rei") d += 0.01;
    if (d < dm) { dm = d; melhor = o; }
  }
  return melhor;
}

export function passo(s) {
  if (s.fase === "fim") return;
  s.tk++;
  s.tempo -= DT;
  const dobro = s.fase === "extra" || s.tempo <= 60;
  for (const lado of [0, 1]) s.energia[lado] = Math.min(ENERGIA_MAX, s.energia[lado] + DT / T_ENERGIA * (dobro ? 2 : 1));
  const porId = new Map(s.ent.map(e => [e.id, e]));

  for (const e of s.ent) {
    if (e.hp <= 0) continue;
    if (e.tn > 0) { e.tn -= DT; if (e.tn <= 0) e.est = 1; continue; }
    const c = e.c;
    if (e.vida) { e.vida -= DT; e.hp -= e.hpMax * DT / c.vida; if (e.hp <= 0) continue; }
    e.cd = Math.max(0, e.cd - DT);
    if (c.invoca) {                                         // o necromante chama esqueletos de tempos em tempos
      e.inv -= DT;
      if (e.inv <= 0) {
        e.inv = c.invoca.cada;
        const atras = e.lado === 0 ? -0.9 : 0.9;
        nascer(s, c.invoca.carta, e.lado, e.x, e.y + atras, c.invoca.n);
        s.ev.push(["invoca", e.id]);
      }
    }
    if (e.k === "rei" && !s.reiAtivo[e.lado]) continue;     // o rei só acorda quando apanha ou perde uma torre
    // alvo: mantém o atual se ainda vale; senão procura outro
    let alvo = porId.get(e.alvo);
    if (alvo && (alvo.hp <= 0 || alvo.tn > 0)) alvo = null;
    if (alvo) {
      const d = Math.hypot(alvo.x - e.x, alvo.y - e.y) - alvo.c.raio - c.raio;
      if (e.fixa || e.predio) { if (d > c.alc) alvo = null; }
      else if (alvo.predio) { if (!c.soPredio && (s.tk + e.id) % 4 === 0) alvo = null; }   // andando para a torre: reolha quem apareceu
      else if (d > c.visao + 1.5) alvo = null;
    }
    if (!alvo) alvo = escolherAlvo(s, e);
    e.alvo = alvo ? alvo.id : 0;
    if (!alvo) { e.est = 1; continue; }
    const dx = alvo.x - e.x, dy = alvo.y - e.y, dist = Math.hypot(dx, dy), d = dist - alvo.c.raio - c.raio;
    if (d <= c.alc) {                                       // ao alcance: bate
      if (e.est !== 2) { e.est = 2; e.cd = Math.max(e.cd, c.cad * 0.45); }
      e.a = Math.atan2(dx, dy);
      if (e.cd <= 0) {
        e.cd = c.cad;
        s.ev.push(["atq", e.id]);
        if (c.proj) {
          s.proj.push({ id: s.prox++, tipo: c.proj, lado: e.lado, x: e.x, y: e.y, alvo: alvo.id, tx: alvo.x, ty: alvo.y, dano: c.dano, area: c.area || 0, ar: !!c.ar,
            alto: e.fixa ? 1 : 0, voaAlvo: !!alvo.c.voa });
        } else if (c.giro) { danoArea(s, e.lado, e.x, e.y, c.giro + c.raio, c.dano, !!c.ar); s.ev.push(["giro", e.id]); }
        else if (c.area) danoArea(s, e.lado, alvo.x, alvo.y, c.area, c.dano, !!c.ar);
        else dano(s, alvo, c.dano, e);
      }
    } else if (!e.predio) {                                 // longe: anda
      e.est = 1;
      const [rx, ry] = rumo(e, alvo.x, alvo.y);
      const vx = rx - e.x, vy = ry - e.y, n = Math.hypot(vx, vy) || 1;
      const andar = Math.min(c.vel * DT, n);
      e.x += vx / n * andar; e.y += vy / n * andar;
      e.a = Math.atan2(vx, vy);
    } else e.est = 1;
  }

  // ninguém fica em cima de ninguém; tropa no chão não entra na torre nem no rio
  const moveis = s.ent.filter(e => !e.predio && e.hp > 0 && e.tn <= 0);
  for (let i = 0; i < moveis.length; i++) {
    const a = moveis[i];
    for (let j = i + 1; j < moveis.length; j++) {
      const b = moveis[j];
      if (!!a.c.voa !== !!b.c.voa) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy), min = (a.c.raio + b.c.raio) * 0.92;
      if (d < min) {
        const f = (min - d) * 0.5, nx = d > 1e-4 ? dx / d : Math.cos(a.id), ny = d > 1e-4 ? dy / d : Math.sin(a.id);
        const pa = b.c.massa / (a.c.massa + b.c.massa), pb = 1 - pa;
        a.x -= nx * f * pa * 2; a.y -= ny * f * pa * 2; b.x += nx * f * pb * 2; b.y += ny * f * pb * 2;
      }
    }
  }
  for (const e of moveis) {
    if (!e.c.voa) {
      for (const o of s.ent) {
        if (!o.predio || o.hp <= 0) continue;
        const dx = e.x - o.x, dy = e.y - o.y, d = Math.hypot(dx, dy), min = o.c.raio + e.c.raio * 0.8;
        if (d < min && d > 1e-4) {
          const nx = dx / d, ny = dy / d;
          e.x = o.x + nx * min; e.y = o.y + ny * min;
          // andando de frente para a construção: escorrega pelo lado (o que aponta para onde ela quer ir, ou para o meio)
          const mx = Math.sin(e.a), my = Math.cos(e.a);
          if (e.est === 1 && mx * nx + my * ny < -0.2) {
            let tx = -ny, ty = nx, lado = mx * tx + my * ty;
            if (Math.abs(lado) < 0.2) lado = tx * (9 - e.x) || 1;
            if (lado < 0) { tx = -tx; ty = -ty; }
            e.x += tx * e.c.vel * DT; e.y += ty * e.c.vel * DT;
          }
        }
      }
      if (e.y > RIO0 && e.y < RIO1) {
        const bx = pontePerto(e.x);
        if (Math.abs(e.x - bx) <= MEIA_PONTE + 0.6) e.x = Math.min(bx + MEIA_PONTE - 0.25, Math.max(bx - MEIA_PONTE + 0.25, e.x));
        else e.y = e.y < 16 ? RIO0 : RIO1;
      }
    }
    e.x = Math.min(L - 0.35, Math.max(0.35, e.x)); e.y = Math.min(C - 0.35, Math.max(0.35, e.y));
  }

  // projéteis
  for (const p of s.proj) {
    if (p.tipo === "bola") {
      p.t += DT;
      const q = Math.min(1, p.t / p.dur);
      p.x = p.x0 + (p.tx - p.x0) * q; p.y = p.y0 + (p.ty - p.y0) * q;
      if (q >= 1) {
        const c = CARTAS[p.carta];
        danoArea(s, p.lado, p.tx, p.ty, c.area, c.dano, true, c.danoTorre);
        s.ev.push(["explode", p.tx, p.ty, c.area, p.carta === "flechas" ? "flechas" : undefined]);
        p.fim = true;
      }
      continue;
    }
    const alvo = porId.get(p.alvo);
    if (alvo && alvo.hp > 0) { p.tx = alvo.x; p.ty = alvo.y; }
    const dx = p.tx - p.x, dy = p.ty - p.y, d = Math.hypot(dx, dy), v = VEL_PROJ[p.tipo] * DT;
    if (d <= v + 0.2) {
      if (p.area) { danoArea(s, p.lado, p.tx, p.ty, p.area, p.dano, p.ar); s.ev.push(["explode", p.tx, p.ty, p.area * 0.7, p.tipo]); }
      else if (alvo && alvo.hp > 0) dano(s, alvo, p.dano);
      p.fim = true;
    } else { p.x += dx / d * v; p.y += dy / d * v; }
  }
  s.proj = s.proj.filter(p => !p.fim);

  // mortes, coroas e o fim
  let caiuRei = -1;
  for (const e of s.ent) {
    if (e.hp > 0) continue;
    s.ev.push(["morte", e.id, e.x, e.y, e.k]);
    if (e.fixa) {
      const quem = 1 - e.lado;
      if (e.k === "rei") { s.coroas[quem] = 3; caiuRei = e.lado; }
      else { s.coroas[quem] = Math.min(3, s.coroas[quem] + 1); s.reiAtivo[e.lado] = true; }
      s.ev.push(["torre", e.id, e.lado, e.k]);
    }
  }
  s.ent = s.ent.filter(e => e.hp > 0);
  if (caiuRei >= 0) return fim(s, 1 - caiuRei);
  if (s.fase === "extra" && s.coroas[0] !== s.coroas[1]) return fim(s, s.coroas[0] > s.coroas[1] ? 0 : 1);
  if (s.tempo <= 0) {
    if (s.coroas[0] !== s.coroas[1]) return fim(s, s.coroas[0] > s.coroas[1] ? 0 : 1);
    if (s.fase === "jogo") { s.fase = "extra"; s.tempo = T_EXTRA; s.ev.push(["extra"]); return; }
    // empate no tempo extra: perde quem tem a torre mais machucada
    const pior = (lado) => Math.min(...s.ent.filter(e => e.fixa && e.lado === lado).map(e => e.hp / e.hpMax));
    const a = pior(0), b = pior(1);
    fim(s, Math.abs(a - b) < 0.005 ? 2 : a > b ? 0 : 1);
  }
}

function fim(s, venc) { s.fase = "fim"; s.venc = venc; s.ev.push(["fim", venc]); }

// foto do estado para desenhar (e para mandar ao outro jogador). Só leva a mão e a energia de quem vai ver.
const EST = ["nascer", "andar", "atacar"];
export function foto(s, lado, ev) {
  const f = {
    tk: s.tk, tempo: Math.max(0, Math.ceil(s.tempo)), fase: s.fase, venc: s.venc, coroas: s.coroas.slice(), energia: Math.round(s.energia[lado] * 100) / 100,
    dobro: s.fase === "extra" || s.tempo <= 60, mao: s.maos[lado].slice(), prox: s.filas[lado][0], rei: s.reiAtivo.slice(),
    ent: s.ent.map(e => [e.id, e.k, e.lado, Math.round(e.x * 100) / 100, Math.round(e.y * 100) / 100, Math.max(0, Math.round(e.hp)), e.hpMax, e.est, Math.round(e.a * 100) / 100,
      e.tn > 0 ? Math.round(e.tn * 100) / 100 : 0]),
    proj: s.proj.map(p => p.tipo === "bola" ? [p.id, "bola", Math.round(p.x * 100) / 100, Math.round(p.y * 100) / 100, Math.round(Math.min(1, p.t / p.dur) * 100) / 100, p.lado, p.carta,
      Math.round(p.tx * 100) / 100, Math.round(p.ty * 100) / 100]
      : [p.id, p.tipo, Math.round(p.x * 100) / 100, Math.round(p.y * 100) / 100, p.alto, p.lado, p.voaAlvo ? 1 : 0, Math.round(p.tx * 100) / 100, Math.round(p.ty * 100) / 100]),
    ev: ev || s.ev,
  };
  return f;
}
export { EST };
