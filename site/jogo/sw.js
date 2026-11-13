// Arena dos Reinos: guarda o jogo no aparelho para abrir rápido e jogar contra o computador sem internet.
// Primeiro tenta a rede (para pegar as atualizações) e, sem rede, usa a cópia guardada.
const VERSAO = "arena-202611131314";
const ARQUIVOS = [
"./",
"index.html",
"estilo.css",
"manifest.json",
"js/bot.js",
"js/cenario.js",
"js/main.js",
"js/progresso.js",
"js/rede.js",
"js/render.js",
"js/sim.js",
"js/som.js",
"vendor/BufferGeometryUtils.js",
"vendor/GLTFLoader.js",
"vendor/LilitaOne-ext.woff2",
"vendor/LilitaOne.woff2",
"vendor/SkeletonUtils.js",
"vendor/peerjs.min.js",
"vendor/three.module.min.js",
"modelos/arvore.glb",
"modelos/bandido.glb",
"modelos/besteiro.glb",
"modelos/bola_fogo.glb",
"modelos/bosque.glb",
"modelos/castelo_azul.glb",
"modelos/castelo_vermelho.glb",
"modelos/catapulta_azul.glb",
"modelos/catapulta_vermelho.glb",
"modelos/cavaleiro.glb",
"modelos/cenario.glb",
"modelos/dragao.glb",
"modelos/esqueleto.glb",
"modelos/flecha.glb",
"modelos/gigante.glb",
"modelos/guerreiro.glb",
"modelos/kaykit.json",
"modelos/mago.glb",
"modelos/necromante.glb",
"modelos/pedra.glb",
"modelos/pedra_cat.glb",
"modelos/pinheiro.glb",
"modelos/ponte.glb",
"modelos/ruina.glb",
"modelos/torre_azul.glb",
"modelos/torre_vermelho.glb",
"cartas/bandidos.png",
"cartas/besteiros.png",
"cartas/bola_fogo.png",
"cartas/catapulta.png",
"cartas/cavaleiro.png",
"cartas/dragao.png",
"cartas/esqueletos.png",
"cartas/flechas.png",
"cartas/gigante.png",
"cartas/guerreiro.png",
"cartas/mago.png",
"cartas/necromante.png",
"img/icone-192.png",
"img/icone-512.png"
];
self.addEventListener("install", (ev) => { ev.waitUntil(caches.open(VERSAO).then(c => c.addAll(ARQUIVOS)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (ev) => {
  ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("arena-") && k !== VERSAO).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (ev) => {
  const url = new URL(ev.request.url);
  if (ev.request.method !== "GET" || url.origin !== location.origin) return;
  const pesado = /\.(glb|png|woff2)$/.test(url.pathname);
  ev.respondWith(pesado
    ? caches.match(ev.request).then(r => r || fetch(ev.request).then(resp => { const cp = resp.clone(); caches.open(VERSAO).then(c => c.put(ev.request, cp)); return resp; }))
    : fetch(ev.request).then(resp => { const cp = resp.clone(); caches.open(VERSAO).then(c => c.put(ev.request, cp)); return resp; }).catch(() => caches.match(ev.request, { ignoreSearch: true })));
});
