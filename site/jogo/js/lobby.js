// O lobby (o menu com abas): barra de recursos, aba Batalha (arena, botão de jogar e os 4 baús), aba Cartas (baralho,
// coleção, detalhe e melhorar), Loja (presente do dia, ofertas, baús), Trilha de troféus, janelas de ajustes e perfil,
// e a tela de abrir baú (que serve para baús ganhos, comprados e da trilha).
import { CARTAS, NIVEL_MAX, RARIDADES, TODAS, fatorNivel } from "./sim.js";
import {
  ARENAS, BAUS, PRECO_BAU, TRILHA, abrirBau, alguemAbrindo, arenaDe, carta, comecarAbrir, comprarBau, comprarOferta, estadoBau, faixaXp,
  lojaDoDia, melhorar, mediaNivel, mudar, nivelRei, pegarPresente, podeMelhorar, presenteDisponivel, prog, proximoNivel, quaseMelhorar,
  resgatarTrilha, temTrilhaPronta, trilhaPronta,
} from "./progresso.js";
import { alternarMudo, alternarMusica, estaMudo, ligarSom, musicaEstaLigada, tocar } from "./som.js";

const $ = (id) => document.getElementById(id);
let api = null, aba = "batalha", arenaVer = 0, trocando = null, cartaAberta = null;

// versão de teste: todas as arenas liberadas para jogar (para voltar a liberar por troféus, mude para false)
export const TUDO_LIBERADO = true;
const liberadas = () => TUDO_LIBERADO ? ARENAS.length : ARENAS.filter(a => prog().trofeus >= a.min).length;
export const arenaJogo = () => { const n = liberadas(), a = prog().arena; return a != null && a < n ? a : TUDO_LIBERADO ? 0 : n - 1; };
export const arenaDoMenu = () => arenaVer;

export function aviso(texto, ms = 1800) { const a = $("aviso"); a.textContent = texto; a.hidden = false; clearTimeout(aviso.t); aviso.t = setTimeout(() => { a.hidden = true; }, ms); }
export const fmt = (n) => n >= 10000 ? `${(n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(".", ",")} mil` : n.toLocaleString("pt-BR");
const tempo = (ms) => { const s = Math.ceil(ms / 1000); return s >= 60 ? `${Math.floor(s / 60)}min ${String(s % 60).padStart(2, "0")}s` : `${s}s`; };
let vibrarLigado = true;
try { vibrarLigado = localStorage.getItem("arena-vibrar") !== "0"; } catch (e) { /* ok */ }
export const vibrar = (p) => { if (!vibrarLigado) return; try { navigator.vibrate && navigator.vibrate(p); } catch (e) { /* ok */ } };

// ------------------------------------------------------------------ a carta (mesma cara em todo lugar)
export function htmlCarta(k, { nivel = null, nome = true, qtd = null } = {}) {
  const c = CARTAS[k];
  return `<img src="cartas/${k}.png" alt="" draggable="false"><span class="custo">${c.custo}</span>${nivel ? `<span class="nv">Nv.${nivel}</span>` : ""}${nome ? `<span class="nomeCarta">${c.nome}</span>` : ""}${qtd ? `<span class="qtd">×${qtd}</span>` : ""}`;
}
export const classeCarta = (k) => `carta ${CARTAS[k].raridade}`;
function barraCopias(k) {
  const p = proximoNivel(k), c = carta(k);
  if (!p) return `<div class="copias max"><i></i><span>MÁX</span></div>`;
  const q = Math.min(1, c.c / p.copias);
  return `<div class="copias${c.c >= p.copias ? " cheia" : ""}"><i style="width:${q * 100}%"></i><span>${c.c}/${p.copias}</span></div>`;
}

// ------------------------------------------------------------------ montar e mostrar
export function iniciarLobby(a) {
  api = a;
  arenaVer = arenaJogo();
  $("nav").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-aba]"); if (b) { ligarSom(); tocar("clique"); irPara(b.dataset.aba); } });
  $("arenaSel").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-a]"); if (!b) return;
    ligarSom(); tocar("clique");
    arenaVer = (arenaVer + Number(b.dataset.a) + ARENAS.length) % ARENAS.length;
    if (arenaVer < liberadas()) mudar({ arena: arenaVer });
    api.cena.trocarCenario(arenaVer);
    desenharArena();
  });
  $("niveis").addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (!b) return; ligarSom(); tocar("clique"); mudar({ nivel: Number(b.dataset.n) }); marcarNivel(); });
  $("baus").addEventListener("click", (ev) => { const s = ev.target.closest(".slot"); if (s) tocarBau(Number(s.dataset.i)); });
  $("gradeBaralho").addEventListener("click", (ev) => {
    const el = ev.target.closest(".carta"); if (!el) return;
    ligarSom();
    if (trocando) { trocarNoBaralho(el.dataset.carta); return; }
    tocar("escolher"); abrirDetalhe(el.dataset.carta);
  });
  $("gradeColecao").addEventListener("click", (ev) => { const el = ev.target.closest(".carta"); if (!el) return; ligarSom(); tocar("escolher"); sairTroca(); abrirDetalhe(el.dataset.carta); });
  $("cancelarTroca").addEventListener("click", () => { tocar("clique"); sairTroca(); });
  $("detalheUsar").addEventListener("click", () => { tocar("clique"); const k = cartaAberta; fecharModais(); entrarTroca(k); });
  $("detalheMelhorar").addEventListener("click", () => { ligarSom(); fazerMelhoria(cartaAberta); });
  $("ofertas").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-j]"); if (b) comprar(Number(b.dataset.j)); });
  $("bausLoja").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-bau]"); if (b) comprarBauLoja(b.dataset.bau); });
  $("presente").addEventListener("click", () => { ligarSom(); const p = pegarPresente(); if (!p) return; tocar("moeda"); abrirTelaBau(p, "Presente do dia", "bau_madeira"); });
  $("trilha").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-j]"); if (b) pegarTrilha(Number(b.dataset.j)); });
  $("abrirAjustes").addEventListener("click", () => { ligarSom(); tocar("clique"); abrirAjustes(); });
  $("abrirPerfil").addEventListener("click", () => { ligarSom(); tocar("clique"); abrirPerfil(); });
  $("verComo").addEventListener("click", () => { tocar("clique"); fecharModais(); abrirModal("como"); });
  $("fundoModal").addEventListener("click", fecharModais);
  for (const b of document.querySelectorAll("[data-fechar]")) b.addEventListener("click", () => { tocar("clique"); fecharModais(); });
  // ajustes
  $("chaveSom").addEventListener("click", () => { ligarSom(); alternarMudo(); tocar("clique"); marcarAjustes(); });
  $("chaveMusica").addEventListener("click", () => { ligarSom(); const lig = alternarMusica(); if (lig) api.musica(); tocar("clique"); marcarAjustes(); });
  $("chaveSombras").addEventListener("click", () => { tocar("clique"); api.cena.altaQualidade(!api.cena.qualidadeAlta); try { localStorage.setItem("arena-qualidade", api.cena.qualidadeAlta ? "1" : "0"); } catch (e) { /* ok */ } marcarAjustes(); });
  $("chaveVibrar").addEventListener("click", () => { vibrarLigado = !vibrarLigado; try { localStorage.setItem("arena-vibrar", vibrarLigado ? "1" : "0"); } catch (e) { /* ok */ } tocar("clique"); vibrar(30); marcarAjustes(); });
  $("nome").addEventListener("change", () => { try { localStorage.setItem("arena-nome", $("nome").value.trim()); } catch (e) { /* ok */ } atualizarRecursos(); });
  try { $("nome").value = localStorage.getItem("arena-nome") || ""; } catch (e) { /* ok */ }
  $("listaCartas").innerHTML = TODAS.map(k => `<div class="linhaCarta"><img src="cartas/${k}.png" alt=""><div><b>${CARTAS[k].nome}<i>${CARTAS[k].custo}</i></b><span>${CARTAS[k].texto}</span></div></div>`).join("");
  // abrir baú: um toque avança
  $("abrirBau").addEventListener("click", avancarBau);
  setInterval(() => { if (!$("lobby").hidden && aba === "batalha") desenharBaus(); if (!$("lobby").hidden && aba === "loja") $("lojaTempo").textContent = `novas em ${ateMeiaNoite()}`; }, 1000);
}

export const nomeEu = () => ($("nome").value.trim() || "Jogador").slice(0, 14);

export function mostrarLobby() {
  for (const id of ["lobby"]) $(id).hidden = false;
  arenaVer = arenaJogo();
  api.cena.trocarCenario(arenaVer);
  irPara(aba, false);
  atualizarRecursos();
  marcarNivel();
}
export function esconderLobby() { $("lobby").hidden = true; fecharModais(); }

function irPara(qual, animar = true) {
  aba = qual;
  for (const b of $("nav").children) b.classList.toggle("ativa", b.dataset.aba === qual);
  for (const a of ["loja", "cartas", "batalha", "trilha"]) {
    const el = $(`aba-${a}`);
    el.hidden = a !== qual;
    if (a === qual && animar) { el.classList.remove("entra"); void el.offsetWidth; el.classList.add("entra"); }
  }
  $("lobby").classList.toggle("opaco", qual !== "batalha");
  if (qual !== "cartas") sairTroca();
  if (qual === "batalha") { desenharArena(); desenharBaus(); }
  if (qual === "cartas") desenharCartas();
  if (qual === "loja") desenharLoja();
  if (qual === "trilha") desenharTrilha();
  pontos();
}

export function atualizarRecursos(animar = false) {
  const p = prog(), fx = faixaXp();
  $("lobbyNome").textContent = nomeEu();
  $("lobbyRei").textContent = fx.n;
  $("lobbyXp").style.width = `${fx.max ? 100 : Math.round(fx.de / fx.ate * 100)}%`;
  $("lobbyXpTxt").textContent = fx.max ? "Nível máximo" : `${fx.de}/${fx.ate} XP`;
  const o = $("lobbyOuro"), t = $("lobbyTrofeus");
  if (animar && o.textContent !== fmt(p.ouro)) { o.classList.remove("sobe"); void o.offsetWidth; o.classList.add("sobe"); }
  o.textContent = fmt(p.ouro); t.textContent = fmt(p.trofeus);
  pontos();
}

// bolinhas vermelhas nas abas quando tem algo para fazer lá
function pontos() {
  const p = $("nav").querySelectorAll(".ponto");
  const melhoraveis = TODAS.filter(podeMelhorar).length;
  p[0].hidden = !presenteDisponivel();
  p[1].hidden = !melhoraveis; p[1].textContent = melhoraveis || "";
  p[2].hidden = !prog().baus.some((b, i) => estadoBau(i).pronto);
  p[3].hidden = !temTrilhaPronta();
}

// ------------------------------------------------------------------ aba Batalha
function desenharArena() {
  const ver = ARENAS[arenaVer], trava = arenaVer >= liberadas();
  $("arenaNum").textContent = `Arena ${arenaVer + 1}`;
  $("arenaNome").textContent = (trava ? "🔒 " : "") + ver.nome;
  $("arenaTrava").textContent = trava ? `Libera com ${ver.min} troféus` : arenaDe(prog().trofeus) === ver ? "Sua arena" : "";
}
function marcarNivel() { for (const b of $("niveis").children) b.setAttribute("aria-checked", String(Number(b.dataset.n) === prog().nivel)); }

function desenharBaus() {
  const abrindoAlgum = alguemAbrindo();
  $("baus").innerHTML = [0, 1, 2, 3].map(i => {
    const e = estadoBau(i);
    if (e.vazio) return `<div class="slot vazio" data-i="${i}"><small>Espaço de baú</small></div>`;
    const img = `<img src="img/ui/bau_${e.b.tipo}.png" alt="">`, nome = BAUS[e.b.tipo].nome.replace("Baú ", "").replace("de ", "");
    if (e.pronto) return `<button class="slot pronto" data-i="${i}" aria-label="Abrir ${BAUS[e.b.tipo].nome}">${img}<small>ABRIR!</small></button>`;
    if (e.abrindo) return `<button class="slot abrindo" data-i="${i}" aria-label="${BAUS[e.b.tipo].nome} abrindo">${img}<small>${tempo(e.falta)}<i>abrindo</i></small></button>`;
    return `<button class="slot" data-i="${i}" aria-label="${BAUS[e.b.tipo].nome}">${img}<small>${abrindoAlgum ? tempo(BAUS[e.b.tipo].seg * 1000) : "Destrancar"}<i>${nome}</i></small></button>`;
  }).join("");
}
function tocarBau(i) {
  ligarSom();
  const e = estadoBau(i);
  if (e.vazio) { aviso("Vença partidas para ganhar baús"); return; }
  if (e.pronto) { const tipo = e.b.tipo, premio = abrirBau(i); if (premio) abrirTelaBau(premio, BAUS[tipo].nome, `bau_${tipo}`); return; }
  if (e.abrindo) { aviso(`Falta ${tempo(e.falta)} para abrir`); return; }
  if (alguemAbrindo()) { aviso("Já tem um baú abrindo. Um por vez!"); tocar("erro"); return; }
  comecarAbrir(i); tocar("clique"); aviso(`${BAUS[e.b.tipo].nome}: abre em ${tempo(BAUS[e.b.tipo].seg * 1000)}`);
  desenharBaus();
}

// ------------------------------------------------------------------ aba Cartas
function desenharCartas() {
  const b = prog().baralho;
  const media = (b.reduce((t, k) => t + CARTAS[k].custo, 0) / b.length).toFixed(1);
  $("infoBaralho").innerHTML = `Custo médio <b>${media.replace(".", ",")}</b> · nível médio <b>${mediaNivel().toFixed(1).replace(".", ",")}</b>`;
  $("gradeBaralho").innerHTML = b.map(k => `<div class="item"><div class="${classeCarta(k)}${trocando ? " trocavel" : ""}" data-carta="${k}" role="button" aria-label="${CARTAS[k].nome}">${htmlCarta(k, { nivel: carta(k).n })}</div>${barraCopias(k)}</div>`).join("");
  const fora = TODAS.filter(k => !b.includes(k));
  $("infoColecao").textContent = `${TODAS.length} cartas · ${fora.length} fora do baralho`;
  $("gradeColecao").innerHTML = fora.map(k => `<div class="item"><div class="${classeCarta(k)}" data-carta="${k}" role="button" aria-label="${CARTAS[k].nome}">${htmlCarta(k, { nivel: carta(k).n })}</div>${barraCopias(k)}</div>`).join("");
  $("trocando").hidden = !trocando;
}
function entrarTroca(k) {
  if (prog().baralho.includes(k)) return;
  trocando = k; desenharCartas();
  $("aba-cartas").scrollTo({ top: 0, behavior: "smooth" });
  aviso(`Toque na carta que vai sair para pôr ${CARTAS[k].nome}`, 2400);
}
function sairTroca() { if (!trocando) return; trocando = null; if (aba === "cartas") desenharCartas(); }
function trocarNoBaralho(sai) {
  const b = prog().baralho.slice(), i = b.indexOf(sai);
  if (i < 0) return;
  b[i] = trocando;
  mudar({ baralho: b });
  tocar("escolher"); aviso(`${CARTAS[trocando].nome} entrou no baralho`);
  trocando = null; desenharCartas();
}

const ICONES = { hp: "❤️", dano: "⚔️", dps: "💥", alc: "🎯", vel: "👟", alvo: "🛡️", area: "💫", n: "👥", vida: "⏳", cura: "💚", efeito: "❄️", custo: "💧" };
function linhasStats(k, nivel) {
  const c = CARTAS[k], f = fatorNivel(nivel), f2 = fatorNivel(nivel + 1), prox = nivel < NIVEL_MAX;
  const v = (x) => Math.round(x * f), dif = (x) => prox ? `<em>+${Math.round(x * f2) - Math.round(x * f)}</em>` : "";
  const L = [];
  if (c.hp) L.push(["hp", c.tipo === "predio" ? "Vida" : c.n > 1 ? "Vida (cada)" : "Vida", `${v(c.hp)}${dif(c.hp)}`]);
  if (c.dano) L.push(["dano", c.area && c.tipo !== "magia" ? "Dano em área" : "Dano", `${v(c.dano)}${dif(c.dano)}`]);
  if (c.cura) L.push(["cura", "Cura", `${v(c.cura)}${dif(c.cura)}`]);
  if (c.tipo === "magia" && c.danoTorre && c.dano) L.push(["alvo", "Dano em torre", `${Math.round(v(c.dano) * c.danoTorre)}`]);
  if (c.cad) L.push(["dps", "Golpe a cada", `${String(c.cad).replace(".", ",")} s`]);
  if (c.vel != null && c.tipo === "tropa") L.push(["vel", "Velocidade", c.vel >= 1.4 ? "Rápida" : c.vel >= 1 ? "Média" : "Lenta"]);
  if (c.alc != null && c.tipo !== "magia") L.push(["alc", "Alcance", c.alc > 2 ? String(c.alc).replace(".", ",") : "Corpo a corpo"]);
  if (c.tipo !== "magia") L.push(["alvo", "Ataca", c.soPredio ? "Construções" : c.ar ? "Chão e ar" : "Só chão"]);
  if (c.area && c.tipo === "magia") L.push(["area", "Raio", String(c.area).replace(".", ",")]);
  if (c.n > 1) L.push(["n", "Quantidade", `×${c.n}`]);
  if (c.vida) L.push(["vida", "Dura", `${c.vida} s`]);
  if (c.congela) L.push(["efeito", "Congela", `${c.congela} s`]);
  if (c.atordoa) L.push(["efeito", "Atordoa", `${String(c.atordoa).replace(".", ",")} s`]);
  return L;
}
export function abrirDetalhe(k) {
  cartaAberta = k;
  const c = CARTAS[k], cc = carta(k), p = proximoNivel(k);
  $("detalheCarta").className = `${classeCarta(k)} grande`;
  $("detalheCarta").innerHTML = htmlCarta(k, { nome: false });
  $("detalheNome").textContent = c.nome;
  $("detalheRar").className = `raridade ${c.raridade}`;
  $("detalheRar").textContent = `${RARIDADES[c.raridade].nome} · ${c.tipo === "magia" ? "Magia" : c.tipo === "predio" ? "Construção" : "Tropa"}`;
  $("detalheTexto").textContent = c.texto;
  $("detalheNivel").innerHTML = `<span>Nível ${cc.n}</span>${barraCopias(k)}`;
  $("detalheStats").innerHTML = linhasStats(k, cc.n).map(([ic, t, v]) => `<div><span>${ICONES[ic]}</span><span><small>${t}</small><b>${v}</b></span></div>`).join("");
  const noBaralho = prog().baralho.includes(k);
  $("detalheUsar").hidden = noBaralho;
  const mb = $("detalheMelhorar");
  mb.hidden = !p;
  if (p) {
    mb.innerHTML = `Melhorar <img src="img/ui/moeda.png" alt="">${fmt(p.ouro)}`;
    mb.disabled = !podeMelhorar(k);
    mb.title = quaseMelhorar(k) ? (prog().ouro < p.ouro ? "Falta ouro" : "") : "Faltam cópias desta carta";
  }
  $("detalhe").querySelector(".botoes").style.gridTemplateColumns = noBaralho || !p ? "1fr" : "1fr 1fr";
  abrirModal("detalhe");
}
function fazerMelhoria(k) {
  const p = proximoNivel(k);
  if (!p) return;
  if (!quaseMelhorar(k)) { aviso(`Faltam ${p.copias - carta(k).c} cópias de ${CARTAS[k].nome}`); tocar("erro"); return; }
  if (prog().ouro < p.ouro) { aviso(`Falta ${fmt(p.ouro - prog().ouro)} de ouro`); tocar("erro"); return; }
  const r = melhorar(k);
  if (!r) return;
  tocar("nivel"); vibrar([20, 30, 40]);
  aviso(`${CARTAS[k].nome} subiu para o nível ${r.nivel}! +${r.xp} XP`, 2200);
  if (r.subiuRei) setTimeout(() => { tocar("vitoria"); aviso(`👑 Seu rei subiu para o nível ${r.subiuRei}!`, 2600); }, 900);
  abrirDetalhe(k);
  const el = $("detalheCarta"); el.classList.remove("nao"); void el.offsetWidth; el.animate([{ transform: "scale(1)" }, { transform: "scale(1.15) rotate(-3deg)" }, { transform: "scale(1)" }], { duration: 450 });
  atualizarRecursos(true);
  if (aba === "cartas") desenharCartas();
}

// ------------------------------------------------------------------ Loja
const ateMeiaNoite = () => { const d = new Date(), m = new Date(d); m.setHours(24, 0, 0, 0); const s = Math.floor((m - d) / 1000); return `${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}min`; };
function desenharLoja() {
  const pres = $("presente"), livre = presenteDisponivel();
  pres.className = `presente${livre ? "" : " pego"}`;
  pres.innerHTML = `<img src="img/ui/moedas.png" alt=""><span>${livre ? "Ouro e cartas grátis" : "Volte amanhã"}<small>${livre ? "Toque para pegar o presente de hoje" : `Novo presente em ${ateMeiaNoite()}`}</small></span><span>${livre ? "🎁" : "✓"}</span>`;
  const loja = lojaDoDia();
  $("lojaTempo").textContent = `novas em ${ateMeiaNoite()}`;
  $("ofertas").innerHTML = loja.ofertas.map((o, j) => `<div class="oferta${o.comprada ? " comprada" : ""}"><div class="${classeCarta(o.k)}" style="cursor:default">${htmlCarta(o.k, { qtd: o.n })}</div>
    <button class="botao ${o.comprada ? "" : "principal"} pequeno" data-j="${j}" ${o.comprada ? "disabled" : ""}>${o.comprada ? "Comprado" : `<img src="img/ui/moeda.png" alt="">${fmt(o.preco)}`}</button></div>`).join("");
  $("bausLoja").innerHTML = Object.entries(PRECO_BAU).map(([t, preco]) => `<div class="oferta"><img class="bauImg" src="img/ui/bau_${t}.png" alt=""><b>${BAUS[t].nome}</b>
    <button class="botao principal pequeno" data-bau="${t}"><img src="img/ui/moeda.png" alt="">${fmt(preco)}</button></div>`).join("");
}
function comprar(j) {
  ligarSom();
  const o = lojaDoDia().ofertas[j];
  if (!o || o.comprada) return;
  if (prog().ouro < o.preco) { aviso("Ouro insuficiente"); tocar("erro"); return; }
  if (!comprarOferta(j)) return;
  tocar("moeda"); aviso(`+${o.n} ${CARTAS[o.k].nome}`);
  atualizarRecursos(true); desenharLoja();
}
function comprarBauLoja(t) {
  ligarSom();
  if (prog().ouro < PRECO_BAU[t]) { aviso("Ouro insuficiente"); tocar("erro"); return; }
  const premio = comprarBau(t);
  if (!premio) return;
  atualizarRecursos(true);
  abrirTelaBau(premio, BAUS[t].nome, `bau_${t}`);
}

// ------------------------------------------------------------------ Trilha de troféus
function desenharTrilha() {
  const p = prog(), itens = [];
  let a = 0;
  const marcos = TRILHA.map((r, j) => ({ ...r, j }));
  for (let i = 0; i < ARENAS.length; i++) {
    const ar = ARENAS[i], prox = ARENAS[i + 1];
    itens.push(`<div class="arenaMarco${arenaDe(p.trofeus) === ar ? " aqui" : ""}"><div><small>Arena ${i + 1}</small><b>${ar.nome}</b></div><span>🏆 ${ar.min}</span></div>`);
    for (const m of marcos.filter(m => m.t >= ar.min && (!prox || m.t < prox.min))) {
      const feito = p.trilha.includes(m.j), chegou = p.trofeus >= m.t;
      const img = m.bau ? `img/ui/bau_${m.bau}.png` : "img/ui/moedas.png";
      const nome = m.bau ? BAUS[m.bau].nome : `${fmt(m.ouro)} de ouro`;
      const lado = feito ? `<span class="feito">✓</span>` : chegou ? `<button class="botao verde pequeno" data-j="${m.j}">Pegar</button>` : `<span class="tranca">🔒</span>`;
      itens.push(`<div class="marco${chegou ? " chegou" : " bloq"}" data-t="${m.t}"><img src="${img}" alt=""><div><b>${nome}</b><small>${feito ? "Resgatado" : chegou ? "Pronto para pegar!" : `Faltam ${m.t - p.trofeus} troféus`}</small></div>${lado}</div>`);
      a++;
    }
  }
  $("trilha").innerHTML = itens.join("");
}
function pegarTrilha(j) {
  ligarSom();
  const r = TRILHA[j];
  if (!trilhaPronta(j)) return;
  const premio = resgatarTrilha(j);
  if (!premio) return;
  atualizarRecursos(true);
  if (r.bau) abrirTelaBau(premio, BAUS[r.bau].nome, `bau_${r.bau}`);
  else { tocar("moeda"); aviso(`+${fmt(r.ouro)} de ouro`); desenharTrilha(); pontos(); }
}

// ------------------------------------------------------------------ janelas
function abrirModal(id) {
  for (const m of ["detalhe", "ajustes", "perfil", "como"]) $(m).hidden = m !== id;
  $("fundoModal").hidden = false;
}
export function fecharModais() { for (const m of ["detalhe", "ajustes", "perfil", "como"]) $(m).hidden = true; $("fundoModal").hidden = true; }
function marcarAjustes() {
  $("chaveSom").setAttribute("aria-checked", String(!estaMudo()));
  $("chaveMusica").setAttribute("aria-checked", String(musicaEstaLigada()));
  $("chaveSombras").setAttribute("aria-checked", String(!!api.cena.qualidadeAlta));
  $("chaveVibrar").setAttribute("aria-checked", String(vibrarLigado));
}
function abrirAjustes() { marcarAjustes(); abrirModal("ajustes"); }
function abrirPerfil() {
  const p = prog();
  const taxa = p.partidas ? Math.round(p.vitorias / p.partidas * 100) : 0;
  $("perfilNome").textContent = nomeEu();
  $("perfilRei").textContent = nivelRei();
  const itens = [["🏆", fmt(p.trofeus), "troféus"], ["⚔️", p.partidas, "partidas"], ["✅", p.vitorias, "vitórias"], ["📈", `${taxa}%`, "de vitórias"],
    ["🔥", p.melhorSeq, "melhor sequência"], ["👑", p.coroas, "coroas ganhas"], ["🎁", p.bausAbertos, "baús abertos"], ["🪙", fmt(p.ouroGanho), "ouro ganho"]];
  $("listaStats").innerHTML = itens.map(([e, v, t]) => `<div><b>${e} ${v}</b><small>${t}</small></div>`).join("");
  abrirModal("perfil");
}

// ------------------------------------------------------------------ abrir baú (toque a toque)
let fila = null;
export function abrirTelaBau(premio, nome, img, depois = null) {
  fila = { premio, passo: -1, img, depois, itens: [{ ouro: premio.ouro }, ...premio.cartas] .filter(x => x.ouro !== 0) };
  $("bauNome").textContent = nome;
  const bi = $("bauImg");
  bi.src = `img/ui/${img}.png`; bi.className = "treme"; bi.hidden = false;
  $("premio").hidden = true; $("resumo").hidden = true; $("palcoBau").classList.remove("menor"); $("palcoBau").hidden = false;
  $("bauTocar").textContent = "Toque para abrir"; $("restam").textContent = "";
  $("abrirBau").hidden = false;
  fecharModais();
}
function avancarBau() {
  if (!fila) return;
  ligarSom();
  const f = fila, bi = $("bauImg");
  f.passo++;
  if (f.passo === 0) { bi.src = `img/ui/${f.img}_aberto.png`.replace("_aberto_aberto", "_aberto"); bi.className = "abre"; tocar("bau"); vibrar(40); }
  if (f.passo < f.itens.length) {
    const it = f.itens[f.passo], pr = $("premio");
    if (it.ouro != null) { pr.innerHTML = `<img class="moedaGrande" src="img/ui/moedas.png" alt=""><b>${fmt(it.ouro)} de ouro</b>`; tocar("moeda"); }
    else {
      const p = proximoNivel(it.k), c = carta(it.k);
      pr.innerHTML = `<div class="${classeCarta(it.k)}">${htmlCarta(it.k, { nome: false, nivel: c.n })}</div><span class="vezes">×${it.n}</span><b>${CARTAS[it.k].nome}</b>${barraCopias(it.k)}${p && c.c >= p.copias ? `<span class="sobeNivel">▲ Pronta para melhorar!</span>` : ""}`;
      pr.querySelector(".copias").style.width = "170px";
      tocar(CARTAS[it.k].raridade === "epico" ? "epico" : "escolher");
      if (CARTAS[it.k].raridade === "epico") vibrar([30, 40, 60]);
    }
    pr.hidden = false; pr.style.animation = "none"; void pr.offsetWidth; pr.style.animation = "";
    $("palcoBau").classList.add("menor");
    $("restam").textContent = `${f.itens.length - f.passo - 1} restante${f.itens.length - f.passo - 1 === 1 ? "" : "s"}`;
    $("bauTocar").textContent = "Toque para continuar";
    return;
  }
  if (f.passo === f.itens.length) {
    $("premio").hidden = true; $("palcoBau").hidden = true;
    $("resumo").innerHTML = f.itens.map((it, i) => it.ouro != null ? `<div class="item" style="animation-delay:${i * 0.05}s"><div class="ouroItem"><img src="img/ui/moeda.png" alt="">${fmt(it.ouro)}</div></div>`
      : `<div class="item" style="animation-delay:${i * 0.05}s"><div class="${classeCarta(it.k)}">${htmlCarta(it.k, { nome: false, qtd: it.n })}</div></div>`).join("");
    $("resumo").hidden = false; $("restam").textContent = "";
    $("bauTocar").textContent = "Toque para fechar";
    return;
  }
  $("abrirBau").hidden = true;
  fila = null;
  atualizarRecursos(true);
  if (aba === "batalha") desenharBaus(); else irPara(aba, false);
  f.depois && f.depois();
}

// quando o jogo volta para o lobby depois de uma partida (o fim já mostrou o que ganhou)
export function depoisDaPartida() { atualizarRecursos(true); if (aba === "batalha") desenharBaus(); }
