"""Cenas 100% desenhadas por código para o canal "E se…?" (planeta, bonequinho, onda, vento…).

Cada cena é uma função (t, dur, w, h, p) -> Image, registrada em CENAS. `render(nome, params, dur, w, h, saida)` grava o mp4.
Estilo: desenho chapado, espaço azul-escuro, amarelo da marca nos textos.
"""
import json, math, random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import graficos as G

ESPACO_A, ESPACO_B = (6, 8, 24), (18, 22, 52)
OCEANO = np.array([52, 132, 245], dtype=np.float32)
TERRA = np.array([236, 212, 140], dtype=np.float32)
CEU_A, CEU_B = (90, 160, 235), (190, 225, 250)
CHAO = (120, 92, 70)
AMARELO, BRANCO = G.AMARELO, G.BRANCO

# contornos bem simplificados dos continentes (lon, lat) — estilo desenho, não mapa preciso
CONTINENTES = [
    [(-80, 10), (-75, 12), (-62, 11), (-50, 2), (-35, -6), (-39, -20), (-48, -27), (-58, -38), (-68, -55), (-74, -48), (-75, -38), (-71, -18), (-81, -5)],
    [(-17, 15), (-10, 35), (10, 37), (32, 31), (43, 12), (51, 11), (40, -15), (35, -25), (20, -35), (12, -17), (9, 4), (-8, 5)],
    [(-168, 66), (-140, 70), (-95, 72), (-62, 62), (-55, 50), (-76, 35), (-81, 25), (-97, 17), (-105, 21), (-118, 33), (-124, 48), (-140, 59)],
    [(-10, 36), (-9, 44), (0, 50), (8, 55), (24, 70), (60, 72), (100, 77), (140, 72), (172, 68), (160, 56), (140, 42), (122, 30),
     (108, 18), (100, 6), (80, 8), (72, 20), (57, 24), (50, 30), (36, 36), (27, 40), (14, 40)],
    [(114, -22), (130, -12), (142, -11), (153, -27), (146, -39), (135, -35), (115, -34)],
    [(-55, 60), (-20, 70), (-25, 82), (-60, 82), (-70, 76)],
    [(-180, -72), (180, -72), (180, -90), (-180, -90)],
]
_TEX = None


MAPA = Path(__file__).parent / "mapa" / "terra-50m.json"


def poligonos_terra():
    """Contornos reais dos continentes (Natural Earth 1:50m, domínio público); sem o arquivo, os desenhados à mão."""
    if MAPA.exists():
        return json.loads(MAPA.read_text())["poligonos"]
    return CONTINENTES


def textura(W=4096, H=2048):
    """Máscara da terra (0 a 1) em projeção equirretangular."""
    global _TEX
    if _TEX is None:
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        for poly in poligonos_terra():
            d.polygon([((lon + 180) / 360 * W, (90 - lat) / 180 * H) for lon, lat in poly], fill=255)
        img = img.filter(ImageFilter.GaussianBlur(1.2))
        _TEX = np.asarray(img, dtype=np.float32) / 255.0
    return _TEX


_COR = None


def cor_terra():
    """Cor da terra com variação suave (mais escura no interior) e gelo perto dos polos: RGB float H×W×3."""
    global _COR
    if _COR is None:
        tex = textura()
        H, W = tex.shape
        rnd = np.random.default_rng(3)
        ruido = np.zeros((H // 16, W // 16), np.float32)
        for k in (1, 2, 4):
            r = rnd.normal(size=(H // 16 // k + 1, W // 16 // k + 1)).astype(np.float32)
            ruido += np.asarray(Image.fromarray(r).resize((W // 16, H // 16), Image.BICUBIC)) / k
        ruido = np.asarray(Image.fromarray(ruido).resize((W, H), Image.BICUBIC))
        lat = np.linspace(90, -90, H, dtype=np.float32)[:, None]
        gelo = np.clip((np.abs(lat) - 62) / 12, 0, 1)
        terra = TERRA[None, None, :] * (1 + 0.07 * ruido[..., None])
        terra = terra * (1 - gelo[..., None]) + np.array([240, 246, 255], np.float32) * gelo[..., None]
        _COR = terra
    return _COR


class Globo:
    """Planeta em projeção ortográfica, girando por `lon0` (graus)."""

    def __init__(self, raio):
        self.r = r = int(raio)
        ys, xs = np.mgrid[-r:r, -r:r].astype(np.float32) + 0.5
        x, y = xs / r, ys / r
        d = np.sqrt(x * x + y * y)
        z = np.sqrt(np.clip(1 - d * d, 0, 1))
        self.lat = np.degrees(np.arcsin(np.clip(-y, -1, 1)))
        self.lon = np.degrees(np.arctan2(x, z))
        luz = np.array([-0.55, -0.45, 0.70]); luz /= np.linalg.norm(luz)
        self.sombra = np.clip(0.30 + 0.85 * np.clip(x * luz[0] + (-y) * -luz[1] + z * luz[2], 0, 1), 0, 1.1)
        self.alfa = np.clip((1 - d) * r, 0, 1)

    def imagem(self, lon0):
        tex = textura()
        H, W = tex.shape
        u = (((self.lon + lon0 + 180) % 360) / 360 * (W - 1)).astype(np.int32)
        v = ((90 - self.lat) / 180 * (H - 1)).astype(np.int32)
        m = tex[v, u][..., None]
        cor = (cor_terra()[v, u] * m + OCEANO * (1 - m)) * self.sombra[..., None]
        rgba = np.dstack([np.clip(cor, 0, 255), self.alfa * 255]).astype(np.uint8)
        return Image.fromarray(rgba, "RGBA")

    def ponto(self, lon, lat, lon0):
        """Posição (x, y) na imagem do globo e se está do lado visível."""
        la, lo = math.radians(lat), math.radians(lon - lon0)
        x, y, z = math.cos(la) * math.sin(lo), -math.sin(la), math.cos(la) * math.cos(lo)
        return self.r + x * self.r, self.r + y * self.r, z > 0.05


def lua_esfera(r, semente=5, luz=(-0.55, -0.45, 0.70)):
    """Lua cinza com mares escuros suaves e crateras com borda clara, iluminada de cima à esquerda (RGBA 2r×2r)."""
    r = int(r)
    ys, xs = np.mgrid[-r:r, -r:r].astype(np.float32) + 0.5
    x, y = xs / r, ys / r
    dd = np.sqrt(x * x + y * y)
    z = np.sqrt(np.clip(1 - dd * dd, 0, 1))
    L = np.array(luz, np.float32); L /= np.linalg.norm(L)
    rnd = np.random.default_rng(semente)
    base = np.full((2 * r, 2 * r), 190.0, np.float32)
    for _ in range(9):                                     # mares: manchas escuras de borda suave
        cx, cy, rr = rnd.uniform(-0.7, 0.5), rnd.uniform(-0.6, 0.6), rnd.uniform(0.12, 0.32)
        base -= rnd.uniform(22, 40) * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * rr * rr))
    nx, ny = x, y
    for _ in range(70):                                    # crateras: fundo escuro e borda clara do lado da luz
        cx, cy = rnd.uniform(-0.95, 0.95), rnd.uniform(-0.95, 0.95)
        rr = float(rnd.choice([0.02, 0.03, 0.04, 0.05, 0.07, 0.10]))
        q = np.sqrt((nx - cx) ** 2 + (ny - cy) ** 2) / rr
        dentro = q < 1
        base[dentro] -= 18 * (1 - q[dentro] ** 2)
        borda = (q >= 0.85) & (q < 1.25)
        lado = ((nx - cx) * L[0] + (ny - cy) * L[1]) / rr       # borda virada para a luz fica clara
        base[borda] += 16 * np.clip(-lado[borda] + 0.2, 0, 1)
    luz_k = np.clip(0.16 + 0.98 * np.clip(x * L[0] + y * L[1] + z * L[2], 0, 1), 0, 1.15) ** 0.9
    v = np.clip(base * luz_k, 0, 255)
    rgb = np.dstack([v * 1.0, v * 0.985, v * 0.955])
    alfa = np.clip((1 - dd) * r, 0, 1) * 255
    return Image.fromarray(np.dstack([rgb, alfa]).astype(np.uint8), "RGBA")


_globos, _fundos = {}, {}


def globo(raio):
    if raio not in _globos:
        _globos[raio] = Globo(raio)
    return _globos[raio]


def espaco(w, h):
    k = (w, h)
    if k not in _fundos:
        img = Image.new("RGB", (w, h), ESPACO_A)
        d = ImageDraw.Draw(img)
        for y in range(h):
            f = (y / h) ** 1.2
            d.line([(0, y), (w, y)], fill=tuple(int(ESPACO_A[i] + (ESPACO_B[i] - ESPACO_A[i]) * f) for i in range(3)))
        rnd = random.Random(7)
        for _ in range(int(w * h / 4000)):
            x, y, s = rnd.random() * w, rnd.random() * h, rnd.choice([1, 1, 1, 2, 2, 3])
            c = rnd.randint(140, 255)
            d.ellipse([x, y, x + s, y + s], fill=(c, c, min(255, c + 20)))
        _fundos[k] = img
    return _fundos[k].copy()


def ceu(w, h, chao_y):
    k = ("ceu", w, h, chao_y)
    if k not in _fundos:
        img = Image.new("RGB", (w, h), CEU_A)
        d = ImageDraw.Draw(img)
        for y in range(int(chao_y)):
            f = y / chao_y
            d.line([(0, y), (w, y)], fill=tuple(int(CEU_A[i] + (CEU_B[i] - CEU_A[i]) * f) for i in range(3)))
        d.rectangle([0, chao_y, w, h], fill=CHAO)
        d.rectangle([0, chao_y, w, chao_y + h * 0.012], fill=(150, 118, 90))
        _fundos[k] = img
    return _fundos[k].copy()


def glow(img, cx, cy, r, cor=(80, 150, 255), forca=0.55):
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(camada).ellipse([cx - r * 1.08, cy - r * 1.08, cx + r * 1.08, cy + r * 1.08], fill=cor + (int(255 * forca),))
    camada = camada.filter(ImageFilter.GaussianBlur(r * 0.12))
    img.paste(camada, (0, 0), camada)


def texto(d, xy, txt, tam, cor=BRANCO, peso="black", anchor="mm", a=1.0, contorno=0):
    f = G.fonte(peso, int(tam))
    d.text(xy, txt, font=f, fill=G.alfa(cor, a, (0, 0, 0)) if a < 1 else cor, anchor=anchor,
           stroke_width=contorno, stroke_fill=(0, 0, 0))


def titulo_quebrado(d, txt, cx, y0, largura, tam, a=1.0, cor=BRANCO):
    f = G.fonte("black", int(tam))
    linhas = G.quebrar(txt, f, largura, d)
    for i, l in enumerate(linhas):
        d.text((cx, y0 + i * tam * 1.12), l, font=f, fill=cor, anchor="ma", stroke_width=max(2, int(tam / 14)), stroke_fill=(0, 0, 0))
    return y0 + len(linhas) * tam * 1.12


def boneco(tam, cor=(255, 255, 255), pose=0.0):
    """Bonequinho de palito (RGBA). pose 0 = de pé, 1 = braços e pernas abertos (voando)."""
    S = 4
    W = int(tam * S)
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, int(W * 0.055))
    cx, cab = W / 2, W * 0.2
    d.ellipse([cx - W * 0.09, cab - W * 0.09, cx + W * 0.09, cab + W * 0.09], fill=cor)
    ombro, quadril = W * 0.34, W * 0.6
    d.line([(cx, cab + W * 0.08), (cx, quadril)], fill=cor, width=lw)
    ab = 0.35 + 0.9 * pose
    for s in (-1, 1):
        d.line([(cx, ombro), (cx + s * W * 0.2 * math.sin(ab + 0.4), ombro + W * 0.18 * math.cos(ab + 0.4) - W * 0.12 * pose)], fill=cor, width=lw)
        d.line([(cx, quadril), (cx + s * W * 0.16 * (0.6 + pose), quadril + W * 0.3 * (1 - 0.3 * pose))], fill=cor, width=lw)
    return img.resize((int(tam), int(tam)), Image.LANCZOS)


def casa(d, x, base, s, cor=(240, 240, 245), teto=(220, 70, 80)):
    d.rectangle([x, base - s, x + s * 1.2, base], fill=cor)
    d.polygon([(x - s * 0.1, base - s), (x + s * 0.6, base - s * 1.55), (x + s * 1.3, base - s)], fill=teto)
    d.rectangle([x + s * 0.45, base - s * 0.5, x + s * 0.75, base], fill=(90, 70, 60))


def arvore(d, x, base, s, inclina=0.0):
    topo = (x + inclina * s, base - s * 1.4)
    d.line([(x, base), topo], fill=(110, 80, 55), width=max(3, int(s * 0.14)))
    r = s * 0.55
    d.ellipse([topo[0] - r, topo[1] - r, topo[0] + r, topo[1] + r], fill=(60, 160, 210))  # copa azulada (sem verde)


def tremor(t, ini, dur, forca):
    if ini <= t <= ini + dur:
        k = 1 - (t - ini) / dur
        return (math.sin(t * 90) * forca * k, math.cos(t * 77) * forca * k)
    return (0, 0)


# ------------------------------------------------------------------ cenas
def c_titulo(t, dur, w, h, p):
    img = espaco(w, h)
    vert = h > w
    r = int(min(w, h) * (0.36 if vert else 0.33))
    cx, cy = w / 2, h * (0.58 if vert else 0.62)
    glow(img, cx, cy, r)
    g = globo(r)
    gi = g.imagem(-15 - 30 * t)
    img.paste(gi, (int(cx - r), int(cy - r)), gi)
    d = ImageDraw.Draw(img)
    k = G.ease(t / 0.6)
    tam = (h * 0.07 if vert else h * 0.095) * (0.6 + 0.4 * k)
    titulo_quebrado(d, p.get("titulo", ""), w / 2, h * (0.1 if vert else 0.07), w * 0.9, tam, cor=AMARELO)
    return img


def c_velocidade(t, dur, w, h, p):
    img = espaco(w, h)
    vert = h > w
    r = int(min(w, h) * (0.33 if vert else 0.36))
    cx, cy = (w / 2, h * 0.42) if vert else (w * 0.33, h * 0.52)
    glow(img, cx, cy, r)
    g = globo(r)
    lon0 = -30 - 6 * t
    gi = g.imagem(lon0)
    img.paste(gi, (int(cx - r), int(cy - r)), gi)
    d = ImageDraw.Draw(img)
    px, py, vis = g.ponto(-47.9, -15.8, lon0)
    if vis:
        x, y = cx - r + px, cy - r + py
        a = G.ease((t - 0.3) / 0.4)
        rr = 14 + 10 * math.sin(t * 6) ** 2
        d.ellipse([x - rr * a, y - rr * a, x + rr * a, y + rr * a], fill=AMARELO)
        texto(d, (x, y - 40), p.get("voce", "VOCÊ"), h * 0.035, AMARELO, a=a, contorno=3)
    # velocímetro
    alvo = float(p.get("velocidade", 1600))
    v = alvo * G.ease((t - 0.6) / 1.8)
    bx, by = (w / 2, h * 0.82) if vert else (w * 0.74, h * 0.48)
    num = f"{int(v):,}".replace(",", ".")
    texto(d, (bx, by), num, h * (0.1 if vert else 0.14), AMARELO, contorno=0)
    texto(d, (bx, by + h * (0.075 if vert else 0.1)), p.get("unidade", "km/h"), h * 0.045, BRANCO, peso="bold")
    if p.get("legenda"):
        texto(d, (bx, by - h * (0.08 if vert else 0.12)), p["legenda"], h * 0.032, BRANCO, peso="semi", a=G.ease((t - 0.8) / 0.5))
    # setas de giro
    for i in range(3):
        ang = math.radians(200 + i * 25 + (t * 40) % 25)
        ax, ay = cx + math.cos(ang) * r * 1.12, cy + math.sin(ang) * r * 1.12
        d.ellipse([ax - 5, ay - 5, ax + 5, ay + 5], fill=(170, 200, 255))
    return img


def c_parada(t, dur, w, h, p):
    img = espaco(w, h)
    vert = h > w
    r = int(min(w, h) * (0.3 if vert else 0.34))
    T0 = 0.6  # o planeta freia aqui
    sx, sy = tremor(t, T0, 0.8, h * 0.012)
    cx, cy = (w * 0.5 + sx, h * 0.62 + sy) if vert else (w * 0.3 + sx, h * 0.55 + sy)
    glow(img, cx, cy, r, cor=(255, 90, 90) if T0 < t < T0 + 0.6 else (80, 150, 255))
    g = globo(r)
    lon0 = -40 - 10 * min(t, T0)
    gi = g.imagem(lon0)
    img.paste(gi, (int(cx - r), int(cy - r)), gi)
    d = ImageDraw.Draw(img)
    if T0 - 0.1 < t < T0 + 0.5:
        texto(d, (cx, cy - r - h * 0.06), "STOP!", h * 0.08, (255, 90, 90), contorno=4)
    px, py, _ = g.ponto(-47.9, -15.8, lon0)
    ox, oy = cx - r + px, cy - r + py
    tv = max(0.0, t - T0)
    voo_x = ox + tv * w * (0.18 if vert else 0.22)
    voo_y = oy - tv * h * 0.16 + (tv ** 2) * h * 0.015
    b = boneco(h * 0.17, cor=AMARELO, pose=min(1.0, tv * 3))
    b = b.rotate(-tv * 380, expand=True, resample=Image.BICUBIC)
    for i in range(6 if tv > 0 else 0):  # linhas de velocidade
        yy = voo_y + (i - 2.5) * h * 0.018
        d.line([(voo_x - w * 0.08 - i * 15, yy), (voo_x - w * 0.02, yy)], fill=(200, 220, 255), width=3)
    img.paste(b, (int(voo_x - b.width / 2), int(voo_y - b.height / 2)), b)
    # comparação de velocidade
    if tv > 0.6:
        a = G.ease((tv - 0.6) / 0.6)
        x0 = w * (0.08 if vert else 0.56)
        y0 = h * (0.12 if vert else 0.1)
        larg = w * (0.62 if vert else 0.27)
        alt = h * 0.05
        itens = [(p.get("voce", "Você"), float(p.get("velocidade", 1600)), AMARELO),
                 (p.get("aviao", "Avião a jato"), float(p.get("vel_aviao", 900)), (150, 170, 200))]
        mx = max(v for _, v, _ in itens)
        for i, (nome, v, cor) in enumerate(itens):
            y = y0 + i * alt * 2.3
            texto(d, (x0, y), nome, h * 0.03, BRANCO, peso="bold", anchor="ls", a=a)
            d.rounded_rectangle([x0, y + 8, x0 + larg * v / mx * a, y + 8 + alt], radius=alt / 2, fill=cor)
            texto(d, (x0 + larg * v / mx * a + 14, y + 8 + alt / 2), f"{int(v):,} km/h".replace(",", "."), h * 0.03, BRANCO,
                  peso="bold", anchor="lm", a=a)
    return img


def c_tsunami(t, dur, w, h, p):
    vert = h > w
    chao = h * (0.72 if vert else 0.74)
    img = ceu(w, h, chao)
    d = ImageDraw.Draw(img)
    rnd = random.Random(3)
    T0 = 0.8
    obj_t = max(0.0, t - T0) * 4.5 / max(4.5, dur)
    # casas e árvores sendo arrastadas para a direita
    for i in range(9):
        x = w * (0.05 + i * 0.12) + (obj_t ** 1.6) * w * (0.25 + rnd.random() * 0.2)
        s = h * (0.06 + rnd.random() * 0.03)
        y = chao - (obj_t ** 2) * h * rnd.random() * 0.15
        if i % 3 == 0:
            arvore(d, x, y, s, inclina=min(1.2, obj_t * 2))
        else:
            casa(d, x, y, s)
    # onda gigante vindo da esquerda
    frente = -w * 0.3 + min(1.0, t / max(1.0, dur * 0.85)) * w * 1.0  # a onda cruza a tela no tempo da cena
    alt = h * (0.55 + 0.05 * math.sin(t * 3))
    pts = [(-10, h), (-10, chao - alt * 0.6)]
    for k in range(40):
        f = k / 39
        x = -10 + (frente + 10) * f
        y = chao - alt * (0.6 + 0.4 * f ** 3) + math.sin(f * 14 + t * 6) * h * 0.012
        pts.append((x, y))
    pts += [(frente + w * 0.05, chao - alt * 0.85), (frente + w * 0.08, chao - alt * 0.6), (frente + w * 0.03, chao), (frente, h)]
    d.polygon(pts, fill=(40, 110, 220))
    d.line(pts[2:-3], fill=(235, 245, 255), width=int(h * 0.012))
    for k in range(12):  # espuma
        fx = frente + w * 0.02 + math.sin(k * 7 + t * 9) * w * 0.02
        fy = chao - alt * (0.85 - k * 0.05)
        rr = h * 0.012
        d.ellipse([fx - rr, fy - rr, fx + rr, fy + rr], fill=(240, 248, 255))
    if p.get("texto"):
        titulo_quebrado(d, p["texto"], w / 2, h * (0.12 if vert else 0.08), w * 0.85, h * (0.05 if vert else 0.065), cor=BRANCO)
    return img


def c_vento(t, dur, w, h, p):
    vert = h > w
    chao = h * (0.74 if vert else 0.78)
    img = ceu(w, h, chao)
    d = ImageDraw.Draw(img)
    rnd = random.Random(11)
    for i in range(70):  # rajadas
        y = rnd.random() * chao
        vel = 0.8 + rnd.random() * 1.4
        x = ((rnd.random() + t * vel) % 1.3 - 0.2) * w
        comp = w * (0.08 + rnd.random() * 0.15)
        d.line([(x, y), (x + comp, y)], fill=(255, 255, 255), width=rnd.choice([2, 3, 4]))
    for i in range(6):
        arvore(d, w * (0.1 + i * 0.16), chao, h * 0.1, inclina=0.9 + 0.15 * math.sin(t * 8 + i))
    a = G.ease((t - 0.2) / 0.5)
    pulso = 1 + 0.04 * math.sin(t * 10)
    titulo_quebrado(d, p.get("titulo", ""), w / 2, h * (0.18 if vert else 0.14), w * 0.9, h * (0.07 if vert else 0.1) * pulso, cor=AMARELO)
    if p.get("final") and t > dur * 0.55:
        af = G.ease((t - dur * 0.55) / 0.6)
        texto(d, (w / 2, h * (0.5 if vert else 0.45)), p["final"], h * (0.04 if vert else 0.055), BRANCO, a=af, contorno=4)
    return img


CENAS = {"titulo_terra": c_titulo, "velocidade": c_velocidade, "parada": c_parada, "tsunami": c_tsunami, "vento": c_vento}


def render(nome, params, dur, w, h, saida):
    f = CENAS[nome]
    G._escrever(lambda t: f(t, dur, w, h, params).convert("RGB"), max(1, round(dur * G.FPS)), w, h, saida)
