// A Máquina do Nexus no computador: o mesmo código do app (js/maquina.js, copiado do repositório privado todo dia),
// com os dados lidos do GitHub pelo token que você digita aqui. O token fica só neste navegador.
import { ABAS_MQ, TELAS_MQ } from "./js/maquina.js";
import { temToken, salvarConfig, esquecer, configPC } from "./js/dados.js";

const tela = document.getElementById("tela"), abas = document.getElementById("abas"), sair = document.getElementById("pc-conta");
const escapar = (s) => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function irPara(aba) {
  if (!TELAS_MQ[aba]) aba = ABAS_MQ[0].id;
  tela.innerHTML = ""; tela.scrollTop = 0;
  tela.dataset.tela = aba; tela.dataset.nav = String(+(tela.dataset.nav || 0) + 1);
  abas.querySelectorAll(".aba").forEach(b => { const on = b.dataset.aba === aba; b.classList.toggle("ativa", on); b.setAttribute("aria-current", on ? "page" : "false"); });
  if (location.hash.slice(1) !== aba) history.replaceState(null, "", `#${aba}`);
  TELAS_MQ[aba]();
}

function pedirToken(erro = "") {
  abas.hidden = true; sair.hidden = true;
  const { repo = "Kimijoao77/Engfy" } = configPC();
  tela.innerHTML = `<section class="pc-entrar">
    <h1>Entrar</h1>
    <p>Cole aqui o mesmo tipo de token do GitHub que o app usa (Perfil → Sincronização). Ele fica só neste navegador
      e serve para ler e gravar os dados do canal no seu repositório privado.</p>
    <label>Repositório<input id="pc-repo" value="${escapar(repo)}" autocomplete="off" spellcheck="false"></label>
    <label>Token do GitHub<input id="pc-token" type="password" autocomplete="off" spellcheck="false" placeholder="github_pat_..."></label>
    ${erro ? `<p class="mq-erro">${escapar(erro)}</p>` : ""}
    <button class="mq-botao" id="pc-ok">Entrar</button>
    <p class="mq-nota">Num computador que não é seu, toque em Sair quando terminar: o token é apagado deste navegador.</p>
  </section>`;
  const ok = async () => {
    const r = document.getElementById("pc-repo").value.trim(), tk = document.getElementById("pc-token").value.trim();
    if (!/^[\w.-]+\/[\w.-]+$/.test(r) || !tk) return pedirToken("Preencha o repositório (dono/nome) e o token.");
    try {
      const resp = await fetch(`https://api.github.com/repos/${r}`, { headers: { Authorization: `Bearer ${tk}`, Accept: "application/vnd.github+json" } });
      if (!resp.ok) return pedirToken(resp.status === 404 ? "Repositório não encontrado com este token." : "O GitHub recusou este token.");
    } catch { return pedirToken("Sem internet agora."); }
    salvarConfig(r, tk); iniciar();
  };
  document.getElementById("pc-ok").onclick = ok;
  document.getElementById("pc-token").onkeydown = (e) => { if (e.key === "Enter") ok(); };
}

function iniciar() {
  if (!temToken()) return pedirToken();
  abas.hidden = false; sair.hidden = false;
  abas.innerHTML = ABAS_MQ.map(a => `<button class="aba" data-aba="${a.id}">${a.svg}<span>${a.nome}</span></button>`).join("");
  abas.querySelectorAll(".aba").forEach(b => (b.onclick = () => irPara(b.dataset.aba)));
  irPara(location.hash.slice(1));
}

sair.onclick = () => { esquecer(); localStorage.removeItem("nexus.maquina.v1"); location.hash = ""; location.reload(); };
window.addEventListener("oq-ir", (e) => irPara(e.detail));
window.addEventListener("hashchange", () => { if (temToken() && tela.dataset.tela !== location.hash.slice(1)) irPara(location.hash.slice(1)); });
iniciar();
