"""Identidade visual do canal Fora de Órbita / Out of Orbit, toda desenhada por código (sem imagem de IA).

O símbolo é o "O" de ÓRBITA/ORBIT: um planeta com a órbita em volta e a lua escapando dela. Em português, a lua
que escapou vira o acento do Ó.

Uso:  python canal/marca.py        → gera canal/marca/: avatar, banner, marca d'água, logos e o quadro da identidade
As cores e as fontes daqui valem para os vídeos, as miniaturas e o app.
"""
import math, random, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PASTA = Path(__file__).parent
FONTES = PASTA / "fontes"
SAIDA = PASTA / "marca"

# ---------- cores ----------
NOITE = (10, 15, 44)          # #0A0F2C  fundo, o espaço
NOITE_2 = (27, 38, 98)        # #1B2662  brilho do fundo
TINTA = (19, 27, 61)          # #131B3D  cartões e faixas
AMARELO = (255, 196, 0)       # #FFC400  a órbita, a lua e os títulos
AMARELO_ESCURO = (204, 150, 0)
GELO = (236, 240, 255)        # #ECF0FF  o planeta
SOMBRA = (154, 166, 226)      # sombra do planeta
BRANCO = (246, 247, 255)
VERMELHO = (255, 82, 82)      # #FF5252  perigo e impacto (só em miniaturas)
CIANO = (126, 226, 255)       # #7EE2FF  atmosfera e água
CORES = {"noite": NOITE, "noite_2": NOITE_2, "tinta": TINTA, "amarelo": AMARELO, "gelo": GELO, "branco": BRANCO,
         "vermelho": VERMELHO, "ciano": CIANO}

NOMES = {"pt": ("FORA DE", "ÓRBITA"), "en": ("OUT OF", "ORBIT")}
NOME_CURTO = {"pt": "Fora de Órbita", "en": "Out of Orbit"}
FRASE = {"pt": "E se o impossível acontecesse?", "en": "What if the impossible happened?"}
SUB = {"pt": "Ciência de verdade para perguntas absurdas", "en": "Real science for absurd questions"}
SS = 4  # desenha 4× maior e reduz: bordas lisas


def fonte(peso, tam):
    return ImageFont.truetype(str(FONTES / f"Unbounded-{peso}.ttf"), max(1, int(tam)))


def hexa(c):
    return "#%02X%02X%02X" % c[:3]


# ---------- fundo ----------
def fundo_espaco(w, h, semente=7, estrelas=True, centro=(0.5, 0.45), raio=0.75):
    """Espaço azul-noite com um brilho suave e estrelas (as mesmas em toda imagem com a mesma semente)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xs / w - centro[0]) * (w / max(w, h))) ** 2 + ((ys / h - centro[1]) * (h / max(w, h))) ** 2) / raio
    k = np.clip(1 - d, 0, 1) ** 1.6
    a, b = np.array(NOITE, np.float32), np.array(NOITE_2, np.float32)
    img = Image.fromarray((a + (b - a) * k[..., None]).astype(np.uint8), "RGB").convert("RGBA")
    if estrelas:
        rnd = random.Random(semente)
        d2 = ImageDraw.Draw(img, "RGBA")
        for _ in range(int(w * h / 9000)):
            x, y = rnd.uniform(0, w), rnd.uniform(0, h)
            r = rnd.choice([0.6, 0.8, 1.0, 1.0, 1.4, 1.9]) * max(1, w / 1600)
            al = rnd.randint(70, 220)
            d2.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, al))
    return img


# ---------- símbolo: o planeta com a órbita e a lua escapando ----------
# Geometria em unidades do raio do planeta (planeta no centro, raio 1).
GEO = {"rx": 1.72, "ry": 0.50, "ang": math.radians(-13), "w": 0.21, "saida": 0.62, "vao": (-0.40, 0.0),
       "dist": 1.62, "rl": 0.34, "rastro": ((0.10, 0.22, 0.38), (0.32, 0.46, 0.55), (0.56, 0.72, 0.75))}


def _el(rx, ry, t, ang=None):
    ang = GEO["ang"] if ang is None else ang
    x, y = rx * math.cos(t), ry * math.sin(t)
    ca, sa = math.cos(ang), math.sin(ang)
    return x * ca - y * sa, x * sa + y * ca


def _lua_pos():
    g = GEO
    x0, y0 = _el(g["rx"], g["ry"], g["saida"])
    dx, dy = g["rx"] * math.sin(g["saida"]), -g["ry"] * math.cos(g["saida"])   # a lua andava com t diminuindo
    ca, sa = math.cos(g["ang"]), math.sin(g["ang"])
    vx, vy = dx * ca - dy * sa, dx * sa + dy * ca
    n = math.hypot(vx, vy)
    return (x0, y0), (vx / n, vy / n)


def _pontos_simbolo(lua=True):
    """Pontos que o símbolo ocupa (para enquadrar sem cortar nada)."""
    g = GEO
    pts = [(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48)]
    pts += [_el(g["rx"] + g["w"] / 2, g["ry"] + g["w"] / 2, t) for t in np.linspace(0, 2 * math.pi, 96)]
    if lua:
        (x0, y0), (vx, vy) = _lua_pos()
        mx, my = x0 + vx * g["dist"], y0 + vy * g["dist"]
        pts += [(mx + g["rl"] * math.cos(a), my + g["rl"] * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 24)]
    return np.array(pts)


def enquadrar(s, lua=True, margem=0.06, circulo=False):
    """Escala e deslocamento (unidades → pixels) para caber em s×s; com circulo=True, cabe no círculo do avatar."""
    p = _pontos_simbolo(lua)
    if circulo:
        c = (p.min(0) + p.max(0)) / 2
        r = np.max(np.hypot(p[:, 0] - c[0], p[:, 1] - c[1]))
        k = float(s * (0.5 - margem) / r)
        return k, float(s / 2 - c[0] * k), float(s / 2 - c[1] * k)
    lo, hi = p.min(0), p.max(0)
    k = float(s * (1 - 2 * margem) / max(hi - lo))
    return k, float(s / 2 - (lo[0] + hi[0]) / 2 * k), float(s / 2 - (lo[1] + hi[1]) / 2 * k)


def desenhar_simbolo(img, k, ox, oy, lua=True, cor_planeta=GELO, cor_orbita=AMARELO, sombra=True):
    """Desenha o símbolo em `img` (RGBA): unidade → pixel com escala k e origem (ox, oy). Desenhe já em tamanho 4×."""
    g = GEO
    P = lambda x, y: (ox + x * k, oy + y * k)
    w = g["w"]

    def banda(t0, t1, n=200):
        fora = [P(*_el(g["rx"] + w / 2, g["ry"] + w / 2, t0 + (t1 - t0) * i / n)) for i in range(n + 1)]
        dentro = [P(*_el(g["rx"] - w / 2, g["ry"] - w / 2, t1 - (t1 - t0) * i / n)) for i in range(n + 1)]
        d.polygon(fora + dentro, fill=cor_orbita)
        for t in (t0, t1):
            x, y = P(*_el(g["rx"], g["ry"], t)); r = w / 2 * k
            d.ellipse([x - r, y - r, x + r, y + r], fill=cor_orbita)

    d = ImageDraw.Draw(img, "RGBA")
    banda(math.pi, 2 * math.pi + g["vao"][0])                         # metade de trás
    # planeta, com a sombra em meia-lua (luz de cima, à esquerda)
    W, H = img.size
    cx, cy = P(0, 0); r = k
    pl = Image.new("L", (W, H), 0); ImageDraw.Draw(pl).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    img.paste(Image.new("RGBA", (W, H), cor_planeta), (0, 0), pl)
    if sombra:
        som = Image.new("L", (W, H), 0); ds = ImageDraw.Draw(som)
        ds.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        ds.ellipse([cx - r * 1.06 - r * 0.40, cy - r * 1.06 - r * 0.34, cx + r * 1.06 - r * 0.40, cy + r * 1.06 - r * 0.34], fill=0)
        som = som.filter(ImageFilter.GaussianBlur(r * 0.025))
        m = (np.asarray(som, np.float32) * np.asarray(pl, np.float32) / 255 * 0.9).astype(np.uint8)
        img.paste(Image.new("RGBA", (W, H), SOMBRA), (0, 0), Image.fromarray(m))
    d = ImageDraw.Draw(img, "RGBA")
    banda(g["saida"] + g["vao"][1], math.pi)                          # metade da frente, com o vão
    if lua:
        (x0, y0), (vx, vy) = _lua_pos()
        for a0, a1, esp in g["rastro"]:                               # rastro: tracinhos que engrossam até a lua
            p0, p1 = P(x0 + vx * g["dist"] * a0, y0 + vy * g["dist"] * a0), P(x0 + vx * g["dist"] * a1, y0 + vy * g["dist"] * a1)
            ww = w * esp * k
            d.line([p0, p1], fill=cor_orbita, width=max(1, int(ww)))
            for px, py in (p0, p1):
                d.ellipse([px - ww / 2, py - ww / 2, px + ww / 2, py + ww / 2], fill=cor_orbita)
        mx, my = P(x0 + vx * g["dist"], y0 + vy * g["dist"]); rl = g["rl"] * k
        d.ellipse([mx - rl, my - rl, mx + rl, my + rl], fill=cor_orbita)
        for fx, fy, fr in ((-0.30, -0.16, 0.25), (0.28, 0.30, 0.17), (0.18, -0.38, 0.11)):
            r2 = rl * fr
            d.ellipse([mx + fx * rl - r2, my + fy * rl - r2, mx + fx * rl + r2, my + fy * rl + r2], fill=AMARELO_ESCURO)


def simbolo(s, lua=True, circulo=False, margem=0.06, **kw):
    """O símbolo sozinho num quadrado s×s transparente."""
    S = s * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    k, ox, oy = enquadrar(S, lua, margem, circulo)
    desenhar_simbolo(img, k, ox, oy, lua, **kw)
    return img.resize((s, s), Image.LANCZOS)


# ---------- logos ----------
def _cap(peso):
    """Altura das maiúsculas por ponto de fonte (para acertar tamanhos pela altura da letra)."""
    b = fonte(peso, 1000).getbbox("H")
    return (b[3] - b[1]) / 1000


def _espacado(d, x, y_base, txt, f, esp, cor):
    """Escreve letra por letra com espaço extra; devolve o x final."""
    for i, ch in enumerate(txt):
        d.text((x, y_base), ch, font=f, fill=cor, anchor="ls")
        x += f.getlength(ch) + (esp if i < len(txt) - 1 else 0)
    return x


def _palavras(idioma, H, cor_texto=BRANCO, lua_no_acento=True):
    """As duas linhas do nome numa altura H (em pixels já ampliados): "FORA DE" pequeno, "ÓRBITA" grande.
    Em português, o acento do Ó é a lua amarela escapando."""
    l1, l2 = NOMES[idioma]
    cap2, cap1 = 0.50 * H, 0.17 * H
    f2, f1 = fonte("Black", cap2 / _cap("Black")), fonte("Bold", cap1 / _cap("Bold"))
    base1 = 0.06 * H + cap1
    base2 = H - 0.04 * H
    sem_acento = l2.replace("Ó", "O") if lua_no_acento else l2
    larg2 = f2.getlength(sem_acento)
    esp1 = cap1 * 0.42
    larg1 = sum(f1.getlength(c) for c in l1) + esp1 * (len(l1) - 1)
    W = int(max(larg1, larg2) + H * 0.06)
    img = Image.new("RGBA", (W, int(H)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    _espacado(d, 0, base1, l1, f1, esp1, cor_texto)
    d.text((0, base2), sem_acento, font=f2, fill=cor_texto, anchor="ls")
    if l2 != sem_acento:                                   # o acento vira a lua
        ob = f2.getbbox("O", anchor="ls")
        ox, oy = (ob[0] + ob[2]) / 2, base2 + ob[1]       # meio do O e topo do O
        r = cap2 * 0.105
        mx, my = ox + cap2 * 0.26, oy - cap2 * 0.19
        ang = math.atan2(-(my - (oy - cap2 * 0.02)), mx - (ox - cap2 * 0.05))
        vx, vy = math.cos(ang), -math.sin(ang)
        for a0, a1, e in ((0.95, 0.70, 0.55), (0.62, 0.44, 0.42)):
            p0 = (mx - vx * r * 2 * a0 * 1.6, my - vy * r * 2 * a0 * 1.6)
            p1 = (mx - vx * r * 2 * a1 * 1.6, my - vy * r * 2 * a1 * 1.6)
            ww = r * e
            d.line([p0, p1], fill=AMARELO, width=max(1, int(ww)))
            for px, py in (p0, p1):
                d.ellipse([px - ww / 2, py - ww / 2, px + ww / 2, py + ww / 2], fill=AMARELO)
        d.ellipse([mx - r, my - r, mx + r, my + r], fill=AMARELO)
    return img


def logo(idioma, altura, cor_texto=BRANCO, com_simbolo=True):
    """Logo horizontal: o símbolo à esquerda e o nome em duas linhas. altura em pixels."""
    H = altura * SS
    txt = _palavras(idioma, H * 0.86, cor_texto, lua_no_acento=not com_simbolo)
    if not com_simbolo:
        return txt.resize((max(1, txt.width // SS), max(1, txt.height // SS)), Image.LANCZOS)
    sim = simbolo(int(H * 1.7)).crop()
    sim = sim.crop(sim.getbbox())
    k = H * 0.92 / sim.height
    sim = sim.resize((int(sim.width * k), int(sim.height * k)), Image.LANCZOS)
    gap = int(H * 0.09)
    img = Image.new("RGBA", (sim.width + gap + txt.width, int(H)), (0, 0, 0, 0))
    img.alpha_composite(sim, (0, (int(H) - sim.height) // 2))
    img.alpha_composite(txt, (sim.width + gap, int(H * 0.07)))
    return img.resize((max(1, img.width // SS), altura), Image.LANCZOS)


def avatar(tam=800):
    img = fundo_espaco(tam, tam, semente=3, centro=(0.5, 0.5), raio=0.62)
    img.alpha_composite(simbolo(tam, circulo=True, margem=0.09))
    return img.convert("RGB")


def marca_dagua(tam=150):
    return simbolo(tam)


def banner(idioma, w=2560, h=1440):
    """Banner do YouTube. No celular só aparece a faixa do meio (1546×423); no computador, a faixa inteira (2560×423);
    na TV, tudo. O nome e a frase ficam centrados na faixa do meio; o planeta grande aparece no computador e na TV."""
    img = fundo_espaco(w, h, semente=11, centro=(0.5, 0.5), raio=0.7)
    S = 2
    camada = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    desenhar_simbolo(camada, 190 * S, 2335 * S, 735 * S, lua=False)          # planeta à direita (computador e TV)
    img.alpha_composite(camada.resize((w, h), Image.LANCZOS))
    lg = logo(idioma, 230)
    y0 = (h - 423) // 2
    img.alpha_composite(lg, ((w - lg.width) // 2, y0 + 48))
    d = ImageDraw.Draw(img)
    d.text((w // 2, y0 + 48 + 230 + 70), SUB[idioma], font=fonte("Medium", 38), fill=(196, 205, 242), anchor="ms")
    return img.convert("RGB")


# ---------- miniatura (capa do vídeo) ----------
def miniatura(cena, linhas, destaque=(), w=1280, h=720, lado="esquerda"):
    """Capa: a cena (RGBA/RGB w×h, desenhada por código) + até 3 linhas curtas em Unbounded Black.
    `destaque`: índices das linhas em amarelo (as outras em branco). Texto com contorno escuro e sombra."""
    img = cena.convert("RGBA").resize((w, h))
    # véu escuro do lado do texto, para ler em qualquer cena
    veu = np.zeros((h, w), np.float32)
    xs = np.linspace(0, 1, w)[None, :] if lado == "esquerda" else np.linspace(1, 0, w)[None, :]
    veu[:] = np.clip(1 - xs / 0.62, 0, 1) ** 1.4 * 200
    img.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in NOITE] + [Image.fromarray(veu.astype(np.uint8))]))
    S = 2
    txt = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    n = len(linhas)
    cap = (h * S) * (0.135 if n <= 2 else 0.105)
    f = fonte("Black", cap / _cap("Black"))
    margem = w * S * 0.05
    larg_max = w * S * 0.60
    tams = []
    for l in linhas:                                          # linha longa diminui até caber
        ff = f
        while ff.getlength(l) > larg_max and ff.size > 20:
            ff = fonte("Black", ff.size * 0.94)
        tams.append(ff)
    alturas = [ff.size * _cap("Black") for ff in tams]
    passo = [a * 1.30 for a in alturas]
    y = (h * S - sum(passo) + passo[-1] * 0.23) / 2 + alturas[0]
    sombra = Image.new("RGBA", txt.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sombra)
    for i, (l, ff) in enumerate(zip(linhas, tams)):
        x = margem if lado == "esquerda" else w * S - margem - ff.getlength(l)
        cor = AMARELO if i in destaque else BRANCO
        ds.text((x + cap * 0.06, y + cap * 0.08), l, font=ff, fill=(0, 0, 0, 200), anchor="ls")
        d.text((x, y), l, font=ff, fill=cor, anchor="ls", stroke_width=int(cap * 0.055), stroke_fill=(8, 10, 30))
        y += passo[i]
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(cap * 0.07)).resize((w, h), Image.LANCZOS))
    img.alpha_composite(txt.resize((w, h), Image.LANCZOS))
    return img.convert("RGB")


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    avatar().save(SAIDA / "avatar.png")
    marca_dagua().save(SAIDA / "marca-dagua.png")
    for i in ("pt", "en"):
        logo(i, 300).save(SAIDA / f"logo-{i}.png")
        banner(i).save(SAIDA / f"banner-{i}.png")
    print("ok", sorted(p.name for p in SAIDA.iterdir()))
