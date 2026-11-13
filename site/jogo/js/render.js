// A parte 3D (Three.js): arena, torres, tropas animadas, projéteis, barras de vida e efeitos.
// Recebe "fotos" do estado (sim.js → foto()) e desenha, suavizando o movimento entre uma foto e outra.
// visao = de que lado o jogador está: o campo dele sempre aparece embaixo e as coisas dele sempre em azul.
import * as THREE from "three";
import { GLTFLoader } from "../vendor/GLTFLoader.js";
import * as SkeletonUtils from "../vendor/SkeletonUtils.js";
import { CARTAS, L, C, RIO0, RIO1, PONTES } from "./sim.js";

const AZUL = new THREE.Color("#2F7BFF"), VERMELHO = new THREE.Color("#F0463C");
// modelos do pacote KayKit (com esqueleto e animações): altura no jogo, em casas
const KAYKIT = { cavaleiro: 2.2, besteiro: 1.9, gigante: 3.6, mago: 2.2, bandido: 1.7 };
const MEUS = ["dragao", "bola_fogo", "flecha", "ponte"];                      // modelados por código no Blender
// do pacote KayKit Medieval Hexagon: um arquivo azul e um vermelho, ou um só (neutros)
const PREDIOS_TIME = ["torre", "castelo", "catapulta"], NEUTROS = ["ruina", "pedra_cat", "arvore", "pinheiro", "pedra", "bosque"];
const ALT_VOO = 1.9;

export class Cena {
  constructor(canvas) {
    this.canvas = canvas;
    this.r = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.cena = new THREE.Scene();
    this.cena.background = new THREE.Color("#274E2B");
    this.cam = new THREE.PerspectiveCamera(30, 1, 1, 300);
    this.cena.add(new THREE.HemisphereLight(0xffffff, 0x7d8a6a, 1.15));
    const sol = new THREE.DirectionalLight(0xfff1d6, 1.9);
    sol.position.set(-8, 18, 10);
    this.cena.add(sol);
    this.visao = 0;
    this.bonecos = new Map();       // id → Boneco
    this.projs = new Map();
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
    this.matBarra = { fundo: new THREE.SpriteMaterial({ color: 0x10182b, depthTest: false }), 0: new THREE.SpriteMaterial({ color: 0x4d9bff, depthTest: false }),
      1: new THREE.SpriteMaterial({ color: 0xff5a4f, depthTest: false }) };
  }

  // ------------------------------------------------------------ carregar os modelos
  async carregar(base, progresso) {
    const loader = new GLTFLoader();
    const nomes = [...Object.keys(KAYKIT), ...MEUS, ...NEUTROS, ...PREDIOS_TIME.flatMap(n => [`${n}_azul`, `${n}_vermelho`])];
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
    const cv = document.createElement("canvas"), T = 48;
    cv.width = L * T; cv.height = C * T;
    const g = cv.getContext("2d");
    for (let y = 0; y < C; y++) for (let x = 0; x < L; x++) {
      const claro = (x + y) % 2 === 0;
      g.fillStyle = claro ? "#7FC65A" : "#74BC51";
      g.fillRect(x * T, y * T, T, T);
    }
    // caminhos de terra das pontes até as torres
    g.fillStyle = "rgba(196,164,108,0.55)";
    for (const px of PONTES) { g.fillRect((px - 1) * T, 5 * T, 2 * T, 22 * T); }
    g.fillRect(2.5 * T, 5.2 * T, 13 * T, 1.6 * T); g.fillRect(2.5 * T, (C - 6.8) * T, 13 * T, 1.6 * T);
    // rio
    const rio = g.createLinearGradient(0, RIO0 * T, 0, RIO1 * T);
    rio.addColorStop(0, "#3FA9E0"); rio.addColorStop(0.5, "#2C8FD0"); rio.addColorStop(1, "#3FA9E0");
    g.fillStyle = rio; g.fillRect(0, RIO0 * T, L * T, (RIO1 - RIO0) * T);
    g.strokeStyle = "rgba(255,255,255,0.35)"; g.lineWidth = 3;
    for (let k = 0; k < 26; k++) { const x = (k * 37 % 100) / 100 * L * T, y = (RIO0 + 0.3 + (k * 53 % 100) / 100 * 1.4) * T; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + 14, y - 5, x + 28, y); g.stroke(); }
    g.fillStyle = "#C9B58A"; g.fillRect(0, RIO0 * T - 5, L * T, 5); g.fillRect(0, RIO1 * T, L * T, 5);
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
    const chao = new THREE.Mesh(new THREE.PlaneGeometry(L, C).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ map: tex }));
    this.cena.add(chao);
    const fora = new THREE.Mesh(new THREE.PlaneGeometry(90, 110).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ color: "#3E7A3A" }));
    fora.position.y = -0.03; this.cena.add(fora);
    // mureta em volta
    const pedra = new THREE.MeshLambertMaterial({ color: "#B9B1A2" });
    for (const [x, z, sx, sz] of [[0, -C / 2 - 0.3, L + 1.2, 0.6], [0, C / 2 + 0.3, L + 1.2, 0.6], [-L / 2 - 0.3, 0, 0.6, C], [L / 2 + 0.3, 0, 0.6, C]]) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(sx, 0.5, sz), pedra); m.position.set(x, 0.2, z); this.cena.add(m);
    }
    for (const px of PONTES) { const p = this.novo("ponte"); p.position.set(px - L / 2, 0.02, 0); this.cena.add(p); }
    // árvores, pedras e arbustos em volta (sempre nos mesmos lugares)
    let s = 7;
    const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
    for (let k = 0; k < 64; k++) {
      const lado = k % 2 ? 1 : -1, x = lado * (L / 2 + 1.8 + rnd() * 7), z = (rnd() - 0.5) * (C + 14);
      const tipo = ["arvore", "pinheiro", "arvore", "bosque", "pedra", "pinheiro"][Math.floor(rnd() * 6)];
      const o = this.novo(tipo); const e = 0.85 + rnd() * 0.6;
      o.position.set(x + (tipo === "bosque" ? lado * 2 : 0), 0, z); o.scale.setScalar(e); o.rotation.y = rnd() * 6.28; this.cena.add(o);
    }
    for (let k = 0; k < 14; k++) {
      const o = this.novo(k % 3 ? "pinheiro" : "bosque"); o.position.set((rnd() - 0.5) * 26, 0, -(C / 2 + 3 + rnd() * 5)); o.scale.setScalar(1 + rnd() * 0.5); this.cena.add(o);
    }
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

  // sim → mundo 3D (o campo de quem joga fica perto da câmera)
  X(x) { return this.visao ? L / 2 - x : x - L / 2; }
  Z(y) { return this.visao ? y - C / 2 : C / 2 - y; }
  giro(a) { return this.visao ? -a : Math.PI - a; }
  paraSim(X, Z) { return this.visao ? [L / 2 - X, Z + C / 2] : [X + L / 2, C / 2 - Z]; }

  ajustar() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) return;
    this.r.setSize(w, h, false);
    this.cam.aspect = w / h;
    this.cam.updateProjectionMatrix();
    // enquadra a arena inteira entre a barra de cima e as cartas
    const el = THREE.MathUtils.degToRad(47), dir = new THREE.Vector3(0, Math.sin(el), Math.cos(el));
    const pts = [];
    for (const x of [-L / 2 - 0.4, L / 2 + 0.4]) { pts.push(new THREE.Vector3(x, 0, C / 2 + 0.6), new THREE.Vector3(x, 0, -C / 2 - 0.4), new THREE.Vector3(x * 0.3, 5.6, -C / 2 + 3)); }
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

  mostrarMarca(x, y, valido, raio = 0.9) {
    if (x == null) { this.marca.visible = false; return; }
    this.marca.visible = true;
    this.marca.position.set(this.X(x), 0, this.Z(y));
    this.anelMarca.scale.setScalar(raio / 0.9);
    this.matMarca.color.set(valido ? 0xffffff : 0xff4b3e);
  }

  // ------------------------------------------------------------ aplicar uma foto do estado
  aplicar(f) {
    this.ultima = f;
    const vistos = new Set();
    for (const e of f.ent) {
      const [id, k, lado, x, y, hp, hpMax, est, a, tn] = e;
      vistos.add(id);
      let b = this.bonecos.get(id);
      if (!b) { b = new Boneco(this, id, k, lado, x, y, hpMax, a); this.bonecos.set(id, b); }
      b.alvo(x, y, hp, est, a, tn);
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
    for (const ev of f.ev || []) this.evento(ev);
  }

  evento(ev) {
    const [t, a, b, c, d] = ev;
    if (t === "atq") { const o = this.bonecos.get(a); o && o.atacar(); this.aoSom && this.aoSom("atq", o && o.k); }
    else if (t === "nasce") { const o = this.bonecos.get(a); if (o) this.poeira(o.g.position.x, o.g.position.z, 0xfff3c4, o.raio + 0.5); this.aoSom && this.aoSom("nasce"); }
    else if (t === "morte") {
      const fixa = d === "torre" || d === "rei";
      this.fumaca(this.X(b), this.Z(c), fixa ? 22 : 7, fixa ? 2.2 : 0.7, fixa ? 0xd8d2c4 : 0xffffff);
      if (fixa) { this.tremor = 0.7; this.ruina(this.X(b), this.Z(c), d === "rei" ? 1.5 : 1); }
      this.aoSom && this.aoSom(fixa ? "torre" : "morte");
    } else if (t === "explode") { this.explosao(this.X(a), this.Z(b), c, d); this.aoSom && this.aoSom(d ? "impacto" : "explosao"); if (!d) this.tremor = 0.35; }
    else if (t === "dano") { const o = this.bonecos.get(a); o && o.apanhar(); }
    else if (t === "magia") this.aoSom && this.aoSom("magia");
  }

  ruina(X, Z, esc) { const r = this.novo("ruina"); r.position.set(X, 0, Z); r.scale.setScalar(esc); this.cena.add(r); (this.ruinas ||= []).push(r); }

  limpar() {
    for (const b of this.bonecos.values()) b.sair(true);
    this.bonecos.clear();
    for (const p of this.projs.values()) p.sair();
    this.projs.clear();
    for (const r of this.ruinas || []) this.cena.remove(r);
    this.ruinas = [];
    for (const e of this.efeitos) this.cena.remove(e.o);
    this.efeitos = [];
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
    const cor = tipo === "magia" ? 0x7fefff : 0xff8a1e;
    const bola = new THREE.Mesh(new THREE.SphereGeometry(1, 18, 12), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.85 }));
    bola.position.set(X, 0.5, Z);
    this.efeito(bola, 0.38, (q) => { bola.scale.setScalar(raio * (0.3 + q * 0.8)); bola.material.opacity = 0.85 * (1 - q); });
    this.poeira(X, Z, tipo === "magia" ? 0xbff6ff : 0xffd98a, raio * 1.1);
    if (!tipo) this.fumaca(X, Z, 12, raio * 0.8, 0x6a6a6a);
  }

  quadro() {
    const dt = Math.min(0.05, this.relogio.getDelta()), agora = this.relogio.elapsedTime;
    for (const b of this.bonecos.values()) b.quadro(dt, agora);
    for (const p of this.projs.values()) p.quadro(dt);
    this.efeitos = this.efeitos.filter(e => { e.t += dt; const q = Math.min(1, e.t / e.dur); e.passo(q); if (q >= 1) { this.cena.remove(e.o); return false; } return true; });
    if (this.camBase) {
      this.tremor = Math.max(0, this.tremor - dt * 1.6);
      const t = this.tremor * this.tremor;
      this.cam.position.set(this.camBase.x + (Math.random() - 0.5) * t * 1.4, this.camBase.y + (Math.random() - 0.5) * t * 1.4, this.camBase.z);
    }
    this.r.render(this.cena, this.cam);
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
      this.altura = this.fixa ? (k === "rei" ? 6.7 : 5.1) : this.voa ? ALT_VOO + 1.9 : 2.7;
      if (k === "dragao") this.esc = 1.3;
    }
    this.m.scale.setScalar(this.esc);
    this.g.position.set(c.X(x), 0, c.Z(y));
    this.ang = this.fixa ? 0 : c.giro(a);               // torres e castelos sempre de frente para a câmera
    this.m.rotation.y = this.predio ? 0 : this.ang;
    if (this.voa) this.m.position.y = ALT_VOO;
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
    this.barra.visible = this.fixa;
    this.largBarra = larg; this.altBarra = alt;
    this.g.add(this.barra);
    if (this.fixa) {
      const cv = document.createElement("canvas"); cv.width = 128; cv.height = 48;
      this.cvNum = cv; this.texNum = new THREE.CanvasTexture(cv); this.texNum.colorSpace = THREE.SRGBColorSpace;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texNum, depthTest: false })); sp.scale.set(1.9, 0.72, 1); sp.position.y = 0.62; sp.renderOrder = 12;
      this.barra.add(sp);
    }
    this.tx = x; this.ty = y; this.hp = hpMax; this.est = 0; this.tn = 0; this.soco = 0; this.tAtq = 9;
    c.cena.add(this.g);
    if (this.mixer) this.tocar("parado", 0);
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
    if (this.mixer && !this.atacando) this.tocar(est === 1 ? "andar" : "parado");
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
  apanhar() { this.soco = 1; }

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
    this.tAtq += dt;
    // nascendo: cresce com um quique
    let esc = this.esc * (1 + this.soco * 0.07);
    if (this.tn > 0) { const q = 1 - Math.min(1, this.tn); esc *= 0.35 + 0.65 * (1 - Math.pow(1 - q, 3)); }
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
    } else if (this.k === "catapulta") {
      if (P.catapult_turret && this.angAlvo != null) {            // a catapulta gira no topo da torre e o braço dá o golpe
        let d = this.angAlvo - this.ang; d = Math.atan2(Math.sin(d), Math.cos(d));
        this.ang += d * (1 - Math.exp(-dt * 10));
        P.catapult_turret.rotation.y = this.ang;
      }
      if (P.catapult_arm) P.catapult_arm.rotation.x = -golpe * 1.3;
    }
  }

  sair(seco) { this.c.cena.remove(this.g); if (this.mixer) this.mixer.stopAllAction(); }
}

// ------------------------------------------------------------------ projéteis
class Projetil {
  constructor(c, p) {
    this.c = c; this.tipo = p[1];
    const time = p[5] === c.visao ? 0 : 1;
    if (this.tipo === "bola") { this.o = c.novo("bola_fogo"); this.o.scale.setScalar(1.9); }
    else if (this.tipo === "pedra") { this.o = c.novo("pedra_cat"); }
    else if (this.tipo === "flecha" || this.tipo === "virote") { this.o = c.novo("flecha"); this.o.scale.setScalar(this.tipo === "virote" ? 1.5 : 1.25); }
    else {
      const cor = this.tipo === "magia" ? (time === 0 ? 0x7fefff : 0xff9df0) : 0xff8a1e;
      this.o = new THREE.Mesh(new THREE.SphereGeometry(this.tipo === "magia" ? 0.24 : 0.3, 12, 8), new THREE.MeshBasicMaterial({ color: cor }));
    }
    this.h0 = this.tipo === "bola" ? 4 : p[4] ? 3.6 : this.tipo === "fogo" ? ALT_VOO + 0.9 : this.tipo === "pedra" ? 2.6 : 1.3;
    this.h1 = p[6] ? ALT_VOO + 0.5 : 0.9;
    this.x = p[2]; this.y = p[3];
    this.o.position.set(c.X(this.x), this.h0, c.Z(this.y));
    this.d0 = this.tipo === "bola" ? 1 : Math.max(0.5, Math.hypot(p[7] - p[2], p[8] - p[3]));
    c.cena.add(this.o);
  }
  alvo(p) {
    this.tx = p[2]; this.ty = p[3];
    this.q = this.tipo === "bola" ? p[4] : 1 - Math.min(1, Math.hypot(p[7] - p[2], p[8] - p[3]) / this.d0);
  }
  quadro(dt) {
    const c = this.c, o = this.o, k = 1 - Math.exp(-dt * 22);
    const antes = o.position.clone();
    this.x += (this.tx - this.x) * k; this.y += (this.ty - this.y) * k;
    const q = this.q || 0;
    const h = this.tipo === "bola" ? 1.2 + Math.sin(Math.PI * q) * 7 + (1 - q) * 2.5 : this.h0 + (this.h1 - this.h0) * q + Math.sin(Math.PI * q) * (this.tipo === "pedra" ? 1.8 : 0.7);
    o.position.set(c.X(this.x), h, c.Z(this.y));
    const v = o.position.clone().sub(antes);
    if (v.lengthSq() > 1e-6) o.lookAt(o.position.clone().add(v));
    if (this.tipo === "bola") o.rotateZ(dt * 9);
    if (this.tipo === "pedra") o.rotateX(this.giro = (this.giro || 0) + dt * 9);
  }
  sair() { this.c.cena.remove(this.o); }
}
