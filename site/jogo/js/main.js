// O jogo em si: telas, cartas, energia e os três jeitos de jogar (contra o computador, criando uma sala ou entrando
// numa sala pelo link). Quem cria a sala roda as regras; o convidado só recebe as fotos do estado e manda as jogadas.
import { Cena } from "./render.js";
import { BARALHO, CARTAS, C, DT, L, RIO0, criarPartida, foto, jogar, passo, podeSoltar } from "./sim.js";
import { criarBot, pensar } from "./bot.js";
import { ligar, novoCodigo } from "./rede.js";
import { alternarMudo, estaMudo, ligarSom, tocar } from "./som.js";

const $ = (id) => document.getElementById(id);
const cena = new Cena($("tela"));
const P = new URLSearchParams(location.search);
let modo = "demo";            // demo (fundo do menu) | bot | dono | convidado
let lado = 0, s = null, bots = [], rede = null, atual = null, sel = null, arrasto = null, acabou = false, rodando = false;
let acc = 0, ultimo = 0, evLocal = [], evRemoto = [], ultEnvio = 0, maoTexto = "", energiaTela = 5, nomeInimigo = "Computador", codigo = "";

const nomeEu = () => ($("nome").value.trim() || "Jogador").slice(0, 14);
const mostrar = (id, sim = true) => { $(id).hidden = !sim; };
const paineis = ["carregando", "menu", "como", "sala", "fim"];
function tela(qual) { for (const p of paineis) mostrar(p, p === qual); }
function aviso(texto, ms = 1800) { const a = $("aviso"); a.textContent = texto; a.hidden = false; clearTimeout(aviso.t); aviso.t = setTimeout(() => { a.hidden = true; }, ms); }
function coroas(el, n) { el.innerHTML = [0, 1, 2].map(i => `<i class="coroa${i < n ? " tem" : ""}"></i>`).join(""); }

// ------------------------------------------------------------------ começar e parar partidas
function hud(sim) {
  for (const id of ["topo", "mao", "botaoSair"]) mostrar(id, sim);
  mostrar("botaoSom", true);
  cena.margens = sim ? { cima: $("topo").offsetHeight / $("palco").offsetHeight + 0.02, baixo: $("mao").offsetHeight / $("palco").offsetHeight + 0.01 } : { cima: 0.04, baixo: 0.05 };
  cena.ajustar();
}

function novaPartida(m, semente = (Math.random() * 1e9) | 0) {
  modo = m; acabou = false; sel = null; arrasto = null; maoTexto = ""; atual = null; evLocal = []; evRemoto = []; acc = 0; rodando = false;
  cena.limpar();
  cena.visao = lado = m === "convidado" ? 1 : 0;
  selecionar(null);
  if (m === "convidado") { s = null; bots = []; }
  else {
    s = criarPartida(semente);
    bots = m === "bot" ? [criarBot(1)] : m === "demo" ? [criarBot(0), criarBot(1)] : [];
    desenhar(foto(s, 0, []));
  }
  $("relogio").classList.remove("pressa");
  mostrar("faixa", false);
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

function comecar(m, semente) {
  tela(null);
  novaPartida(m, semente);
  hud(true);
  $("nomeEu").textContent = nomeEu(); $("nomeInimigo").textContent = nomeInimigo;
  contagem(() => { rodando = true; ultimo = performance.now(); acc = 0; });
}

function paraMenu() {
  clearTimeout(contagem.t); mostrar("contagem", false);
  if (rede) { rede.fechar(); rede = null; }
  hud(false);
  novaPartida("demo");
  rodando = true; ultimo = performance.now();
  const sala = P.get("sala");
  $("entrarSala").hidden = !sala;
  if (sala) $("entrarSala").textContent = `Entrar na sala ${sala.toUpperCase()}`;
  tela("menu");
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
  }
  const eu = lado, ele = 1 - lado;
  coroas($("coroasEu"), f.coroas[eu]); coroas($("coroasInimigo"), f.coroas[ele]);
  const seg = f.tempo;
  $("tempo").textContent = `${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}`;
  $("avisoTempo").textContent = f.fase === "extra" ? "TEMPO EXTRA" : f.dobro ? "ENERGIA EM DOBRO" : "";
  $("relogio").classList.toggle("pressa", f.fase === "extra" || seg <= 10);
  if (f.fase === "jogo" && seg <= 10 && seg > 0 && seg !== desenhar.seg) { desenhar.seg = seg; tocar("tique"); }
  if (f.fase === "jogo" && seg === 60 && desenhar.dobro !== f.tk >> 5) { if (!desenhar.avisou) { desenhar.avisou = true; faixa("Energia em dobro!"); } } else if (seg > 60) desenhar.avisou = false;
  const texto = f.mao.join(",") + "|" + f.prox;
  if (texto !== maoTexto) { maoTexto = texto; montarMao(f); }
  for (const el of $("cartas").children) el.classList.toggle("cara", CARTAS[el.dataset.carta].custo > f.energia);
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
  cena.mostrarMarca(x, y, ok, CARTAS[carta].tipo === "magia" ? CARTAS[carta].area : 0.9);
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
  selecionar(null);
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
  const ganhei = venc === lado, empate = venc === 2;
  setTimeout(() => {
    if (modo === "demo") return;
    tocar(empate ? "extra" : ganhei ? "vitoria" : "derrota");
    $("tituloFim").textContent = empate ? "Empate" : ganhei ? "Vitória!" : "Derrota";
    coroas($("fimCoroasEu"), atual.coroas[lado]); coroas($("fimCoroasInimigo"), atual.coroas[1 - lado]);
    $("fimNomeEu").textContent = nomeEu(); $("fimNomeInimigo").textContent = nomeInimigo;
    $("textoFim").textContent = empate ? "Ninguém derrubou mais torres." : ganhei ? (atual.coroas[lado] === 3 ? "Você derrubou o castelo!" : "Você derrubou mais torres.") : (atual.coroas[1 - lado] === 3 ? "Seu castelo caiu." : "O adversário derrubou mais torres.");
    $("deNovo").textContent = modo === "convidado" ? "Pedir revanche" : "Jogar de novo";
    tela("fim");
  }, 1500);
}

// ------------------------------------------------------------------ salas (jogar com um amigo)
function linkDaSala() { return `${location.origin}${location.pathname}?sala=${codigo}${P.has("canal") ? "&canal=1" : ""}`; }

function abrirSala() {
  ligarSom();
  codigo = novoCodigo();
  $("codigoSala").textContent = codigo; $("estadoSala").textContent = "Abrindo a sala…";
  mostrar("caixaLink", false); mostrar("mandarLink", false);
  tela("sala");
  rede = ligar("dono", codigo, (msg) => {
    if (msg.t === "ola") { nomeInimigo = String(msg.nome || "Amigo").slice(0, 14); rede.enviar({ t: "comeca", nome: nomeEu() }); comecar("dono"); }
    else if (msg.t === "j" && s && rodando) jogar(s, 1, msg.i | 0, Number(msg.x), Number(msg.y));
    else if (msg.t === "denovo" && acabou) { rede.enviar({ t: "comeca", nome: nomeEu() }); comecar("dono"); }
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
    if (msg.t === "comeca") { nomeInimigo = String(msg.nome || "Amigo").slice(0, 14); comecar("convidado"); }
    else if (msg.t === "f" && modo === "convidado") desenhar(msg.f);
  }, (estado, detalhe) => {
    if (estado === "ligado") { $("estadoSala").textContent = "Conectado! Começando…"; rede.enviar({ t: "ola", nome: nomeEu() }); }
    else if (estado === "caiu") { aviso("O outro jogador saiu da partida.", 3000); paraMenu(); }
    else if (estado === "erro") { $("estadoSala").textContent = detalhe; }
  });
}

// ------------------------------------------------------------------ botões
const clique = (id, f) => $(id).addEventListener("click", () => { ligarSom(); tocar("clique"); f(); });
clique("jogarBot", () => { nomeInimigo = "Computador"; comecar("bot"); });
clique("criarSala", abrirSala);
clique("entrarSala", () => entrarNaSala(P.get("sala")));
clique("sairSala", paraMenu);
clique("verComo", () => tela("como"));
clique("fecharComo", () => tela("menu"));
clique("paraMenu", paraMenu);
clique("botaoSair", () => { if (acabou || confirm("Sair da partida?")) paraMenu(); });
clique("deNovo", () => {
  if (modo === "bot") comecar("bot");
  else if (modo === "dono") { rede.enviar({ t: "comeca", nome: nomeEu() }); comecar("dono"); }
  else if (modo === "convidado") { rede.enviar({ t: "denovo" }); $("textoFim").textContent = "Pedido enviado. Esperando o outro jogador…"; }
});
clique("copiarLink", async () => { try { await navigator.clipboard.writeText(linkDaSala()); aviso("Link copiado"); } catch (e) { $("linkSala").select(); aviso("Segure no link para copiar"); } });
clique("mandarLink", () => navigator.share({ title: "Arena dos Reinos", text: "Vem jogar comigo!", url: linkDaSala() }).catch(() => {}));
$("botaoSom").addEventListener("click", () => { ligarSom(); $("botaoSom").classList.toggle("mudo", alternarMudo()); });
$("botaoSom").classList.toggle("mudo", estaMudo());
$("nome").addEventListener("change", () => { try { localStorage.setItem("arena-nome", $("nome").value.trim()); } catch (e) { /* ok */ } });
try { $("nome").value = localStorage.getItem("arena-nome") || ""; } catch (e) { /* ok */ }
$("listaCartas").innerHTML = BARALHO.map(k => `<div class="linhaCarta"><img src="cartas/${k}.png" alt=""><div><b>${CARTAS[k].nome}<i>${CARTAS[k].custo}</i></b><span>${CARTAS[k].texto}</span></div></div>`).join("");

cena.aoSom = (nome, extra) => { if (modo !== "demo") tocar(nome, extra); };
window.addEventListener("resize", () => hud(!$("topo").hidden));
window.addEventListener("pagehide", () => { if (rede) rede.fechar(); });

// ------------------------------------------------------------------ quadro a quadro
function quadro() {
  if (atual && modo !== "demo") {
    energiaTela += (atual.energia - energiaTela) * 0.25;
    $("energiaCheia").style.width = `${energiaTela * 10}%`;
    $("energiaNum").textContent = Math.floor(atual.energia + 0.001);
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
  window.__jogo = { cena, estado: () => ({ modo, lado, rodando, acabou, atual, sel, temSim: !!s }), sim: () => s, RIO0 };
  paraMenu();
  requestAnimationFrame(quadro);
})();
