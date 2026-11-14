// Partículas da arena: faíscas dos golpes, almas das tropas que morrem, brasas das explosões, fogo e fumaça das torres
// caídas e fogos de artifício da vitória (o clima de cada arena fica em cenario.js).
// Tudo num só THREE.Points por tipo de mistura (somando luz ou por cima), para ficar leve no celular.
import * as THREE from "three";

const VERT = `attribute float tam; attribute vec4 cor; varying vec4 vCor; uniform float escala;
void main() { vCor = cor; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = max(1.0, tam * escala / -mv.z); gl_Position = projectionMatrix * mv; }`;
const FRAG = `uniform sampler2D mapa; varying vec4 vCor;
void main() { float a = texture2D(mapa, gl_PointCoord).a * vCor.a; if (a < 0.01) discard; gl_FragColor = vec4(vCor.rgb, a); }`;

const cores = new Map();
function linear(hex) {                                   // cor em espaço linear (o mesmo das luzes)
  if (!cores.has(hex)) { const c = new THREE.Color(hex); cores.set(hex, [c.r, c.g, c.b]); }
  return cores.get(hex);
}
const ac = (a, b) => a + Math.random() * (b - a);

export class Particulas {
  constructor(cena, tex, max = 900, somaLuz = true) {
    this.max = max; this.n = 0;
    this.pos = new Float32Array(max * 3); this.vel = new Float32Array(max * 3);
    this.cor = new Float32Array(max * 4); this.tam = new Float32Array(max);
    this.vida = new Float32Array(max); this.vidaMax = new Float32Array(max); this.grav = new Float32Array(max);
    this.arrasto = new Float32Array(max); this.tam0 = new Float32Array(max); this.alfa0 = new Float32Array(max);
    this.cresce = new Float32Array(max); this.vagar = new Float32Array(max); this.chao = new Float32Array(max);
    const g = this.geo = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("cor", new THREE.BufferAttribute(this.cor, 4).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("tam", new THREE.BufferAttribute(this.tam, 1).setUsage(THREE.DynamicDrawUsage));
    g.setDrawRange(0, 0);
    this.mat = new THREE.ShaderMaterial({ uniforms: { mapa: { value: tex }, escala: { value: 500 } }, vertexShader: VERT, fragmentShader: FRAG,
      transparent: true, depthWrite: false, blending: somaLuz ? THREE.AdditiveBlending : THREE.NormalBlending });
    this.pts = new THREE.Points(g, this.mat); this.pts.frustumCulled = false; this.pts.renderOrder = somaLuz ? 6 : 5;
    cena.add(this.pts);
  }
  /** n partículas saindo de (x, y, z). o: cores [hex], vel [min, max], dir "esfera" | "cima" | "anel" | [dx, dy, dz],
   *  abre (espalhamento do cone), vida [min, max], tam [min, max], grav, arrasto, cresce, alfa, vagar, raio (onde nascem). */
  emitir(x, y, z, n, o = {}) {
    const cs = o.cores || [0xffffff], v = o.vel || [1, 3], vida = o.vida || [0.4, 0.8], tam = o.tam || [0.12, 0.25], raio = o.raio || 0;
    for (let k = 0; k < n; k++) {
      if (this.n >= this.max) return;
      const i = this.n++, i3 = i * 3, i4 = i * 4;
      let dx, dy, dz;
      if (o.dir === "cima") { const a = Math.random() * 6.28, ab = o.abre ?? 0.5; dx = Math.cos(a) * ab * Math.random(); dz = Math.sin(a) * ab * Math.random(); dy = 1; }
      else if (o.dir === "anel") { const a = Math.random() * 6.28; dx = Math.cos(a); dz = Math.sin(a); dy = o.abre ?? 0.15; }
      else if (Array.isArray(o.dir)) { const ab = o.abre ?? 0.3; dx = o.dir[0] + ac(-ab, ab); dy = o.dir[1] + ac(-ab, ab); dz = o.dir[2] + ac(-ab, ab); }
      else { dx = ac(-1, 1); dy = ac(-1, 1); dz = ac(-1, 1); }
      const nn = Math.hypot(dx, dy, dz) || 1, sp = ac(v[0], v[1]);
      const ra = Math.random() * 6.28, rr = raio * Math.sqrt(Math.random());
      this.pos[i3] = x + Math.cos(ra) * rr; this.pos[i3 + 1] = y + (o.altura ? ac(0, o.altura) : 0); this.pos[i3 + 2] = z + Math.sin(ra) * rr;
      this.vel[i3] = dx / nn * sp; this.vel[i3 + 1] = dy / nn * sp; this.vel[i3 + 2] = dz / nn * sp;
      const [r, g, b] = linear(cs[Math.floor(Math.random() * cs.length)]);
      this.cor[i4] = r; this.cor[i4 + 1] = g; this.cor[i4 + 2] = b; this.cor[i4 + 3] = this.alfa0[i] = o.alfa ?? 1;
      this.tam[i] = this.tam0[i] = ac(tam[0], tam[1]);
      this.vida[i] = this.vidaMax[i] = ac(vida[0], vida[1]);
      this.grav[i] = o.grav ?? -6; this.arrasto[i] = o.arrasto ?? 1.5; this.cresce[i] = o.cresce ?? 0;
      this.vagar[i] = o.vagar ?? 0; this.chao[i] = o.quica ? 1 : 0;
    }
  }
  quadro(dt) {
    let i = 0;
    while (i < this.n) {
      this.vida[i] -= dt;
      if (this.vida[i] <= 0) { this.trocar(i, --this.n); continue; }
      const i3 = i * 3, q = 1 - this.vida[i] / this.vidaMax[i], f = Math.max(0, 1 - this.arrasto[i] * dt);
      if (this.vagar[i]) { const w = this.vagar[i] * dt; this.vel[i3] += ac(-w, w); this.vel[i3 + 1] += ac(-w, w) * 0.5; this.vel[i3 + 2] += ac(-w, w); }
      this.vel[i3 + 1] += this.grav[i] * dt;
      this.vel[i3] *= f; this.vel[i3 + 1] *= f; this.vel[i3 + 2] *= f;
      this.pos[i3] += this.vel[i3] * dt; this.pos[i3 + 1] += this.vel[i3 + 1] * dt; this.pos[i3 + 2] += this.vel[i3 + 2] * dt;
      if (this.pos[i3 + 1] < 0.03) { this.pos[i3 + 1] = 0.03; if (this.chao[i]) { this.vel[i3 + 1] *= -0.35; this.vel[i3] *= 0.6; this.vel[i3 + 2] *= 0.6; } else this.vel[i3 + 1] = 0; }
      this.tam[i] = this.tam0[i] * (1 + this.cresce[i] * q);
      // aparece rápido e some devagar
      this.cor[i * 4 + 3] = this.alfa0[i] * Math.min(1, q * 8) * Math.pow(1 - q, 1.3);
      i++;
    }
    this.geo.setDrawRange(0, this.n);
    for (const k of ["position", "cor", "tam"]) this.geo.attributes[k].needsUpdate = true;
  }
  trocar(a, b) {
    if (a === b) return;
    for (const [arr, w] of [[this.pos, 3], [this.vel, 3], [this.cor, 4]]) for (let k = 0; k < w; k++) arr[a * w + k] = arr[b * w + k];
    for (const arr of [this.tam, this.vida, this.vidaMax, this.grav, this.arrasto, this.tam0, this.alfa0, this.cresce, this.vagar, this.chao]) arr[a] = arr[b];
  }
  limpar() { this.n = 0; this.geo.setDrawRange(0, 0); }
}
