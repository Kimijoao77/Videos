// A parte 3D (Three.js): arena, torres, tropas animadas, projéteis, barras de vida e efeitos.
// Recebe "fotos" do estado (sim.js → foto()) e desenha, suavizando o movimento entre uma foto e outra.
// visao = de que lado o jogador está: o campo dele sempre aparece embaixo e as coisas dele sempre em azul.
import * as THREE from "three";
import { GLTFLoader } from "../vendor/GLTFLoader.js";
import * as SkeletonUtils from "../vendor/SkeletonUtils.js";
import { CARTAS, L, C, RIO0, RIO1, PONTES, lugaresDe } from "./sim.js";
import { montarCenario } from "./cenario.js";
import { EffectComposer } from "../vendor/pos/postprocessing/EffectComposer.js";
import { RenderPass } from "../vendor/pos/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "../vendor/pos/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "../vendor/pos/postprocessing/OutputPass.js";
import { Particulas, Clima } from "./efeitos.js";

const AZUL = new THREE.Color("#2F7BFF"), VERMELHO = new THREE.Color("#F0463C");
// modelos do pacote KayKit (com esqueleto e animações): altura no jogo, em casas
const KAYKIT = { cavaleiro: 2.2, besteiro: 1.9, gigante: 3.6, mago: 2.2, bandido: 1.7, esqueleto: 1.35, guerreiro: 2.35, necromante: 2.2,
  paladino: 2.35, mago_gelo: 2.2, assassino: 1.75 };
const MEUS = ["dragao", "bola_fogo", "flecha", "ponte", "balao"];             // modelados por código no Blender
// do pacote KayKit Medieval Hexagon: um arquivo azul e um vermelho, ou um só (neutros)
const PREDIOS_TIME = ["torre", "castelo", "catapulta", "quartel", "mina", "torre_arq"], NEUTROS = ["ruina", "pedra_cat", "arvore", "pinheiro", "pedra", "bosque"];
const ALT_VOO = 1.9;
const COR_RASTRO = { fogo: 0xff8a1e, magia: 0x7fefff, sombra: 0xb26bff, bola: 0xffa52e, geada: 0xbfeeff };
// altura de cada construção (para a barra de vida) e quanto o balão fica acima do chão
const ALT_PREDIO = { catapulta: 2.7, quartel: 2.7, mina: 2.2, torre_arq: 4.0 };
const ALT_BALAO = ALT_VOO - 0.35;

// brilho redondo (para magia, fogo e o clarão de quando a tropa nasce)
function texturaBrilho() {
  const cv = document.createElement("canvas"); cv.width = cv.height = 64;
  const g = cv.getContext("2d"), gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.35, "rgba(255,255,255,0.55)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Cena {
  constructor(canvas) {
    this.canvas = canvas;
    this.r = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.cena = new THREE.Scene();
    this.cena.background = new THREE.Color("#274E2B");
    this.cam = new THREE.PerspectiveCamera(30, 1, 1, 300);
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x7d8a6a, 1.15);
    this.cena.add(this.hemi);
    const sol = this.sol = new THREE.DirectionalLight(0xfff1d6, 1.9);
    sol.position.set(-8, 18, 10);
    // sombras de verdade (prédios, árvores e tropas); se o aparelho for fraco, a qualidade automática desliga
    this.r.shadowMap.enabled = true; this.r.shadowMap.type = THREE.PCFSoftShadowMap;
    sol.castShadow = true; sol.shadow.mapSize.set(2048, 2048); sol.shadow.bias = -0.0008; sol.shadow.normalBias = 0.03;
    Object.assign(sol.shadow.camera, { left: -24, right: 24, top: 30, bottom: -26, near: 1, far: 70 });
    this.cena.add(sol, sol.target);
    this.matPeca = new THREE.MeshLambertMaterial();
    this.visao = 0;
    this.bonecos = new Map();       // id → Boneco
    this.projs = new Map();
    this.zonasVis = new Map();      // veneno e fúria no chão
    this.efeitos = [];
    this.modelos = {};
    this.relogio = new THREE.Clock();
    this.tremor = 0;
    this.margens = { cima: 0.08, baixo: 0.24 };
    this.raio = new THREE.Raycaster();
    this.chao = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    this.matCor = new THREE.MeshLambertMaterial({ vertexColors: true });
    this.matTime = [new THREE.MeshLambertMaterial({ color: AZUL }), new THREE.MeshLambertMaterial({ color: VERMELHO })];
    this.matDisco = [new THREE.MeshBasicMaterial({ color: AZUL, transparent: true, opacity: 0.5, depthWrite: false }),
      new THREE.MeshBasicMaterial({ color: VERMELHO, transparent: true, opacity: 0.5, depthWrite: false })];
    this.geoDisco = new THREE.CircleGeometry(1, 28).rotateX(-Math.PI / 2);
    this.matSombra = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false });
    this.texBrilho = texturaBrilho();
    this.geoBolinha = new THREE.SphereGeometry(1, 8, 6);
    this.qual = { soma: 0, n: 0, razao: Math.min(window.devicePixelRatio || 1, 2) };
    this.qualidadeAlta = true;
    this.matGelo = new THREE.MeshLambertMaterial({ color: 0xbff0ff, emissive: 0x2a8fd0, emissiveIntensity: 0.35, transparent: true, opacity: 0.5, depthWrite: false });
    this.matEstrela = new THREE.SpriteMaterial({ map: this.texBrilho, color: 0xffe066, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.matBarra = { fundo: new THREE.SpriteMaterial({ color: 0x10182b, depthTest: false }), 0: new THREE.SpriteMaterial({ color: 0x4d9bff, depthTest: false }),
      1: new THREE.SpriteMaterial({ color: 0xff5a4f, depthTest: false }) };
    // brilho (bloom): só o que é bem claro brilha (fogo, magia, raio, faíscas); some se o aparelho não aguentar
    this.composer = new EffectComposer(this.r);
    this.composer.addPass(new RenderPass(this.cena, this.cam));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.55, 0.45, 0.82);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    // aparelho que já mostrou tela preta com o brilho fica sem ele (guardado no aparelho)
    let semBrilho = false; try { semBrilho = localStorage.getItem("arena-sem-brilho") === "1"; } catch (e) { /* ok */ }
    this.comBrilho = !semBrilho && this.r.capabilities.isWebGL2;
    this.conferirBrilho = 3;      // confere os primeiros quadros com brilho (e depois de vez em quando)
    this._px = new Uint8Array(4);
    // partículas: faíscas e fogo (somam luz) e fumaça e poeira (por cima); o clima de cada arena
    this.faiscas = new Particulas(this.cena, this.texBrilho, 1400, true);
    this.poeiraP = new Particulas(this.cena, this.texBrilho, 600, false);
    this.clima = new Clima(this.cena, this.texBrilho);
    this.emissores = [];          // fogo que fica um tempo (torre caída)
    this._v2 = new THREE.Vector2();
  }

  // qualidade: sombras e resolução cheia (ou leve, para aparelho fraco)
  altaQualidade(v) {
    this.qualidadeAlta = v;
    this.sol.castShadow = v;
    this.comBrilho = v;
    this.qual.razao = v ? Math.min(window.devicePixelRatio || 1, 2) : 1;
    this.r.setPixelRatio(this.qual.razao);
    this.composer.setPixelRatio(this.qual.razao);
    this.ajustar();
  }

  // ------------------------------------------------------------ carregar os modelos
  async carregar(base, progresso) {
    const loader = new GLTFLoader();
    const nomes = ["cenario", ...Object.keys(KAYKIT), ...MEUS, ...NEUTROS, ...PREDIOS_TIME.flatMap(n => [`${n}_azul`, `${n}_vermelho`])];
    let feitos = 0;
    await Promise.all(nomes.map(async (n) => {
      const g = await loader.loadAsync(`${base}modelos/${n}.glb`);
      this.modelos[n] = g;
      feitos++;
      progresso && progresso(feitos / nomes.length);
    }));
    for (const n of Object.keys(KAYKIT)) {                    // materiais leves e a altura original
      const g = this.modelos[n];
      const caixa = new THREE.Box3().setFromObject(g.scene);
      g.altura = caixa.max.y;
      g.scene.traverse(o => {
        if (!o.isMesh) return;
        const m = new THREE.MeshLambertMaterial({ map: o.material.map });
        o.material = m;
        o.frustumCulled = false;
      });
    }
    for (const n of MEUS) this.prepararMeu(n);
    const leve = (g) => { g.scene.traverse(o => { if (o.isMesh) o.material = new THREE.MeshLambertMaterial({ map: o.material.map }); }); return g.scene; };
    for (const n of NEUTROS) { const cena = leve(this.modelos[n]); this.modelos[n].porTime = [cena, cena]; }
    for (const n of PREDIOS_TIME) this.modelos[n] = { porTime: [leve(this.modelos[`${n}_azul`]), leve(this.modelos[`${n}_vermelho`])] };
    // peças de cenário: um arquivo só, todas com o mesmo material (a cor do tema tinge todas de uma vez)
    const cen = this.modelos.cenario.scene;
    this.pecas = {};
    for (const o of cen.children) {
      o.traverse(m => { if (m.isMesh) { if (!this.matPeca.map) { this.matPeca.map = m.material.map; } m.material = this.matPeca; } });
      o.position.set(0, 0, 0); this.pecas[o.name] = o;
    }
    this.montarArena();
  }

  // meus modelos: troca a cor mágica (magenta) pela cor do time; guarda uma versão azul e uma vermelha
  prepararMeu(n) {
    const g = this.modelos[n];
    g.porTime = [0, 1].map(time => {
      const cor = time === 0 ? AZUL : VERMELHO;
      const copia = g.scene.clone(true);
      copia.traverse(o => {
        if (!o.isMesh) return;
        const geo = o.geometry.clone(), c = geo.getAttribute("color");
        if (c) {
          for (let i = 0; i < c.count; i++) {
            const r = c.getX(i), gg = c.getY(i), b = c.getZ(i);
            if (gg < 0.02 && Math.abs(r - b) < 0.02 && r > 0.05) c.setXYZ(i, cor.r * r, cor.g * r, cor.b * r);
          }
          c.needsUpdate = true;
        }
        o.geometry = geo;
        o.material = this.matCor;
      });
      return copia;
    });
  }

  novo(n, time = 0) {
    const g = this.modelos[n];
    if (g.porTime) return g.porTime[time].clone(true);
    const o = SkeletonUtils.clone(g.scene);
    o.traverse(m => { if (m.isMesh && /Cape|Shield/.test(m.name)) m.material = this.matTime[time]; });
    return o;
  }

  // ------------------------------------------------------------ a arena
  montarArena() {
    this.trocarCenario(this.temaAtual || 0);
    for (const px of PONTES) { const p = this.novo("ponte"); p.position.set(px - L / 2, 0.02, 0); p.traverse(m => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } }); this.cena.add(p); }
    // zona proibida (aparece quando o jogador escolhe uma carta) e a marca de onde vai cair
    this.zonas = new THREE.Group(); this.zonas.visible = false; this.cena.add(this.zonas);
    this.matZona = new THREE.MeshBasicMaterial({ color: 0xff3b30, transparent: true, opacity: 0.26, depthWrite: false });
    this.marca = new THREE.Group(); this.marca.visible = false; this.cena.add(this.marca);
    this.matMarca = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85, depthWrite: false });
    const anel = new THREE.Mesh(new THREE.RingGeometry(0.75, 0.95, 32).rotateX(-Math.PI / 2), this.matMarca); anel.position.y = 0.06;
    const feixe = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.5, 3, 12, 1, true), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.22, depthWrite: false, side: THREE.DoubleSide }));
    feixe.position.y = 1.5;
    this.marca.add(anel, feixe); this.anelMarca = anel;
  }

  // troca o cenário (0 a 5, um por arena)
  trocarCenario(i) {
    if (this.cenario && this.temaAtual === i) return;
    if (this.cenario) {
      this.cena.remove(this.cenario.grupo);
      this.cenario.grupo.traverse(o => { if (o.isMesh || o.isPoints) { o.geometry.dispose(); const m = o.material; if (m !== this.matPeca) { if (m.map) m.map.dispose(); m.dispose(); } } });
    }
    this.temaAtual = i;
    this.cenario = montarCenario(this, i, (n) => this.peca(n));
    this.clima && this.clima.trocar(i);
    this.ajustarNeblina();
  }
  peca(n) { const o = this.pecas && this.pecas[n]; return o ? o.clone(true) : null; }
  ajustarNeblina() {
    if (!this.cena.fog || !this.camBase) return;
    const d = this.camBase.length();
    this.cena.fog.near = d + 6; this.cena.fog.far = d + (this.temaAtual === 2 ? 45 : 90);
  }

  // sim → mundo 3D (o campo de quem joga fica perto da câmera)
  X(x) { return this.visao ? L / 2 - x : x - L / 2; }
  Z(y) { return this.visao ? y - C / 2 : C / 2 - y; }
  giro(a) { return this.visao ? -a : Math.PI - a; }
  paraSim(X, Z) { return this.visao ? [L / 2 - X, Z + C / 2] : [X + L / 2, C / 2 - Z]; }

  ajustar() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) return;
    this.r.setSize(w, h, false);
    this.composer.setPixelRatio(this.r.getPixelRatio()); this.composer.setSize(w, h);
    this.cam.aspect = w / h;
    this.cam.updateProjectionMatrix();
    // enquadra a arena inteira entre a barra de cima e as cartas
    const el = THREE.MathUtils.degToRad(47), dir = new THREE.Vector3(0, Math.sin(el), Math.cos(el));
    const pts = [];
    for (const x of [-L / 2 - 0.4, L / 2 + 0.4]) { pts.push(new THREE.Vector3(x, 0, C / 2 + 0.6), new THREE.Vector3(x, 0, -C / 2 - 2.6), new THREE.Vector3(x * 0.3, 5.6, -C / 2 + 3)); }
    const yCima = 1 - 2 * this.margens.cima, yBaixo = -1 + 2 * this.margens.baixo;
    const medir = (d, zt) => {
      this.cam.position.set(0, dir.y * d, dir.z * d + zt);
      this.cam.lookAt(0, 0, zt);
      this.cam.updateMatrixWorld();
      let x1 = 0, y0 = 9, y1 = -9;
      for (const p of pts) { const q = p.clone().project(this.cam); x1 = Math.max(x1, Math.abs(q.x)); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y); }
      return [x1, y0, y1];
    };
    const centrar = (d) => {                   // acha o zt que põe a arena no meio do espaço livre
      let a = -40, b = 40;
      for (let k = 0; k < 22; k++) { const m = (a + b) / 2, [, y0, y1] = medir(d, m); if ((y0 + y1) / 2 < (yCima + yBaixo) / 2) a = m; else b = m; }
      return (a + b) / 2;
    };
    let perto = 12, longe = 220;
    for (let k = 0; k < 22; k++) {             // a menor distância em que tudo cabe
      const d = (perto + longe) / 2, [x1, y0, y1] = medir(d, centrar(d));
      if (x1 <= 0.98 && y1 - y0 <= yCima - yBaixo) longe = d; else perto = d;
    }
    medir(longe, centrar(longe));
    this.camBase = this.cam.position.clone();
    this.ajustarNeblina();
  }

  // ponto da arena debaixo do dedo (coordenadas da simulação), ou null
  apontar(cx, cy) {
    const r = this.canvas.getBoundingClientRect();
    const v = new THREE.Vector2(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
    this.raio.setFromCamera(v, this.cam);
    const p = new THREE.Vector3();
    if (!this.raio.ray.intersectPlane(this.chao, p)) return null;
    return this.paraSim(p.x, p.z);
  }

  mostrarZonas(mostrar, magia, caiuEsq, caiuDir) {
    this.zonas.visible = mostrar && !magia;
    if (!this.zonas.visible) return;
    this.zonas.clear();
    const quad = (x0, x1, y0, y1) => {      // em coordenadas "do jogador": x 0..18, y 0..32 (o dele é y < 15)
      const m = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, y1 - y0).rotateX(-Math.PI / 2), this.matZona);
      m.position.set((x0 + x1) / 2 - L / 2, 0.05, C / 2 - (y0 + y1) / 2); this.zonas.add(m);
    };
    quad(0, L, 21.25, C);
    quad(0, L / 2, RIO0 - 0.25, caiuEsq ? RIO1 + 0.25 : 21.25);
    quad(L / 2, L, RIO0 - 0.25, caiuDir ? RIO1 + 0.25 : 21.25);
  }

  mostrarMarca(x, y, valido, raio = 0.9, carta = null) {
    if (x == null) { this.marca.visible = false; return; }
    this.marca.visible = true;
    this.marca.position.set(this.X(x), 0, this.Z(y));
    this.anelMarca.scale.setScalar(raio / 0.9);
    this.matMarca.color.set(valido ? 0xffffff : 0xff4b3e);
    if (carta !== this.cartaFantasma) this.montarFantasma(carta);
    if (this.fantasma) for (const m of this.fantasmaMats) m.opacity = valido ? 0.55 : 0.25;
  }

  // a prévia meio transparente da tropa (ou construção) no lugar onde a carta vai cair
  montarFantasma(carta) {
    if (this.fantasma) { this.marca.remove(this.fantasma); this.fantasma = null; }
    this.cartaFantasma = carta;
    const c = carta && CARTAS[carta];
    if (!c || c.tipo === "magia") return;
    const g = new THREE.Group(), modelo = c.modelo || carta, mats = [];
    const dir = this.visao === 0 ? 1 : -1;      // para a frente, visto do jogador
    for (const [dx, dy] of lugaresDe(c.n, 1)) {
      const o = this.novo(modelo, 0);
      if (KAYKIT[modelo]) {
        o.scale.setScalar(KAYKIT[modelo] / this.modelos[modelo].altura);
        const mx = new THREE.AnimationMixer(o), clip = this.modelos[modelo].animations.find(a => a.name === "parado");
        if (clip) { mx.clipAction(clip).play(); mx.update(0.01); }
      } else if (carta === "dragao") { o.scale.setScalar(1.3); o.position.y = ALT_VOO; }
      else if (carta === "balao") o.position.y = ALT_BALAO;
      o.rotation.y = Math.PI;
      o.traverse(m => {
        if (!m.isMesh) return;
        m.material = m.material.clone(); m.material.transparent = true; m.material.opacity = 0.55; m.material.depthWrite = false; mats.push(m.material);
      });
      o.position.x += dx; o.position.z += -dy * dir * (this.visao === 0 ? 1 : -1);
      g.add(o);
    }
    this.fantasma = g; this.fantasmaMats = mats;
    this.marca.add(g);
  }

  // onde um ponto da arena aparece na tela (para a coroa voar até o placar)
  naTela(x, y, alt = 0) {
    const v = new THREE.Vector3(this.X(x), alt, this.Z(y)).project(this.cam), r = this.canvas.getBoundingClientRect();
    return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };
  }

  // balão com um emoji em cima do castelo de um lado (emotes)
  emote(lado, texto) {
    const rei = [...this.bonecos.values()].find(b => b.k === "rei" && b.lado === lado);
    const x = rei ? rei.g.position.x : 0, z = rei ? rei.g.position.z : (lado === this.visao ? C / 2 - 3 : -C / 2 + 3);
    const cv = document.createElement("canvas"); cv.width = 160; cv.height = 140;
    const g = cv.getContext("2d");
    g.fillStyle = "#ffffff"; g.strokeStyle = "#10182b"; g.lineWidth = 8;
    g.beginPath(); g.roundRect(8, 8, 144, 104, 26); g.moveTo(66, 112); g.lineTo(80, 134); g.lineTo(94, 112); g.fill(); g.stroke();
    g.fillStyle = "#ffffff"; g.fillRect(70, 104, 20, 10);
    g.font = "64px 'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(texto, 80, 62);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
    sp.renderOrder = 20; sp.position.set(x, 8.2, z);
    this.efeito(sp, 2.4, (q) => { const s = q < 0.12 ? q / 0.12 : 1; sp.scale.set(3.4 * s, 3.0 * s, 1); sp.material.opacity = q > 0.85 ? (1 - q) / 0.15 : 1; sp.position.y = 8.2 + q * 0.6; });
  }

  // ------------------------------------------------------------ aplicar uma foto do estado
  aplicar(f) {
    this.ultima = f; this._nf = 0;
    const vistos = new Set();
    for (const e of f.ent) {
      const [id, k, lado, x, y, hp, hpMax, est, a, tn, para] = e;
      vistos.add(id);
      let b = this.bonecos.get(id);
      if (!b) { b = new Boneco(this, id, k, lado, x, y, hpMax, a); this.bonecos.set(id, b); }
      b.alvo(x, y, hp, est, a, tn);
      b.parar(para || 0);
      b.marcas(e[11] || 0);
    }
    for (const [id, b] of this.bonecos) if (!vistos.has(id)) { b.sair(); this.bonecos.delete(id); }
    const pv = new Set();
    for (const p of f.proj) {
      pv.add(p[0]);
      let o = this.projs.get(p[0]);
      if (!o) { o = new Projetil(this, p); this.projs.set(p[0], o); }
      o.alvo(p);
    }
    for (const [id, o] of this.projs) if (!pv.has(id)) { o.sair(); this.projs.delete(id); }
    const zv = new Set();
    for (const z of f.zonas || []) {
      zv.add(z[0]);
      if (!this.zonasVis.has(z[0])) this.zonasVis.set(z[0], new Zona(this, z));
    }
    for (const [id, o] of this.zonasVis) if (!zv.has(id)) { o.sair(); this.zonasVis.delete(id); }
    for (const ev of f.ev || []) this.evento(ev);
  }

  evento(ev) {
    const [t, a, b, c, d] = ev;
    if (t === "atq") { const o = this.bonecos.get(a); o && o.atacar(); this.aoSom && this.aoSom("atq", o && o.k); }
    else if (t === "nasce") { const o = this.bonecos.get(a); if (o) { this.surgir(o); this.faiscas.emitir(o.g.position.x, 0.2, o.g.position.z, 14, { cores: o.time === 0 ? [0x9fd0ff, 0xffffff] : [0xffa8a0, 0xffffff], dir: "anel", abre: 0.6, vel: [1.5, 3], vida: [0.3, 0.6], tam: [0.12, 0.22], grav: 1, arrasto: 2.2, raio: o.raio }); } this.aoSom && this.aoSom("nasce"); }
    else if (t === "giro") { const o = this.bonecos.get(a); if (o) { o.atacar(); this.poeira(o.g.position.x, o.g.position.z, 0xffffff, CARTAS[o.k].giro + 0.6); } }
    else if (t === "invoca") { const o = this.bonecos.get(a); if (o) o.invocar(); this.aoSom && this.aoSom("magia"); }
    else if (t === "morte") {
      const fixa = d === "torre" || d === "rei", o = this.bonecos.get(a);
      this.fumaca(this.X(b), this.Z(c), fixa ? 22 : 7, fixa ? 2.2 : 0.7, fixa ? 0xd8d2c4 : 0xffffff);
      if (fixa) { this.tremor = 0.7; this.ruina(this.X(b), this.Z(c), d === "rei" ? 1.5 : 1); this.destrocos(this.X(b), this.Z(c), d === "rei" ? 1.4 : 1); }
      else if (o) this.alma(this.X(b), this.Z(c), o.time, o.voa ? ALT_VOO : 0.6);
      this.aoSom && this.aoSom(fixa ? "torre" : "morte");
    } else if (t === "explode") {
      this.explosao(this.X(a), this.Z(b), c, d);
      const especial = d === "relampago" ? "raio" : d === "gelo" || d === "geada" ? "gelo" : d === "cura" ? "cura" : d === "queda" ? "explosao" : null;
      this.aoSom && this.aoSom(especial || (d ? "impacto" : "explosao"));
      if (!d) this.tremor = 0.35; else if (d === "relampago") this.tremor = 0.25; else if (d === "queda") this.tremor = Math.max(this.tremor, 0.42);
    }
    else if (t === "curou") { const o = this.bonecos.get(a); if (o) this.poeira(o.g.position.x, o.g.position.z, 0x7dff9a, o.raio + 0.4); }
    else if (t === "investida") { const o = this.bonecos.get(a); if (o) this.poeira(o.g.position.x, o.g.position.z, 0xfff0c8, o.raio + 0.5); this.aoSom && this.aoSom("investida"); }
    else if (t === "golpeForte") { const o = this.bonecos.get(a); if (o) { this.poeira(o.g.position.x, o.g.position.z, 0xffd166, o.raio + 1.1); this.onda(o.g.position.x, o.g.position.z, 1.2, [0xffd36b, 0xffffff]); this.tremor = Math.max(this.tremor, 0.18); } this.aoSom && this.aoSom("golpeForte"); }
    else if (t === "salto") { const o = this.bonecos.get(a); if (o) o.saltar(); this.aoSom && this.aoSom("salto"); }
    else if (t === "pouso") { const o = this.bonecos.get(a); if (o) { this.poeira(o.g.position.x, o.g.position.z, 0xd9d2ff, o.raio + 0.9); this.fumaca(o.g.position.x, o.g.position.z, 5, 0.5, 0xbdb6a6); this.onda(o.g.position.x, o.g.position.z, 1, [0xd9c8ff, 0xffffff]); } this.tremor = Math.max(this.tremor, 0.14); this.aoSom && this.aoSom("pouso"); }
    else if (t === "gera") { const o = this.bonecos.get(a); if (o) { this.maisEnergia(o); this.faiscas.emitir(o.g.position.x, o.altura, o.g.position.z, 12, { cores: [0xe35cff, 0xffb8ff], dir: "cima", abre: 0.8, vel: [1, 2.5], vida: [0.4, 0.8], tam: [0.1, 0.2], grav: -1 }); } this.aoSom && b === this.visao && this.aoSom("gera"); }
    else if (t === "zona") this.aoSom && this.aoSom(a === "furia" ? "furia" : "veneno");
    else if (t === "dano") {
      const o = this.bonecos.get(a);
      if (o) {
        if (c === "z") { o.pisca = Math.max(o.pisca, 0.22); o.tingir(); }
        else {
          o.apanhar();
          if ((this._nf = (this._nf || 0) + 1) < 14) {         // faíscas no golpe (no máximo umas 14 por quadro)
            const p = o.g.position, h = o.fixa ? o.altura * 0.55 : o.voa ? ALT_VOO + 0.4 : Math.min(1.1, o.altura * 0.5);
            this.faisca(p.x, h, p.z, o.fixa ? 7 : 5, o.fixa ? [0xfff2c0, 0xffd36b, 0xffffff] : [0xffffff, 0xfff0a8, 0xffd36b], o.fixa ? 1.2 : 1);
          }
        }
      }
    }
    else if (t === "magia") this.aoSom && this.aoSom("magia");
  }

  // tropa nascendo: coluna de luz na cor do time e um anel no chão
  surgir(o) {
    const cor = o.time === 0 ? 0x6fb0ff : 0xff7a70, X = o.g.position.x, Z = o.g.position.z, r = o.raio + 0.35;
    const col = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.7, r, 5, 18, 1, true), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }));
    col.position.set(X, 2.5, Z);
    this.efeito(col, 0.6, (q) => { col.scale.set(1 - q * 0.5, 1, 1 - q * 0.5); col.material.opacity = 0.55 * (1 - q); });
    this.poeira(X, Z, cor, r + 0.3);
  }

  // rastro de projétil: bolinha que some e encolhe
  rastro(pos, cor, tam = 0.16) {
    const m = new THREE.Mesh(this.geoBolinha, new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.7, depthWrite: false }));
    m.position.copy(pos); m.scale.setScalar(tam);
    this.efeito(m, 0.32, (q) => { m.scale.setScalar(tam * (1 - q * 0.8)); m.material.opacity = 0.7 * (1 - q); m.position.y += 0.01; });
  }

  // a mina cavou energia: uma gota rosa com "+1" subindo
  maisEnergia(o) {
    const cv = document.createElement("canvas"); cv.width = 128; cv.height = 128;
    const g = cv.getContext("2d");
    g.fillStyle = "#e35cff"; g.strokeStyle = "#2a0a35"; g.lineWidth = 6;
    g.beginPath(); g.moveTo(64, 10); g.bezierCurveTo(100, 54, 108, 70, 108, 84); g.arc(64, 84, 44, 0, Math.PI); g.bezierCurveTo(20, 70, 28, 54, 64, 10); g.fill(); g.stroke();
    g.font = "bold 44px 'Lilita One', system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.lineWidth = 7; g.strokeStyle = "#2a0a35";
    g.strokeText("+1", 64, 84); g.fillStyle = "#ffffff"; g.fillText("+1", 64, 84);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
    sp.renderOrder = 15; sp.position.set(o.g.position.x, o.altura + 0.6, o.g.position.z);
    this.efeito(sp, 1.3, (q) => { sp.position.y = o.altura + 0.6 + q * 1.6; const e = q < 0.15 ? q / 0.15 : 1; sp.scale.setScalar(1.25 * e); sp.material.opacity = q > 0.7 ? (1 - q) / 0.3 : 1; });
  }
  // geada do mago de gelo: estouro azul-claro e floquinhos
  geadaArea(X, Z, raio) {
    const bola = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 10), new THREE.MeshBasicMaterial({ color: 0xd6f6ff, transparent: true, opacity: 0.8, depthWrite: false }));
    bola.position.set(X, 0.5, Z);
    this.efeito(bola, 0.4, (q) => { bola.scale.setScalar(raio * (0.3 + q * 0.9)); bola.material.opacity = 0.8 * (1 - q); });
    this.poeira(X, Z, 0xbff6ff, raio * 1.1);
    const g = new THREE.Group(); g.position.set(X, 0, Z);
    const lista = [], mf = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, depthWrite: false });
    for (let k = 0; k < 10; k++) { const m = new THREE.Mesh(this.geoBolinha, mf), a = Math.random() * 6.28, d = Math.random() * raio; m.scale.setScalar(0.06 + Math.random() * 0.05); lista.push([m, Math.cos(a) * d, Math.sin(a) * d, 0.5 + Math.random() * 1.5]); g.add(m); }
    this.efeito(g, 0.8, (q) => { for (const [m, x, z, h] of lista) m.position.set(x, h * (1 - q), z); mf.opacity = 0.95 * (1 - q); });
  }

  ruina(X, Z, esc) { const r = this.novo("ruina"); r.position.set(X, 0, Z); r.scale.setScalar(esc); this.cena.add(r); (this.ruinas ||= []).push(r); }

  limpar() {
    for (const b of this.bonecos.values()) b.sair(true);
    this.bonecos.clear();
    for (const p of this.projs.values()) p.sair();
    this.projs.clear();
    for (const z of this.zonasVis.values()) this.cena.remove(z.g);
    this.zonasVis.clear();
    for (const r of this.ruinas || []) this.cena.remove(r);
    this.ruinas = [];
    for (const e of this.efeitos) this.cena.remove(e.o);
    this.efeitos = [];
    this.faiscas.limpar(); this.poeiraP.limpar(); this.emissores = [];
    this.ultima = null;
  }

  // ------------------------------------------------------------ efeitos
  efeito(o, dur, passo) { this.cena.add(o); this.efeitos.push({ o, t: 0, dur, passo }); }
  poeira(X, Z, cor, raio) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.6, 0.8, 28).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.8, depthWrite: false }));
    m.position.set(X, 0.07, Z);
    this.efeito(m, 0.45, (q) => { m.scale.setScalar(raio * (0.4 + q * 1.3)); m.material.opacity = 0.8 * (1 - q); });
  }
  fumaca(X, Z, n, raio, cor) {
    const mat = new THREE.MeshLambertMaterial({ color: cor, transparent: true, opacity: 0.9 });
    const g = new THREE.Group(); g.position.set(X, 0.4, Z);
    const bolas = [];
    for (let k = 0; k < n; k++) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.25 + Math.random() * 0.3, 8, 6), mat);
      const a = Math.random() * 6.28, v = (0.5 + Math.random()) * raio;
      bolas.push([m, Math.cos(a) * v, 0.8 + Math.random() * 1.6, Math.sin(a) * v]); g.add(m);
    }
    this.efeito(g, 0.7 + raio * 0.15, (q) => { for (const [m, vx, vy, vz] of bolas) { m.position.set(vx * q, vy * q, vz * q); m.scale.setScalar(1 + q * 1.2); } mat.opacity = 0.9 * (1 - q * q); });
  }
  explosao(X, Z, raio, tipo) {
    if (tipo === "relampago") return this.relampago(X, Z, raio);
    if (tipo === "gelo") return this.geloArea(X, Z, raio);
    if (tipo === "cura") return this.curaArea(X, Z, raio);
    if (tipo === "geada") return this.geadaArea(X, Z, raio);
    if (tipo === "flechas") {                      // chuva de flechas: poeira e flechas fincadas que somem
      this.poeira(X, Z, 0xe8d7a8, raio);
      const g = new THREE.Group(); g.position.set(X, 0, Z);
      for (let k = 0; k < 16; k++) {
        const f = this.novo("flecha"); const a = Math.random() * 6.28, d = Math.sqrt(Math.random()) * raio * 0.85;
        f.position.set(Math.cos(a) * d, 0.25, Math.sin(a) * d); f.rotation.set(-Math.PI / 2 + (Math.random() - 0.5) * 0.5, 0, (Math.random() - 0.5) * 0.5); f.scale.setScalar(1.3); g.add(f);
      }
      this.efeito(g, 1.1, (q) => { g.position.y = q > 0.7 ? -(q - 0.7) * 1.5 : 0; });
      this.fumaca(X, Z, 8, raio * 0.6, 0xd9c9a0);
      return;
    }
    if (tipo === "queda") tipo = undefined;                // bomba do balão: explosão grande, como a bola de fogo
    const cor = tipo === "magia" ? 0x7fefff : 0xff8a1e;
    if (tipo === "magia" || tipo === "sombra") this.faiscas.emitir(X, 0.6, Z, 14, { cores: tipo === "sombra" ? [0xc58bff, 0xffffff] : [0x9ff4ff, 0xffffff], vel: [2, 4], vida: [0.25, 0.5], tam: [0.1, 0.2], grav: -3, arrasto: 2 });
    else this.brasas(X, Z, raio);
    const bola = new THREE.Mesh(new THREE.SphereGeometry(1, 18, 12), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.85 }));
    bola.position.set(X, 0.5, Z);
    this.efeito(bola, 0.38, (q) => { bola.scale.setScalar(raio * (0.3 + q * 0.8)); bola.material.opacity = 0.85 * (1 - q); });
    this.poeira(X, Z, tipo === "magia" ? 0xbff6ff : 0xffd98a, raio * 1.1);
    if (!tipo) this.fumaca(X, Z, 12, raio * 0.8, 0x6a6a6a);
  }

  // relâmpago: três raios em zigue-zague caindo do céu, clarão e anel amarelo no chão
  relampago(X, Z, raio) {
    const mat = new THREE.MeshBasicMaterial({ color: 0xfff7b0, transparent: true, opacity: 1, depthWrite: false, blending: THREE.AdditiveBlending });
    const g = new THREE.Group(); g.position.set(X, 0, Z);
    for (let k = 0; k < 3; k++) {
      const a = Math.random() * 6.28, d = k === 0 ? 0 : raio * (0.35 + Math.random() * 0.45);
      const x0 = Math.cos(a) * d, z0 = Math.sin(a) * d, pts = [];
      for (let j = 0; j <= 7; j++) pts.push(new THREE.Vector3(x0 + (j && j < 7 ? (Math.random() - 0.5) * 1.1 : 0), 15 - j * 15 / 7, z0 + (j && j < 7 ? (Math.random() - 0.5) * 1.1 : 0)));
      const tubo = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0), 28, k === 0 ? 0.16 : 0.1, 6), mat);
      g.add(tubo);
    }
    const flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texBrilho, color: 0xfff2a0, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    flash.position.y = 1; flash.scale.setScalar(raio * 3.2); g.add(flash);
    this.efeito(g, 0.42, (q) => { mat.opacity = q < 0.15 ? 1 : Math.max(0, 1 - (q - 0.15) / 0.85) * (0.6 + 0.4 * Math.sin(q * 60)); flash.material.opacity = 1 - q; });
    this.poeira(X, Z, 0xffe680, raio);
    this.fumaca(X, Z, 6, raio * 0.5, 0x8a8a8a);
    this.faiscas.emitir(X, 0.4, Z, 30, { cores: [0xfff7b0, 0xffffff, 0xffe066], dir: "cima", abre: 2, vel: [3, 7], vida: [0.2, 0.5], tam: [0.1, 0.2], grav: -10, arrasto: 1.5, raio: raio * 0.6, quica: true });
  }
  // gelo: cúpula azul que cresce e some, anel e floquinhos caindo
  geloArea(X, Z, raio) {
    const mat = new THREE.MeshLambertMaterial({ color: 0xcff6ff, emissive: 0x3aa6e0, emissiveIntensity: 0.5, transparent: true, opacity: 0.55, depthWrite: false });
    const cup = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 14, 0, Math.PI * 2, 0, Math.PI / 2), mat);
    cup.position.set(X, 0, Z);
    this.efeito(cup, 0.9, (q) => { const e = raio * (0.3 + 0.75 * Math.min(1, q * 2.4)); cup.scale.set(e, e * 0.55, e); mat.opacity = 0.55 * (1 - Math.max(0, q - 0.4) / 0.6); });
    this.poeira(X, Z, 0xbff6ff, raio * 1.05);
    this.faiscas.emitir(X, 0.3, Z, 26, { cores: [0xd6f6ff, 0xffffff, 0x9fe4ff], dir: "cima", abre: 1.8, vel: [1.5, 4], vida: [0.4, 0.8], tam: [0.1, 0.2], grav: -4, arrasto: 1.6, raio: raio * 0.7 });
    const flocos = new THREE.Group(); flocos.position.set(X, 0, Z);
    const mf = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, depthWrite: false });
    const lista = [];
    for (let k = 0; k < 26; k++) {
      const m = new THREE.Mesh(this.geoBolinha, mf), a = Math.random() * 6.28, d = Math.sqrt(Math.random()) * raio;
      m.scale.setScalar(0.07 + Math.random() * 0.06); lista.push([m, Math.cos(a) * d, Math.sin(a) * d, 2.5 + Math.random() * 3]); flocos.add(m);
    }
    this.efeito(flocos, 1.2, (q) => { for (const [m, x, z, h] of lista) m.position.set(x + Math.sin(q * 9 + h) * 0.15, h * (1 - q), z); mf.opacity = 0.95 * (1 - q * q); });
  }
  // cura: coluna verde, anel e brilhinhos subindo
  curaArea(X, Z, raio) {
    const mat = new THREE.MeshBasicMaterial({ color: 0x6dff96, transparent: true, opacity: 0.35, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending });
    const col = new THREE.Mesh(new THREE.CylinderGeometry(raio, raio, 3.2, 32, 1, true), mat);
    col.position.set(X, 1.6, Z);
    this.efeito(col, 1.0, (q) => { mat.opacity = 0.35 * Math.sin(Math.PI * Math.min(1, q * 1.3)); col.scale.set(1, 0.4 + q, 1); });
    this.poeira(X, Z, 0x7dff9a, raio);
    const g = new THREE.Group(); g.position.set(X, 0, Z);
    const lista = [];
    for (let k = 0; k < 18; k++) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texBrilho, color: 0x8dffa8, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      const a = Math.random() * 6.28, d = Math.sqrt(Math.random()) * raio;
      sp.scale.setScalar(0.5); lista.push([sp, Math.cos(a) * d, Math.sin(a) * d, Math.random() * 0.4]); g.add(sp);
    }
    this.efeito(g, 1.3, (q) => { for (const [sp, x, z, a0] of lista) { const qq = Math.max(0, q - a0); sp.position.set(x, 0.3 + qq * 4, z); sp.material.opacity = Math.max(0, 1 - qq * 1.4); } });
  }

  quadro() {
    const dtReal = this.relogio.getDelta(), dt = Math.min(0.05, dtReal), agora = this.relogio.elapsedTime;
    // qualidade automática: se o aparelho não aguenta ~40 quadros por segundo, desenha com menos pixels
    const Q = this.qual;
    Q.soma += dtReal; Q.n++;
    if (Q.soma > 3) {
      const fps = Q.n / Q.soma;
      if (fps < 40 && this.comBrilho) this.comBrilho = false;
      else if (fps < 40 && Q.razao > 0.75) { Q.razao = Math.max(0.75, Q.razao - 0.35); this.r.setPixelRatio(Q.razao); this.ajustar(); }
      else if (fps < 34 && this.sol.castShadow) this.sol.castShadow = false;
      Q.soma = 0; Q.n = 0;
    }
    if (this.cenario) this.cenario.quadro(agora, dt);
    for (const b of this.bonecos.values()) b.quadro(dt, agora);
    for (const p of this.projs.values()) p.quadro(dt);
    for (const z of this.zonasVis.values()) z.quadro(dt, agora);
    // partículas: tamanho em pixels de acordo com a tela; fogo que fica; clima
    const esc = this.r.getDrawingBufferSize(this._v2).y / (2 * Math.tan(THREE.MathUtils.degToRad(this.cam.fov / 2)));
    this.faiscas.mat.uniforms.escala.value = this.poeiraP.mat.uniforms.escala.value = this.clima.luz.mat.uniforms.escala.value = this.clima.cobre.mat.uniforms.escala.value = esc;
    this.emissores = this.emissores.filter(e => { e.t += dt; e.acc += dt * e.taxa; while (e.acc >= 1) { e.acc--; e.fn(); } return e.t < e.dur; });
    this.faiscas.quadro(dt); this.poeiraP.quadro(dt);
    this.clima.quadro(dt, true);
    this.efeitos = this.efeitos.filter(e => { e.t += dt; const q = Math.min(1, e.t / e.dur); e.passo(q); if (q >= 1) { this.cena.remove(e.o); return false; } return true; });
    if (this.camBase) {
      this.tremor = Math.max(0, this.tremor - dt * 1.6);
      const t = this.tremor * this.tremor;
      this.cam.position.set(this.camBase.x + (Math.random() - 0.5) * t * 1.4, this.camBase.y + (Math.random() - 0.5) * t * 1.4, this.camBase.z);
    }
    if (this.comBrilho) {
      this.composer.render();
      // segurança: se o brilho deixar a tela preta (alguns aparelhos), desliga e lembra
      if (this.conferirBrilho > 0 || (this.qual.n === 1 && Math.random() < 0.1)) {
        if (this.conferirBrilho > 0) this.conferirBrilho--;
        const gl = this.r.getContext(), w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
        let soma = 0;
        for (const [fx, fy] of [[0.5, 0.5], [0.3, 0.7], [0.7, 0.3]]) { gl.readPixels(Math.floor(w * fx), Math.floor(h * fy), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, this._px); soma += this._px[0] + this._px[1] + this._px[2]; }
        if (soma < 6) {
          this.comBrilho = false;
          try { localStorage.setItem("arena-sem-brilho", "1"); } catch (e) { /* ok */ }
          this.r.render(this.cena, this.cam);
        }
      }
    } else this.r.render(this.cena, this.cam);
  }

  // ------------------------------------------------------------ partículas dos eventos
  faisca(X, Y, Z, n, cores, forca = 1) {
    this.faiscas.emitir(X, Y, Z, n, { cores, vel: [2 * forca, 4.5 * forca], vida: [0.18, 0.4], tam: [0.1, 0.2], grav: -9, arrasto: 2.5 });
  }
  alma(X, Z, time, alto = 0.6) {               // tropa morrendo: brilhos na cor do time subindo
    const cor = time === 0 ? [0x7fc4ff, 0xcfe8ff, 0xffffff] : [0xff8a80, 0xffd0c8, 0xffffff];
    this.faiscas.emitir(X, alto, Z, 16, { cores: cor, dir: "cima", abre: 0.9, vel: [1.2, 3.2], vida: [0.5, 0.95], tam: [0.12, 0.26], grav: 1.5, arrasto: 1.2, raio: 0.3 });
  }
  brasas(X, Z, raio, cores = [0xffb347, 0xff7a2e, 0xffe08a]) {
    this.faiscas.emitir(X, 0.6, Z, Math.round(14 + raio * 8), { cores, dir: "cima", abre: 1.6, vel: [2.5, 6.5], vida: [0.5, 1.1], tam: [0.1, 0.24], grav: -7, arrasto: 0.9, raio: raio * 0.4, quica: true });
    this.poeiraP.emitir(X, 0.4, Z, Math.round(6 + raio * 3), { cores: [0x6b6b6b, 0x8a8278, 0x4a4a4a], dir: "cima", abre: 1.2, vel: [0.8, 2], vida: [0.9, 1.6], tam: [0.7, 1.2], grav: 0.6, arrasto: 1.4, cresce: 1.4, alfa: 0.55, raio: raio * 0.5 });
  }
  onda(X, Z, raio, cores) {                     // golpe forte e pouso: anel de faíscas rente ao chão
    this.faiscas.emitir(X, 0.15, Z, 22, { cores, dir: "anel", abre: 0.25, vel: [3, 5.5 * raio], vida: [0.25, 0.45], tam: [0.12, 0.22], grav: -2, arrasto: 3 });
  }
  // torre caída: pedaços voando, faíscas e fogo com fumaça por uns segundos
  destrocos(X, Z, esc) {
    const mat = new THREE.MeshLambertMaterial({ color: 0x8c8780 }), g = new THREE.Group(), lista = [];
    for (let k = 0; k < 14; k++) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), mat), tam = 0.18 + Math.random() * 0.3 * esc;
      m.scale.set(tam, tam * 0.8, tam * 1.1);
      const a = Math.random() * 6.28, v = 2 + Math.random() * 4;
      lista.push([m, Math.cos(a) * v, 4 + Math.random() * 5, Math.sin(a) * v, Math.random() * 8, 2 + Math.random() * 2.5]); g.add(m);
    }
    g.position.set(X, 0, Z);
    this.efeito(g, 1.5, (q) => {
      const t = q * 1.5;
      for (const [m, vx, vy, vz, gr, h0] of lista) { m.position.set(vx * t, Math.max(0.1, h0 + vy * t - 9.8 * t * t / 2), vz * t); m.rotation.set(gr * t, gr * t * 0.7, 0); }
      mat.transparent = q > 0.8; mat.opacity = q > 0.8 ? (1 - q) / 0.2 : 1;
    });
    this.brasas(X, Z, 2.2 * esc);
    this.emissores.push({ t: 0, dur: 4.5, taxa: 26, acc: 0, fn: () => {
      this.faiscas.emitir(X, 0.6, Z, 1, { cores: [0xff9a2e, 0xffd36b, 0xff6a2a], dir: "cima", abre: 0.5, vel: [1.4, 2.6], vida: [0.5, 0.9], tam: [0.45, 0.8], grav: 0.8, arrasto: 1, cresce: -0.6, raio: 1.0 * esc });
      if (Math.random() < 0.4) this.poeiraP.emitir(X, 1.6, Z, 1, { cores: [0x4a4a4a, 0x5e5a56], dir: "cima", abre: 0.3, vel: [0.8, 1.4], vida: [1.4, 2.2], tam: [0.8, 1.3], grav: 0.3, arrasto: 0.5, cresce: 1.6, alfa: 0.45, raio: 0.8 * esc });
    } });
  }
  // fogos de artifício em cima do lado do adversário (vitória)
  fogos() {
    const cores = [[0xffd36b, 0xffffff], [0x7fc4ff, 0xffffff], [0xff7ad9, 0xffffff], [0x8dff9a, 0xffffff], [0xffa04d, 0xfff0a0]];
    for (let k = 0; k < 9; k++) {
      const X = (Math.random() - 0.5) * 14, Z = (this.visao === 0 ? -1 : -1) * (6 + Math.random() * 9), alto = 9 + Math.random() * 5, atraso = k * 0.33 + Math.random() * 0.2;
      const c = cores[k % cores.length];
      this.efeito(new THREE.Group(), atraso + 0.7, (q) => {
        const t = q * (atraso + 0.7);
        if (t >= atraso && !this._f?.has(`${k}`)) {
          (this._f ||= new Set()).add(`${k}`);
          this.faiscas.emitir(X, 0.5, Z, 10, { cores: [0xfff0c0], dir: [0, 1, 0], abre: 0.05, vel: [alto * 1.2, alto * 1.25], vida: [0.55, 0.6], tam: [0.12, 0.18], grav: -6, arrasto: 0.2 });
        }
        if (q >= 1) {
          this.faiscas.emitir(X, alto, Z, 70, { cores: c, vel: [3, 7], vida: [0.9, 1.6], tam: [0.16, 0.3], grav: -2.2, arrasto: 1.1 });
          this.aoSom && this.aoSom("fogos");
        }
      });
    }
    setTimeout(() => { this._f = null; }, 4000);
  }
}

// ------------------------------------------------------------------ uma tropa, torre ou construção
class Boneco {
  constructor(c, id, k, lado, x, y, hpMax, a) {
    this.c = c; this.id = id; this.k = k; this.lado = lado; this.hpMax = hpMax;
    const time = lado === c.visao ? 0 : 1;
    this.time = time;
    this.fixa = k === "torre" || k === "rei";
    const carta = CARTAS[k];
    const modelo = this.fixa ? (k === "rei" ? "castelo" : "torre") : (carta.modelo || k);
    this.raio = this.fixa ? (k === "rei" ? 1.85 : 1.3) : carta.raio;
    this.voa = !this.fixa && !!carta.voa;
    this.predio = this.fixa || carta.tipo === "predio";
    this.g = new THREE.Group();
    this.m = c.novo(modelo, time);
    this.g.add(this.m);
    this.mats = [];                                   // materiais só deste boneco (para piscar quando apanha)
    this.m.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); this.mats.push(o.material); o.castShadow = true; o.receiveShadow = this.fixa; } });
    this.pisca = 0;
    this.esc = 1;
    if (KAYKIT[modelo]) {
      const gl = c.modelos[modelo];
      this.esc = KAYKIT[modelo] / gl.altura;
      this.mixer = new THREE.AnimationMixer(this.m);
      this.acoes = {};
      for (const clip of gl.animations) this.acoes[clip.name] = this.mixer.clipAction(clip);
      this.acoes.atacar.setLoop(THREE.LoopOnce); this.acoes.atacar.clampWhenFinished = false;
      this.dAtq = gl.animations.find(a => a.name === "atacar").duration;
      this.base = null;
      this.mixer.addEventListener("finished", () => { this.atacando = false; this.tocar(this.est === 1 ? "andar" : "parado", 0.12); });
      this.altura = KAYKIT[modelo];
    } else {
      this.pecas = {};
      this.m.traverse(o => { this.pecas[o.name] = o; });
      this.altura = this.fixa ? (k === "rei" ? 6.7 : 5.1) : k === "balao" ? ALT_BALAO + 3.3 : this.voa ? ALT_VOO + 1.9 : ALT_PREDIO[k] || 2.7;
      if (k === "dragao") this.esc = 1.3;
    }
    this.m.scale.setScalar(this.esc);
    this.g.position.set(c.X(x), 0, c.Z(y));
    this.ang = this.fixa ? 0 : c.giro(a);               // torres e castelos sempre de frente para a câmera
    this.m.rotation.y = this.predio ? 0 : this.ang;
    if (this.voa) {
      this.m.position.y = k === "balao" ? ALT_BALAO : ALT_VOO;
      const s = new THREE.Mesh(c.geoDisco, c.matSombra); s.scale.setScalar(this.raio * 1.6); s.position.y = 0.035; this.g.add(s);
    }
    // disco do time no chão
    if (!this.fixa) {
      const d = new THREE.Mesh(c.geoDisco, c.matDisco[time]);
      d.scale.setScalar(this.raio * 1.25); d.position.y = 0.04; this.g.add(d);
    }
    // barra de vida
    const larg = this.fixa ? 2.4 : Math.max(0.9, this.raio * 2.2), alt = this.fixa ? 0.34 : 0.17;
    this.barra = new THREE.Group();
    const fundo = new THREE.Sprite(c.matBarra.fundo); fundo.scale.set(larg + 0.1, alt + 0.1, 1);
    this.vida = new THREE.Sprite(c.matBarra[time]); this.vida.center.set(0, 0.5); this.vida.position.x = -larg / 2; this.vida.scale.set(larg, alt, 1);
    fundo.renderOrder = 10; this.vida.renderOrder = 11;
    this.barra.add(fundo, this.vida);
    this.barra.position.y = this.altura + 0.45;
    this.barra.visible = this.fixa && !c.demo;
    this.largBarra = larg; this.altBarra = alt;
    this.g.add(this.barra);
    if (this.fixa) {
      const cv = document.createElement("canvas"); cv.width = 128; cv.height = 48;
      this.cvNum = cv; this.texNum = new THREE.CanvasTexture(cv); this.texNum.colorSpace = THREE.SRGBColorSpace;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texNum, depthTest: false })); sp.scale.set(1.9, 0.72, 1); sp.position.y = 0.62; sp.renderOrder = 12;
      this.barra.add(sp);
    }
    this.tx = x; this.ty = y; this.hp = hpMax; this.est = 0; this.tn = 0; this.soco = 0; this.tAtq = 9; this.f = 0; this.tPoeira = 0;
    c.cena.add(this.g);
    if (this.mixer) {
      if (this.acoes.nascer && !this.fixa) {               // os esqueletos saem do chão
        const a = this.acoes.nascer; a.setLoop(THREE.LoopOnce); a.clampWhenFinished = true;
        a.setEffectiveTimeScale(Math.max(1, a.getClip().duration / 1.0)).play(); this.nascendo = true; this.base = "nascer";
      } else this.tocar("parado", 0);
    }
  }

  tocar(nome, fade = 0.15) {
    if (this.base === nome && !this.atacando) return;
    const nova = this.acoes[nome];
    if (!nova) return;
    for (const [n, a] of Object.entries(this.acoes)) if (n !== nome && a.isRunning()) a.fadeOut(fade);
    nova.reset().setEffectiveWeight(1).fadeIn(fade).play();
    if (nome !== "atacar") this.base = nome;
  }

  alvo(x, y, hp, est, a, tn) {
    this.tx = x; this.ty = y; this.est = est; this.tn = tn;
    if (hp !== this.hp) {
      this.hp = hp;
      const q = Math.max(0, hp / this.hpMax);
      this.vida.scale.x = Math.max(0.001, this.largBarra * q);
      if (!this.fixa) this.barra.visible = q < 0.999;
      if (this.fixa) this.numero();
    } else if (this.fixa && !this.temNum) this.numero();
    if (!this.fixa) this.angAlvo = this.c.giro(a);
    if (this.nascendo && tn <= 0) this.nascendo = false;
    if (this.mixer && !this.atacando && !this.nascendo) this.tocar(est === 1 ? "andar" : "parado");
  }

  numero() {
    this.temNum = true;
    const g = this.cvNum.getContext("2d");
    g.clearRect(0, 0, 128, 48);
    g.font = "bold 34px 'Lilita One', system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
    g.lineWidth = 7; g.strokeStyle = "#10182b"; g.strokeText(String(this.hp), 64, 26);
    g.fillStyle = "#ffffff"; g.fillText(String(this.hp), 64, 26);
    this.texNum.needsUpdate = true;
  }

  atacar() {
    this.tAtq = 0;
    if (this.mixer) {
      this.atacando = true;
      const cad = CARTAS[this.k].cad, a = this.acoes.atacar;
      for (const [n, o] of Object.entries(this.acoes)) if (n !== "atacar" && o.isRunning()) o.fadeOut(0.08);
      a.reset().setEffectiveTimeScale(Math.max(1, this.dAtq / (cad * 0.95))).setEffectiveWeight(1).fadeIn(0.06).play();
    }
  }
  apanhar() { this.soco = 1; this.pisca = 1; }
  // 0 normal, 1 tonto (estrelinhas girando), 2 congelado (bloco de gelo e cor azulada)
  parar(v) {
    if (v === this.parado) return;
    this.parado = v;
    if (v === 1 && !this.estrelas) {
      this.estrelas = new THREE.Group();
      for (let k = 0; k < 3; k++) { const e = new THREE.Sprite(this.c.matEstrela); e.scale.setScalar(0.5); this.estrelas.add(e); }
      this.estrelas.position.y = this.altura + 0.15; this.g.add(this.estrelas);
    }
    if (v === 2 && !this.blocoGelo) {
      const r = this.raio * (this.fixa ? 1.0 : 1.15), h = this.fixa ? this.altura * 0.75 : this.altura * 0.95;
      this.blocoGelo = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 1.08, h, 7), this.c.matGelo);
      this.blocoGelo.position.y = h / 2 + (this.voa ? ALT_VOO - 0.6 : 0); this.g.add(this.blocoGelo);
    }
    if (this.estrelas) this.estrelas.visible = v === 1;
    if (this.blocoGelo) this.blocoGelo.visible = v === 2;
    for (const m of this.mats) if (m.emissive) { if (v === 2) m.emissive.setRGB(0.1, 0.35, 0.6); else m.emissive.setScalar(0); }
  }
  // marcas que vêm da partida: 1 investida, 2 lento, 4 fúria, 8 no ar (salto)
  marcas(f) {
    if (f === this.f) return;
    const antes = this.f;
    this.f = f;
    if ((f & 4) && !this.aneFuria) {                     // fúria: anel rosa-choque girando nos pés
      this.aneFuria = new THREE.Mesh(new THREE.RingGeometry(0.75, 1, 24, 1, 0, Math.PI * 1.6).rotateX(-Math.PI / 2),
        new THREE.MeshBasicMaterial({ color: 0xff4fd8, transparent: true, opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending }));
      this.aneFuria.position.y = 0.08; this.aneFuria.scale.setScalar(this.raio * 1.5); this.g.add(this.aneFuria);
    }
    if (this.aneFuria) this.aneFuria.visible = !!(f & 4);
    if ((f & 8) && !(antes & 8) && !this.tSalto) this.saltar();
    if (this.mixer) this.mixer.timeScale = (f & 2 ? 0.65 : 1) * (f & 4 ? 1.4 : 1) * (f & 1 ? 1.35 : 1);
    this.tingir();
  }
  saltar() {
    this.tSalto = performance.now();
    if (this.acoes && this.acoes.saltar) {
      this.atacando = true;
      const a = this.acoes.saltar;
      for (const [n, o] of Object.entries(this.acoes)) if (n !== "saltar" && o.isRunning()) o.fadeOut(0.06);
      a.setLoop(THREE.LoopOnce); a.clampWhenFinished = false;
      a.reset().setEffectiveTimeScale(Math.max(1, a.getClip().duration / 0.62)).setEffectiveWeight(1).fadeIn(0.05).play();
    }
  }
  // cor por cima do modelo: piscada de quando apanha, azul do lento, rosa da fúria
  tingir() {
    const p = this.pisca * 0.45, f = this.f || 0;
    const r = p + (f & 4 ? 0.13 : 0), g = p + (f & 2 ? 0.05 : 0), b = p + (f & 2 ? 0.13 : 0) + (f & 4 ? 0.07 : 0);
    for (const m of this.mats) if (m.emissive) m.emissive.setRGB(r, g, b);
  }
  invocar() {
    const a = this.acoes && this.acoes.invocar;
    if (!a) return;
    this.atacando = true;
    for (const [n, o] of Object.entries(this.acoes)) if (n !== "invocar" && o.isRunning()) o.fadeOut(0.08);
    a.setLoop(THREE.LoopOnce); a.reset().setEffectiveTimeScale(1.4).setEffectiveWeight(1).fadeIn(0.06).play();
  }

  quadro(dt, agora) {
    const c = this.c, p = this.g.position;
    const k = 1 - Math.exp(-dt * 13);
    p.x += (c.X(this.tx) - p.x) * k; p.z += (c.Z(this.ty) - p.z) * k;
    if (!this.predio && this.angAlvo != null) {
      let d = this.angAlvo - this.ang; d = Math.atan2(Math.sin(d), Math.cos(d));
      this.ang += d * (1 - Math.exp(-dt * 12));
      this.m.rotation.y = this.ang;
    }
    this.soco = Math.max(0, this.soco - dt * 7);
    if (this.parado) {                                   // tonto ou congelado: não anima
      if (this.estrelas && this.parado === 1) { const t = agora * 6; this.estrelas.children.forEach((e, k) => e.position.set(Math.cos(t + k * 2.09) * 0.45, Math.sin(t * 2 + k) * 0.06, Math.sin(t + k * 2.09) * 0.45)); }
      this.m.scale.setScalar(this.esc);
      return;
    }
    if (this.pisca > 0) { this.pisca = Math.max(0, this.pisca - dt * 6); this.tingir(); }
    if (this.aneFuria && this.aneFuria.visible) this.aneFuria.rotation.y += dt * 5;
    if ((this.f & 1) && this.est === 1) {                // investida: poeira saindo dos pés
      this.tPoeira -= dt;
      if (this.tPoeira <= 0) { this.tPoeira = 0.1; this.c.fumaca(p.x, p.z, 2, 0.25, 0xe7dcc2); }
    }
    if (this.tSalto) {                                    // salto: arco no ar
      const q = (performance.now() - this.tSalto) / 560;
      if (q >= 1 && !(this.f & 8)) { this.tSalto = 0; this.m.position.y = 0; }
      else this.m.position.y = Math.sin(Math.PI * Math.min(1, q)) * 2.3;
    }
    this.tAtq += dt;
    // nascendo: cresce com um quique
    let esc = this.esc * (1 + this.soco * 0.07);
    if (this.tn > 0 && !this.acoes?.nascer) { const q = 1 - Math.min(1, this.tn); esc *= 0.35 + 0.65 * (1 - Math.pow(1 - q, 3)); }
    this.m.scale.setScalar(esc);
    if (this.mixer) { this.mixer.update(dt); return; }
    const P = this.pecas, golpe = Math.max(0, 1 - this.tAtq / 0.35);
    if (this.k === "dragao") {
      const bate = Math.sin(agora * 11);
      if (P.asa_e) P.asa_e.rotation.z = 0.25 + bate * 0.55;
      if (P.asa_d) P.asa_d.rotation.z = -0.25 - bate * 0.55;
      if (P.cauda) P.cauda.rotation.y = Math.sin(agora * 3) * 0.3;
      if (P.cabeca) P.cabeca.rotation.x = -golpe * 0.5;
      this.m.position.y = ALT_VOO + Math.sin(agora * 2.4 + this.id) * 0.14 - bate * 0.05;
      this.m.rotation.x = 0.12;
    } else if (this.k === "balao") {
      this.m.position.y = ALT_BALAO + Math.sin(agora * 1.7 + this.id) * 0.13;
      this.m.rotation.z = Math.sin(agora * 1.1 + this.id) * 0.05;
      if (P.bomba) P.bomba.visible = this.tAtq > 1.1;
    } else if (this.k === "catapulta") {
      if (P.catapult_turret && this.angAlvo != null) {            // a catapulta gira no topo da torre e o braço dá o golpe
        let d = this.angAlvo - this.ang; d = Math.atan2(Math.sin(d), Math.cos(d));
        this.ang += d * (1 - Math.exp(-dt * 10));
        P.catapult_turret.rotation.y = this.ang;
      }
      if (P.catapult_arm) P.catapult_arm.rotation.x = -golpe * 1.3;
    }
  }

  // morte: encolhe, afunda e some (na limpeza da partida, some na hora)
  sair(seco) {
    if (seco || this.fixa) { this.c.cena.remove(this.g); if (this.mixer) this.mixer.stopAllAction(); return; }
    this.c.cena.remove(this.g);
    const g = this.g, m = this.m, e0 = m.scale.x, y0 = m.position.y;
    for (const mt of this.mats) { mt.transparent = true; }
    this.barra.visible = false;
    this.c.efeito(g, 0.35, (q) => {
      m.scale.setScalar(e0 * (1 - q * 0.7)); m.position.y = y0 - q * (this.voa ? 1.6 : 0.4); m.rotation.z = q * 0.6;
      for (const mt of this.mats) { mt.opacity = 1 - q; if (mt.emissive) mt.emissive.setScalar(0.5 * (1 - q)); }
    });
  }
}

// ------------------------------------------------------------------ zonas no chão (veneno e fúria)
class Zona {
  constructor(c, z) {
    this.c = c; this.k = z[1];
    const r = z[4], veneno = this.k === "veneno", cor = veneno ? 0x6dff5a : 0xff4fd8;
    this.g = new THREE.Group(); this.g.position.set(c.X(z[2]), 0, c.Z(z[3]));
    this.disco = new THREE.Mesh(new THREE.CircleGeometry(r, 40).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0, depthWrite: false }));
    this.disco.position.y = 0.06;
    this.borda = new THREE.Mesh(new THREE.RingGeometry(r * 0.94, r, 48).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.borda.position.y = 0.08;
    this.g.add(this.disco, this.borda);
    if (veneno) {                                     // cúpula de névoa verde
      this.cupula = new THREE.Mesh(new THREE.SphereGeometry(r, 28, 12, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshLambertMaterial({ color: 0x8dff6a, emissive: 0x2c8a1c, emissiveIntensity: 0.6, transparent: true, opacity: 0, depthWrite: false }));
      this.cupula.scale.y = 0.42; this.g.add(this.cupula);
    }
    this.bolhas = [];
    const mat = new THREE.SpriteMaterial({ map: c.texBrilho, color: veneno ? 0xa8ff7a : 0xff8ae8, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    for (let k = 0; k < (veneno ? 22 : 16); k++) {
      const sp = new THREE.Sprite(mat), a = Math.random() * 6.28, d = Math.sqrt(Math.random()) * r * 0.92;
      sp.scale.setScalar(veneno ? 0.35 + Math.random() * 0.35 : 0.28 + Math.random() * 0.2);
      this.bolhas.push([sp, Math.cos(a) * d, Math.sin(a) * d, Math.random(), 0.6 + Math.random() * 0.7]); this.g.add(sp);
    }
    this.matBolha = mat; this.t = 0; this.fim = 0;
    c.cena.add(this.g);
  }
  quadro(dt) {
    this.t += dt;
    const entra = Math.min(1, this.t / 0.35), sai = this.fim ? Math.max(0, 1 - (this.t - this.fim) / 0.4) : 1, a = entra * sai;
    const veneno = this.k === "veneno";
    this.disco.material.opacity = (veneno ? 0.3 : 0.22) * a;
    this.borda.material.opacity = 0.85 * a;
    if (this.cupula) this.cupula.material.opacity = 0.2 * a;
    if (!veneno) this.borda.rotation.y += dt * 1.5;
    this.matBolha.opacity = a;
    for (const b of this.bolhas) {                     // bolhas (veneno) ou faíscas (fúria) subindo sem parar
      const [sp, x, z, f, v] = b;
      const q = (this.t * v + f) % 1;
      sp.position.set(x, q * (veneno ? 1.6 : 2.6), z);
      sp.material.opacity = a;
    }
    if (this.fim && sai <= 0) { this.c.cena.remove(this.g); this.morta = true; }
  }
  // some devagar (o efeito vazio só serve para continuar chamando o quadro até sumir)
  sair() { this.fim = this.t; const z = this; this.c.efeito(new THREE.Group(), 0.5, () => { if (!z.morta) z.quadro(1 / 60); }); }
}

// ------------------------------------------------------------------ projéteis
class Projetil {
  constructor(c, p) {
    this.c = c; this.tipo = p[1];
    const time = p[5] === c.visao ? 0 : 1;
    this.carta = p[6];
    if (this.tipo === "bola" && this.carta === "flechas") {             // chuva de flechas: um bando de flechas voando junto
      this.o = new THREE.Group();
      for (let k = 0; k < 14; k++) { const f = c.novo("flecha"); f.scale.setScalar(1.4); f.position.set((Math.random() - 0.5) * 2.6, (Math.random() - 0.5) * 1.2, (Math.random() - 0.5) * 2.2); this.o.add(f); }
    } else if (this.tipo === "bola") { this.o = c.novo("bola_fogo"); this.o.scale.setScalar(1.9); }
    else if (this.tipo === "queda") {                                     // bomba do balão
      this.o = new THREE.Group();
      const bomba = new THREE.Mesh(c.geoBolinha, new THREE.MeshLambertMaterial({ color: 0x1d1f26 })); bomba.scale.setScalar(0.3); this.o.add(bomba);
      const pavio = new THREE.Sprite(new THREE.SpriteMaterial({ map: c.texBrilho, color: 0xffb347, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      pavio.position.y = 0.38; pavio.scale.setScalar(0.5); this.o.add(pavio);
    }
    else if (this.tipo === "fogo") { this.o = c.novo("bola_fogo"); this.o.scale.setScalar(0.75); }
    else if (this.tipo === "pedra") { this.o = c.novo("pedra_cat"); }
    else if (this.tipo === "flecha" || this.tipo === "virote") { this.o = c.novo("flecha"); this.o.scale.setScalar(this.tipo === "virote" ? 1.5 : 1.25); }
    else {                                         // magia do mago e a sombra do necromante: bolinha brilhante
      const cor = this.tipo === "sombra" ? 0xc58bff : this.tipo === "geada" ? 0xc9f3ff : time === 0 ? 0x9ff4ff : 0xffa6f2;
      this.o = new THREE.Group();
      this.o.add(new THREE.Mesh(c.geoBolinha, new THREE.MeshBasicMaterial({ color: 0xffffff })));
      this.o.children[0].scale.setScalar(0.16);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: c.texBrilho, color: cor, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      halo.scale.setScalar(1.1); this.o.add(halo);
    }
    this.corRastro = this.carta === "flechas" ? null : COR_RASTRO[this.tipo] && (this.tipo === "magia" && time === 1 ? 0xff9df0 : COR_RASTRO[this.tipo]);
    this.tRastro = 0;
    this.h0 = this.tipo === "bola" ? 4 : p[4] ? 3.6 : this.tipo === "fogo" ? ALT_VOO + 0.9 : this.tipo === "pedra" ? 2.6 : 1.3;
    this.h1 = p[6] ? ALT_VOO + 0.5 : 0.9;
    this.x = p[2]; this.y = p[3];
    this.o.position.set(c.X(this.x), this.h0, c.Z(this.y));
    this.d0 = this.tipo === "bola" || this.tipo === "queda" ? 1 : Math.max(0.5, Math.hypot(p[7] - p[2], p[8] - p[3]));
    if (this.tipo === "queda") this.o.position.y = ALT_BALAO + 0.1;
    c.cena.add(this.o);
  }
  alvo(p) {
    this.tx = p[2]; this.ty = p[3];
    this.q = this.tipo === "bola" || this.tipo === "queda" ? p[4] : 1 - Math.min(1, Math.hypot(p[7] - p[2], p[8] - p[3]) / this.d0);
  }
  quadro(dt) {
    const c = this.c, o = this.o, k = 1 - Math.exp(-dt * 22);
    const antes = o.position.clone();
    this.x += (this.tx - this.x) * k; this.y += (this.ty - this.y) * k;
    const q = this.q || 0;
    if (this.tipo === "queda") {
      o.position.set(c.X(this.x), 0.25 + (ALT_BALAO - 0.15) * (1 - q * q), c.Z(this.y)); o.rotation.z += dt * 3;
      if (Math.random() < 0.6) c.faiscas.emitir(o.position.x, o.position.y + 0.4, o.position.z, 1, { cores: [0xffd36b, 0xffffff], vel: [0.5, 1.5], vida: [0.15, 0.3], tam: [0.06, 0.12], grav: -3 });
      return;
    }
    const h = this.tipo === "bola" ? 1.2 + Math.sin(Math.PI * q) * 7 + (1 - q) * 2.5 : this.h0 + (this.h1 - this.h0) * q + Math.sin(Math.PI * q) * (this.tipo === "pedra" ? 1.8 : 0.7);
    o.position.set(c.X(this.x), h, c.Z(this.y));
    const v = o.position.clone().sub(antes);
    if (v.lengthSq() > 1e-6) o.lookAt(o.position.clone().add(v));
    if (this.tipo === "bola" && this.carta !== "flechas") o.rotateZ(dt * 9);
    this.tRastro += dt;
    if (this.tRastro > 0.03) {
      this.tRastro = 0;
      if (this.corRastro) c.rastro(o.position, this.corRastro, this.tipo === "bola" ? 0.5 : this.tipo === "fogo" ? 0.28 : 0.16);
      const P = o.position, fogo = this.tipo === "fogo" || (this.tipo === "bola" && this.carta !== "flechas");
      if (fogo) c.faiscas.emitir(P.x, P.y, P.z, this.tipo === "bola" ? 3 : 2, { cores: [0xffb347, 0xff7a2e, 0xffe08a], vel: [0.3, 1.2], vida: [0.25, 0.5], tam: this.tipo === "bola" ? [0.25, 0.5] : [0.12, 0.3], grav: 1.2, arrasto: 2, raio: 0.15 });
      else if (this.corRastro) c.faiscas.emitir(P.x, P.y, P.z, 1, { cores: [this.corRastro, 0xffffff], vel: [0.2, 0.6], vida: [0.2, 0.35], tam: [0.1, 0.18], grav: 0, arrasto: 2 });
      else if (this.tipo === "flecha" || this.tipo === "virote") c.faiscas.emitir(P.x, P.y, P.z, 1, { cores: [0xffffff], vel: [0, 0.1], vida: [0.1, 0.14], tam: [0.06, 0.09], grav: 0, alfa: 0.5 });
    }
    if (this.tipo === "pedra") o.rotateX(this.giro = (this.giro || 0) + dt * 9);
  }
  sair() { this.c.cena.remove(this.o); }
}
