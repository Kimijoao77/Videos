"""Fotos de conferência: python ver.py NOME [NOME...] (cada modelo visto de frente-lado e de trás)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit
import personagens as P

SAIDA = Path(sys.argv[1])
SAIDA.mkdir(parents=True, exist_ok=True)
for nome in sys.argv[2:]:
    for i, (az, cor) in enumerate(((-30, (0.16, 0.45, 0.95)), (150, (0.9, 0.2, 0.2)))):
        kit.limpar()
        kit.COR_TIME = cor
        m = getattr(P, nome)()
        m.montar()
        alt = getattr(m, "alt", 1.0) * m.e
        kit.foto(SAIDA / f"{nome}_{i}.png", alvo=(0, 0, alt * 0.5), dist=alt * 2.6 + 0.8, az=az, el=20)
