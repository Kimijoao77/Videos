"""Problemas de tática do Lichess para o app de xadrez do Nexus (pedido do João em 10/11/2026: "muito mais táticas").

A base de problemas do Lichess é de domínio público (CC0, database.lichess.org). O script baixa a base inteira, escolhe
uns 10 mil problemas bons para quem está começando (rating 400 a 2000, bem avaliados, muito jogados, até 5 lances seus),
separa pelos temas do app e grava no formato do app (app/www/xadrez/problemas.json do Engfy):
[id, fen, lance do adversário, solução (lances separados por espaço), temas (separados por vírgula), rating].
"""
import csv
import heapq
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
SAIDA = Path("saida/problemas-lichess.json")
# tema do Lichess -> tema do app, nesta ordem (o primeiro que aparece vale)
ORDEM = [("mateIn1", "mate1"), ("mateIn2", "mate2"), ("mateIn3", "mate3"), ("mateIn4", "mate_longo"), ("mateIn5", "mate_longo"),
         ("fork", "garfo"), ("pin", "cravada"), ("skewer", "espeto"), ("discoveredAttack", "descoberto"), ("doubleCheck", "descoberto"),
         ("hangingPiece", "peca_solta"), ("trappedPiece", "peca_presa"), ("capturingDefender", "remover_defensor"),
         ("deflection", "desvio"), ("attraction", "atracao"), ("promotion", "promocao"), ("advancedPawn", "promocao"),
         ("defensiveMove", "defesa"), ("sacrifice", "sacrificio")]
FAIXAS = [(400, 600, 100), (600, 800, 100), (800, 1000, 100), (1000, 1200, 80), (1200, 1400, 80), (1400, 1600, 50),
          (1600, 1800, 50), (1800, 2000, 50)]          # (de, até, quantos de cada tema)


def tema_do_app(temas: set[str]) -> str:
    return next((app for li, app in ORDEM if li in temas), "ganho")


def faixa(r: int):
    return next(((a, b, n) for a, b, n in FAIXAS if a <= r < b), None)


def main() -> int:
    curl = subprocess.Popen(["curl", "-sL", "--fail", URL], stdout=subprocess.PIPE)
    zst = subprocess.Popen(["zstd", "-dc"], stdin=curl.stdout, stdout=subprocess.PIPE)
    curl.stdout.close()
    leitor = csv.reader(io.TextIOWrapper(zst.stdout, encoding="utf-8", newline=""))
    cab = next(leitor)
    k = {c: i for i, c in enumerate(cab)}
    potes: dict[tuple, list] = {}
    lidos = bons = 0
    for lin in leitor:
        lidos += 1
        try:
            r, dev, pop, n = int(lin[k["Rating"]]), int(lin[k["RatingDeviation"]]), int(lin[k["Popularity"]]), int(lin[k["NbPlays"]])
        except (ValueError, IndexError):
            continue
        f = faixa(r)
        if not f or dev > 90 or pop < 85 or n < 300:
            continue
        lances = lin[k["Moves"]].split()
        if len(lances) < 2 or len(lances) > 10:
            continue
        temas = set(lin[k["Themes"]].split())
        tema = tema_do_app(temas)
        if len(lances) > 8 and tema != "mate_longo":          # até 4 lances seus (5 só nos mates longos)
            continue
        bons += 1
        extra = ["corredor"] if "backRankMate" in temas and tema in ("mate1", "mate2") else []
        item = ["li" + lin[k["PuzzleId"]], lin[k["FEN"]], lances[0], " ".join(lances[1:]), ",".join([tema] + extra), r]
        pote = potes.setdefault((tema, f[0]), [])
        chave = (pop, n, lin[k["PuzzleId"]])
        if len(pote) < f[2]:
            heapq.heappush(pote, (chave, item))
        elif chave > pote[0][0]:
            heapq.heapreplace(pote, (chave, item))
    zst.wait()
    if curl.wait() != 0 or lidos < 100000:
        print(f"a base não baixou inteira ({lidos} linhas)")
        return 1
    escolhidos = sorted((it for pote in potes.values() for _, it in pote), key=lambda it: (it[4], it[5]))
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps(escolhidos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{lidos} problemas lidos, {bons} bons, {len(escolhidos)} escolhidos ({SAIDA.stat().st_size / 1e6:.1f} MB)")
    por = Counter(it[4].split(",")[0] for it in escolhidos)
    for t, q in sorted(por.items(), key=lambda x: -x[1]):
        print(f"  {t}: {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
