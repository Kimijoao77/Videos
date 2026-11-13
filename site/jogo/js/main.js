// O jogo em si: telas, cartas, energia e os três jeitos de jogar (contra o computador, criando uma sala ou entrando
// numa sala pelo link). Quem cria a sala roda as regras; o convidado só recebe as fotos do estado e manda as jogadas.
import { Cena } from "./render.js";
import { CARTAS, C, DT, L, RIO0, TODAS, baralhoValido, criarPartida, foto, jogar, passo, podeSoltar } from "./sim.js";
import { BARALHOS_BOT, criarBot, pensar } from "./bot.js";
import { ligar, novoCodigo } from "./rede.js";
import { alternarMudo, alternarMusica, estaMudo, iniciarMusica, ligarSom, musicaEstaLigada, pararMusica, tocar } from "./som.js";
import { ARENAS, arenaDe, mudar, prog, proximaArena, registrar } from "./progresso.js";

const $ = (id) => document.getElementById(id);
const cena = new Cena($("tela"));
const P = new URLSearchParams(location.search);
const EMOJIS = ["👍", "😂", "😮", "😡", "👏"];
let modo = "demo";            // demo (fundo do menu) | bot | dono | convidado
let lado = 0, s = null, bots = [], rede = null, atual = null, sel = null, arrasto = null, acabou = false, rodando = false;
let acc = 0, ultimo = 0, evLocal = [], evRemoto = [], ultEnvio = 0, maoTexto = "", energiaTela = 5, nomeInimigo = "Computador", codigo = "";
let baralhoDele = null, posTorre = {}, tutorial = 0, jaJogou = false;

const nomeEu = () => ($("nome").value.trim() || "Jogador").slice(0, 14);
const mostrar = (id, sim = true) => { $(id).hidden = !sim; };
const paineis = ["carregando", "menu", "como", "sala", "fim", "baralho", "stats"];
function tela(qual) { for (const p of paineis) mostrar(p, p === qual); }
function aviso(texto, ms = 1800) { const a = $("aviso"); a.textContent = texto; a.hidden = false; clearTimeout(aviso.t); aviso.t = setTimeout(() => { a.hidden = true; }, ms); }
function coroas(el, n) { el.innerHTML = [0, 1, 2].map(i => `<i class="coroa${i < n ? " tem" : ""}"></i>`).join(""); }
const vibrar = (p) => { try { navigator.vibrate && navigator.vibrate(p); } catch (e) { /* ok */ } };

// ------------------------------------------------------------------ começar e parar partidas
function hud(sim) {
  for (const id of ["topo", "mao", "botaoSair"]) mostrar(id, sim);
  mostrar("botaoEmote", sim); mostrar("emotes", false);
  mostrar("botaoSom", true); mostrar("botaoMusica", true);
  $("palco").style.setProperty("--altMao", `${$("mao").offsetHeight || 180}px`);
  cena.margens = sim ? { cima: $("topo").offsetHeight / $("palco").offsetHeight + 0.02, baixo: $("mao").offsetHeight / $("palco").offsetHeight + 0.01 } : { cima: 0.04, baixo: 0.05 };
  cena.ajustar();
}

function novaPartida(m, semente = (Math.random() * 1e9) | 0) {
  modo = m; acabou = false; sel = null; arrasto = null; maoTexto = ""; atual = null; evLocal = []; evRemoto = []; acc = 0; rodando = false; posTorre = {}; jaJogou = false;
  cena.limpar();
  cena.visao = lado = m === "convidado" ? 1 : 0;
  selecionar(null);
  if (m === "convidado") { s = null; bots = []; }
  else {
    const bot = () => BARALHOS_BOT[Math.floor(Math.random() * BARALHOS_BOT.length)];
    const meu = m === "demo" ? bot() : prog().baralho;
    const dele = m === "dono" ? baralhoValido(baralhoDele) : bot();
    s = criarPartida(semente, [meu, dele]);
    bots = m === "bot" ? [criarBot(1, prog().nivel)] : m === "demo" ? [criarBot(0), criarBot(1)] : [];
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
  tela(null);
  cena.trocarCenario(arena);
  novaPartida(m, semente);
  hud(true);
  $("nomeEu").textContent = nomeEu(); $("nomeInimigo").textContent = nomeInimigo;
  iniciarMusica(true);
  tutorial = m === "bot" && !prog().tutorial ? 1 : 0;
  contagem(() => {
    rodando = true; ultimo = performance.now(); acc = 0;
    if (tutorial === 1) dica("Toque numa carta e depois no seu lado da arena (ou arraste a carta até lá) 👇");
  });
}

function paraMenu() {
  clearTimeout(contagem.t); mostrar("contagem", false);
  if (rede) { rede.fechar(); rede = null; }
  hud(false);
  mostrar("botaoEmote", false);
  cena.trocarCenario(arenaVer);
  novaPartida("demo");
  rodando = true; ultimo = performance.now();
  const sala = P.get("sala");
  $("entrarSala").hidden = !sala;
  if (sala) $("entrarSala").textContent = `Entrar na sala ${sala.toUpperCase()}`;
  mostrarTrofeus();
  marcarNivel();
  pararMusica(); iniciarMusica(false);
  tela("menu");
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
  $("avisoTempo").textContent = f.fase === "extra" ? "TEMPO EXTRA" : f.dobro ? "ENERGIA EM DOBRO" : "";
  $("relogio").classList.toggle("pressa", f.fase === "extra" || seg <= 10);
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

function htmlCarta(carta) {
  const c = CARTAS[carta];
  return `<img src="cartas/${carta}.png" alt="" draggable="false"><span class="custo">${c.custo}</span><span class="nomeCarta">${c.nome}</span>`;
}
function montarMao(f) {
  const cx = $("cartas");
  cx.innerHTML = f.mao.map((carta, i) => `<div class="carta${sel === i ? " sel" : ""}" data-i="${i}" data-carta="${carta}" role="button" aria-label="${CARTAS[carta].nome}, custa ${CARTAS[carta].custo}">${htmlCarta(carta)}</div>`).join("");
  $("proxima").innerHTML = f.prox ? htmlCarta(f.prox) : "";
}

// ------------------------------------------------------------------ escolher e soltar cartas
function selecionar(i) {
  sel = i;
  for (const el of $("cartas").children) el.classList.toggle("sel", Number(el.dataset.i) === i);
  const carta = i != null && atual ? atual.mao[i] : null;
  if (!carta) { cena.mostrarZonas(false); cena.mostrarMarca(null); return; }
  // torres inimigas caídas abrem o bolsão do lado delas (esquerda/direita como o jogador vê)
  const inim = atual.ent.filter(e => e[1] === "torre" && e[2] !== lado);
  const naEsq = (x) => lado === 0 ? x < 9 : x > 9;
  cena.mostrarZonas(true, CARTAS[carta].tipo === "magia", !inim.some(e => naEsq(e[3])), !inim.some(e => !naEsq(e[3])));
}

function estadoParaRegra() {
  if (s) return s;
  return { ent: atual.ent.map(e => ({ k: e[1], lado: e[2], x: e[3], y: e[4], fixa: e[1] === "torre" || e[1] === "rei", c: { raio: e[1] === "rei" ? 1.85 : 1.3 } })) };
}
function podeAqui(carta, x, y) { return atual && podeSoltar(estadoParaRegra(), lado, carta, x, y); }
const grade = (v) => Math.round(v * 2) / 2;

function marcar(cx, cy) {
  if (sel == null || !atual) return null;
  const p = cena.apontar(cx, cy);
  if (!p) { cena.mostrarMarca(null); return null; }
  const carta = atual.mao[sel], x = grade(Math.min(L - 0.5, Math.max(0.5, p[0]))), y = grade(Math.min(C - 0.5, Math.max(0.5, p[1])));
  const ok = podeAqui(carta, x, y);
  cena.mostrarMarca(x, y, ok, CARTAS[carta].tipo === "magia" ? CARTAS[carta].area : 0.9, carta);
  return { x, y, ok };
}

function soltar(cx, cy) {
  const m = marcar(cx, cy);
  if (!m || sel == null) return;
  const i = sel, carta = atual.mao[i], el = $("cartas").children[i];
  const nao = (texto) => { tocar("erro"); aviso(texto); if (el) { el.classList.remove("nao"); void el.offsetWidth; el.classList.add("nao"); } };
  if (!rodando || acabou) return;
  if (CARTAS[carta].custo > atual.energia) return nao("Energia insuficiente");
  if (!m.ok) return nao(CARTAS[carta].tipo === "magia" ? "Fora da arena" : "Solte no seu lado da arena");
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
function fimDePartida(venc) {
  acabou = true;
  selecionar(null);
  mostrar("dica", false); mostrar("emotes", false);
  const ganhei = venc === lado, empate = venc === 2;
  const tipo = modo === "bot" ? `bot${prog().nivel}` : "online";
  const delta = registrar(empate ? "e" : ganhei ? "v" : "d", tipo, atual.coroas[lado]);
  setTimeout(() => {
    if (modo === "demo") return;
    pararMusica();
    tocar(empate ? "extra" : ganhei ? "vitoria" : "derrota");
    if (ganhei) { vibrar([40, 40, 90]); confete(); }
    $("tituloFim").textContent = empate ? "Empate" : ganhei ? "Vitória!" : "Derrota";
    coroas($("fimCoroasEu"), atual.coroas[lado]); coroas($("fimCoroasInimigo"), atual.coroas[1 - lado]);
    $("fimNomeEu").textContent = nomeEu(); $("fimNomeInimigo").textContent = nomeInimigo;
    $("textoFim").textContent = empate ? "Ninguém derrubou mais torres." : ganhei ? (atual.coroas[lado] === 3 ? "Você derrubou o castelo!" : "Você derrubou mais torres.") : (atual.coroas[1 - lado] === 3 ? "Seu castelo caiu." : "O adversário derrubou mais torres.");
    const g = $("ganhoTrofeus");
    g.hidden = delta === 0; g.classList.toggle("perde", delta < 0);
    g.textContent = `🏆 ${delta > 0 ? "+" : ""}${delta}  (${prog().trofeus})` + (ganhei && prog().sequencia > 1 ? `  🔥 ${prog().sequencia} seguidas` : "");
    $("deNovo").textContent = modo === "convidado" ? "Pedir revanche" : "Jogar de novo";
    tela("fim");
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

// ------------------------------------------------------------------ troféus, nível, baralho e recordes
// arenas: a que aparece no fundo do menu (dá para espiar as bloqueadas) e a que vale para jogar (só as liberadas)
// versão de teste: tudo liberado (todas as arenas para jogar). Para voltar a liberar por troféus, mude para false.
const TUDO_LIBERADO = true;
const liberadas = () => TUDO_LIBERADO ? ARENAS.length : ARENAS.filter(a => prog().trofeus >= a.min).length;
const arenaJogo = () => { const n = liberadas(), a = prog().arena; return a != null && a < n ? a : TUDO_LIBERADO ? 0 : n - 1; };
let arenaVer = arenaJogo();
function mostrarTrofeus() {
  const p = prog(), a = arenaDe(p.trofeus), prox = proximaArena(p.trofeus);
  const pct = prox ? Math.round((p.trofeus - a.min) / (prox.min - a.min) * 100) : 100;
  const ver = ARENAS[arenaVer], trava = arenaVer >= liberadas();
  $("trofeus").innerHTML = `<b>🏆 ${p.trofeus}</b><small>${prox ? `Próxima arena com ${prox.min} troféus` : "Você chegou na arena máxima!"}</small><div class="trilho"><i style="width:${pct}%"></i></div>
    <div class="arenaSel"><button type="button" data-a="-1" aria-label="Arena anterior">◀</button><span><em>Arena ${arenaVer + 1}</em>${trava ? "🔒 " : ""}${ver.nome}${trava ? `<i>Libera com ${ver.min} 🏆</i>` : ""}</span><button type="button" data-a="1" aria-label="Próxima arena">▶</button></div>`;
}
$("trofeus").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-a]"); if (!b) return;
  ligarSom(); tocar("clique");
  arenaVer = (arenaVer + Number(b.dataset.a) + ARENAS.length) % ARENAS.length;
  if (arenaVer < liberadas()) mudar({ arena: arenaVer });
  cena.trocarCenario(arenaVer);
  mostrarTrofeus();
});
function marcarNivel() {
  for (const b of $("niveis").children) b.setAttribute("aria-checked", String(Number(b.dataset.n) === prog().nivel));
  $("notaNivel").textContent = ["Bom para aprender. Vale menos troféus.", "Um adversário justo.", "Reage rápido e ganha 25% a mais de energia. Vale mais troféus."][prog().nivel];
}
$("niveis").addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (!b) return; ligarSom(); tocar("clique"); mudar({ nivel: Number(b.dataset.n) }); marcarNivel(); });

let escolha = [];
function abrirBaralho() {
  escolha = prog().baralho.slice();
  desenharBaralho();
  tela("baralho");
}
function desenharBaralho() {
  const media = escolha.length ? (escolha.reduce((t, k) => t + CARTAS[k].custo, 0) / escolha.length).toFixed(1) : "-";
  $("infoBaralho").innerHTML = `Escolha <b>8 cartas</b>. Selecionadas: <b>${escolha.length}/8</b> · custo médio <b>${media}</b>`;
  $("gradeBaralho").innerHTML = TODAS.map(k => `<div class="carta ${escolha.includes(k) ? "dentro" : "fora"}" data-carta="${k}" role="checkbox" aria-checked="${escolha.includes(k)}" aria-label="${CARTAS[k].nome}">${htmlCarta(k)}</div>`).join("");
  $("salvarBaralho").disabled = escolha.length !== 8;
  $("salvarBaralho").style.opacity = escolha.length === 8 ? 1 : 0.5;
}
$("gradeBaralho").addEventListener("click", (ev) => {
  const el = ev.target.closest(".carta"); if (!el) return;
  const k = el.dataset.carta;
  if (escolha.includes(k)) escolha = escolha.filter(x => x !== k);
  else if (escolha.length < 8) escolha.push(k);
  else { aviso("Tire uma carta antes de pôr outra"); tocar("erro"); return; }
  tocar("escolher"); desenharBaralho();
  aviso(CARTAS[k].texto, 2200);
});

function abrirStats() {
  const p = prog();
  const taxa = p.partidas ? Math.round(p.vitorias / p.partidas * 100) : 0;
  const itens = [["🏆", p.trofeus, "troféus"], ["⚔️", p.partidas, "partidas"], ["✅", p.vitorias, "vitórias"], ["📈", `${taxa}%`, "de vitórias"],
    ["🔥", p.melhorSeq, "melhor sequência"], ["👑", p.coroas, "coroas ganhas"]];
  $("listaStats").innerHTML = itens.map(([e, v, t]) => `<div><b>${e} ${v}</b><small>${t}</small></div>`).join("");
  tela("stats");
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

function abrirSala() {
  ligarSom();
  codigo = novoCodigo();
  $("codigoSala").textContent = codigo; $("estadoSala").textContent = "Abrindo a sala…";
  mostrar("caixaLink", false); mostrar("mandarLink", false);
  tela("sala");
  rede = ligar("dono", codigo, (msg) => {
    if (msg.t === "ola") { nomeInimigo = String(msg.nome || "Amigo").slice(0, 14); baralhoDele = msg.baralho; rede.enviar({ t: "comeca", nome: nomeEu(), arena: arenaJogo() }); comecar("dono"); }
    else if (msg.t === "j" && s && rodando) jogar(s, 1, msg.i | 0, Number(msg.x), Number(msg.y));
    else if (msg.t === "denovo" && acabou) { rede.enviar({ t: "comeca", nome: nomeEu(), arena: arenaJogo() }); comecar("dono"); }
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
  tela("sala");
  rede = ligar("convidado", codigo, (msg) => {
    if (msg.t === "comeca") { nomeInimigo = String(msg.nome || "Amigo").slice(0, 14); comecar("convidado", undefined, Math.min(ARENAS.length - 1, Math.max(0, msg.arena | 0))); }
    else if (msg.t === "f" && modo === "convidado") desenhar(msg.f);
    else if (msg.t === "emo") emoteDeFora(msg.i | 0);
  }, (estado, detalhe) => {
    if (estado === "ligado") { $("estadoSala").textContent = "Conectado! Começando…"; rede.enviar({ t: "ola", nome: nomeEu(), baralho: prog().baralho }); }
    else if (estado === "caiu") { aviso("O outro jogador saiu da partida.", 3000); paraMenu(); }
    else if (estado === "erro") { $("estadoSala").textContent = detalhe; }
  });
}

// ------------------------------------------------------------------ botões
const clique = (id, f) => $(id).addEventListener("click", () => { ligarSom(); tocar("clique"); f(); });
clique("jogarBot", () => { nomeInimigo = ["Computador (fácil)", "Computador", "Computador (difícil)"][prog().nivel]; comecar("bot"); });
clique("criarSala", abrirSala);
clique("entrarSala", () => entrarNaSala(P.get("sala")));
clique("sairSala", paraMenu);
clique("verComo", () => tela("como"));
clique("fecharComo", () => tela("menu"));
clique("verBaralho", abrirBaralho);
clique("salvarBaralho", () => { if (escolha.length !== 8) return; mudar({ baralho: escolha.slice() }); aviso("Baralho salvo"); tela("menu"); });
clique("verStats", abrirStats);
clique("fecharStats", () => tela("menu"));
clique("paraMenu", paraMenu);
clique("botaoSair", () => { if (acabou || confirm("Sair da partida?")) paraMenu(); });
clique("botaoEmote", abrirEmotes);
clique("deNovo", () => {
  if (modo === "bot") comecar("bot");
  else if (modo === "dono") { rede.enviar({ t: "comeca", nome: nomeEu(), arena: arenaJogo() }); comecar("dono"); }
  else if (modo === "convidado") { rede.enviar({ t: "denovo" }); $("textoFim").textContent = "Pedido enviado. Esperando o outro jogador…"; }
});
clique("copiarLink", async () => { try { await navigator.clipboard.writeText(linkDaSala()); aviso("Link copiado"); } catch (e) { $("linkSala").select(); aviso("Segure no link para copiar"); } });
clique("mandarLink", () => navigator.share({ title: "Arena dos Reinos", text: "Vem jogar comigo!", url: linkDaSala() }).catch(() => {}));
$("botaoSom").addEventListener("click", () => { ligarSom(); $("botaoSom").classList.toggle("mudo", alternarMudo()); });
$("botaoSom").classList.toggle("mudo", estaMudo());
$("botaoMusica").addEventListener("click", () => { ligarSom(); const lig = alternarMusica(); $("botaoMusica").classList.toggle("mudo", !lig); if (lig) iniciarMusica(modo !== "demo"); });
$("botaoMusica").classList.toggle("mudo", !musicaEstaLigada());
$("nome").addEventListener("change", () => { try { localStorage.setItem("arena-nome", $("nome").value.trim()); } catch (e) { /* ok */ } });
try { $("nome").value = localStorage.getItem("arena-nome") || ""; } catch (e) { /* ok */ }
$("listaCartas").innerHTML = TODAS.map(k => `<div class="linhaCarta"><img src="cartas/${k}.png" alt=""><div><b>${CARTAS[k].nome}<i>${CARTAS[k].custo}</i></b><span>${CARTAS[k].texto}</span></div></div>`).join("");
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
    const tentar = () => { if (modo === "demo") location.reload(); else setTimeout(tentar, 3000); };
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
  window.__jogo = { cena, estado: () => ({ modo, lado, rodando, acabou, atual, sel, temSim: !!s }), sim: () => s, prog, RIO0 };
  paraMenu();
  requestAnimationFrame(quadro);
})();
