"""Cenas 2D no estilo documentário ilustrado (o jeito dos canais tipo Oceanverse): cores chapadas, céu de papel, água
em corte (a superfície com cristinhas e o fundo em degradê), papel rasgado e mapas antigos. Tudo desenhado por código,
nenhuma imagem pronta ou gerada por IA.

Mesmo formato de cenas3d.py: cena(q, t, dur, p, ctx) pinta o quadro float32 q (H×W×3). As paisagens vêm de
paisagem.py (camadas com paralaxe); os desenhos fixos (navio, cartões, etiquetas) são feitos em alta resolução uma vez
e guardados. As cenas usam o tamanho do próprio q, então também servem de fundo desfocado (renderizadas pequenas).

Etiquetas (em qualquer cena): p["etiquetas"] = [{"texto": {"pt", "en"}, "x": 0.5, "y": 0.2, "em": 0.3 (fração da
batida em que aparece; ou "em_palavra": índice), "estilo": "papel|amarelo|vermelho", "tam": 46, "rot": -3}].
Câmera: p["zoom"] = [1.0, 1.05] (aproxima devagar, com paralaxe nas paisagens), p["pan"] = [dx0, dx1] em pixels.

Catálogo:
  mar_navio     mar em corte (céu de papel, água turquesa com peixes e raios de luz) e o galeão indo para a ilha;
                tempestade=True (céu escuro, chuva, relâmpagos), fumaca=x (coluna de fumaça na ilha), navio=False;
                inclina=[0, 14, 6] (o navio deitando de lado, graus ao longo da batida) e afunda=[0, 0.3, 1] (o navio
                descendo para o fundo, fração da altura, com bolhas subindo), desde 10/11/2026
  frota         vários galeões: a Armada (bandeira), navios presos no porto (parados=True) ou batalha=True
  mapa          cartão de mapa antigo (contornos reais do Natural Earth), rota pontilhada com o navio, rosa dos ventos
  calendario    folha de calendário: dia e mês fixos, as folhas dos anos virando
  ilha_noite    ilha à noite: lua, nuvens, floresta em camadas com névoa, a cerca de troncos, vaga-lumes e a água
  entalhe       troncos de perto, a palavra entalhada letra por letra (com lascas voando) à luz de tocha
  cruz          cartão pregado na madeira com o sinal combinado (uma cruz) sendo riscado
  linha_tempo   linha do tempo em papel, com ícones nos marcos e um intervalo destacado
  titulo        cartão grande com o título do vídeo, sobre a ilha à noite
  capitulo      cartão de capítulo ("PARTE 1" e o nome) sobre uma cena desfocada
  retrato       camafeu com a silhueta de perfil de uma figura da época (não é retrato fiel), nome e ano; apaga=[t0, t1]
  colonos       a praia com o grupo de colonos aparecendo um a um, o navio ao fundo
  baus          cinco baús arrombados na areia, papéis voando
  escavacao     corte do solo numa escavação: camadas, a grade de barbante e os achados aparecendo
  aneis         corte de um tronco de cipreste com os anéis; destaque=True acende os três anéis finos da seca
  pedra         pedra com inscrição entalhada aparecendo letra a letra; muitas=True mostra a pilha de pedras falsas
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import efeitos as FX
import paisagem as P

PASTA = Path(__file__).parent
FONTES = PASTA / "fontes"
PAPEL = (240, 229, 204)
PAPEL_SOMBRA = (214, 196, 160)
TINTA = (34, 30, 28)
VERMELHO = (196, 60, 46)
AMARELO = (242, 192, 56)
BRANCO = (250, 248, 242)

CEU_DIA = [(0.0, (0.89, 0.82, 0.72)), (0.55, (0.96, 0.90, 0.80)), (1.0, (0.96, 0.90, 0.80))]
CEU_NOITE = [(0.0, (0.035, 0.05, 0.12)), (0.45, (0.09, 0.13, 0.25)), (0.72, (0.18, 0.24, 0.37)), (1.0, (0.18, 0.24, 0.37))]
AGUA_DIA = dict(clara=(0.42, 0.80, 0.82), corpo=(0.22, 0.64, 0.72), fundo=(0.05, 0.20, 0.34), brilho=(0.84, 0.98, 0.98),
                lis_cor=(0.55, 0.85, 0.88), r_cor=(0.55, 0.85, 0.85))
AGUA_NOITE = dict(clara=(0.20, 0.30, 0.45), corpo=(0.09, 0.16, 0.28), fundo=(0.02, 0.04, 0.10), brilho=(0.50, 0.60, 0.78),
                  lis_cor=(0.22, 0.32, 0.48), r_cor=(0.28, 0.38, 0.55))


def L(x, idioma):
    if isinstance(x, dict):
        return x.get(idioma) or x.get("pt") or ""
    return x if x is not None else ""


@lru_cache(maxsize=32)
def fonte(peso, tam):
    return ImageFont.truetype(str(FONTES / f"Poppins-{peso}.ttf"), int(tam))


def _curva(p0, p1, p2, n=24):
    """Pontos de uma Bézier quadrática."""
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = map(np.array, (p0, p1, p2))
    return [tuple(v) for v in (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2]


# ------------------------------------------------------------------ papel
def _rasgado(x0, y0, x1, y1, semente, amp=5.0, passo=14):
    """Contorno de papel rasgado em volta do retângulo."""
    rnd = np.random.default_rng(semente)
    pts = []
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        n = max(2, int(math.hypot(bx - ax, by - ay) / passo))
        nx, ny = (by - ay), -(bx - ax)
        nn = math.hypot(nx, ny) or 1
        nx, ny = nx / nn, ny / nn
        for k in range(n):
            f = k / n
            j = rnd.uniform(-amp, amp) * (0.35 if k % 3 else 1.0)
            pts.append((ax + (bx - ax) * f + nx * j, ay + (by - ay) * f + ny * j))
    return pts


def _sombra(rgba, raio=10, desloc=(6, 10), forca=0.45):
    """Sombra suave embaixo de um recorte RGBA (devolve um RGBA maior, com a sombra e o recorte)."""
    m = raio * 2 + max(abs(desloc[0]), abs(desloc[1]))
    w, h = rgba.size
    out = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    a = rgba.getchannel("A").point(lambda v: int(v * forca))
    sombra = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
    sombra.putalpha(a)
    out.alpha_composite(sombra, (m + desloc[0], m + desloc[1]))
    out = out.filter(ImageFilter.GaussianBlur(raio))
    out.alpha_composite(rgba, (m, m))
    return out


@lru_cache(maxsize=24)
def _textura_papel(w, h, semente=1):
    rnd = np.random.default_rng(semente)
    campo = np.zeros((h, w), np.float32)
    for cel, peso in ((max(8, w // 6), 1.0), (max(4, w // 25), 0.4), (3, 0.15)):
        q = rnd.normal(size=(h // cel + 2, w // cel + 2)).astype(np.float32)
        campo += np.asarray(Image.fromarray(q).resize((w, h), Image.BICUBIC)) * peso
    return campo


@lru_cache(maxsize=96)
def etiqueta(texto, tam=46, estilo="papel", semente=1, rot=0.0):
    """Etiqueta de papel rasgado com o texto (RGBA, já com sombra)."""
    k = 2
    f = fonte("Bold" if estilo == "papel" else "ExtraBold", tam * k)
    asc, desc = f.getmetrics()
    tw = f.getlength(texto)
    px, py = tam * 0.55 * k, tam * 0.28 * k
    w, h = int(tw + 2 * px), int(asc + desc * 0.4 + 2 * py)
    pad = 12 * k
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fundo, cor = {"papel": (BRANCO, TINTA), "amarelo": (AMARELO, TINTA), "vermelho": (VERMELHO, BRANCO)}[estilo]
    d.polygon(_rasgado(pad, pad, pad + w, pad + h, semente, amp=2.6 * k, passo=9 * k), fill=fundo)
    d.text((pad + px, pad + py - desc * 0.15), texto, font=f, fill=cor)
    im = im.resize((im.width // k, im.height // k), Image.LANCZOS)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    return _sombra(im, raio=6, desloc=(3, 6), forca=0.5)


@lru_cache(maxsize=16)
def cartao(w, h, semente=3, cor=PAPEL):
    """Cartão de papel envelhecido com bordas rasgadas e textura (RGBA, sem sombra)."""
    k = 2
    W2, H2 = w * k, h * k
    m = 10 * k
    mascara = Image.new("L", (W2 + 2 * m, H2 + 2 * m), 0)
    ImageDraw.Draw(mascara).polygon(_rasgado(m, m, m + W2, m + H2, semente, amp=5 * k, passo=12 * k), fill=255)
    mascara = mascara.resize((w + 2 * 10, h + 2 * 10), Image.LANCZOS)
    tw, th = mascara.size
    tex = _textura_papel(tw, th, semente)
    base = np.array(cor, np.float32)[None, None, :] * (1 + 0.035 * tex[..., None])
    ys, xs = np.mgrid[0:th, 0:tw].astype(np.float32)
    borda = np.minimum(np.minimum(xs, tw - xs), np.minimum(ys, th - ys)) / (0.18 * min(tw, th))
    base *= (0.86 + 0.14 * np.clip(borda, 0, 1))[..., None]                       # bordas mais escuras
    rgba = np.dstack([np.clip(base, 0, 255).astype(np.uint8), np.asarray(mascara)])
    return Image.fromarray(rgba, "RGBA")


# ------------------------------------------------------------------ colar no quadro (float)
_NP = {}


def _np(img):
    """A imagem PIL como float 0..1 (guardada, porque as etiquetas e cartões se repetem a cada quadro)."""
    chave = id(img)
    item = _NP.get(chave)
    if item is not None and item[0] is img:
        return item[1]
    arr = np.asarray(img, np.float32) / 255.0
    if len(_NP) > 96:
        _NP.pop(next(iter(_NP)))
    _NP[chave] = (img, arr)
    return arr


def colar(q, a, x0, y0, alfa=1.0):
    """Cola a imagem RGBA (float h×w×4, 0..1) no quadro com o canto em (x0, y0). Devolve (X0, Y0, recorte usado)."""
    H, W = q.shape[:2]
    h, w = a.shape[:2]
    x0, y0 = int(round(x0)), int(round(y0))
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return None
    sub = a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    al = sub[..., 3:4] * alfa
    reg = q[Y0:Y1, X0:X1]
    reg[:] = reg * (1 - al) + sub[..., :3] * al
    return X0, Y0, sub


def colar_img(q, img, cx, cy, escala=1.0, alfa=1.0):
    """Cola uma imagem PIL RGBA centrada em (cx, cy)."""
    if escala != 1.0:
        img = img.resize((max(1, int(img.width * escala)), max(1, int(img.height * escala))), Image.BILINEAR)
        a = np.asarray(img, np.float32) / 255.0
    else:
        a = _np(img)
    return colar(q, a, cx - img.width / 2, cy - img.height / 2, alfa)


def poligono(q, pts, cor, alfa=1.0):
    """Polígono chapado com borda suave, direto no quadro."""
    H, W = q.shape[:2]
    pts = np.asarray(pts, np.float64)
    x0, y0 = (np.floor(pts.min(0)) - 1).astype(int)
    x1, y1 = (np.ceil(pts.max(0)) + 1).astype(int)
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if X1 <= X0 or Y1 <= Y0 or alfa <= 0:
        return
    k = 3
    m = Image.new("L", ((x1 - x0) * k, (y1 - y0) * k), 0)
    ImageDraw.Draw(m).polygon([((x - x0) * k, (y - y0) * k) for x, y in pts], fill=255)
    m = np.asarray(m.resize((x1 - x0, y1 - y0), Image.BOX), np.float32) * (alfa / 255.0)
    m = m[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None]
    reg = q[Y0:Y1, X0:X1]
    reg += (np.asarray(cor, np.float32) - reg) * m


def _etiquetas(q, p, t, dur, idioma):
    H, W = q.shape[:2]
    u = H / 1080
    for i, e in enumerate(p.get("etiquetas") or []):
        t0 = float(e.get("em", 0.0)) * dur
        if t < t0:
            continue
        k = FX.sai((t - t0) / 0.28, 3)
        esc = (0.82 + 0.18 * k) * u
        img = etiqueta(L(e.get("texto"), idioma), int(e.get("tam", 46)), e.get("estilo", "papel"), 3 + i, float(e.get("rot", 0)))
        colar_img(q, img, W * e.get("x", 0.5), H * e.get("y", 0.2) + (1 - k) * 18 * u, esc, min(1.0, k * 2))


def _poeira(q, t, n=140, cor=(1.0, 0.95, 0.85), forca=0.18, semente=21):
    H, W = q.shape[:2]
    u = H / 1080
    s = np.random.default_rng(semente).random((n, 5))
    xs = (s[:, 0] * W + np.sin(t * 0.4 + s[:, 1] * 6.28) * 30 * u + t * 6 * u) % W
    ys = (s[:, 2] * H - t * (4 + 10 * s[:, 3]) * u) % H
    FX.particulas(q, xs, ys, (1.0 + 2.2 * s[:, 4]) * u, np.tile([cor], (n, 1)), forca * (0.3 + 0.7 * s[:, 1]))


def _cam(p, t, dur, W, H, padrao_zoom=(1.0, 1.04), padrao_pan=(0.0, -25.0), cx=None, cy=None):
    k = FX.suave(t / max(dur, 1e-6))
    z = p.get("zoom", list(padrao_zoom))
    z = [z, z] if isinstance(z, (int, float)) else z
    pan = p.get("pan", list(padrao_pan))
    pan = [pan, pan] if isinstance(pan, (int, float)) else pan
    u = H / 1080
    return P.Camera(W, H, s=FX.mistura(z[0], z[1], k), dx=FX.mistura(pan[0], pan[1], k) * u, cx=cx, cy=cy)


def fundo(q, nome, t, dur, p, ctx, escuro=0.5, borrao=2.0, tinta=(1.0, 1.0, 1.0)):
    """Pinta no quadro a cena `nome` desfocada e escurecida (renderizada em 1/4 do tamanho), como fundo de cartões."""
    H, W = q.shape[:2]
    pq = np.empty((H // 4, W // 4, 3), np.float32)
    CENAS[nome](pq, t, dur, p, dict(ctx, W=W // 4, H=H // 4))
    im = Image.fromarray((np.clip(pq, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(borrao))
    q[:] = np.asarray(im.resize((W, H), Image.BICUBIC), np.float32) * (escuro / 255.0) * np.asarray(tinta, np.float32)


# ------------------------------------------------------------------ bichos e o navio
def gaivota(q, x, y, s, fase, t, cor=(0.30, 0.29, 0.32)):
    f = math.sin(t * 7.0 + fase)
    for lado in (-1, 1):
        a = (x, y)
        b = (x + lado * s * 0.5, y - s * (0.18 + 0.30 * f))
        c = (x + lado * s, y - s * (0.05 + 0.15 * f) + s * 0.12)
        FX.linha(q, a, b, largura=s * 0.11, cor=cor, forca=1.0)
        FX.linha(q, b, c, largura=s * 0.08, cor=cor, forca=1.0)


def peixe(q, x, y, s, t, fase, cor, alfa=0.7, lado=-1):
    bal = math.sin(t * 6 + fase) * 0.25
    corpo = [(x + lado * s * math.cos(a) * 0.9, y + s * 0.38 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 18)]
    poligono(q, corpo, cor, alfa)
    cx = x - lado * s * 0.85
    poligono(q, [(cx, y), (cx - lado * s * 0.55, y - s * (0.4 + bal)), (cx - lado * s * 0.55, y + s * (0.4 - bal))], cor, alfa)


def _galeao(altura, vela, bandeira, nacao="inglaterra"):
    """Galeão do século XVI, de lado (proa à direita), chapado com sombras simples. RGBA.
    A linha d'água fica a ~76% da altura. nacao muda as bandeiras: inglaterra (cruz de São Jorge), espanha (cruz de
    Borgonha em X), franca (azul com cruz branca), portugal (branca com o escudo das quinas), suecia (azul com cruz
    amarela)."""
    k = 3
    H = altura * k
    W = int(H * 1.32)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P_ = lambda u, v: (u * W, v * H)                                          # noqa: E731
    lw = lambda px: max(1, int(px * k * altura / 420))                       # noqa: E731
    madeira, madeira_c, madeira_e = (139, 90, 55), (166, 112, 70), (92, 58, 36)
    faixa, corda = (64, 40, 26), (70, 52, 38)
    vela_c, vela_s = (244, 234, 212), (218, 202, 172)
    amarelo = (250, 206, 102)
    mastros = {"mez": (0.27, 0.15), "gra": (0.50, 0.0), "tra": (0.72, 0.08)}
    for u, top in mastros.values():
        d.line([P_(u, top), P_(u, 0.66)], fill=madeira_e, width=lw(7))
    d.line([P_(0.86, 0.59), P_(1.0, 0.43)], fill=madeira_e, width=lw(6))                     # gurupés
    for u, top in mastros.values():                                                         # cordame
        for du in (-0.09, -0.05, 0.05, 0.09):
            d.line([P_(u, top + 0.04), P_(u + du, 0.63)], fill=corda, width=lw(1.6))
    d.line([P_(0.50, 0.01), P_(0.72, 0.10)], fill=corda, width=lw(1.6))
    d.line([P_(0.72, 0.09), P_(0.99, 0.44)], fill=corda, width=lw(1.6))
    d.line([P_(0.27, 0.16), P_(0.50, 0.03)], fill=corda, width=lw(1.6))
    b = 0.022 + 0.008 * math.sin(vela)
    for nome, v0, v1, mw, bar in (("gra", 0.06, 0.27, 0.10, b * 0.8), ("gra", 0.30, 0.56, 0.145, b),
                                  ("tra", 0.13, 0.30, 0.08, b * 0.7), ("tra", 0.33, 0.535, 0.115, b * 0.9)):
        u = mastros[nome][0]
        baixo = _curva(P_(u + mw * 1.05, v1 - 0.01), P_(u, v1 + bar * 2.2), P_(u - mw * 1.05, v1 - 0.01))
        lado_d = _curva(P_(u + mw, v0), P_(u + mw + bar * 0.6, (v0 + v1) / 2), P_(u + mw * 1.05, v1 - 0.01), 12)
        lado_e = _curva(P_(u - mw * 1.05, v1 - 0.01), P_(u - mw - bar * 0.6, (v0 + v1) / 2), P_(u - mw, v0), 12)
        d.polygon([P_(u - mw, v0)] + lado_d + baixo + lado_e, fill=vela_c)
        som = [P_(u - mw, v0), P_(u - mw * 0.45, v0), P_(u - mw * 0.5, v1 + bar * 1.2)] + \
            _curva(P_(u - mw * 0.5, v1 + bar * 1.2), P_(u - mw * 0.8, v1 + bar * 0.8), P_(u - mw * 1.05, v1 - 0.01), 8) + lado_e
        d.polygon(som, fill=vela_s)
        for f in (0.33, 0.66):
            xu = u - mw + 2 * mw * f
            d.line([P_(xu, v0), P_(xu, v1 + bar * 1.6 * math.sin(math.pi * f) - 0.005)], fill=(226, 212, 186), width=lw(1.2))
        d.line([P_(u - mw * 1.12, v0), P_(u + mw * 1.12, v0)], fill=madeira_e, width=lw(5))
    d.polygon([P_(0.30, 0.19), P_(0.18, 0.52), P_(0.37, 0.50)], fill=vela_c)                 # vela latina
    d.polygon([P_(0.30, 0.19), P_(0.18, 0.52), P_(0.25, 0.51)], fill=vela_s)
    d.line([P_(0.34, 0.14), P_(0.16, 0.54)], fill=madeira_e, width=lw(4))
    d.polygon([P_(0.97, 0.45), P_(0.86, 0.58), P_(0.93, 0.58)], fill=vela_c)                 # bujarrona
    borda = _curva(P_(0.10, 0.50), P_(0.50, 0.66), P_(0.90, 0.53), 40)
    quilha = _curva(P_(0.92, 0.66), P_(0.55, 0.92), P_(0.12, 0.84), 40)
    d.polygon([P_(0.06, 0.47)] + borda + [P_(0.95, 0.60), P_(0.92, 0.66)] + quilha + [P_(0.08, 0.80)], fill=madeira)
    d.polygon(_curva(P_(0.10, 0.71), P_(0.50, 0.81), P_(0.93, 0.66), 40) + quilha, fill=madeira_e)
    d.line(_curva(P_(0.07, 0.62), P_(0.50, 0.76), P_(0.94, 0.61), 40), fill=faixa, width=lw(9))   # cinta
    for off in (-0.045, 0.035):
        d.line(_curva(P_(0.08, 0.62 + off), P_(0.50, 0.76 + off), P_(0.93, 0.61 + off), 40), fill=madeira_e, width=lw(1.6))
    d.line([P_(0.06, 0.47)] + borda + [P_(0.95, 0.60)], fill=madeira_c, width=lw(5))
    d.polygon([P_(0.04, 0.40), P_(0.27, 0.43), P_(0.28, 0.57), P_(0.05, 0.53)], fill=madeira)   # castelo de popa
    d.line([P_(0.04, 0.40), P_(0.27, 0.43)], fill=madeira_c, width=lw(5))
    d.polygon([P_(0.76, 0.50), P_(0.92, 0.47), P_(0.93, 0.56), P_(0.77, 0.58)], fill=madeira)   # castelo de proa
    d.line([P_(0.76, 0.50), P_(0.92, 0.47)], fill=madeira_c, width=lw(5))
    for i in range(3):                                                                       # janelas acesas
        x0 = 0.07 + i * 0.06
        d.rectangle([P_(x0, 0.455 + i * 0.004), P_(x0 + 0.03, 0.49 + i * 0.004)], fill=amarelo)
    for i in range(7):                                                                       # portinholas
        u = 0.30 + i * 0.075
        v = 0.665 + 0.035 * (1 - ((u - 0.5) / 0.45) ** 2)
        d.rectangle([P_(u, v), P_(u + 0.026, v + 0.032)], fill=faixa)
        d.rectangle([P_(u + 0.004, v + 0.005), P_(u + 0.022, v + 0.027)], fill=(40, 26, 18))
    d.polygon([P_(0.075, 0.74), P_(0.105, 0.75), P_(0.12, 0.85), P_(0.09, 0.85)], fill=madeira_e)   # leme
    flamula = {"inglaterra": VERMELHO, "espanha": (214, 170, 40), "franca": (40, 70, 150), "portugal": (180, 30, 30),
               "suecia": (0, 82, 147)}[nacao]
    for j, (u, top) in enumerate(mastros.values()):                                          # flâmulas
        ond = math.sin(bandeira + j)
        y = top - 0.005
        d.polygon([P_(u, y), P_(u + 0.07, y + 0.012 + 0.006 * ond), P_(u, y + 0.03)], fill=flamula)
    d.line([P_(0.045, 0.40), P_(0.03, 0.28)], fill=madeira_e, width=lw(3))                  # bandeira da popa
    if nacao == "inglaterra":                                                                  # cruz de São Jorge
        d.rectangle([P_(0.0, 0.28), P_(0.03, 0.34)], fill=(246, 242, 232))
        d.rectangle([P_(0.0, 0.302), P_(0.03, 0.318)], fill=VERMELHO)
        d.rectangle([P_(0.0115, 0.28), P_(0.0185, 0.34)], fill=VERMELHO)
    elif nacao == "espanha":                                                                   # cruz de Borgonha
        d.rectangle([P_(-0.01, 0.28), P_(0.03, 0.34)], fill=(246, 242, 232))
        d.line([P_(-0.008, 0.283), P_(0.028, 0.337)], fill=(180, 30, 30), width=lw(4))
        d.line([P_(-0.008, 0.337), P_(0.028, 0.283)], fill=(180, 30, 30), width=lw(4))
    elif nacao == "portugal":                                                                  # branca, escudo das quinas
        d.rectangle([P_(-0.01, 0.28), P_(0.03, 0.34)], fill=(246, 242, 232))
        d.polygon([P_(0.002, 0.292), P_(0.018, 0.292), P_(0.018, 0.318), P_(0.010, 0.330), P_(0.002, 0.318)], fill=(180, 30, 30))
        d.polygon([P_(0.006, 0.298), P_(0.014, 0.298), P_(0.014, 0.316), P_(0.010, 0.322), P_(0.006, 0.316)], fill=(40, 70, 150))
    elif nacao == "suecia":                                                                    # azul, cruz amarela
        d.rectangle([P_(-0.01, 0.28), P_(0.03, 0.34)], fill=(0, 82, 147))
        d.rectangle([P_(-0.01, 0.304), P_(0.03, 0.316)], fill=(254, 204, 0))
        d.rectangle([P_(0.004, 0.28), P_(0.012, 0.34)], fill=(254, 204, 0))
    else:                                                                                     # França: azul, cruz branca
        d.rectangle([P_(-0.01, 0.28), P_(0.03, 0.34)], fill=(40, 70, 150))
        d.rectangle([P_(-0.01, 0.304), P_(0.03, 0.316)], fill=(246, 242, 232))
        d.rectangle([P_(0.006, 0.28), P_(0.014, 0.34)], fill=(246, 242, 232))
    d.ellipse([P_(0.035, 0.37), P_(0.05, 0.39)], fill=amarelo)                              # lanterna
    return im.resize((W // k, H // k), Image.LANCZOS)


@lru_cache(maxsize=160)
def navio(altura=420, fase=0, nacao="inglaterra", espelho=False):
    """Galeão (RGBA). fase 0..23 anima a barriga das velas e as bandeiras; espelho = proa para a esquerda."""
    a = fase / 24 * 2 * math.pi
    im = _galeao(int(altura), a, 2 * a, nacao)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if espelho else im


# ------------------------------------------------------------------ mapa
@lru_cache(maxsize=1)
def _poligonos():
    arq = PASTA / "mapa" / "terra-50m.json"
    return json.loads(arq.read_text())["poligonos"] if arq.exists() else []


def _rosa(d, cx, cy, r, k):
    """Rosa dos ventos de 8 pontas, em tinta, com o N."""
    tinta, clara = (92, 70, 48, 255), (226, 208, 170, 255)
    d.ellipse([cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78], outline=tinta, width=max(1, int(1.4 * k)))
    d.ellipse([cx - r * 0.66, cy - r * 0.66, cx + r * 0.66, cy + r * 0.66], outline=tinta, width=max(1, int(0.8 * k)))
    for i in range(8):
        a = math.pi / 2 - i * math.pi / 4
        comp = r if i % 2 == 0 else r * 0.58
        larg = r * (0.16 if i % 2 == 0 else 0.12)
        ponta = (cx + math.cos(a) * comp, cy - math.sin(a) * comp)
        e = (cx + math.cos(a + math.pi / 2) * larg, cy - math.sin(a + math.pi / 2) * larg)
        dd = (cx + math.cos(a - math.pi / 2) * larg, cy - math.sin(a - math.pi / 2) * larg)
        d.polygon([(cx, cy), e, ponta], fill=tinta)
        d.polygon([(cx, cy), dd, ponta], fill=clara, outline=tinta)
    d.text((cx, cy - r * 1.18), "N", font=fonte("Black", int(r * 0.42)), fill=tinta, anchor="mm")


def _ajustar_bbox(bbox, iw, ih):
    """Aumenta a menor dimensão da caixa (lon0, lon1, lat0, lat1) para o mapa não ficar esticado: 1° de longitude
    vale cos(latitude) de 1° de latitude. Nunca corta nada do que foi pedido."""
    lon0, lon1, lat0, lat1 = bbox
    cosl = math.cos(math.radians((lat0 + lat1) / 2))
    larg, alt = (lon1 - lon0) * cosl, (lat1 - lat0)
    alvo = iw / ih
    if larg / alt < alvo:                                                  # estreito demais: abre a longitude
        extra = (alt * alvo / cosl - (lon1 - lon0)) / 2
        lon0, lon1 = lon0 - extra, lon1 + extra
    else:                                                                  # baixo demais: abre a latitude
        extra = (larg / alvo - alt) / 2
        lat0, lat1 = lat0 - extra, lat1 + extra
    return (lon0, lon1, lat0, lat1)


@lru_cache(maxsize=8)
def cartao_mapa(w, h, bbox, rotulos=(), semente=5):
    """Cartão com um mapa antigo: mar com linhas, ondas de costa, terra bege, grade, rosa dos ventos.
    Devolve (cartão RGBA sem sombra, sombra RGBA, margem da sombra, projeção (m, iw, ih, k))."""
    c = cartao(w, h, semente).copy()
    k = 2
    m = int(min(w, h) * 0.07)
    iw, ih = (w - 2 * m) * k, (h - 2 * m) * k
    bbox = _ajustar_bbox(bbox, iw, ih)
    lon0, lon1, lat0, lat1 = bbox

    def pr(lon, lat):
        return ((lon - lon0) / (lon1 - lon0) * iw, (lat1 - lat) / (lat1 - lat0) * ih)

    mapa = Image.new("RGBA", (iw, ih), (150, 196, 204, 255))
    d = ImageDraw.Draw(mapa)
    for y in range(0, ih, 18 * k):                                                 # linhas do mar
        d.line([(0, y), (iw, y)], fill=(143, 189, 198, 255), width=k)
    polys = []
    for poly in _poligonos():
        lons = [p[0] for p in poly]
        lats = [p[1] for p in poly]
        if max(lons) < lon0 - 2 or min(lons) > lon1 + 2 or max(lats) < lat0 - 2 or min(lats) > lat1 + 2:
            continue
        pts = [pr(lo, la) for lo, la in poly]
        if len(pts) >= 3:
            polys.append(pts)
    for larg, cor in ((30, (160, 204, 210, 255)), (22, (150, 196, 204, 255)), (14, (166, 208, 214, 255)), (7, (150, 196, 204, 255))):
        for pts in polys:                                                           # ondas da costa
            d.line(pts + [pts[0]], fill=cor, width=larg * k, joint="curve")
    for pts in polys:
        d.polygon(pts, fill=(233, 214, 170, 255))
    for pts in polys:
        d.line(pts + [pts[0]], fill=(150, 118, 80, 255), width=2 * k, joint="curve")
    for g in range(int(math.ceil(lon0 / 4)) * 4, int(lon1) + 1, 4):                # grade
        x = pr(g, lat0)[0]
        for y in range(0, ih, 16 * k):
            d.line([(x, y), (x, y + 7 * k)], fill=(120, 96, 66, 90), width=k)
    for g in range(int(math.ceil(lat0 / 4)) * 4, int(lat1) + 1, 4):
        y = pr(lon0, g)[1]
        for x in range(0, iw, 16 * k):
            d.line([(x, y), (x + 7 * k, y)], fill=(120, 96, 66, 90), width=k)
    for (lo, la, txt) in rotulos:                                                  # nomes pequenos
        x, y = pr(lo, la)
        d.text((x, y), txt, font=fonte("Bold", 19 * k), fill=(120, 96, 66, 255), anchor="mm")
    _rosa(d, iw * 0.12, ih * 0.83, min(iw, ih) * 0.085, k)
    d.rectangle([2, 2, iw - 3, ih - 3], outline=(120, 96, 66, 255), width=2 * k)
    mapa = mapa.resize((iw // k, ih // k), Image.LANCZOS)
    c.alpha_composite(mapa, (10 + m, 10 + m))
    raio, desl = 14, (8, 14)
    ms = raio * 2 + max(desl)
    sombra = Image.new("RGBA", (c.width + 2 * ms, c.height + 2 * ms), (0, 0, 0, 0))
    s = Image.new("RGBA", c.size, (0, 0, 0, 255))
    s.putalpha(c.getchannel("A").point(lambda v: int(v * 0.55)))
    sombra.alpha_composite(s, (ms + desl[0], ms + desl[1]))
    sombra = sombra.filter(ImageFilter.GaussianBlur(raio))
    return c, sombra, ms, (10 + m, iw // k, ih // k, bbox)


def _alfinete(img, x, y, rotulo, u=1.0):
    d = ImageDraw.Draw(img)
    r = 9 * u
    d.ellipse([x - r, y - 2.6 * r - r, x + r, y - 2.6 * r + r], fill=VERMELHO, outline=(120, 30, 22))
    d.polygon([(x - r * 0.75, y - 2.6 * r + r * 0.4), (x + r * 0.75, y - 2.6 * r + r * 0.4), (x, y)], fill=VERMELHO)
    d.ellipse([x - r * 0.35, y - 2.6 * r - r * 0.35, x + r * 0.35, y - 2.6 * r + r * 0.35], fill=(255, 220, 210))
    if rotulo:
        e = etiqueta(rotulo, tam=24, estilo="papel", semente=4)
        img.alpha_composite(e, (int(x - e.width / 2), int(y - 2.6 * r - r - e.height + 6)))


def _barquinho(d, x, y, s, lado=1):
    """Navio pequeno de mapa antigo (casco e duas velas)."""
    d.polygon([(x - s, y), (x + s, y), (x + s * 0.7 * lado if lado > 0 else x + s * 0.7, y + s * 0.45),
               (x - s * 0.7, y + s * 0.45)], fill=(92, 60, 38, 255))
    d.line([(x, y), (x, y - s * 1.3)], fill=(70, 50, 34, 255), width=max(1, int(s * 0.12)))
    d.polygon([(x - s * 0.55, y - s * 1.15), (x + s * 0.55, y - s * 1.15), (x + s * 0.6, y - s * 0.2), (x - s * 0.6, y - s * 0.2)],
              fill=(246, 238, 220, 255), outline=(150, 120, 90, 255))
    d.polygon([(x, y - s * 1.45), (x + s * 0.45 * lado, y - s * 1.35), (x, y - s * 1.25)], fill=VERMELHO)


# ------------------------------------------------------------------ cenas
@lru_cache(maxsize=6)
def _perfis_mar(W, H, nivel_f, ilha_x):
    u = H / 1080
    nivel = H * nivel_f
    nuv = P.nuvens(W, H * 0.20, 5, (260 * u, 520 * u), (26 * u, 46 * u), semente=14, achatada=0.3, bolhas=(4, 8))
    nuv2 = P.nuvens(W, H * 0.36, 4, (200 * u, 380 * u), (18 * u, 30 * u), semente=6, achatada=0.3, bolhas=(4, 7))
    chao = P.ilha(W, W * ilha_x, W * (ilha_x + 0.52), nivel + 6 * u, 70 * u, semente=4, borda=0.2, escala=160 * u)
    flo_tras = P.floresta(W, chao - 18 * u, 70, (40 * u, 90 * u), 0.30, semente=9,
                          faixa=(W * (ilha_x + 0.04), W * (ilha_x + 0.49)), copas=0.35)
    flo = P.floresta(W, chao, 60, (30 * u, 70 * u), 0.32, semente=12, faixa=(W * (ilha_x + 0.03), W * (ilha_x + 0.5)), copas=0.45)
    tormenta = P.nuvens(W, H * 0.12, 9, (380 * u, 760 * u), (50 * u, 90 * u), semente=31, achatada=0.35, bolhas=(5, 9))
    tormenta2 = P.nuvens(W, H * 0.30, 8, (300 * u, 600 * u), (36 * u, 60 * u), semente=37, achatada=0.35, bolhas=(5, 9))
    return nuv, nuv2, flo_tras, flo, tormenta, tormenta2


def _fumaca_coluna(q, x, y, t, u, cor=(0.55, 0.52, 0.50), n=46, altura=0.45, vento=0.08, forca=0.5, semente=7):
    """Coluna de fumaça subindo de (x, y), levada pelo vento para a direita."""
    H, W = q.shape[:2]
    s = np.random.default_rng(semente).random((n, 3))
    idade = (t * 0.09 + s[:, 0]) % 1.0
    ys = y - idade * H * altura
    xs = x + idade ** 1.4 * W * vento + 14 * u * np.sin(t * 0.6 + s[:, 1] * 6.28) * idade
    raios = (10 + 70 * idade ** 0.8) * u * (0.8 + 0.4 * s[:, 2])
    alfas = forca * (1 - idade) ** 0.8 * np.clip(idade * 10, 0, 1)
    FX.fumaca(q, xs, ys, raios, cor, alfas)


def _fogueira(q, x, y, t, u, forca=1.0):
    """Brilho de fogueira entre as árvores (pisca), faíscas subindo e um pouco de fumaça."""
    pisca = 0.8 + 0.15 * math.sin(t * 11) + 0.08 * math.sin(t * 27 + 1.3)
    FX.brilho(q, x, y, 70 * u, cor=(1.0, 0.55, 0.22), forca=0.55 * pisca * forca, nucleo=0.6)
    FX.brilho(q, x, y - 6 * u, 18 * u, cor=(1.0, 0.80, 0.45), forca=1.1 * pisca * forca, nucleo=1.2)
    s = np.random.default_rng(11).random((24, 3))
    idade = (t * 0.5 + s[:, 0]) % 1.0
    FX.particulas(q, x + (s[:, 1] - 0.5) * 40 * u + idade * 20 * u, y - idade * 140 * u, (1.2 + s[:, 2]) * u,
                  np.tile([[1.0, 0.7, 0.3]], (24, 1)), 1.4 * (1 - idade) * forca)
    _fumaca_coluna(q, x, y - 30 * u, t, u, cor=(0.10, 0.11, 0.16), n=20, altura=0.3, vento=0.03, forca=0.35 * forca, semente=13)


def _notas(q, t, u, de=(0.95, 0.80), ate=(0.55, 0.30), n=7, cor=(0.98, 0.94, 0.82)):
    """Notas musicais (♪) subindo de um lado da tela para o outro."""
    H, W = q.shape[:2]
    for i in range(n):
        k = (t * 0.16 + i / n) % 1.0
        x = W * FX.mistura(de[0], ate[0], k) + 30 * u * math.sin(t * 1.5 + i)
        y = H * FX.mistura(de[1], ate[1], k)
        a = min(1.0, k * 5) * (1 - k) * 0.9
        s = (14 + 6 * (i % 3)) * u
        cabeca = [(x + s * 0.55 * math.cos(v) * math.cos(0.4) - s * 0.38 * math.sin(v) * math.sin(0.4),
                   y + s * 0.55 * math.cos(v) * math.sin(0.4) + s * 0.38 * math.sin(v) * math.cos(0.4)) for v in np.linspace(0, 6.28, 16)]
        poligono(q, cabeca, cor, a)
        FX.linha(q, (x + s * 0.48, y - s * 0.1), (x + s * 0.48, y - s * 2.0), largura=2.6 * u, cor=cor, forca=a)
        FX.linha(q, (x + s * 0.48, y - s * 2.0), (x + s * 1.05, y - s * 1.45), largura=2.6 * u, cor=cor, forca=a)


def no_tempo(v, f):
    """Valor ao longo da batida: um número fixo, ou uma lista de valores do começo ao fim (passagem suave entre eles)."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    v = [float(x) for x in v]
    if len(v) == 1:
        return v[0]
    x = min(max(f, 0.0), 1.0) * (len(v) - 1)
    i = min(int(x), len(v) - 2)
    k = x - i
    k = k * k * (3 - 2 * k)
    return v[i] * (1 - k) + v[i + 1] * k


def _mar(q, t, dur, p, ctx, navios):
    """Mar em corte. navios: [{"x": (x0, x1) em fração, "tam": 0.4, "nacao", "espelho", "fundo": 0..1 (longe = menor e
    mais claro), "balanco": 1.0}]. p: tempestade, fumaca (x da coluna), ilha, ilha_x, sol."""
    H, W = q.shape[:2]
    u = H / 1080
    nivel_f = p.get("nivel", 0.57)
    nivel = H * nivel_f
    tormenta = bool(p.get("tempestade"))
    cam = _cam(p, t, dur, W, H)
    c = P.Cena(q, cam, t, luz=tuple(p.get("sol", (0.80, 0.18))), semente=1)
    ilha_x = float(p.get("ilha_x", 0.66))
    nuv, nuv2, flo_tras, flo, torm, torm2 = _perfis_mar(W, H, nivel_f, ilha_x)
    if tormenta:
        c.ceu([(0.0, (0.13, 0.14, 0.18)), (0.55, (0.32, 0.34, 0.38)), (1.0, (0.32, 0.34, 0.38))])
        c.nuvens(torm, p=0.02, deriva=t * 30 * u, cor=(0.20, 0.21, 0.25), cor_base=(0.26, 0.27, 0.31), tex_k=0.06)
        c.nuvens(torm2, p=0.05, deriva=t * 55 * u, cor=(0.27, 0.28, 0.32), cor_base=(0.33, 0.34, 0.38), tex_k=0.06)
    else:
        c.ceu(CEU_DIA)
        sx, sy = c.luz_tela(0.0)
        for r, cor, a in ((150, (0.98, 0.88, 0.62), 0.25), (110, (0.99, 0.86, 0.55), 0.35), (72, (1.0, 0.84, 0.48), 1.0)):
            P._k_disco(q, float(sx), float(sy), float(r * u * cam.escala(0)), np.array(cor, np.float32), c.tex, 0.0, 0.0, float(a))
        for lista, pp, dv in ((nuv, 0.02, 4.0), (nuv2, 0.05, 7.0)):
            c.nuvens(lista, p=pp, deriva=t * dv * u - 6 * u, desloc=7 * u, cor=(0.84, 0.75, 0.63), alfa=0.5, tex_k=0.0)
            c.nuvens(lista, p=pp, deriva=t * dv * u, cor=(1.0, 0.97, 0.91), cor_base=(0.98, 0.93, 0.85), tex_k=0.03)
    if p.get("ilha", True):
        if p.get("fumaca") is not None:
            fx, fy = cam.ponto(W * float(p["fumaca"]), nivel - 40 * u, 0.25)
            _fumaca_coluna(q, fx, fy, t, u)
        c.faixa(flo_tras, None, p=0.25, cor=(0.52, 0.64, 0.58), borda=((0.10, 0.10, 0.06), 2.0 * u), luz_k=0.6, tex_k=0.04)
        c.faixa(flo, None, p=0.27, cor=(0.33, 0.50, 0.44), borda=((0.12, 0.12, 0.07), 2.0 * u), luz_k=0.6, tex_k=0.04)
    if not tormenta:
        for i, (gx, gy, gs) in enumerate(((0.36, 0.25, 26), (0.42, 0.30, 20), (0.31, 0.33, 16))):
            xw = W * gx + t * 18 * u + 10 * u * math.sin(t * 0.7 + i)
            x, y = cam.ponto(xw, H * gy + 6 * u * math.sin(t * 1.1 + i * 2), 0.4)
            gaivota(q, x, y, gs * u * cam.escala(0.4), i * 1.3, t)
    cascos = []
    for k, nv_p in enumerate(sorted(navios, key=lambda d: -d.get("fundo", 0.0))):
        x0f, x1f = nv_p.get("x", (0.14, 0.46))
        xw = W * FX.mistura(x0f, x1f, t / max(dur, 1e-6))
        longe = float(nv_p.get("fundo", 0.0))
        pn = 0.32 - 0.2 * longe
        bal = float(nv_p.get("balanco", 1.0)) * (3.0 if tormenta else 1.0)
        fase = (int(t * 8) + 5 * k) % 24
        nv0 = navio(int(H * nv_p.get("tam", 0.40) * cam.escala(pn)), fase, nv_p.get("nacao", "inglaterra"), bool(nv_p.get("espelho")))
        frac = t / max(dur, 1e-6)
        incl = no_tempo(nv_p.get("inclina"), frac)                       # o navio deitando de lado (graus)
        afund = min(1.0, max(0.0, no_tempo(nv_p.get("afunda"), frac)))   # descendo para o fundo (fração da altura)
        ang = math.sin(t * 1.1 + k * 1.7) * 1.6 * bal * (1 - afund) + incl
        nv = nv0.rotate(ang, resample=Image.BICUBIC, expand=True)
        xs, ys = cam.ponto(xw, nivel, pn)
        ys += math.sin(t * 1.3 + k) * 5 * u * bal * (1 - afund)
        a = np.asarray(nv, np.float32) / 255.0
        if longe > 0:                                                    # longe: mais claro (ar entre nós e o navio)
            ceu = np.asarray((0.93, 0.87, 0.78) if not tormenta else (0.40, 0.42, 0.46), np.float32)
            a[..., :3] = a[..., :3] * (1 - 0.45 * longe) + ceu * 0.45 * longe
        if incl or afund:                       # gira em volta da linha d'água (não do meio do desenho) e afunda
            ys += afund * nv0.height * 0.95
            r_ = math.radians(ang)
            d = 0.26 * nv0.height
            r = colar(q, a, xs - nv.width / 2 - d * math.sin(r_), ys - nv.height / 2 - d * math.cos(r_))
            nv_p = dict(nv_p, _afund=afund, _xs=xs, _larg=nv0.width, _alt=nv0.height)
        else:
            r = colar(q, a, xs - nv.width / 2, ys - nv.height * 0.76)
        if r:
            cascos.append((r, nv_p))
    agua = dict(AGUA_DIA)
    if tormenta:
        agua.update(clara=(0.42, 0.52, 0.56), corpo=(0.18, 0.30, 0.36), fundo=(0.04, 0.10, 0.16), brilho=(0.80, 0.86, 0.88))
    F = c.agua(nivel, p=0.3, crista=(14.0 if tormenta else 6.0) * u, faixa=(24.0 if tormenta else 14.0) * u, onda=0.012 / u,
               vel=2.4 if tormenta else 1.0, listras=0.08, raios=0.0 if tormenta else 0.10, lis_prof=260 * u, **agua)
    for (X0, Y0, sub), nv_p in cascos:                                  # o casco aparece através da água
        tras = np.interp(np.arange(X0, X0 + sub.shape[1]) + 0.5, np.arange(W + 1), F) - 14 * u
        yy = np.arange(Y0, Y0 + sub.shape[0])[:, None] + 0.5
        m = (sub[..., 3] * (yy > tras[None, :]) * 0.42)[..., None]
        reg = q[Y0:Y0 + sub.shape[0], X0:X0 + sub.shape[1]]
        reg[:] = reg * (1 - m) + sub[..., :3] * m
        if nv_p.get("_afund", 0) > 0.02:                                # afundando: bolhas subindo do casco
            s = np.random.default_rng(11).random((40, 4))
            subida = (t * (60 + 50 * s[:, 2]) * u + s[:, 1] * 400 * u) % (380 * u)
            bx = nv_p["_xs"] + (s[:, 0] - 0.5) * nv_p["_larg"] * 0.7 + 6 * u * np.sin(t * 3 + s[:, 3] * 6)
            fundo_b = nivel + 40 * u + nv_p["_afund"] * nv_p["_alt"] * 0.8
            FX.particulas(q, bx, fundo_b - subida, (2.0 + 4.0 * s[:, 3]) * u, np.tile([[0.85, 0.97, 0.98]], (40, 1)),
                          0.55 * min(1.0, nv_p["_afund"] * 4) * (subida / (380 * u)))
        if nv_p.get("parado") or nv_p.get("_afund", 0) > 0.3:
            continue
        lado = -1 if nv_p.get("espelho") else 1
        bx = X0 + sub.shape[1] * (0.93 if lado > 0 else 0.07)          # espuma na proa
        by = float(np.interp(bx, np.arange(W + 1), F))
        s = np.random.default_rng(5).random((16, 3))
        fa = (t * 1.3 + s[:, 0]) % 1.0
        FX.particulas(q, bx + lado * fa * 46 * u * (0.5 + s[:, 1]), by - 3 * u - fa * 7 * u * s[:, 2], (1.5 + 2.5 * s[:, 2]) * u,
                      np.tile([[0.9, 0.98, 0.98]], (16, 1)), 0.9 * (1 - fa))
    if not tormenta:
        for i in range(7):                                              # cardume
            px = (W * (0.75 - 0.03 * i) - t * 40 * u + 60 * u * (i % 3)) % (W * 1.2) - W * 0.1
            py = H * (0.78 + 0.03 * math.sin(i * 1.7)) + 8 * u * math.sin(t * 1.2 + i)
            peixe(q, px, py, (16 + 4 * (i % 2)) * u, t, i, (0.08, 0.30, 0.40), 0.55)
    s = np.random.default_rng(3).random((70, 4))                       # partículas na água
    fundo_h = H - nivel - 40 * u
    xs_ = (s[:, 0] * W + t * 8 * u) % W
    ys_ = nivel + 40 * u + ((s[:, 1] * fundo_h + t * 6 * u * s[:, 2]) % fundo_h)
    FX.particulas(q, xs_, ys_, (1.0 + 1.5 * s[:, 3]) * u, np.tile([[0.7, 0.95, 0.95]], (70, 1)), 0.25 * s[:, 2])
    if tormenta:
        FX.chuva(q, t, u=u)
        for tr in (0.35, 0.78):                                          # relâmpagos
            dtr = t / max(dur, 1e-6) - tr
            if 0 <= dtr * dur < 0.35:
                k = math.exp(-dtr * dur * 9)
                q += 0.35 * k
                rnd = np.random.default_rng(int(tr * 100))
                x = W * rnd.uniform(0.2, 0.8)
                y = 0.0
                for _ in range(7):
                    nx, ny = x + rnd.uniform(-60, 60) * u, y + H * 0.07
                    FX.linha(q, (x, y), (nx, ny), largura=3.5 * u, cor=(0.85, 0.9, 1.0), forca=1.5 * k, brilho_w=8 * u)
                    x, y = nx, ny
    batalha = p.get("_batalha")
    if batalha:                                                          # tiros de canhão: clarão e fumaça
        for i, (fx_, fy_) in enumerate(batalha):
            fase = (t * 0.7 + i * 0.37) % 1.0
            if fase < 0.08:
                FX.brilho(q, fx_, fy_, 30 * u, cor=(1.0, 0.75, 0.35), forca=1.4 * (1 - fase / 0.08), nucleo=1.0)
            idade = fase
            FX.fumaca(q, [fx_ + idade * 90 * u * (1 if fx_ < W / 2 else -1) + j * 18 * u for j in range(4)],
                      [fy_ - idade * 40 * u - j * 6 * u for j in range(4)], [(18 + 60 * idade) * u] * 4, (0.92, 0.90, 0.86),
                      [0.55 * (1 - idade)] * 4)
    _etiquetas(q, p, t, dur, ctx["idioma"])


def mar_navio(q, t, dur, p, ctx):
    navios = []
    if p.get("navio", True):
        navios.append({"x": p.get("x", [0.14, 0.46]), "tam": p.get("tam_navio", 0.40), "nacao": p.get("nacao", "inglaterra"),
                       "inclina": p.get("inclina"), "afunda": p.get("afunda")})
    _mar(q, t, dur, p, ctx, navios)


def frota(q, t, dur, p, ctx):
    """Vários galeões: a Armada (bandeira espanha), navios presos no porto (parados) ou uma batalha (batalha=True)."""
    H, W = q.shape[:2]
    n = int(p.get("n", 7))
    rnd = np.random.default_rng(int(p.get("semente", 4)))
    navios = []
    if p.get("batalha"):
        navios = [{"x": (0.18, 0.24), "tam": 0.30, "nacao": "inglaterra"}, {"x": (0.05, 0.10), "tam": 0.22, "nacao": "inglaterra", "fundo": 0.3},
                  {"x": (0.80, 0.74), "tam": 0.36, "nacao": "franca", "espelho": True},
                  {"x": (0.95, 0.88), "tam": 0.28, "nacao": "franca", "espelho": True, "fundo": 0.3}]
        p = dict(p, ilha=False, _batalha=[(W * 0.30, H * 0.50), (W * 0.66, H * 0.50), (W * 0.24, H * 0.47), (W * 0.72, H * 0.46)])
    else:
        for i in range(n):
            longe = rnd.uniform(0.0, 0.9)
            x0 = (i + 0.5) / n + rnd.uniform(-0.04, 0.04)
            dx = 0.0 if p.get("parados") else 0.06
            navios.append({"x": (x0 - dx, x0 + dx), "tam": 0.34 * (1 - 0.55 * longe), "nacao": p.get("bandeira", "espanha"),
                           "fundo": longe, "parado": bool(p.get("parados")), "balanco": 0.6})
        p = dict(p, ilha=bool(p.get("parados")), ilha_x=-0.25)
    _mar(q, t, dur, p, ctx, navios)


@lru_cache(maxsize=6)
def _perfis_ilha(W, H, nivel_f):
    u = H / 1080
    nivel = H * nivel_f
    nuv = P.nuvens(W, H * 0.16, 4, (300 * u, 620 * u), (20 * u, 40 * u), semente=17, achatada=0.3, bolhas=(4, 8))
    nuv2 = P.nuvens(W, H * 0.34, 3, (240 * u, 420 * u), (14 * u, 26 * u), semente=23, achatada=0.3, bolhas=(4, 7))
    morros = P.morros(W, nivel - 2 * u, 90 * u, 420 * u, semente=21, oitavas=3)
    chao = P.ilha(W, -0.25 * W, 1.25 * W, nivel + 2 * u, 40 * u, semente=5, borda=0.06, escala=300 * u)
    flo_tras = P.floresta(W, chao - 14 * u, 170, (110 * u, 220 * u), 0.28, semente=31, copas=0.25)
    cerca, bordas = P.palicada(W, 0.36 * W, 0.64 * W, chao - 2 * u, 150 * u, 44, semente=3)
    arb = np.minimum(P.floresta(W, chao + 4 * u, 60, (34 * u, 80 * u), 0.55, semente=41, faixa=(-0.25 * W, 0.355 * W), copas=0.8),
                     P.floresta(W, chao + 4 * u, 60, (34 * u, 80 * u), 0.55, semente=43, faixa=(0.645 * W, 1.25 * W), copas=0.8))
    return nuv, nuv2, morros, flo_tras, cerca, bordas, arb, chao


PALETAS_ILHA = {
    "noite": dict(ceu=CEU_NOITE, lua=True, estrelas=True, luz=(0.76, 0.17),
                  nuvem=(0.11, 0.15, 0.28), nuvem_b=(0.13, 0.17, 0.30), nuvem_borda=(0.20, 0.24, 0.34),
                  morros=(0.17, 0.23, 0.35), morros_borda=(0.14, 0.16, 0.22), nevoa=(0.20, 0.26, 0.38), nevoa2=(0.16, 0.21, 0.32),
                  flo=(0.10, 0.16, 0.24), flo_b=(0.08, 0.13, 0.20), flo_borda=(0.24, 0.30, 0.44),
                  cerca=(0.40, 0.32, 0.27), cerca_b=(0.22, 0.18, 0.17), cerca_borda=(0.40, 0.42, 0.52), cerca_linha=(0.09, 0.07, 0.07),
                  arb=(0.06, 0.10, 0.15), arb_borda=(0.20, 0.26, 0.38), agua=AGUA_NOITE, nevoa_frente=(0.30, 0.36, 0.50),
                  vagalumes=True),
    "dia": dict(ceu=CEU_DIA, sol=True, luz=(0.78, 0.17),
                nuvem=(1.0, 0.97, 0.91), nuvem_b=(0.98, 0.93, 0.85), nuvem_borda=None, sombra_nuvem=True,
                morros=(0.62, 0.70, 0.64), morros_borda=(0.10, 0.10, 0.06), nevoa=(0.95, 0.92, 0.84), nevoa2=(0.93, 0.90, 0.82),
                flo=(0.36, 0.52, 0.44), flo_b=(0.30, 0.46, 0.38), flo_borda=(0.12, 0.12, 0.07),
                cerca=(0.62, 0.45, 0.30), cerca_b=(0.45, 0.32, 0.22), cerca_borda=(0.25, 0.22, 0.14), cerca_linha=(0.30, 0.20, 0.13),
                arb=(0.24, 0.42, 0.34), arb_borda=(0.10, 0.10, 0.06), agua=AGUA_DIA, nevoa_frente=(0.95, 0.92, 0.84)),
    "seca": dict(ceu=[(0.0, (0.93, 0.78, 0.52)), (0.6, (0.99, 0.88, 0.64)), (1.0, (0.99, 0.88, 0.64))], sol=True, luz=(0.70, 0.16),
                 nuvem=None, morros=(0.76, 0.66, 0.46), morros_borda=(0.12, 0.10, 0.05), nevoa=(0.98, 0.86, 0.62), nevoa2=(0.97, 0.85, 0.62),
                 flo=(0.58, 0.54, 0.32), flo_b=(0.52, 0.46, 0.28), flo_borda=(0.15, 0.12, 0.05),
                 cerca=(0.62, 0.45, 0.30), cerca_b=(0.45, 0.32, 0.22), cerca_borda=(0.25, 0.22, 0.14), cerca_linha=(0.30, 0.20, 0.13),
                 arb=(0.50, 0.44, 0.26), arb_borda=(0.15, 0.12, 0.05), nevoa_frente=(0.98, 0.86, 0.62),
                 agua=dict(clara=(0.64, 0.70, 0.56), corpo=(0.42, 0.50, 0.42), fundo=(0.18, 0.24, 0.22), brilho=(0.90, 0.92, 0.80),
                           lis_cor=(0.60, 0.66, 0.55), r_cor=(0.70, 0.72, 0.58))),
    "entardecer": dict(ceu=[(0.0, (0.20, 0.16, 0.32)), (0.42, (0.68, 0.38, 0.42)), (0.70, (0.98, 0.66, 0.44)), (1.0, (0.98, 0.66, 0.44))],
                       sol=True, sol_cor=(1.0, 0.86, 0.55), luz=(0.70, 0.62),
                       nuvem=(0.52, 0.30, 0.42), nuvem_b=(0.80, 0.46, 0.40), nuvem_borda=None,
                       morros=(0.42, 0.28, 0.40), morros_borda=(0.20, 0.10, 0.12), nevoa=(0.92, 0.58, 0.46), nevoa2=(0.80, 0.50, 0.46),
                       flo=(0.24, 0.16, 0.26), flo_b=(0.20, 0.13, 0.22), flo_borda=(0.55, 0.30, 0.25),
                       cerca=(0.34, 0.22, 0.22), cerca_b=(0.22, 0.14, 0.16), cerca_borda=(0.60, 0.34, 0.26), cerca_linha=(0.12, 0.07, 0.08),
                       arb=(0.14, 0.09, 0.15), arb_borda=(0.45, 0.25, 0.22), nevoa_frente=(0.85, 0.55, 0.48),
                       agua=dict(clara=(0.88, 0.62, 0.50), corpo=(0.40, 0.30, 0.42), fundo=(0.10, 0.08, 0.18), brilho=(1.0, 0.82, 0.62),
                                 lis_cor=(0.80, 0.55, 0.50), r_cor=(0.90, 0.60, 0.50))),
}


def ilha_noite(q, t, dur, p, ctx):
    """A ilha com a cerca de troncos. Paletas: noite (padrão), dia, seca, entardecer. Extras: fogo (x da fogueira),
    notas (música vindo do mar)."""
    H, W = q.shape[:2]
    u = H / 1080
    nome = "entardecer" if p.get("entardecer") else "seca" if p.get("seca") else "dia" if p.get("dia") else "noite"
    S = PALETAS_ILHA[nome]
    nivel_f = p.get("nivel", 0.74)
    nivel = H * nivel_f
    cam = _cam(p, t, dur, W, H, padrao_pan=(0.0, -15.0), cy=H * 0.60)
    c = P.Cena(q, cam, t, luz=S["luz"], semente=2)
    c.ceu(S["ceu"])
    lx, ly = c.luz_tela(0.0)
    if S.get("estrelas"):
        c.estrelas(n=420, ate=0.62, forca=0.9)
    if S.get("lua"):
        R = 46 * u * cam.escala(0)
        for r, cor, a in ((2.4, (0.20, 0.26, 0.42), 0.35), (1.65, (0.32, 0.38, 0.55), 0.35)):
            P._k_disco(q, float(lx), float(ly), float(R * r), np.array(cor, np.float32), c.tex, 0.0, 0.0, float(a))
        FX.brilho(q, lx, ly, R * 1.6, cor=(0.6, 0.7, 0.95), forca=0.22, nucleo=0.0)
        P._k_disco(q, float(lx), float(ly), float(R), np.array((0.96, 0.95, 0.88), np.float32), c.tex, 0.10, 0.12, 1.0)
    if S.get("sol"):
        sc = S.get("sol_cor", (1.0, 0.84, 0.48))
        for r, a in ((150, 0.22), (110, 0.32), (72, 1.0)):
            cor = tuple(min(1.0, x * (1.0 + 0.1 * (r > 72))) for x in sc)
            P._k_disco(q, float(lx), float(ly), float(r * u * cam.escala(0)), np.array(cor, np.float32), c.tex, 0.0, 0.0, float(a))
    nuv, nuv2, morros, flo_tras, cerca, bordas, arb, chao = _perfis_ilha(W, H, nivel_f)
    if S.get("nuvem") is not None:
        borda = (S["nuvem_borda"], 3 * u) if S.get("nuvem_borda") else None
        for lista, pp, dv in ((nuv, 0.02, 5.0), (nuv2, 0.04, 8.0)):
            if S.get("sombra_nuvem"):
                c.nuvens(lista, p=pp, deriva=t * dv * u - 6 * u, desloc=7 * u, cor=(0.84, 0.75, 0.63), alfa=0.5, tex_k=0.0)
            c.nuvens(lista, p=pp, deriva=t * dv * u, cor=S["nuvem"], cor_base=S["nuvem_b"], borda=borda, luz_k=0.3, tex_k=0.03)
    c.faixa(morros, None, p=0.08, cor=S["morros"], borda=(S["morros_borda"], 2 * u), luz_k=0.5, tex_k=0.04)
    c.nevoa(nivel - 30 * u, 26 * u, S["nevoa"], forca=0.55 if nome == "noite" else 0.35, p=0.1, vel=6)
    c.faixa(flo_tras, None, p=0.2, cor=S["flo"], cor_base=S["flo_b"], borda=(S["flo_borda"], 2.4 * u), luz_k=0.7, tex_k=0.05)
    c.nevoa(nivel - 60 * u, 18 * u, S["nevoa2"], forca=0.35 if nome == "noite" else 0.2, p=0.22, vel=9, semente_ox=40)
    if p.get("fogo") is not None:
        fx, fy = cam.ponto(W * float(p["fogo"]), nivel - 60 * u, 0.22)
        _fogueira(q, fx, fy, t, u * cam.escala(0.22), forca=1.0 if nome == "noite" else 0.6)
    c.faixa(cerca, None, p=0.24, cor=S["cerca"], cor_base=S["cerca_b"], ya=nivel - 150 * u, yb=nivel,
            borda=(S["cerca_borda"], 3.0 * u), luz_k=0.4, tex_k=0.10, tex_esc=1.5)
    c.linhas_v(bordas, 0.24, S["cerca_linha"], larg=2.0 * u, forca=0.75)
    ya = nivel - 2 * u - 150 * u * 0.55                                   # travessa da cerca
    a = cam.ponto(0.36 * W, ya, 0.24)
    b = cam.ponto(0.64 * W, ya, 0.24)
    FX.linha(q, a, b, largura=6 * u * cam.escala(0.24), cor=tuple(x * 0.6 for x in S["cerca_b"]), forca=0.9)
    c.faixa(arb, None, p=0.26, cor=S["arb"], borda=(S["arb_borda"], 2.2 * u), luz_k=0.6, tex_k=0.05)
    if S.get("vagalumes"):
        s = np.random.default_rng(9).random((40, 5))
        xw = s[:, 0] * W * 1.1 - W * 0.05 + 25 * u * np.sin(t * 0.5 + s[:, 1] * 6.28)
        yw = nivel - (15 + 170 * s[:, 2]) * u + 12 * u * np.sin(t * 0.8 + s[:, 3] * 6.28)
        xs, ys = cam.ponto(xw, yw, 0.28)
        pisca = np.clip(np.sin(t * (1.5 + s[:, 4]) + s[:, 1] * 6.28), 0, 1) ** 2
        FX.particulas(q, xs, ys, np.full(40, 3.0 * u), np.tile([[1.0, 0.86, 0.45]], (40, 1)), 1.6 * pisca)
        FX.particulas(q, xs, ys, np.full(40, 9.0 * u), np.tile([[1.0, 0.80, 0.40]], (40, 1)), 0.12 * pisca)
    ag = S["agua"]
    c.agua(nivel, p=0.3, crista=4.0 * u, faixa=10.0 * u, onda=0.012 / u, listras=0.05, raios=0.05 if nome == "noite" else 0.08,
           lis_prof=200 * u, **ag)
    c.nevoa(nivel - 8 * u, 14 * u, S["nevoa_frente"], forca=0.30 if nome == "noite" else 0.15, p=0.5, vel=12, semente_ox=90)
    if p.get("notas"):
        _notas(q, t, u)
    _etiquetas(q, p, t, dur, ctx["idioma"])


def _rota(d, pts, k, u, cor=(150, 46, 34, 255), barco=True):
    """Rota tracejada desenhada até a fração k, com um navio de mapa na ponta enquanto anda."""
    seg = np.hypot(*np.diff(pts, axis=0).T)
    acum = np.concatenate([[0], np.cumsum(seg)])
    fim = acum[-1] * k
    traco, vao = 12 * u, 9 * u
    pos = 0.0
    while pos < fim:
        a_, b_ = pos, min(pos + traco, fim)
        xa, ya = np.interp(a_, acum, pts[:, 0]), np.interp(a_, acum, pts[:, 1])
        xb, yb = np.interp(b_, acum, pts[:, 0]), np.interp(b_, acum, pts[:, 1])
        d.line([(xa, ya), (xb, yb)], fill=cor, width=max(2, int(3.4 * u)))
        pos += traco + vao
    if barco and 0 < k < 1:
        xh, yh = np.interp(fim, acum, pts[:, 0]), np.interp(fim, acum, pts[:, 1])
        lado = -1 if pts[-1, 0] < pts[0, 0] else 1
        _barquinho(d, xh, yh - 4 * u, 13 * u, lado)


def _estrela(d, x, y, r):
    """Estrela de quatro pontas, azul por fora e vermelha por dentro (o símbolo escondido no mapa de White)."""
    for raio, cor in ((r, (40, 70, 160, 255)), (r * 0.62, (196, 40, 40, 255))):
        pts = []
        for i in range(8):
            a = i * math.pi / 4
            rr = raio if i % 2 == 0 else raio * 0.36
            pts.append((x + math.cos(a) * rr, y - math.sin(a) * rr))
        d.polygon(pts, fill=cor)


def mapa(q, t, dur, p, ctx):
    H, W = q.shape[:2]
    u = H / 1080
    fundo(q, p.get("fundo", "mar_navio"), t + 4.0, dur, {"x": [0.30, 0.34], "zoom": 1.0, "pan": 0.0}, ctx, escuro=0.55)
    _poeira(q, t, n=60, cor=(1.0, 0.95, 0.85), forca=0.10)
    rot = tuple((a, b, L(c_, ctx["idioma"])) for a, b, c_ in (p.get("rotulos") or []))
    cw, ch = int(W * 0.52), int(H * 0.70)
    card, sombra, ms, (m0, iw, ih, bbox) = cartao_mapa(cw, ch, tuple(p.get("bbox", (-84.0, -66.0, 30.0, 42.5))), rot)
    lon0, lon1, lat0, lat1 = bbox
    tf = t / max(dur, 1e-6)

    def pr(lon, lat):
        return m0 + (lon - lon0) / (lon1 - lon0) * iw, m0 + (lat1 - lat) / (lat1 - lat0) * ih

    img = card.copy()
    d = ImageDraw.Draw(img)
    for chave, cor in (("rota", (150, 46, 34, 255)), ("rota2", (60, 80, 140, 255))):
        if p.get(chave):
            pts = np.array([pr(lo, la) for lo, la in _curva(*[tuple(x) for x in p[chave]], 60)])
            k = FX.suave(FX.entre(tf, *p.get(chave + "_t", [0.1, 0.7])))
            _rota(d, pts, k, u, cor)
            if chave == "rota" and p.get("risco_rota"):                  # X vermelho no fim da rota (não foram)
                kr = FX.entre(tf, *p["risco_rota"])
                if kr > 0:
                    x, y = pts[-1]
                    s = 22 * u
                    for j, (a_, b_) in enumerate((((x - s, y - s), (x + s, y + s)), ((x + s, y - s), (x - s, y + s)))):
                        kj = min(1.0, max(0.0, kr * 2 - j))
                        if kj > 0:
                            d.line([a_, (a_[0] + (b_[0] - a_[0]) * kj, a_[1] + (b_[1] - a_[1]) * kj)], fill=VERMELHO + (255,), width=max(3, int(6 * u)))
    if p.get("remendo"):                                                  # remendo de papel sobre a estrela escondida
        x, y = pr(*p["remendo"])
        a0, a1 = p.get("remendo_t", [0.3, 0.6])
        kr = 1.0 if a0 < 0 else FX.suave(FX.entre(tf, a0, a1))
        _estrela(d, x, y, 15 * u)
        if kr < 1:
            pedaco = cartao(int(46 * u), int(40 * u), 41, (226, 212, 180)).rotate(8 + 30 * kr, resample=Image.BICUBIC, expand=True)
            pedaco = _sombra(pedaco, raio=4, desloc=(2, 3 + int(10 * kr)), forca=0.5)
            if kr > 0:
                pedaco.putalpha(pedaco.getchannel("A").point(lambda v, a=1 - kr: int(v * a)))
            img.alpha_composite(pedaco, (int(x - pedaco.width / 2 + kr * 70 * u), int(y - pedaco.height / 2 - kr * 60 * u)))
    if p.get("pino"):
        x, y = pr(*p["pino"])
        _alfinete(img, x, y, L(p.get("rotulo", ""), ctx["idioma"]), u)
    if p.get("selo"):
        s_ = etiqueta(L(p["selo"], ctx["idioma"]), tam=34, estilo="vermelho", semente=9, rot=6)
        img.alpha_composite(s_, (int(img.width - s_.width - 6), 4))
    tudo = sombra.copy()
    tudo.alpha_composite(img, (ms, ms))
    tudo = tudo.rotate(-2.0, resample=Image.BICUBIC, expand=True)
    k = FX.sai(t / 0.6, 3)
    z = p.get("zoom", [1.0, 1.06])
    esc = FX.mistura(z[0], z[1], FX.suave(tf)) if isinstance(z, list) else z
    if p.get("remendo") and isinstance(z, list) and z[1] > 1.1:          # aproxima na direção da estrela
        x, y = pr(*p["remendo"])
        cx = W * 0.5 - (x + ms - tudo.width / 2) * (esc - 1) * 0.9
        cy = H * 0.52 - (y + ms - tudo.height / 2) * (esc - 1) * 0.9
    else:
        cx, cy = W * p.get("cx", 0.5), H * 0.52
    colar_img(q, tudo, cx, cy + (1 - k) * 40 * u, esc, min(1.0, k * 1.5))
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=24)
def _folha_cal(cw, ch, mes, dia, ano, semente=7):
    """Folha do calendário (RGBA): cabeçalho vermelho com o mês, dia grande, ano embaixo, argolas em cima."""
    c = cartao(cw, ch, semente).copy()
    d = ImageDraw.Draw(c)
    d.rectangle([10, 10 + ch * 0.06, cw + 10, 10 + ch * 0.24], fill=VERMELHO)
    d.text(((cw + 20) / 2, 10 + ch * 0.15), mes, font=fonte("ExtraBold", int(ch * 0.085)), fill=BRANCO, anchor="mm")
    d.text(((cw + 20) / 2, 10 + ch * 0.55), str(dia), font=fonte("Black", int(ch * 0.40)), fill=TINTA, anchor="mm")
    d.text(((cw + 20) / 2, 10 + ch * 0.87), str(ano), font=fonte("Bold", int(ch * 0.10)), fill=(110, 90, 66), anchor="mm")
    for fx in (0.3, 0.7):
        x = 10 + cw * fx
        d.ellipse([x - ch * 0.02, 10 + ch * 0.015, x + ch * 0.02, 10 + ch * 0.055], fill=(60, 52, 46))
    return c


def calendario(q, t, dur, p, ctx):
    H, W = q.shape[:2]
    u = H / 1080
    fundo(q, p.get("fundo", "mar_navio"), t + 6.0, dur, {"x": [0.36, 0.38], "zoom": 1.0, "pan": 0.0}, ctx, escuro=0.5)
    _poeira(q, t, n=60, cor=(1.0, 0.92, 0.78), forca=0.10)
    cw, ch = int(W * 0.26), int(H * 0.5)
    mes = L(p.get("mes", {"pt": "AGOSTO", "en": "AUGUST"}), ctx["idioma"])
    dia = p.get("dia", 18)
    a0, a1 = p.get("anos", [1587, 1590])
    t0, t1 = p.get("anos_t", [0.25, 0.6])
    pos = FX.mistura(a0, a1, FX.entre(t / max(dur, 1e-6), t0, t1))
    ano = int(math.floor(pos + 1e-6))
    f = pos - ano
    k = FX.sai(t / 0.5, 3)
    cx, cy = W * 0.5, H * 0.5 + (1 - k) * 40 * u
    pilha = cartao(cw, ch, 11)
    for i in (2, 1):                                                      # folhas de baixo (grossura do bloco)
        colar_img(q, _sombra(pilha.rotate(3, resample=Image.BICUBIC, expand=True), 10, (6, 10), 0.45), cx + 5 * i * u,
                  cy + 7 * i * u, alfa=min(1.0, k * 1.5))
    if f > 1e-3 and ano < a1:
        colar_img(q, _folha_cal(cw, ch, mes, dia, ano + 1).rotate(3, resample=Image.BICUBIC, expand=True), cx, cy, alfa=min(1.0, k * 1.5))
    topo = _folha_cal(cw, ch, mes, dia, ano)
    if f > 1e-3 and ano < a1:                                             # a folha de cima vira (presa em cima)
        fl = FX.entra(f, 2)
        hh = max(2, int(topo.height * (1 - fl)))
        dobra = topo.resize((topo.width, hh), Image.BILINEAR)
        sombra_k = 1 - 0.35 * fl
        dobra = Image.merge("RGBA", [*(ch_.point(lambda v, s=sombra_k: int(v * s)) for ch_ in dobra.split()[:3]), dobra.getchannel("A")])
        r = dobra.rotate(3, resample=Image.BICUBIC, expand=True)
        a = np.asarray(r, np.float32) / 255.0
        colar(q, a, cx - r.width / 2, cy - topo.height / 2 - 6 * u, alfa=min(1.0, k * 1.5))
    else:
        colar_img(q, _sombra(topo.rotate(3, resample=Image.BICUBIC, expand=True), 14, (8, 14), 0.55), cx, cy, alfa=min(1.0, k * 1.5))
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=2)
def _madeira(W, H, semente=4):
    """Troncos verticais lado a lado (float32), com veios, nós, rachaduras e frestas escuras entre eles."""
    rnd = np.random.default_rng(semente)
    larg = int(W / 7)
    img = np.zeros((H, W, 3), np.float32)
    xs = np.arange(W)
    ys = np.arange(H)[:, None]
    for i in range(-1, W // larg + 2):
        x0 = i * larg + rnd.integers(-10, 10)
        cor = np.array([118, 82, 54], np.float32) * rnd.uniform(0.85, 1.1)
        sel = (xs >= x0) & (xs < x0 + larg)
        if not sel.any():
            continue
        uu = (xs[sel] - x0) / larg
        cil = np.sin(np.pi * uu) ** 0.6
        veio = rnd.normal(size=(H // 60 + 2, sel.sum() // 3 + 2)).astype(np.float32)
        veio = np.asarray(Image.fromarray(veio).resize((sel.sum(), H), Image.BICUBIC))
        tom = cor[None, None, :] * (0.55 + 0.45 * cil)[None, :, None] * (1 + 0.12 * veio[..., None])
        for _ in range(2):                                                # nós
            ny, nx = rnd.uniform(0.1, 0.9) * H, rnd.uniform(0.3, 0.7)
            dn = ((ys - ny) / (0.03 * H)) ** 2 + ((uu[None, :] - nx) / 0.12) ** 2
            tom *= (1 - 0.35 * np.exp(-dn) + 0.1 * np.exp(-dn * 0.3))[..., None]
        img[:, sel] = tom
        fresta = (xs >= x0 - 3) & (xs < x0 + 3)
        img[:, fresta] *= 0.35
    return np.clip(img / 255.0, 0, 1)


@lru_cache(maxsize=2)
def _casca(W, H, semente=6):
    """Tronco de árvore de perto (float32): casca com sulcos verticais compridos e placas, sombra cilíndrica."""
    rnd = np.random.default_rng(semente)
    campo = np.zeros((H, W), np.float32)
    for (cy, cx), peso in (((10, 90), 1.0), ((24, 260), 0.5), ((60, 600), 0.25)):
        r = rnd.normal(size=(cy, cx)).astype(np.float32)
        campo += np.asarray(Image.fromarray(r).resize((W, H), Image.BICUBIC)) * peso
    sulco = np.clip(1 - np.abs(np.sin(campo * 2.2)) * 1.6, 0, 1) ** 2               # linhas escuras compridas
    xs = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    cil = np.cos(xs * 1.1) ** 0.8
    base = np.array([0.36, 0.28, 0.22], np.float32)
    img = base[None, None, :] * (0.75 + 0.18 * campo[..., None]) * (1 - 0.55 * sulco[..., None]) * cil[..., None]
    return np.clip(img, 0, 1)


@lru_cache(maxsize=24)
def _letras(palavra, n, W, H):
    """As n primeiras letras da palavra entalhada, só na faixa da palavra: (y0, x0, máscara, gx, gy, centro de cada
    letra)."""
    f = fonte("Black", int(H * 0.17))
    total = f.getlength(palavra)
    x = (W - total) / 2
    y0, y1 = int(H * 0.36), int(H * 0.64)
    x0, x1 = max(0, int(x - H * 0.03)), min(W, int(x + total + H * 0.03))
    k = 2
    m = Image.new("L", ((x1 - x0) * k, (y1 - y0) * k), 0)
    d = ImageDraw.Draw(m)
    fk = fonte("Black", int(H * 0.17) * k)
    pos = []
    for i, ch_ in enumerate(palavra):
        pos.append(x + f.getlength(ch_) / 2)
        if i < n:
            d.text(((x - x0) * k, (H * 0.5 - y0) * k), ch_, font=fk, fill=255, anchor="lm")
        x += f.getlength(ch_)
    m = np.asarray(m.resize((x1 - x0, y1 - y0), Image.BOX), np.float32) / 255.0
    bl = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(H * 0.006)), np.float32) / 255.0
    gy, gx = np.gradient(bl)
    return y0, x0, m, gx, gy, tuple(pos)


def entalhe(q, t, dur, p, ctx):
    H, W = q.shape[:2]
    u = H / 1080
    casca = bool(p.get("casca"))
    q[:] = _casca(W, H) if casca else _madeira(W, H)
    palavra = L(p.get("palavra", "CROATOAN"), ctx["idioma"])
    t0, t1 = p.get("letras_t", [0.1, 0.7])
    n = len(palavra)
    pronta = t0 < 0                                                       # letras já entalhadas desde o começo
    kk = 1.0 if pronta else FX.entre(t / max(dur, 1e-6), t0, t1)
    mostrar = int(math.ceil(kk * n)) if kk > 0 else 0
    y0, x0, m, gx, gy, pos = _letras(palavra, mostrar, W, H)
    if mostrar:
        reg = q[y0:y0 + m.shape[0], x0:x0 + m.shape[1]]
        luz = -(gx * 0.7 + gy * 0.7) * H * 0.012                          # parede do sulco virada pra luz (tocha à esquerda)
        parede = np.clip(luz, -1, 1)[..., None]
        if casca:                                                         # na casca, o corte mostra a madeira clara
            sulco = np.array([0.80, 0.64, 0.44], np.float32) * (0.82 + 0.18 * m[..., None]) * np.ones_like(reg)
            sulco += np.where(parede > 0, parede * 0.10, parede * 0.35)
        else:
            sulco = reg * 0.30 * (1 - 0.25 * m[..., None])
            sulco += np.where(parede > 0, parede * np.array([0.55, 0.40, 0.26], np.float32), parede * 0.10)
        reg[:] = reg * (1 - m[..., None]) + sulco * m[..., None]
        borda = np.clip(np.abs(gx) + np.abs(gy), 0, 1)[..., None] * (1 - m[..., None])
        reg += borda * H * 0.02 * np.array([0.10, 0.07, 0.04], np.float32)
    dur_l = (t1 - t0) * dur / max(1, n)                                  # lascas saindo de cada letra nova
    for i in range(0 if pronta else min(n, mostrar + 1)):
        te = (t0 * dur) + i * dur_l
        idade = t - te
        if 0 <= idade < 0.9:
            s = np.random.default_rng(100 + i).random((14, 4))
            vx = (s[:, 0] - 0.5) * 380 * u
            vy = -(120 + 260 * s[:, 1]) * u
            xs = pos[i] + vx * idade
            ys = H * 0.5 + vy * idade + 900 * u * idade ** 2
            FX.particulas(q, xs, ys, (1.5 + 2.5 * s[:, 2]) * u, np.tile([[0.75, 0.55, 0.35]], (14, 1)), np.full(14, 0.9 * (1 - idade / 0.9)))
    T = ctx.get("T", t)                                                   # luz de tocha que pisca, vinda da esquerda
    pisca = 0.85 + 0.1 * math.sin(T * 13) + 0.05 * math.sin(T * 31)
    ys, xs = np.ogrid[0:H, 0:W]
    d2 = ((xs - W * 0.18) / (W * 0.65)) ** 2 + ((ys - H * 0.55) / (H * 0.8)) ** 2
    luzt = np.exp(-d2 * 1.6).astype(np.float32) * pisca
    q *= (0.25 + 1.05 * luzt)[..., None] * np.array([1.0, 0.88, 0.7], np.float32)
    _poeira(q, t, n=70, cor=(1.0, 0.7, 0.35), forca=0.35, semente=5)
    z = p.get("zoom", [1.0, 1.04])
    s_ = FX.mistura(z[0], z[1], FX.suave(t / max(dur, 1e-6))) if isinstance(z, list) else z
    if abs(s_ - 1) > 1e-4:
        q[:] = FX.zoom(q, s_)
    _etiquetas(q, p, t, dur, ctx["idioma"])


def cruz(q, t, dur, p, ctx):
    """Cartão pregado na madeira com o sinal combinado. risco_t: quando a cruz é riscada (None = não risca);
    texto: o nome do lugar embaixo e a cruz em cima, que aparece em cruz_t. sinal=False (10/11/2026): sem a cruz, só
    o texto grande no meio do cartão (e o risco por cima dele), para quando a história não tem o sinal de Roanoke."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    q[:] = _madeira(W, H) * 0.38
    cw = int(H * 0.5)
    c = cartao(cw, cw, 12).copy()
    d = ImageDraw.Draw(c)
    texto = L(p.get("texto"), ctx["idioma"]) if p.get("texto") else ""
    cx, cy, r = (cw + 20) / 2, (cw + 20) / 2, cw * 0.3
    esc = 1.0
    if texto and not p.get("sinal", True):                               # só o texto, quebrado em até 3 linhas
        palavras, linhas = texto.split(), []
        for w_ in palavras:
            if linhas and len(linhas[-1]) + len(w_) + 1 <= 11:
                linhas[-1] += " " + w_
            else:
                linhas.append(w_)
        tam = int(cw * (0.15 if max(len(x) for x in linhas) <= 8 else 0.12))
        f = fonte("Black", tam)
        for j, ln in enumerate(linhas):
            d.text((cx, cy + (j - (len(linhas) - 1) / 2) * tam * 1.15), ln, font=f, fill=TINTA, anchor="mm")
        r = cw * 0.3
        esc = 0.0
    elif texto:
        f = fonte("Black", int(cw * 0.085))
        d.text((cx, cy + r * 0.95), texto, font=f, fill=TINTA, anchor="mm")
        cy, r = cy - r * 0.32, r * 0.62
        a0, a1 = p.get("cruz_t", [0.5, 0.65])
        esc = FX.sai(FX.entre(tf, a0, a1), 3)
    if esc > 0:
        for ang in range(0, 360, 90):                                     # cruz pátea (de Malta)
            a = math.radians(ang)
            ponta = [(cx + math.cos(a + s) * r * 1.05 * esc, cy - math.sin(a + s) * r * 1.05 * esc) for s in (-0.42, 0.42)]
            d.polygon([(cx, cy)] + ponta, fill=TINTA if not texto else VERMELHO)
    rt = p.get("risco_t", [0.35, 0.55])
    k = FX.entre(tf, *rt) if rt else 0.0
    if k > 0:                                                             # risco vermelho em duas pinceladas
        lw = int(cw * 0.05)
        for j, (a, b) in enumerate((((cx - r * 1.2, cy - r * 1.2), (cx + r * 1.2, cy + r * 1.2)),
                                    ((cx + r * 1.2, cy - r * 1.2), (cx - r * 1.2, cy + r * 1.2)))):
            kj = min(1.0, max(0.0, k * 2 - j))
            if kj <= 0:
                continue
            pts = [(a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s + math.sin(s * 9 + j) * cw * 0.006) for s in np.linspace(0, kj, 30)]
            d.line(pts, fill=VERMELHO, width=lw, joint="curve")
    prego = (cw + 20) / 2, 26
    d.ellipse([prego[0] - 9, prego[1] - 9, prego[0] + 9, prego[1] + 9], fill=(70, 66, 62))
    d.ellipse([prego[0] - 4, prego[1] - 6, prego[0] + 3, prego[1] + 1], fill=(150, 146, 140))
    colar_img(q, _sombra(c.rotate(-3, resample=Image.BICUBIC, expand=True), 14, (8, 14), 0.6), W * 0.5, H * 0.5)
    _poeira(q, t, n=60)
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=16)
def _icone(nome, tam):
    """Ícones chapados para a linha do tempo (RGBA)."""
    k = 3
    s = tam * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if nome == "navio":
        g = navio(int(tam * 1.0), 0)
        g = g.resize((tam * k, int(g.height * tam * k / g.width)), Image.LANCZOS)
        im.alpha_composite(g, (0, max(0, (s - g.height) // 2)))
    elif nome == "cerca":
        for i in range(9):
            x = s * (0.08 + i * 0.1)
            h = s * (0.55 + 0.08 * math.sin(i * 2.1))
            d.polygon([(x, s * 0.9), (x + s * 0.085, s * 0.9), (x + s * 0.085, s * 0.9 - h), (x + s * 0.0425, s * 0.9 - h - s * 0.08),
                       (x, s * 0.9 - h)], fill=(122, 92, 66), outline=(70, 52, 38))
        d.line([(s * 0.06, s * 0.6), (s * 0.96, s * 0.6)], fill=(70, 52, 38), width=int(s * 0.04))
    elif nome == "pergunta":
        d.ellipse([s * 0.1, s * 0.1, s * 0.9, s * 0.9], fill=VERMELHO)
        d.text((s * 0.5, s * 0.52), "?", font=fonte("Black", int(s * 0.62)), fill=BRANCO, anchor="mm")
    return im.resize((tam, tam), Image.LANCZOS)


def linha_tempo(q, t, dur, p, ctx):
    H, W = q.shape[:2]
    u = H / 1080
    fundo(q, p.get("fundo", "ilha_noite"), t + 3.0, dur, {"zoom": 1.0, "pan": 0.0}, ctx, escuro=0.55)
    _poeira(q, t, n=60, cor=(0.8, 0.9, 1.0), forca=0.10)
    marcos = p.get("marcos", [])
    x0, x1, y = W * 0.12, W * 0.88, H * 0.60
    k = FX.sai(FX.entre(t / max(dur, 1e-6), 0.0, 0.35), 2)
    if k > 0:                                                             # tira de papel
        tira = cartao(int((x1 - x0) * k) + 2, int(14 * u), 31, PAPEL)
        colar_img(q, tira, x0 + (x1 - x0) * k / 2, y)
    anos = [m["ano"] for m in marcos] or [0, 1]
    amin, amax = min(anos), max(anos)
    xs = {}
    for i, m in enumerate(marcos):
        f = m["x"] if m.get("x") is not None else (m["ano"] - amin) / max(1, amax - amin)
        mx = x0 + (x1 - x0) * f
        xs[i] = mx
        tm = float(m.get("em", 0.1 + 0.25 * i)) * dur
        if t < tm:
            continue
        kk = FX.sai((t - tm) / 0.3, 3)
        cor = (0.77, 0.24, 0.18) if m.get("destaque") else (0.94, 0.90, 0.80)
        FX.particulas(q, [mx], [y], [11 * u * kk], [cor], [3.0])
        poligono(q, [(mx + 12 * u * math.cos(a) * kk, y + 12 * u * math.sin(a) * kk) for a in np.linspace(0, 6.28, 20)], cor)
        e = etiqueta(str(m["ano"]), 44, "vermelho" if m.get("destaque") else "papel", 30 + i)
        colar_img(q, e, mx, y - 70 * u - (1 - kk) * 16 * u, u, min(1.0, kk * 2))
        if m.get("icone"):
            ic = _icone(m["icone"], int(110 * u))
            colar_img(q, ic, mx, y - 175 * u - (1 - kk) * 20 * u, 1.0, min(1.0, kk * 2))
        if m.get("texto"):
            e2 = etiqueta(L(m["texto"], ctx["idioma"]), 30, "papel", 40 + i)
            colar_img(q, e2, mx, y + 70 * u, u, min(1.0, kk * 2))
    arco = p.get("arco")
    if arco:                                                              # arco do intervalo (ex.: 1590 → hoje)
        i0, i1, em = arco
        ka = FX.sai(FX.entre(t / max(dur, 1e-6), em, em + 0.25), 2)
        if ka > 0 and i0 in xs and i1 in xs:
            a, b = xs[i0], xs[i1]
            pts = [(a + (b - a) * s, y - 32 * u - math.sin(math.pi * s) * 90 * u) for s in np.linspace(0, ka, 50)]
            for j in range(len(pts) - 1):
                if j % 3 != 2:
                    FX.linha(q, pts[j], pts[j + 1], largura=4 * u, cor=(0.95, 0.75, 0.22), forca=1.0)
    _etiquetas(q, p, t, dur, ctx["idioma"])


def titulo(q, t, dur, p, ctx):
    H, W = q.shape[:2]
    u = H / 1080
    fundo(q, p.get("fundo", "ilha_noite"), t + 8.0, dur, {"zoom": 1.0, "pan": 0.0}, ctx, escuro=0.65, borrao=1.2)
    _poeira(q, t, n=100, cor=(0.8, 0.9, 1.0), forca=0.14)
    cw, ch = int(W * 0.62), int(H * 0.42)
    c = cartao(cw, ch, 21).copy()
    d = ImageDraw.Draw(c)
    linhas = L(p.get("linhas", {"pt": ["O MISTÉRIO", "DE ROANOKE"]}), ctx["idioma"])
    f = fonte("Black", int(ch * 0.22))
    for i, ln in enumerate(linhas):
        d.text(((cw + 20) / 2, 10 + ch * (0.34 + 0.28 * i)), ln, font=f, fill=VERMELHO if i == len(linhas) - 1 else TINTA, anchor="mm")
    k = FX.sai(t / 0.6, 3)
    colar_img(q, _sombra(c.rotate(-1.5, resample=Image.BICUBIC, expand=True), 16, (8, 16), 0.6), W * 0.5,
              H * 0.48 + (1 - k) * 50 * u, 1.0, min(1.0, k * 1.5))
    _etiquetas(q, p, t, dur, ctx["idioma"])


# ------------------------------------------------------------------ cenas do documentário completo
@lru_cache(maxsize=8)
def _cartao_capitulo(cw, ch, parte, nome):
    """Cartão do capítulo já inclinado e com sombra (feito uma vez por capítulo)."""
    c = cartao(cw, ch, 25).copy()
    d = ImageDraw.Draw(c)
    cx = (cw + 20) / 2
    d.text((cx, 10 + ch * 0.30), parte, font=fonte("Bold", int(ch * 0.13)), fill=VERMELHO, anchor="mm")
    d.line([(cx - ch * 0.12, 10 + ch * 0.43), (cx + ch * 0.12, 10 + ch * 0.43)], fill=(150, 120, 90), width=3)
    f = fonte("Black", int(ch * 0.25))
    while f.size > 20 and f.getlength(nome) > cw * 0.9:
        f = fonte("Black", f.size - 4)
    d.text((cx, 10 + ch * 0.66), nome, font=f, fill=TINTA, anchor="mm")
    return _sombra(c.rotate(-1.5, resample=Image.BICUBIC, expand=True), 16, (8, 16), 0.6)


def capitulo(q, t, dur, p, ctx):
    """Cartão de capítulo: "PARTE 1" pequeno em vermelho e o nome grande, sobre uma cena desfocada."""
    H, W = q.shape[:2]
    u = H / 1080
    fundo(q, p.get("fundo", "ilha_noite"), t + 2.0, dur, {"zoom": 1.0, "pan": 0.0}, ctx, escuro=0.55)
    _poeira(q, t, n=80, cor=(1.0, 0.95, 0.85), forca=0.12)
    img = _cartao_capitulo(int(W * 0.46), int(H * 0.34), L(p.get("parte", "PARTE 1"), ctx["idioma"]), L(p.get("nome", ""), ctx["idioma"]))
    k = FX.sai(t / 0.6, 3)
    colar_img(q, img, W * 0.5, H * 0.5 + (1 - k) * 50 * u, 1.0 + 0.03 * FX.suave(t / max(dur, 1e-6)), min(1.0, k * 1.5))
    _etiquetas(q, p, t, dur, ctx["idioma"])


def _suavizar(pts, n=6):
    """Curva fechada Catmull-Rom passando pelos pontos (para um canto vivo, repita o ponto)."""
    m = len(pts)
    out = []
    for i in range(m):
        p0, p1, p2, p3 = pts[(i - 1) % m], pts[i], pts[(i + 1) % m], pts[(i + 2) % m]
        for k in range(n):
            s = k / n
            s2, s3 = s * s, s * s * s
            out.append(tuple(0.5 * (2 * p1[j] + (p2[j] - p0[j]) * s + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * s2
                                    + (3 * p1[j] - p0[j] - 3 * p2[j] + p3[j]) * s3) for j in (0, 1)))
    return out


def _silhueta(d, x0, y0, w, h, tipo, cor=(34, 28, 26)):
    """Silhueta de perfil (olhando para a direita) de um homem da era elisabetana: barba pontuda, gola de rufo e gibão;
    tipo "chapeu" (chapéu alto com pluma) ou "barba" (barba mais cheia e boina achatada). Grade de 0 a 100 na caixa."""
    P_ = lambda a, b: (x0 + a / 100 * w, y0 + b / 100 * h)                # noqa: E731
    lw = max(1, int(w * 0.004))
    corpo = [(16, 103), (19, 88), (27, 79), (39, 75), (52, 74.5), (65, 75.5), (76, 80), (83, 89), (86, 103)]
    d.polygon([P_(*p) for p in _suavizar(corpo, 6)], fill=cor)
    for i in range(4):                                                    # botões do gibão
        bx, by = P_(67 + i * 1.2, 82 + i * 5.5)
        r = w * 0.008
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=(176, 146, 96))
    cabeca = [(41, 67), (37, 58), (34.5, 49), (33.5, 40), (35, 31), (39.5, 23.5), (46.5, 18.5), (55, 16.5), (62, 18), (67, 22.5),
              (69.8, 28.5), (70.6, 33.5), (69.6, 36.6), (71.4, 40.2), (74.6, 45.2), (74.6, 45.2), (72.2, 46.6), (71.3, 47.3),
              (72.6, 49.0), (71.2, 50.6), (72.0, 52.3), (71.0, 53.8), (68.5, 58.5), (62.0, 62.0), (56.5, 66.0), (55.0, 70.0)]
    d.polygon([P_(*p) for p in _suavizar(cabeca, 5)], fill=cor)
    cx, cy, rx, ry = 52.5, 71.5, 22.0, 7.0                                # gola de rufo
    pts = []
    for i in range(96):
        a = i / 96 * 2 * math.pi
        k = 1 + 0.06 * abs(math.sin(a * 14))
        pts.append(P_(cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    d.polygon(pts, fill=(244, 237, 220), outline=(150, 128, 98))
    for i in range(28):
        a = i / 28 * 2 * math.pi
        d.line([P_(cx + math.cos(a) * rx * 0.45, cy + math.sin(a) * ry * 0.45), P_(cx + math.cos(a) * rx * 0.97, cy + math.sin(a) * ry * 0.97)],
               fill=(200, 186, 160), width=lw)
    if tipo == "chapeu":                                                  # barba pontuda, por cima da gola
        barba = [(71.0, 53.5), (72.2, 57.5), (70.8, 62.0), (67.8, 67.8), (67.8, 67.8), (63.5, 65.5), (60.5, 61.5), (63.0, 57.0), (67.5, 54.5)]
    else:
        barba = [(71.0, 53.5), (72.8, 58.0), (71.6, 63.5), (68.4, 70.0), (68.4, 70.0), (62.5, 67.5), (58.5, 62.0), (61.5, 56.5), (67.0, 54.0)]
    d.polygon([P_(*p) for p in _suavizar(barba, 5)], fill=cor)
    if tipo == "chapeu":
        pluma = [(46, 14), (40, 7), (31, 2.5), (22, 2), (17, 4.5), (25, 5.5), (33, 8), (41, 14.5)]
        d.polygon([P_(*p) for p in _suavizar(pluma, 5)], fill=(196, 172, 128))
        d.polygon([P_(42.5, 18), P_(45.5, 2.5), P_(65.5, 3.5), P_(67.5, 18)], fill=cor)                        # copa
        d.ellipse([*P_(35, 15.8), *P_(75.5, 21.2)], fill=cor)                                                   # aba
        d.polygon([P_(43.6, 13.5), P_(66.6, 13.5), P_(66.9, 16), P_(43.2, 16)], fill=(160, 128, 76))          # fita
    else:
        boina = [(29.5, 21.5), (31, 16), (39, 11.5), (51, 9.5), (63, 10.5), (71.5, 14), (74, 18.5), (71, 21), (60, 20), (48, 20.5), (37, 22.5)]
        d.polygon([P_(*p) for p in _suavizar(boina, 5)], fill=cor)
        bx, by = P_(68.5, 16.5)
        r = w * 0.012
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=(196, 160, 90))                                         # broche


@lru_cache(maxsize=8)
def _camafeu(lado, tipo, semente=27):
    """Cartão com moldura oval e a silhueta dentro (RGBA, sem sombra)."""
    k = 2
    c = cartao(lado, int(lado * 1.22), semente).copy()
    W2, H2 = c.width * k, c.height * k
    camada = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    m = W2 * 0.10
    d.ellipse([m, m, W2 - m, H2 - m], fill=(236, 224, 198, 255), outline=(140, 104, 62, 255), width=int(W2 * 0.018))
    d.ellipse([m * 1.35, m * 1.35, W2 - m * 1.35, H2 - m * 1.35], outline=(176, 140, 92, 255), width=int(W2 * 0.006))
    oval = Image.new("L", (W2, H2), 0)
    ImageDraw.Draw(oval).ellipse([m * 1.4, m * 1.4, W2 - m * 1.4, H2 - m * 1.4], fill=255)
    sil = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    b = W2 * 0.84
    _silhueta(ImageDraw.Draw(sil), (W2 - b) / 2 - W2 * 0.03, H2 * 0.5 - b * 0.42, b, b, tipo)
    sil.putalpha(Image.fromarray(np.minimum(np.asarray(sil.getchannel("A")), np.asarray(oval))))
    camada.alpha_composite(sil)
    c.alpha_composite(camada.resize((c.width, c.height), Image.LANCZOS))
    return c


@lru_cache(maxsize=8)
def _camafeu_sombra(lado, tipo):
    return _sombra(_camafeu(lado, tipo).rotate(2, resample=Image.BICUBIC, expand=True), 16, (8, 16), 0.6)


def retrato(q, t, dur, p, ctx):
    """Camafeu com o perfil de uma figura histórica (silhueta, não é um retrato fiel), nome e ano."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    fundo(q, p.get("fundo", "mar_navio"), t + 1.0, dur, {"navio": False, "zoom": 1.0, "pan": 0.0}, ctx, escuro=0.5)
    _poeira(q, t, n=70, cor=(1.0, 0.95, 0.85), forca=0.12)
    cam = _camafeu_sombra(int(H * 0.46), p.get("tipo", "barba"))
    apaga = p.get("apaga")
    alfa = 1.0
    if apaga:
        alfa = 1.0 - 0.75 * FX.suave(FX.entre(tf, *apaga))
    k = FX.sai(t / 0.6, 3)
    colar_img(q, cam, W * 0.5, H * 0.47 + (1 - k) * 40 * u, 1.0 + 0.04 * FX.suave(tf), min(1.0, k * 1.5) * alfa)
    e = etiqueta(L(p.get("nome", ""), ctx["idioma"]), 52, "papel", 61, -2.0)
    colar_img(q, e, W * 0.5, H * 0.86 + (1 - k) * 20 * u, u, min(1.0, k * 2))
    if p.get("ano"):
        ka = FX.sai(FX.entre(tf, 0.25, 0.4), 3)
        if ka > 0:
            e2 = etiqueta(L(p["ano"], ctx["idioma"]), 40, "amarelo", 62, 4.0)
            colar_img(q, e2, W * 0.70, H * 0.17 + (1 - ka) * 16 * u, (0.85 + 0.15 * ka) * u, min(1.0, ka * 2))
    _etiquetas(q, p, t, dur, ctx["idioma"])


PELES = [(238, 202, 172), (230, 190, 158), (219, 174, 140)]


CABELOS = [(64, 44, 30), (102, 70, 44), (186, 148, 90), (40, 32, 28)]


ROUPAS = [(116, 80, 56), (128, 58, 50), (78, 86, 104), (108, 98, 68), (66, 62, 64), (146, 112, 70)]


@lru_cache(maxsize=48)
def _colono_img(tipo, h, semente, chapeu=False):
    """Colono de frente, chapado (RGBA, já com a sombra no chão): homem (gibão, calções bufantes, meias), mulher
    (vestido longo, avental, touca), menino ou menina (cabeça proporcionalmente maior). O chão fica na base da imagem."""
    rnd = np.random.default_rng(semente)
    k = 3
    A = h * k                                                             # altura da pessoa em pixels (×k)
    topo = 0.14                                                           # folga em cima para o chapéu
    W_, H_ = int(A * 0.62), int(A * (1 + topo + 0.02))
    im = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P_ = lambda a, b: (W_ / 2 + a * A, (b + topo) * A)                     # noqa: E731
    E_ = lambda x0, y0, x1, y1: [*P_(x0, y0), *P_(x1, y1)]                # noqa: E731
    esc = lambda c, f: tuple(int(v * f) for v in c)                       # noqa: E731
    pele = PELES[rnd.integers(len(PELES))]
    cabelo = CABELOS[rnd.integers(len(CABELOS))]
    roupa = ROUPAS[rnd.integers(len(ROUPAS))]
    roupa2 = ROUPAS[rnd.integers(len(ROUPAS))]
    meia = ((206, 196, 176), (84, 76, 70), (150, 140, 120))[rnd.integers(3)]
    branco = (240, 236, 224)
    crianca = tipo in ("menino", "menina")
    mulher = tipo in ("mulher", "menina")
    rc = 0.088 if crianca else 0.066                                      # raio da cabeça
    yc = rc + 0.01
    om = 0.12 if crianca else 0.125                                       # meia largura dos ombros
    yo = yc + rc + 0.035                                                  # altura dos ombros
    d.ellipse(E_(-0.2, 0.975, 0.2, 1.015), fill=(0, 0, 0, 55))            # sombra no chão
    if mulher:
        d.polygon([P_(-0.10, 0.45), P_(0.10, 0.45), P_(0.23, 0.99), P_(-0.23, 0.99)], fill=roupa)                    # saia
        if not crianca:
            d.polygon([P_(-0.07, 0.47), P_(0.07, 0.47), P_(0.095, 0.88), P_(-0.095, 0.88)], fill=branco)            # avental
        d.polygon([P_(-om * 0.85, yo), P_(om * 0.85, yo), P_(0.095, 0.47), P_(-0.095, 0.47)], fill=roupa2)          # corpete
        d.polygon([P_(-0.075, yo - 0.005), P_(0.075, yo - 0.005), P_(0.0, yo + 0.075)], fill=branco)                # gola
        braco = esc(roupa2, 0.8)
    else:
        for s_ in (-1, 1):                                                                                            # meias e sapatos
            d.polygon([P_(s_ * 0.022, 0.62), P_(s_ * 0.080, 0.62), P_(s_ * 0.070, 0.965), P_(s_ * 0.036, 0.965)], fill=meia)
            d.ellipse(E_(s_ * 0.054 - 0.042, 0.95, s_ * 0.054 + 0.042, 0.995) if s_ < 0 else E_(0.054 - 0.042, 0.95, 0.054 + 0.042, 0.995),
                      fill=(44, 34, 30))
        d.ellipse(E_(-0.13, 0.45, 0.13, 0.68), fill=esc(roupa, 0.82))                                                # calções bufantes
        d.polygon([P_(-om, yo), P_(om, yo), P_(0.11, 0.50), P_(0.0, 0.555), P_(-0.11, 0.50)], fill=roupa)            # gibão
        for j in range(4):
            bx, by = P_(0.0, yo + 0.05 + j * 0.085)
            d.ellipse([bx - A * 0.008, by - A * 0.008, bx + A * 0.008, by + A * 0.008], fill=esc(roupa, 0.6))
        d.ellipse(E_(-0.075, yo - 0.03, 0.075, yo + 0.012), fill=branco)                                             # gola
        braco = esc(roupa, 0.8)
    for s_ in (-1, 1):                                                                                                # braços e mãos
        x_o = s_ * om
        d.polygon([P_(x_o - s_ * 0.045, yo + 0.005), P_(x_o + s_ * 0.005, yo + 0.005), P_(x_o + s_ * 0.012, 0.52),
                   P_(x_o - s_ * 0.030, 0.52)], fill=braco)
        hx, hy = P_(x_o - s_ * 0.008, 0.535)
        rh = A * 0.022
        d.ellipse([hx - rh, hy - rh, hx + rh, hy + rh], fill=pele)
    d.rectangle(E_(-0.024, yc + rc * 0.6, 0.024, yo + 0.005), fill=esc(pele, 0.9))                                   # pescoço
    d.ellipse(E_(-rc, yc - rc, rc, yc + rc), fill=pele)                                                              # cabeça
    if mulher:                                                                                                        # touca
        d.chord(E_(-rc * 1.14, yc - rc * 1.18, rc * 1.14, yc + rc * 0.85), 175, 365, fill=branco)
        for s_ in (-1, 1):
            d.rectangle(E_(min(s_ * rc * 1.12, s_ * rc * 0.86), yc - rc * 0.1, max(s_ * rc * 1.12, s_ * rc * 0.86), yc + rc * 0.75),
                        fill=branco)
    else:
        d.chord(E_(-rc * 1.07, yc - rc * 1.14, rc * 1.07, yc + rc * 0.95), 192, 348, fill=cabelo)                    # cabelo
        if not crianca and rnd.random() < 0.6:
            d.chord(E_(-rc * 1.03, yc - rc * 1.03, rc * 1.03, yc + rc * 1.03), 12, 168, fill=cabelo)                 # barba
        if chapeu:
            d.ellipse(E_(-rc * 1.65, yc - rc * 1.02, rc * 1.65, yc - rc * 0.62), fill=(42, 36, 32))                  # aba
            d.polygon([P_(-rc * 0.95, yc - rc * 0.8), P_(rc * 0.95, yc - rc * 0.8), P_(rc * 0.78, yc - rc * 2.55),
                       P_(-rc * 0.78, yc - rc * 2.55)], fill=(42, 36, 32))                                               # copa
            d.rectangle(E_(-rc * 0.93, yc - rc * 1.15, rc * 0.93, yc - rc * 0.98), fill=(120, 96, 60))               # fita
    return im.resize((W_ // k, H_ // k), Image.LANCZOS)


def colonos(q, t, dur, p, ctx):
    """Praia com o grupo de colonos (homens, mulheres e crianças) aparecendo um a um; o navio ao fundo."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    _mar(q, t, dur, {"ilha": False, "zoom": [1.0, 1.03], "pan": [0, -10], "nivel": 0.56}, dict(ctx),
         [{"x": (0.80, 0.84), "tam": 0.22, "fundo": 0.45, "parado": True, "balanco": 0.5}])
    areia = H * 0.74
    xs = np.arange(W, dtype=np.float32)
    borda = areia + 5 * u * np.sin(xs / W * 9 + t * 0.9) + 3 * u * np.sin(xs / W * 23 - t * 1.4)
    ys = np.arange(H, dtype=np.float32)[:, None]
    m = np.clip(ys - borda[None, :] + 0.5, 0, 1)[..., None]
    prof = np.clip((ys - areia) / (H - areia), 0, 1)[..., None]
    cor_areia = np.array([0.90, 0.80, 0.62], np.float32) * (1 - 0.12 * prof)
    espuma = np.clip(1 - np.abs(ys - borda[None, :] - 3 * u) / (3 * u), 0, 1)[..., None] * 0.8
    q[:] = q * (1 - m) + (cor_areia * (1 - espuma) + np.array([0.98, 0.97, 0.92], np.float32) * espuma) * m
    grupo = ["homem", "mulher", "menina", "homem", "mulher", "homem", "menino", "mulher", "homem", "menino", "mulher", "homem",
             "menina", "homem"]
    n = len(grupo)
    rnd = np.random.default_rng(int(p.get("semente", 12)))
    dxs, escs = rnd.uniform(-14, 14, n), rnd.uniform(0.94, 1.05, n)
    ordem = sorted(range(n), key=lambda i: i % 3)                         # de trás para a frente
    for i in ordem:
        tipo = grupo[i]
        ti = 0.05 + 0.5 * i / n
        if tf < ti:
            continue
        kk = FX.sai((tf - ti) * dur / 0.35, 3)
        prof_i = i % 3                                                    # 0 = atrás (menor), 2 = na frente
        x = W * (0.08 + 0.84 * (i + 0.5) / n) + dxs[i] * u
        base = areia + (34 + 46 * prof_i) * u
        alt = (0.27 if tipo == "homem" else 0.255 if tipo == "mulher" else 0.17) * (0.9 + 0.06 * prof_i) * escs[i]
        img = _colono_img(tipo, max(8, int(H * alt)), 100 + i, tipo == "homem" and i % 2 == 0)
        colar(q, _np(img), x - img.width / 2, base - img.height + (1 - kk) * 26 * u, min(1.0, kk * 1.5))
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=16)
def _bau_img(lado, semente):
    """Baú de madeira aberto e revirado (RGBA): a tampa aberta para trás, papéis, um livro rasgado ou um capacete
    enferrujado saindo de dentro."""
    k = 2
    s = lado * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = np.random.default_rng(semente)
    mad, mad_e, ferro = (128, 84, 50), (90, 58, 35), (70, 62, 56)
    d.polygon([(s * 0.17, s * 0.37), (s * 0.83, s * 0.37), (s * 0.88, s * 0.10), (s * 0.12, s * 0.10)], fill=mad_e)      # tampa
    for x in (0.27, 0.73):
        xt = x + (x - 0.5) * 0.2
        d.polygon([(s * (x - 0.02), s * 0.37), (s * (x + 0.02), s * 0.37), (s * (xt + 0.022), s * 0.10), (s * (xt - 0.022), s * 0.10)],
                  fill=ferro)
    d.polygon([(s * 0.17, s * 0.37), (s * 0.83, s * 0.37), (s * 0.86, s * 0.45), (s * 0.14, s * 0.45)], fill=(38, 25, 17))  # dentro
    for _ in range(3):                                                                                                 # papéis
        x, y = rnd.uniform(0.24, 0.70), rnd.uniform(0.33, 0.40)
        a = rnd.uniform(-0.6, 0.6)
        w_, h_ = s * 0.14, s * 0.10
        cx, cy = s * x, s * y
        pts = [(cx + math.cos(a) * dx - math.sin(a) * dy, cy + math.sin(a) * dx + math.cos(a) * dy) for dx, dy in
               ((-w_ / 2, -h_ / 2), (w_ / 2, -h_ / 2), (w_ / 2, h_ / 2), (-w_ / 2, h_ / 2))]
        d.polygon(pts, fill=(236, 228, 204), outline=(176, 166, 136))
    if semente % 2 == 0:                                                                                               # livro rasgado
        d.polygon([(s * 0.30, s * 0.40), (s * 0.52, s * 0.31), (s * 0.57, s * 0.42), (s * 0.35, s * 0.50)], fill=(112, 42, 32))
        d.polygon([(s * 0.33, s * 0.40), (s * 0.52, s * 0.33), (s * 0.55, s * 0.41), (s * 0.36, s * 0.47)], fill=(234, 224, 198))
        d.line([(s * 0.42, s * 0.36), (s * 0.45, s * 0.44)], fill=(150, 140, 120), width=max(1, s // 200))
    else:                                                                                                              # capacete
        d.pieslice([s * 0.50, s * 0.27, s * 0.78, s * 0.55], 180, 360, fill=(150, 84, 40))
        d.polygon([(s * 0.46, s * 0.41), (s * 0.82, s * 0.41), (s * 0.78, s * 0.445), (s * 0.50, s * 0.445)], fill=(128, 70, 34))
        d.line([(s * 0.64, s * 0.25), (s * 0.64, s * 0.29)], fill=(120, 64, 30), width=int(s * 0.03))
        for _ in range(10):
            x, y = rnd.uniform(0.53, 0.75), rnd.uniform(0.32, 0.40)
            d.ellipse([s * x, s * y, s * (x + 0.02), s * (y + 0.015)], fill=(184, 104, 52))                            # ferrugem
    d.rectangle([s * 0.14, s * 0.45, s * 0.86, s * 0.86], fill=mad)                                                    # frente
    d.rectangle([s * 0.14, s * 0.45, s * 0.86, s * 0.47], fill=(150, 102, 64))
    for y in (0.60, 0.73):
        d.line([(s * 0.14, s * y), (s * 0.86, s * y)], fill=mad_e, width=int(s * 0.012))
    for x in (0.22, 0.78):
        d.rectangle([s * (x - 0.025), s * 0.45, s * (x + 0.025), s * 0.86], fill=ferro)                                # ferragens
    d.rectangle([s * 0.46, s * 0.50, s * 0.54, s * 0.60], fill=ferro)                                                  # fechadura
    d.polygon([(s * 0.47, s * 0.60), (s * 0.53, s * 0.60), (s * 0.56, s * 0.66), (s * 0.50, s * 0.64)], fill=(56, 50, 46))  # arrombada
    return im.resize((lado, lado), Image.LANCZOS)


def baus(q, t, dur, p, ctx):
    """Cinco baús enterrados e arrombados na areia da vila, aparecendo um a um, com papéis voando."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    fundo(q, "ilha_noite", t, dur, {"dia": True, "zoom": 1.0, "pan": 0.0}, ctx, escuro=0.85, borrao=2.5)
    chao = H * 0.58
    ys = np.linspace(0, 1, H - int(chao), dtype=np.float32)[:, None, None]
    q[int(chao):] = np.array([0.80, 0.68, 0.50], np.float32) * (1 - 0.25 * ys)
    tex = P.textura(5)
    q[int(chao):] *= (1 + 0.05 * np.asarray(Image.fromarray(tex).resize((W, H - int(chao)), Image.BILINEAR)))[..., None]
    for i, (bx, by, esc) in enumerate(((0.16, 0.74, 0.9), (0.33, 0.84, 1.05), (0.50, 0.72, 0.85), (0.67, 0.86, 1.1), (0.84, 0.74, 0.92))):
        ti = 0.05 + 0.13 * i
        if tf < ti:
            continue
        kk = FX.sai((tf - ti) * dur / 0.4, 3)
        img = _bau_img(int(H * 0.30 * esc), i)
        poligono(q, [(W * bx + math.cos(a) * img.width * 0.48, H * by + img.height * 0.36 + math.sin(a) * img.height * 0.08)
                     for a in np.linspace(0, 6.28, 24)], (0.55, 0.44, 0.30), 0.6 * kk)                                    # buraco
        colar_img(q, img, W * bx, H * by + (1 - kk) * 30 * u, 1.0, min(1.0, kk * 1.5))
    s = np.random.default_rng(8).random((10, 4))                                                                          # papéis no vento
    for j in range(10):
        k = (t * 0.12 + s[j, 0]) % 1.0
        x = W * (0.1 + 0.8 * s[j, 1]) + k * W * 0.25
        y = H * (0.75 - 0.5 * k) + 40 * u * math.sin(t * 2 + j)
        a = t * (1 + s[j, 2]) + j
        w_, h_ = 26 * u, 20 * u
        pts = [(x + math.cos(a) * dx - math.sin(a) * dy * 0.6, y + math.sin(a) * dx + math.cos(a) * dy * 0.6) for dx, dy in
               ((-w_, -h_), (w_, -h_), (w_, h_), (-w_, h_))]
        poligono(q, pts, (0.94, 0.91, 0.82), 0.85 * min(1.0, k * 6) * (1 - k))
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=2)
def _solo(W, H, semente=9):
    """Corte do solo: céu de papel, grama e camadas de terra com bordas onduladas (float32) e as alturas das camadas."""
    u = H / 1080
    img = np.empty((H, W, 3), np.float32)
    img[:] = np.array([0.95, 0.89, 0.79], np.float32)
    xs = np.arange(W)
    rnd = np.random.default_rng(semente)
    camadas = [(0.30, (0.40, 0.56, 0.32)), (0.33, (0.36, 0.26, 0.18)), (0.50, (0.78, 0.66, 0.46)), (0.66, (0.62, 0.42, 0.28)),
               (0.82, (0.50, 0.40, 0.32)), (1.10, (0.40, 0.33, 0.28))]
    ys = np.arange(H)[:, None]
    alturas = []
    for j, (yf, cor) in enumerate(camadas):
        borda = H * yf + 10 * u * np.sin(xs / W * 6.28 * rnd.uniform(1, 3) + rnd.uniform(0, 6)) + 5 * u * np.sin(xs / W * 40 + j)
        alturas.append(float(np.mean(borda)))
        sel = ys >= borda[None, :]
        img[sel] = np.array(cor, np.float32)
    tex = P.textura(7)
    img *= (1 + 0.06 * np.asarray(Image.fromarray(tex).resize((W, H), Image.BILINEAR)))[..., None]
    for _ in range(int(220 * W / 1920)):                                                                      # pedrinhas
        x, y = rnd.uniform(0, W), rnd.uniform(H * 0.36, H)
        r = rnd.uniform(2, 6) * u
        y0, y1, x0, x1 = int(max(0, y - r)), int(min(H, y + r)), int(max(0, x - r)), int(min(W, x + r))
        img[y0:y1, x0:x1] *= 0.82
    return np.clip(img, 0, 1), tuple(alturas)


def _achado(q, nome, x, y, s, alfa):
    """Objetos achados na escavação, chapados."""
    metal, metal_e = (0.42, 0.40, 0.38), (0.26, 0.24, 0.23)
    if nome == "espada":                                                   # punho de rapieira: cabo, guarda, arco e pomo
        poligono(q, [(x - s * 0.9, y - s * 0.08), (x + s * 0.9, y - s * 0.08), (x + s * 0.9, y + s * 0.08), (x - s * 0.9, y + s * 0.08)], metal, alfa)
        poligono(q, [(x + s * 0.9, y - s * 0.12), (x + s * 1.5, y - s * 0.10), (x + s * 1.5, y + s * 0.10), (x + s * 0.9, y + s * 0.12)], (0.40, 0.28, 0.18), alfa)
        poligono(q, [(x + s * 1.65 + math.cos(a) * s * 0.17, y + math.sin(a) * s * 0.17) for a in np.linspace(0, 6.28, 16)], metal, alfa)
        poligono(q, [(x + s * 0.82, y - s * 0.6), (x + s * 0.92, y - s * 0.6), (x + s * 0.92, y + s * 0.6), (x + s * 0.82, y + s * 0.6)], metal_e, alfa)
        arco = [(x + s * (0.9 + 0.35 * math.sin(a)), y - s * 0.55 * math.cos(a)) for a in np.linspace(0, math.pi, 14)]
        for (ax, ay), (bx, by) in zip(arco, arco[1:]):
            FX.linha(q, (ax, ay), (bx, by), largura=s * 0.07, cor=metal_e, forca=alfa)
    elif nome == "arma":                                                   # pedaço de fecho de arma
        poligono(q, [(x - s, y - s * 0.15), (x + s * 0.6, y - s * 0.15), (x + s * 0.6, y + s * 0.15), (x - s, y + s * 0.15)], metal_e, alfa)
        poligono(q, [(x + s * 0.2, y + s * 0.15), (x + s * 0.4, y + s * 0.15), (x + s * 0.3, y + s * 0.5)], metal_e, alfa)
    elif nome == "metal":
        rnd = np.random.default_rng(int(x))
        for _ in range(4):
            cx, cy = x + rnd.uniform(-s, s), y + rnd.uniform(-s * 0.3, s * 0.3)
            poligono(q, [(cx + math.cos(a) * s * rnd.uniform(0.12, 0.25), cy + math.sin(a) * s * rnd.uniform(0.08, 0.18)) for a in np.linspace(0, 6.28, 7)],
                     (0.52, 0.36, 0.24), alfa)
    elif nome == "ceramica":                                               # cacos de cerâmica vidrada
        rnd = np.random.default_rng(int(y))
        for j in range(5):
            cx, cy = x + (j - 2) * s * 0.55, y + rnd.uniform(-s * 0.2, s * 0.2)
            r = s * rnd.uniform(0.25, 0.4)
            pts = [(cx + math.cos(a) * r * rnd.uniform(0.7, 1.2), cy + math.sin(a) * r * 0.6 * rnd.uniform(0.7, 1.2)) for a in np.linspace(0, 6.28, 6)]
            poligono(q, pts, (0.62, 0.52, 0.30) if j % 2 else (0.48, 0.56, 0.36), alfa)


def escavacao(q, t, dur, p, ctx):
    """Corte de uma escavação arqueológica: camadas de terra, a vala com a grade de barbante e os achados aparecendo
    (sempre na mesma camada); camadas=True marca a idade das camadas."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    solo, alturas = _solo(W, H)
    q[:] = solo
    x0, x1, y0, y1 = W * 0.22, W * 0.78, alturas[1], H * 0.80
    q[int(y0):int(y1), int(x0):int(x1)] *= 0.84                                                           # a vala
    for a, b in (((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)), ((x0, y1), (x1, y1))):
        FX.linha(q, a, b, largura=3 * u, cor=(0.20, 0.14, 0.10), forca=0.8)
    for i in range(7):                                                                                     # grade de barbante
        x = x0 + (x1 - x0) * i / 6
        FX.linha(q, (x, y0 - 30 * u), (x, y0 + 4 * u), largura=4 * u, cor=(0.55, 0.40, 0.25), forca=1.0)
        FX.linha(q, (x, y0), (x, y1), largura=1.6 * u, cor=(0.96, 0.95, 0.90), forca=0.5)
    for j in range(4):
        y = y0 + (y1 - y0) * j / 3
        FX.linha(q, (x0, y), (x1, y), largura=1.6 * u, cor=(0.96, 0.95, 0.90), forca=0.5)
    camada_y = (alturas[2] + alturas[3]) / 2
    if p.get("camadas"):                                                   # a camada do achado é a mais nova
        kc = FX.suave(FX.entre(tf, 0.1, 0.3))
        for yb in (alturas[2], alturas[3], alturas[4]):
            FX.linha(q, (0, yb), (W, yb), largura=3 * u, cor=(0.98, 0.96, 0.90), forca=0.8 * kc, tracos=22 * u)
    achados = p.get("achados", ["espada"])
    for i, nome in enumerate(achados):
        ti = 0.1 + 0.2 * i
        kk = FX.sai(FX.entre(tf, ti, ti + 0.25), 2)
        if kk <= 0:
            continue
        x = W * (0.36 + 0.28 * i / max(1, len(achados) - 1)) if len(achados) > 1 else W * 0.5
        y = camada_y + (i % 2) * 24 * u
        FX.brilho(q, x, y, 110 * u, cor=(1.0, 0.92, 0.70), forca=0.30 * kk, nucleo=0.0)
        _achado(q, nome, x - (60 * u if nome == "espada" else 0), y, 90 * u, kk)
        sp = np.random.default_rng(i).random((18, 3))                                                        # poeira do pincel
        idade = (t * 0.8 + sp[:, 0]) % 1.0
        FX.fumaca(q, x + (sp[:, 1] - 0.5) * 200 * u, y - idade * 70 * u, (6 + 16 * idade) * u, (0.90, 0.82, 0.66),
                  0.35 * (1 - idade) * kk)
    if p.get("camadas"):
        for y, txt, est in (((alturas[2] + alturas[3]) / 2, {"pt": "séc. 17", "en": "1600s"}, "vermelho"),
                            ((alturas[3] + alturas[4]) / 2, {"pt": "séc. 16", "en": "1500s"}, "papel")):
            e = etiqueta(L(txt, ctx["idioma"]), 40, est, 70 + len(est), -2.0)
            colar_img(q, e, W * 0.11, y, u)
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=2)
def _tronco(W, H, semente=13):
    """Corte de um tronco de cipreste, chapado e sem serrilhado: anéis com largura variando ano a ano, os três anéis
    finos e escuros da seca, o miolo, rachaduras saindo da casca, a casca e a sombra na mesa.
    Devolve (imagem float32, centro, raio do meio da faixa da seca)."""
    u = H / 1080
    rnd = np.random.default_rng(semente)
    cx, cy, R = W * 0.5, H * 0.51, H * 0.43
    n = 46
    larg = rnd.uniform(0.7, 1.3, n)
    larg[:5] *= 1.5                                                       # anéis do miolo, mais largos
    seca = n - 9
    larg[seca:seca + 3] = 0.36
    raios = np.concatenate([[0.0], np.cumsum(larg) / np.sum(larg) * R * 0.90])
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xs - cx, ys - cy
    ang = np.arctan2(dy, dx)
    dist = np.sqrt(dx * dx + dy * dy)
    r = dist * (1 + 0.022 * np.sin(ang * 3 + 1.0) + 0.010 * np.sin(ang * 7 + 2.0) + 0.004 * np.sin(ang * 17 + 0.5))
    idx = np.clip(np.searchsorted(raios, r) - 1, 0, n - 1)
    ini, fim = raios[idx], raios[idx + 1]
    noseca = (idx >= seca) & (idx < seca + 3)
    tard0 = ini + (fim - ini) * np.where(noseca, 0.45, 0.70)
    late = np.clip(r - tard0 + 0.5, 0, 1) * np.clip(fim - r + 0.5, 0, 1)
    late = np.maximum(late, np.clip(ini - r + 0.5, 0, 1))                  # borda do anel anterior
    clara = np.array([0.91, 0.76, 0.55], np.float32)
    escura = np.where(noseca[..., None], np.array([0.46, 0.29, 0.17], np.float32), np.array([0.73, 0.53, 0.34], np.float32))
    img = clara * (1 - late[..., None]) + escura * late[..., None]
    img *= (1.03 - 0.07 * (r / R) ** 2)[..., None]
    tex = np.asarray(Image.fromarray(P.textura(semente)).resize((W, H), Image.BILINEAR))
    img *= (1 + 0.035 * tex)[..., None]
    miolo = np.clip(5 * u - dist + 0.5, 0, 1)[..., None]
    img = img * (1 - miolo) + np.array([0.55, 0.36, 0.22], np.float32) * miolo
    for a0, comp in zip(rnd.uniform(-math.pi, math.pi, 3), rnd.uniform(0.22, 0.42, 3)):    # rachaduras da casca para dentro
        r0 = R * (0.92 - comp)
        da = np.angle(np.exp(1j * (ang - a0)))
        larg_px = 5 * u * np.clip((dist - r0) / (R * comp), 0, 1)
        k_ = np.clip(larg_px - np.abs(da) * dist + 0.5, 0, 1) * (dist > r0)
        img = img * (1 - k_[..., None]) + np.array([0.24, 0.15, 0.10], np.float32) * k_[..., None]
    borda = R * (1 + 0.012 * np.sin(ang * 23 + 1.3) + 0.008 * np.sin(ang * 41) + 0.006 * np.sin(ang * 67 + 2.0))
    casca = np.clip(r - R * 0.90 + 0.5, 0, 1)[..., None]
    cor_casca = np.array([0.33, 0.23, 0.17], np.float32) * (0.86 + 0.14 * np.sin(ang * 90))[..., None]
    img = img * (1 - casca) + cor_casca * casca
    cambio = np.clip(1.6 * u - np.abs(r - R * 0.90), 0, 1)[..., None] * 0.6
    img = img * (1 - cambio) + np.array([0.96, 0.86, 0.66], np.float32) * cambio
    fundo_ = np.array([0.11, 0.095, 0.085], np.float32) * (1.1 - 0.35 * (ys / H))[..., None]
    sdx, sdy = dx - 14 * u, dy - 22 * u
    sombra = np.clip((R * 1.04 - np.sqrt(sdx * sdx + sdy * sdy)) / (40 * u), 0, 1) * 0.55
    fundo_ = fundo_ * (1 - sombra)[..., None]
    dentro = np.clip(borda - r + 0.5, 0, 1)[..., None]
    img = fundo_ * (1 - dentro) + img * dentro
    rs = float((raios[seca] + raios[seca + 3]) / 2)
    banda = (np.clip(r - raios[seca] + 1.5, 0, 1) * np.clip(raios[seca + 3] - r + 1.5, 0, 1)).astype(np.float32)
    halo = np.asarray(Image.fromarray((banda * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9 * u)), np.float32) / 255.0
    return np.clip(img, 0, 1).astype(np.float32), (cx, cy), rs, banda, np.minimum(halo * 2.2, 1.0), ang.astype(np.float32)


def aneis(q, t, dur, p, ctx):
    """Corte do tronco com os anéis; com destaque, um anel vermelho marca os três anéis finos da seca e a câmera vai
    até eles."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    img, (cx, cy), rs, banda, halo, ang = _tronco(W, H)
    q[:] = img
    if p.get("destaque"):
        dt = p.get("destaque_t", 0.4)
        kd = FX.suave(FX.entre(tf, dt, dt + 0.12))
        if kd > 0:                                                        # os anéis da seca acendem em vermelho, em volta
            varre = -math.pi + 2.0 * math.pi * FX.suave(FX.entre(tf, dt, dt + 0.3)) + 1e-3
            corte = (ang <= varre)[..., None]
            vermelho = np.array([1.0, 0.30, 0.22], np.float32)
            kb = banda[..., None] * corte * (0.75 * kd)
            q[:] = q * (1 - kb) + vermelho * kb
            q += vermelho * (halo[..., None] * corte * (0.45 * kd * (0.85 + 0.15 * math.sin(t * 4))))
    z = p.get("zoom", [1.0, 1.1])
    s_ = FX.mistura(z[0], z[1], FX.suave(tf)) if isinstance(z, list) else z
    if abs(s_ - 1) > 1e-4:
        foco_x = cx + rs * 0.97 * FX.suave(tf) if p.get("destaque") else cx
        q[:] = FX.zoom(q, s_, foco_x, cy)
    _poeira(q, t, n=50, cor=(1.0, 0.92, 0.75), forca=0.10)
    _etiquetas(q, p, t, dur, ctx["idioma"])


@lru_cache(maxsize=32)
def _pedra_img(w, h, semente=17, verso=False):
    """Pedra lisa e irregular (float32 RGB e máscara); verso=True é o outro lado (o contorno espelhado)."""
    rnd = np.random.default_rng(semente)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = (xs - w / 2) / (w * 0.48), (ys - h / 2) / (h * 0.46)
    if verso:
        dx = -dx
    ang = np.arctan2(dy, dx)
    r = np.sqrt(dx * dx + dy * dy) * (1 + 0.05 * np.sin(ang * 3 + rnd.uniform(0, 6)) + 0.03 * np.sin(ang * 5 + rnd.uniform(0, 6)))
    m = np.clip((1 - r) * 40, 0, 1)
    tex = np.asarray(Image.fromarray(P.textura(semente % 7 + 1)).resize((w, h), Image.BILINEAR))
    pint = rnd.random((h, w)).astype(np.float32)
    cor = np.array([0.58, 0.55, 0.50], np.float32) * (0.85 + 0.12 * tex[..., None]) * (0.95 + 0.08 * (pint[..., None] > 0.985))
    rel = np.sqrt(np.clip(1 - r * r, 0, 1))                               # cúpula lisa (sem bico no meio)
    gy, gx = np.gradient(rel)
    luz = np.clip(-(gx + gy) * h * 0.5, -0.6, 0.6)
    cor = cor * (0.78 + 0.30 * rel[..., None]) + luz[..., None] * 0.22
    return np.clip(cor, 0, 1).astype(np.float32), m.astype(np.float32)


@lru_cache(maxsize=4)
def _sulcos(w, h, linhas, mostrar, tam):
    """Máscara das letras entalhadas (as `mostrar` primeiras) e a "parede" iluminada dos sulcos (luz de cima à esquerda)."""
    k = 2
    masc = Image.new("L", (w * k, h * k), 0)
    d = ImageDraw.Draw(masc)
    f = fonte("Bold", int(h * 0.11 * tam * k))
    feitas = 0
    n = len(linhas)
    for i, ln in enumerate(linhas):
        y = h * k * (0.5 + (i - (n - 1) / 2) * 0.17 * tam)
        vis = ln[:max(0, mostrar - feitas)]
        feitas += len(ln)
        if vis:
            d.text(((w * k - f.getlength(ln)) / 2, y), vis, font=f, fill=255, anchor="lm")
    mk = np.asarray(masc.resize((w, h), Image.BOX), np.float32) / 255.0
    bl = np.asarray(Image.fromarray((mk * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(h * 0.006)), np.float32) / 255.0
    gy, gx = np.gradient(bl)
    return mk, np.clip(-(gx + gy) * h * 0.02, -1, 1)[..., None].astype(np.float32)


@lru_cache(maxsize=2)
def _luz_rasante(W, H):
    luz = np.exp(-(((np.arange(W)[None, :] - W * 0.3) / (W * 0.7)) ** 2 + ((np.arange(H)[:, None] - H * 0.3) / (H * 0.9)) ** 2))
    return (0.55 + 0.6 * luz.astype(np.float32))[..., None]


def pedra(q, t, dur, p, ctx):
    """A Pedra de Dare: inscrição entalhada aparecendo letra a letra; muitas=True mostra a pilha de pedras falsas."""
    H, W = q.shape[:2]
    u = H / 1080
    tf = t / max(dur, 1e-6)
    ys = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    q[:] = np.array([0.16, 0.13, 0.11], np.float32) * (1.15 - 0.4 * ys)
    if p.get("muitas"):
        rnd = np.random.default_rng(3)
        comp, rots = rnd.uniform(0.55, 0.8, (12, 4)), rnd.uniform(-12, 12, 12)
        for i in range(12):
            col, lin = i % 6, i // 6
            w, h = int(W * 0.13), int(H * 0.22)
            cor, m = _pedra_img(w, h, 20 + i)
            x0, y0 = int(W * (0.05 + 0.15 * col)), int(H * (0.30 + 0.30 * lin))
            reg = q[y0:y0 + h, x0:x0 + w]
            reg[:] = reg * (1 - m[..., None]) + cor * m[..., None]
            for j in range(4):                                             # riscos de inscrição
                yy = y0 + h * (0.3 + 0.13 * j)
                FX.linha(q, (x0 + w * 0.2, yy), (x0 + w * comp[i, j], yy), largura=3 * u, cor=(0.30, 0.28, 0.25), forca=0.8)
            if i > 0:
                ks = FX.sai(FX.entre(tf, 0.45 + 0.03 * i, 0.5 + 0.03 * i), 3)
                if ks > 0:
                    e = etiqueta(L({"pt": "FALSA", "en": "FAKE"}, ctx["idioma"]), 28, "vermelho", 80 + i, float(round(rots[i], 1)))
                    colar_img(q, e, x0 + w / 2, y0 + h / 2, (1.4 - 0.4 * ks) * u, ks)
    else:
        w, h = int(W * 0.62), int(H * 0.62)
        cor, m = _pedra_img(w, h, 17, bool(p.get("verso")))
        x0, y0 = (W - w) // 2, int(H * 0.19)
        reg = q[y0:y0 + h, x0:x0 + w]
        sombra = np.roll(np.roll(m, int(14 * u), 0), int(10 * u), 1)
        reg *= (1 - 0.6 * sombra)[..., None]
        reg[:] = reg * (1 - m[..., None]) + cor * m[..., None]
        linhas = tuple(p.get("inscricao") or ())
        if linhas:
            total = sum(len(x) for x in linhas)
            t0, t1 = p.get("letras_t", [0.2, 0.8])
            kk = 1.0 if t0 < 0 else FX.entre(tf, t0, t1)
            mk, parede = _sulcos(w, h, linhas, int(math.ceil(kk * total)), float(p.get("tam", 1.0)))
            mk = mk * m
            sulco = reg * 0.45 + np.where(parede > 0, parede * 0.35, parede * 0.15)
            reg[:] = reg * (1 - mk[..., None]) + sulco * mk[..., None]
    q *= _luz_rasante(W, H)
    z = p.get("zoom", [1.0, 1.04])
    s_ = FX.mistura(z[0], z[1], FX.suave(tf)) if isinstance(z, list) else z
    if abs(s_ - 1) > 1e-4:
        q[:] = FX.zoom(q, s_)
    _poeira(q, t, n=60, cor=(0.95, 0.90, 0.80), forca=0.10)
    _etiquetas(q, p, t, dur, ctx["idioma"])


CENAS = {"mar_navio": mar_navio, "frota": frota, "mapa": mapa, "calendario": calendario, "ilha_noite": ilha_noite, "entalhe": entalhe,
         "cruz": cruz, "linha_tempo": linha_tempo, "titulo": titulo, "capitulo": capitulo, "retrato": retrato, "colonos": colonos,
         "baus": baus, "escavacao": escavacao, "aneis": aneis, "pedra": pedra}
