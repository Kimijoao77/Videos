"""Efeitos 2D para os quadros float32 (H×W×3), compilados com numba: brilhos, anéis e linhas suaves, partículas,
raio anamórfico (lens flare), gradientes. Tudo é somado ou misturado direto no quadro.
"""
import math

import numpy as np
from numba import njit, prange


@njit(parallel=True, cache=True, fastmath=True)
def _k_brilho(q, x, y, raio, r, g, b, forca, nucleo):
    """Brilho radial somado: núcleo forte (gaussiano) e halo largo (1/d²)."""
    H, W = q.shape[0], q.shape[1]
    alcance = raio * 6.0
    y0, y1 = max(0, int(y - alcance)), min(H, int(y + alcance) + 1)
    x0, x1 = max(0, int(x - alcance)), min(W, int(x + alcance) + 1)
    for j in prange(y0, y1):
        dy = (j + 0.5 - y) / raio
        for i in range(x0, x1):
            dx = (i + 0.5 - x) / raio
            d2 = dx * dx + dy * dy
            k = (math.exp(-d2 * 4.0) * nucleo + 0.06 / (0.06 + d2) * (1.0 - min(1.0, d2 / 36.0))) * forca
            q[j, i, 0] += r * k
            q[j, i, 1] += g * k
            q[j, i, 2] += b * k


def brilho(q, x, y, raio, cor=(1.0, 0.95, 0.85), forca=1.0, nucleo=1.0):
    if raio > 0.3 and forca > 0:
        _k_brilho(q, float(x), float(y), float(raio), cor[0], cor[1], cor[2], float(forca), float(nucleo))


@njit(parallel=True, cache=True, fastmath=True)
def _k_anel(q, cx, cy, R, w, r, g, b, forca, ang0, ang1, tracos, brilho_w):
    H, W = q.shape[0], q.shape[1]
    alc = w * 0.5 + brilho_w * 3 + 2
    y0, y1 = max(0, int(cy - R - alc)), min(H, int(cy + R + alc) + 1)
    x0, x1 = max(0, int(cx - R - alc)), min(W, int(cx + R + alc) + 1)
    pi2 = 2.0 * math.pi
    for j in prange(y0, y1):
        for i in range(x0, x1):
            dx = i + 0.5 - cx
            dy = j + 0.5 - cy
            d = math.sqrt(dx * dx + dy * dy)
            e = abs(d - R)
            if e > alc:
                continue
            a = math.atan2(-dy, dx)
            if a < 0:
                a += pi2
            # dentro do arco [ang0, ang1] (radianos, sentido anti-horário a partir da direita)
            aa = a - ang0
            aa -= math.floor(aa / pi2) * pi2
            if aa > (ang1 - ang0):
                continue
            if tracos > 0:
                fase = (a * R / tracos) % 2.0
                if fase > 1.0:
                    continue
            k = max(0.0, min(1.0, w * 0.5 + 0.5 - e))
            if brilho_w > 0:
                k += math.exp(-(e / brilho_w) ** 2) * 0.35
            k *= forca
            q[j, i, 0] = q[j, i, 0] * (1 - min(k, 1.0)) + r * k
            q[j, i, 1] = q[j, i, 1] * (1 - min(k, 1.0)) + g * k
            q[j, i, 2] = q[j, i, 2] * (1 - min(k, 1.0)) + b * k


def anel(q, cx, cy, R, largura=2.0, cor=(1, 1, 1), forca=1.0, ang0=0.0, ang1=2 * math.pi, tracos=0.0, brilho_w=0.0):
    """Círculo (ou arco de ang0 a ang1, radianos) suave. tracos: tamanho do traço em pixels (0 = contínuo)."""
    if R > 0 and forca > 0:
        _k_anel(q, float(cx), float(cy), float(R), float(largura), cor[0], cor[1], cor[2], float(forca),
                float(ang0), float(ang1), float(tracos), float(brilho_w))


@njit(parallel=True, cache=True, fastmath=True)
def _k_linha(q, ax, ay, bx, by, w, r, g, b, forca, tracos, brilho_w, f0, f1):
    H, W = q.shape[0], q.shape[1]
    alc = w * 0.5 + brilho_w * 3 + 2
    y0, y1 = max(0, int(min(ay, by) - alc)), min(H, int(max(ay, by) + alc) + 1)
    x0, x1 = max(0, int(min(ax, bx) - alc)), min(W, int(max(ax, bx) + alc) + 1)
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy + 1e-9
    L = math.sqrt(L2)
    for j in prange(y0, y1):
        for i in range(x0, x1):
            px, py = i + 0.5 - ax, j + 0.5 - ay
            t = (px * vx + py * vy) / L2
            if t < 0.0 or t > 1.0:
                continue
            dx, dy = px - t * vx, py - t * vy
            e = math.sqrt(dx * dx + dy * dy)
            if e > alc:
                continue
            if tracos > 0 and ((t * L / tracos) % 2.0) > 1.0:
                continue
            k = max(0.0, min(1.0, w * 0.5 + 0.5 - e))
            if brilho_w > 0:
                k += math.exp(-(e / brilho_w) ** 2) * 0.35
            k *= forca * (f0 + (f1 - f0) * t)
            q[j, i, 0] = q[j, i, 0] * (1 - min(k, 1.0)) + r * k
            q[j, i, 1] = q[j, i, 1] * (1 - min(k, 1.0)) + g * k
            q[j, i, 2] = q[j, i, 2] * (1 - min(k, 1.0)) + b * k


def linha(q, a, b, largura=2.0, cor=(1, 1, 1), forca=1.0, tracos=0.0, brilho_w=0.0, desvanece=(1.0, 1.0)):
    """Segmento suave de a até b (pixels). desvanece: força no começo e no fim (rastro que some)."""
    _k_linha(q, float(a[0]), float(a[1]), float(b[0]), float(b[1]), float(largura), cor[0], cor[1], cor[2],
             float(forca), float(tracos), float(brilho_w), float(desvanece[0]), float(desvanece[1]))


@njit(parallel=True, cache=True, fastmath=True)
def _k_particulas(q, xs, ys, rs, cs, ks):
    H, W = q.shape[0], q.shape[1]
    n = xs.shape[0]
    # cada partícula num laço; partículas pequenas: custo baixo mesmo com milhares
    for p in prange(n):
        x, y, rr, kk = xs[p], ys[p], rs[p], ks[p]
        if kk <= 0 or rr <= 0:
            continue
        alc = rr * 3.0 + 1
        y0, y1 = max(0, int(y - alc)), min(H, int(y + alc) + 1)
        x0, x1 = max(0, int(x - alc)), min(W, int(x + alc) + 1)
        for j in range(y0, y1):
            dy = (j + 0.5 - y) / rr
            for i in range(x0, x1):
                dx = (i + 0.5 - x) / rr
                k = math.exp(-(dx * dx + dy * dy) * 1.6) * kk
                q[j, i, 0] += cs[p, 0] * k
                q[j, i, 1] += cs[p, 1] * k
                q[j, i, 2] += cs[p, 2] * k


def particulas(q, xs, ys, raios, cores, forcas):
    """Pontos de luz somados (bolhas, faíscas, poeira). cores: N×3."""
    if len(xs):
        _k_particulas(q, np.asarray(xs, np.float64), np.asarray(ys, np.float64), np.asarray(raios, np.float64),
                      np.ascontiguousarray(cores, np.float64), np.asarray(forcas, np.float64))


@njit(parallel=True, cache=True, fastmath=True)
def _k_raio(q, x, y, comp, alt, r, g, b, forca):
    """Raio anamórfico horizontal (o traço de luz das câmeras de cinema)."""
    H, W = q.shape[0], q.shape[1]
    y0, y1 = max(0, int(y - alt * 4)), min(H, int(y + alt * 4) + 1)
    for j in prange(y0, y1):
        dy = (j + 0.5 - y) / alt
        fy = math.exp(-dy * dy)
        for i in range(W):
            dx = abs(i + 0.5 - x) / comp
            k = fy * math.exp(-dx * 3.0) * forca
            q[j, i, 0] += r * k
            q[j, i, 1] += g * k
            q[j, i, 2] += b * k


def raio(q, x, y, comprimento, altura=2.0, cor=(0.55, 0.75, 1.0), forca=0.6):
    if forca > 0:
        _k_raio(q, float(x), float(y), float(comprimento), float(altura), cor[0], cor[1], cor[2], float(forca))


def gradiente(h, w, topo, base, meio=None):
    """Fundo em degradê vertical (float32)."""
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    a, b = np.array(topo, np.float32), np.array(base, np.float32)
    if meio is not None:
        m = np.array(meio, np.float32)
        g = np.where(t < 0.5, a + (m - a) * (t * 2), m + (b - m) * ((t - 0.5) * 2))
    else:
        g = a + (b - a) * t
    return np.ascontiguousarray(np.broadcast_to(g, (h, w, 3)).astype(np.float32))


# ---------------------------------------------------------------- curvas de tempo
def suave(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def sai(x, p=3):
    """Começa rápido e termina devagar."""
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** p


def entra(x, p=3):
    x = min(1.0, max(0.0, x))
    return x ** p


def entre(t, a, b):
    """Progresso 0 a 1 de t entre a e b."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return min(1.0, max(0.0, (t - a) / (b - a)))


def mistura(a, b, k):
    return a + (b - a) * k


@njit(parallel=True, cache=True, fastmath=True)
def _k_coluna(q, x, y, largura, altura, r, g, b, forca):
    """Coluna de luz que sobe de (x, y) e some com a altura (pluma, feixe)."""
    H, W = q.shape[0], q.shape[1]
    y0 = max(0, int(y - altura * 4))
    x0, x1 = max(0, int(x - largura * 4)), min(W, int(x + largura * 4) + 1)
    for j in prange(y0, min(H, int(y) + 1)):
        sobe = (y - j) / altura
        larg = largura * (1.0 + sobe * 0.8)
        fy = math.exp(-sobe)
        for i in range(x0, x1):
            dx = (i + 0.5 - x) / larg
            k = math.exp(-dx * dx) * fy * forca
            q[j, i, 0] += r * k
            q[j, i, 1] += g * k
            q[j, i, 2] += b * k


def coluna(q, x, y, largura, altura, cor=(1.0, 0.6, 0.3), forca=0.5):
    if forca > 0:
        _k_coluna(q, float(x), float(y), float(largura), float(altura), cor[0], cor[1], cor[2], float(forca))


@njit(parallel=True, cache=True, fastmath=True)
def _k_zoom(src, dst, s, cx, cy):
    H, W = src.shape[0], src.shape[1]
    for j in prange(H):
        fy = cy + (j + 0.5 - cy) / s - 0.5
        iy = int(math.floor(fy))
        ay = fy - iy
        iy = min(max(iy, 0), H - 2)
        for i in range(W):
            fx = cx + (i + 0.5 - cx) / s - 0.5
            ix = int(math.floor(fx))
            ax = fx - ix
            ix = min(max(ix, 0), W - 2)
            for c in range(3):
                dst[j, i, c] = (src[iy, ix, c] * (1 - ax) + src[iy, ix + 1, c] * ax) * (1 - ay) + \
                               (src[iy + 1, ix, c] * (1 - ax) + src[iy + 1, ix + 1, c] * ax) * ay


def zoom(q, s, cx=None, cy=None):
    """Aproxima o quadro inteiro (s > 1) em volta de (cx, cy); devolve um quadro novo."""
    if abs(s - 1) < 1e-4:
        return q
    H, W = q.shape[:2]
    out = np.empty_like(q)
    _k_zoom(q, out, float(s), float(W / 2 if cx is None else cx), float(H / 2 if cy is None else cy))
    return out


@njit(parallel=True, cache=True, fastmath=True)
def _k_fumaca(q, xs, ys, rs, r, g, b, alfas):
    """Manchas suaves MISTURADAS no quadro (fumaça, poeira escura): cada uma puxa a cor para (r, g, b) com alfa gaussiano."""
    H, W = q.shape[0], q.shape[1]
    n = xs.shape[0]
    for p in range(n):
        x, y, rr, aa = xs[p], ys[p], rs[p], alfas[p]
        if aa <= 0 or rr <= 0:
            continue
        alc = rr * 2.2 + 1
        y0, y1 = max(0, int(y - alc)), min(H, int(y + alc) + 1)
        x0, x1 = max(0, int(x - alc)), min(W, int(x + alc) + 1)
        for j in prange(y0, y1):
            dy = (j + 0.5 - y) / rr
            for i in range(x0, x1):
                dx = (i + 0.5 - x) / rr
                k = math.exp(-(dx * dx + dy * dy) * 1.2) * aa
                q[j, i, 0] += (r - q[j, i, 0]) * k
                q[j, i, 1] += (g - q[j, i, 1]) * k
                q[j, i, 2] += (b - q[j, i, 2]) * k


def fumaca(q, xs, ys, raios, cor, alfas):
    """Fumaça/neblina em manchas: mistura (não soma) a cor no quadro."""
    if len(xs):
        _k_fumaca(q, np.asarray(xs, np.float64), np.asarray(ys, np.float64), np.asarray(raios, np.float64),
                  float(cor[0]), float(cor[1]), float(cor[2]), np.asarray(alfas, np.float64))


@njit(parallel=True, cache=True, fastmath=True)
def _k_chuva(q, xs, ys, dx, dy, comp, larg, r, g, b, alfa):
    """Gotas de chuva: traços finos e inclinados, misturados no quadro."""
    H, W = q.shape[0], q.shape[1]
    n = xs.shape[0]
    for p in prange(n):
        ax, ay = xs[p], ys[p]
        bx, by = ax + dx * comp, ay + dy * comp
        x0, x1 = max(0, int(min(ax, bx) - larg - 1)), min(W, int(max(ax, bx) + larg + 2))
        y0, y1 = max(0, int(min(ay, by) - larg - 1)), min(H, int(max(ay, by) + larg + 2))
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy + 1e-6
        for j in range(y0, y1):
            for i in range(x0, x1):
                px, py = i + 0.5 - ax, j + 0.5 - ay
                s = (px * vx + py * vy) / L2
                if s < 0.0 or s > 1.0:
                    continue
                ex, ey = px - s * vx, py - s * vy
                d = math.sqrt(ex * ex + ey * ey)
                if d >= larg:
                    continue
                k = (1.0 - d / larg) * alfa * (0.4 + 0.6 * s)
                q[j, i, 0] += (r - q[j, i, 0]) * k
                q[j, i, 1] += (g - q[j, i, 1]) * k
                q[j, i, 2] += (b - q[j, i, 2]) * k


def chuva(q, t, n=520, angulo=12.0, vel=1500.0, comp=34.0, larg=1.2, cor=(0.78, 0.82, 0.88), alfa=0.45, semente=3, u=1.0):
    """Chuva caindo inclinada, contínua no tempo (cada gota volta ao topo)."""
    H, W = q.shape[:2]
    s = np.random.default_rng(semente).random((n, 3))
    a = math.radians(angulo)
    dx, dy = math.sin(a), math.cos(a)
    v = vel * u * (0.8 + 0.4 * s[:, 2])
    ys = (s[:, 1] * (H + 200 * u) + t * v) % (H + 200 * u) - 100 * u
    xs = (s[:, 0] * (W + 300 * u) + ys * math.tan(a)) % (W + 300 * u) - 150 * u
    _k_chuva(q, xs.astype(np.float64), ys.astype(np.float64), dx, dy, comp * u, larg * u, float(cor[0]), float(cor[1]),
             float(cor[2]), float(alfa))
