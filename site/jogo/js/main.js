// O jogo em si: partidas, cartas na mão, energia, fim de partida e os três jeitos de jogar (contra o computador,
// criando uma sala ou entrando numa sala pelo link). Quem cria a sala roda as regras; o convidado só recebe as fotos
// do estado e manda as jogadas. O menu (lobby com abas, baús, loja...) fica em lobby.js.
import { Cena } from "./render.js";
import { CARTAS, C, DT, L, NIVEL_MAX, RIO0, baralhoValido, criarPartida, foto, jogar, passo, podeSoltar } from "./sim.js";
import { BARALHOS_BOT, criarBot, pensar } from "./bot.js";
import { ligar, novoCodigo } from "./rede.js";
import { iniciarMusica, ligarSom, pararMusica, tocar } from "./som.js";
import { ARENAS, BAUS, carta, mediaNivel, mudar, nivelRei, niveisDoBaralho, prog, registrar } from "./progresso.js";
import { abrirTelaBau, arenaDoMenu, arenaJogo, atualizarRecursos, aviso, classeCarta, depoisDaPartida, esconderLobby, fecharModais, fmt, htmlCarta, iniciarLobby, mostrarLobby, nomeEu, vibrar } from "./lobby.js";

const $ = (id) => document.getElementById(id);
const cena = new Cena($("tela"));
const P = new URLSearchParams(location.search);
const EMOJIS = ["👍", "😂", "😮", "😡", "👏"];
let modo = "demo";            // demo (fundo do menu) | bot | dono | convidado
let lado = 0, s = null, bots = [], rede = null, atual = null, sel = null, arrasto = null, acabou = false, rodando = false;
let acc = 0, ultimo = 0, evLocal = [], evRemoto = [], ultEnvio = 0, maoTexto = "", energiaTela = 5, nomeInimigo = "Computador", codigo = "";
let dele = { baralho: null, niveis: {}, rei: 1 }, posTorre = {}, tutorial = 0, jaJogou = false, reiInimigo = 1, nivMeus = {};

const mostrar = (id, sim = true) => { $(id).hidden = !sim; };
function coroas(el, n) { el.innerHTML = [0, 1, 2].map(i => `<i class="coroa${i < n ? " tem" : ""}"></i>`).join(""); }

// ------------------------------------------------------------------ começar e parar partidas
function hud(sim) {
  for (const id of ["topo", "mao", "botaoSair"]) mostrar(id, sim);
  mostrar("botaoEmote", sim); mostrar("emotes", false);
  $("palco").style.setProperty("--altMao", `${$("mao").offsetHeight || 180}px`);
  cena.margens = sim ? { cima: $("topo").offsetHeight / $("palco").offsetHeight + 0.02, baixo: $("mao").offsetHeight / $("palco").offsetHeight + 0.01 }
    : { cima: 0.13, baixo: 0.36 };
  cena.ajustar();
}

// níveis do computador: perto da média do seu baralho (fácil um a menos, difícil um a mais)
function niveisBot(baralho, nv) {
  const base = Math.round(mediaNivel()) + [-1, 0, 1][nv];
  return Object.fromEntries(baralho.map(k => [k, Math.max(1, Math.min(NIVEL_MAX, base))]));
}

function novaPartida(m, semente = (Math.random() * 1e9) | 0) {
  cena.demo = m === "demo";
  modo = m; acabou = false; sel = null; arrasto = null; maoTexto = ""; atual = null; evLocal = []; evRemoto = []; acc = 0; rodando = false; posTorre = {}; jaJogou = false;
  cena.limpar();
  cena.visao = lado = m === "convidado" ? 1 : 0;
  selecionar(null);
  if (m === "convidado") { s = null; bots = []; }
  else {
    const bot = () => BARALHOS_BOT[Math.floor(Math.random() * BARALHOS_BOT.length)];
    const meu = m === "demo" ? bot() : prog().baralho;
    const outro = m === "dono" ? baralhoValido(dele.baralho) : bot();
    const nv = prog().nivel;
    nivMeus = m === "demo" ? {} : niveisDoBaralho(meu);
    const nivDele = m === "dono" ? (dele.niveis || {}) : m === "bot" ? niveisBot(outro, nv) : {};
    const reiMeu = m === "demo" ? 1 : nivelRei();
    reiInimigo = m === "dono" ? (dele.rei | 0 || 1) : m === "bot" ? Math.max(1, Math.min(NIVEL_MAX, nivelRei() + [-1, 0, 1][nv])) : 1;
    s = criarPartida(semente, [meu, outro], [nivMeus, nivDele], [reiMeu, reiInimigo]);
    bots = m === "bot" ? [criarBot(1, nv)] : m === "demo" ? [criarBot(0), criarBot(1)] : [];
    desenhar(foto(s, 0, []));
  }
  $("relogio").classList.remove("pressa");
  mostrar("faixa", false); mostrar("dica", false);
}

function contagem(depois) {
  const c = $("contagem");
  let n = 3;
  const passoC = () => {
    if (n === 0) { c.hidden = true; tocar("comeca"); depois && depois(); return; }
    c.textContent = n; c.hidden = false; c.classList.remove("pulo"); void c.offsetWidth; c.classList.add("pulo");
    tocar("contagem"); n--; contagem.t = setTimeout(passoC, 800);
  };
  clearTimeout(contagem.t); passoC();
}

function comecar(m, semente, arena = arenaJogo()) {
  esconderLobby(); mostrar("fim", false); mostrar("sala", false); mostrar("fundoModal", false);
  cena.trocarCenario(arena);
  novaPartida(m, semente);
  hud(true);
  const reiEu = nivelRei();
  $("nomeEu").textContent = nomeEu(); $("nomeInimigo").textContent = nomeInimigo;
  $("reiEu").textContent = reiEu; $("reiInimigo").textContent = reiInimigo;
  $("vsNomeEu").textContent = nomeEu(); $("vsNomeEle").textContent = nomeInimigo;
  $("vsReiEu").textContent = reiEu; $("vsReiEle").textContent = reiInimigo;
  $("vsArena").textContent = ARENAS[arena] ? ARENAS[arena].nome : "";
  mostrar("vs"); tocar("vs");
  iniciarMusica(true);
  tutorial = m === "bot" && !prog().tutorial ? 1 : 0;
  clearTimeout(comecar.t);
  comecar.t = setTimeout(() => {
    mostrar("vs", false);
    contagem(() => {
      rodando = true; ultimo = performance.now(); acc = 0;
      if (tutorial === 1) dica("Toque numa carta e depois no seu lado da arena (ou arraste a carta até lá) 👇");
    });
  }, 1700);
}

function paraMenu() {
  clearTimeout(contagem.t); clearTimeout(comecar.t); mostrar("contagem", false); mostrar("vs", false);
  if (rede) { rede.fechar(); rede = null; }
  hud(false);
  mostrar("botaoEmote", false); mostrar("fim", false); mostrar("sala", false); mostrar("fundoModal", false);
  novaPartida("demo");
  rodando = true; ultimo = performance.now();
  const sala = P.get("sala");
  $("entrarSala").hidden = !sala;
  if (sala) $("entrarSala").textContent = `Entrar na sala ${sala.toUpperCase()}`;
  mostrarLobby();
  pararMusica(); iniciarMusica(false);
}

function dica(texto, ms = 0) {
  const d = $("dica"); d.textContent = texto; d.hidden = false;
  clearTimeout(dica.t); if (ms) dica.t = setTimeout(() => { d.hidden = true; }, ms);
}

// ------------------------------------------------------------------ o relógio das regras (20 passos por segundo)
setInterval(() => {
  if (!s || !rodando || modo === "convidado") return;
  const agora = performance.now();
  acc += Math.min(3, (agora - ultimo) / 1000); ultimo = agora;
  let n = 0;
  while (acc >= DT && n < 60) {
    for (const b of bots) pensar(b, s, DT);
    passo(s);
    acc -= DT; n++;
    if (s.ev.length) { evLocal.push(...s.ev); evRemoto.push(...s.ev); s.ev.length = 0; }
  }
  if (!n) return;
  desenhar(foto(s, 0, evLocal)); evLocal = [];
  if (modo === "dono" && rede && s.tk - ultEnvio >= 2) { rede.enviar({ t: "f", f: foto(s, 1, evRemoto) }); evRemoto = []; ultEnvio = s.tk; }
  if (modo === "demo" && s.fase === "fim") setTimeout(() => { if (modo === "demo") { novaPartida("demo"); rodando = true; ultimo = performance.now(); } }, 2500);
}, 25);

// ------------------------------------------------------------------ desenhar uma foto do estado: 3D + barra de cima + cartas
function desenhar(f) {
  atual = f;
  cena.aplicar(f);
  if (modo === "demo") return;
  for (const ev of f.ev || []) {
    if (ev[0] === "extra") { faixa("Tempo extra!"); tocar("extra"); }
    if (ev[0] === "fim" && !acabou) fimDePartida(ev[1]);
    if (ev[0] === "morte" && (ev[4] === "torre" || ev[4] === "rei")) posTorre[ev[1]] = [ev[2], ev[3]];
    if (ev[0] === "torre") torreCaiu(ev[1], ev[2]);
  }
  const eu = lado, ele = 1 - lado;
  coroas($("coroasEu"), f.coroas[eu]); coroas($("coroasInimigo"), f.coroas[ele]);
  const seg = f.tempo;
  $("tempo").textContent = `${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}`;
  $("avisoTempo").textContent = f.fase === "extra" ? "TEMPO EXTRA" : "";
  $("relogio").classList.toggle("pressa", f.fase === "extra" || seg <= 10);
  mostrar("dobro", !!f.dobro);
  if (f.fase === "jogo" && seg <= 10 && seg > 0 && seg !== desenhar.seg) { desenhar.seg = seg; tocar("tique"); }
  if (f.fase === "jogo" && seg === 60) { if (!desenhar.avisou) { desenhar.avisou = true; faixa("Energia em dobro!"); } } else if (seg > 60) desenhar.avisou = false;
  const texto = f.mao.join(",") + "|" + f.prox;
  if (texto !== maoTexto) { maoTexto = texto; montarMao(f); }
  for (const el of $("cartas").children) el.classList.toggle("cara", CARTAS[el.dataset.carta].custo > f.energia);
}

// uma torre caiu: a coroa sai voando de onde ela estava até o placar de quem derrubou
function torreCaiu(id, ladoDela) {
  const quem = 1 - ladoDela, pos = posTorre[id];
  vibrar(60);
  if (modo === "bot" && Math.random() < 0.6) setTimeout(() => cena.emote(1, quem === 1 ? "😂" : "😡"), 700);
  if (!pos) return;
  const de = cena.naTela(pos[0], pos[1], 3), alvo = $(quem === lado ? "coroasEu" : "coroasInimigo").getBoundingClientRect(), palco = $("palco").getBoundingClientRect();
  const c = document.createElement("i"); c.className = "coroaVoa";
  c.style.left = `${de.x - palco.left - 23}px`; c.style.top = `${de.y - palco.top - 19}px`; c.style.transform = "scale(1.8)";
  $("palco").appendChild(c);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    c.style.left = `${alvo.left - palco.left + alvo.width / 2 - 23}px`; c.style.top = `${alvo.top - palco.top - 8}px`; c.style.transform = "scale(0.6)";
  }));
  setTimeout(() => c.remove(), 900);
}

function faixa(texto) { const fx = $("faixa"); fx.textContent = texto; fx.hidden = false; clearTimeout(faixa.t); faixa.t = setTimeout(() => { fx.hidden = true; }, 1800); }

function montarMao(f) {
  const cx = $("cartas");
  const nv = (k) => modo === "convidado" ? carta(k).n : (nivMeus[k] || 1);
  cx.innerHTML = f.mao.map((k, i) => `<div class="${classeCarta(k)}${sel === i ? " sel" : ""}" data-i="${i}" data-carta="${k}" role="button" aria-label="${CARTAS[k].nome}, custa ${CARTAS[k].custo}">${htmlCarta(k, { nivel: nv(k) })}</div>`).join("");
  const px = $("proxima");
  px.className = f.prox ? `${classeCarta(f.prox)} mini` : "carta mini";
  px.innerHTML = f.prox ? htmlCarta(f.prox, { nome: false }) : "";
}

// ------------------------------------------------------------------ escolher e soltar cartas
function selecionar(i) {
  sel = i;
  for (const el of $("cartas").children) el.classList.toggle("sel", Number(el.dataset.i) === i);
  const k = i != null && atual ? atual.mao[i] : null;
  if (!k) { cena.mostrarZonas(false); cena.mostrarMarca(null); return; }
  // torres inimigas caídas abrem o bolsão do lado delas (esquerda/direita como o jogador vê)
  const inim = atual.ent.filter(e => e[1] === "torre" && e[2] !== lado);
  const naEsq = (x) => lado === 0 ? x < 9 : x > 9;
  cena.mostrarZonas(true, CARTAS[k].tipo === "magia", !inim.some(e => naEsq(e[3])), !inim.some(e => !naEsq(e[3])));
}

function estadoParaRegra() {
  if (s) return s;
  return { ent: atual.ent.map(e => ({ k: e[1], lado: e[2], x: e[3], y: e[4], fixa: e[1] === "torre" || e[1] === "rei", c: { raio: e[1] === "rei" ? 1.85 : 1.3 } })) };
}
function podeAqui(k, x, y) { return atual && podeSoltar(estadoParaRegra(), lado, k, x, y); }
const grade = (v) => Math.round(v * 2) / 2;

function marcar(cx, cy) {
  if (sel == null || !atual) return null;
  const p = cena.apontar(cx, cy);
  if (!p) { cena.mostrarMarca(null); return null; }
  const k = atual.mao[sel], x = grade(Math.min(L - 0.5, Math.max(0.5, p[0]))), y = grade(Math.min(C - 0.5, Math.max(0.5, p[1])));
  const ok = podeAqui(k, x, y);
  cena.mostrarMarca(x, y, ok, CARTAS[k].tipo === "magia" ? CARTAS[k].area : 0.9, k);
  return { x, y, ok };
}

function soltar(cx, cy) {
  const m = marcar(cx, cy);
  if (!m || sel == null) return;
  const i = sel, k = atual.mao[i], el = $("cartas").children[i];
  const nao = (texto) => { tocar("erro"); aviso(texto); if (el) { el.classList.remove("nao"); void el.offsetWidth; el.classList.add("nao"); } };
  if (!rodando || acabou) return;
  if (CARTAS[k].custo > atual.energia) return nao("Energia insuficiente");
  if (!m.ok) return nao(CARTAS[k].tipo === "magia" ? "Fora da arena" : "Solte no seu lado da arena");
  if (modo === "convidado") rede.enviar({ t: "j", i, x: m.x, y: m.y });
  else jogar(s, lado, i, m.x, m.y);
  vibrar(12);
  selecionar(null);
  if (tutorial === 1 && !jaJogou) {
    jaJogou = true; tutorial = 2;
    dica("Isso! A energia enche sozinha. Junte tropas e derrube as torres vermelhas 🏰", 5000);
    mudar({ tutorial: true });
  }
}

$("cartas").addEventListener("pointerdown", (ev) => {
  const el = ev.target.closest(".carta");
  if (!el || modo === "demo") return;
  ligarSom();
  const i = Number(el.dataset.i);
  if (sel === i && !arrasto) { selecionar(null); return; }
  tocar("escolher");
  selecionar(i);
  arrasto = { x: ev.clientX, y: ev.clientY, moveu: false };
});
window.addEventListener("pointermove", (ev) => {
  if (arrasto) {
    if (Math.hypot(ev.clientX - arrasto.x, ev.clientY - arrasto.y) > 14) arrasto.moveu = true;
    if (arrasto.moveu) { if (ev.clientY < $("mao").getBoundingClientRect().top) marcar(ev.clientX, ev.clientY); else cena.mostrarMarca(null); }
  } else if (sel != null && ev.pointerType === "mouse" && ev.target === $("tela")) marcar(ev.clientX, ev.clientY);
});
window.addEventListener("pointerup", (ev) => {
  if (!arrasto) return;
  const a = arrasto; arrasto = null;
  if (a.moveu) { if (ev.clientY < $("mao").getBoundingClientRect().top) soltar(ev.clientX, ev.clientY); else cena.mostrarMarca(null); }
});
$("tela").addEventListener("pointerdown", (ev) => { if (sel != null && !arrasto && modo !== "demo") soltar(ev.clientX, ev.clientY); });

// ------------------------------------------------------------------ fim de partida
let bauGanho = null;
function fimDePartida(venc) {
  acabou = true;
  selecionar(null);
  mostrar("dica", false); mostrar("emotes", false);
  const ganhei = venc === lado, empate = venc === 2;
  const tipo = modo === "bot" ? `bot${prog().nivel}` : "online";
  const r = registrar(empate ? "e" : ganhei ? "v" : "d", tipo, atual.coroas[lado]);
  bauGanho = r.bau;
  setTimeout(() => {
    if (modo === "demo") return;
    pararMusica();
    tocar(empate ? "extra" : ganhei ? "vitoria" : "derrota");
    if (ganhei) { vibrar([40, 40, 90]); confete(); }
    const t = $("tituloFim");
    t.textContent = empate ? "Empate" : ganhei ? "Vitória!" : "Derrota";
    t.classList.toggle("derrota", !ganhei);
    coroas($("fimCoroasEu"), atual.coroas[lado]); coroas($("fimCoroasInimigo"), atual.coroas[1 - lado]);
    $("fimNomeEu").textContent = nomeEu(); $("fimNomeInimigo").textContent = nomeInimigo;
    $("textoFim").textContent = empate ? "Ninguém derrubou mais torres." : ganhei ? (atual.coroas[lado] === 3 ? "Você derrubou o castelo!" : "Você derrubou mais torres.") : (atual.coroas[1 - lado] === 3 ? "Seu castelo caiu." : "O adversário derrubou mais torres.");
    const g = [];
    if (r.delta) g.push(`<span class="ganho${r.delta < 0 ? " perde" : ""}"><img src="img/ui/trofeu.png" alt="">${r.delta > 0 ? "+" : ""}${r.delta}</span>`);
    if (r.ouro) g.push(`<span class="ganho" style="animation-delay:.15s"><img src="img/ui/moeda.png" alt="">+${r.ouro}</span>`);
    if (r.xp) g.push(`<span class="ganho xp" style="animation-delay:.3s"><img src="img/ui/estrela.png" alt="">+${r.xp} XP</span>`);
    if (ganhei && prog().sequencia > 1) g.push(`<span class="ganho" style="animation-delay:.45s">🔥 ${prog().sequencia} seguidas</span>`);
    $("ganhos").innerHTML = g.join("");
    const gb = $("ganhoBau");
    gb.hidden = !ganhei;
    gb.innerHTML = r.bau ? `<img src="img/ui/bau_${r.bau.tipo}.png" alt=""><b>${BAUS[r.bau.tipo].nome}</b><small>Abra na tela de Batalha</small>`
      : `<b>Espaços de baú cheios</b><small>Abra um baú para ganhar o próximo</small>`;
    if (r.subiuRei) setTimeout(() => { tocar("nivel"); aviso(`👑 Seu rei subiu para o nível ${r.subiuRei}!`, 2600); }, 1400);
    $("deNovo").textContent = modo === "convidado" ? "Revanche" : "Jogar de novo";
    mostrar("fim");
  }, 1500);
}

function confete() {
  const cx = $("confete"), cores = ["#FFC83D", "#2F7BFF", "#F0463C", "#7FE07A", "#C45BFF", "#FFFFFF"];
  for (let k = 0; k < 90; k++) {
    const i = document.createElement("i");
    i.style.left = `${Math.random() * 100}%`; i.style.background = cores[k % cores.length];
    i.style.animationDuration = `${1.8 + Math.random() * 1.8}s`; i.style.animationDelay = `${Math.random() * 0.6}s`;
    i.style.transform = `rotate(${Math.random() * 360}deg)`;
    cx.appendChild(i);
  }
  setTimeout(() => { cx.innerHTML = ""; }, 4600);
}

// ------------------------------------------------------------------ emotes
function abrirEmotes() { const e = $("emotes"); e.hidden = !e.hidden; }
$("emotes").innerHTML = EMOJIS.map((e, i) => `<button data-i="${i}" aria-label="Mandar ${e}">${e}</button>`).join("");
$("emotes").addEventListener("click", (ev) => {
  const b = ev.target.closest("button"); if (!b) return;
  const i = Number(b.dataset.i);
  cena.emote(lado, EMOJIS[i]); tocar("clique");
  if (rede) rede.enviar({ t: "emo", i });
  if (modo === "bot" && Math.random() < 0.5) setTimeout(() => cena.emote(1, EMOJIS[Math.floor(Math.random() * EMOJIS.length)]), 900);
  mostrar("emotes", false);
});
const emoteDeFora = (i) => { if (EMOJIS[i]) { cena.emote(1 - lado, EMOJIS[i]); tocar("clique"); } };

// ------------------------------------------------------------------ salas (jogar com um amigo)
function linkDaSala() { return `${location.origin}${location.pathname}?sala=${codigo}${P.has("canal") ? "&canal=1" : ""}`; }
const meusDados = () => ({ nome: nomeEu(), baralho: prog().baralho, niveis: niveisDoBaralho(), rei: nivelRei() });
function mostrarSala() { fecharModais(); mostrar("fundoModal"); mostrar("sala"); }

function abrirSala() {
  ligarSom();
  codigo = novoCodigo();
  $("codigoSala").textContent = codigo; $("estadoSala").textContent = "Abrindo a sala…";
  mostrar("caixaLink", false); mostrar("mandarLink", false);
  mostrarSala();
  rede = ligar("dono", codigo, (msg) => {
    if (msg.t === "ola") {
      nomeInimigo = String(msg.nome || "Amigo").slice(0, 14);
      dele = { baralho: msg.baralho, niveis: msg.niveis && typeof msg.niveis === "object" ? msg.niveis : {}, rei: Math.max(1, Math.min(NIVEL_MAX, msg.rei | 0 || 1)) };
      rede.enviar({ t: "comeca", ...meusDados(), arena: arenaJogo() }); comecar("dono");
    }
    else if (msg.t === "j" && s && rodando) jogar(s, 1, msg.i | 0, Number(msg.x), Number(msg.y));
    else if (msg.t === "denovo" && acabou) { rede.enviar({ t: "comeca", ...meusDados(), arena: arenaJogo() }); comecar("dono"); }
    else if (msg.t === "emo") emoteDeFora(msg.i | 0);
  }, (estado, detalhe) => {
    if (estado === "pronto") { $("estadoSala").textContent = "Mande este link para o seu amigo. A partida começa quando ele entrar."; $("linkSala").value = linkDaSala(); mostrar("caixaLink"); mostrar("mandarLink", !!navigator.share); }
    else if (estado === "caiu") { aviso("O outro jogador saiu da partida.", 3000); paraMenu(); }
    else if (estado === "erro") { $("estadoSala").textContent = detalhe; }
  });
}

function entrarNaSala(cod) {
  ligarSom();
  codigo = cod.toUpperCase();
  $("codigoSala").textContent = codigo; $("estadoSala").textContent = "Entrando na sala…";
  mostrar("caixaLink", false); mostrar("mandarLink", false);
  mostrarSala();
  rede = ligar("convidado", codigo, (msg) => {
    if (msg.t === "comeca") { nomeInimigo = String(msg.nome || "Amigo").slice(0, 14); reiInimigo = Math.max(1, Math.min(NIVEL_MAX, msg.rei | 0 || 1)); comecar("convidado", undefined, Math.min(ARENAS.length - 1, Math.max(0, msg.arena | 0))); }
    else if (msg.t === "f" && modo === "convidado") desenhar(msg.f);
    else if (msg.t === "emo") emoteDeFora(msg.i | 0);
  }, (estado, detalhe) => {
    if (estado === "ligado") { $("estadoSala").textContent = "Conectado! Começando…"; rede.enviar({ t: "ola", ...meusDados() }); }
    else if (estado === "caiu") { aviso("O outro jogador saiu da partida.", 3000); paraMenu(); }
    else if (estado === "erro") { $("estadoSala").textContent = detalhe; }
  });
}

// ------------------------------------------------------------------ botões
const clique = (id, f) => $(id).addEventListener("click", () => { ligarSom(); tocar("clique"); f(); });
// o computador ganha um apelido de reino a cada partida
const APELIDOS = ["Barão de Ferro", "Duquesa Brasa", "Sir Tomate", "Rainha da Neve", "Conde Trovão", "Lady Faísca", "Mestre Pão", "Capitão Lama",
  "Bruxa do Brejo", "Rei Pipoca", "Dama do Lago", "Visconde Grilo"];
clique("jogarBot", () => { nomeInimigo = APELIDOS[Math.floor(Math.random() * APELIDOS.length)]; comecar("bot"); });
clique("criarSala", abrirSala);
clique("entrarSala", () => entrarNaSala(P.get("sala")));
clique("sairSala", paraMenu);
clique("paraMenu", () => { paraMenu(); depoisDaPartida(); });
clique("botaoSair", () => { if (acabou || confirm("Sair da partida? Conta como derrota.")) { if (!acabou && modo === "bot") registrar("d", `bot${prog().nivel}`, 0); paraMenu(); } });
clique("botaoEmote", abrirEmotes);
clique("deNovo", () => {
  if (modo === "bot") comecar("bot");
  else if (modo === "dono") { rede.enviar({ t: "comeca", ...meusDados(), arena: arenaJogo() }); comecar("dono"); }
  else if (modo === "convidado") { rede.enviar({ t: "denovo" }); $("textoFim").textContent = "Pedido enviado. Esperando o outro jogador…"; }
});
clique("copiarLink", async () => { try { await navigator.clipboard.writeText(linkDaSala()); aviso("Link copiado"); } catch (e) { $("linkSala").select(); aviso("Segure no link para copiar"); } });
clique("mandarLink", () => navigator.share({ title: "Arena dos Reinos", text: "Vem jogar comigo!", url: linkDaSala() }).catch(() => {}));
// a música só pode começar depois do primeiro toque na tela
window.addEventListener("pointerdown", () => { ligarSom(); iniciarMusica(modo !== "demo"); }, { once: true });

cena.aoSom = (nome, extra) => { if (modo !== "demo") tocar(nome, extra); };
window.addEventListener("resize", () => hud(!$("topo").hidden));
window.addEventListener("pagehide", () => { if (rede) rede.fechar(); });

// ------------------------------------------------------------------ app instalável
let pedidoInstalar = null;
window.addEventListener("beforeinstallprompt", (ev) => { ev.preventDefault(); pedidoInstalar = ev; mostrar("instalar"); });
clique("instalar", async () => { if (!pedidoInstalar) return; pedidoInstalar.prompt(); await pedidoInstalar.userChoice.catch(() => {}); pedidoInstalar = null; mostrar("instalar", false); });
if ("serviceWorker" in navigator && location.protocol === "https:") {
  // quando sai versão nova do jogo, o aparelho baixa sozinho e recarrega (só se estiver no menu, para não cortar partida)
  const tinha = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.register("sw.js").then(r => { r.update().catch(() => {}); setInterval(() => r.update().catch(() => {}), 5 * 60 * 1000); }).catch(() => {});
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!tinha) return;
    const tentar = () => { if (modo === "demo" && $("abrirBau").hidden) location.reload(); else setTimeout(tentar, 3000); };
    tentar();
  });
}

// ------------------------------------------------------------------ quadro a quadro
function quadro() {
  if (atual && modo !== "demo") {
    energiaTela += (atual.energia - energiaTela) * 0.25;
    $("energiaCheia").style.width = `${energiaTela * 10}%`;
    $("energiaNum").textContent = Math.floor(atual.energia + 0.001);
    for (const el of $("cartas").children) {           // a sombra na carta mostra quanto falta de energia
      const custo = CARTAS[el.dataset.carta].custo;
      el.style.setProperty("--falta", Math.max(0, Math.min(1, 1 - energiaTela / custo)).toFixed(3));
    }
  }
  cena.quadro();
  requestAnimationFrame(quadro);
}

(async () => {
  try {
    await cena.carregar("./", (q) => { $("cargaCheia").style.width = `${Math.round(q * 100)}%`; });
  } catch (e) {
    $("cargaTexto").textContent = "Não deu para carregar o jogo. Confira a internet e abra de novo.";
    console.error(e);
    return;
  }
  try { if (localStorage.getItem("arena-qualidade") === "0") cena.altaQualidade(false); } catch (e) { /* ok */ }
  iniciarLobby({ cena, musica: () => iniciarMusica(modo !== "demo") });
  window.__jogo = { cena, estado: () => ({ modo, lado, rodando, acabou, atual, sel, temSim: !!s }), sim: () => s, prog, RIO0, abrirTelaBau, fmt, arenaDoMenu, jogar };
  mostrar("carregando", false);
  paraMenu();
  requestAnimationFrame(quadro);
})();
