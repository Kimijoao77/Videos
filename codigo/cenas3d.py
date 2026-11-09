"""Cenas realistas do Fora de Órbita (v2), desenhadas por código com os planetas de planeta.py.

Cada cena é uma função cena(q, t, dur, p, ctx) que pinta o quadro inteiro q (float32 H×W×3) no instante t (segundos
desde o começo da batida, que dura dur). p são os parâmetros do roteiro; ctx tem W, H, T (tempo do vídeo) e idioma.
Posições e tamanhos no roteiro são frações da largura (x, r) e da altura (y) da tela.

Catálogo (os parâmetros de cada uma estão na própria função):
  sol        o Sol de perto; pode sumir (apaga) num instante
  terra      a Terra girando; luz do Sol pode apagar, gelo pode cobrir, Lua opcional
  lua        a Lua de perto; luz pode apagar
  luz_viaja  a última luz saindo de onde estava o Sol até a Terra (com o tempo de viagem)
  orbita     vista de cima: a Terra em volta do Sol; o Sol some e a Terra sai pela tangente
  fonte      fundo do mar: fonte hidrotermal com brilho e partículas subindo
  planeta    qualquer corpo de planeta.CORPOS girando (marte, jupiter, saturno, venus, mercurio, netuno, urano)
"""
import math

import numpy as np

import efeitos as FX
import planeta as PL
from efeitos import entre, mistura, sai, suave


def _v(p, k, padrao):
    v = p.get(k, padrao)
    return padrao if v is None else v


def _curva(p, nome, t, dur, padrao):
    """Valor que muda no tempo: p[nome] pode ser um número ou [inicio, fim]; p[nome + '_t'] = [t0, t1] em frações
    da batida (padrão: a batida toda), com curva suave."""
    v = p.get(nome, padrao)
    if not isinstance(v, (list, tuple)):
        return float(v)
    t0, t1 = p.get(nome + "_t", [0.0, 1.0])
    return mistura(float(v[0]), float(v[1]), suave(entre(t / max(dur, 1e-6), t0, t1)))


def _fundo(q, ctx, p, t, brilho=0.45):
    q[:] = PL.ceu(ctx["W"], ctx["H"], t=ctx["T"], brilho=_v(p, "ceu", brilho), angulo=_v(p, "ceu_angulo", -30.0),
                  centro=tuple(_v(p, "ceu_centro", (0.5, 0.5))), zoom=_curva(p, "ceu_zoom", t, 1.0, 0.0))


# ------------------------------------------------------------------ o Sol
def sol(q, t, dur, p, ctx):
    """p: r (raio, fração da largura; pode ser [ini, fim]), x, y, apaga (fração da batida em que some; None = não some),
    expo (brilho), giro (graus por segundo)."""
    W, H = ctx["W"], ctx["H"]
    _fundo(q, ctx, p, t, 0.32)
    r = _curva(p, "r", t, dur, 0.56) * W
    cx, cy = _v(p, "x", 0.5) * W, _v(p, "y", 0.44) * H
    escala, clarao, resto = 1.0, 0.0, 1.0
    if p.get("apaga") is not None:
        ta = float(p["apaga"]) * dur
        if t >= ta:
            u = (t - ta) / 0.32                                        # some em ~0,3 s, encolhendo e brilhando
            escala = max(0.0, 1.0 - sai(u, 2))
            clarao = 0.7 * math.exp(-((t - ta - 0.2) / 0.06) ** 2)      # clarão rápido no fim do sumiço
            resto = max(0.0, 1.0 - (t - ta) / 1.4)                     # o brilho que sobra apaga devagar
    if escala > 0.003:
        PL.desenhar(q, cx, cy, r * escala, "sol", lon0=_v(p, "giro", 6.0) * ctx["T"], lat0=6, inclina=7,
                    exposicao=_v(p, "expo", 1.2) * (1 + 1.5 * (1 - escala)))
        FX.raio(q, cx, cy, W * 0.9, altura=3.0 + 4 * escala, cor=(1.0, 0.72, 0.42), forca=0.25 * escala)
    if resto > 0 and escala < 1:
        FX.brilho(q, cx, cy, r * 0.25 * resto + 2, cor=(1.0, 0.85, 0.65), forca=0.9 * resto, nucleo=1.5)
    if clarao > 0.01:
        q += clarao


# ------------------------------------------------------------------ a Terra
def terra(q, t, dur, p, ctx):
    """p: r, x, y (podem ser [ini, fim]); lon0 (longitude no centro), vel (graus por segundo), lat0, inclina,
    sol [x, y, z] (de onde vem a luz), luz (1 = Sol normal; [1, 0] apaga, com luz_t), noite (luzes das cidades),
    gelo ([0, 1] cobre de gelo, com gelo_t), aro (contorno azul quando escuro), lua {x, y, r, luz} (opcional),
    nuvens (0 a 1)."""
    W, H = ctx["W"], ctx["H"]
    _fundo(q, ctx, p, t)
    r = _curva(p, "r", t, dur, 0.42) * W
    cx = _curva(p, "x", t, dur, 0.5) * W
    cy = _curva(p, "y", t, dur, 0.45) * H
    luz = _curva(p, "luz", t, dur, 1.0)
    gelo = _curva(p, "gelo", t, dur, 0.0)
    lua = p.get("lua")
    if lua:                                                         # a Lua atrás (desenhada antes se estiver longe)
        lr = _curva(lua, "r", t, dur, 0.08) * W
        lx, ly = _curva(lua, "x", t, dur, 0.8) * W, _curva(lua, "y", t, dur, 0.18) * H
        PL.desenhar(q, lx, ly, lr, "lua", lon0=10, lat0=0, inclina=0, sol=tuple(_v(p, "sol", (-0.7, 0.35, 0.6))),
                    exposicao=_curva(lua, "luz", t, dur, luz))
    PL.desenhar(q, cx, cy, r, "terra", lon0=_v(p, "lon0", -35.0) - _v(p, "vel", 1.6) * t, lat0=_v(p, "lat0", 16.0),
                inclina=_v(p, "inclina", 18.0), sol=tuple(_v(p, "sol", (-0.7, 0.35, 0.6))),
                giro_nuvens=0.25 * ctx["T"], exposicao=luz, noite_k=_curva(p, "noite", t, dur, 1.0),
                nuvens_k=_v(p, "nuvens", 1.0) * (1 - gelo),
                mistura=PL.gelo() if gelo > 0.001 else None, mistura_k=gelo, mistura_brilho=0.0,
                aro=_curva(p, "aro", t, dur, 0.0))


# ------------------------------------------------------------------ a Lua
def lua(q, t, dur, p, ctx):
    """p: r, x, y, luz ([1, 0] apaga, com luz_t), sol, lon0, vel."""
    W, H = ctx["W"], ctx["H"]
    _fundo(q, ctx, p, t, 0.38)
    PL.desenhar(q, _curva(p, "x", t, dur, 0.5) * W, _curva(p, "y", t, dur, 0.44) * H, _curva(p, "r", t, dur, 0.4) * W,
                "lua", lon0=_v(p, "lon0", 0.0) - _v(p, "vel", 1.0) * t, lat0=_v(p, "lat0", 4.0), inclina=_v(p, "inclina", 6.0),
                sol=tuple(_v(p, "sol", (-0.75, 0.3, 0.55))), exposicao=_curva(p, "luz", t, dur, 1.0),
                aro=_curva(p, "aro", t, dur, 0.0))


# ------------------------------------------------------------------ planeta qualquer
def planeta(q, t, dur, p, ctx):
    """p: corpo (marte, jupiter, saturno...), r, x, y, lon0, vel, lat0, inclina, sol, luz, aneis (true/false)."""
    W, H = ctx["W"], ctx["H"]
    _fundo(q, ctx, p, t)
    PL.desenhar(q, _curva(p, "x", t, dur, 0.5) * W, _curva(p, "y", t, dur, 0.45) * H, _curva(p, "r", t, dur, 0.38) * W,
                _v(p, "corpo", "marte"), lon0=_v(p, "lon0", 0.0) - _v(p, "vel", 2.0) * t, lat0=_v(p, "lat0", 12.0),
                inclina=_v(p, "inclina", 12.0), sol=tuple(_v(p, "sol", (-0.7, 0.35, 0.6))),
                exposicao=_curva(p, "luz", t, dur, 1.0), aneis=_v(p, "aneis", None))


# ------------------------------------------------------------------ a última luz viajando
def luz_viaja(q, t, dur, p, ctx):
    """O lugar onde estava o Sol (em cima, à esquerda) e a Terra (embaixo, à direita). Uma frente de luz sai do Sol e
    chega na Terra no fim da batida (chega = fração). p: sol_x, sol_y, terra_x, terra_y, terra_r, chega."""
    W, H = ctx["W"], ctx["H"]
    _fundo(q, ctx, p, t, 0.4)
    sx, sy = _v(p, "sol_x", 0.2) * W, _v(p, "sol_y", 0.2) * H
    ex, ey, er = _v(p, "terra_x", 0.7) * W, _v(p, "terra_y", 0.55) * H, _v(p, "terra_r", 0.14) * W
    dist = math.hypot(ex - sx, ey - sy)
    chega = _v(p, "chega", 0.92)
    k = entre(t / dur, 0.0, chega)
    R = dist * k
    # fantasma de onde estava o Sol
    FX.brilho(q, sx, sy, 10, cor=(1.0, 0.8, 0.55), forca=0.25, nucleo=0.6)
    FX.anel(q, sx, sy, 14, largura=1.5, cor=(1.0, 0.82, 0.6), forca=0.5, tracos=5)
    # a Terra ainda iluminada (a luz ainda está chegando)
    direcao = ((sx - ex) / dist, -(sy - ey) / dist, 0.25)
    PL.desenhar(q, ex, ey, er, "terra", lon0=-30 - 2 * t, lat0=14, inclina=18, sol=direcao,
                giro_nuvens=0.25 * ctx["T"])
    # a frente de luz (anel que cresce)
    if 0 < k < 1:
        FX.anel(q, sx, sy, R, largura=3.0, cor=(1.0, 0.9, 0.72), forca=0.95, brilho_w=10.0)
        FX.anel(q, sx, sy, R * 0.985, largura=2.0, cor=(1.0, 0.8, 0.55), forca=0.35, brilho_w=24.0)
    # linha tracejada da distância
    FX.linha(q, (sx, sy), (ex - (ex - sx) / dist * er * 1.15, ey - (ey - sy) / dist * er * 1.15), largura=2.0,
             cor=(0.75, 0.85, 1.0), forca=0.55, tracos=9)


# ------------------------------------------------------------------ órbita vista de cima
def orbita(q, t, dur, p, ctx):
    """p: R (raio da órbita, fração da largura), x, y (centro), ang0 (graus), vel (graus por segundo), some (fração da
    batida em que o Sol some; None = não some), sol_r, terra_r."""
    W, H = ctx["W"], ctx["H"]
    _fundo(q, ctx, p, t, 0.4)
    cx, cy = _v(p, "x", 0.5) * W, _v(p, "y", 0.44) * H
    R = _v(p, "R", 0.36) * W
    ang0, vel = math.radians(_v(p, "ang0", 210.0)), math.radians(_v(p, "vel", 22.0))
    ts = p.get("some")
    ts = None if ts is None else float(ts) * dur

    def pos(tt):
        a = ang0 + vel * tt
        return cx + R * math.cos(a), cy - R * math.sin(a), a

    if ts is None or t < ts:
        ex, ey, a = pos(t)
        vivo = True
    else:
        sx0, sy0, a = pos(ts)                                          # segue reto pela tangente, mesma velocidade
        vx, vy = -math.sin(a) * R * vel, -math.cos(a) * R * vel
        ex, ey = sx0 + vx * (t - ts), sy0 + vy * (t - ts)
        vivo = False
    luz_sol = 1.0 if vivo else max(0.0, 1.0 - (t - ts) / 0.25)
    # órbita tracejada (fica fraca depois) e a marca de onde estava o Sol
    FX.anel(q, cx, cy, R, largura=2.2, cor=(0.7, 0.8, 1.0), forca=0.75 * (1.0 if vivo else max(0.35, luz_sol)), tracos=12,
            brilho_w=3.0)
    if not vivo:
        FX.anel(q, cx, cy, 18, largura=1.6, cor=(1.0, 0.82, 0.6), forca=0.55, tracos=5)
    sr = _v(p, "sol_r", 0.075) * W
    if luz_sol > 0:
        PL.desenhar(q, cx, cy, sr * (0.6 + 0.4 * luz_sol), "sol", lon0=8 * ctx["T"], lat0=4, inclina=5,
                    exposicao=1.2 * luz_sol, halo_k=luz_sol)
        FX.raio(q, cx, cy, W * 0.6, altura=2.5, cor=(1.0, 0.72, 0.42), forca=0.2 * luz_sol)
    if not vivo:
        clarao = math.exp(-((t - ts - 0.1) / 0.12) ** 2)
        if clarao > 0.01:
            FX.brilho(q, cx, cy, sr, cor=(1.0, 0.9, 0.75), forca=1.6 * clarao, nucleo=2)
        # rastro reto da Terra
        sx0, sy0, _ = pos(ts)
        FX.linha(q, (sx0, sy0), (ex, ey), largura=3.5, cor=(0.6, 0.8, 1.0), forca=1.0, brilho_w=10, desvanece=(0.05, 1.0))
    er = _v(p, "terra_r", 0.06) * W
    dx, dy = cx - ex, cy - ey
    dn = math.hypot(dx, dy) or 1.0
    PL.desenhar(q, ex, ey, er, "terra", lon0=-30 - 20 * t, lat0=10, inclina=20, sol=(dx / dn, -dy / dn, 0.2),
                exposicao=luz_sol, aro=0.0 if vivo else 1.1 * (1 - luz_sol), noite_k=1.6)


# ------------------------------------------------------------------ fundo do mar
def _semente(n, s):
    return np.random.default_rng(s).random((n, 6))


_ROCHA = {}


def _rocha(W, H, base_y):
    """Silhueta da chaminé hidrotermal e do fundo (máscara float H×W), feita uma vez."""
    chave = (W, H, int(base_y))
    if chave in _ROCHA:
        return _ROCHA[chave]
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    rnd = np.random.default_rng(4)
    # chão irregular
    pts = [(0, H)]
    for i in range(0, W + 60, 60):
        pts.append((i, base_y + 120 + rnd.uniform(-30, 30)))
    pts.append((W, H))
    d.polygon(pts, fill=255)
    # chaminé: tronco que afina para cima, com saliências
    topo = base_y - H * 0.16
    cx = W * 0.5
    lados = []
    n = 14
    for k in range(n + 1):
        y = topo + (base_y + 140 - topo) * k / n
        larg = W * (0.035 + 0.10 * (k / n) ** 1.6) + rnd.uniform(-8, 8)
        lados.append((cx - larg, y))
    dir_ = [(cx + (cx - x) + rnd.uniform(-10, 10), y) for x, y in lados]
    d.polygon(lados + dir_[::-1], fill=255)
    for _ in range(5):                                                 # chaminés menores dos lados
        bx = cx + rnd.uniform(-0.3, 0.3) * W
        bt = base_y - rnd.uniform(0.02, 0.08) * H
        d.polygon([(bx - 26, base_y + 150), (bx - 9, bt), (bx + 9, bt), (bx + 26, base_y + 150)], fill=255)
    m = np.asarray(im.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0
    _ROCHA[chave] = (m, topo)
    return _ROCHA[chave]


def fonte(q, t, dur, p, ctx):
    """Fonte hidrotermal no escuro do fundo do mar. p: zoom ([ini, fim])."""
    W, H = ctx["W"], ctx["H"]
    T = ctx["T"]
    q[:] = FX.gradiente(H, W, (0.0, 0.035, 0.075), (0.0, 0.004, 0.01), meio=(0.0, 0.016, 0.035))
    base_y = H * 0.74
    m, topo = _rocha(W, H, base_y)
    vx, vy = W * 0.5, topo + 8
    pulso = 0.85 + 0.15 * math.sin(T * 2.3) * math.sin(T * 1.1 + 1)
    # brilho quente da boca da chaminé (atrás da fumaça)
    FX.brilho(q, vx, vy, W * 0.05, cor=(1.0, 0.6, 0.3), forca=1.4 * pulso, nucleo=1.6)
    FX.brilho(q, vx, vy - H * 0.06, W * 0.22, cor=(0.30, 0.42, 0.62), forca=0.3, nucleo=0.3)
    FX.coluna(q, vx, vy, W * 0.022, H * 0.12, cor=(1.0, 0.62, 0.34), forca=0.55 * pulso)
    FX.coluna(q, vx, vy - 10, W * 0.05, H * 0.22, cor=(0.35, 0.5, 0.75), forca=0.12)
    # pluma: partículas quentes subindo e esfriando
    n = 900
    s = _semente(n, 9)
    vida = 3.2 + s[:, 0] * 2.5
    fase = (T / vida + s[:, 1]) % 1.0
    subida = fase * H * (0.42 + 0.2 * s[:, 2])
    abre = (fase ** 0.8) * W * (0.03 + 0.09 * s[:, 3])
    xs = vx + np.sin(T * (0.6 + s[:, 4]) + s[:, 5] * 6.28) * abre + (s[:, 3] - 0.5) * abre * 1.4
    ys = vy - subida
    quente = (1 - fase) ** 2
    cores = np.stack([0.55 + 0.45 * quente, 0.45 + 0.25 * quente, 0.42 - 0.15 * quente], 1)
    FX.particulas(q, xs, ys, 1.8 + 4.5 * fase * s[:, 2], cores, 0.32 * (1 - fase) * (0.4 + 0.6 * s[:, 0]))
    # neve marinha e pontos bioluminescentes (azul-gelo) flutuando
    n2 = 260
    s2 = _semente(n2, 17)
    xs2 = (s2[:, 0] * W + np.sin(T * 0.3 + s2[:, 1] * 6.28) * 20) % W
    ys2 = (s2[:, 2] * H + T * (8 + 14 * s2[:, 3])) % H
    cores2 = np.tile(np.array([[0.55, 0.85, 1.0]]), (n2, 1))
    pisca = 0.5 + 0.5 * np.sin(T * (1 + 2 * s2[:, 4]) + s2[:, 5] * 6.28)
    FX.particulas(q, xs2, ys2, 1.2 + 2.2 * s2[:, 4], cores2, 0.10 + 0.45 * pisca * (s2[:, 5] > 0.6))
    # rocha por cima, com a borda iluminada pelo brilho
    rocha = np.array([0.008, 0.011, 0.016], np.float32)
    q *= (1 - m)[..., None]
    q += m[..., None] * rocha
    ys_, xs_ = np.ogrid[0:H, 0:W]
    d2 = ((xs_ - vx) / (W * 0.07)) ** 2 + ((ys_ - vy) / (H * 0.035)) ** 2
    q += (m * np.exp(-d2) * 0.7 * pulso)[..., None] * np.array([1.0, 0.55, 0.3], np.float32)


CENAS = {"sol": sol, "terra": terra, "lua": lua, "luz_viaja": luz_viaja, "orbita": orbita, "fonte": fonte,
         "planeta": planeta}
