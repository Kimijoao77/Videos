// Os cenários: cada arena (por troféus) tem o seu lugar, com luz, chão, rio, muros e tudo o que fica em volta.
// 0 Campo de Treino · 1 Vila dos Camponeses · 2 Floresta Sombria · 3 Castelo de Pedra · 4 Reino dos Dragões · 5 Lenda dos Reinos
// Tudo fica fora da área de jogo (só decoração) e em coordenadas do mundo, então não muda com o lado do jogador.
// As peças vêm de modelos/cenario.glb (KayKit Medieval Hexagon, CC0) e dos modelos de natureza que o jogo já usa.
import * as THREE from "three";
import { L, C, RIO0, RIO1, PONTES } from "./sim.js";
import { mergeGeometries } from "../vendor/BufferGeometryUtils.js";

export const TEMAS = [
  { nome: "Campo de Treino", morro: { grama: "#7cc25a", escura: "#5c9a45", pedra: "#9a9488", terra: "#b89a6a", alto: 7 }, praca: [176, 150, 112], fundo: "#9fd3ef", hemi: [0xffffff, 0x7d8a6a, 1.15], sol: [0xfff1d6, 1.9], neblina: "#a9d8ee",
    grama: ["#7FC65A", "#74BC51"], fora: "#5f9e47", terra: "#c4a46c", agua: ["#3FA9E0", "#2C8FD0"], tufo: [0x4f9a3a, 0x8fd468],
    flores: ["#ffffff", "#ffe066"], borda: "madeira", part: "folhas", tinta: 0xffffff },
  { nome: "Vila dos Camponeses", morro: { grama: "#86c55a", escura: "#669e48", pedra: "#a39c90", terra: "#c4a46c", alto: 6.5 }, praca: [186, 168, 138], fundo: "#a6d8f0", hemi: [0xffffff, 0x8a7d5a, 1.1], sol: [0xffe2b8, 2.0], neblina: "#b8dcea",
    grama: ["#86c55a", "#7bbb50"], fora: "#6aa14a", terra: "#c9a46a", agua: ["#46b0e3", "#2f92d2"], tufo: [0x5a9d3c, 0x9fdc6c],
    flores: ["#ff8fb1", "#ffffff", "#ffd23f", "#b48cff"], borda: "pedra", part: "petalas", tinta: 0xffffff },
  { nome: "Floresta Sombria", morro: { grama: "#4a7f40", escura: "#2f5a2d", pedra: "#5f6466", terra: "#6e5c45", alto: 8.5 }, praca: [104, 108, 112], fundo: "#2b3d4f", hemi: [0x9fb6ff, 0x2d3b2a, 0.95], sol: [0xb9c8ff, 1.1], neblina: "#33485a",
    grama: ["#4f8a45", "#477f3f"], fora: "#2f5a32", terra: "#7d6a4f", agua: ["#2c6f8f", "#215a77"], tufo: [0x2f5f2c, 0x5f9a4c],
    flores: ["#b9f3ff", "#d6b8ff"], cogumelos: true, borda: "madeira", part: "vagalumes", tinta: 0xc9d4ff },
  { nome: "Castelo de Pedra", morro: { grama: "#7ab45a", escura: "#5e8f48", pedra: "#a8a49c", terra: "#9a8a72", alto: 8 }, praca: [160, 158, 152], fundo: "#a9c6dc", hemi: [0xffffff, 0x7a7a70, 1.1], sol: [0xfff4e0, 1.9], neblina: "#b4c9d8",
    grama: ["#78b956", "#6fae4e"], fora: "#5e8f48", terra: "#a9a49a", pedras: true, agua: ["#3a9fd6", "#2a83bd"], tufo: [0x4f8a38, 0x8ccc62],
    flores: ["#ffffff"], borda: "muralha", part: "poeira", tinta: 0xffffff },
  { nome: "Reino dos Dragões", morro: { grama: "#5a4a40", escura: "#3a2e29", pedra: "#4a403c", terra: "#2e2420", alto: 9 }, praca: [92, 72, 64], fundo: "#3a1f1c", hemi: [0xffb08a, 0x3a2020, 0.85], sol: [0xffa36b, 1.7], neblina: "#4a2620",
    grama: ["#6e6250", "#655a49"], fora: "#3b302b", terra: "#4a3c36", lava: true, agua: ["#ff7a1a", "#ff3d00"], tufo: [0x5a4a35, 0x8a7550],
    flores: [], rachas: true, borda: "ruina", part: "brasas", tinta: 0x9a8a80 },
  { nome: "Lenda dos Reinos", morro: { grama: "#a4cc62", escura: "#d2bc6a", pedra: "#c8b89a", terra: "#d4b26a", alto: 7 }, praca: [214, 196, 160], fundo: "#f6c27a", hemi: [0xfff0d0, 0x8a6a4a, 1.15], sol: [0xffc27a, 2.1], neblina: "#f2c48a",
    grama: ["#8bc85c", "#80be53"], fora: "#6b9a45", terra: "#d8b46a", pedras: true, ouro: true, agua: ["#4fc0ea", "#36a2db"], tufo: [0x5d9a3c, 0xb7e070],
    flores: ["#ffd23f", "#ffffff", "#ff8fb1"], borda: "muralha", part: "brilhos", tinta: 0xfff2dc },
];

// número pseudoaleatório repetível (o cenário sai sempre igual)
function sorteio(semente) { let s = semente; return () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; }
const tex = (cv, rep) => { const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; if (rep) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rep, rep); } return t; };

// ------------------------------------------------------------------ chão da arena (desenhado num canvas)
function chaoArena(T, tema) {
  const P = 48, cv = document.createElement("canvas");
  cv.width = L * P; cv.height = C * P;
  const g = cv.getContext("2d"), r = sorteio(11);
  for (let y = 0; y < C; y++) for (let x = 0; x < L; x++) { g.fillStyle = (x + y) % 2 ? T.grama[1] : T.grama[0]; g.fillRect(x * P, y * P, P, P); }
  // manchas e fiapos de grama
  for (let k = 0; k < 2600; k++) {
    const x = r() * cv.width, y = r() * cv.height;
    g.fillStyle = r() < 0.5 ? "rgba(0,0,0,0.05)" : "rgba(255,255,255,0.05)";
    g.beginPath(); g.ellipse(x, y, 4 + r() * 14, 3 + r() * 8, r() * 3, 0, 7); g.fill();
  }
  g.lineWidth = 2;
  for (let k = 0; k < 2200; k++) {
    const x = r() * cv.width, y = r() * cv.height;
    g.strokeStyle = r() < 0.5 ? "rgba(20,60,10,0.18)" : "rgba(230,255,190,0.16)";
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 5, y - 5 - r() * 5); g.stroke();
  }
  // caminhos: das pontes até as torres e a frente dos castelos
  const caminho = (pts, larg) => {
    for (const [x0, y0, x1, y1] of pts) {
      const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 4);
      for (let i = 0; i <= n; i++) {
        const q = i / n, x = (x0 + (x1 - x0) * q) * P, y = (y0 + (y1 - y0) * q) * P;
        for (let j = 0; j < 3; j++) {
          g.fillStyle = T.terra; g.globalAlpha = 0.35 + r() * 0.25;
          g.beginPath(); g.arc(x + (r() - 0.5) * larg * P * 0.9, y + (r() - 0.5) * P * 0.3, larg * P * (0.35 + r() * 0.2), 0, 7); g.fill();
        }
      }
    }
    g.globalAlpha = 1;
  };
  const trilhas = [];
  for (const px of PONTES) trilhas.push([px, 6, px, RIO0], [px, RIO1, px, C - 6]);
  trilhas.push([3, 6, 15, 6], [3, C - 6, 15, C - 6], [9, 3.5, 9, 6], [9, C - 3.5, 9, C - 6]);
  caminho(trilhas, 1.8);
  if (T.pedras) {                       // calçamento de pedra nos caminhos
    for (const [x0, y0, x1, y1] of trilhas) {
      const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 3);
      for (let i = 0; i <= n; i++) for (let j = -2; j <= 2; j++) {
        const q = i / n, hz = x0 === x1;
        const x = (x0 + (x1 - x0) * q + (hz ? j * 0.33 : 0)) * P, y = (y0 + (y1 - y0) * q + (hz ? 0 : j * 0.33)) * P;
        const c = 150 + Math.floor(r() * 50);
        g.fillStyle = T.ouro && r() < 0.25 ? `rgb(${c + 50},${c + 25},${c - 60})` : `rgb(${c},${c - 4},${c - 12})`;
        g.beginPath(); g.roundRect(x - 6 - r() * 3, y - 6 - r() * 3, 11 + r() * 4, 11 + r() * 4, 4); g.fill();
        g.strokeStyle = "rgba(0,0,0,0.18)"; g.lineWidth = 1.5; g.stroke();
      }
    }
  }
  // pedrinhas
  for (let k = 0; k < 260; k++) {
    const x = r() * cv.width, y = r() * cv.height, c = 120 + r() * 60;
    g.fillStyle = `rgba(${c},${c - 6},${c - 14},0.8)`;
    g.beginPath(); g.ellipse(x, y, 2 + r() * 4, 1.5 + r() * 3, r() * 3, 0, 7); g.fill();
  }
  // flores
  for (let k = 0; k < (T.flores.length ? 520 : 0); k++) {
    const x = r() * cv.width, y = r() * cv.height;
    if (Math.abs(y / P - (RIO0 + RIO1) / 2) < 2) continue;
    g.fillStyle = T.flores[Math.floor(r() * T.flores.length)];
    for (let j = 0; j < 3; j++) { g.beginPath(); g.arc(x + (r() - 0.5) * 10, y + (r() - 0.5) * 10, 2 + r() * 1.5, 0, 7); g.fill(); }
  }
  if (T.cogumelos) for (let k = 0; k < 70; k++) {
    const x = r() * cv.width, y = r() * cv.height;
    g.fillStyle = "#f2efe6"; g.fillRect(x - 1.5, y, 3, 5);
    g.fillStyle = r() < 0.5 ? "#d9473f" : "#9e6bd6"; g.beginPath(); g.ellipse(x, y, 6, 4, 0, Math.PI, 0); g.fill();
  }
  if (T.rachas) {                        // terra rachada com brilho de lava
    for (let k = 0; k < 46; k++) {
      let x = r() * cv.width, y = r() * cv.height;
      g.strokeStyle = "rgba(255,110,30,0.55)"; g.lineWidth = 2 + r() * 2; g.shadowColor = "#ff6a00"; g.shadowBlur = 8;
      g.beginPath(); g.moveTo(x, y);
      for (let j = 0; j < 5; j++) { x += (r() - 0.5) * 50; y += (r() - 0.5) * 50; g.lineTo(x, y); }
      g.stroke();
    }
    g.shadowBlur = 0;
  }
  // terra gasta em volta das torres
  for (const [x, y, rr] of [[3.5, 6.5, 2], [14.5, 6.5, 2], [9, 3, 2.6], [3.5, C - 6.5, 2], [14.5, C - 6.5, 2], [9, C - 3, 2.6]]) {
    const gr = g.createRadialGradient(x * P, y * P, rr * P * 0.4, x * P, y * P, rr * P);
    gr.addColorStop(0, "rgba(60,40,20,0.22)"); gr.addColorStop(1, "rgba(60,40,20,0)");
    g.fillStyle = gr; g.beginPath(); g.arc(x * P, y * P, rr * P, 0, 7); g.fill();
  }
  // margens do rio (o rio de verdade é outra peça, por cima)
  g.fillStyle = T.lava ? "#2a1a16" : "#C9B58A";
  g.fillRect(0, RIO0 * P - 8, L * P, (RIO1 - RIO0) * P + 16);
  for (let k = 0; k < 120; k++) {
    const x = r() * cv.width, y = (r() < 0.5 ? RIO0 * P - 8 : RIO1 * P + 8) + (r() - 0.5) * 10, c = 110 + r() * 70;
    g.fillStyle = `rgb(${c},${c - 8},${c - 20})`; g.beginPath(); g.ellipse(x, y, 4 + r() * 6, 3 + r() * 4, r() * 3, 0, 7); g.fill();
  }
  return tex(cv);
}

// ------------------------------------------------------------------ água (ou lava) com shader
const AGUA_VERT = `#include <common>
#include <fog_pars_vertex>
uniform float uTempo; varying vec2 vUv; varying vec3 vMundo;
void main() {
  vUv = uv;
  vec4 mundo = modelMatrix * vec4(position, 1.0);
  float meio = 1.0 - abs(uv.y - 0.5) * 2.0;
  mundo.y += (sin(mundo.x * 1.3 + uTempo * 2.0) * 0.03 + sin(mundo.x * 2.9 - uTempo * 1.6 + mundo.z * 3.0) * 0.015) * meio;
  vMundo = mundo.xyz;
  vec4 mvPosition = viewMatrix * mundo;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;
const AGUA_FRAG = `#include <common>
#include <fog_pars_fragment>
uniform float uTempo, uLava; uniform vec3 uFundo, uRaso, uCeu, uEspuma;
varying vec2 vUv; varying vec3 vMundo;
float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float ruido(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y); }
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { s += a * ruido(p); p = p * 2.03 + 1.7; a *= 0.5; } return s; }
void main() {
  vec2 p = vMundo.xz;
  float borda = abs(vUv.y - 0.5) * 2.0;
  vec2 fluxo = vec2(uTempo * 0.45, 0.0);
  float n1 = fbm(p * 1.3 - fluxo), n2 = fbm(p * 2.7 + vec2(-uTempo * 0.6, uTempo * 0.15));
  vec3 cor;
  if (uLava > 0.5) {
    float crosta = smoothstep(0.45, 0.66, fbm(p * 1.6 - fluxo * 0.35));
    vec3 quente = mix(vec3(1.0, 0.22, 0.02), vec3(1.0, 0.72, 0.18), smoothstep(0.35, 0.8, n2));
    cor = mix(quente * (1.4 + 0.3 * sin(uTempo * 2.0 + p.x)), vec3(0.06, 0.03, 0.02), crosta * 0.88);
    cor = mix(cor, vec3(0.05, 0.02, 0.02), smoothstep(0.8, 1.0, borda));
  } else {
    cor = mix(uFundo, uRaso, smoothstep(0.3, 1.0, borda));
    cor = mix(cor, uCeu, smoothstep(0.5, 0.85, n1 * 0.7 + n2 * 0.5) * 0.4);          // o céu refletido nas cristas
    float brilho = smoothstep(0.86, 0.93, n2 * 0.55 + n1 * 0.6) * (1.0 - borda * 0.7);
    cor += vec3(1.0, 0.98, 0.9) * brilho * 1.2;                                       // reflexos do sol (brilham com o bloom)
    float faixa = fract(n1 * 4.0 - uTempo * 0.25);
    cor += uEspuma * smoothstep(0.46, 0.5, faixa) * smoothstep(0.54, 0.5, faixa) * 0.12 * (1.0 - borda);
    float espuma = smoothstep(0.72, 0.97, borda + (n2 - 0.5) * 0.4);                 // espuma nas margens
    cor = mix(cor, uEspuma, espuma * 0.9);
  }
  gl_FragColor = vec4(cor, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  #include <fog_fragment>
}`;
function materialAgua(T) {
  const uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
    uTempo: { value: 0 }, uLava: { value: T.lava ? 1 : 0 },
    uFundo: { value: new THREE.Color(T.agua[1]).multiplyScalar(0.85) }, uRaso: { value: new THREE.Color(T.agua[0]) },
    uCeu: { value: new THREE.Color(T.neblina) }, uEspuma: { value: new THREE.Color("#f2fbff") },
  }]);
  return new THREE.ShaderMaterial({ uniforms, vertexShader: AGUA_VERT, fragmentShader: AGUA_FRAG, fog: true });
}

// textura da água (ou lava) que corre (antes do shader; fica de reserva)
function texturaRio(T) {
  const cv = document.createElement("canvas"); cv.width = 256; cv.height = 64;
  const g = cv.getContext("2d"), r = sorteio(5);
  const gr = g.createLinearGradient(0, 0, 0, 64); gr.addColorStop(0, T.agua[0]); gr.addColorStop(0.5, T.agua[1]); gr.addColorStop(1, T.agua[0]);
  g.fillStyle = gr; g.fillRect(0, 0, 256, 64);
  for (let k = 0; k < 40; k++) {
    const x = r() * 256, y = 6 + r() * 52, w = 10 + r() * 26;
    g.strokeStyle = T.lava ? `rgba(255,${200 + r() * 55},90,0.7)` : "rgba(255,255,255,0.35)"; g.lineWidth = T.lava ? 2 + r() * 2 : 1.5 + r();
    for (const dx of [0, -256, 256]) { g.beginPath(); g.moveTo(x + dx, y); g.quadraticCurveTo(x + dx + w / 2, y - 3, x + dx + w, y); g.stroke(); }
  }
  if (T.lava) for (let k = 0; k < 30; k++) { g.fillStyle = "rgba(60,20,10,0.5)"; const x = r() * 256, y = r() * 64; g.beginPath(); g.ellipse(x, y, 6 + r() * 10, 3 + r() * 4, 0, 0, 7); g.fill(); }
  const t = tex(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}

// 1.x: em volta da arena é uma praça de pedra (pedido do João: construções em volta, não tudo verde)
function texturaFora(T) {
  const cv = document.createElement("canvas"); cv.width = cv.height = 256;
  const g = cv.getContext("2d"), r = sorteio(3), [fr, fg, fb] = T.praca || [150, 140, 125];
  g.fillStyle = `rgb(${fr * 0.62},${fg * 0.62},${fb * 0.62})`; g.fillRect(0, 0, 256, 256);   // rejunte
  // paralelepípedos de tamanhos diferentes, fileira por fileira (a textura emenda nos quatro lados)
  for (let y = 0; y < 256; y += 16) {
    let x = -r() * 20;
    while (x < 256) {
      const w = 12 + r() * 14, v = 0.84 + r() * 0.26;
      g.fillStyle = `rgb(${Math.min(255, fr * v)},${Math.min(255, fg * v)},${Math.min(255, fb * v)})`;
      for (const ox of [0, 256, -256]) for (const oy of [0, 256, -256]) { g.beginPath(); g.roundRect(x + 1.2 + ox, y + 1.2 + oy, w - 2.4, 13.6, 5); g.fill(); }
      x += w;
    }
  }
  for (let k = 0; k < 500; k++) {                       // sujeira e brilho nas pedras
    g.fillStyle = r() < 0.6 ? "rgba(0,0,0,0.08)" : "rgba(255,255,255,0.07)";
    const x = r() * 256, y = r() * 256; g.beginPath(); g.ellipse(x, y, 2 + r() * 7, 1 + r() * 4, r() * 3, 0, 7); g.fill();
  }
  return tex(cv, 110);
}

function texturaFundo(T) {
  const cv = document.createElement("canvas"); cv.width = 4; cv.height = 128;
  const g = cv.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 128);
  const c = new THREE.Color(T.fundo);
  gr.addColorStop(0, "#" + c.clone().multiplyScalar(0.75).getHexString()); gr.addColorStop(1, T.neblina);
  g.fillStyle = gr; g.fillRect(0, 0, 4, 128);
  return tex(cv);
}

// tufos de grama 3D (três folhas), muitos de uma vez
function geoTufo() {
  const pos = [], cor = [];
  for (let k = 0; k < 3; k++) {
    const a = k * 2.1, ca = Math.cos(a), sa = Math.sin(a), inc = 0.25;
    pos.push(-0.06 * ca, 0, -0.06 * sa, 0.06 * ca, 0, 0.06 * sa, inc * sa, 1, -inc * ca);
    cor.push(0, 0, 0, 0, 0, 0, 1, 1, 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("cor", new THREE.Float32BufferAttribute(cor, 3));
  return g;
}

// ------------------------------------------------------------------ monta tudo
export function montarCenario(cena, i, pecas) {
  const T = TEMAS[i] || TEMAS[0];
  const grupo = new THREE.Group();
  const r = sorteio(101 + i * 7);
  const animados = [];   // { o, f(o, t, dt) }
  const sombra = (o, recebe = false) => { o.traverse(m => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = recebe; } }); return o; };

  // luz e ar
  cena.hemi.color.set(T.hemi[0]); cena.hemi.groundColor.set(T.hemi[1]); cena.hemi.intensity = T.hemi[2];
  cena.sol.color.set(T.sol[0]); cena.sol.intensity = T.sol[1];
  cena.cena.background = texturaFundo(T);
  cena.cena.fog = new THREE.Fog(T.neblina, 60, 140);
  cena.matPeca.color.set(T.tinta);

  // chão da arena, chão de fora e o rio que atravessa tudo
  const chao = new THREE.Mesh(new THREE.PlaneGeometry(L, C).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ map: chaoArena(T, T) }));
  chao.receiveShadow = true; grupo.add(chao);
  const fora = new THREE.Mesh(new THREE.PlaneGeometry(420, 420).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ map: texturaFora(T) }));
  fora.position.y = -0.04; fora.receiveShadow = true; grupo.add(fora);
  const zRio = C / 2 - (RIO0 + RIO1) / 2, largRio = RIO1 - RIO0;
  const matRio = materialAgua(T);
  const rio = new THREE.Mesh(new THREE.PlaneGeometry(240, largRio, 240, 6).rotateX(-Math.PI / 2), matRio);
  rio.position.set(0, 0.012, zRio); grupo.add(rio);
  animados.push({ f: (t) => { matRio.uniforms.uTempo.value = t; } });
  if (T.lava) {
    const luz = new THREE.PointLight(0xff5a1a, 3, 14, 1.6); luz.position.set(0, 1.5, zRio); grupo.add(luz);
    animados.push({ f: (t) => { luz.intensity = 2.5 + Math.sin(t * 3.1) * 0.6 + Math.sin(t * 7.3) * 0.3; } });
  }
  // barranco do rio fora da arena (as duas margens)
  const margem = new THREE.MeshLambertMaterial({ color: T.lava ? "#2a1a16" : "#bda67a" });
  for (const s of [-1, 1]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(240, 0.5).rotateX(-Math.PI / 2), margem);
    m.position.set(0, -0.01, zRio + s * (largRio / 2 + 0.2)); grupo.add(m);
  }

  // ---- medidas da arquibancada e o relevo em volta (um vale: morros que sobem a partir da arquibancada)
  const ALT = 0.46, LARG = 1.0, NIV = 5, X0 = L / 2 + 1.2, Z0 = C / 2 + 1.2;
  const XF = X0 + NIV * LARG, ZF = Z0 + NIV * LARG, HTOPO = NIV * ALT;
  const hash = (x, z) => { const v = Math.sin(x * 127.1 + z * 311.7 + i * 17.3) * 43758.5453; return v - Math.floor(v); };
  const vruido = (x, z) => { const xi = Math.floor(x), zi = Math.floor(z), fx = x - xi, fz = z - zi, u = fx * fx * (3 - 2 * fx), v = fz * fz * (3 - 2 * fz);
    const a = hash(xi, zi), b = hash(xi + 1, zi), c = hash(xi, zi + 1), d = hash(xi + 1, zi + 1); return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v; };
  const fbm2 = (x, z) => vruido(x, z) * 0.5 + vruido(x * 2.1 + 5, z * 2.1 + 3) * 0.3 + vruido(x * 4.3 + 11, z * 4.3 + 7) * 0.2;
  const M = T.morro;
  const altChao = (x, z) => {
    if (Math.abs(x) <= XF + 0.02 && Math.abs(z) <= ZF + 0.02) return 0;     // dentro: a arena e a arquibancada têm chão próprio
    const d = Math.hypot(Math.max(Math.abs(x) - XF, 0), Math.max(Math.abs(z) - ZF, 0));
    let h = HTOPO + 0.12 + M.alto * (1 - Math.exp(-d / 6.5)) + (fbm2(x * 0.12, z * 0.12) - 0.5) * (0.4 + Math.min(d, 14) * 0.28);
    const rio = Math.abs(z - zRio), larg = largRio / 2 + 0.5 + d * 0.06;        // o rio sai entre os morros
    if (rio < larg + 2.4) h = h * Math.min(1, Math.max(0, (rio - larg) / 2.4)) - 0.18 * (rio < larg ? 1 : 0);
    return h;
  };

  // helpers para pôr peças
  const ocupado = [];             // retângulos [x0, x1, z0, z1] das arquibancadas
  const livre = (x, z) => !ocupado.some(([a, b, c, d]) => x > a && x < b && z > c && z < d);
  const dentro = (x, z, folga = 0.8) => Math.abs(x) < L / 2 + folga && Math.abs(z) < C / 2 + folga;
  const noRio = (z, folga = 0.6) => Math.abs(z - zRio) < largRio / 2 + folga;
  const por = (nome, x, z, esc = 1, giro = r() * 6.28, y = 0) => {
    if (y === 0 && !livre(x, z)) return null;
    if (y === 0) y = altChao(x, z) - 0.05;
    const o = pecas(nome); if (!o) return null;
    o.position.set(x, y, z); o.scale.setScalar(esc); o.rotation.y = giro; grupo.add(sombra(o)); return o;
  };
  const espalhar = (nomes, n, area, esc, extra) => {     // n peças em lugares livres de uma área [x0,x1,z0,z1]
    let feitos = 0, tent = 0;
    while (feitos < n && tent++ < n * 30) {
      const x = area[0] + r() * (area[1] - area[0]), z = area[2] + r() * (area[3] - area[2]);
      if (dentro(x, z, 1.4) || noRio(z, 1.2)) continue;
      const o = por(nomes[Math.floor(r() * nomes.length)], x, z, esc[0] + r() * (esc[1] - esc[0]));
      if (o) { feitos++; extra && extra(o); }
    }
  };
  const lados = (f) => { for (const s of [-1, 1]) f(s); };

  // ---- borda da arena
  const zBorda = [-C / 2 - 0.35, C / 2 + 0.35];
  if (T.borda === "muralha" || T.borda === "ruina") {
    const quebrado = T.borda === "ruina";
    const peca = (x, z, rot, esc) => { if (quebrado && r() < 0.25) return; const o = por("muro", x, z, esc, rot); if (o && quebrado) o.rotation.z = (r() - 0.5) * 0.12; };
    for (let z = -C / 2 + 1; z <= C / 2 - 1; z += 2) { if (noRio(z, 0.3)) continue; for (const s of [-1, 1]) peca(s * (L / 2 + 0.45), z, Math.PI / 2, 0.55 * 1); }
    for (let x = -L / 2 + 1; x <= L / 2 - 1; x += 2) peca(x, zBorda[0] - 0.1, 0, 0.55);
    for (let x = -L / 2 + 1; x <= L / 2 - 1; x += 2) { const o = por("cerca_pedra", x, zBorda[1], 1.6, Math.PI / 2); }
    if (!quebrado) for (const s of [-1, 1]) for (const z of [-C / 2 - 0.4, C / 2 + 0.4, zRio - largRio / 2 - 0.6, zRio + largRio / 2 + 0.6]) por("torre_vigia", s * (L / 2 + 0.6), z, 0.55, 0);
  } else {
    const nome = T.borda === "pedra" ? "cerca_pedra" : "cerca_madeira";
    const esc = T.borda === "pedra" ? 1.7 : 1.5, passo = 1.15 * esc;
    // a peça do pacote é a borda de um hexágono: a cerca fica a 1 unidade do centro da peça, por isso o deslocamento
    for (const s of [-1, 1]) for (let z = -C / 2 + passo / 2; z < C / 2; z += passo) {
      if (noRio(z, 0.4)) continue;
      por(nome, s * (L / 2 + 0.3) + esc, z, esc, 0);
    }
    for (const zb of zBorda) for (let x = -L / 2 + passo / 2; x < L / 2; x += passo) por(nome, x, zb - esc, esc, Math.PI / 2);
  }

  // moitas de grama nos morros (balançam com o vento, como as da arena)
  const moitas = [];
  for (let k = 0; k < 420; k++) {
    const a = r() * Math.PI * 2, d = 0.4 + Math.pow(r(), 1.2) * 16, bx = Math.cos(a), bz = Math.sin(a), esc = Math.max(Math.abs(bx) / (XF + d), Math.abs(bz) / (ZF + d));
    const x = bx / esc, z = bz / esc; if (Math.abs(z - zRio) < largRio / 2 + 0.8) continue;
    moitas.push([x, altChao(x, z), z]);
  }
  // ---- tufos de grama e flores (dentro e fora da arena)
  const geo = geoTufo(), n = 440;
  const matTufo = new THREE.MeshLambertMaterial({ side: THREE.DoubleSide });
  const uVento = { value: 0 };
  animados.push({ f: (t) => { uVento.value = t; } });
  const cb = new THREE.Color(T.tufo[0]), cp = new THREE.Color(T.tufo[1]);
  matTufo.onBeforeCompile = (sh) => {
    sh.uniforms.uVento = uVento;
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nattribute vec3 cor;\nvarying float vAlt;\nuniform float uVento;").replace("#include <begin_vertex>", "#include <begin_vertex>\nvAlt = cor.x;")
      .replace("#include <project_vertex>", `vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_INSTANCING
mvPosition = instanceMatrix * mvPosition;
#endif
float bal = sin(uVento * 1.8 + mvPosition.x * 0.45 + mvPosition.z * 0.3) * 0.65 + sin(uVento * 3.1 + mvPosition.x * 1.1) * 0.25;
mvPosition.x += bal * vAlt * vAlt * 0.09; mvPosition.z += bal * vAlt * vAlt * 0.04;
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`);
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", `#include <common>\nvarying float vAlt;`)
      .replace("vec4 diffuseColor = vec4( diffuse, opacity );", `vec4 diffuseColor = vec4( mix(vec3(${cb.r.toFixed(3)},${cb.g.toFixed(3)},${cb.b.toFixed(3)}), vec3(${cp.r.toFixed(3)},${cp.g.toFixed(3)},${cp.b.toFixed(3)}), vAlt), opacity );`);
  };
  const tufos = new THREE.InstancedMesh(geo, matTufo, n + moitas.length);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), v = new THREE.Vector3(), e = new THREE.Vector3();
  let k = 0;
  const torres = [[-5.5, 9.5], [5.5, 9.5], [0, 13], [-5.5, -9.5], [5.5, -9.5], [0, -13]];
  for (let t = 0; t < n * 4 && k < n; t++) {
    const naArena = true;                 // fora da arena agora é praça de pedra
    const x = naArena ? (r() - 0.5) * (L - 0.6) : (r() - 0.5) * 60, z = naArena ? (r() - 0.5) * (C - 0.6) : -C / 2 - 30 + r() * (C + 34);
    if (!naArena && dentro(x, z, 0.3)) continue;
    if (noRio(z, 0.3)) continue;
    if (naArena && (PONTES.some(px => Math.abs(x - (px - L / 2)) < 1.4) || Math.abs(Math.abs(z) - (C / 2 - 6)) < 1 || torres.some(([a, b]) => Math.hypot(x - a, z - b) < 2.2))) continue;
    v.set(x, 0, z); q.setFromAxisAngle(e.set(0, 1, 0), r() * 6.28);
    const h = (naArena ? 0.16 : 0.28) + r() * 0.16; m4.compose(v, q, e.set(h * 1.4, h, h * 1.4));
    tufos.setMatrixAt(k++, m4);
  }
  for (const [x, y, z] of moitas) { v.set(x, y - 0.02, z); q.setFromAxisAngle(e.set(0, 1, 0), r() * 6.28); const h = 0.32 + r() * 0.3; m4.compose(v, q, e.set(h * 1.5, h, h * 1.5)); tufos.setMatrixAt(k++, m4); }
  tufos.count = k; grupo.add(tufos);

  // ---- a arena fica num vale (pedido do João: fechada e cheia, mas com cara de natureza): degraus de grama e pedra
  // com a torcida sentada em bancos de madeira, e morros com árvores, pedras e algumas casas subindo atrás
  const corM = (h) => new THREE.Color(h);
  const matPedra = new THREE.MeshLambertMaterial({ color: corM(M.pedra) }), matPedra2 = new THREE.MeshLambertMaterial({ color: corM(M.pedra).multiplyScalar(0.86) });
  const matGrama = new THREE.MeshLambertMaterial({ color: corM(M.grama) }), matBanco = new THREE.MeshLambertMaterial({ color: 0x8a5a32 });
  const lugares = [];               // onde senta cada torcedor: [x, y, z, time]
  const caixa = (cx, cy, cz, sx, sy, sz, mat, sombraP = true) => { const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), mat); m.position.set(cx, cy, cz); m.castShadow = sombraP; m.receiveShadow = true; grupo.add(m); return m; };
  const timeDe = (z) => (z > zRio ? 0 : 1);                       // embaixo (perto da câmera) é o seu lado: torcida azul
  // um degrau: pedra na frente, grama em cima e um banco comprido na beira
  const degrau = (cx, cz, sx, sz, k, eixoX) => {
    const h = (k + 1) * ALT;
    caixa(cx, h / 2, cz, sx, h, sz, k % 2 ? matPedra2 : matPedra, k === NIV - 1);
    caixa(cx, h + 0.03, cz, sx + 0.02, 0.06, sz + 0.02, matGrama, false);
    const bx = eixoX ? cx - Math.sign(cx) * (LARG * 0.5 - 0.22) : cx, bz = eixoX ? cz : cz - Math.sign(cz) * (LARG * 0.5 - 0.22);
    caixa(bx, h + 0.16, bz, eixoX ? 0.26 : sx - 0.4, 0.1, eixoX ? sz - 0.4 : 0.26, matBanco, false);
    return [h + 0.2, bx, bz];
  };
  lados(sx => {
    for (let k = 0; k < NIV; k++) {
      const [y, bx] = degrau(sx * (X0 + (k + 0.5) * LARG), 0, LARG, 2 * Z0 - 0.2, k, true);
      for (let z = -Z0 + 0.4; z < Z0 - 0.3; z += 0.48 + r() * 0.12) if (r() < 0.86) lugares.push([bx + (r() - 0.5) * 0.12, y, z, timeDe(z)]);
    }
    ocupado.push(sx < 0 ? [-XF - 0.6, -X0 + 0.2, -ZF - 0.6, ZF + 0.6] : [X0 - 0.2, XF + 0.6, -ZF - 0.6, ZF + 0.6]);
  });
  for (const sz of [-1, 1]) {
    for (let k = 0; k < NIV; k++) {
      const [y, , bz] = degrau(0, sz * (Z0 + (k + 0.5) * LARG), 2 * XF - 0.1, LARG, k, false);
      for (let x = -XF + 0.4; x < XF - 0.3; x += 0.48 + r() * 0.12) {
        if (sz < 0 && Math.abs(x) < 1.7 && k >= 2) continue;          // o camarote
        if (Math.abs(x) > X0 - 0.2 && Math.abs(x) < X0 + 0.2) continue;
        if (r() < 0.86) lugares.push([x, y, bz + (r() - 0.5) * 0.12, sz > 0 ? 0 : 1]);
      }
    }
    ocupado.push([-XF - 0.6, XF + 0.6, sz < 0 ? -ZF - 0.6 : Z0 - 0.2, sz < 0 ? -Z0 + 0.2 : ZF + 0.6]);
  }
  // camarote do rei (de madeira, com toldo vermelho e dourado), no meio dos degraus de cima
  {
    const zc = -(Z0 + 3.5 * LARG), h = 3 * ALT + 0.3;
    caixa(0, h / 2, zc, 3.4, h, 2.2, matBanco);
    for (const x of [-1.5, 1.5]) caixa(x, h + 0.9, zc - 0.9, 0.16, 1.8, 0.16, matBanco);
    const cv = document.createElement("canvas"); cv.width = 128; cv.height = 32; const g = cv.getContext("2d");
    for (let k = 0; k < 8; k++) { g.fillStyle = k % 2 ? "#f2c14e" : "#c0392b"; g.fillRect(k * 16, 0, 16, 32); }
    const toldo = new THREE.Mesh(new THREE.PlaneGeometry(3.6, 1.6), new THREE.MeshLambertMaterial({ map: tex(cv), side: THREE.DoubleSide }));
    toldo.position.set(0, h + 1.85, zc - 0.3); toldo.rotation.x = -Math.PI / 2 + 0.35; toldo.castShadow = true; grupo.add(toldo);
    for (const x of [-0.7, 0.7]) lugares.push([x, h, zc + 0.3, 1]);
  }
  // os morros: uma malha só, com cor por vértice (grama clara e escura, terra e pedra nas partes íngremes e no alto)
  {
    const W = 104, D = 116, geo = new THREE.PlaneGeometry(W, D, 140, 156).rotateX(-Math.PI / 2), pos = geo.attributes.position;
    for (let k = 0; k < pos.count; k++) { const x = pos.getX(k), z = pos.getZ(k); pos.setY(k, Math.abs(x) <= XF + 0.02 && Math.abs(z) <= ZF + 0.02 ? -0.6 : altChao(x, z)); }
    geo.computeVertexNormals();
    const nor = geo.attributes.normal, cores = new Float32Array(pos.count * 3);
    const cG = corM(M.grama), cE = corM(M.escura), cP = corM(M.pedra), cT = corM(M.terra), tmp = new THREE.Color();
    for (let k = 0; k < pos.count; k++) {
      const x = pos.getX(k), y = pos.getY(k), z = pos.getZ(k), ny = nor.getY(k), n = fbm2(x * 0.35, z * 0.35);
      tmp.copy(cG).lerp(cE, Math.min(1, Math.max(0, (n - 0.35) * 2.2)));
      if (n > 0.66) tmp.lerp(cT, Math.min(1, (n - 0.66) * 3));                                   // terra
      const ingreme = Math.min(1, Math.max(0, (0.86 - ny) * 5)), alto = Math.min(1, Math.max(0, (y - HTOPO - M.alto * 0.82) * 0.8));
      tmp.lerp(cP, Math.max(ingreme, alto, Math.abs(z - zRio) < largRio / 2 + 1.4 ? 0.85 : 0));    // pedra
      cores[k * 3] = tmp.r; cores[k * 3 + 1] = tmp.g; cores[k * 3 + 2] = tmp.b;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(cores, 3));
    const morros = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true }));
    morros.receiveShadow = true; grupo.add(morros);
  }
  // natureza nos morros: árvores em grupos, pedras e moitas; algumas casas e torres no meio
  const ARV = i === 4 ? ["rocha_c", "rocha_d", "rocha_e", "toco", "tocos"] : i === 2 ? ["arvores_g", "arvores_m", "arvores_g", "rocha_c"] : ["arvores_g", "arvores_m", "arvores_p", "arvores_m", "rocha_c", "rocha_e"];
  const naturezaEm = (x, z) => {
    if (Math.abs(z - zRio) < largRio / 2 + 1.2) return;
    const nome = ARV[Math.floor(r() * ARV.length)], esc = nome.startsWith("arvores") ? 2.4 + r() * 0.9 : nome.startsWith("rocha") ? 2.6 + r() * 1.6 : 2.4 + r();
    por(nome, x, z, esc);
  };
  for (let k = 0; k < 230; k++) {
    const a = r() * Math.PI * 2, d = 0.8 + Math.pow(r(), 1.4) * 22;                     // mais perto da arquibancada, mais denso
    const bx = Math.cos(a), bz = Math.sin(a), esc = Math.max(Math.abs(bx) / (XF + d), Math.abs(bz) / (ZF + d));
    naturezaEm(bx / esc, bz / esc);
  }
  const RUA = [["tenda", "arquearia", "tenda", "celeiro"], ["casa_a", "taverna", "casa_b", "moinho", "casa_c", "igreja"], ["casa_c", "serraria", "celeiro"],
    ["torre_vigia", "igreja", "quartel", "torre_vigia"], ["torre_vigia", "ferreiro", "torre_vigia"], ["igreja", "casa_b", "torre_vigia", "mercado"]][i];
  for (let k = 0; k < 9; k++) {
    const a = (k / 9) * Math.PI * 2 + r() * 0.4, d = 2.5 + r() * 5, bx = Math.cos(a), bz = Math.sin(a), esc = Math.max(Math.abs(bx) / (XF + d), Math.abs(bz) / (ZF + d));
    const x = bx / esc, z = bz / esc;
    if (Math.abs(z - zRio) < largRio / 2 + 2.5) continue;
    const nome = RUA[k % RUA.length], o = por(nome, x, z, nome === "torre_vigia" ? 1.5 : 2.7, Math.atan2(-x, -z) + (r() - 0.5) * 0.4);
    if (o && nome === "moinho") moinhoGira(o, 0.8);
  }
  // bandeiras dos times na beira de cima dos degraus
  lados(sx => { for (let z = -ZF + 2.5; z < ZF - 2; z += 4.2) bandeira(timeDe(z) === 0 ? "bandeira_azul" : "bandeira_vermelho", sx * (XF + 0.9), z, 4.4); });
  for (const sz of [-1, 1]) for (const x of [-7, -3.5, 3.5, 7]) bandeira(sz > 0 ? "bandeira_azul" : "bandeira_vermelho", x, sz * (ZF + 0.9), 4.4);
  // o público: corpo e cabeça (dois InstancedMesh), pulando de leve; quando uma torre cai, todo mundo pula
  const uPub = { tempo: { value: 0 }, festa: { value: 0 } };
  const matPub = () => {
    const m = new THREE.MeshLambertMaterial();
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uTempoP = uPub.tempo; sh.uniforms.uFesta = uPub.festa;
      sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nuniform float uTempoP, uFesta;").replace("#include <project_vertex>", `vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_INSTANCING
mvPosition = instanceMatrix * mvPosition;
float fase = instanceMatrix[3].x * 1.7 + instanceMatrix[3].z * 2.3;
float mexe = step(0.4, fract(fase * 0.37)) + uFesta;
mvPosition.y += abs(sin(uTempoP * (2.4 + uFesta * 5.0) + fase)) * (0.035 + uFesta * 0.24) * min(1.0, mexe);
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`);
    };
    return m;
  };
  const corpos = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.15, 0.19, 0.44, 7).translate(0, 0.22, 0), matPub(), lugares.length);
  const cabecas = new THREE.InstancedMesh(new THREE.SphereGeometry(0.125, 9, 7).translate(0, 0.56, 0), matPub(), lugares.length);
  const ROUPA = [[0x3a7bd5, 0x2f5fb3, 0x5aa0f2, 0x1f3f7a, 0xffffff, 0xe8d9b5], [0xd94a3a, 0xb8352a, 0xf06a50, 0x7a1f1a, 0xffffff, 0xe8d9b5]];
  const PELE = [0xf1c27d, 0xe0ac69, 0xc68642, 0x8d5524, 0xffdbac];
  const cc = new THREE.Color(), mm = new THREE.Matrix4();
  lugares.forEach(([x, y, z, t], k) => {
    mm.makeTranslation(x, y, z); corpos.setMatrixAt(k, mm); cabecas.setMatrixAt(k, mm);
    corpos.setColorAt(k, cc.set(ROUPA[t][Math.floor(r() * ROUPA[t].length)])); cabecas.setColorAt(k, cc.set(PELE[Math.floor(r() * PELE.length)]));
  });
  grupo.add(corpos, cabecas);                          // a torcida não faz sombra (são centenas de bonequinhos)
  animados.push({ f: (t, dt) => { uPub.tempo.value = t; uPub.festa.value = Math.max(0, uPub.festa.value - dt * 0.35); } });

  // ---- temas
  const nuvens = [];
  const nuvem = (x, z, y, esc) => { const o = por(r() < 0.5 ? "nuvem" : "nuvem_p", x, z, esc, 0, y); if (o) { o.userData.vivo = true; o.traverse(m => { if (m.isMesh) m.castShadow = false; }); nuvens.push(o); } };
  const fundoMontanhas = (nomes, n, esc) => { for (let j = 0; j < n; j++) por(nomes[j % nomes.length], -46 + j * (92 / (n - 1)) + (r() - 0.5) * 6, -C / 2 - 26 - r() * 14, esc[0] + r() * (esc[1] - esc[0])); };
  const lateral = (nomes, n, esc) => lados(s => espalhar(nomes, n, s < 0 ? [-34, -X0 - NIV * LARG - 5.5, -C / 2 - 4, C / 2 + 4] : [X0 + NIV * LARG + 5.5, 34, -C / 2 - 4, C / 2 + 4], esc));
  const arvoresNat = (n) => lados(s => { for (let j = 0; j < Math.ceil(n / 2); j++) { const x = s * (X0 + NIV * LARG + 6 + r() * 14), z = (r() - 0.5) * (C + 10); if (noRio(z, 1.2)) continue; const tipo = ["arvore", "pinheiro", "bosque", "arvore", "pinheiro"][Math.floor(r() * 5)]; if (!livre(x, z)) continue; const o = cena.novo(tipo); o.position.set(x, altChao(x, z) - 0.05, z); o.scale.setScalar(0.8 + r() * 0.6); o.rotation.y = r() * 6.28; grupo.add(sombra(o)); } });
  const juncos = () => lados(s => { for (let j = 0; j < 22; j++) { const x = s * (L / 2 + 1 + r() * 22), lado = r() < 0.5 ? -1 : 1; por(r() < 0.5 ? "junco" : "planta_agua", x, zRio + lado * (largRio / 2 + 0.1 + r() * 0.3), 2.4 + r()); } });
  const lirios = () => { for (let j = 0; j < 26; j++) { const x = (r() < 0.5 ? -1 : 1) * (L / 2 + 0.8 + r() * 24); por(r() < 0.5 ? "lirio" : "lirio_b", x, zRio + (r() - 0.5) * (largRio - 0.6), 2.2 + r(), r() * 6.28, 0.03); } };
  function moinhoGira(o, vel) { return o && o.traverse(m => { if (/fan|wheel/.test(m.name)) m.userData.vivo = true; if (/fan|wheel/.test(m.name)) animados.push({ f: (t, dt) => { if (/fan/.test(m.name)) m.rotation.z -= dt * vel; else m.rotation.x -= dt * vel; } }); }); }
  function bandeira(nome, x, z, esc) { const o = por(nome, x, z, esc, Math.PI / 2 + (r() - 0.5) * 0.3); if (o) { o.userData.vivo = true; const f = r() * 6; animados.push({ f: (t) => { o.rotation.y = Math.PI / 2 + Math.sin(t * 2.2 + f) * 0.18; } }); } return o; };
  const zLonge = -C / 2 - 1.2;    // logo atrás da borda de cima

  if (i === 0) {               // Campo de Treino: barracas, alvos, armas e colinas
    for (const [x, z, n, esc, g] of [[-12, -19, "tenda", 3.2, 0.4], [-7.5, -20.5, "tenda", 3, -0.2], [7, -20, "tenda", 3.1, 0.3], [12.5, -18.5, "tenda", 3.3, -0.5],
      [-3, -19.2, "alvo", 3.2, 0], [0, -19.8, "alvo", 3.2, 0], [3, -19.2, "alvo", 3.2, 0], [-10, -17.5, "armas", 3, 0], [10, -17.3, "armas", 3, 0],
      [-14.5, -21.5, "celeiro", 2.4, 0.3], [15, -22, "arquearia", 2.4, -0.4], [-5.5, -23, "balde_flechas", 3, 0], [5.4, -22.8, "barril", 3, 0], [6.2, -23.4, "barril", 3, 0],
      [-11, -15, "caixa", 3, 0.2], [11.5, -14, "caixote", 3, 1.2], [-11.3, 4, "carrinho", 3, 0.8], [11.4, -4, "saco", 3, 0], [11.2, 6, "toras", 3, 1.4]]) por(n, x, z, esc, g);
    for (const s of [-1, 1]) for (const z of [zLonge, C / 2 + 1.2]) bandeira(s < 0 ? "bandeira_azul" : "bandeira_vermelho", s * (L / 2 + 0.6), z, 4);
    fundoMontanhas(["colina", "colina_b", "montanha", "colina"], 9, [5, 7]);
    arvoresNat(24); lateral(["arvores_m", "arvores_p", "rocha_c", "toco"], 10, [2.2, 3]);
    juncos(); lirios();
    for (let j = 0; j < 6; j++) nuvem(-30 + j * 12 + r() * 4, -26 - r() * 10, 8 + r() * 3, 4 + r() * 2);
  } else if (i === 1) {        // Vila: casas, moinho, poço, mercado, igreja e moinho d'água no rio
    for (const [x, z, n, esc, g] of [[-13, -20, "casa_a", 2.6, 0.5], [-8, -21.5, "taverna", 2.5, 0.1], [-2.5, -22, "mercado", 2.4, 0], [3, -21.5, "igreja", 2.6, -0.2],
      [9, -21, "casa_b", 2.6, -0.4], [14, -19.5, "casa_c", 2.6, -0.9], [-17.5, -24, "moinho", 3.4, 0.4], [18, -25, "celeiro", 3, 0.2], [0, -18.6, "poco", 2.2, 0],
      [-5.5, -18.2, "carrinho", 3, 0.6], [5.5, -18.4, "caixa", 3, 0.3], [6.3, -18.1, "barril", 3, 0], [-11.2, -12, "casa_a", 2.4, 1.57], [12, -12.5, "casa_c", 2.4, -1.57],
      [-12, 9, "ferreiro", 2.4, 1.57], [12.4, 10, "serraria", 2.4, -1.57], [-11, 4.6, "toras", 3, 0], [11, -6, "sacos", 3, 0], [-11.2, -5, "saco", 3, 0.5]]) {
      const o = por(n, x, z, esc, g); if (n === "moinho") moinhoGira(o, 0.9);
    }
    moinhoGira(por("moinho_agua", -L / 2 - 3.2, zRio - largRio / 2 - 0.6, 2.4, Math.PI / 2), 1.4);
    moinhoGira(por("moinho", 20, -10, 3, -0.6), 0.7);
    fundoMontanhas(["colina", "montanha", "colina_b", "montanha_b"], 9, [5, 7.5]);
    arvoresNat(16); lateral(["arvores_m", "arvores_p", "toco", "rocha_c"], 8, [2.2, 3]);
    for (const s of [-1, 1]) for (const z of [zLonge, C / 2 + 1.2]) bandeira(s < 0 ? "bandeira_azul" : "bandeira_vermelho", s * (L / 2 + 0.6), z, 4);
    juncos(); lirios();
    for (let j = 0; j < 7; j++) nuvem(-34 + j * 11 + r() * 4, -24 - r() * 12, 8 + r() * 3, 4 + r() * 2);
  } else if (i === 2) {        // Floresta Sombria: mata fechada, ruínas, mina e vaga-lumes
    for (let j = 0; j < 70; j++) {
      const x = (r() - 0.5) * 70, z = -C / 2 - 1.6 - r() * 26;
      if (dentro(x, z, 1.6)) continue;
      if (!livre(x, z)) continue;
      const tipo = ["bosque", "pinheiro", "arvore", "bosque"][Math.floor(r() * 4)], o = cena.novo(tipo);
      o.position.set(x, altChao(x, z) - 0.05, z); o.scale.setScalar(1 + r() * 0.8); o.rotation.y = r() * 6.28; grupo.add(sombra(o));
    }
    arvoresNat(40);
    for (const [x, z, n, esc, g] of [[-6, -18.5, "ruina", 1.6, 0.4], [6.5, -19, "ruina", 1.7, -0.6], [0, -21, "mina", 2.6, 0], [-12, 6, "ruina", 1.5, 1.2], [11.5, -6, "ruina", 1.4, 2.5],
      [-3, -18.3, "rocha_e", 3.5, 0], [3, -18.4, "rocha_d", 3.5, 1], [-11, -3, "tocos", 3, 0.5], [11, 3, "tocos", 3, 1.5], [11.6, 12, "toco", 3, 0], [-11.5, 13, "rocha_c", 3.5, 0]]) {
      const o = n === "ruina" ? (() => { if (!livre(x, z)) return null; const a = cena.novo("ruina"); a.position.set(x, altChao(x, z) - 0.05, z); a.scale.setScalar(esc); a.rotation.y = g; grupo.add(sombra(a)); return a; })() : por(n, x, z, esc, g);
    }
    fundoMontanhas(["montanha", "montanha_b", "montanha"], 8, [6, 8]);
    juncos();
    // névoa baixa: placas transparentes que se mexem devagar
    const cv = document.createElement("canvas"); cv.width = cv.height = 128; const g = cv.getContext("2d");
    const gr = g.createRadialGradient(64, 64, 4, 64, 64, 64); gr.addColorStop(0, "rgba(200,220,255,0.55)"); gr.addColorStop(1, "rgba(200,220,255,0)"); g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
    const tn = tex(cv);
    for (let j = 0; j < 14; j++) {
      const p = new THREE.Mesh(new THREE.PlaneGeometry(14, 6).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ map: tn, transparent: true, opacity: 0.35, depthWrite: false, fog: false }));
      const x0 = (r() - 0.5) * 50, z0 = -C / 2 - 4 - r() * 18; p.position.set(x0, 0.6 + r() * 0.8, z0); grupo.add(p);
      const f = r() * 6; animados.push({ f: (t) => { p.position.x = x0 + Math.sin(t * 0.15 + f) * 4; p.material.opacity = 0.25 + Math.sin(t * 0.4 + f) * 0.1; } });
    }
  } else if (i === 3) {        // Castelo de Pedra: muralha com portão, torres de vigia, igreja, quartel e ferreiro
    for (let x = -26; x <= 26; x += 2) { if (Math.abs(x) < 1.5) continue; por("muro", x, -C / 2 - 9, 1, 0); }
    por("muro_portao", 0, -C / 2 - 9, 1, 0);
    for (const x of [-26, -14, -5, 5, 14, 26]) por("torre_vigia", x, -C / 2 - 9.3, 1.25, 0);
    for (const [x, z, n, esc, g] of [[-9.5, -19.5, "quartel", 2.4, 0.2], [9.5, -19.5, "ferreiro", 2.5, -0.3], [-3, -20.5, "armas", 3, 0], [3, -20.5, "armas", 3, 0],
      [-14.5, -19, "barril", 3, 0], [-15.2, -19.5, "barril", 3, 0], [15, -19, "caixa", 3, 0.5], [0, -30, "igreja", 3.2, 0], [-10, -31, "quartel", 2.8, 0.3], [10, -31, "taverna", 2.8, -0.2],
      [-12, -12, "torre_vigia", 1.3, 0], [12, -12, "torre_vigia", 1.3, 0], [-12, 12, "torre_vigia", 1.3, 0], [12, 12, "torre_vigia", 1.3, 0], [-12, 0.5, "pedras_cortadas", 3, 0], [12, -1, "andaime", 2.2, -1.57]]) por(n, x, z, esc, g);
    for (const x of [-20, -8, 8, 20]) bandeira(x < 0 ? "bandeira_azul" : "bandeira_vermelho", x, -C / 2 - 9.6, 6);
    fundoMontanhas(["montanha_b", "montanha", "montanha_c"], 9, [6, 8]);
    arvoresNat(14); juncos(); lirios();
    for (let j = 0; j < 6; j++) nuvem(-30 + j * 12 + r() * 4, -30 - r() * 10, 10 + r() * 3, 4 + r() * 2);
  } else if (i === 4) {        // Reino dos Dragões: montanhas peladas, ruínas, rochas e fumaça
    fundoMontanhas(["montanha_nua", "montanha_c", "montanha_nua"], 10, [6, 9]);
    lateral(["montanha_c", "montanha_nua"], 3, [3.5, 5]);
    for (let j = 0; j < 14; j++) { const x = (r() - 0.5) * 50, z = -C / 2 - 2 - r() * 16; if (dentro(x, z, 1.6) || !livre(x, z)) continue; const a = cena.novo("ruina"); a.position.set(x, altChao(x, z) - 0.05, z); a.scale.setScalar(1.2 + r() * 0.7); a.rotation.y = r() * 6.28; grupo.add(sombra(a)); }
    lateral(["rocha_c", "rocha_d", "rocha_e", "toco", "tocos"], 18, [2.5, 4]);
    espalhar(["rocha_c", "rocha_e", "pedras_cortadas"], 14, [-28, 28, -C / 2 - 16, -C / 2 - 1.5], [2.5, 4]);
    // colunas de fumaça
    const tf = (() => { const cv = document.createElement("canvas"); cv.width = cv.height = 64; const g = cv.getContext("2d"); const gr = g.createRadialGradient(32, 32, 2, 32, 32, 32); gr.addColorStop(0, "rgba(70,60,60,0.8)"); gr.addColorStop(1, "rgba(70,60,60,0)"); g.fillStyle = gr; g.fillRect(0, 0, 64, 64); return tex(cv); })();
    for (const [x, z] of [[-14, -24], [9, -28], [20, -20], [-22, -30], [2, -36]]) {
      for (let j = 0; j < 7; j++) {
        const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tf, transparent: true, depthWrite: false, opacity: 0.6 }));
        grupo.add(sp); const f = j / 7;
        animados.push({ f: (t) => { const q = (t * 0.08 + f) % 1; sp.position.set(x + Math.sin(q * 4 + x) * 1.2 * q, 1 + q * 14, z - q * 3); sp.scale.setScalar(2 + q * 7); sp.material.opacity = 0.55 * Math.sin(q * Math.PI); } });
      }
    }
  } else {                     // Lenda dos Reinos: cidade dourada, muralha, bandeiras e montanhas
    for (let x = -26; x <= 26; x += 2) { if (Math.abs(x) < 1.5) continue; por("muro", x, -C / 2 - 12, 1.1, 0); }
    por("muro_portao", 0, -C / 2 - 12, 1.1, 0);
    for (const x of [-24, -12, -4, 4, 12, 24]) por("torre_vigia", x, -C / 2 - 12.3, 1.5, 0);
    for (const [x, z, n, esc, g] of [[0, -34, "igreja", 4.2, 0], [-9, -33, "quartel", 3.2, 0.2], [9, -33, "taverna", 3.2, -0.2], [-17, -32, "torre_vigia", 2.2, 0], [17, -32, "torre_vigia", 2.2, 0],
      [-8, -20, "mercado", 2.6, 0.3], [8, -20, "mercado", 2.6, -0.3], [-14, -19.5, "casa_b", 2.6, 0.5], [14, -19.5, "casa_b", 2.6, -0.5], [0, -20, "poco", 2.4, 0],
      [-3.5, -18.5, "caixa", 3, 0], [3.5, -18.5, "barril", 3, 0], [-12, -10, "torre_vigia", 1.4, 0], [12, -10, "torre_vigia", 1.4, 0], [-12, 11, "torre_vigia", 1.4, 0], [12, 11, "torre_vigia", 1.4, 0]]) por(n, x, z, esc, g);
    for (const x of [-20, -16, -8, 8, 16, 20]) bandeira("bandeira_amarela", x, -C / 2 - 12.8, 7);
    for (const s of [-1, 1]) for (const z of [-12, -4, 4, 12]) bandeira("bandeira_amarela", s * (L / 2 + 1.6), z, 4.5);
    fundoMontanhas(["montanha_b", "montanha", "montanha_b"], 9, [7, 9]);
    arvoresNat(10); juncos(); lirios();
    for (let j = 0; j < 7; j++) nuvem(-34 + j * 11 + r() * 4, -30 - r() * 12, 11 + r() * 3, 4.5 + r() * 2);
  }
  // ---- a faixa logo do lado de fora da cerca (é o que mais aparece no celular): objetos do tema e tochas
  const BEIRA = [["barril", "caixa", "saco", "armas", "balde_flechas", "arvores_p", "toras", "alvo"], ["carrinho", "barril", "caixa_p", "saco", "arvores_p", "toras", "caixote", "poco"],
    ["toco", "rocha_c", "tocos", "rocha_e", "arvores_p", "rocha_d"], ["barril", "armas", "pedras_cortadas", "caixa", "caixote", "balde_flechas"],
    ["rocha_c", "rocha_d", "rocha_e", "toco", "tocos", "pedras_cortadas"], ["barril", "caixa", "carrinho", "pedras_cortadas", "arvores_p", "armas"]][i];
  const escBeira = { arvores_p: 2.2, poco: 1.6, alvo: 2.4, toco: 2.6, tocos: 2.4 };
  lados(s => {
    for (let z = -C / 2 + 1; z < C / 2 + 1; z += 1.7 + r() * 1.6) {
      if (noRio(z, 1.4)) continue;
      const n = BEIRA[Math.floor(r() * BEIRA.length)];
      por(n, s * (L / 2 + 1.5 + r() * 2.2), z, (escBeira[n] || 3) * (0.85 + r() * 0.3));
    }
  });
  if (i >= 2) {                // tochas com fogo que tremula
    const geoPoste = new THREE.CylinderGeometry(0.07, 0.1, 1.5, 6), matPoste = new THREE.MeshLambertMaterial({ color: 0x5a3b22 });
    const corFogo = i === 2 ? 0x8fe8ff : 0xffa030;     // na floresta, fogo-fátuo azulado
    lados(s => {
      for (const z of [-13, -7, 7, 13]) {
        const x = s * (L / 2 + 0.95), poste = new THREE.Mesh(geoPoste, matPoste);
        poste.position.set(x, 0.75, z); poste.castShadow = true; grupo.add(poste);
        const fogo = new THREE.Sprite(new THREE.SpriteMaterial({ map: cena.texBrilho, color: corFogo, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
        const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: cena.texBrilho, color: corFogo, transparent: true, opacity: 0.35, depthWrite: false, blending: THREE.AdditiveBlending }));
        fogo.position.set(x, 1.62, z); halo.position.set(x, 1.6, z); halo.scale.setScalar(2.4); grupo.add(fogo, halo);
        const f = r() * 9;
        animados.push({ f: (t) => { const v = 0.8 + Math.sin(t * 13 + f) * 0.1 + Math.sin(t * 7.7 + f) * 0.1; fogo.scale.set(0.55 * v, 0.8 * v, 1); halo.material.opacity = 0.25 + v * 0.12; } });
      }
    });
  }

  animados.push({ f: (t, dt) => { for (const o of nuvens) { o.position.x += dt * 0.4; if (o.position.x > 45) o.position.x = -45; } } });

  // ---- partículas no ar
  const tipo = T.part, np = { folhas: 40, petalas: 50, vagalumes: 70, poeira: 30, brasas: 90, brilhos: 60 }[tipo] || 0;
  if (np) {
    const pos = new Float32Array(np * 3), dados = [];
    for (let j = 0; j < np; j++) { dados.push({ x: (r() - 0.5) * 30, y: r() * 8, z: (r() - 0.5) * 44, f: r() * 6, v: 0.5 + r() }); }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const cor = { folhas: 0x8bc34a, petalas: 0xffa6c9, vagalumes: 0xd8ff7a, poeira: 0xfff3d0, brasas: 0xff8a2a, brilhos: 0xffe08a }[tipo];
    const brilha = tipo === "vagalumes" || tipo === "brasas" || tipo === "brilhos";
    const mat = new THREE.PointsMaterial({ color: cor, size: brilha ? 0.55 : 0.32, map: cena.texBrilho, transparent: true, depthWrite: false, opacity: brilha ? 1 : 0.85,
      blending: brilha ? THREE.AdditiveBlending : THREE.NormalBlending, sizeAttenuation: true, fog: false });
    const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; grupo.add(pts);
    animados.push({ f: (t, dt) => {
      for (let j = 0; j < np; j++) {
        const d = dados[j];
        if (tipo === "brasas") { d.y += dt * d.v * 1.6; d.x += Math.sin(t * 2 + d.f) * dt * 0.6; if (d.y > 9) { d.y = 0; d.x = (r() - 0.5) * 30; } }
        else if (tipo === "vagalumes") { d.x += Math.sin(t * 0.7 + d.f) * dt * 0.5; d.z += Math.cos(t * 0.5 + d.f * 2) * dt * 0.5; d.y = 0.6 + (Math.sin(t * 0.9 + d.f) + 1) * 1.4; }
        else if (tipo === "brilhos" || tipo === "poeira") { d.y += dt * 0.25 * d.v; d.x += Math.sin(t * 0.6 + d.f) * dt * 0.3; if (d.y > 8) d.y = 0; }
        else { d.y -= dt * 0.45 * d.v; d.x += (Math.sin(t * 1.3 + d.f) * 0.8 + 0.5) * dt; d.z += Math.cos(t + d.f) * dt * 0.3; if (d.y < 0.1) { d.y = 8; d.x = (r() - 0.5) * 30; } }
        pos[j * 3] = d.x; pos[j * 3 + 1] = d.y; pos[j * 3 + 2] = d.z;
      }
      geo.attributes.position.needsUpdate = true;
      if (tipo === "vagalumes") mat.opacity = 0.75 + Math.sin(t * 3) * 0.25;
    } });
  }

  // junta tudo o que não se mexe e usa o mesmo material numa malha só: centenas de peças viram meia dúzia de desenhos
  // (o celular agradece). O cenário de fora não faz sombra; só recebe.
  grupo.updateMatrixWorld(true);
  const inv = grupo.matrixWorld.clone().invert(), lotes = new Map();
  const vivo = (o) => { for (let n = o; n && n !== grupo; n = n.parent) if (n.userData.vivo) return true; return false; };
  grupo.traverse(o => {
    if (!o.isMesh || o.isInstancedMesh || o.isSkinnedMesh || vivo(o)) return;
    const m = o.material;
    if (Array.isArray(m) || !m.isMeshLambertMaterial || m.transparent || !o.geometry.attributes.normal) return;
    const g0 = o.geometry;
    if (g0.attributes.position.count > 20000) return;                       // chão e morros ficam como estão
    const chave = m.uuid + "|" + Object.keys(g0.attributes).sort().join(",");
    const g = g0.index ? g0.toNonIndexed() : g0.clone();
    for (const k of Object.keys(g.attributes)) {
      if (!["position", "normal", "uv", "color"].includes(k)) { g.deleteAttribute(k); continue; }
      const at = g.attributes[k];                                           // alguns arquivos vêm com números inteiros (compactados): passa para decimal
      if (!(at.array instanceof Float32Array) || at.isInterleavedBufferAttribute) {
        const f = new Float32Array(at.count * at.itemSize);
        for (let i = 0; i < at.count; i++) for (let c = 0; c < at.itemSize; c++) f[i * at.itemSize + c] = at.getComponent(i, c);
        g.setAttribute(k, new THREE.BufferAttribute(f, at.itemSize));
      }
    }
    g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
    if (!lotes.has(chave)) lotes.set(chave, { m, gs: [], os: [] });
    const l = lotes.get(chave); l.gs.push(g); l.os.push(o);
  });
  for (const l of lotes.values()) {
    const junto = l.gs.length > 1 ? mergeGeometries(l.gs, false) : null;
    for (const g of l.gs) g.dispose();
    if (!junto) continue;                                                   // peça única (ou que não deu para juntar) fica como está
    const malha = new THREE.Mesh(junto, l.m); malha.receiveShadow = true; malha.castShadow = false;
    grupo.add(malha);
    for (const o of l.os) if (o.parent) o.parent.remove(o);
  }
  cena.cena.add(grupo);
  return { grupo, tema: T, quadro: (t, dt) => { for (const a of animados) a.f(t, dt); }, comemorar: () => { uPub.festa.value = 1; } };
}
