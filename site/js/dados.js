// Dados no computador: o mesmo jeito do app (API do GitHub, conteúdo do repositório), mas o repositório e o token
// ficam no localStorage deste navegador, digitados na tela de entrar. Nada vai para outro lugar.
const K = "nexus.pc.github";
export function configPC() { try { return JSON.parse(localStorage.getItem(K) || "{}"); } catch { return {}; } }
export function salvarConfig(repo, token) { localStorage.setItem(K, JSON.stringify({ repo, token })); }
export function esquecer() { localStorage.removeItem(K); }
export function temToken() { return !!configPC().token; }
const api = (caminho) => `https://api.github.com/repos/${configPC().repo || "Kimijoao77/Engfy"}/contents/${caminho}`;
const cab = (tipo = "json") => ({ Authorization: `Bearer ${configPC().token}`, Accept: tipo === "raw" ? "application/vnd.github.raw+json" : "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" });
async function gh(caminho, tipo = "json") {
  const r = await fetch(api(caminho), { headers: cab(tipo), cache: "no-store" });
  if (r.status === 404) return null;
  if (r.status === 401 || r.status === 403) throw new Error("O GitHub recusou o acesso: toque em Sair e entre de novo com um token válido.");
  if (!r.ok) throw new Error(`GitHub respondeu ${r.status}`);
  return tipo === "raw" ? r : r.json();
}
export async function baixarTexto(caminho) { const r = await gh(caminho, "raw"); return r ? r.text() : null; }
export async function baixarBinario(caminho) { const r = await gh(caminho, "raw"); return r ? r.blob() : null; }
function base64(texto) {
  const bytes = new TextEncoder().encode(texto);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}
export async function enviarJSON(caminho, obj, mensagem) {
  const content = base64(JSON.stringify(obj, null, 1));
  for (let tentativa = 1; tentativa <= 3; tentativa++) {
    const atual = await gh(caminho);
    const corpo = { message: `${mensagem} (pelo computador)`, content };
    if (atual?.sha) corpo.sha = atual.sha;
    const r = await fetch(api(caminho), { method: "PUT", headers: { ...cab(), "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    if (r.ok) return;
    if ((r.status === 409 || r.status === 422) && tentativa < 3) { await new Promise(ok => setTimeout(ok, 700 * tentativa)); continue; }
    throw new Error(`Não consegui gravar ${caminho} (${r.status})`);
  }
}
