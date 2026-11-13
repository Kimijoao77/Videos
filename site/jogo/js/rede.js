// Partida entre dois aparelhos por link: os dois navegadores se ligam direto um no outro (WebRTC, pela biblioteca
// PeerJS e o servidor público dela, que só apresenta um ao outro). O dono da sala manda o jogo; o convidado manda só
// as jogadas. Com ?canal=1 no endereço, usa um canal entre abas do mesmo navegador (para testar sem internet).
const PREFIXO = "arena-jv-";
const TESTE = new URLSearchParams(location.search).has("canal");

export function novoCodigo() {
  const letras = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  return Array.from({ length: 5 }, () => letras[Math.floor(Math.random() * letras.length)]).join("");
}

// papel: "dono" ou "convidado". Devolve { enviar(msg), fechar() }. aoEstado(estado, detalhe):
// "pronto" (sala aberta, esperando) · "ligado" (os dois conectados) · "caiu" · "erro"
export function ligar(papel, codigo, aoMsg, aoEstado) {
  if (TESTE) return ligarCanal(papel, codigo, aoMsg, aoEstado);
  let conn = null, fechado = false;
  const peer = papel === "dono" ? new window.Peer(PREFIXO + codigo) : new window.Peer();
  const usar = (c) => {
    conn = c;
    c.on("open", () => aoEstado("ligado"));
    c.on("data", (d) => aoMsg(d));
    c.on("close", () => { if (!fechado) aoEstado("caiu"); });
    c.on("error", () => { if (!fechado) aoEstado("caiu"); });
  };
  peer.on("open", () => {
    if (papel === "dono") aoEstado("pronto");
    else usar(peer.connect(PREFIXO + codigo, { reliable: true }));
  });
  peer.on("connection", (c) => { if (conn && conn.open) { c.close(); return; } usar(c); });
  peer.on("error", (e) => {
    if (fechado) return;
    const tipo = e && e.type;
    aoEstado("erro", tipo === "peer-unavailable" ? "Sala não encontrada. Confira o link com quem criou." : tipo === "unavailable-id" ? "Esse código de sala já está em uso. Crie outra sala."
      : tipo === "network" || tipo === "server-error" || tipo === "socket-error" ? "Sem conexão com o servidor das salas. Confira a internet." : "Não deu para conectar (" + (tipo || "erro") + ").");
  });
  peer.on("disconnected", () => { if (!fechado && !(conn && conn.open)) { try { peer.reconnect(); } catch (e) { /* ok */ } } });
  return {
    enviar(msg) { if (conn && conn.open) conn.send(msg); },
    fechar() { fechado = true; try { conn && conn.close(); peer.destroy(); } catch (e) { /* ok */ } },
  };
}

function ligarCanal(papel, codigo, aoMsg, aoEstado) {
  const bc = new BroadcastChannel(PREFIXO + codigo);
  let ligado = false;
  bc.onmessage = (ev) => {
    const { de, sis, msg } = ev.data;
    if (de === papel) return;
    if (sis === "oi" && papel === "dono") { bc.postMessage({ de: papel, sis: "ola" }); if (!ligado) { ligado = true; aoEstado("ligado"); } }
    else if (sis === "ola" && papel === "convidado") { if (!ligado) { ligado = true; aoEstado("ligado"); } }
    else if (sis === "tchau") { if (ligado) aoEstado("caiu"); }
    else if (msg) aoMsg(msg);
  };
  setTimeout(() => { if (papel === "dono") aoEstado("pronto"); else bc.postMessage({ de: papel, sis: "oi" }); }, 50);
  return { enviar(msg) { bc.postMessage({ de: papel, msg }); }, fechar() { bc.postMessage({ de: papel, sis: "tchau" }); bc.close(); } };
}
