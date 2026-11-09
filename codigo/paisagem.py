"""Paisagens ilustradas em camadas, desenhadas por código (nada de imagem pronta ou gerada por IA).

Uma paisagem é uma pilha de faixas de trás pra frente: céu → astros → nuvens → morros e florestas (com névoa entre
elas) → mar → reflexos → primeiro plano. Cada faixa tem profundidade p (0 = horizonte, 1 = colada na câmera): a câmera
desloca e aproxima cada faixa na proporção de p (paralaxe), e as faixas de trás ficam mais claras e azuladas
(perspectiva atmosférica, feita pela cor que a cena escolhe e pela névoa).

A água é chapada, no estilo de ilustração: uma faixa de superfície com cristas pequenas que andam e balançam, o corpo
em degradê (turquesa → azul fundo), listras de luz compridas que deslizam, raios de luz descendo da superfície e, à
noite, o reflexo da lua em traços horizontais que tremem.

Perfis (contornos) são vetores com o y do topo de cada coluna, no "mundo" (a tela com zoom 1), com margem dos lados
(MARGEM) para a câmera poder andar sem acabar o desenho.
"""
import math
from functools import lru_cache

import numpy as np
from numba import njit, prange

import efeitos as FX

TEX = 256
MARGEM = 0.35          # sobra de cada lado dos perfis, em fração da largura
LONGE = 1e9            # topo "sem nada" (coluna vazia)


# ------------------------------------------------------------------ ruídos
@lru_cache(maxsize=8)
def textura(semente=1, beta=1.5):
    """Ruído contínuo e repetível (TEX×TEX, de −1 a 1), para variar a cor das faixas e desenhar a névoa."""
    rnd = np.random.default_rng(semente)
    f = np.fft.fftfreq(TEX)
    k = np.sqrt(f[None, :] ** 2 + f[:, None] ** 2)
    k[0, 0] = 1.0
    esp = np.fft.fft2(rnd.normal(size=(TEX, TEX))) / k ** beta
    esp[0, 0] = 0
    t = np.real(np.fft.ifft2(esp))
    return (t / np.abs(t).max()).astype(np.float32)


def ruido1d(n, escala, semente, oitavas=4):
    """fBm 1D (de −1 a 1): soma de ruídos suaves, o primeiro com um ponto a cada `escala` pixels."""
    rnd = np.random.default_rng(semente)
    out = np.zeros(n, np.float64)
    amp, tot = 1.0, 0.0
    for o in range(oitavas):
        passo = max(2.0, escala / 2 ** o)
        pts = rnd.uniform(-1, 1, int(n / passo) + 3)
        xs = np.arange(n) / passo
        i = np.floor(xs).astype(int)
        fr = (1 - np.cos((xs - i) * np.pi)) / 2
        out += amp * (pts[i] * (1 - fr) + pts[i + 1] * fr)
        tot += amp
        amp *= 0.5
    return out / tot


@njit(inline="always", fastmath=True)
def _amostra(tex, u, v):
    T = tex.shape[0]
    fu = math.floor(u)
    fv = math.floor(v)
    du = u - fu
    dv = v - fv
    i0 = int(fu) % T
    j0 = int(fv) % T
    i1 = (i0 + 1) % T
    j1 = (j0 + 1) % T
    a = tex[j0, i0] * (1.0 - du) + tex[j0, i1] * du
    b = tex[j1, i0] * (1.0 - du) + tex[j1, i1] * du
    return a * (1.0 - dv) + b * dv


# ------------------------------------------------------------------ núcleos (numba)
@njit(parallel=True, cache=True, fastmath=True)
def _k_faixa(q, topo, base, ya, yb, ca, cb, rim, rim_w, rim_b, rim_bw, luz_x, luz_k, tex, tex_k, tex_esc, ox, oy, alfa):
    """Preenche entre o contorno de cima (topo, W+1 valores nas bordas dos pixels) e o de baixo (base).
    Cor em degradê vertical (ca em ya → cb em yb), textura, luz de contorno no topo (mais forte nas encostas viradas
    para a luz) e, se pedido, na base. Borda suavizada pela fração da coluna coberta."""
    H, W = q.shape[0], q.shape[1]
    for x in prange(W):
        a = topo[x]
        b = topo[x + 1]
        lo = min(a, b)
        hi = max(a, b)
        dh = hi - lo
        mid = 0.5 * (a + b)
        ba = 0.5 * (base[x] + base[x + 1])
        if ba <= lo or lo > H:
            continue
        y_ini = max(0, int(math.floor(lo)) - 1)
        y_fim = min(H, int(math.ceil(ba)) + 1)
        dirx = 1.0 if luz_x > x else -1.0
        rk = 1.0 + luz_k * max(-1.0, min(1.0, (b - a) * dirx * 0.35))
        if rk < 0.0:
            rk = 0.0
        for y in range(y_ini, y_fim):
            yc = y + 0.5
            if dh > 1.0:
                cov = (yc - lo) / dh
            else:
                cov = yc - mid + 0.5
            if cov <= 0.0:
                continue
            if cov > 1.0:
                cov = 1.0
            cbx = ba - y
            if cbx <= 0.0:
                continue
            if cbx < 1.0:
                cov *= cbx
            f = (yc - ya) / (yb - ya) if yb != ya else 0.0
            if f < 0.0:
                f = 0.0
            elif f > 1.0:
                f = 1.0
            r = ca[0] + (cb[0] - ca[0]) * f
            g = ca[1] + (cb[1] - ca[1]) * f
            bl = ca[2] + (cb[2] - ca[2]) * f
            if tex_k != 0.0:
                tv = 1.0 + tex_k * _amostra(tex, x * tex_esc + ox, y * tex_esc + oy)
                r *= tv
                g *= tv
                bl *= tv
            if rim_w > 0.0:
                d = yc - mid
                if d < rim_w * 4.0:
                    k = math.exp(-max(d, 0.0) / rim_w) * rk
                    r += rim[0] * k
                    g += rim[1] * k
                    bl += rim[2] * k
            if rim_bw > 0.0:
                d2 = ba - yc
                if d2 < rim_bw * 4.0:
                    k = math.exp(-max(d2, 0.0) / rim_bw)
                    r += rim_b[0] * k
                    g += rim_b[1] * k
                    bl += rim_b[2] * k
            al = alfa * cov
            q[y, x, 0] += (r - q[y, x, 0]) * al
            q[y, x, 1] += (g - q[y, x, 1]) * al
            q[y, x, 2] += (bl - q[y, x, 2]) * al


@njit(parallel=True, cache=True, fastmath=True)
def _k_agua_det(q, frente, t, tex, lis_cor, lis_k, lis_prof, lis_vel, rx, rw, rk, r_incl, r_prof, r_cor,
                luz_x, luz_larg, luz_cor, luz_k):
    """Detalhes da água chapada, abaixo da linha `frente`: listras de luz compridas que deslizam, raios de luz
    descendo da superfície (rx, rw, rk por raio) e, se luz_k > 0, o reflexo da lua/sol em traços que tremem."""
    H, W = q.shape[0], q.shape[1]
    nr = rx.shape[0]
    for x in prange(W):
        ys = 0.5 * (frente[x] + frente[x + 1])
        if ys >= H:
            continue
        y0 = max(0, int(ys) + 1)
        for y in range(y0, H):
            d = y + 0.5 - ys
            r = 0.0
            g = 0.0
            b = 0.0
            if lis_k > 0.0:
                n = _amostra(tex, x * 0.045 + t * lis_vel, y * 0.55)
                k = (n - 0.22) / 0.2
                if k > 0.0:
                    if k > 1.0:
                        k = 1.0
                    k = k * k * lis_k * math.exp(-d / lis_prof)
                    r += lis_cor[0] * k
                    g += lis_cor[1] * k
                    b += lis_cor[2] * k
            if nr > 0:
                entra = min(1.0, d / 40.0)
                some = math.exp(-d / r_prof) * entra
                if some > 0.003:
                    for i in range(nr):
                        xc = rx[i] + d * r_incl
                        w = rw[i] * (1.0 + d * 0.004)
                        u = (x + 0.5 - xc) / w
                        if u * u < 9.0:
                            k = rk[i] * math.exp(-u * u) * some
                            r += r_cor[0] * k
                            g += r_cor[1] * k
                            b += r_cor[2] * k
            if luz_k > 0.0:
                lw = luz_larg * (1.0 + d * 0.012)
                u = (x + 0.5 - luz_x) / lw
                if u * u < 6.0:
                    n2 = _amostra(tex, x * 0.09 + 50.0 + t * 1.6, y * 0.9 + 30.0)
                    k = (n2 + 0.05) / 0.25
                    if k > 0.0:
                        if k > 1.0:
                            k = 1.0
                        k = k * math.exp(-u * u) * luz_k * math.exp(-d / (0.6 * H))
                        r += luz_cor[0] * k
                        g += luz_cor[1] * k
                        b += luz_cor[2] * k
            q[y, x, 0] += r
            q[y, x, 1] += g
            q[y, x, 2] += b


@njit(parallel=True, cache=True, fastmath=True)
def _k_reflexo(q, topo, horiz, alcance, cor, forca, t, amp, suave):
    """Reflexo na água de tudo que está acima do horizonte com o contorno `topo` (espelhado, ondulando)."""
    H, W = q.shape[0], q.shape[1]
    y0 = max(0, int(horiz))
    y1 = min(H, int(horiz + alcance) + 1)
    for y in prange(y0, y1):
        v = y + 0.5 - horiz
        if v <= 0.0:
            continue
        ym = horiz - v
        fade = 1.0 - v / alcance
        if fade <= 0.0:
            continue
        fade = fade ** 0.7
        ond = amp * (0.3 + v / alcance)
        for x in range(W):
            xs = x + 0.5 + ond * (math.sin(v * 0.45 - t * 2.1 + x * 0.013) + 0.5 * math.sin(v * 1.1 + t * 3.3 - x * 0.021))
            if xs < 0.0:
                xs = 0.0
            elif xs > W - 1.001:
                xs = W - 1.001
            i = int(xs)
            fx = xs - i
            tp = topo[i] * (1.0 - fx) + topo[i + 1] * fx
            cov = (ym - tp) / suave + 0.5
            if cov <= 0.0:
                continue
            if cov > 1.0:
                cov = 1.0
            rasgo = 0.86 + 0.14 * math.sin(v * 0.8 + t * 3.0 + x * 0.003)
            k = forca * cov * fade * rasgo
            q[y, x, 0] += (cor[0] - q[y, x, 0]) * k
            q[y, x, 1] += (cor[1] - q[y, x, 1]) * k
            q[y, x, 2] += (cor[2] - q[y, x, 2]) * k


@njit(parallel=True, cache=True, fastmath=True)
def _k_nevoa(q, yc, alt, cor, forca, tex, ox, oy, esc_x, esc_y):
    """Faixa de névoa: densidade gaussiana em y, rasgada pelo ruído (que a cena faz andar com ox)."""
    H, W = q.shape[0], q.shape[1]
    y0 = max(0, int(yc - alt * 2.6))
    y1 = min(H, int(yc + alt * 2.6) + 1)
    for y in prange(y0, y1):
        dy = (y + 0.5 - yc) / alt
        base = math.exp(-dy * dy) * forca
        if base < 0.003:
            continue
        for x in range(W):
            nz = _amostra(tex, x * esc_x + ox, y * esc_y + oy)
            k = base * (0.5 + 0.75 * nz)
            if k <= 0.0:
                continue
            if k > 1.0:
                k = 1.0
            q[y, x, 0] += (cor[0] - q[y, x, 0]) * k
            q[y, x, 1] += (cor[1] - q[y, x, 1]) * k
            q[y, x, 2] += (cor[2] - q[y, x, 2]) * k


@njit(parallel=True, cache=True, fastmath=True)
def _k_disco(q, cx, cy, r, cor, tex, tex_k, escuro, alfa):
    """Disco de sol ou lua com manchas suaves (tex) e borda escurecida."""
    H, W = q.shape[0], q.shape[1]
    y0 = max(0, int(cy - r - 2))
    y1 = min(H, int(cy + r + 3))
    x0 = max(0, int(cx - r - 2))
    x1 = min(W, int(cx + r + 3))
    for y in prange(y0, y1):
        for x in range(x0, x1):
            dx = (x + 0.5 - cx) / r
            dy = (y + 0.5 - cy) / r
            d = math.sqrt(dx * dx + dy * dy)
            cov = (1.0 - d) * r + 0.5
            if cov <= 0.0:
                continue
            if cov > 1.0:
                cov = 1.0
            mu = math.sqrt(max(0.0, 1.0 - d * d))
            k = (1.0 - escuro * (1.0 - mu)) * (1.0 + tex_k * _amostra(tex, dx * 40.0 + 100.0, dy * 40.0 + 70.0))
            a = cov * alfa
            q[y, x, 0] += (cor[0] * k - q[y, x, 0]) * a
            q[y, x, 1] += (cor[1] * k - q[y, x, 1]) * a
            q[y, x, 2] += (cor[2] * k - q[y, x, 2]) * a


@njit(parallel=True, cache=True, fastmath=True)
def _k_linhas_v(q, xs, y0s, y1s, larg, cor, forca):
    """Linhas verticais suaves (separação dos troncos de uma cerca), de y0 a y1 em cada x."""
    H, W = q.shape[0], q.shape[1]
    for i in prange(xs.shape[0]):
        xc = xs[i]
        a = max(0, int(y0s[i]))
        b = min(H, int(y1s[i]) + 1)
        xa = max(0, int(xc - larg - 1))
        xb = min(W, int(xc + larg + 2))
        for x in range(xa, xb):
            d = abs(x + 0.5 - xc) / larg
            if d >= 1.0:
                continue
            k = (1.0 - d) * forca
            for y in range(a, b):
                fy = min(1.0, (y - y0s[i]) / 6.0)
                kk = k * max(0.0, fy)
                q[y, x, 0] += (cor[0] - q[y, x, 0]) * kk
                q[y, x, 1] += (cor[1] - q[y, x, 1]) * kk
                q[y, x, 2] += (cor[2] - q[y, x, 2]) * kk


# ------------------------------------------------------------------ perfis (no mundo, com margem)
def grade(W):
    M = int(W * MARGEM)
    return np.arange(-M, W + M + 1, dtype=np.float64)


def plano(W, y):
    return np.full(len(grade(W)), float(y))


def morros(W, y, amp, escala, semente, oitavas=4, picos=1.0):
    """Linha de morros: base em y, subindo até amp (pixels)."""
    n = len(grade(W))
    r = 0.5 + 0.5 * ruido1d(n, escala, semente, oitavas)
    return y - amp * r ** picos


def ilha(W, x0, x1, y, alt, semente, borda=0.18, escala=180.0):
    """Ilha no horizonte: platô suave entre x0 e x1 (pixels do mundo), com bordas descendo até o mar."""
    g = grade(W)
    u = (g - x0) / max(1.0, x1 - x0)
    env = np.clip(np.minimum(u, 1 - u) / borda, 0, 1)
    env = env * env * (3 - 2 * env)
    nz = 0.75 + 0.25 * ruido1d(len(g), escala, semente, 3)
    return np.where(env > 0, y - alt * env * nz, LONGE)


def floresta(W, chao, n, alt, largura=0.34, semente=1, faixa=None, copas=0.0, camadas=4, rugas=1.0):
    """Árvores sobre o perfil `chao`: pinheiros em camadas (e copas redondas na fração `copas`).
    alt = (mín, máx) em pixels; faixa = (x0, x1) no mundo onde podem nascer."""
    g = grade(W)
    out = np.array(chao, np.float64)
    rnd = np.random.default_rng(semente)
    x0, x1 = faixa if faixa else (g[0], g[-1])
    xs = np.sort(rnd.uniform(x0, x1, n))
    base0 = int(g[0])
    for xc in xs:
        i_c = int(round(xc)) - base0
        if i_c < 0 or i_c >= len(g):
            continue
        yb = chao[i_c]
        if yb >= LONGE * 0.5:
            continue
        h = rnd.uniform(*alt)
        w = h * largura * rnd.uniform(0.8, 1.2)
        if rnd.random() < copas:                                   # copa redonda (carvalho, arbusto)
            r = w * 1.05
            for k in range(3):
                cx_ = xc + rnd.uniform(-0.45, 0.45) * r
                cy_ = yb - h + r * 0.9 + rnd.uniform(0, 0.25) * r
                rr = r * rnd.uniform(0.6, 0.9)
                i0, i1 = max(0, int(cx_ - rr) - base0), min(len(g), int(cx_ + rr) + 2 - base0)
                if i1 <= i0:
                    continue
                dx = g[i0:i1] - cx_
                yy = cy_ - np.sqrt(np.clip(rr * rr - dx * dx, 0, None))
                yy = np.where(np.abs(dx) < rr, yy, LONGE)
                out[i0:i1] = np.minimum(out[i0:i1], yy)
            continue
        for j in range(camadas):                                  # pinheiro: camadas de triângulos
            yj = yb - h + h * j * (0.78 / camadas) * rugas
            wj = w * (0.42 + 0.58 * (j + 1) / camadas) * rnd.uniform(0.9, 1.1)
            hh = h * 0.36
            i0, i1 = max(0, int(xc - wj) - base0), min(len(g), int(xc + wj) + 2 - base0)
            if i1 <= i0:
                continue
            dx = np.abs(g[i0:i1] - xc)
            yy = np.where(dx < wj, yj + hh * dx / wj, LONGE)
            out[i0:i1] = np.minimum(out[i0:i1], yy)
        i0, i1 = max(0, int(xc - 1.5) - base0), min(len(g), int(xc + 2.5) - base0)   # ponta fina
        out[i0:i1] = np.minimum(out[i0:i1], yb - h - h * 0.04)
    return out


def palicada(W, x0, x1, chao, alt, n, semente=3, ponta=0.16):
    """Cerca de troncos pontudos entre x0 e x1, de pé sobre o perfil `chao`. Devolve (perfil, bordas_dos_troncos)."""
    g = grade(W)
    out = np.full(len(g), LONGE)
    rnd = np.random.default_rng(semente)
    larg = (x1 - x0) / n
    base0 = int(g[0])
    bordas = []
    for i in range(n):
        xa = x0 + i * larg
        xc = xa + larg / 2
        i_c = int(round(xc)) - base0
        yb = chao[min(max(i_c, 0), len(g) - 1)]
        h = alt * rnd.uniform(0.92, 1.08)
        ia, ib = int(xa) - base0, int(xa + larg) + 1 - base0
        dx = np.abs(g[ia:ib] - xc) / (larg / 2)
        out[ia:ib] = np.minimum(out[ia:ib], yb - h + ponta * h * np.clip(dx, 0, 1))
        bordas.append((xa + larg, yb - h + ponta * h, yb))
    return out, bordas


def capim(W, chao, n, alt, semente=5, faixa=None, largura=5.0, curva=0.25):
    """Capim/juncos: muitas folhas finas e pontudas sobre o perfil `chao`."""
    g = grade(W)
    out = np.array(chao, np.float64)
    rnd = np.random.default_rng(semente)
    x0, x1 = faixa if faixa else (g[0], g[-1])
    base0 = int(g[0])
    for _ in range(n):
        xb = rnd.uniform(x0, x1)
        i_b = int(round(xb)) - base0
        if i_b < 0 or i_b >= len(g):
            continue
        yb = chao[i_b]
        h = rnd.uniform(*alt)
        xt = xb + rnd.uniform(-curva, curva) * h
        w = largura * rnd.uniform(0.7, 1.4)
        i0, i1 = max(0, int(min(xb, xt) - w) - base0), min(len(g), int(max(xb, xt) + w) + 2 - base0)
        xx = g[i0:i1]
        # folha: triângulo da base (largura w) até a ponta (xt, yb − h)
        s = np.clip((xx - (xb - w)) / max(1e-3, xt - (xb - w)), 0, 1)       # lado esquerdo
        s2 = np.clip(((xb + w) - xx) / max(1e-3, (xb + w) - xt), 0, 1)       # lado direito
        yy = np.where((xx >= min(xb - w, xt)) & (xx <= max(xb + w, xt)), yb - h * np.minimum(s, s2), LONGE)
        out[i0:i1] = np.minimum(out[i0:i1], yy)
    return out


def nuvens(W, y, n, larg, alt, semente=7, faixa=None, achatada=0.35, bolhas=(5, 10)):
    """Nuvens soltas numa faixa de altura y: cada uma com o topo em bolhas (elipses de tamanhos variados) e a base
    quase reta, levemente curva. Devolve uma lista de (topo, base), da mais longe (atrás) para a mais perto."""
    g = grade(W)
    rnd = np.random.default_rng(semente)
    x0, x1 = faixa if faixa else (g[0], g[-1])
    base0 = int(g[0])
    lista = []
    centros = np.sort(rnd.uniform(x0, x1, n))
    for xc in centros:
        L = rnd.uniform(*larg)
        hc = rnd.uniform(*alt)
        yc = y + rnd.uniform(-0.7, 0.7) * hc
        fundo = yc + hc * achatada
        topo = np.full(len(g), LONGE)
        nb = int(rnd.integers(*bolhas))
        for k in range(nb):
            u_c = (k + 0.5) / nb - 0.5 + rnd.uniform(-0.06, 0.06)
            bx = xc + u_c * L
            meio = 1.0 - abs(u_c) * 1.6                      # bolhas mais altas no meio
            rx = L * rnd.uniform(0.07, 0.16)
            ry = min(hc * (0.45 + 0.7 * meio) * rnd.uniform(0.7, 1.1), rx * 0.9)
            i0, i1 = max(0, int(bx - rx) - base0), min(len(g), int(bx + rx) + 2 - base0)
            if i1 <= i0:
                continue
            u = (g[i0:i1] - bx) / rx
            yy = np.where(np.abs(u) < 1, fundo - ry * np.sqrt(np.clip(1 - u * u, 0, None)), LONGE)
            topo[i0:i1] = np.minimum(topo[i0:i1], yy)
        ok = topo < LONGE * 0.5
        if not ok.any():
            continue
        xa, xb = g[ok].min(), g[ok].max()
        u = np.clip((g - xa) / max(1.0, xb - xa), 0, 1)
        base = np.where(ok, fundo + hc * 0.10 * np.sin(np.pi * u), -1.0)
        topo = np.where(ok, np.minimum(topo, base - 0.5), LONGE)
        lista.append((topo, base))
    return lista


# ------------------------------------------------------------------ câmera e cena
class Camera:
    """Zoom s e deslocamento (dx, dy) em pixels; cada faixa sente na proporção da profundidade p."""

    def __init__(self, W, H, s=1.0, dx=0.0, dy=0.0, cx=None, cy=None):
        self.W, self.H, self.s, self.dx, self.dy = W, H, s, dx, dy
        self.cx = W / 2 if cx is None else cx
        self.cy = H / 2 if cy is None else cy

    def fator(self, p):
        return 0.06 + 0.94 * p

    def escala(self, p):
        """Zoom sentido pela faixa: tudo aproxima (s), as de perto um pouco mais, as de longe um pouco menos."""
        return self.s ** (0.75 + 0.5 * p)

    def ponto(self, xw, yw, p):
        k, s = self.fator(p), self.escala(p)
        return self.cx + (xw + self.dx * k - self.cx) * s, self.cy + (yw - self.cy) * s + self.dy * k

    def y(self, yw, p):
        return self.cy + (yw - self.cy) * self.escala(p) + self.dy * self.fator(p)

    def perfil(self, perfil, p, deriva=0.0):
        """Reamostra um perfil do mundo para as W+1 bordas de pixel da tela."""
        k, s = self.fator(p), self.escala(p)
        xs = np.arange(self.W + 1, dtype=np.float64)
        xw = self.cx + (xs - self.cx) / s - self.dx * k - deriva
        g = grade(self.W)
        yw = np.interp(xw, g, perfil)
        longe = yw > LONGE * 0.5
        y = self.cy + (yw - self.cy) * s + self.dy * k
        y[longe] = LONGE
        return y.astype(np.float32)


def degrade(H, paradas):
    """Coluna de cor (H×3) a partir de paradas [(y em fração da altura, (r, g, b)), ...]."""
    ys = np.linspace(0, 1, H)
    pos = np.array([p for p, _ in paradas], np.float64)
    cores = np.array([c for _, c in paradas], np.float64)
    return np.stack([np.interp(ys, pos, cores[:, i]) for i in range(3)], 1).astype(np.float32)


class Cena:
    """Desenha camadas no quadro q (float32 H×W×3) com uma câmera e o tempo t."""

    def __init__(self, q, cam, t, luz=(0.5, 0.3), semente=1):
        self.q, self.cam, self.t = q, cam, t
        self.H, self.W = q.shape[:2]
        self.tex = textura(semente)
        self.luz = (luz[0] * self.W, luz[1] * self.H)          # posição da luz (sol/lua) no mundo, em pixels
        self.ceu_col = None

    def luz_tela(self, p=0.0):
        return self.cam.ponto(self.luz[0], self.luz[1], p)

    def ceu(self, paradas, p=0.0):
        """Degradê do céu (paradas em fração da altura do mundo); guarda a coluna para o mar refletir."""
        H = self.H
        col = degrade(int(H * 1.6), [(a / 1.6 + 0.3 / 1.6, c) for a, c in paradas])
        # mundo y → linha da coluna estendida (0.3 H de sobra em cima)
        ys = self.cam.cy + (np.arange(H) + 0.5 - self.cam.dy * self.cam.fator(p) - self.cam.cy) / self.cam.escala(p)
        idx = np.clip(((ys / H) + 0.3) / 1.6 * (len(col) - 1), 0, len(col) - 1).astype(int)
        self.ceu_col = col[idx]
        self.q[:] = self.ceu_col[:, None, :]

    def estrelas(self, n=420, semente=4, ate=0.6, forca=0.9, p=0.0):
        rnd = np.random.default_rng(semente)
        s = rnd.random((n, 5))
        xw = s[:, 0] * self.W * 1.2 - self.W * 0.1
        yw = (s[:, 1] ** 1.3) * self.H * ate
        xs, ys = self.cam.ponto(xw, yw, p)
        pisca = 0.55 + 0.45 * np.sin(self.t * (1.5 + 3 * s[:, 2]) + s[:, 3] * 6.28)
        tam = 0.6 + 1.6 * s[:, 4] ** 3
        cores = np.where(s[:, 2:3] > 0.8, [1.0, 0.9, 0.78], [0.85, 0.9, 1.0]).astype(np.float32)
        FX.particulas(self.q, xs, ys, tam, cores, forca * pisca * (0.35 + 0.65 * s[:, 4]))

    def astro(self, raio, cor=(0.96, 0.95, 0.88), halo=(0.55, 0.65, 0.9), halo_k=0.5, manchas=0.10, p=0.0, sol=False):
        x, y = self.luz_tela(p)
        r = raio * self.cam.escala(p)
        FX.brilho(self.q, x, y, r * 7.0, cor=halo, forca=halo_k * 0.35, nucleo=0.0)
        FX.brilho(self.q, x, y, r * 2.2, cor=halo, forca=halo_k, nucleo=0.25)
        _k_disco(self.q, float(x), float(y), float(r), np.array(cor, np.float32), self.tex,
                 0.0 if sol else manchas, 0.15 if not sol else -0.2, 1.0)

    def faixa(self, topo, base=None, p=0.5, cor=(0.1, 0.1, 0.1), cor_base=None, ya=None, yb=None, borda=None,
              borda_baixo=None, luz_k=0.8, tex_k=0.05, tex_esc=0.6, alfa=1.0, deriva=0.0, desloc=0.0):
        """Faixa entre `topo` e `base` (perfis do mundo; base None = até o fim da tela). ya/yb (mundo): onde o
        degradê vai de `cor` a `cor_base`. borda = (cor, largura): luz de contorno no topo."""
        T = self.cam.perfil(topo, p, deriva) + np.float32(desloc)
        B = self.cam.perfil(base, p, deriva) + np.float32(desloc) if base is not None else np.full(self.W + 1, self.H + 2.0, np.float32)
        if base is not None:
            B[B > LONGE * 0.5] = -1.0
        ya_s = self.cam.y(ya, p) if ya is not None else float(np.min(T))
        yb_s = self.cam.y(yb, p) if yb is not None else float(self.H)
        cb = cor_base if cor_base is not None else cor
        rim, rw = (borda if borda else ((0, 0, 0), 0.0))
        rimb, rbw = (borda_baixo if borda_baixo else ((0, 0, 0), 0.0))
        lx = self.luz_tela(p)[0]
        _k_faixa(self.q, T, B, float(ya_s), float(yb_s), np.array(cor, np.float32), np.array(cb, np.float32),
                 np.array(rim, np.float32), float(rw) * self.cam.escala(p), np.array(rimb, np.float32), float(rbw),
                 float(lx), float(luz_k), self.tex, float(tex_k), float(tex_esc), float(self.cam.dx * self.cam.fator(p) * tex_esc),
                 0.0, float(alfa))
        return T

    def x_mundo(self, p, deriva=0.0):
        """x do mundo de cada uma das W+1 bordas de pixel da tela, para a profundidade p."""
        cam = self.cam
        xs = np.arange(self.W + 1, dtype=np.float64)
        return cam.cx + (xs - cam.cx) / cam.escala(p) - cam.dx * cam.fator(p) - deriva

    def agua(self, y, p=0.35, clara=(0.42, 0.80, 0.82), corpo=(0.22, 0.64, 0.72), fundo=(0.04, 0.20, 0.34),
             y_fundo=None, faixa=12.0, crista=5.0, onda=0.012, vel=1.0, brilho=(0.80, 0.96, 0.96), brilho_w=1.5,
             listras=0.07, lis_cor=(0.55, 0.85, 0.88), lis_prof=260.0, raios=0.10, n_raios=6, r_cor=(0.55, 0.85, 0.85),
             luz=0.0, luz_cor=(0.9, 0.92, 1.0), luz_larg=40.0, semente=3):
        """Água chapada vista de lado, linha d'água em y (mundo). Uma faixa clara de superfície com cristas pontudas
        que andam e balançam, o corpo em degradê até `fundo` (em y_fundo), listras e raios de luz. Devolve a linha
        da frente (W+1 valores, na tela) para quem quiser pôr coisas na água."""
        t = self.t
        u = self.H / 1080.0
        xw = self.x_mundo(p)
        rnd = np.random.default_rng(semente)
        f1, f2 = rnd.uniform(0, 6.28, 2)
        env1 = 0.65 + 0.35 * np.sin(xw * 0.0013 / u + f1 + t * 0.15)
        env2 = 0.65 + 0.35 * np.sin(xw * 0.0009 / u + f2 - t * 0.12)
        balanco = u * (2.2 * np.sin(xw * 0.0035 / u + t * 0.55 * vel) + 1.2 * np.sin(xw * 0.0071 / u - t * 0.8 * vel))
        tras = y - faixa * 0.5 + crista * env1 * np.abs(np.sin(xw * onda * 2.3 - t * 1.25 * vel)) + balanco
        frente = y + faixa * 0.5 + crista * 0.8 * env2 * np.abs(np.sin(xw * onda * 1.6 + t * 0.9 * vel + 1.7)) + balanco * 1.2
        T = self.cam.y(tras, p).astype(np.float32)
        F = self.cam.y(frente, p).astype(np.float32)
        base = np.full(self.W + 1, self.H + 2.0, np.float32)
        ys = float(self.cam.y(y, p))
        yf = float(self.cam.y(y_fundo if y_fundo is not None else self.H * 1.1, p))
        lx = self.luz_tela(p)[0]
        _k_faixa(self.q, T, base, ys - faixa, ys + faixa, np.array(clara, np.float32), np.array(clara, np.float32),
                 np.array(brilho, np.float32), float(brilho_w), np.zeros(3, np.float32), 0.0, float(lx), 0.0, self.tex,
                 0.03, 0.8, 0.0, 0.0, 1.0)
        _k_faixa(self.q, F, base, ys, yf, np.array(corpo, np.float32), np.array(fundo, np.float32),
                 np.array([c * 0.25 for c in brilho], np.float32), 1.2, np.zeros(3, np.float32), 0.0, float(lx), 0.0,
                 self.tex, 0.025, 0.5, float(t * 2.0), 0.0, 1.0)
        rx = np.zeros(0, np.float32)
        rw = rk = rx
        if raios > 0 and n_raios > 0:
            base_x = (np.arange(n_raios) + rnd.uniform(0.1, 0.9, n_raios)) / n_raios
            rx = (self.cam.ponto(base_x * self.W * 1.3 - self.W * 0.15, y, p)[0] + 40 * u * np.sin(t * 0.25 + np.arange(n_raios) * 1.7)).astype(np.float32)
            rw = (rnd.uniform(30, 90, n_raios) * u * self.cam.escala(p)).astype(np.float32)
            rk = (raios * rnd.uniform(0.5, 1.0, n_raios) * (0.75 + 0.25 * np.sin(t * 0.6 + np.arange(n_raios) * 2.3))).astype(np.float32)
        _k_agua_det(self.q, F, float(t), self.tex, np.array(lis_cor, np.float32), float(listras), float(lis_prof),
                    float(0.6 * vel), rx, rw, rk, 0.18, float(self.H * 0.35), np.array(r_cor, np.float32),
                    float(lx), float(luz_larg), np.array(luz_cor, np.float32), float(luz))
        return F

    def reflexo(self, topo_tela, horiz_tela, cor, forca=0.6, alcance=None, amp=4.0, suave=3.0, borrao=9):
        """Reflexo na água do contorno `topo_tela` (o que faixa() devolve), alisado para parecer água."""
        tp = np.where(topo_tela > LONGE * 0.5, horiz_tela + 50.0, topo_tela).astype(np.float64)
        if borrao > 1:
            k = np.ones(borrao) / borrao
            tp = np.convolve(np.pad(tp, borrao, mode="edge"), k, mode="same")[borrao:-borrao]
        _k_reflexo(self.q, tp.astype(np.float32), float(horiz_tela), float(alcance or (self.H - horiz_tela)),
                   np.array(cor, np.float32), float(forca), float(self.t), float(amp), float(suave))

    def nuvens(self, lista, p=0.02, deriva=0.0, **kw):
        """Desenha as nuvens de nuvens() (uma faixa por nuvem, de trás pra frente)."""
        for topo, base in lista:
            self.faixa(topo, base, p=p, deriva=deriva, **kw)

    def nevoa(self, y, alt, cor, forca=0.35, p=0.3, vel=6.0, esc=(0.12, 0.5), semente_ox=0.0):
        yc = self.cam.y(y, p)
        ox = semente_ox + self.t * vel * esc[0] + self.cam.dx * self.cam.fator(p) * esc[0]
        _k_nevoa(self.q, float(yc), float(alt * self.cam.escala(p)), np.array(cor, np.float32), float(forca), self.tex,
                 float(ox), float(semente_ox * 0.37), float(esc[0]), float(esc[1]))

    def linhas_v(self, bordas, p, cor, larg=2.2, forca=0.6):
        """Linhas verticais (separação de troncos) a partir de [(x, y_topo, y_base)] do mundo."""
        if not bordas:
            return
        b = np.array(bordas, np.float64)
        xs, y0 = self.cam.ponto(b[:, 0], b[:, 1], p)
        _, y1 = self.cam.ponto(b[:, 0], b[:, 2], p)
        _k_linhas_v(self.q, xs.astype(np.float32), y0.astype(np.float32), y1.astype(np.float32),
                    float(larg * self.cam.escala(p)), np.array(cor, np.float32), float(forca))
