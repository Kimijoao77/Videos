"""Gera os modelos do jogo (GLB, um por arquivo, com a cor mágica do time) e a arte das cartas (PNG sem fundo, em azul).
Uso: python exportar.py PASTA_DO_JOGO [modelos] [cartas]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy

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
        "dragao": ("dragao", [(0, 0)], (0, 0.0, 1.0), 7.4, -34, 6),
        "bola_fogo": ("bola_fogo", [(0, 0)], (0, 0.3, 0.5), 3.9, -62, 6),
    }
    # chuva de flechas: várias flechas caindo inclinadas
    kit.limpar()
    import math as _m
    import random as _r
    _r.seed(8)
    for k in range(11):
        raiz = P.flecha().montar()
        raiz.location = (_r.uniform(-0.75, 0.75), _r.uniform(-0.5, 0.5), _r.uniform(0.2, 1.5))
        raiz.rotation_euler = (_m.radians(62 + _r.uniform(-6, 6)), 0, _m.radians(_r.uniform(-8, 8)))
        raiz.scale = (2.2, 2.2, 2.2)
    kit.foto(JOGO / "cartas" / "flechas.png", alvo=(0, 0, 0.85), dist=4.6, az=-62, el=4, larg=512, alt=512, amostras=48, transparente=True)
    print("carta flechas", flush=True)
    for carta, (modelo, onde, alvo, dist, az, el) in CARTAS.items():
        kit.limpar()
        for (x, y) in onde:
            raiz = getattr(P, modelo)().montar()
            raiz.location = (x, y, 0)
        if carta == "dragao":                          # na carta, as asas abertas para cima
            import math
            bpy.data.objects["asa_e"].rotation_euler = (0, math.radians(-32), 0)
            bpy.data.objects["asa_d"].rotation_euler = (0, math.radians(32), 0)
        kit.foto(JOGO / "cartas" / f"{carta}.png", alvo=alvo, dist=dist, az=az, el=el, larg=512, alt=512, amostras=48, transparente=True)
        print("carta", carta, flush=True)
