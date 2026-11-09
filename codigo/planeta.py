"""Planetas realistas desenhados por código, com mapas reais (NASA e Solar System Scope), compilados com numba.

Cada quadro é calculado na hora (centésimos de segundo): projeção da esfera, textura do dia, luz do Sol com terminador
suave, brilho do Sol no mar, luzes das cidades no lado da noite, nuvens, relevo (crateras da Lua), atmosfera na borda,
halo por fora, anéis com sombra, estrelas e a Via Láctea ao fundo, brilho (bloom), vinheta e grão de filme.

O quadro é um array float32 (altura × largura × 3) em valores de tela (0 a 1; acima de 1 vira brilho no pós).
Os mapas ficam em canal/recursos/ (baixados de Releases: canal-recursos). Sem um mapa, aquela parte fica de fora.
"""
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from numba import njit, prange
from PIL import Image, ImageDraw, ImageFilter

RECURSOS = Path(__file__).parent / "recursos"
Image.MAX_IMAGE_PIXELS = None

CORPOS = {
    "terra": dict(dia="terra.jpg", noite="noite.jpg", nuvens="nuvens.jpg", oceano="oceano.png",
                  atm=(0.30, 0.56, 1.0), atm_k=1.0, mar_escuro=0.72),
    "lua": dict(dia="lua.jpg", relevo="lua_relevo.png", relevo_k=9.0, fotometria="lunar"),
    "marte": dict(dia="marte.jpg", atm=(1.0, 0.66, 0.48), atm_k=0.35),
    "jupiter": dict(dia="jupiter.jpg", atm=(0.95, 0.86, 0.72), atm_k=0.22),
    "saturno": dict(dia="saturno.jpg", atm=(0.95, 0.88, 0.70), atm_k=0.2, aneis="saturno_aneis.png", aneis_r=(1.24, 2.27)),
    "venus": dict(dia="venus.jpg", atm=(1.0, 0.92, 0.72), atm_k=0.45),
    "mercurio": dict(dia="mercurio.jpg", fotometria="lunar"),
    "netuno": dict(dia="netuno.jpg", atm=(0.45, 0.62, 1.0), atm_k=0.5),
    "urano": dict(dia="urano.jpg", atm=(0.62, 0.9, 1.0), atm_k=0.4),
    "sol": dict(dia="sol.jpg", emissivo=True, sat=0.6, contraste=0.75, tinta=(1.0, 0.85, 0.58), brilho=1.5),
}

_VAZIO1 = np.zeros((1, 1), np.uint8)
_VAZIO2 = np.zeros((1, 1, 2), np.float32)
_VAZIO3 = np.zeros((1, 1, 3), np.uint8)
_VAZIO3F = np.zeros((1, 1, 3), np.float32)
_VAZIO_AN = (np.zeros((2, 3), np.float32), np.zeros(2, np.float32))


# ---------------------------------------------------------------- mapas
@lru_cache(maxsize=16)
def _imagem(nome):
    p = RECURSOS / nome
    if not p.exists():
        return None
    im = Image.open(p)
    im.load()
    return im


def tem(nome):
    return bool(nome) and _imagem(nome) is not None


@lru_cache(maxsize=40)
def _nivel(nome, largura, modo):
    """Mapa equirretangular numa largura: modo rgb (uint8 H×W×3), l (uint8 H×W), lmax (uint8 H×W, o maior dos
    canais) ou grad (float32 H×W×2, derivada da altura em x e y)."""
    im = _imagem(nome)
    if im is None:
        return None
    largura = int(min(largura, im.width))
    alt = max(1, largura // 2)
    if modo == "grad":
        a = np.asarray(im).astype(np.float32)
        if a.ndim == 3:
            a = a[..., :3].mean(axis=2)
        a = (a - a.min()) / max(1e-6, float(a.max() - a.min()))
        a = np.asarray(Image.fromarray(a, "F").resize((largura, alt), Image.BILINEAR), np.float32)
        a = (np.roll(a, 1, axis=1) + 2 * a + np.roll(a, -1, axis=1)) * 0.25
        a = (np.vstack([a[:1], a[:-1]]) + 2 * a + np.vstack([a[1:], a[-1:]])) * 0.25
        gx = (np.roll(a, -1, axis=1) - np.roll(a, 1, axis=1)) * 0.5 * (largura / 2048)
        gy = (np.vstack([a[1:], a[-1:]]) - np.vstack([a[:1], a[:-1]])) * 0.5 * (largura / 2048)
        return np.ascontiguousarray(np.dstack([gx, gy]).astype(np.float32))
    if modo == "lmax":
        m = im.convert("RGB")
        if m.width != largura:
            m = m.resize((largura, alt), Image.LANCZOS)
        return np.ascontiguousarray(np.asarray(m).max(axis=2))
    m = im.convert("RGB" if modo == "rgb" else "L")
    if m.width != largura or m.height != alt:
        m = m.resize((largura, alt), Image.LANCZOS)
    return np.ascontiguousarray(np.asarray(m))


def _mapa(nome, r, modo="rgb", fator=1.1, ajuste=None):
    """O nível do mapa com pelo menos ~1 texel por pixel no centro do disco. ajuste: (saturação, contraste, tinta RGB,
    brilho) para mudar a cor do mapa (ex.: o Sol mais amarelo e menos laranja)."""
    if not tem(nome):
        return None
    im = _imagem(nome)
    precisa = 2 * math.pi * r * fator
    w = 1024
    while w < precisa and w < im.width:
        w *= 2
    if ajuste:
        return _nivel_ajustado(nome, min(w, im.width), ajuste)
    return _nivel(nome, min(w, im.width), modo)


@lru_cache(maxsize=8)
def _nivel_ajustado(nome, largura, ajuste):
    sat, contraste, tinta, brilho = ajuste
    a = _nivel(nome, largura, "rgb").astype(np.float32) / 255.0
    lum = a.mean(axis=2, keepdims=True)
    a = lum + (a - lum) * sat
    m = float(lum.mean())
    a = m + (a - m) * contraste
    a = a * np.array(tinta, np.float32) * brilho
    return np.ascontiguousarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


@lru_cache(maxsize=4)
def _mapa_aneis(nome, n=2048):
    """Perfil radial dos anéis: (cor N×3, opacidade N), de dentro para fora."""
    im = _imagem(nome) if isinstance(nome, str) and nome != "procedural" else None
    if im is None:
        x = np.linspace(0, 1, n, dtype=np.float32)
        faixas = 0.55 + 0.45 * np.sin(x * 90) * np.sin(x * 17 + 1)
        op = np.clip(faixas * (x > 0.04) * (x < 0.97) * (1 - 0.85 * ((x > 0.62) & (x < 0.66))), 0, 1)
        cor = np.stack([0.86 + 0 * x, 0.8 + 0 * x, 0.7 + 0 * x], 1).astype(np.float32)
        return np.ascontiguousarray(cor), op.astype(np.float32)
    a = np.asarray(im.convert("RGBA").resize((n, max(1, im.height)), Image.LANCZOS), np.float32) / 255.0
    linha = a.mean(axis=0)
    return np.ascontiguousarray(linha[:, :3]), np.ascontiguousarray(linha[:, 3])


def _norm(v):
    v = np.asarray(v, np.float64)
    return v / max(1e-9, float(np.linalg.norm(v)))


# ---------------------------------------------------------------- núcleo compilado
@njit(cache=True, fastmath=True, inline="always")
def _sm(x, a, b):
    t = (x - a) / (b - a)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


@njit(cache=True, fastmath=True, inline="always")
def _cl(x, a, b):
    return a if x < a else (b if x > b else x)


@njit(cache=True, fastmath=True, inline="always")
def _pos(t, u, v):
    H = t.shape[0]
    W = t.shape[1]
    fx = u * W - 0.5
    fy = v * H - 0.5
    ix = int(math.floor(fx))
    iy = int(math.floor(fy))
    ax = fx - ix
    ay = fy - iy
    x0 = ix % W
    x1 = (ix + 1) % W
    y0 = min(max(iy, 0), H - 1)
    y1 = min(max(iy + 1, 0), H - 1)
    return x0, x1, y0, y1, (1 - ax) * (1 - ay), ax * (1 - ay), (1 - ax) * ay, ax * ay


@njit(cache=True, fastmath=True, inline="always")
def _bil1(t, u, v):
    x0, x1, y0, y1, a, b, c, d = _pos(t, u, v)
    return t[y0, x0] * a + t[y0, x1] * b + t[y1, x0] * c + t[y1, x1] * d


@njit(cache=True, fastmath=True, inline="always")
def _bil3(t, u, v, k):
    x0, x1, y0, y1, a, b, c, d = _pos(t, u, v)
    return t[y0, x0, k] * a + t[y0, x1, k] * b + t[y1, x0, k] * c + t[y1, x1, k] * d


@njit(cache=True, fastmath=True, inline="always")
def _anel(cr, cg, cb, px, pz, rho, rin, rout, Sb, an_cor, an_op, opac):
    n = an_op.shape[0]
    k = int((rho - rin) / (rout - rin) * (n - 1))
    k = 0 if k < 0 else (n - 1 if k > n - 1 else k)
    op = an_op[k] * 0.92 * opac
    luz = 0.55 + 0.45 * abs(Sb[1])
    ps = px * Sb[0] + pz * Sb[2]
    perp2 = px * px + pz * pz - ps * ps
    if ps < 0 and perp2 < 1.0:
        luz *= 0.12
    return (cr * (1 - op) + an_cor[k, 0] * luz * op, cg * (1 - op) + an_cor[k, 1] * luz * op,
            cb * (1 - op) + an_cor[k, 2] * luz * op)


@njit(parallel=True, cache=True, fastmath=True)
def _k_corpo(q, P, M, S, Sb, Hv, dia, oce, nuv, noi, rel, mis, an_cor, an_op):
    cx, cy, r, lon0r, giro, expo = P[0], P[1], P[2], P[3], P[4], P[5]
    noite_k, halo_k, nuvens_k, mis_k, proprio, opac = P[6], P[7], P[8], P[9], P[10], P[11]
    ar, ag, ab, atm_k, mar, gama, rel_k = P[12], P[13], P[14], P[15], P[16], P[17], P[18]
    tem_atm, emiss, lunar, tem_oce, tem_nuv = P[19] > 0, P[20] > 0, P[21] > 0, P[22] > 0, P[23] > 0
    tem_noi, tem_rel, tem_mis, tem_an, rin, rout = P[24] > 0, P[25] > 0, P[26] > 0, P[27] > 0, P[28], P[29]
    halo_w, x0, x1, y0, y1, tem_dia = P[30], int(P[31]), int(P[32]), int(P[33]), int(P[34]), P[35] > 0
    br, bg, bb, lim, mis_br, aro = P[36], P[37], P[38], P[39], P[40], P[41]
    sol_k = min(max(expo, 0.0), 1.0)
    inv2pi = 1.0 / (2.0 * math.pi)
    invpi = 1.0 / math.pi
    borda = 1.0 + 1.0 / r
    anel_ok = tem_an and abs(M[1, 2]) > 1e-4
    sombra_anel = tem_an and abs(Sb[1]) > 1e-4
    nan_ = an_op.shape[0]
    for j in prange(y0, y1):
        Y = -(j + 0.5 - cy) / r
        for i in range(x0, x1):
            X = (i + 0.5 - cx) / r
            d2 = X * X + Y * Y
            if d2 >= lim * lim:
                continue
            d = math.sqrt(d2)
            cr = q[j, i, 0]
            cg = q[j, i, 1]
            cb = q[j, i, 2]
            hit = False
            t_r = 0.0
            px = 0.0
            pz = 0.0
            rho = 0.0
            if anel_ok:
                t_r = -(M[1, 0] * X + M[1, 1] * Y) / M[1, 2]
                px = M[0, 0] * X + M[0, 1] * Y + M[0, 2] * t_r
                pz = M[2, 0] * X + M[2, 1] * Y + M[2, 2] * t_r
                rho = math.sqrt(px * px + pz * pz)
                hit = rho >= rin and rho <= rout
                if hit and t_r < 0:
                    cr, cg, cb = _anel(cr, cg, cb, px, pz, rho, rin, rout, Sb, an_cor, an_op, opac)
            if (tem_atm or emiss) and halo_k > 0 and d >= 0.97 and d < 1.0 + halo_w:
                tt = _cl((d - 1.0) / halo_w, 0.0, 1.0)
                if emiss:
                    g = (math.exp(-tt * 7.0) * 0.75 + math.exp(-tt * 2.2) * 0.28) * halo_k * opac
                    cr += g
                    cg += g * 0.82
                    cb += g * 0.55
                else:
                    lado = _cl((X * S[0] + Y * S[1]) / max(d, 1e-6), -1.0, 1.0)
                    contra = max(0.0, -S[2])
                    k = min(0.05 + _sm(lado, -0.3, 0.6) + contra * 1.6 * _sm(lado, -0.9, 0.2), 2.2) * sol_k + aro * 0.5
                    g = math.exp(-tt * 6.0) * (1.0 - tt) * k * atm_k * halo_k * 0.85 * opac
                    cr += g * ar
                    cg += g * ag
                    cb += g * ab
            if d < borda:
                alpha = _cl((1.0 - d) * r + 0.5, 0.0, 1.0) * opac
                z = math.sqrt(max(0.0, 1.0 - d2))
                xb = M[0, 0] * X + M[0, 1] * Y + M[0, 2] * z
                yb = M[1, 0] * X + M[1, 1] * Y + M[1, 2] * z
                zb = M[2, 0] * X + M[2, 1] * Y + M[2, 2] * z
                lat = math.asin(_cl(yb, -1.0, 1.0))
                lon = math.atan2(xb, zb)
                v = 0.5 - lat * invpi
                u = (lon + lon0r) * inv2pi + 0.5
                u -= math.floor(u)
                lam = S[0] * X + S[1] * Y + S[2] * z
                if tem_rel:
                    gx = _bil3(rel, u, v, 0)
                    gy = _bil3(rel, u, v, 1)
                    c = max(math.sqrt(xb * xb + zb * zb), 0.15)
                    ge = gx / c * rel_k
                    gn = -gy * rel_k
                    e_s = (zb * Sb[0] - xb * Sb[2]) / c
                    n_s = (-yb / c) * (xb * Sb[0] + zb * Sb[2]) + c * Sb[1]
                    b_s = xb * Sb[0] + yb * Sb[1] + zb * Sb[2]
                    lam = (b_s - ge * e_s - gn * n_s) / math.sqrt(1.0 + ge * ge + gn * gn)
                if tem_dia:
                    sr = _bil3(dia, u, v, 0) * (1.0 / 255.0)
                    sg = _bil3(dia, u, v, 1) * (1.0 / 255.0)
                    sb_ = _bil3(dia, u, v, 2) * (1.0 / 255.0)
                else:
                    sr, sg, sb_ = br, bg, bb
                if emiss:                                                  # escurecimento do limbo (mais no azul)
                    esc = (0.16 + 0.84 * z ** 0.55) * 1.2 * expo
                    orr = sr * esc
                    og = sg * esc * (0.62 + 0.38 * math.sqrt(z))
                    ob = sb_ * esc * (0.35 + 0.65 * z ** 0.7)
                else:
                    oc = 0.0
                    if tem_oce:
                        oc = _bil1(oce, u, v) * (1.0 / 255.0)
                    elif tem_noi:
                        oc = _cl((sb_ - sr - 0.03) * 6.0, 0.0, 1.0)
                    if mar > 0:
                        k = 1.0 - oc * (1.0 - mar)
                        sr *= k
                        sg *= k
                        sb_ *= k
                    mr = 0.0
                    mg = 0.0
                    mb = 0.0
                    if tem_mis:
                        mr = _bil3(mis, u, v, 0)
                        mg = _bil3(mis, u, v, 1)
                        mb = _bil3(mis, u, v, 2)
                        sr = sr * (1 - mis_k) + mr * mis_k
                        sg = sg * (1 - mis_k) + mg * mis_k
                        sb_ = sb_ * (1 - mis_k) + mb * mis_k
                    luz = max(lam, 0.0)
                    dia_k = _sm(lam, -0.04, 0.16) * sol_k
                    if lunar:
                        razao = min(2.0 * luz / (luz + max(z, 0.05)), 1.2)
                        ilum = razao ** 0.8 * 0.92 + 0.004
                    else:
                        ilum = (0.004 + luz) ** gama
                    ilum *= expo
                    orr = sr * ilum
                    og = sg * ilum
                    ob = sb_ * ilum
                    if oc > 0:
                        nh = X * Hv[0] + Y * Hv[1] + z * Hv[2]
                        if nh > 0.82:
                            ln = math.log(nh)
                            b = (math.exp(ln * 1400.0) * 0.9 + math.exp(ln * 120.0) * 0.14 + math.exp(ln * 18.0) * 0.03) * oc * dia_k * expo
                            orr += b
                            og += b * 0.94
                            ob += b * 0.82
                    nv = 0.0
                    if tem_nuv and nuvens_k > 0:
                        uc = u - giro
                        uc -= math.floor(uc)
                        nv = _cl((_bil1(nuv, uc, v) * (1.0 / 255.0) - 0.06) * 1.25 * nuvens_k, 0.0, 1.0)
                    if tem_noi and noite_k > 0:
                        lz = _cl((_bil1(noi, u, v) * (1.0 / 255.0) - 0.04) / 0.96, 0.0, 1.0)
                        lz = lz * (0.4 + 0.6 * lz) * (1.0 - 0.75 * nv) * (1.0 - dia_k) * noite_k * 1.25
                        orr += lz
                        og += lz * 0.78
                        ob += lz * 0.48
                    if tem_mis and mis_br > 0:
                        k = mis_k * (0.35 + 0.65 * (1.0 - dia_k)) * mis_br
                        orr += mr * k
                        og += mg * k
                        ob += mb * k
                    if nv > 0:
                        cnv = (0.003 + luz) ** 0.55 * 0.97 * nv * 0.94 * expo
                        k = 1.0 - 0.94 * nv
                        orr = orr * k + cnv * 0.96
                        og = og * k + cnv * 0.97
                        ob = ob * k + cnv
                    if tem_atm:
                        f = 1.0 - z
                        f2 = f * f
                        f3 = f2 * f
                        lado = _sm(lam, -0.3, 0.5) * sol_k
                        nev = (f2 * 0.55 + f3 * f3 * 0.9) * lado * atm_k
                        k = 1.0 - f3 * 0.45 * atm_k * lado
                        orr = orr * k + nev * ar
                        og = og * k + nev * ag
                        ob = ob * k + nev * ab
                        dl = (lam - 0.03) / 0.09
                        tw = math.exp(-dl * dl) * f * math.sqrt(f) * 0.16 * atm_k * sol_k
                        orr += tw
                        og += tw * 0.62
                        ob += tw * 0.42
                    if aro > 0:                                            # luz de contorno (artística)
                        f = 1.0 - z
                        a3 = f * f * f * aro
                        orr += a3 * 0.35
                        og += a3 * 0.52
                        ob += a3 * 0.85
                    if proprio > 0:
                        orr += sr * proprio
                        og += sg * proprio
                        ob += sb_ * proprio
                    if sombra_anel:
                        ts = -yb / Sb[1]
                        if ts > 0:
                            qx = xb + ts * Sb[0]
                            qz = zb + ts * Sb[2]
                            rs = math.sqrt(qx * qx + qz * qz)
                            if rs >= rin and rs <= rout:
                                kk = int((rs - rin) / (rout - rin) * (nan_ - 1))
                                kk = 0 if kk < 0 else (nan_ - 1 if kk > nan_ - 1 else kk)
                                s = 1.0 - an_op[kk] * 0.8
                                orr *= s
                                og *= s
                                ob *= s
                cr = cr * (1.0 - alpha) + orr * alpha
                cg = cg * (1.0 - alpha) + og * alpha
                cb = cb * (1.0 - alpha) + ob * alpha
            if hit and t_r >= 0:
                cr, cg, cb = _anel(cr, cg, cb, px, pz, rho, rin, rout, Sb, an_cor, an_op, opac)
            q[j, i, 0] = cr
            q[j, i, 1] = cg
            q[j, i, 2] = cb


def desenhar(quadro, cx, cy, r, corpo="terra", lon0=0.0, lat0=12.0, inclina=18.0, sol=(-0.8, 0.35, 0.5),
             giro_nuvens=0.0, exposicao=1.0, noite_k=1.0, halo_k=1.0, nuvens_k=1.0, mistura=None, mistura_k=0.0,
             aneis=None, aneis_r=None, brilho_proprio=0.0, opacidade=1.0, cor=(0.5, 0.5, 0.5), mistura_brilho=0.85,
             aro=0.0):
    """Desenha o corpo no quadro (float32 H×W×3, contíguo) com centro (cx, cy) e raio r em pixels.
    lon0/lat0: longitude/latitude no centro do disco (graus). inclina: eixo inclinado na tela (graus, anti-horário).
    sol: direção da luz (x direita, y cima, z para a câmera). mistura: mapa (nome ou array equirretangular float)
    que se mistura à superfície com peso mistura_k e brilha sozinho (lava). aneis: True (os do corpo) ou o nome do
    mapa. giro_nuvens em graus. Corpo pode ser um nome de CORPOS ou um dicionário no mesmo formato."""
    cfg = CORPOS[corpo] if isinstance(corpo, str) else corpo
    Hq, Wq = quadro.shape[:2]
    r = float(r)
    if r < 0.6 or opacidade <= 0:
        return
    atm = cfg.get("atm")
    emiss = bool(cfg.get("emissivo"))
    if aneis is True:
        aneis = cfg.get("aneis") or "procedural"
    ar = aneis_r or cfg.get("aneis_r", (1.25, 2.3))
    halo_w = 0.9 if emiss else 0.11
    lim = max(1.0 + (halo_w if (atm or emiss) else 0.0), ar[1] if aneis else 1.0) + 2.0 / r
    x0, x1 = max(0, int(cx - r * lim)), min(Wq, int(cx + r * lim) + 1)
    y0, y1 = max(0, int(cy - r * lim)), min(Hq, int(cy + r * lim) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    S = _norm(sol)
    tau, phi = math.radians(inclina), math.radians(lat0)
    ct, st, cp, sp = math.cos(tau), math.sin(tau), math.cos(phi), math.sin(phi)
    # matriz câmera -> corpo (desfaz a inclinação na tela, depois a latitude de onde se olha)
    M = np.array([[ct, st, 0], [-st * cp, ct * cp, sp], [st * sp, -ct * sp, cp]], np.float64)
    Sb = M @ S
    Hv = _norm(S + np.array([0, 0, 1.0]))
    ajuste = (cfg["sat"], cfg.get("contraste", 1.0), tuple(cfg.get("tinta", (1, 1, 1))), cfg.get("brilho", 1.0)) if "sat" in cfg else None
    dia = _mapa(cfg.get("dia"), r, ajuste=ajuste)
    oce = _mapa(cfg.get("oceano"), r, "l")
    nuv = _mapa(cfg.get("nuvens"), r, "l")
    noi = _mapa(cfg.get("noite"), r, "lmax")
    rel = _mapa(cfg.get("relevo"), r, "grad", fator=0.8)
    mis = None
    if mistura is not None and mistura_k > 0:
        mis = _nivel(mistura, 4096, "rgb").astype(np.float32) / 255 if isinstance(mistura, str) else mistura
        mis = np.ascontiguousarray(mis, np.float32)
    an_cor, an_op = _mapa_aneis(aneis) if aneis else _VAZIO_AN
    a = atm or (0, 0, 0)
    P = np.array([cx, cy, r, math.radians(lon0), giro_nuvens / 360.0, exposicao,
                  noite_k, halo_k, nuvens_k, mistura_k if mis is not None else 0.0, brilho_proprio, min(1.0, opacidade),
                  a[0], a[1], a[2], cfg.get("atm_k", 1.0), cfg.get("mar_escuro", 0.0), cfg.get("gama_luz", 0.62),
                  cfg.get("relevo_k", 4.0),
                  1.0 if atm else 0.0, 1.0 if emiss else 0.0, 1.0 if cfg.get("fotometria") == "lunar" else 0.0,
                  1.0 if oce is not None else 0.0, 1.0 if nuv is not None else 0.0, 1.0 if noi is not None else 0.0,
                  1.0 if rel is not None else 0.0, 1.0 if mis is not None else 0.0, 1.0 if aneis else 0.0, ar[0], ar[1],
                  halo_w, x0, x1, y0, y1, 1.0 if dia is not None else 0.0, cor[0], cor[1], cor[2], lim,
                  mistura_brilho, aro], np.float64)
    _k_corpo(quadro, P, M, S, Sb, Hv,
             dia if dia is not None else _VAZIO3, oce if oce is not None else _VAZIO1,
             nuv if nuv is not None else _VAZIO1, noi if noi is not None else _VAZIO1,
             rel if rel is not None else _VAZIO2, mis if mis is not None else _VAZIO3F, an_cor, an_op)


# ---------------------------------------------------------------- céu
@lru_cache(maxsize=4)
def _estrelas_brilhantes(w, h, semente=5):
    rnd = np.random.default_rng(semente)
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(int(w * h / 26000)):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        s = rnd.uniform(0.6, 1.5) * w / 1080
        c = [(255, 255, 255), (210, 225, 255), (255, 240, 220)][rnd.integers(0, 3)]
        d.ellipse([x - s, y - s, x + s, y + s], fill=c)
    glow = img.filter(ImageFilter.GaussianBlur(2.6 * w / 1080))
    return Image.fromarray(np.clip(np.asarray(img, np.float32) * 0.7 + np.asarray(glow, np.float32) * 2.2, 0, 255).astype(np.uint8))


@lru_cache(maxsize=4)
def estrelas(w, h, semente=7):
    """Céu estrelado feito por código (quando não há a Via Láctea), RGB."""
    rnd = np.random.default_rng(semente)
    px = np.zeros((h, w, 3), np.uint8)
    px[:] = (4, 6, 18)
    n = int(w * h / 700)
    xs, ys = rnd.integers(0, w, n), rnd.integers(0, h, n)
    v = (rnd.random(n) ** 3 * 200 + 40).astype(np.uint8)
    px[ys, xs] = np.maximum(px[ys, xs], v[:, None])
    est = _estrelas_brilhantes(w, h)
    return Image.fromarray(np.clip(px.astype(np.int32) + np.asarray(est, np.int32), 0, 255).astype(np.uint8))


@lru_cache(maxsize=3)
def _ceu_base(w, h, angulo, centro, escala, brilho):
    """Recorte da Via Láctea, girado, com folga de 30% para a câmera andar (uint8 H×W×3)."""
    im = _imagem("via_lactea.jpg")
    W2, H2 = int(w * 1.3), int(h * 1.3)
    if im is None:
        return np.ascontiguousarray(np.asarray(estrelas(W2, H2)))
    cw = im.width * escala                       # largura do recorte na panorâmica (menor = mais zoom)
    ch = cw * H2 / W2
    cx, cy = centro[0] * im.width, centro[1] * im.height
    a = math.radians(angulo)
    ca, sa = math.cos(a), math.sin(a)
    sx, sy = cw / W2, ch / H2
    coef = (ca * sx, -sa * sy, cx - ca * sx * W2 / 2 + sa * sy * H2 / 2,
            sa * sx, ca * sy, cy - sa * sx * W2 / 2 - ca * sy * H2 / 2)
    rec = im.convert("RGB").transform((W2, H2), Image.AFFINE, coef, resample=Image.BICUBIC)
    a = np.asarray(rec, np.float32) / 255.0
    a = np.clip(a * 4.5, 0, 1) ** 0.85 * brilho                       # o mapa original é bem escuro
    a[..., 2] *= 1.08
    a[..., 0] *= 0.93
    est = np.asarray(_estrelas_brilhantes(W2, H2), np.float32) / 255.0
    return np.ascontiguousarray((np.clip(a + est, 0, 1) * 255).astype(np.uint8))


@njit(parallel=True, cache=True, fastmath=True)
def _k_ceu(base, out, sx, sy, ox, oy, k):
    H = base.shape[0]
    W = base.shape[1]
    for j in prange(out.shape[0]):
        fy = oy + (j + 0.5) * sy - 0.5
        iy = int(math.floor(fy))
        ay = fy - iy
        iy = min(max(iy, 0), H - 2)
        for i in range(out.shape[1]):
            fx = ox + (i + 0.5) * sx - 0.5
            ix = int(math.floor(fx))
            ax = fx - ix
            ix = min(max(ix, 0), W - 2)
            for c in range(3):
                v = (base[iy, ix, c] * (1 - ax) + base[iy, ix + 1, c] * ax) * (1 - ay) + \
                    (base[iy + 1, ix, c] * (1 - ax) + base[iy + 1, ix + 1, c] * ax) * ay
                out[j, i, c] = v * k


def ceu(w, h, t=0.0, angulo=-30.0, centro=(0.5, 0.5), escala=0.17, brilho=0.5, deriva=(0.010, 0.005), zoom=0.0,
        luz=1.0):
    """Fundo do quadro (float32 h×w×3): Via Láctea com estrelas andando devagar (deriva por segundo, em fração da tela)
    e zoom (0 = normal, 0.2 = 20% mais perto)."""
    base = _ceu_base(w, h, angulo, tuple(centro), escala, brilho)
    H2, W2 = base.shape[:2]
    z = 1.0 / (1.0 + zoom)
    cw, ch = w * z, h * z
    ox = float(np.clip((W2 - cw) / 2 + deriva[0] * t * w, 0, W2 - cw - 1))
    oy = float(np.clip((H2 - ch) / 2 + deriva[1] * t * h, 0, H2 - ch - 1))
    out = np.empty((h, w, 3), np.float32)
    _k_ceu(base, out, cw / w, ch / h, ox, oy, luz / 255.0)
    return out


# ---------------------------------------------------------------- pós (brilho, vinheta, grão)
@njit(parallel=True, cache=True, fastmath=True)
def _k_reduz(q, k, limiar, out):
    hh = out.shape[0]
    ww = out.shape[1]
    inv = 1.0 / (k * k)
    for j in prange(hh):
        for i in range(ww):
            for c in range(3):
                s = 0.0
                for a in range(k):
                    for b in range(k):
                        v = q[j * k + a, i * k + b, c] - limiar
                        if v > 0:
                            s += v
                out[j, i, c] = s * inv


@njit(parallel=True, cache=True, fastmath=True)
def _k_caixa(src, dst, raio, eixo):
    """Média móvel (caixa) num eixo; três passadas seguidas ≈ desfoque gaussiano."""
    H, W = src.shape[0], src.shape[1]
    n = 2 * raio + 1
    if eixo == 1:
        for j in prange(H):
            for c in range(3):
                s = 0.0
                for i in range(-raio, raio + 1):
                    s += src[j, min(max(i, 0), W - 1), c]
                for i in range(W):
                    dst[j, i, c] = s / n
                    s += src[j, min(i + raio + 1, W - 1), c] - src[j, max(i - raio, 0), c]
    else:
        for i in prange(W):
            for c in range(3):
                s = 0.0
                for jj in range(-raio, raio + 1):
                    s += src[min(max(jj, 0), H - 1), i, c]
                for jj in range(H):
                    dst[jj, i, c] = s / n
                    s += src[min(jj + raio + 1, H - 1), i, c] - src[max(jj - raio, 0), i, c]


def _desfoca(a, raio):
    b = np.empty_like(a)
    for _ in range(3):
        _k_caixa(a, b, raio, 1)
        _k_caixa(b, a, raio, 0)
    return a


@njit(parallel=True, cache=True, fastmath=True)
def _k_final(q, b1, b2, k, bloom, vinheta, grao, ruido, semente, out):
    H, W = q.shape[0], q.shape[1]
    hh, ww = b1.shape[0], b1.shape[1]
    joelho = 0.8
    nr = ruido.shape[0]
    asp = H / W * 0.62
    for j in prange(H):
        fy = (j + 0.5) / k - 0.5
        iy = int(math.floor(fy))
        ay = fy - iy
        iy = min(max(iy, 0), hh - 2)
        ny = (j / H - 0.5) * 2 * asp
        for i in range(W):
            fx = (i + 0.5) / k - 0.5
            ix = int(math.floor(fx))
            ax = fx - ix
            ix = min(max(ix, 0), ww - 2)
            nx = (i / W - 0.5) * 2
            dv = math.sqrt(nx * nx + ny * ny) - 0.35
            vin = 1.0 - vinheta * (dv ** 1.6 if dv > 0 else 0.0)
            g = ruido[(j * 1031 + i * 7 + semente * 7919) % nr] * grao
            for c in range(3):
                v = q[j, i, c]
                if bloom > 0:
                    a1 = (b1[iy, ix, c] * (1 - ax) + b1[iy, ix + 1, c] * ax) * (1 - ay) + \
                         (b1[iy + 1, ix, c] * (1 - ax) + b1[iy + 1, ix + 1, c] * ax) * ay
                    a2 = (b2[iy, ix, c] * (1 - ax) + b2[iy, ix + 1, c] * ax) * (1 - ay) + \
                         (b2[iy + 1, ix, c] * (1 - ax) + b2[iy + 1, ix + 1, c] * ax) * ay
                    v += (a1 * 0.6 + a2 * 0.9) * bloom
                if v > joelho:
                    e = v - joelho
                    v = joelho + e / (1.0 + e / (1.0 - joelho))
                v = v * vin + g
                v = 0.0 if v < 0 else (1.0 if v > 1 else v)
                out[j, i, c] = np.uint8(v * 255.0 + 0.5)


_RUIDO = np.random.default_rng(3).normal(0, 1, 1 << 20).astype(np.float32)


def finalizar(q, i=0, bloom=0.55, limiar=0.72, vinheta=0.32, grao=0.007):
    """Do quadro float (0 a 1+) para RGB uint8: brilho em volta do que passa do limiar, compressão suave das luzes,
    vinheta e grão de filme."""
    h, w = q.shape[:2]
    k = 4
    hh, ww = h // k, w // k
    pequeno = np.empty((hh, ww, 3), np.float32)
    _k_reduz(q, k, limiar, pequeno)
    b1 = _desfoca(pequeno.copy(), 1)
    b2 = _desfoca(pequeno, 5)
    out = np.empty((h, w, 3), np.uint8)
    _k_final(q, b1, b2, k, bloom, vinheta, grao, _RUIDO, int(i) % 977, out)
    return out


# ---------------------------------------------------------------- mapas feitos por código
@lru_cache(maxsize=4)
def lava(largura=2048, semente=11):
    """Mapa de lava (placas escuras e rachaduras brilhando), equirretangular, float32 0 a 1."""
    H, W = largura // 2, largura
    rnd = np.random.default_rng(semente)
    campo = np.zeros((H, W), np.float32)
    for cel, peso in ((128, 1.0), (52, 0.45), (22, 0.18)):
        qq = rnd.normal(size=(H // cel + 2, W // cel + 2)).astype(np.float32)
        campo += np.asarray(Image.fromarray(qq).resize((W, H), Image.BICUBIC)) * peso
    veios = np.exp(-(np.abs(campo) / 0.06) ** 2)
    base = np.array([0.16, 0.035, 0.03], np.float32)
    quente = np.array([1.0, 0.42, 0.12], np.float32)
    branco = np.array([1.0, 0.9, 0.6], np.float32)
    cor = base + (quente - base) * np.clip(veios * 1.3, 0, 1)[..., None]
    cor = cor + (branco - cor) * np.clip(veios - 0.75, 0, 1)[..., None] * 3
    return np.ascontiguousarray(np.clip(cor, 0, 1).astype(np.float32))


@lru_cache(maxsize=2)
def gelo(largura=4096, semente=21):
    """Terra congelada (equirretangular, float32 0 a 1): mar coberto por placas de gelo azuladas com rachaduras e
    continentes cobertos de neve, mantendo o relevo do mapa do dia."""
    H, W = largura // 2, largura
    dia = _nivel("terra.jpg", largura, "rgb") if tem("terra.jpg") else None
    oce = _nivel("oceano.png", largura, "l") if tem("oceano.png") else None
    if dia is not None:
        a = dia.astype(np.float32) / 255.0
        H, W = a.shape[:2]
        lum = a.mean(axis=2)
    else:
        lum = np.full((H, W), 0.4, np.float32)
    mar = (oce.astype(np.float32) / 255.0) if oce is not None and oce.shape[:2] == (H, W) else np.zeros((H, W), np.float32)
    rnd = np.random.default_rng(semente)
    campo = np.zeros((H, W), np.float32)
    for cel, peso in ((96, 1.0), (40, 0.5), (14, 0.25)):
        qq = rnd.normal(size=(H // cel + 2, W // cel + 2)).astype(np.float32)
        campo += np.asarray(Image.fromarray(qq).resize((W, H), Image.BICUBIC)) * peso
    racha = np.exp(-(np.abs(campo) / 0.05) ** 2)                      # rachaduras finas no gelo do mar
    neve = np.array([0.94, 0.97, 1.0], np.float32) * np.clip(0.82 + 0.35 * lum, 0, 1.05)[..., None]
    placa = np.array([0.74, 0.88, 0.98], np.float32) * (0.93 + 0.07 * np.tanh(campo))[..., None]
    placa = placa * (1 - 0.45 * racha)[..., None] + np.array([0.42, 0.62, 0.82], np.float32) * (0.45 * racha)[..., None]
    cor = neve * (1 - mar)[..., None] + placa * mar[..., None]
    return np.ascontiguousarray(np.clip(cor, 0, 1).astype(np.float32))
