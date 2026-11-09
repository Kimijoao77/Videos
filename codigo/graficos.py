"""Gráficos animados do canal (quadro a quadro com Pillow, direto para o ffmpeg).

Tipos de cena: numero, linha_tempo, grafico (linha ou barras), citacao.
Cada função recebe os dados já no idioma certo, a duração em segundos e o tamanho (16:9 ou vertical).
"""
import math, re, subprocess
from PIL import Image, ImageDraw, ImageFont

FPS = 30
AMARELO = (255, 196, 0)
CIANO = (51, 195, 224)
ROXO = (139, 124, 255)
CINZA = (150, 160, 180)
BRANCO = (245, 247, 250)
FUNDO_A, FUNDO_B = (9, 12, 22), (20, 27, 46)
CORES = [AMARELO, CIANO, ROXO, CINZA]

PESOS = {"black": "Inter-Black", "bold": "Inter-Bold", "semi": "Inter-SemiBold", "reg": "Inter-Medium"}
_cache = {}


def fonte(peso, tam):
    k = (peso, tam)
    if k not in _cache:
        for base in ("/usr/share/fonts/opentype/inter/", "/usr/share/fonts/truetype/inter/"):
            for ext in (".otf", ".ttf"):
                try:
                    _cache[k] = ImageFont.truetype(base + PESOS[peso] + ext, tam); break
                except OSError:
                    pass
            if k in _cache:
                break
        else:
            _cache[k] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", tam)
    return _cache[k]


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def fundo(w, h):
    """Azul-escuro com degradê suave e uma grade discreta."""
    img = Image.new("RGB", (w, h), FUNDO_A)
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = (y / h) ** 1.4
        d.line([(0, y), (w, y)], fill=tuple(int(FUNDO_A[i] + (FUNDO_B[i] - FUNDO_A[i]) * k) for i in range(3)))
    passo = max(w, h) // 16
    for x in range(0, w, passo):
        d.line([(x, 0), (x, h)], fill=(26, 33, 52))
    for y in range(0, h, passo):
        d.line([(0, y), (w, y)], fill=(26, 33, 52))
    return img


def quebrar(texto, f, largura, d):
    linhas, atual = [], ""
    for p in str(texto).split():
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=f) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual); atual = p
    if atual:
        linhas.append(atual)
    return linhas


def alfa(cor, a, base=FUNDO_A):
    a = max(0.0, min(1.0, a))
    return tuple(int(base[i] + (cor[i] - base[i]) * a) for i in range(3))


def _escrever(quadros, n, w, h, saida):
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(saida)],
                         stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(quadros(i / FPS).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg falhou ao gravar o gráfico")


def _titulo(d, texto, w, h, a, vertical):
    if not texto:
        return
    f = fonte("bold", int(h * (0.032 if vertical else 0.045)))
    x, y = int(w * 0.07), int(h * (0.12 if vertical else 0.09))
    d.rectangle([x, y, x + int(w * 0.012), y + f.size], fill=alfa(AMARELO, a))
    d.text((x + int(w * 0.025), y - f.size * 0.08), texto, font=f, fill=alfa(BRANCO, a))


# ------------------------------------------------------------------ número grande
_NUM = re.compile(r"(\d[\d.,]*)")


def numero(valor, legenda, dur, w, h, saida, vertical=False):
    base = fundo(w, h)
    m = _NUM.search(valor)
    alvo, casas, sep_dec = None, 0, ","
    if m:
        bruto = m.group(1)
        if "," in bruto and (bruto.count(",") == 1 and len(bruto.split(",")[1]) <= 2):
            sep_dec, casas = ",", len(bruto.split(",")[1]); alvo = float(bruto.replace(".", "").replace(",", "."))
        elif "." in bruto and bruto.count(".") == 1 and len(bruto.split(".")[1]) <= 2:
            sep_dec, casas = ".", len(bruto.split(".")[1]); alvo = float(bruto.replace(",", ""))
        else:
            alvo = float(re.sub(r"[.,]", "", bruto))
    fv = fonte("black", int(h * (0.11 if vertical else 0.19)))
    fl = fonte("semi", int(h * (0.032 if vertical else 0.048)))

    def fmt(x):
        if alvo is None:
            return valor
        if casas:
            s = f"{x:,.{casas}f}"
            s = s.replace(",", "X").replace(".", sep_dec).replace("X", "." if sep_dec == "," else ",")
        else:
            s = f"{int(round(x)):,}".replace(",", "." if sep_dec == "," else ",")
        return valor[:m.start()] + s + valor[m.end():]

    def q(t):
        img = base.copy(); d = ImageDraw.Draw(img)
        k = ease(t / 1.3)
        txt = fmt(alvo * k) if alvo is not None else valor
        larg_final = d.textlength(fmt(alvo) if alvo is not None else valor, font=fv)
        f = fv
        if larg_final > w * 0.86:  # número comprido: diminui a fonte
            f = fonte("black", int(fv.size * w * 0.86 / larg_final))
        cy = h * (0.42 if vertical else 0.40)
        d.text((w / 2, cy), txt, font=f, fill=alfa(AMARELO, min(1, t / 0.3)), anchor="mm")
        bw = w * 0.30 * ease((t - 0.3) / 0.8)
        d.rectangle([w / 2 - bw / 2, cy + f.size * 0.62, w / 2 + bw / 2, cy + f.size * 0.62 + h * 0.008], fill=AMARELO)
        a = ease((t - 0.6) / 0.6)
        for i, l in enumerate(quebrar(legenda, fl, w * 0.8, d)[:3]):
            d.text((w / 2, cy + f.size * 0.62 + h * 0.05 + i * fl.size * 1.25), l, font=fl, fill=alfa(BRANCO, a), anchor="ma")
        return img
    _escrever(q, max(1, round(dur * FPS)), w, h, saida)


# ------------------------------------------------------------------ linha do tempo
def linha_tempo(titulo, eventos, dur, w, h, saida, vertical=False):
    base = fundo(w, h)
    eventos = eventos[:6 if vertical else 5]
    n = len(eventos)
    fa = fonte("black", int(h * (0.042 if vertical else 0.07)))
    ft = fonte("semi", int(h * (0.022 if vertical else 0.032)))
    dur_anim = min(dur * 0.75, 1.0 + 0.9 * n)

    def q(t):
        img = base.copy(); d = ImageDraw.Draw(img)
        _titulo(d, titulo, w, h, ease(t / 0.5), vertical)
        k = ease(t / dur_anim)
        if vertical:
            x0, y0, y1 = w * 0.18, h * 0.22, h * 0.88
            d.line([(x0, y0), (x0, y0 + (y1 - y0) * k)], fill=CINZA, width=6)
            for i, e in enumerate(eventos):
                y = y0 + (y1 - y0) * (i + 0.5) / n
                a = ease((t - (0.4 + i * 0.9 * dur_anim / max(1, n) / 1.2)) / 0.5)
                if a <= 0:
                    continue
                r = 16 + 6 * (1 - a)
                d.ellipse([x0 - r, y - r, x0 + r, y + r], fill=AMARELO)
                d.text((x0 + 50, y - fa.size * 0.9), str(e["data"]), font=fa, fill=alfa(AMARELO, a))
                for j, l in enumerate(quebrar(e["texto"], ft, w * 0.68, d)[:2]):
                    d.text((x0 + 50, y + 8 + j * ft.size * 1.2), l, font=ft, fill=alfa(BRANCO, a))
        else:
            x0, x1, y = w * 0.08, w * 0.92, h * 0.55
            d.line([(x0, y), (x0 + (x1 - x0) * k, y)], fill=CINZA, width=6)
            for i, e in enumerate(eventos):
                x = x0 + (x1 - x0) * (i + 0.5) / n
                a = ease((t - (0.4 + i * 0.9 * dur_anim / max(1, n) / 1.2)) / 0.5)
                if a <= 0:
                    continue
                r = 16 + 8 * (1 - a)
                d.ellipse([x - r, y - r, x + r, y + r], fill=AMARELO)
                d.text((x, y - 40 - 20 * (1 - a)), str(e["data"]), font=fa, fill=alfa(AMARELO, a), anchor="ms")
                larg = (x1 - x0) / n * 0.9
                for j, l in enumerate(quebrar(e["texto"], ft, larg, d)[:3]):
                    d.text((x, y + 44 + j * ft.size * 1.2), l, font=ft, fill=alfa(BRANCO, a), anchor="ma")
        return img
    _escrever(q, max(1, round(dur * FPS)), w, h, saida)


# ------------------------------------------------------------------ gráfico de linha / barras
def _fmt_val(v, unidade):
    s = f"{v:,.1f}" if abs(v) < 100 and v != int(v) else f"{int(round(v)):,}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}{unidade}" if unidade in ("%",) else (f"{s} {unidade}" if unidade else s)


def grafico(titulo, estilo, rotulos, series, unidade, fonte_dados, dur, w, h, saida, vertical=False):
    base = fundo(w, h)
    fx = fonte("semi", int(h * (0.02 if vertical else 0.03)))
    fv = fonte("bold", int(h * (0.022 if vertical else 0.034)))
    ff = fonte("reg", int(h * (0.016 if vertical else 0.024)))
    fl = fonte("semi", int(h * (0.02 if vertical else 0.03)))
    todos = [v for s in series for v in s["valores"] if v is not None]
    vmax = max(todos) if todos else 1
    vmax = vmax * 1.15 if vmax > 0 else 1
    L, R = w * (0.1 if vertical else 0.09), w * (0.92 if vertical else 0.94)
    T, B = h * (0.26 if vertical else 0.22), h * (0.72 if vertical else 0.80)
    n = len(rotulos)
    dur_anim = min(dur * 0.7, 3.0)

    def X(i):
        return L + (R - L) * (i + 0.5) / n

    def Y(v):
        return B - (B - T) * v / vmax

    def q(t):
        img = base.copy(); d = ImageDraw.Draw(img)
        _titulo(d, titulo, w, h, ease(t / 0.5), vertical)
        a0 = ease(t / 0.6)
        for g in range(5):  # grade
            y = B - (B - T) * g / 4
            d.line([(L, y), (R, y)], fill=alfa((60, 70, 95), a0), width=1)
        d.line([(L, B), (R, B)], fill=alfa(CINZA, a0), width=3)
        passo = max(1, math.ceil(n / (6 if vertical else 10)))
        for i, r in enumerate(rotulos):
            if i % passo == 0 or i == n - 1:
                d.text((X(i), B + 14), str(r), font=fx, fill=alfa(CINZA, a0), anchor="ma")
        k = ease((t - 0.4) / dur_anim)
        if estilo == "barras":
            ns = len(series)
            bw = (R - L) / n * 0.7 / ns
            for si, s in enumerate(series):
                cor = CORES[si % len(CORES)]
                for i, v in enumerate(s["valores"]):
                    if v is None:
                        continue
                    ki = ease((t - 0.4 - i * dur_anim * 0.5 / n) / (dur_anim * 0.6))
                    x = X(i) - (R - L) / n * 0.35 + si * bw
                    y = B - (B - Y(v)) * ki
                    d.rectangle([x + 2, y, x + bw - 2, B], fill=cor)
                    if ki > 0.95 and (n <= 12 or i == n - 1):
                        d.text((x + bw / 2, y - 10), _fmt_val(v, unidade), font=fv if n <= 8 else fx, fill=BRANCO, anchor="ms")
        else:
            for si, s in enumerate(series):
                cor = CORES[si % len(CORES)]
                pts = [(X(i), Y(v)) for i, v in enumerate(s["valores"]) if v is not None]
                if len(pts) < 2:
                    continue
                total = (len(pts) - 1) * k
                ate = int(total)
                caminho = pts[:ate + 1]
                if ate < len(pts) - 1:
                    f = total - ate
                    (xa, ya), (xb, yb) = pts[ate], pts[ate + 1]
                    caminho.append((xa + (xb - xa) * f, ya + (yb - ya) * f))
                if len(caminho) >= 2:
                    d.line(caminho, fill=cor, width=8, joint="curve")
                xe, ye = caminho[-1]
                d.ellipse([xe - 12, ye - 12, xe + 12, ye + 12], fill=cor)
                if k >= 0.99:  # valor final ao lado do último ponto
                    d.text((xe, ye - 22), _fmt_val([v for v in s["valores"] if v is not None][-1], unidade), font=fv, fill=cor, anchor="ms")
        if len(series) > 1 or (series and series[0].get("nome")):
            x = L
            for si, s in enumerate(series):
                cor = CORES[si % len(CORES)]
                y = h * (0.80 if vertical else 0.155)
                if not vertical:
                    x0 = w * 0.07 + si * w * 0.22
                    x = x0 + w * 0.025
                d.rectangle([x - 2, y + fl.size * 0.2, x + fl.size * 0.8, y + fl.size], fill=cor)
                d.text((x + fl.size * 1.1, y), s.get("nome", ""), font=fl, fill=BRANCO)
                if vertical:
                    y += fl.size * 1.4
        if fonte_dados:
            d.text((R, h * (0.95 if not vertical else 0.86)), f"Fonte: {fonte_dados}" if not str(fonte_dados).lower().startswith(("fonte", "source")) else fonte_dados,
                   font=ff, fill=CINZA, anchor="rs")
        return img
    _escrever(q, max(1, round(dur * FPS)), w, h, saida)


# ------------------------------------------------------------------ citação
def citacao(texto, autor, dur, w, h, saida, vertical=False, aspas=True):
    base = fundo(w, h)
    fq = fonte("bold", int(h * (0.04 if vertical else 0.06)))
    fa = fonte("semi", int(h * (0.024 if vertical else 0.035)))
    fg = fonte("black", int(h * (0.12 if vertical else 0.2)))

    def q(t):
        img = base.copy(); d = ImageDraw.Draw(img)
        a = ease(t / 0.6)
        if aspas:
            d.text((w * 0.08, h * (0.2 if vertical else 0.12)), "“", font=fg, fill=alfa(AMARELO, a))
        linhas = quebrar(texto, fq, w * 0.8, d)[:6]
        y0 = h / 2 - len(linhas) * fq.size * 0.65
        for i, l in enumerate(linhas):
            ai = ease((t - 0.2 - i * 0.12) / 0.5)
            d.text((w * 0.1, y0 + i * fq.size * 1.3 + 12 * (1 - ai)), l, font=fq, fill=alfa(BRANCO, ai))
        if autor:
            for j, l in enumerate(quebrar(f"— {autor}", fa, w * 0.8, d)[:3]):
                d.text((w * 0.1, y0 + len(linhas) * fq.size * 1.3 + 30 + j * fa.size * 1.3), l, font=fa, fill=alfa(AMARELO, ease((t - 0.8) / 0.5)))
        return img
    _escrever(q, max(1, round(dur * FPS)), w, h, saida)
