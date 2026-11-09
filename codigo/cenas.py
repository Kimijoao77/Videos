"""Cenas do Fora de Órbita / Out of Orbit, desenhadas 100% por código, no estilo da marca (marca.py).

Cada cena é uma função (t, dur, w, h, p) -> Image RGB, registrada em CENAS. O roteiro escolhe a cena pelo nome
(visual {"tipo": "anim", "nome": "...", "params": {...}}) e gerar.py grava o mp4 com render().
Funcionam em pé (Short 1080×1920) e deitadas (vídeo 1920×1080).

Catálogo (o Claude consulta ao escrever o roteiro; textos podem ser {"pt": ..., "en": ...}):
  titulo     gancho: a Terra com brilho e o título grande.            titulo, objeto ("lua"|"asteroide"|""), rotulo
  ceu        céu à noite sobre uma cidade, com a Lua (ou outro astro). escala_ini, escala_fim, alerta (0/1), tremor (0/1), rotulo
  queda      vista de cima: a Lua sai da órbita e cai na Terra, com contadores de distância e de dias.
                                                                       km_ini, dias, rotulo_km ("km"), rotulo_dia ("dia")
  mare       cidade no litoral à noite, a água subindo.               subida (0 a 1), lua (tamanho da Lua no céu), rotulo
  despedaca  a Lua chega perto da Terra, racha e vira pedaços.        rotulo
  chuva      pedaços caindo na Terra: rastros, clarões e anéis.       rotulo
  brasa      a Terra vira brasa: crosta derretida e brilho vermelho.  rotulo
  colisao    um planeta bate na Terra jovem e os destroços viram a Lua. rotulo
  fim        cartão final com o logo do canal.                        texto
"""
import math, random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import animacoes as AN
import graficos as G
import marca as M

FPS = G.FPS
AMARELO, BRANCO, GELO, VERMELHO, CIANO, NOITE, TINTA = M.AMARELO, M.BRANCO, M.GELO, M.VERMELHO, M.CIANO, M.NOITE, M.TINTA


# ------------------------------------------------------------------ ajudantes
def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def entre(t, a, b):
    """0 antes de a, 1 depois de b, suave no meio."""
    return suave((t - a) / max(1e-6, b - a))


@lru_cache(maxsize=8)
def _fundo(w, h, semente):
    return M.fundo_espaco(w, h, semente=semente).convert("RGB")


def fundo(w, h, semente=7):
    return _fundo(w, h, semente).copy().convert("RGBA")


def num(p, k, padrao):
    try:
        return float(p.get(k, padrao))
    except (TypeError, ValueError):
        return padrao


def chip(img, texto, x, y, tam, cor=AMARELO, ancora="lt", a=1.0):
    """Etiqueta da marca: fundo azul-tinta arredondado e texto em Unbounded."""
    if not texto or a <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    f = M.fonte("Bold", tam)
    b = d.textbbox((0, 0), texto, font=f, anchor="ls")
    pw, ph = tam * 0.62, tam * 0.48
    lw, lh = b[2] - b[0] + 2 * pw, -b[1] + 2 * ph
    if ancora[0] == "m":
        x -= lw / 2
    elif ancora[0] == "r":
        x -= lw
    if ancora[1] == "m":
        y -= lh / 2
    elif ancora[1] == "b":
        y -= lh
    d.rounded_rectangle([x, y, x + lw, y + lh], radius=lh / 2, fill=TINTA + (int(225 * a),), outline=cor + (int(150 * a),), width=max(2, int(tam * 0.08)))
    d.text((x + pw, y + ph - b[1]), texto, font=f, fill=cor + (int(255 * a),), anchor="ls")


def titulo(img, texto, cx, y0, largura, cap, a=1.0, cor_ultima=AMARELO):
    """Título em Unbounded Black, quebrado em linhas; a última linha em amarelo. Devolve o y do fim."""
    if not texto or a <= 0:
        return y0
    d = ImageDraw.Draw(img, "RGBA")
    f = M.fonte("Black", cap / M._cap("Black"))
    palavras, linhas, atual = texto.split(), [], ""
    for pw in palavras:
        if f.getlength((atual + " " + pw).strip()) <= largura or not atual:
            atual = (atual + " " + pw).strip()
        else:
            linhas.append(atual); atual = pw
    linhas.append(atual)
    y = y0
    for i, l in enumerate(linhas):
        cor = cor_ultima if i == len(linhas) - 1 and len(linhas) > 1 else BRANCO
        d.text((cx, y + cap), l, font=f, fill=cor + (int(255 * a),), anchor="ms", stroke_width=max(2, int(cap * 0.07)), stroke_fill=(6, 9, 28, int(255 * a)))
        y += cap * 1.42
    return y


def colar_seguro(img, peca, cx, cy):
    """Cola uma imagem RGBA centrada em (cx, cy), mesmo saindo da tela."""
    x, y = int(round(cx - peca.width / 2)), int(round(cy - peca.height / 2))
    img.paste(peca, (x, y), peca)


def brilho(img, cx, cy, r, cor, forca=0.5, borrao=0.35):
    """Halo suave: desenha e borra numa camada 4× menor (bem mais rápido) e amplia."""
    q = 4
    W, H = img.size
    cam = Image.new("RGBA", (W // q + 1, H // q + 1), (0, 0, 0, 0))
    ImageDraw.Draw(cam).ellipse([(cx - r) / q, (cy - r) / q, (cx + r) / q, (cy + r) / q], fill=cor + (int(255 * forca),))
    cam = cam.filter(ImageFilter.GaussianBlur(max(1, r * borrao / q))).resize((W, H), Image.BILINEAR)
    img.alpha_composite(cam)


def tremer(t, forca, h):
    if forca <= 0:
        return 0, 0
    return math.sin(t * 61) * forca * h, math.cos(t * 47) * forca * h


@lru_cache(maxsize=4)
def _lua_grande():
    return AN.lua_esfera(700)


def lua(r):
    r = max(2, int(r))
    return _lua_grande().resize((2 * r, 2 * r), Image.LANCZOS)


def terra(r, lon0, maximo=480):
    """Terra de raio r; acima de `maximo`, calcula menor e amplia (a textura é suave, não perde nada)."""
    if r <= maximo:
        return AN.globo(int(r)).imagem(lon0)
    return AN.globo(maximo).imagem(lon0).resize((int(2 * r), int(2 * r)), Image.BICUBIC)


# ------------------------------------------------------------------ titulo
def c_titulo(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 21)
    zoom = 1 + 0.06 * t / dur
    r0 = int(min(w, h) * (0.42 if vert else 0.36))
    r = r0 * zoom
    cx, cy = w * 0.5, h * (0.70 if vert else 0.62)
    brilho(img, cx, cy, r * 1.05, CIANO, 0.40, 0.12)
    globo = terra(r0, -20 - 25 * t / dur)
    colar_seguro(img, globo.resize((int(2 * r), int(2 * r)), Image.BICUBIC), cx, cy)
    if p.get("objeto") == "lua":
        k = entre(t, 0.2, dur)
        rl = r * (0.18 + 0.20 * k)
        lx, ly = cx + r * (0.95 - 0.25 * k), cy - r * (1.05 - 0.15 * k)
        brilho(img, lx, ly, rl * 1.3, (255, 255, 255), 0.18, 0.4)
        colar_seguro(img, lua(rl), lx, ly)
    a = entre(t, 0.05, 0.6)
    titulo(img, p.get("titulo", ""), w / 2, h * (0.10 if vert else 0.07), w * 0.86, h * (0.052 if vert else 0.075), a)
    if p.get("rotulo"):
        chip(img, p["rotulo"], w / 2, h * (0.40 if vert else 0.34), int(h * (0.022 if vert else 0.032)), ancora="mt", a=entre(t, 0.8, 1.3))
    return img.convert("RGB")


# ------------------------------------------------------------------ ceu (cidade à noite com um astro no céu)
@lru_cache(maxsize=4)
def _cidade(w, h, chao, semente=4):
    """Duas camadas de prédios (a de trás mais clara) com janelas; devolve (camada RGBA, lista de janelas)."""
    rnd = random.Random(semente)
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    janelas = []
    for camada, (cor, hmin, hmax, larg) in enumerate([((28, 38, 84), 0.10, 0.30, (0.05, 0.11)), ((12, 17, 44), 0.06, 0.22, (0.06, 0.13))]):
        x = -w * 0.02
        while x < w:
            bw = w * rnd.uniform(*larg)
            bh = h * rnd.uniform(hmin, hmax) * (1.25 if camada == 0 else 1.0)
            topo = chao - bh
            d.rectangle([x, topo, x + bw, h], fill=cor)
            if rnd.random() < 0.25:                                   # antena
                ax = x + bw * rnd.uniform(0.3, 0.7)
                d.rectangle([ax - 2, topo - h * 0.03, ax + 2, topo], fill=cor)
            if camada == 1:
                passo_x, passo_y = w * 0.018, h * 0.022
                for jy in np.arange(topo + passo_y, chao - passo_y * 0.5, passo_y):
                    for jx in np.arange(x + passo_x * 0.6, x + bw - passo_x * 0.4, passo_x):
                        if rnd.random() < 0.38:
                            janelas.append((jx, jy, w * 0.006, h * 0.006, rnd.random()))
            x += bw + w * rnd.uniform(0.0, 0.015)
    return cam, tuple(janelas)


@lru_cache(maxsize=4)
def _ceu(w, h, chao, alerta):
    ys = np.linspace(0, 1, h)[:, None]
    topo, base = np.array(M.NOITE, np.float32), np.array((44, 58, 128) if not alerta else (120, 36, 46), np.float32)
    k = np.clip(ys / (chao / h), 0, 1) ** 2.2
    arr = topo + (base - topo) * k[..., None]
    img = Image.fromarray(np.repeat(arr[:, None, :], w, axis=1).reshape(h, w, 3).astype(np.uint8), "RGB").convert("RGBA")
    rnd = random.Random(9)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(int(w * h / 7000)):
        x, y = rnd.uniform(0, w), rnd.uniform(0, chao * 0.85)
        r = rnd.choice([0.8, 1.0, 1.3, 1.8]) * w / 1080
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(60, 200)))
    return img


def c_ceu(t, dur, w, h, p):
    vert = h > w
    chao = h * (0.80 if vert else 0.84)
    alerta = int(num(p, "alerta", 0)) == 1
    img = _ceu(w, h, chao, alerta).copy()
    k = suave(t / dur)
    e0, e1 = num(p, "escala_ini", 1), num(p, "escala_fim", 1)
    esc = e0 * (e1 / e0) ** k if e0 > 0 else e1
    r = min(w, h) * 0.055 * esc
    lx, ly = w * 0.62, h * (0.30 if vert else 0.33) + r * 0.15
    dx, dy = tremer(t, 0.004 if int(num(p, "tremor", 0)) and t > dur * 0.4 else 0, h)
    brilho(img, lx + dx, ly + dy, r * 2.2, (210, 225, 255), min(0.55, 0.22 + 0.05 * esc), 0.45)
    colar_seguro(img, lua(r), lx + dx, ly + dy)
    cidade, janelas = _cidade(w, h, chao)
    img.alpha_composite(cidade, (int(dx), int(dy)))
    d = ImageDraw.Draw(img, "RGBA")
    for jx, jy, jw, jh, fase in janelas:
        if (math.sin(t * 2.0 + fase * 40) + 1.2) > 0.25:
            d.rectangle([jx + dx, jy + dy, jx + jw + dx, jy + jh + dy], fill=(255, 214, 110, 210))
    if p.get("rotulo"):
        chip(img, p["rotulo"], w * 0.06, h * (0.08 if vert else 0.08), int(h * (0.028 if vert else 0.036)), a=entre(t, 0.3, 0.8))
    return img.convert("RGB")


# ------------------------------------------------------------------ queda (vista de cima)
def _ciclo(tau):
    """Queda livre a partir do repouso: fração da distância r/r0 no tempo tau (0 a 1 do tempo total da queda)."""
    tau = max(0.0, min(1.0, tau))
    alvo = math.pi * tau
    th = alvo / 2
    for _ in range(30):                                            # θ + sen θ = π τ (Newton)
        f = th + math.sin(th) - alvo
        th -= f / (1 + math.cos(th) + 1e-9)
        th = max(0.0, min(math.pi, th))
    return (1 + math.cos(th)) / 2


def c_queda(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 33)
    d = ImageDraw.Draw(img, "RGBA")
    rt = min(w, h) * (0.11 if vert else 0.10)
    ex, ey = (w * 0.5, h * 0.78) if vert else (w * 0.22, h * 0.55)
    D = (h * 0.50) if vert else (w * 0.60)
    ang0 = -math.pi / 2 if vert else 0.0                           # a Lua começa em cima (em pé) ou à direita (deitado)
    t_para, t_fim = dur * 0.16, dur * 0.94
    # órbita tracejada que some quando a Lua para
    a_orb = 1 - entre(t, t_para, t_para + 0.8)
    n = 90
    for i in range(0, n, 2):
        a1, a2 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.line([(ex + D * math.cos(a1), ey + D * math.sin(a1)), (ex + D * math.cos(a2), ey + D * math.sin(a2))], fill=AMARELO + (int(150 * a_orb),), width=max(2, int(min(w, h) * 0.004)))
    # Lua: anda um pouco na órbita, para e cai em linha reta
    ang = ang0 - 0.35 * (1 - entre(t, 0, t_para)) if t < t_para else ang0
    tau = (t - t_para) / (t_fim - t_para)
    frac = _ciclo(tau) if t > t_para else 1.0
    dist = rt * 1.25 + (D - rt * 1.25) * frac
    lx, ly = ex + dist * math.cos(ang), ey + dist * math.sin(ang)
    if t > t_para:                                                  # rastro da queda
        d.line([(ex + D * math.cos(ang), ey + D * math.sin(ang)), (lx, ly)], fill=AMARELO + (170,), width=max(2, int(min(w, h) * 0.006)))
    brilho(img, ex, ey, rt * 1.25, CIANO, 0.35, 0.25)
    colar_seguro(img, terra(rt, -40 - 30 * t / dur), ex, ey)
    rl = rt * 0.27 * 1.6
    colar_seguro(img, lua(rl), lx, ly)
    # contadores
    km = num(p, "km_ini", 384400) * frac
    dias = num(p, "dias", 4.8) * max(0.0, min(1.0, tau if t > t_para else 0))
    tam = int(h * (0.028 if vert else 0.038))
    km_txt = f"{km:,.0f}".replace(",", ".") + f" {p.get('rotulo_km', 'km')}"
    dia_txt = f"{p.get('rotulo_dia', 'dia')} {dias:.1f}".replace(".", ",")
    if vert:
        chip(img, km_txt, w * 0.5, h * 0.07, tam, ancora="mt")
        chip(img, dia_txt, w * 0.5, h * 0.07 + tam * 2.6, tam, cor=GELO, ancora="mt")
    else:
        chip(img, km_txt, w * 0.62, h * 0.10, tam, ancora="lt")
        chip(img, dia_txt, w * 0.62, h * 0.10 + tam * 2.6, tam, cor=GELO, ancora="lt")
    if p.get("rotulo") and frac < 0.5:
        chip(img, p["rotulo"], (w * 0.5 if vert else w * 0.62), (h * 0.07 + tam * 5.2 if vert else h * 0.10 + tam * 5.2), tam, cor=VERMELHO, ancora=("mt" if vert else "lt"), a=entre(0.5 - frac, 0, 0.08))
    return img.convert("RGB")


# ------------------------------------------------------------------ mare (litoral à noite, água subindo)
def c_mare(t, dur, w, h, p):
    vert = h > w
    chao = h * (0.66 if vert else 0.70)
    img = _ceu(w, h, chao, False).copy()
    r = min(w, h) * 0.055 * num(p, "lua", 3)
    lx, ly = w * 0.30, h * (0.20 if vert else 0.24)
    brilho(img, lx, ly, r * 2.0, (210, 225, 255), 0.35, 0.45)
    colar_seguro(img, lua(r), lx, ly)
    cidade, janelas = _cidade(w, h, chao, 6)
    # a cidade fica do meio para a direita, numa faixa de areia
    img.alpha_composite(cidade)
    d = ImageDraw.Draw(img, "RGBA")
    for jx, jy, jw, jh, fase in janelas:
        if jx > w * 0.35 and (math.sin(t * 2.0 + fase * 40) + 1.2) > 0.25:
            d.rectangle([jx, jy, jx + jw, jy + jh], fill=(255, 214, 110, 210))
    d.rectangle([0, chao, w, h], fill=(36, 34, 52))
    # mar: o nível sobe com a cena; ondas por cima
    sub = num(p, "subida", 0.6)
    k = entre(t, 0.1, dur * 0.95)
    nivel = chao + h * 0.12 - k * sub * h * 0.45
    pts = [(0, h)]
    for i in range(0, 61):
        x = w * i / 60
        y = nivel + math.sin(i * 0.55 + t * 3.2) * h * 0.008 + math.sin(i * 0.21 - t * 1.7) * h * 0.012
        pts.append((x, y))
    pts.append((w, h))
    agua = Image.new("RGBA", img.size, (0, 0, 0, 0))
    da = ImageDraw.Draw(agua, "RGBA")
    da.polygon(pts, fill=(24, 74, 150, 235))
    da.line(pts[1:-1], fill=(170, 230, 255, 230), width=max(2, int(h * 0.005)))
    for i in range(14):                                             # reflexo da Lua na água
        y = nivel + h * 0.02 + i * h * 0.018
        meia = w * (0.07 - i * 0.004) * (1 + 0.15 * math.sin(t * 3 + i))
        if y < h:
            da.line([(lx - meia, y), (lx + meia, y)], fill=(230, 240, 255, max(0, 140 - i * 9)), width=max(1, int(h * 0.004)))
    img.alpha_composite(agua)
    if p.get("rotulo"):
        chip(img, p["rotulo"], w * 0.06, h * 0.08, int(h * (0.028 if vert else 0.036)), cor=AMARELO, a=entre(t, 0.4, 0.9))
    return img.convert("RGB")


# ------------------------------------------------------------------ despedaca (a Lua racha perto da Terra)
@lru_cache(maxsize=2)
def _pedacos(r, n=46, semente=8):
    """Corta a Lua (raio r) em pedaços (Voronoi). Devolve [(imagem RGBA, dx, dy do centro do pedaço)]."""
    base = lua(r)
    rnd = np.random.default_rng(semente)
    ang = rnd.uniform(0, 2 * math.pi, n)
    rad = np.sqrt(rnd.uniform(0, 1, n)) * r * 0.95
    sx, sy = r + rad * np.cos(ang), r + rad * np.sin(ang)
    ys, xs = np.mgrid[0:2 * r, 0:2 * r]
    dist = (xs[..., None] - sx) ** 2 + (ys[..., None] - sy) ** 2
    rotulo = np.argmin(dist, axis=2)
    alfa = np.asarray(base)[..., 3]
    arr = np.asarray(base)
    pecas = []
    for i in range(n):
        m = (rotulo == i) & (alfa > 10)
        if m.sum() < 30:
            continue
        yy, xx = np.nonzero(m)
        y0, y1, x0, x1 = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
        pedaco = arr[y0:y1, x0:x1].copy()
        pedaco[..., 3] = np.where(m[y0:y1, x0:x1], pedaco[..., 3], 0)
        pecas.append((Image.fromarray(pedaco, "RGBA"), (x0 + x1) / 2 - r, (y0 + y1) / 2 - r))
    return pecas


def c_despedaca(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 44)
    R = w * (1.05 if vert else 0.75)
    ex, ey = w * 0.5, h + R * (0.55 if vert else 0.62)
    brilho(img, ex, ey, R * 1.03, CIANO, 0.45, 0.06)
    colar_seguro(img, terra(R, -60 - 8 * t / dur), ex, ey)
    rl = int(min(w, h) * (0.20 if vert else 0.22))
    lx, ly = w * 0.5, h * (0.33 if vert else 0.36)
    t_racha, t_quebra = dur * 0.30, dur * 0.50
    if t < t_quebra:
        dx, dy = tremer(t, 0.003 if t > t_racha else 0, h)
        colar_seguro(img, lua(rl), lx + dx, ly + dy)
        if t > t_racha:                                             # rachaduras crescendo
            d = ImageDraw.Draw(img, "RGBA")
            k = entre(t, t_racha, t_quebra)
            rnd = random.Random(5)
            for _ in range(7):
                x, y = lx + rnd.uniform(-0.3, 0.3) * rl, ly + rnd.uniform(-0.3, 0.3) * rl
                a = rnd.uniform(0, 2 * math.pi)
                pts = [(x, y)]
                for _s in range(int(2 + 6 * k)):
                    a += rnd.uniform(-0.6, 0.6)
                    x += math.cos(a) * rl * 0.12
                    y += math.sin(a) * rl * 0.12
                    if math.hypot(x - lx, y - ly) > rl * 0.97:
                        break
                    pts.append((x, y))
                if len(pts) > 1:
                    d.line(pts, fill=(255, 120, 90, int(220 * k)), width=max(2, int(rl * 0.018)))
    else:
        k = (t - t_quebra) / max(0.1, dur - t_quebra)
        rnd = random.Random(12)
        for img_p, px, py in _pedacos(rl):
            # maré: estica na direção da Terra (para baixo) e abre para os lados
            v = 0.45 + rnd.random() * 0.8
            gx = px * (1 + 0.9 * k * v)
            gy = py * (1 + 1.6 * k * v) + rl * 2.2 * k * k * (0.6 + 0.4 * (py / rl + 1))
            giro = rnd.uniform(-1, 1) * 160 * k
            peca = img_p.rotate(giro, expand=True, resample=Image.BICUBIC)
            colar_seguro(img, peca, lx + gx, ly + gy)
        d = ImageDraw.Draw(img, "RGBA")
        for _ in range(140):                                        # poeira
            a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(0, 1) * rl
            x = lx + math.cos(a) * r0 * (1 + 1.4 * k)
            y = ly + math.sin(a) * r0 * (1 + 2.2 * k) + rl * 1.8 * k * k
            s = rnd.uniform(1, 3) * w / 1080
            d.ellipse([x - s, y - s, x + s, y + s], fill=(200, 196, 190, int(200 * (1 - k * 0.5))))
    if p.get("rotulo"):
        chip(img, p["rotulo"], w / 2, h * (0.07 if vert else 0.07), int(h * (0.028 if vert else 0.036)), cor=VERMELHO, ancora="mt", a=entre(t, 0.2, 0.7))
    return img.convert("RGB")


# ------------------------------------------------------------------ chuva (pedaços caindo na Terra)
def c_chuva(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 55)
    r = min(w, h) * (0.40 if vert else 0.36)
    cx, cy = w * 0.5, h * (0.58 if vert else 0.55)
    k = t / dur
    cor_atm = tuple(int(CIANO[i] + (VERMELHO[i] - CIANO[i]) * suave(k * 1.3)) for i in range(3))
    brilho(img, cx, cy, r * 1.07, cor_atm, 0.55, 0.10)
    colar_seguro(img, terra(r, -10 - 20 * k), cx, cy)
    q = 2                                                           # crateras e clarões em meia resolução
    marcas = Image.new("RGBA", (w // q, h // q), (0, 0, 0, 0))
    luz = Image.new("RGBA", (w // q, h // q), (0, 0, 0, 0))
    dm, dl = ImageDraw.Draw(marcas, "RGBA"), ImageDraw.Draw(luz, "RGBA")
    meia = lambda caixa: [c / q for c in caixa]
    rnd = random.Random(21)
    rastros = []
    lw = max(3, int(min(w, h) * 0.008))
    for i in range(60):
        chegada = rnd.uniform(0.04, 0.96) * dur
        a = rnd.uniform(0, 2 * math.pi); rr = math.sqrt(rnd.uniform(0, 0.8)) * r
        alvo = (cx + math.cos(a) * rr, cy + math.sin(a) * rr)
        origem = (alvo[0] + w * 0.8, alvo[1] - h * 0.8)
        tam = rnd.uniform(0.6, 1.4)
        voo = 0.6
        if chegada - voo < t < chegada:
            f = (t - (chegada - voo)) / voo
            rastros.append((origem, alvo, f, tam))
        elif t >= chegada:
            f = min(1.0, (t - chegada) / 1.2)
            rc = r * 0.045 * tam * (1 + 0.6 * f)
            dm.ellipse(meia([alvo[0] - rc, alvo[1] - rc * 0.8, alvo[0] + rc, alvo[1] + rc * 0.8]), fill=(70, 12, 10, 200))
            dl.ellipse(meia([alvo[0] - rc * 1.8, alvo[1] - rc * 1.5, alvo[0] + rc * 1.8, alvo[1] + rc * 1.5]), fill=(255, 90, 50, int(150 * (1 - 0.4 * f))))
            if f < 1:                                               # clarão
                rf = r * 0.12 * tam * (0.6 + 1.6 * f)
                dl.ellipse(meia([alvo[0] - rf, alvo[1] - rf, alvo[0] + rf, alvo[1] + rf]), fill=(255, 245, 210, int(255 * (1 - f) ** 1.5)))
    img.alpha_composite(luz.filter(ImageFilter.GaussianBlur(r * 0.03 / q)).resize((w, h), Image.BILINEAR))
    img.alpha_composite(marcas.filter(ImageFilter.GaussianBlur(max(1, r * 0.006 / q))).resize((w, h), Image.BILINEAR))
    d = ImageDraw.Draw(img, "RGBA")
    for origem, alvo, f, tam in rastros:
        x = origem[0] + (alvo[0] - origem[0]) * f
        y = origem[1] + (alvo[1] - origem[1]) * f
        for cauda, larg, al in ((0.22, 2.2, 70), (0.12, 1.3, 170), (0.05, 0.7, 255)):
            x2 = origem[0] + (alvo[0] - origem[0]) * max(0, f - cauda)
            y2 = origem[1] + (alvo[1] - origem[1]) * max(0, f - cauda)
            d.line([(x2, y2), (x, y)], fill=(255, 210, 140, al), width=max(2, int(lw * larg * tam)))
        rc = lw * 1.2 * tam
        d.ellipse([x - rc, y - rc, x + rc, y + rc], fill=(255, 252, 236, 255))
    if p.get("rotulo"):
        chip(img, p["rotulo"], w / 2, h * 0.07, int(h * (0.028 if vert else 0.036)), cor=VERMELHO, ancora="mt", a=entre(t, 0.2, 0.7))
    dx, dy = tremer(t, 0.002, h)
    if dx or dy:
        img = img.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)
    return img.convert("RGB")


# ------------------------------------------------------------------ brasa (a Terra derretendo)
_LAVA = None


def _textura_lava():
    global _LAVA
    if _LAVA is None:
        H, W = AN.textura().shape
        rnd = np.random.default_rng(11)
        campo = np.zeros((H // 4, W // 4), np.float32)
        for cel, peso in ((96, 1.0), (40, 0.45), (18, 0.18)):        # ruído suave em 3 escalas (cel = pixels por célula)
            r = rnd.normal(size=(H // cel + 2, W // cel + 2)).astype(np.float32)
            campo += np.asarray(Image.fromarray(r).resize((W // 4, H // 4), Image.BICUBIC)) * peso
        campo = np.asarray(Image.fromarray(campo).resize((W, H), Image.BICUBIC))
        veios = np.exp(-(np.abs(campo) / 0.07) ** 2)                # rachaduras onde o campo cruza o zero
        base = np.array([58, 14, 18], np.float32)
        lava = np.array([255, 110, 60], np.float32)
        quente = np.array([255, 214, 120], np.float32)
        cor = base + (lava - base) * np.clip(veios * 1.2, 0, 1)[..., None]
        cor = cor + (quente - cor) * np.clip(veios - 0.7, 0, 1)[..., None] * 2
        _LAVA = np.clip(cor, 0, 255)
    return _LAVA


def _globo_misturado(r, lon0, k):
    g = AN.globo(int(r))
    tex = AN.textura()
    H, W = tex.shape
    u = (((g.lon + lon0 + 180) % 360) / 360 * (W - 1)).astype(np.int32)
    v = ((90 - g.lat) / 180 * (H - 1)).astype(np.int32)
    m = tex[v, u][..., None]
    normal = AN.cor_terra()[v, u] * m + AN.OCEANO * (1 - m)
    lava = _textura_lava()[v, u]
    luz = g.sombra[..., None] * (1 - k) + (0.55 + 0.45 * g.sombra[..., None]) * k   # lava brilha mesmo no lado escuro
    cor = (normal * (1 - k) + lava * k) * luz
    return Image.fromarray(np.dstack([np.clip(cor, 0, 255), g.alfa * 255]).astype(np.uint8), "RGBA")


def c_brasa(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 66)
    r = min(w, h) * (0.42 if vert else 0.38)
    cx, cy = w * 0.5, h * (0.56 if vert else 0.54)
    k = entre(t, 0.1, dur * 0.8)
    brilho(img, cx, cy, r * 1.08, (255, 80, 60), 0.25 + 0.45 * k, 0.12)
    colar_seguro(img, _globo_misturado(r, 30 - 15 * t / dur, k), cx, cy)
    if p.get("rotulo"):
        chip(img, p["rotulo"], w / 2, h * 0.07, int(h * (0.028 if vert else 0.036)), cor=VERMELHO, ancora="mt", a=entre(t, 0.4, 0.9))
    return img.convert("RGB")


# ------------------------------------------------------------------ colisao (Theia: a origem da Lua)
def _bola(r, cor, luz=(-0.55, -0.45, 0.70)):
    r = max(2, int(r))
    ys, xs = np.mgrid[-r:r, -r:r].astype(np.float32) + 0.5
    x, y = xs / r, ys / r
    dd = np.sqrt(x * x + y * y)
    z = np.sqrt(np.clip(1 - dd * dd, 0, 1))
    L = np.array(luz, np.float32); L /= np.linalg.norm(L)
    k = np.clip(0.18 + 0.95 * np.clip(x * L[0] + y * L[1] + z * L[2], 0, 1), 0, 1.1)
    rgb = np.array(cor, np.float32)[None, None, :] * k[..., None]
    alfa = np.clip((1 - dd) * r, 0, 1) * 255
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alfa]).astype(np.uint8), "RGBA")


def c_colisao(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 77)
    R = min(w, h) * (0.30 if vert else 0.27)
    cx, cy = w * 0.5, h * (0.56 if vert else 0.55)
    t_bate = dur * 0.32
    brilho(img, cx, cy, R * 1.1, (255, 120, 80), 0.40, 0.12)
    rnd = random.Random(31)
    k = max(0.0, (t - t_bate) / max(0.1, dur - t_bate))
    # destroços: cada um tem um ângulo no anel; os de trás (sen < 0) vão antes do planeta
    pedras = []
    if t >= t_bate:
        for i in range(420):
            base = rnd.uniform(0, 2 * math.pi)
            esp = rnd.uniform(0, 1)
            ang = base + k * (1.2 + esp)                            # giram no anel
            sai = min(1.0, k * 3.0)                                 # saem do ponto do impacto e se espalham
            ang = (-0.9) * (1 - sai) + ang * sai
            junta = suave((k - 0.45) / 0.55) * 0.9                  # no fim, vão se juntando num ponto do anel
            ang = ang * (1 - junta) + 4.3 * junta
            rad = R * (1.25 + esp * (0.45 if vert else 0.7)) * (1 - 0.15 * junta)
            x = cx + math.cos(ang) * rad
            y = cy + math.sin(ang) * rad * 0.34 - math.cos(ang) * rad * 0.10
            s_ = rnd.uniform(1.6, 4.2) * w / 1080
            calor = max(0.0, 1 - k * 1.3)
            cor = (255, int(140 + 100 * calor), int(90 + 60 * calor), 235)
            pedras.append((math.sin(ang) >= 0, x, y, s_, cor))
    d = ImageDraw.Draw(img, "RGBA")
    for frente, x, y, s_, cor in pedras:
        if not frente:
            d.ellipse([x - s_, y - s_, x + s_, y + s_], fill=cor)
    img.alpha_composite(_bola(R, (150, 70, 52)), (int(cx - R), int(cy - R)))
    d = ImageDraw.Draw(img, "RGBA")
    for frente, x, y, s_, cor in pedras:
        if frente:
            d.ellipse([x - s_, y - s_, x + s_, y + s_], fill=cor)
    if t < t_bate:                                                  # o outro planeta chegando
        f = t / t_bate
        rt = R * 0.50
        ox, oy = cx + R * 1.75, cy - R * 1.55
        tx, ty = cx + R * 0.80, cy - R * 0.62
        x, y = ox + (tx - ox) * f ** 1.6, oy + (ty - oy) * f ** 1.6
        img.alpha_composite(_bola(rt, (128, 120, 112)), (int(x - rt), int(y - rt)))
    else:
        fl = max(0, 1 - k * 3.5)
        if fl > 0:
            brilho(img, cx + R * 0.7, cy - R * 0.6, R * (0.5 + 1.4 * k), (255, 245, 210), 0.95 * fl, 0.5)
        if k > 0.6:                                                 # a Lua nova aparece onde os destroços se juntam
            rl = R * 0.27 * entre(k, 0.6, 1.0)
            ang = 4.3
            mx, my = cx + math.cos(ang) * R * 1.55, cy + math.sin(ang) * R * 1.55 * 0.34 - math.cos(ang) * R * 1.55 * 0.10
            colar_seguro(img, lua(rl), mx, my)
    if p.get("rotulo"):
        chip(img, p["rotulo"], w / 2, h * 0.07, int(h * (0.028 if vert else 0.036)), cor=AMARELO, ancora="mt", a=entre(t, 0.2, 0.7))
    return img.convert("RGB")


# ------------------------------------------------------------------ fim (cartão com o logo)
@lru_cache(maxsize=4)
def _logo(idioma, altura):
    return M.logo(idioma, altura)


def c_fim(t, dur, w, h, p):
    vert = h > w
    img = fundo(w, h, 88)
    idioma = p.get("_idioma", "pt")
    alt = int(h * (0.10 if vert else 0.20))
    lg = _logo(idioma, alt)
    if lg.width > w * 0.86:
        lg = lg.resize((int(w * 0.86), int(lg.height * w * 0.86 / lg.width)), Image.LANCZOS)
    a = entre(t, 0.0, 0.5)
    s = 0.92 + 0.08 * a
    peca = lg.resize((max(1, int(lg.width * s)), max(1, int(lg.height * s))), Image.LANCZOS)
    if a < 1:
        al = np.asarray(peca).copy(); al[..., 3] = (al[..., 3] * a).astype(np.uint8); peca = Image.fromarray(al, "RGBA")
    colar_seguro(img, peca, w / 2, h * 0.46)
    if p.get("texto"):
        d = ImageDraw.Draw(img, "RGBA")
        f = M.fonte("Medium", h * (0.022 if vert else 0.034))
        d.text((w / 2, h * 0.46 + lg.height * 0.75), p["texto"], font=f, fill=(196, 205, 242, int(255 * entre(t, 0.4, 0.9))), anchor="mm")
    return img.convert("RGB")


CENAS = {"titulo": c_titulo, "ceu": c_ceu, "queda": c_queda, "mare": c_mare, "despedaca": c_despedaca, "chuva": c_chuva,
         "brasa": c_brasa, "colisao": c_colisao, "fim": c_fim}


def render(nome, params, dur, w, h, saida):
    f = CENAS[nome]
    G._escrever(lambda t: f(t, dur, w, h, params), max(1, round(dur * FPS)), w, h, saida)
