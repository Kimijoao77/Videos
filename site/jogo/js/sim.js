// As regras do jogo, sem nada de tela: arena, torres, energia, cartas, alvo, caminho, projéteis e fim de partida.
// Quem manda é o dono da sala (ou o próprio aparelho, contra o bot): ele roda passo() 20 vezes por segundo e manda
// fotos do estado (foto()) para o outro jogador. Lado 0 fica embaixo (y pequeno), lado 1 em cima.
// Unidade: 1 = 1 casa. A arena tem 18 casas de largura (x) e 32 de comprimento (y), com o rio no meio.

export const L = 18, C = 32, RIO0 = 15, RIO1 = 17, PONTES = [3.5, 14.5], MEIA_PONTE = 0.95;
export const DT = 0.05, T_PARTIDA = 180, T_EXTRA = 60, ENERGIA_MAX = 10, T_ENERGIA = 2.8;

// tipo: tropa | predio | magia · n: quantos nascem · cad: segundos entre golpes · vel: casas/s · alc: alcance (borda a
// borda) · visao: até onde enxerga inimigo · ar: acerta quem voa · soPredio: só ataca construção · area: raio do dano
export const CARTAS = {
  cavaleiro: { nome: "Cavaleiro", custo: 3, tipo: "tropa", raridade: "comum", n: 1, hp: 1450, dano: 165, cad: 1.2, vel: 1.0, alc: 0.5, raio: 0.5, visao: 5.5, massa: 6,
    texto: "Forte e barato. Aguenta pancada na frente das outras tropas." },
  besteiros: { nome: "Besteiros", custo: 3, tipo: "tropa", raridade: "comum", n: 2, modelo: "besteiro", hp: 300, dano: 105, cad: 1.1, vel: 1.0, alc: 5, raio: 0.4, visao: 5.5, ar: true, proj: "virote", massa: 3,
    texto: "Dois atiradores de besta. Acertam de longe, inclusive quem voa." },
  gigante: { nome: "Gigante", custo: 5, tipo: "tropa", raridade: "raro", n: 1, hp: 3300, dano: 210, cad: 1.5, vel: 0.75, alc: 0.5, raio: 0.8, visao: 7, soPredio: true, massa: 18,
    texto: "Muita vida. Ignora as tropas e vai direto nas construções." },
  mago: { nome: "Mago", custo: 5, tipo: "tropa", raridade: "raro", n: 1, hp: 600, dano: 235, cad: 1.4, vel: 1.0, alc: 5.5, raio: 0.45, visao: 5.5, ar: true, proj: "magia", area: 1.5, massa: 4,
    texto: "Bolas de energia que acertam todos em volta do alvo." },
  bandidos: { nome: "Bandidos", custo: 2, tipo: "tropa", raridade: "comum", n: 3, modelo: "bandido", hp: 190, dano: 85, cad: 1.0, vel: 1.5, alc: 0.5, raio: 0.35, visao: 5.5, massa: 2,
    texto: "Três bandidos rápidos e fracos. Bons para cercar." },
  dragao: { nome: "Dragão", custo: 4, tipo: "tropa", raridade: "epico", n: 1, hp: 1000, dano: 135, cad: 1.5, vel: 1.5, alc: 3.5, raio: 0.6, visao: 5.5, ar: true, voa: true, proj: "fogo", area: 1.2, massa: 5,
    texto: "Voa por cima do rio e cospe fogo em área." },
  catapulta: { nome: "Catapulta", custo: 3, tipo: "predio", raridade: "raro", n: 1, hp: 800, dano: 130, cad: 0.9, vel: 0, alc: 5.5, raio: 0.65, visao: 5.5, ar: true, proj: "pedra", vida: 30, massa: 999,
    texto: "Torre de defesa que atira pedras. Dura 30 segundos." },
  bola_fogo: { nome: "Bola de Fogo", custo: 4, tipo: "magia", raridade: "raro", dano: 570, area: 2.5, danoTorre: 0.35,
    texto: "Dano em área em qualquer lugar da arena." },
  esqueletos: { nome: "Esqueletos", custo: 1, tipo: "tropa", raridade: "comum", n: 3, modelo: "esqueleto", hp: 75, dano: 70, cad: 1.0, vel: 1.4, alc: 0.5, raio: 0.32, visao: 5.5, massa: 1,
    texto: "Três esqueletos baratinhos. Distraem e cercam o inimigo." },
  guerreiro: { nome: "Guerreiro Esqueleto", custo: 4, tipo: "tropa", raridade: "raro", n: 1, hp: 1500, dano: 190, cad: 1.5, vel: 1.0, alc: 0.6, raio: 0.55, visao: 5.5, giro: 1.6, massa: 7,
    texto: "Gira o machado e acerta todo mundo em volta dele." },
  necromante: { nome: "Necromante", custo: 5, tipo: "tropa", raridade: "epico", n: 1, hp: 700, dano: 110, cad: 1.6, vel: 1.0, alc: 5, raio: 0.45, visao: 5.5, ar: true, proj: "sombra", massa: 4,
    invoca: { carta: "esqueletos", n: 2, cada: 7 },
    texto: "Atira magia de longe e chama dois esqueletos a cada 7 segundos." },
  flechas: { nome: "Chuva de Flechas", custo: 3, tipo: "magia", raridade: "comum", dano: 250, area: 3.8, danoTorre: 0.4,
    texto: "Muitas flechas numa área grande. Acaba com tropas fracas." },
  relampago: { nome: "Relâmpago", custo: 2, tipo: "magia", raridade: "comum", dano: 175, area: 2.3, danoTorre: 0.4, atordoa: 0.6, instante: true,
    texto: "Cai do céu na hora: dano rápido e deixa todo mundo tonto por um instante." },
  gelo: { nome: "Gelo", custo: 4, tipo: "magia", raridade: "epico", dano: 95, area: 3.0, danoTorre: 0.4, congela: 4, instante: true,
    texto: "Congela tropas e torres inimigas por 4 segundos." },
  cura: { nome: "Poção de Cura", custo: 3, tipo: "magia", raridade: "raro", cura: 520, area: 3.0, instante: true,
    texto: "Cura as suas tropas que estiverem na área." },
  paladino: { nome: "Paladino", custo: 4, tipo: "tropa", raridade: "epico", n: 1, hp: 1650, dano: 230, cad: 1.4, vel: 1.0, alc: 0.6, raio: 0.55, visao: 5.5, massa: 8,
    investida: { dist: 2.5, vel: 2.1, mult: 2 },
    texto: "Depois de andar um pouco sem lutar, dispara numa investida: o primeiro golpe tira o dobro." },
  mago_gelo: { nome: "Mago de Gelo", custo: 3, tipo: "tropa", raridade: "raro", n: 1, hp: 620, dano: 80, cad: 1.5, vel: 1.0, alc: 5, raio: 0.45, visao: 5.5, ar: true, proj: "geada", area: 1.2, lento: 2.5, massa: 4,
    texto: "Atira gelo de longe numa área pequena: quem é atingido anda e ataca mais devagar." },
  assassino: { nome: "Assassino", custo: 4, tipo: "tropa", raridade: "epico", n: 1, hp: 900, dano: 150, cad: 0.9, vel: 1.45, alc: 0.5, raio: 0.42, visao: 6.5, massa: 4,
    salto: { min: 2.6, max: 6.5, mult: 2.2, dur: 0.55, espera: 5 },
    texto: "Salta de longe em cima do alvo, até por cima do rio, e o golpe da aterrissagem tira o dobro. No ar ninguém acerta." },
  balao: { nome: "Balão", custo: 5, tipo: "tropa", raridade: "epico", n: 1, hp: 1400, dano: 600, cad: 2.2, vel: 1.0, alc: 0.3, raio: 0.6, visao: 7, voa: true, soPredio: true, bomba: 1.3, massa: 5,
    morte: { dano: 240, area: 2.0 },
    texto: "Voa direto nas construções e solta bombas pesadas. Quando cai, a última bomba explode no chão." },
  quartel: { nome: "Quartel", custo: 5, tipo: "predio", raridade: "raro", n: 1, hp: 1200, dano: 0, cad: 1, vel: 0, alc: 0, raio: 0.95, visao: 0, vida: 40, massa: 999, semAtaque: true,
    invoca: { carta: "bandidos", n: 1, cada: 4.5, frente: 1.4 }, morteInvoca: { carta: "bandidos", n: 2 },
    texto: "Treina um bandido a cada 4,5 segundos durante 40 segundos. Quando cai, saem mais dois." },
  mina: { nome: "Mina de Energia", custo: 5, tipo: "predio", raridade: "raro", n: 1, hp: 950, dano: 0, cad: 1, vel: 0, alc: 0, raio: 0.85, visao: 0, vida: 64, massa: 999, semAtaque: true,
    gera: { energia: 1, cada: 8 },
    texto: "Cava 1 de energia a cada 8 segundos enquanto estiver de pé. Dura 64 segundos." },
  torre_arq: { nome: "Torre de Arqueiros", custo: 4, tipo: "predio", raridade: "raro", n: 1, hp: 1150, dano: 90, cad: 0.75, vel: 0, alc: 6.5, raio: 0.75, visao: 6.5, ar: true, proj: "flecha", alto: true, vida: 35, massa: 999,
    texto: "Torre de defesa com flechas rápidas, inclusive em quem voa. Dura 35 segundos." },
  veneno: { nome: "Veneno", custo: 4, tipo: "magia", raridade: "epico", dano: 70, area: 3.2, danoTorre: 0.3, instante: true, zona: { dur: 8, cada: 0.5, lento: true },
    texto: "Nuvem venenosa por 8 segundos: tira vida de tudo o que fica dentro e deixa mais lento." },
  furia: { nome: "Fúria", custo: 2, tipo: "magia", raridade: "epico", area: 3.0, instante: true, zona: { dur: 6, cada: 0.25, furia: true },
    texto: "Por 6 segundos, as suas tropas dentro da área andam e atacam 40% mais rápido." },
  // ---------- leva 3: bichos, dinossauros, construções e magias novas
  barbaros: { nome: "Bárbaros", custo: 5, tipo: "tropa", raridade: "comum", n: 4, modelo: "barbaro", hp: 640, dano: 150, cad: 1.4, vel: 1.0, alc: 0.5, raio: 0.45, visao: 5.5, massa: 5,
    texto: "Quatro bárbaros de machado. Muita vida e golpe forte, mas lentos." },
  cacadora: { nome: "Caçadora", custo: 4, tipo: "tropa", raridade: "raro", n: 1, hp: 620, dano: 210, cad: 1.7, vel: 1.0, alc: 6.5, raio: 0.42, visao: 7, ar: true, proj: "virote", massa: 4,
    texto: "Atira mais longe que qualquer tropa, em quem anda e em quem voa." },
  lobos: { nome: "Lobos", custo: 3, tipo: "tropa", raridade: "comum", n: 3, modelo: "lobo", hp: 340, dano: 95, cad: 0.9, vel: 2.0, alc: 0.5, raio: 0.42, visao: 6, massa: 3,
    texto: "Três lobos muito rápidos. Chegam primeiro e mordem sem parar." },
  touro: { nome: "Touro Bravo", custo: 4, tipo: "tropa", raridade: "raro", n: 1, hp: 1500, dano: 240, cad: 1.6, vel: 1.9, alc: 0.5, raio: 0.6, visao: 7, soPredio: true, pulaRio: true, massa: 10,
    texto: "Corre direto nas construções e pula o rio em qualquer lugar, sem precisar da ponte." },
  aranhas: { nome: "Aranhas", custo: 3, tipo: "tropa", raridade: "comum", n: 4, modelo: "aranha", hp: 170, dano: 60, cad: 1.0, vel: 1.5, alc: 0.5, raio: 0.36, visao: 5.5, lentoGolpe: 1.4, massa: 2,
    texto: "Quatro aranhas. A picada deixa o inimigo lento por um instante." },
  vespas: { nome: "Vespas", custo: 3, tipo: "tropa", raridade: "raro", n: 3, modelo: "vespa", hp: 190, dano: 85, cad: 1.0, vel: 1.7, alc: 1.2, raio: 0.36, visao: 6, voa: true, ar: true, massa: 1,
    texto: "Três vespas voando. Ferroam quem anda e quem voa." },
  raptores: { nome: "Raptores", custo: 4, tipo: "tropa", raridade: "raro", n: 2, modelo: "raptor", hp: 520, dano: 135, cad: 0.8, vel: 1.9, alc: 0.5, raio: 0.45, visao: 6.5, massa: 4,
    salto: { min: 2, max: 4.5, mult: 1.6, dur: 0.42, espera: 4 },
    texto: "Dois raptores rápidos que dão um bote em quem estiver perto." },
  rex: { nome: "Tiranossauro", custo: 7, tipo: "tropa", raridade: "epico", n: 1, hp: 4000, dano: 330, cad: 1.8, vel: 0.75, alc: 0.8, raio: 1.0, visao: 6, area: 1.1, massa: 25,
    texto: "Enorme. Cada mordida pega todo mundo em volta do alvo." },
  triceratops: { nome: "Tricerátops", custo: 5, tipo: "tropa", raridade: "epico", n: 1, hp: 2300, dano: 250, cad: 1.5, vel: 1.0, alc: 0.6, raio: 0.75, visao: 6, massa: 16,
    investida: { dist: 2.5, vel: 2.0, mult: 2 }, empurra: 1.6,
    texto: "Dispara numa investida e joga as tropas longe com os chifres." },
  espiritos: { nome: "Espíritos de Fogo", custo: 2, tipo: "tropa", raridade: "comum", n: 3, modelo: "espirito", hp: 90, dano: 160, cad: 1.0, vel: 2.2, alc: 0.6, raio: 0.32, visao: 6, ar: true, area: 1.4, kamikaze: true, massa: 1,
    texto: "Três chamas que correm e explodem em quem encostar." },
  canhao: { nome: "Canhão", custo: 3, tipo: "predio", raridade: "comum", n: 1, hp: 850, dano: 170, cad: 1.0, vel: 0, alc: 5.5, raio: 0.7, visao: 5.5, proj: "bala", vida: 30, massa: 999,
    texto: "Defesa barata com tiros fortes em quem anda (não acerta quem voa). Dura 30 segundos." },
  estabulo: { nome: "Estábulo", custo: 5, tipo: "predio", raridade: "raro", n: 1, hp: 1100, dano: 0, cad: 1, vel: 0, alc: 0, raio: 1.0, visao: 0, vida: 45, massa: 999, semAtaque: true,
    invoca: { carta: "lobos", n: 1, cada: 5, frente: 1.4 },
    texto: "Solta um lobo a cada 5 segundos durante 45 segundos." },
  poco: { nome: "Poço Mágico", custo: 4, tipo: "predio", raridade: "raro", n: 1, hp: 900, dano: 0, cad: 1, vel: 0, alc: 0, raio: 0.8, visao: 0, vida: 40, massa: 999, semAtaque: true,
    aura: { cura: 55, raio: 3.5, cada: 0.5 },
    texto: "Cura as suas tropas em volta dele, sem parar, durante 40 segundos." },
  tornado: { nome: "Tornado", custo: 3, tipo: "magia", raridade: "epico", dano: 45, area: 3.2, danoTorre: 0.3, instante: true, zona: { dur: 2.6, cada: 0.05, puxa: 2.8 },
    texto: "Puxa as tropas inimigas para o meio por 2,6 segundos (e tira um pouco de vida)." },
  terremoto: { nome: "Terremoto", custo: 3, tipo: "magia", raridade: "raro", dano: 65, area: 3.2, danoTorre: 2.8, danoPredio: 4, instante: true, zona: { dur: 3, cada: 0.5, lento: true },
    texto: "Treme o chão por 3 segundos: estraga muito as construções e deixa as tropas lentas." },
  cemiterio: { nome: "Cemitério", custo: 5, tipo: "magia", raridade: "epico", area: 3.0, instante: true, zona: { dur: 9, cada: 0.55, invoca: "esqueletos" },
    texto: "Por 9 segundos, esqueletos saem da terra em qualquer lugar da área." },
  escudo: { nome: "Escudo", custo: 2, tipo: "magia", raridade: "raro", area: 3.0, escudo: 260, instante: true,
    texto: "As suas tropas na área ganham um escudo que segura 260 de dano." },
  meteoro: { nome: "Meteoro", custo: 5, tipo: "magia", raridade: "epico", dano: 900, area: 2.6, danoTorre: 0.35, meteoro: 2.0,
    texto: "Cai do céu 2 segundos depois: o maior estrago de todos (avisa onde vai cair)." },
  barril: { nome: "Barril de Bandidos", custo: 3, tipo: "magia", raridade: "comum", dano: 80, area: 1.5, danoTorre: 1, solta: { carta: "bandidos", n: 3 },
    texto: "Arremessa um barril em qualquer lugar da arena: ele quebra e saem três bandidos." },
  exercito: { nome: "Exército de Esqueletos", custo: 3, tipo: "tropa", raridade: "epico", n: 12, modelo: "esqueleto", hp: 75, dano: 70, cad: 1.0, vel: 1.4, alc: 0.5, raio: 0.32, visao: 5.5, massa: 1,
    texto: "Doze esqueletos de uma vez. Cercam e derrubam qualquer tropa sozinha." },
};
// raridades: cor da moldura, cópias e ouro para subir de nível (do nível 1 para o 2, do 2 para o 3...)
export const RARIDADES = {
  comum: { nome: "Comum", copias: [2, 4, 10, 20, 50, 100, 200, 400, 800], ouro: [5, 20, 50, 150, 400, 1000, 2000, 4000, 8000] },
  raro: { nome: "Rara", copias: [2, 4, 10, 20, 50, 100, 150, 200, 300], ouro: [50, 150, 400, 1000, 2000, 4000, 8000, 12000, 16000] },
  epico: { nome: "Épica", copias: [2, 4, 8, 12, 20, 30, 40, 60, 80], ouro: [400, 1000, 2000, 4000, 8000, 12000, 16000, 20000, 30000] },
};
export const NIVEL_MAX = 10;
// cada nível a mais: +10% de vida e de dano (torres: +8% por nível do rei)
export const fatorNivel = (n) => Math.pow(1.1, Math.max(1, Math.min(NIVEL_MAX, n | 0 || 1)) - 1);
export const fatorRei = (n) => Math.pow(1.08, Math.max(1, Math.min(NIVEL_MAX, n | 0 || 1)) - 1);
// onde nasce cada boneco de uma carta (em volta do ponto, "para a frente" = dir)
export function lugaresDe(n, dir = 1) {
  if (n === 1) return [[0, 0]];
  if (n === 2) return [[-0.55, 0], [0.55, 0]];
  if (n === 3) return [[0, 0.5 * dir], [-0.6, -0.35 * dir], [0.6, -0.35 * dir]];
  const r = [];
  const dentro = Math.min(4, n), fora = n - dentro;
  for (let k = 0; k < dentro; k++) { const a = 2 * Math.PI * k / dentro + 0.4; r.push([0.62 * Math.cos(a), 0.62 * Math.sin(a)]); }
  for (let k = 0; k < fora; k++) { const a = 2 * Math.PI * k / fora; r.push([1.35 * Math.cos(a), 1.25 * Math.sin(a)]); }
  return r;
}
export const BARALHO = ["cavaleiro", "besteiros", "gigante", "mago", "bandidos", "dragao", "catapulta", "bola_fogo"];
export const TODAS = ["cavaleiro", "besteiros", "gigante", "mago", "bandidos", "dragao", "catapulta", "bola_fogo", "esqueletos", "guerreiro", "necromante", "flechas",
  "relampago", "gelo", "cura", "exercito", "paladino", "mago_gelo", "assassino", "balao", "quartel", "mina", "torre_arq", "veneno", "furia",
  "barbaros", "cacadora", "lobos", "touro", "aranhas", "vespas", "raptores", "rex", "triceratops", "espiritos", "canhao", "estabulo", "poco", "tornado", "terremoto", "cemiterio", "escudo", "meteoro", "barril"];
// um baralho válido tem 8 cartas diferentes que existem; se não, usa o padrão
export function baralhoValido(b) {
  return Array.isArray(b) && b.length === 8 && new Set(b).size === 8 && b.every(k => CARTAS[k]) ? b.slice() : BARALHO.slice();
}
const TORRE = { hp: 2600, dano: 105, cad: 0.8, alc: 7.5, raio: 1.3, ar: true, proj: "flecha", massa: 999 };
const REI = { hp: 4200, dano: 105, cad: 1.0, alc: 7.0, raio: 1.85, ar: true, proj: "flecha", massa: 999 };
const VEL_PROJ = { flecha: 14, magia: 10, fogo: 9, virote: 16, pedra: 12, sombra: 10, geada: 11, bala: 15 };
const LENTO = 0.65, FURIA = 1.4;                            // lento: anda e ataca a 65%; fúria: 140%
// fora do jogo agora: morto, nascendo ou no meio do salto (ninguém mira nem acerta)
const fora = (o) => o.hp <= 0 || o.tn > 0 || !!o.pulo;
const T_NASCER = 1.0;

// gerador de números da partida (a mesma semente dá o mesmo embaralhamento)
function rng(s) {
  return () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

// niveis: [{carta: nível}, {carta: nível}] · reis: [nível do rei de cada lado] (vida e dano das torres)
export function criarPartida(semente = 1, baralhos = [BARALHO, BARALHO], niveis = [{}, {}], reis = [1, 1]) {
  const r = rng(semente);
  const s = { tk: 0, tempo: T_PARTIDA, fase: "jogo", venc: -1, coroas: [0, 0], energia: [5, 5], ent: [], proj: [], ev: [], prox: 1, r,
    maos: [[], []], filas: [[], []], reiAtivo: [false, false], niv: [niveis[0] || {}, niveis[1] || {}], reis: reis.slice(), cache: [{}, {}], zonas: [] };
  for (const lado of [0, 1]) {
    const b = baralhoValido(baralhos[lado]);
    for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; }
    s.maos[lado] = b.slice(0, 4);
    s.filas[lado] = b.slice(4);
    const y = (v) => lado === 0 ? v : C - v;
    for (const [k, x, yy] of [["torre", 3.5, 6.5], ["torre", 14.5, 6.5], ["rei", 9, 3]]) {
      const f = fatorRei(s.reis[lado]), b0 = k === "rei" ? REI : TORRE;
      const c = { ...b0, hp: Math.round(b0.hp * f), dano: Math.round(b0.dano * f) };
      s.ent.push({ id: s.prox++, k, lado, x, y: y(yy), hp: c.hp, hpMax: c.hp, cd: 0, alvo: 0, est: 1, tn: 0, a: lado === 0 ? 0 : Math.PI, predio: true, fixa: true, c });
    }
  }
  return s;
}

export function dadosDe(e) { return e.c; }
// a carta com o nível de quem jogou (vida, dano e cura sobem 10% por nível)
export function dados(s, lado, k) {
  const ch = s.cache[lado];
  if (ch[k]) return ch[k];
  const c = CARTAS[k], f = fatorNivel(s.niv[lado][k] || 1), d = { ...c };
  if (c.hp) d.hp = Math.round(c.hp * f);
  if (c.dano) d.dano = Math.round(c.dano * f);
  if (c.cura) d.cura = Math.round(c.cura * f);
  return (ch[k] = d);
}

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
  if (c.tipo === "magia" && c.instante) { magia(s, lado, carta, x, y); return true; }
  if (c.meteoro) {                                          // meteoro: cai do céu depois de um tempo (a marca avisa onde)
    const d = dados(s, lado, carta);
    s.proj.push({ id: s.prox++, tipo: "queda", lado, x, y, tx: x, ty: y, t: 0, dur: c.meteoro, dano: d.dano, area: c.area, ar: true, torre: c.danoTorre, carta });
    s.ev.push(["magia", lado, x, y]); s.ev.push(["aviso", x, y, c.area, c.meteoro]);
    return true;
  }
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

// magia que acontece na hora (relâmpago, gelo, cura)
function magia(s, lado, carta, x, y) {
  const c = dados(s, lado, carta);
  if (c.escudo) {                                           // escudo: segura dano antes da vida
    for (const o of s.ent) if (o.lado === lado && !o.fixa && o.hp > 0 && Math.hypot(o.x - x, o.y - y) <= c.area + o.c.raio * 0.6) { o.escudo = c.escudo; o.tEscudo = 10; s.ev.push(["escudo", o.id]); }
    s.ev.push(["magia", lado, x, y]); s.ev.push(["explode", x, y, c.area, "escudo"]);
    return;
  }
  if (c.zona) {                                             // veneno, fúria, tornado, terremoto e cemitério: áreas que ficam um tempo
    s.zonas.push({ id: s.prox++, k: carta, lado, x, y, area: c.area, t: c.zona.dur, tick: 0, cada: c.zona.cada, dano: c.dano || 0, danoTorre: c.danoTorre || 1,
      danoPredio: c.danoPredio || 1, lento: !!c.zona.lento, furia: !!c.zona.furia, puxa: c.zona.puxa || 0, invoca: c.zona.invoca || null });
    s.ev.push(["magia", lado, x, y]); s.ev.push(["zona", carta, x, y, c.area]);
    return;
  }
  if (c.cura) {
    for (const o of s.ent) if (o.lado === lado && !o.fixa && o.hp > 0 && Math.hypot(o.x - x, o.y - y) <= c.area + o.c.raio * 0.6) { o.hp = Math.min(o.hpMax, o.hp + c.cura); s.ev.push(["curou", o.id]); }
  } else {
    for (const o of s.ent) {
      if (o.lado === lado || fora(o)) continue;
      if (Math.hypot(o.x - x, o.y - y) > c.area + o.c.raio * 0.6) continue;
      dano(s, o, o.fixa ? c.dano * c.danoTorre : c.dano);
      if (c.atordoa) { o.para = Math.max(o.para || 0, c.atordoa); o.gelo = false; o.cd = Math.max(o.cd, o.c.cad * 0.5); }
      if (c.congela) { o.para = Math.max(o.para || 0, c.congela); o.gelo = true; }
    }
  }
  s.ev.push(["magia", lado, x, y]);
  s.ev.push(["explode", x, y, c.area, carta]);
}

function nascer(s, carta, lado, x, y, n) {
  const c = dados(s, lado, carta), dir = lado === 0 ? 1 : -1;
  for (const [dx, dy] of lugaresDe(n, dir)) {
    const e = { id: s.prox++, k: carta, lado, x: Math.min(L - 0.4, Math.max(0.4, x + dx)), y: Math.min(C - 0.4, Math.max(0.4, y + dy)), hp: c.hp, hpMax: c.hp, cd: 0, alvo: 0, est: 0,
      tn: T_NASCER, a: lado === 0 ? 0 : Math.PI, predio: c.tipo === "predio", fixa: false, c, vida: c.vida || 0, inv: c.invoca ? c.invoca.cada * 0.5 : 0, para: 0, gelo: false,
      ger: c.gera ? c.gera.cada : 0, lento: 0, furia: 0, corrida: 0, investe: false, pulo: null, esperaSalto: 0 };
    s.ent.push(e);
    s.ev.push(["nasce", e.id]);
  }
}

const ladoDoRio = (y) => y < RIO0 ? 0 : y > RIO1 ? 1 : -1;
const pontePerto = (x) => Math.abs(x - PONTES[0]) < Math.abs(x - PONTES[1]) ? PONTES[0] : PONTES[1];

// para onde andar agora para chegar em (tx, ty): quem anda no chão tem de passar por uma ponte
function rumo(e, tx, ty) {
  if (e.c.voa || e.c.pulaRio) return [tx, ty];
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

function dano(s, alvo, v, autor, aos = false) {
  if (alvo.hp <= 0) return;
  if (alvo.escudo > 0) { const seg = Math.min(alvo.escudo, v); alvo.escudo -= seg; v -= seg; if (alvo.escudo <= 0) s.ev.push(["quebraEscudo", alvo.id]); if (v <= 0) { s.ev.push(["dano", alvo.id, 0, "e"]); return; } }
  alvo.hp -= v;
  if (alvo.k === "rei") s.reiAtivo[alvo.lado] = true;
  s.ev.push(aos ? ["dano", alvo.id, Math.round(v), "z"] : ["dano", alvo.id, Math.round(v)]);   // "z": aos poucos (veneno), pisca de leve
}

function danoArea(s, lado, x, y, raio, v, ar, fatorTorre = 1, lento = 0) {
  for (const o of s.ent) {
    if (o.lado === lado || fora(o)) continue;
    if (o.c.voa && !ar) continue;
    if (Math.hypot(o.x - x, o.y - y) > raio + o.c.raio * 0.6) continue;
    dano(s, o, o.fixa ? v * fatorTorre : v);
    if (lento) o.lento = Math.max(o.lento || 0, lento);
  }
}

function escolherAlvo(s, e) {
  const c = e.c;
  let melhor = null, dm = 1e9;
  // 1) uma tropa inimiga à vista (quem só ataca construção pula esta parte)
  if (!c.soPredio) {
    for (const o of s.ent) {
      if (o.lado === e.lado || fora(o) || o.predio) continue;
      if (o.c.voa && !c.ar) continue;
      const d = Math.hypot(o.x - e.x, o.y - e.y) - o.c.raio - c.raio;
      if (d <= (e.fixa || e.predio ? c.alc : c.visao) && d < dm) { dm = d; melhor = o; }
    }
    if (melhor) return melhor;
  }
  if (e.fixa || e.predio) {                                 // torre e catapulta também atiram em construção ao alcance
    for (const o of s.ent) {
      if (o.lado === e.lado || fora(o) || !o.predio || o.fixa) continue;
      const d = Math.hypot(o.x - e.x, o.y - e.y) - o.c.raio - c.raio;
      if (d <= c.alc && d < dm) { dm = d; melhor = o; }
    }
    return melhor;
  }
  // 2) a construção inimiga mais perto (pelo caminho de verdade: passando pela ponte)
  for (const o of s.ent) {
    if (o.lado === e.lado || fora(o) || !o.predio) continue;
    let d = Math.hypot(o.x - e.x, o.y - e.y);
    if (!c.voa && !c.pulaRio && ladoDoRio(o.y) !== ladoDoRio(e.y) && ladoDoRio(e.y) !== -1) {
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

  // zonas (veneno e fúria): de tempos em tempos pegam quem está dentro
  for (const z of s.zonas) {
    z.t -= DT; z.tick -= DT;
    if (z.tick > 0) continue;
    z.tick += z.cada;
    if (z.invoca) {                                         // cemitério: um esqueleto num ponto qualquer da área
      const a = s.r() * Math.PI * 2, d = Math.sqrt(s.r()) * z.area * 0.9;
      nascer(s, z.invoca, z.lado, Math.min(L - 0.5, Math.max(0.5, z.x + Math.cos(a) * d)), Math.min(C - 0.5, Math.max(0.5, z.y + Math.sin(a) * d)), 1);
      continue;
    }
    for (const o of s.ent) {
      if (fora(o) || Math.hypot(o.x - z.x, o.y - z.y) > z.area + o.c.raio * 0.6) continue;
      if (z.furia) { if (o.lado === z.lado && !o.fixa) o.furia = Math.max(o.furia || 0, z.cada + 0.8); }
      else if (o.lado !== z.lado) {
        const f = o.fixa ? z.danoTorre : o.predio ? z.danoPredio : 1;
        if (z.dano) dano(s, o, z.dano * f * z.cada, null, true);
        if (z.lento && !o.fixa) o.lento = Math.max(o.lento || 0, z.cada + 0.3);
        if (z.puxa && !o.predio) {                          // tornado: puxa para o meio
          const dx = z.x - o.x, dy = z.y - o.y, d = Math.hypot(dx, dy);
          if (d > 0.25) { const v = Math.min(d, z.puxa * z.cada * Math.min(1.6, 6 / Math.max(3, o.c.massa))); o.x += dx / d * v; o.y += dy / d * v; }
        }
      }
    }
  }
  s.zonas = s.zonas.filter(z => z.t > 0);

  for (const e of s.ent) {
    if (e.hp <= 0) continue;
    if (e.tn > 0) { e.tn -= DT; if (e.tn <= 0) e.est = 1; continue; }
    const c = e.c;
    if (e.vida) { e.vida -= DT; e.hp -= e.hpMax * DT / c.vida; if (e.hp <= 0) continue; }
    if (e.pulo) {                                           // assassino no ar: vai até o alvo e cai com o golpe forte
      const p = e.pulo, alvo = porId.get(p.alvo);
      p.t += DT;
      if (alvo && alvo.hp > 0) { const ux = alvo.x - p.x0, uy = alvo.y - p.y0, n = Math.hypot(ux, uy) || 1, r = alvo.c.raio + c.raio; p.tx = alvo.x - ux / n * r; p.ty = alvo.y - uy / n * r; }
      const q = Math.min(1, p.t / c.salto.dur);
      e.x = p.x0 + (p.tx - p.x0) * q; e.y = p.y0 + (p.ty - p.y0) * q;
      if (q >= 1) {
        e.pulo = null; e.esperaSalto = c.salto.espera; e.cd = c.cad; e.est = 2;
        if (alvo && alvo.hp > 0) dano(s, alvo, c.dano * c.salto.mult, e);
        s.ev.push(["pouso", e.id]);
      }
      continue;
    }
    if (e.para > 0) { e.para -= DT; e.investe = false; e.corrida = 0; if (e.para <= 0) { e.para = 0; e.gelo = false; } continue; }
    if (e.lento > 0) e.lento -= DT;
    if (e.furia > 0) e.furia -= DT;
    if (e.tEscudo > 0) { e.tEscudo -= DT; if (e.tEscudo <= 0) e.escudo = 0; }
    if (c.aura) {                                           // poço mágico: cura quem é do time em volta
      e.tAura = (e.tAura || 0) - DT;
      if (e.tAura <= 0) {
        e.tAura = c.aura.cada;
        for (const o of s.ent) if (o.lado === e.lado && !o.predio && o.hp > 0 && o.hp < o.hpMax && Math.hypot(o.x - e.x, o.y - e.y) <= c.aura.raio) { o.hp = Math.min(o.hpMax, o.hp + c.aura.cura * c.aura.cada); s.ev.push(["curou", o.id]); }
      }
    }
    if (e.esperaSalto > 0) e.esperaSalto -= DT;
    const rit = (e.lento > 0 ? LENTO : 1) * (e.furia > 0 ? FURIA : 1);   // ritmo: anda e ataca mais devagar ou mais rápido
    e.cd = Math.max(0, e.cd - DT * rit);
    if (c.invoca) {                                         // o necromante chama esqueletos de tempos em tempos (o quartel, bandidos)
      e.inv -= DT;
      if (e.inv <= 0) {
        e.inv = c.invoca.cada;
        const dy = c.invoca.frente ? (e.lado === 0 ? 1 : -1) * c.invoca.frente : (e.lado === 0 ? -0.9 : 0.9);
        nascer(s, c.invoca.carta, e.lado, e.x, e.y + dy, c.invoca.n);
        s.ev.push(["invoca", e.id]);
      }
    }
    if (c.gera) {                                           // a mina cava energia
      e.ger -= DT;
      if (e.ger <= 0) { e.ger += c.gera.cada; s.energia[e.lado] = Math.min(ENERGIA_MAX, s.energia[e.lado] + c.gera.energia); s.ev.push(["gera", e.id, e.lado]); }
    }
    if (c.semAtaque) { e.est = 1; continue; }
    if (e.k === "rei" && !s.reiAtivo[e.lado]) continue;     // o rei só acorda quando apanha ou perde uma torre
    // alvo: mantém o atual se ainda vale; senão procura outro
    let alvo = porId.get(e.alvo);
    if (alvo && fora(alvo)) alvo = null;
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
    // assassino: alvo a uma boa distância (e no chão) → salta em cima dele
    if (c.salto && e.esperaSalto <= 0 && !alvo.c.voa && d >= c.salto.min && d <= c.salto.max) {
      e.pulo = { t: 0, x0: e.x, y0: e.y, tx: alvo.x, ty: alvo.y, alvo: alvo.id };
      e.a = Math.atan2(dx, dy); e.est = 1;
      s.ev.push(["salto", e.id]);
      continue;
    }
    if (d <= c.alc) {                                       // ao alcance: bate
      if (e.est !== 2) { e.est = 2; e.cd = Math.max(e.cd, e.investe ? 0.12 : c.cad * 0.45); }
      e.a = Math.atan2(dx, dy);
      if (e.cd <= 0) {
        e.cd = c.cad;
        s.ev.push(["atq", e.id]);
        let v = c.dano;
        if (c.investida) { if (e.investe) { v *= c.investida.mult; s.ev.push(["golpeForte", e.id]); } e.investe = false; e.corrida = 0; }
        if (c.bomba) {                                      // o balão solta a bomba: cai em meio segundo
          s.proj.push({ id: s.prox++, tipo: "queda", lado: e.lado, x: alvo.x, y: alvo.y, tx: alvo.x, ty: alvo.y, t: 0, dur: 0.45, dano: v, area: c.bomba, ar: false });
        } else if (c.proj) {
          s.proj.push({ id: s.prox++, tipo: c.proj, lado: e.lado, x: e.x, y: e.y, alvo: alvo.id, tx: alvo.x, ty: alvo.y, dano: v, area: c.area || 0, ar: !!c.ar,
            alto: e.fixa || c.alto ? 1 : 0, voaAlvo: !!alvo.c.voa, lento: c.lento || 0 });
        } else if (c.giro) { danoArea(s, e.lado, e.x, e.y, c.giro + c.raio, v, !!c.ar); s.ev.push(["giro", e.id]); }
        else if (c.area) danoArea(s, e.lado, alvo.x, alvo.y, c.area, v, !!c.ar);
        else dano(s, alvo, v, e);
        if (c.kamikaze) { e.hp = 0; s.ev.push(["explode", e.x, e.y, c.area, "fogo"]); }   // espírito de fogo: explode junto
        if (c.lentoGolpe && !alvo.fixa) alvo.lento = Math.max(alvo.lento || 0, c.lentoGolpe);
        if (c.empurra && !alvo.predio && alvo.hp > 0 && alvo.c.massa < c.massa) {          // chifrada: joga a tropa para trás
          const d = Math.hypot(dx, dy) || 1, f = c.empurra * (v > c.dano ? 1.5 : 1);
          alvo.x = Math.min(L - 0.4, Math.max(0.4, alvo.x + dx / d * f)); alvo.y = Math.min(C - 0.4, Math.max(0.4, alvo.y + dy / d * f));
          s.ev.push(["empurrao", alvo.id]);
        }
      }
    } else if (!e.predio) {                                 // longe: anda
      e.est = 1;
      const [rx, ry] = rumo(e, alvo.x, alvo.y);
      const vx = rx - e.x, vy = ry - e.y, n = Math.hypot(vx, vy) || 1;
      const vel = (c.investida && e.investe ? c.investida.vel : c.vel) * rit;
      const andar = Math.min(vel * DT, n);
      e.x += vx / n * andar; e.y += vy / n * andar;
      e.a = Math.atan2(vx, vy);
      if (c.investida && !e.investe) {                      // paladino: depois de andar um tanto, dispara
        e.corrida += andar;
        if (e.corrida >= c.investida.dist) { e.investe = true; s.ev.push(["investida", e.id]); }
      }
    } else e.est = 1;
  }

  // ninguém fica em cima de ninguém; tropa no chão não entra na torre nem no rio
  const moveis = s.ent.filter(e => !e.predio && e.hp > 0 && e.tn <= 0 && !e.pulo);
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
      if (e.y > RIO0 && e.y < RIO1 && !e.c.pulaRio) {
        const bx = pontePerto(e.x);
        if (Math.abs(e.x - bx) <= MEIA_PONTE + 0.6) e.x = Math.min(bx + MEIA_PONTE - 0.25, Math.max(bx - MEIA_PONTE + 0.25, e.x));
        else e.y = e.y < 16 ? RIO0 : RIO1;
      }
    }
    e.x = Math.min(L - 0.35, Math.max(0.35, e.x)); e.y = Math.min(C - 0.35, Math.max(0.35, e.y));
  }

  // projéteis
  for (const p of s.proj) {
    if (p.tipo === "queda") {                               // bomba do balão caindo
      p.t += DT;
      if (p.t >= p.dur) { danoArea(s, p.lado, p.tx, p.ty, p.area, p.dano, p.ar, p.torre ?? 1); s.ev.push(["explode", p.tx, p.ty, p.area, p.carta === "meteoro" ? "meteoro" : "queda"]); p.fim = true; }
      continue;
    }
    if (p.tipo === "bola") {
      p.t += DT;
      const q = Math.min(1, p.t / p.dur);
      p.x = p.x0 + (p.tx - p.x0) * q; p.y = p.y0 + (p.ty - p.y0) * q;
      if (q >= 1) {
        const c = dados(s, p.lado, p.carta);
        danoArea(s, p.lado, p.tx, p.ty, c.area, c.dano, true, c.danoTorre);
        if (c.solta) nascer(s, c.solta.carta, p.lado, p.tx, p.ty, c.solta.n);          // barril: saem os bandidos
        s.ev.push(["explode", p.tx, p.ty, c.area, p.carta === "flechas" ? "flechas" : p.carta === "barril" ? "barril" : undefined]);
        p.fim = true;
      }
      continue;
    }
    const alvo = porId.get(p.alvo);
    if (alvo && alvo.hp > 0) { p.tx = alvo.x; p.ty = alvo.y; }
    const dx = p.tx - p.x, dy = p.ty - p.y, d = Math.hypot(dx, dy), v = VEL_PROJ[p.tipo] * DT;
    if (d <= v + 0.2) {
      if (p.area) { danoArea(s, p.lado, p.tx, p.ty, p.area, p.dano, p.ar, 1, p.lento || 0); s.ev.push(["explode", p.tx, p.ty, p.area * 0.7, p.tipo]); }
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
    if (e.c.morte) {                                        // o balão caindo: a última bomba
      const f = CARTAS[e.k].dano ? e.c.dano / CARTAS[e.k].dano : 1;
      s.proj.push({ id: s.prox++, tipo: "queda", lado: e.lado, x: e.x, y: e.y, tx: e.x, ty: e.y, t: 0, dur: 0.9, dano: e.c.morte.dano * f, area: e.c.morte.area, ar: false });
    }
    if (e.c.morteInvoca) nascer(s, e.c.morteInvoca.carta, e.lado, e.x, e.y + (e.lado === 0 ? 1 : -1) * 1.1, e.c.morteInvoca.n);
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
      e.tn > 0 ? Math.round(e.tn * 100) / 100 : 0, e.para > 0 ? (e.gelo ? 2 : 1) : 0,
      (e.investe ? 1 : 0) | (e.lento > 0 ? 2 : 0) | (e.furia > 0 ? 4 : 0) | (e.pulo ? 8 : 0) | (e.escudo > 0 ? 16 : 0)]),
    proj: s.proj.map(p => p.tipo === "bola" || p.tipo === "queda" ? [p.id, p.tipo, Math.round(p.x * 100) / 100, Math.round(p.y * 100) / 100, Math.round(Math.min(1, p.t / p.dur) * 100) / 100, p.lado, p.carta,
      Math.round(p.tx * 100) / 100, Math.round(p.ty * 100) / 100]
      : [p.id, p.tipo, Math.round(p.x * 100) / 100, Math.round(p.y * 100) / 100, p.alto, p.lado, p.voaAlvo ? 1 : 0, Math.round(p.tx * 100) / 100, Math.round(p.ty * 100) / 100]),
    zonas: (s.zonas || []).map(z => [z.id, z.k, Math.round(z.x * 100) / 100, Math.round(z.y * 100) / 100, z.area, z.lado, Math.round(z.t * 10) / 10]),
    ev: ev || s.ev,
  };
  return f;
}
export { EST };
