"""Gera os modelos do jogo (GLB, um por arquivo, com a cor mágica do time) e a arte das cartas (PNG sem fundo, em azul).
Uso: python exportar.py PASTA_DO_JOGO [modelos] [cartas]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit
import personagens as P

JOGO = Path(sys.argv[1])
QUAIS = sys.argv[2:] or ["modelos", "cartas"]
AZUL = (0.16, 0.45, 0.95)

if "modelos" in QUAIS:
    (JOGO / "modelos").mkdir(exist_ok=True)
    kit.COR_TIME = None
    for nome in P.TROPAS + P.PREDIOS + P.OBJETOS:
        kit.limpar()
        getattr(P, nome)().montar()
        kit.exportar(JOGO / "modelos" / f"{nome}.glb")
        print("modelo", nome, (JOGO / "modelos" / f"{nome}.glb").stat().st_size // 1024, "kB", flush=True)

if "cartas" in QUAIS:
    (JOGO / "cartas").mkdir(exist_ok=True)
    kit.COR_TIME = AZUL
    # carta: (modelo, [posições dos bonecos], alvo, distância, azimute, elevação)
    CARTAS = {
        "dragao": ("dragao", [(0, 0)], (0, -0.1, 0.72), 3.9, -34, 10),
        "balista": ("balista", [(0, 0)], (0, 0, 0.5), 3.7, -40, 22),
        "bola_fogo": ("bola_fogo", [(0, 0)], (0, 0.1, 0.5), 2.6, -55, 8),
    }
    for carta, (modelo, onde, alvo, dist, az, el) in CARTAS.items():
        kit.limpar()
        for (x, y) in onde:
            raiz = getattr(P, modelo)().montar()
            raiz.location = (x, y, 0)
        kit.foto(JOGO / "cartas" / f"{carta}.png", alvo=alvo, dist=dist, az=az, el=el, larg=256, alt=256, amostras=40, transparente=True)
        print("carta", carta, flush=True)
