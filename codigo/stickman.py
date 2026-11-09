"""Bonecos palito (stickman) desenhados por código, para canais de histórias.

O boneco é um esqueleto 2D (quadril, tronco, cabeça, braços e pernas com dois segmentos) desenhado com traços
arredondados e suaves direto no quadro float32 (numba). As poses são ângulos em graus (0 = para baixo, positivo =
para a frente/direita); ciclos de caminhada e corrida são calculados.
"""
import math

import numpy as np
from numba import njit, prange

# proporções em frações da altura do boneco
PROP = {"cabeca": 0.105, "pescoco": 0.04, "tronco": 0.30, "braco": 0.17, "antebraco": 0.16, "coxa": 0.235, "canela": 0.235}


@njit(parallel=True, cache=True, fastmath=True)
def _k_tracos(q, segs, larg, r, g, b, alfa):
    """Desenha segmentos (x0, y0, x1, y1) com pontas redondas e borda suave."""
    H, W = q.shape[0], q.shape[1]
    n = segs.shape[0]
    x0 = max(0, int(min(segs[:, 0].min(), segs[:, 2].min()) - larg - 2))
    x1 = min(W, int(max(segs[:, 0].max(), segs[:, 2].max()) + larg + 3))
    y0 = max(0, int(min(segs[:, 1].min(), segs[:, 3].min()) - larg - 2))
    y1 = min(H, int(max(segs[:, 1].max(), segs[:, 3].max()) + larg + 3))
    meia = larg * 0.5
    for j in prange(y0, y1):
        py = j + 0.5
        for i in range(x0, x1):
            px = i + 0.5
            dmin = 1e9
            for k in range(n):
                ax, ay, bx, by = segs[k, 0], segs[k, 1], segs[k, 2], segs[k, 3]
                vx, vy = bx - ax, by - ay
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 < 1e-9 else ((px - ax) * vx + (py - ay) * vy) / l2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                dx, dy = px - ax - t * vx, py - ay - t * vy
                d = math.sqrt(dx * dx + dy * dy)
                if d < dmin:
                    dmin = d
            k_ = meia + 0.5 - dmin
            if k_ <= 0:
                continue
            a = (1.0 if k_ > 1 else k_) * alfa
            q[j, i, 0] = q[j, i, 0] * (1 - a) + r * a
            q[j, i, 1] = q[j, i, 1] * (1 - a) + g * a
            q[j, i, 2] = q[j, i, 2] * (1 - a) + b * a


@njit(parallel=True, cache=True, fastmath=True)
def _k_disco(q, cx, cy, raio, r, g, b, alfa, borda, br, bg, bb):
    H, W = q.shape[0], q.shape[1]
    for j in prange(max(0, int(cy - raio - 2)), min(H, int(cy + raio + 3))):
        for i in range(max(0, int(cx - raio - 2)), min(W, int(cx + raio + 3))):
            d = math.sqrt((i + 0.5 - cx) ** 2 + (j + 0.5 - cy) ** 2)
            k = raio + 0.5 - d
            if k <= 0:
                continue
            a = (1.0 if k > 1 else k) * alfa
            if borda > 0 and d > raio - borda:
                cr, cg, cb = br, bg, bb
            else:
                cr, cg, cb = r, g, b
            q[j, i, 0] = q[j, i, 0] * (1 - a) + cr * a
            q[j, i, 1] = q[j, i, 1] * (1 - a) + cg * a
            q[j, i, 2] = q[j, i, 2] * (1 - a) + cb * a


def _p(x, y, ang, comp):
    a = math.radians(ang)
    return x + math.sin(a) * comp, y + math.cos(a) * comp


def pose_caminhar(fase, velocidade=1.0):
    """Ciclo de caminhada (fase 0 a 1). velocidade > 1 vira corrida (passos e braços maiores)."""
    s = math.sin(2 * math.pi * fase)
    c = math.cos(2 * math.pi * fase)
    k = min(1.6, velocidade)
    return {"tronco": 4 * k, "cabeca": 2 * k,
            "braco_e": (-28 * k * s, 25 + 20 * k * max(0.0, -s)), "braco_d": (28 * k * s, 25 + 20 * k * max(0.0, s)),
            "perna_e": (26 * k * s, -10 - 40 * k * max(0.0, c)), "perna_d": (-26 * k * s, -10 - 40 * k * max(0.0, -c)),
            "pulo": abs(c) * 0.012 * k}


POSES = {
    "parado": {"tronco": 0, "cabeca": 0, "braco_e": (-10, 5), "braco_d": (10, -5), "perna_e": (-6, 0), "perna_d": (6, 0)},
    "medo": {"tronco": -8, "cabeca": -10, "braco_e": (-35, 120), "braco_d": (35, -120), "perna_e": (-14, 12), "perna_d": (10, -8)},
    "lanterna": {"tronco": 3, "cabeca": 6, "braco_e": (-8, 10), "braco_d": (70, 20), "perna_e": (-6, 0), "perna_d": (8, 0)},
    "agachado": {"tronco": 25, "cabeca": 10, "braco_e": (30, 60), "braco_d": (40, 50), "perna_e": (60, -110), "perna_d": (40, -100)},
    "bracos_alto": {"tronco": 0, "cabeca": -5, "braco_e": (-160, 10), "braco_d": (160, -10), "perna_e": (-8, 0), "perna_d": (8, 0)},
}


def esqueleto(x, y, altura, pose, virado=1):
    """Pontos do boneco. (x, y) = pés no chão; virado = 1 (olha para a direita) ou -1."""
    P = {k: v * altura for k, v in PROP.items()}
    pulo = pose.get("pulo", 0.0) * altura
    quadril = (x, y - P["coxa"] - P["canela"] - pulo)

    def ang(a):
        return a * virado

    topo = _p(*quadril, 180 + ang(pose.get("tronco", 0)), P["tronco"])
    pesc = _p(*topo, 180 + ang(pose.get("tronco", 0) + pose.get("cabeca", 0)), P["pescoco"] + P["cabeca"])
    pts = {"quadril": quadril, "ombro": topo, "cabeca": pesc}
    for lado in ("e", "d"):
        a1, a2 = pose.get(f"braco_{lado}", (0, 0))
        cot = _p(*topo, ang(a1), P["braco"])
        mao = _p(*cot, ang(a1 + a2), P["antebraco"])
        pts[f"cotovelo_{lado}"], pts[f"mao_{lado}"] = cot, mao
        b1, b2 = pose.get(f"perna_{lado}", (0, 0))
        joe = _p(*quadril, ang(b1), P["coxa"])
        pe = _p(*joe, ang(b1 + b2), P["canela"])
        pts[f"joelho_{lado}"], pts[f"pe_{lado}"] = joe, pe
    return pts


def desenhar(q, x, y, altura, pose, cor=(0.95, 0.95, 0.97), virado=1, olhos=None, alfa=1.0, espessura=0.045,
             cor_cabeca=None, contorno=None):
    """Desenha o boneco no quadro. olhos: None, 'normal', 'medo' ou 'brilho' (olhos brancos de criatura)."""
    pts = esqueleto(x, y, altura, pose, virado)
    larg = max(1.5, altura * espessura)
    segs = []
    for a, b in (("quadril", "ombro"), ("ombro", "cotovelo_e"), ("cotovelo_e", "mao_e"), ("ombro", "cotovelo_d"),
                 ("cotovelo_d", "mao_d"), ("quadril", "joelho_e"), ("joelho_e", "pe_e"), ("quadril", "joelho_d"),
                 ("joelho_d", "pe_d")):
        segs.append((*pts[a], *pts[b]))
    segs = np.array(segs, np.float64)
    if contorno is not None:
        _k_tracos(q, segs, larg + altura * 0.02, contorno[0], contorno[1], contorno[2], alfa)
    _k_tracos(q, segs, larg, cor[0], cor[1], cor[2], alfa)
    hx, hy = pts["cabeca"]
    rc = altura * PROP["cabeca"]
    cc = cor_cabeca or cor
    if contorno is not None:
        _k_disco(q, hx, hy, rc + altura * 0.01, contorno[0], contorno[1], contorno[2], alfa, 0, 0, 0, 0)
    _k_disco(q, hx, hy, rc, cc[0], cc[1], cc[2], alfa, 0, 0, 0, 0)
    if olhos:
        ex = rc * 0.38 * virado
        ey = -rc * 0.12
        ro = rc * (0.2 if olhos == "medo" else 0.14)
        for dx in (ex - rc * 0.32 * virado, ex + rc * 0.12 * virado):
            if olhos == "brilho":
                _k_disco(q, hx + dx, hy + ey, ro * 1.1, 1.0, 1.0, 1.0, alfa, 0, 0, 0, 0)
            else:
                _k_disco(q, hx + dx, hy + ey, ro, 0.06, 0.07, 0.1, alfa, 0, 0, 0, 0)
    return pts
