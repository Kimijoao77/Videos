// O que fica guardado no aparelho: troféus, estatísticas, o baralho escolhido, o nível do computador e se o tutorial
// já foi visto. Tudo no armazenamento do navegador; se ele não funcionar, o jogo segue com os valores padrão.
import { BARALHO, baralhoValido } from "./sim.js";

const CHAVE = "arena-progresso";
const PADRAO = { trofeus: 0, partidas: 0, vitorias: 0, derrotas: 0, empates: 0, sequencia: 0, melhorSeq: 0, coroas: 0, baralho: BARALHO.slice(), nivel: 1, tutorial: false, arena: null };
let dados = { ...PADRAO };
try { dados = { ...PADRAO, ...JSON.parse(localStorage.getItem(CHAVE) || "{}") }; } catch (e) { /* sem armazenamento */ }
dados.baralho = baralhoValido(dados.baralho);

function salvar() { try { localStorage.setItem(CHAVE, JSON.stringify(dados)); } catch (e) { /* ok */ } }
export const prog = () => dados;
export function mudar(campos) { Object.assign(dados, campos); salvar(); }

// arenas por troféus
export const ARENAS = [
  { min: 0, nome: "Campo de Treino" }, { min: 200, nome: "Vila dos Camponeses" }, { min: 500, nome: "Floresta Sombria" },
  { min: 900, nome: "Castelo de Pedra" }, { min: 1400, nome: "Reino dos Dragões" }, { min: 2000, nome: "Lenda dos Reinos" },
];
export function arenaDe(t) { let a = ARENAS[0]; for (const x of ARENAS) if (t >= x.min) a = x; return a; }
export function proximaArena(t) { return ARENAS.find(x => x.min > t) || null; }

// resultado: "v" | "d" | "e". tipo: "bot0" | "bot1" | "bot2" | "online". Devolve a variação de troféus.
export function registrar(resultado, tipo, minhasCoroas) {
  const ganho = { bot0: [10, -8], bot1: [25, -15], bot2: [40, -20], online: [30, -20] }[tipo] || [25, -15];
  let delta = 0;
  dados.partidas++; dados.coroas += minhasCoroas;
  if (resultado === "v") { dados.vitorias++; dados.sequencia++; dados.melhorSeq = Math.max(dados.melhorSeq, dados.sequencia); delta = ganho[0] + Math.min(10, (dados.sequencia - 1) * 2); }
  else if (resultado === "d") { dados.derrotas++; dados.sequencia = 0; delta = Math.max(-dados.trofeus, ganho[1]); }
  else dados.empates++;
  dados.trofeus += delta;
  salvar();
  return delta;
}
