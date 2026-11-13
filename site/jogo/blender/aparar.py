"""Corta a sobra transparente das imagens da interface (deixa uma margem pequena). Uso: python aparar.py ARQ..."""
import sys
from PIL import Image

for arq in sys.argv[1:]:
    im = Image.open(arq).convert("RGBA")
    caixa = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not caixa:
        continue
    m = max(4, int(0.03 * max(im.size)))
    x0, y0, x1, y1 = max(0, caixa[0] - m), max(0, caixa[1] - m), min(im.width, caixa[2] + m), min(im.height, caixa[3] + m)
    im.crop((x0, y0, x1, y1)).save(arq, optimize=True)
    print(arq, im.size, "->", (x1 - x0, y1 - y0))
