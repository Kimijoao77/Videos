"""Fábrica v2 do Fora de Órbita / Out of Orbit: Shorts com visual realista, legenda palavra a palavra, sons e trilha.

Uso:  python canal/filme.py canal/roteiros/<slug>.json [--saida canal/saida] [--idiomas pt,en] [--offline] [--ate S]

O roteiro (versão 2) tem "batidas": cada uma é uma frase da narração com a cena que aparece enquanto ela é falada.
  {"fala": {"pt": "...", "en": "..."},
   "cena": "terra", "params": {...},                        cena de cenas3d.py (o catálogo está lá)
   "texto": {"tipo": "titulo|contador|numero|rotulo", ...}, texto grande na tela (opcional; ver desenhar_texto)
   "transicao": "corte|zoom|flash|fade",                    como esta batida entra (padrão: zoom)
   "sons": [{"nome": "impacto", "em": 0.4}],                efeitos de sons.py, em fração da batida
   "trilha": {"tipo": "corte", "em": 0.4, "dur": 1.2},      a trilha some (ou "tensao" até "ate" batidas depois)
   "respiro": 0.15}                                         pausa depois da fala (segundos)
Textos {...} podem ser {"pt": ..., "en": ...} ou um texto só. Parâmetros de cena com {"pt", "en"} também.

Sai em <saida>/<slug>/<idioma>/: short.mp4, capa.jpg (um quadro da cena com o título), meta.json.
Regra do projeto: a única IA que cria conteúdo é o Claude (roteiro); o visual e o som são feitos por código.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import cenas2d as C2  # noqa: E402
import cenas3d as C3  # noqa: E402
import efeitos as FX  # noqa: E402
import planeta as PL  # noqa: E402
import sons as SN  # noqa: E402
import voz as V  # noqa: E402

W, H, FPS = 1080, 1920, 30          # Short vertical; roteiro com "formato": "doc" vira 1920×1080 (vídeo longo)
SR = SN.SR
CENAS = {**C3.CENAS, **C2.CENAS}
POS = {}                             # ajustes do pós (brilho, vinheta, grão) vindos do roteiro
FONTES = Path(__file__).parent / "fontes"
AMARELO = (255, 196, 0)
NOITE = (6, 10, 30)
BRANCO = (255, 255, 255)


def L(x, idioma):
    if isinstance(x, dict):
        return x.get(idioma) or x.get("pt") or ""
    return x if x is not None else ""


def sh(*cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr[-3000:])
        raise RuntimeError(f"falhou: {' '.join(map(str, cmd[:6]))}…")
    return r.stdout + r.stderr


def fonte(peso, tam):
    arq = {"black": "Unbounded-Black.ttf", "extrabold": "Unbounded-ExtraBold.ttf", "bold": "Unbounded-Bold.ttf",
           "semibold": "Unbounded-SemiBold.ttf", "medium": "Unbounded-Medium.ttf"}[peso]
    return ImageFont.truetype(str(FONTES / arq), tam)


def _params(b, idioma):
    p = {}
    for k, v in (b.get("params") or {}).items():
        p[k] = L(v, idioma) if isinstance(v, dict) and ("pt" in v or "en" in v) else v
    return p


def resolver(batidas, idioma, palavras, tl):
    """Cópia das batidas no idioma, com os tempos marcados por palavra ("..._palavra": índice da palavra na fala)
    trocados por frações da batida (o Sol some exatamente na palavra "some")."""
    out = []
    for b, pal, (ini, fim) in zip(batidas, palavras, tl):
        dur = max(1e-6, fim - ini)

        def frac(idx):
            idx = int(L(idx, idioma))
            return (pal[min(max(idx, 0), len(pal) - 1)]["t"] / dur) if pal else 0.0

        nb = json.loads(json.dumps(b))
        p = _params(nb, idioma)
        for k in list(p):
            if k.endswith("_palavra"):
                p[k[: -len("_palavra")]] = frac(p.pop(k))
        nb["params"] = p
        for e in p.get("etiquetas") or []:
            if "em_palavra" in e:
                e["em"] = frac(e.pop("em_palavra"))
        for s in nb.get("sons") or []:
            if "em_palavra" in s:
                s["em"] = frac(s.pop("em_palavra"))
        if nb.get("trilha") and "em_palavra" in nb["trilha"]:
            nb["trilha"]["em"] = frac(nb["trilha"].pop("em_palavra"))
        out.append(nb)
    return out


# ------------------------------------------------------------------ texto com contorno e sombra
def texto_rgba(linhas, fnt, cores, contorno=8, sombra=True, espaco=1.04):
    """linhas: [[(palavra, cor), ...], ...] → imagem RGBA justa, centralizada linha a linha."""
    esp = fnt.getlength(" ")
    asc, desc = fnt.getmetrics()
    alt_l = int((asc + desc) * espaco)
    larg = [sum(fnt.getlength(w) for w, _ in ln) + esp * (len(ln) - 1) for ln in linhas]
    pad = contorno + 24
    cw, ch = int(max(larg) + pad * 2), int(alt_l * len(linhas) + pad * 2)
    camada = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    if sombra:
        sb = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sb)
    for li, ln in enumerate(linhas):
        x = (cw - larg[li]) / 2
        y = pad + li * alt_l
        for w, cor in ln:
            if sombra:
                ds.text((x + 2, y + 10), w, font=fnt, fill=(0, 0, 0, 170), stroke_width=contorno + 2, stroke_fill=(0, 0, 0, 170))
            d.text((x, y), w, font=fnt, fill=cor, stroke_width=contorno, stroke_fill=NOITE)
            x += fnt.getlength(w) + esp
    if sombra:
        sb = sb.filter(ImageFilter.GaussianBlur(9))
        sb.alpha_composite(camada)
        camada = sb
    return camada


def quebra(palavras, fnt, largura_max):
    """Divide em linhas que cabem na largura (palavras: [(texto, cor)])."""
    esp = fnt.getlength(" ")
    linhas, atual, w = [], [], 0.0
    for p in palavras:
        lw = fnt.getlength(p[0])
        if atual and w + esp + lw > largura_max:
            linhas.append(atual)
            atual, w = [], 0.0
        w += (esp if atual else 0) + lw
        atual.append(p)
    if atual:
        linhas.append(atual)
    return linhas


def colar(img, camada, cx, cy, escala=1.0, alfa=1.0):
    if escala != 1.0:
        camada = camada.resize((max(1, int(camada.width * escala)), max(1, int(camada.height * escala))), Image.BILINEAR)
    if alfa < 1.0:
        a = camada.getchannel("A").point(lambda v: int(v * alfa))
        camada = camada.copy()
        camada.putalpha(a)
    img.alpha_composite(camada, (int(cx - camada.width / 2), int(cy - camada.height / 2)))


def _volta(x):
    """Curva com um pequeno exagero no fim (o texto 'pula' ao aparecer)."""
    x = min(1.0, max(0.0, x))
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ------------------------------------------------------------------ legenda palavra a palavra
class Legenda:
    def __init__(self, palavras, idioma, y=0.70, tam=78, max_palavras=3, max_chars=16):
        self.y = y
        self.fnt = fonte("extrabold", tam)
        blocos, atual = [], []
        for p in palavras:
            atual.append(p)
            txt = " ".join(x["w"] for x in atual)
            if len(atual) >= max_palavras or len(txt) >= max_chars or re.search(r"[.!?,;:…]$", p["w"]):
                blocos.append(atual)
                atual = []
        if atual:
            blocos.append(atual)
        self.blocos = []
        for i, b in enumerate(blocos):
            ini = b[0]["t"]
            fim = b[-1]["t"] + b[-1]["d"] + 0.35
            if i + 1 < len(blocos):
                fim = min(fim, blocos[i + 1][0]["t"])
            self.blocos.append({"p": b, "ini": ini, "fim": fim})
        self.cache = {}

    def desenhar(self, img, T):
        for bi, b in enumerate(self.blocos):
            if b["ini"] <= T < b["fim"]:
                break
        else:
            return
        ativa = max([k for k, p in enumerate(b["p"]) if p["t"] <= T + 0.03] or [0])
        chave = (bi, ativa)
        if chave not in self.cache:
            pal = [(re.sub(r"[,;:]$", "", p["w"]).upper(), AMARELO if k == ativa else BRANCO) for k, p in enumerate(b["p"])]
            self.cache = {k: v for k, v in self.cache.items() if k[0] >= bi - 1}
            self.cache[chave] = texto_rgba(quebra(pal, self.fnt, W * 0.86), self.fnt, None)
        k = (T - b["ini"]) / 0.16
        esc = 0.82 + 0.18 * _volta(k) if k < 1 else 1.0
        colar(img, self.cache[chave], W / 2, H * self.y, escala=esc, alfa=min(1.0, k * 3))


# ------------------------------------------------------------------ textos grandes das batidas
def _fmt(v, formato, sufixo, idioma):
    if formato == "mm:ss":
        v = max(0, int(round(v)))
        return f"{v // 60}:{v % 60:02d}"
    if formato == "inteiro":
        s = f"{int(round(v)):,}"
        return (s.replace(",", ".") if idioma == "pt" else s) + sufixo
    n = int(round(v))
    return (f"−{abs(n)}" if n < 0 else str(n)) + sufixo


_CACHE_TXT = {}


def desenhar_texto(img, spec, t, dur, idioma):
    """Tipos: titulo {texto, y, tam, destaque (palavra amarela)}; contador {de, ate, formato mm:ss|inteiro|graus,
    sufixo, t: [t0, t1] frações, y, rotulo}; rotulo {texto, x, y, tam} (etiqueta pequena)."""
    if not spec:
        return
    tipo = spec.get("tipo", "titulo")
    entra = FX.sai(t / 0.22, 3)
    if tipo == "titulo":
        txt = L(spec.get("texto"), idioma)
        dest = L(spec.get("destaque"), idioma).upper()
        chave = ("titulo", txt, idioma, spec.get("tam", 84))
        if chave not in _CACHE_TXT:
            fnt = fonte("black", spec.get("tam", 84))
            pal = [(w, AMARELO if dest and w.strip("?!.,") == dest else BRANCO) for w in txt.upper().split()]
            _CACHE_TXT[chave] = texto_rgba(quebra(pal, fnt, W * 0.88), fnt, None, contorno=9)
        colar(img, _CACHE_TXT[chave], W / 2, H * spec.get("y", 0.15) + (1 - entra) * 40, alfa=entra)
    elif tipo == "contador":
        t0, t1 = spec.get("t", [0.0, 1.0])
        k = FX.entre(t / max(dur, 1e-6), t0, t1)
        k = k if spec.get("linear", True) else FX.suave(k)
        v = FX.mistura(float(L(spec.get("de", 0), idioma)), float(L(spec.get("ate", 0), idioma)), k)
        s = _fmt(v, spec.get("formato", "inteiro"), L(spec.get("sufixo", ""), idioma), idioma)
        fnt = fonte("black", spec.get("tam", 150))
        cor = AMARELO if spec.get("amarelo", True) else BRANCO
        camada = texto_rgba([[(s, cor)]], fnt, None, contorno=10)
        y = H * spec.get("y", 0.16)
        colar(img, camada, W / 2, y + (1 - entra) * 40, alfa=entra)
        rot = L(spec.get("rotulo"), idioma)
        if rot:
            chave = ("rot", rot)
            if chave not in _CACHE_TXT:
                fr = fonte("bold", 40)
                _CACHE_TXT[chave] = texto_rgba([[(rot.upper(), BRANCO)]], fr, None, contorno=6)
            colar(img, _CACHE_TXT[chave], W / 2, y + camada.height * 0.5 + 6, alfa=entra)
    elif tipo == "rotulo":
        txt = L(spec.get("texto"), idioma).upper()
        chave = ("rotulo", txt, spec.get("tam", 46))
        if chave not in _CACHE_TXT:
            fr = fonte("bold", spec.get("tam", 46))
            _CACHE_TXT[chave] = texto_rgba([[(txt, AMARELO if spec.get("amarelo") else BRANCO)]], fr, None, contorno=6)
        colar(img, _CACHE_TXT[chave], W * spec.get("x", 0.5), H * spec.get("y", 0.2), alfa=entra)


# ------------------------------------------------------------------ som
def ler_wav(arq):
    with wave.open(str(arq)) as w:
        n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
        a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a).astype(np.float32)
    return a


def gravar_wav(arq, a):
    a = a if a.ndim == 2 else a[:, None]
    with wave.open(str(arq), "wb") as w:
        w.setnchannels(a.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def mixar(batidas, tl, total, vozes, saida):
    n = int(SR * (total + 0.2))
    voz = np.zeros(n, np.float32)
    for (ini, _), a in zip(tl, vozes):
        i0 = int(ini * SR)
        voz[i0:i0 + len(a)] += a[: max(0, n - i0)]
    sfx = np.zeros(n, np.float32)
    eventos = []
    for i, (b, (ini, fim)) in enumerate(zip(batidas, tl)):
        dur = fim - ini
        sons = list(b.get("sons") or [])
        tr = b.get("transicao", "zoom")
        if i > 0 and tr in ("zoom", "corte") and not b.get("sem_whoosh"):
            sons.append({"nome": "whoosh", "em_s": -0.18, "vol": 0.22})
        if i > 0 and tr == "flash":
            sons.append({"nome": "impacto", "em_s": 0.0, "vol": 0.7})
        for s in sons:
            x = SN.efeito(s["nome"])
            t0 = ini + (s["em_s"] if "em_s" in s else s.get("em", 0.0) * dur)
            i0 = max(0, int(t0 * SR))
            m = min(len(x), n - i0)
            if m > 0:
                sfx[i0:i0 + m] += x[:m] * s.get("vol", 0.8)
        tri = b.get("trilha")
        if tri:
            e = dict(tri)
            e["t"] = ini + e.pop("em", 0.0) * dur
            if "ate_batida" in e:
                j = min(len(tl) - 1, i + int(e.pop("ate_batida")))
                e["ate"] = tl[j][1]
            eventos.append(e)
    musica = SN.trilha(total, eventos, semente=len(batidas))[:n]
    if len(musica) < n:
        musica = np.vstack([musica, np.zeros((n - len(musica), 2), np.float32)])
    # a trilha abaixa quando a voz fala
    env = np.abs(voz)
    k = int(SR * 0.12)
    env = np.convolve(env, np.ones(k, np.float32) / k, mode="same")
    ganho = 1.0 - 0.6 * np.clip(env / 0.04, 0, 1)
    ganho = np.convolve(ganho, np.ones(k, np.float32) / k, mode="same")
    mix = musica * (0.55 * ganho)[:, None] + (voz * 1.0 + sfx * 0.55)[:, None]
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    gravar_wav(saida, mix)
    return saida


# ------------------------------------------------------------------ montagem
def narrar(batidas, idioma, tmp, offline, voz_cfg):
    """voz_cfg (do roteiro): {"motor": "edge|kokoro", "pt": "nome da voz", "en": "...", "velocidade": 1.0}."""
    duracoes, palavras, vozes, origens = [], [], [], set()
    voz_cfg = voz_cfg or {}
    for i, b in enumerate(batidas):
        texto = L(b["fala"], idioma)
        dur, pal, origem = V.narrar(texto, idioma, tmp, f"b{i:02d}", offline, motor=voz_cfg.get("motor", "edge"),
                                    voz=voz_cfg.get(idioma), velocidade=float(voz_cfg.get("velocidade", 1.0)))
        origens.add(origem)
        duracoes.append(dur)
        palavras.append(pal)
        vozes.append(ler_wav(tmp / f"b{i:02d}.wav"))
    return duracoes, palavras, vozes, origens


def renderizar(r, idioma, tl, total, legenda, saida, ate=None):
    batidas = r["batidas"]
    proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                             "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", str(saida)],
                            stdin=subprocess.PIPE)
    n = int(math.ceil((min(total, ate) if ate else total) * FPS))
    q = np.empty((H, W, 3), np.float32)
    q2 = np.empty((H, W, 3), np.float32)
    escuros, t_ini = 0, time.time()
    for f in range(n):
        T = f / FPS
        i = next((k for k, (a, b) in enumerate(tl) if a <= T < b), len(tl) - 1)
        b = batidas[i]
        ini, fim = tl[i]
        dur, t = fim - ini, T - ini
        ctx = {"W": W, "H": H, "T": T, "idioma": idioma}
        CENAS[b["cena"]](q, t, dur, _params(b, idioma), ctx)
        quadro = q
        tr = b.get("transicao", "zoom") if i > 0 else "nenhuma"
        if tr == "zoom" and t < 0.32:
            quadro = FX.zoom(q, 1.0 + 0.07 * (1 - FX.sai(t / 0.32, 3)))
        elif tr == "flash" and t < 0.25:
            quadro = q + (1 - t / 0.25) ** 2 * 0.9
        elif tr == "fade" and t < 0.4:
            pb = batidas[i - 1]
            pi_, pf = tl[i - 1]
            CENAS[pb["cena"]](q2, t + (pf - pi_), pf - pi_, _params(pb, idioma), ctx)
            k = FX.suave(t / 0.4)
            quadro = q2 * (1 - k) + q * k
        img = Image.fromarray(PL.finalizar(quadro, f, **POS)).convert("RGBA")
        desenhar_texto(img, b.get("texto"), t, dur, idioma)
        legenda.desenhar(img, T)
        rgb = img.convert("RGB")
        if np.asarray(rgb)[::16, ::16].mean() < 3:
            escuros += 1
        proc.stdin.write(rgb.tobytes())
        if f % 150 == 0:
            print(f"    quadro {f}/{n} ({time.time() - t_ini:.0f}s)", flush=True)
    proc.stdin.close()
    proc.wait()
    return {"quadros": n, "quadros_quase_pretos": escuros, "segundos_render": round(time.time() - t_ini)}


def capa(r, idioma, tl, pasta):
    """capa.jpg (vertical, para o app e para escolher o quadro do Short) e miniatura.jpg (1280×720 no estilo da marca):
    um quadro da batida escolhida, sem legenda, com o título curto."""
    import marca as MC
    c = r.get("capa") or {}
    i = int(c.get("batida", 0))
    ini, fim = tl[i]
    t = c.get("t", 0.5) * (fim - ini)
    b = r["batidas"][i]
    linhas = L(c.get("linhas"), idioma) or [L(r[idioma].get("titulo"), idioma)]
    dest = set(c.get("destaque", [len(linhas) - 1]))
    q = np.empty((H, W, 3), np.float32)
    CENAS[b["cena"]](q, t, fim - ini, _params(b, idioma), {"W": W, "H": H, "T": ini + t, "idioma": idioma})
    img = Image.fromarray(PL.finalizar(q, 0)).convert("RGBA")
    fnt = fonte("black", 104)
    pal = [[(ln.upper(), AMARELO if k in dest else BRANCO)] for k, ln in enumerate(linhas)]
    colar(img, texto_rgba(pal, fnt, None, contorno=10), W / 2, H * c.get("y", 0.2))
    img.convert("RGB").save(pasta / "capa.jpg", quality=92)
    # horizontal: a mesma cena refeita em 1280×720, com o assunto à direita e o texto à esquerda
    w2, h2 = 1280, 720
    p2 = dict(_params(b, idioma), **(c.get("params_horizontal") or {"r": 0.34, "x": 0.7, "y": 0.5}))
    q2 = np.empty((h2, w2, 3), np.float32)
    CENAS[b["cena"]](q2, t, fim - ini, p2, {"W": w2, "H": h2, "T": ini + t, "idioma": idioma})
    quadro = Image.fromarray(PL.finalizar(q2, 0, vinheta=0.2))
    MC.miniatura(quadro, [ln.upper() for ln in linhas], destaque=tuple(dest), lado="esquerda").convert("RGB").save(
        pasta / "miniatura.jpg", quality=92)


# polígono de papel rasgado da faixa vermelha (o mesmo clip-path da miniatura aprovada pelo dono em 08/11)
_RASGO = [(0, 8), (3, 0), (9, 6), (15, 1), (22, 5), (30, 0), (38, 4), (46, 1), (54, 6), (62, 0), (70, 4), (78, 1), (86, 5),
          (93, 0), (100, 7), (99, 50), (100, 92), (95, 100), (88, 95), (80, 100), (72, 96), (64, 100), (55, 95), (47, 100),
          (39, 96), (31, 100), (23, 95), (15, 100), (7, 96), (0, 100), (1, 50)]


def _texto_esp(d, xy, txt, f, fill, esp):
    """Texto com espaço entre letras (esp em px; negativo aperta), mantendo o kerning dos pares (como letter-spacing)."""
    for i, ch in enumerate(txt):
        d.text((xy[0] + f.getlength(txt[:i]) + esp * i, xy[1]), ch, font=f, fill=fill, anchor="ls")


def miniatura_doc(r, idioma, tl, pasta):
    """Miniatura do vídeo longo (1280×720) no estilo aprovado pelo dono (08/11/2026, sem logo): a cena da batida da
    capa sem etiquetas; à esquerda, em Poppins Black, a 1ª linha em creme com sombra dura e a linha de destaque em
    branco numa faixa vermelha de papel rasgado, um pouco torta. capa: {"batida", "t", "linhas": {pt: [..], en: [..]},
    "destaque": [1], "params": {...} (troca parâmetros da cena só na capa)}."""
    c = r.get("capa") or {}
    i = int(c.get("batida", 0))
    ini, fim = tl[i]
    t = c.get("t", 0.5) * (fim - ini)
    b = r["batidas"][i]
    w2, h2 = 1280, 720
    q = np.empty((h2, w2, 3), np.float32)
    p2 = dict(_params(b, idioma), **(c.get("params") or {}))
    p2["etiquetas"] = []
    CENAS[b["cena"]](q, t, fim - ini, p2, {"W": w2, "H": h2, "T": ini + t, "idioma": idioma})
    img = Image.fromarray(PL.finalizar(q, 0, bloom=0.3, vinheta=0.35, grao=0.004)).convert("RGBA")
    linhas = [ln.upper() for ln in (L(c.get("linhas"), idioma) or [L(r[idioma].get("titulo"), idioma)])]
    dest = set(c.get("destaque", [len(linhas) - 1]))
    tam = 118                                                     # encolhe se a linha mais larga não couber
    while tam > 64 and max(C2.fonte("Black", tam).getlength(ln) * 0.99 + (60 if k in dest else 0)
                           for k, ln in enumerate(linhas)) > w2 - 56 - 44:
        tam -= 4
    f = C2.fonte("Black", tam)
    k_ = tam / 118
    esp = -0.01 * tam                                            # letter-spacing: -0.01em
    x, topo = 56, 44
    for k, ln in enumerate(linhas):
        base = topo + round(100 * k_)                              # linha da base, como no CSS (line-height 1)
        if k in dest:
            pt_, pl, pb = round(10 * k_), round(30 * k_), round(16 * k_)
            lw, lh = round(f.getlength(ln) + esp * len(ln)) + 2 * pl, tam + pt_ + pb
            faixa = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
            d = ImageDraw.Draw(faixa)
            d.polygon([(a / 100 * (lw - 1), b_ / 100 * (lh - 1)) for a, b_ in _RASGO], fill=(196, 60, 46, 255))
            _texto_esp(d, (pl, pt_ + round(100 * k_)), ln, f, (255, 255, 255, 255), esp)
            torta = faixa.rotate(2, resample=Image.BICUBIC, expand=True)
            img.alpha_composite(torta, (round(x + lw / 2 - torta.width / 2), round(topo + lh / 2 - torta.height / 2)))
            topo += lh + round(10 * k_)
        else:
            brilho = Image.new("RGBA", img.size, (0, 0, 0, 0))
            _texto_esp(ImageDraw.Draw(brilho), (x, base), ln, f, (0, 0, 0, 140), esp)
            img.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(14)))
            camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dc = ImageDraw.Draw(camada)
            _texto_esp(dc, (x, base + round(6 * k_)), ln, f, (34, 30, 28, 255), esp)
            _texto_esp(dc, (x, base), ln, f, (240, 229, 204, 255), esp)
            img.alpha_composite(camada)
            topo += tam + round(10 * k_)
    img.convert("RGB").save(pasta / "miniatura.jpg", quality=92)
    img.convert("RGB").save(pasta / "capa.jpg", quality=92)


class _SemLegenda:
    def desenhar(self, img, T):
        pass


def fazer_short(r, idioma, video, tl, todas, pasta):
    """O Short do documentário (canal/short_doc.py). Devolve o que entra no meta.json, ou None se falhar: o Short nunca
    derruba o documentário."""
    try:
        import short_doc as SD
        if not Path(video).exists():
            raise RuntimeError(f"falta {video}")
        print(f"[{idioma}] Short…", flush=True)
        qc = SD.fazer(r, idioma, video, tl, todas, pasta / "short.mp4")
        return {"_checagem": {"short": qc}, "duracao_short_s": round(qc["duracao_s"]), "short": SD.meta_short(r[idioma], idioma)}
    except Exception as e:  # noqa: BLE001
        print(f"[{idioma}] o Short falhou (o documentário segue normal): {e}", flush=True)
        return None


def juntar(video, audio, final):
    """Imagem e som num mp4 só, com o volume no padrão do YouTube (-14 LUFS)."""
    sh("ffmpeg", "-y", "-v", "error", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
       "-af", "loudnorm=I=-14:TP=-1.0:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
       "-movflags", "+faststart", final)


def checar(arq, total):
    log = sh("ffmpeg", "-v", "info", "-i", arq, "-af", "silencedetect=n=-45dB:d=2.5", "-f", "null", "-")
    silencios = [round(float(x), 1) for x in re.findall(r"silence_duration: ([\d.]+)", log)]
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)          # hh:mm:ss (antes pegava só os segundos: 7:03 → 3 s)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    return {"silencios": silencios, "ok": not [x for x in silencios if x > 3.0] and dur > 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roteiro")
    ap.add_argument("--saida", default="canal/saida")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--idiomas", default="pt,en")
    ap.add_argument("--ate", type=float, default=None, help="renderiza só os primeiros S segundos (teste)")
    ap.add_argument("--so-short", action="store_true",
                    help="documentário já pronto: renderiza só o gancho e faz o Short (precisa de <saida>/<slug>/<idioma>/meta.json)")
    ap.add_argument("--sem-short", action="store_true", help="documentário sem o Short")
    a = ap.parse_args()
    r = json.loads(Path(a.roteiro).read_text(encoding="utf-8"))
    global W, H
    doc = r.get("formato") == "doc"
    if doc:                                                     # vídeo longo deitado, sem legenda queimada
        W, H = 1920, 1080
        POS.update({"bloom": 0.35, "vinheta": 0.3, "grao": 0.006})
    POS.update(r.get("pos") or {})
    raiz = Path(a.saida) / r["slug"]
    for idioma in a.idiomas.split(","):
        pasta = raiz / idioma
        tmp = pasta / "_tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        print(f"[{idioma}] narração…", flush=True)
        duracoes, palavras, vozes, origens = narrar(r["batidas"], idioma, tmp, a.offline, r.get("voz"))
        tl, t = [], 0.0
        for b, d in zip(r["batidas"], duracoes):
            dur = d + float(b.get("respiro", 0.12))
            tl.append((t, t + dur))
            t += dur
        total = t + float(r.get("cauda", 0.5))
        tl[-1] = (tl[-1][0], total)
        todas = [{"w": p["w"], "t": ini + p["t"], "d": p["d"]} for (ini, _), pal in zip(tl, palavras) for p in pal]
        (pasta / "tempos.json").write_text(json.dumps({"tl": tl, "palavras": todas}), encoding="utf-8")
        legenda = Legenda(todas, idioma) if (not doc or r.get("legenda")) else _SemLegenda()
        rl = dict(r, batidas=resolver(r["batidas"], idioma, palavras, tl))
        for b in rl["batidas"]:
            b.setdefault("transicao", r.get("transicao_padrao", "fade" if doc else "zoom"))
        if a.so_short:
            # O documentário já está na Release: renderiza de novo só o gancho (com a narração e o código de agora, então
            # a legenda bate com a voz mesmo que alguma fala tenha sido refeita depois) e faz o Short dele. O meta.json do
            # documentário (baixado da Release) só ganha o Short.
            if not doc:
                raise SystemExit("--so-short é só para documentário (formato doc)")
            import short_doc as SD
            meta_arq = pasta / "meta.json"
            meta = json.loads(meta_arq.read_text(encoding="utf-8")) if meta_arq.exists() else {}
            if not meta.get("titulo"):
                raise SystemExit(f"[{idioma}] falta o meta.json do documentário em {meta_arq}")
            fim, _ = SD.ponto_de_corte(r["batidas"], tl)
            print(f"[{idioma}] só o Short: gancho de {fim:.1f}s; renderizando…", flush=True)
            renderizar(rl, idioma, tl, total, legenda, tmp / "video.mp4", fim + 0.5)
            gancho = tmp / "gancho.mp4"
            juntar(tmp / "video.mp4", mixar(rl["batidas"], tl, total, vozes, tmp / "mix.wav"), gancho)
            curto = fazer_short(r, idioma, gancho, tl, todas, pasta)
            if not curto:
                raise SystemExit(f"[{idioma}] o Short não saiu")
            meta.setdefault("checagem", {}).update(curto.pop("_checagem"))
            meta.update(curto)
            meta_arq.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"ok {idioma}: {pasta / 'short.mp4'} · {meta['checagem'].get('short')}", flush=True)
            continue
        print(f"[{idioma}] {len(r['batidas'])} batidas, {total:.1f}s; renderizando…", flush=True)
        video = tmp / "video.mp4"
        info = renderizar(rl, idioma, tl, total, legenda, video, a.ate)
        audio = mixar(rl["batidas"], tl, total, vozes, tmp / "mix.wav")
        nome = "video" if doc else "short"
        final = pasta / f"{nome}.mp4"
        juntar(video, audio, final)
        (miniatura_doc if doc else capa)(rl, idioma, tl, pasta)
        qc = checar(final, total)
        qc.update(info)
        info_l = r[idioma]
        fontes_txt = "\n".join(f"- {u}" for u in r.get("fontes", []))
        creditos = {"pt": ("Fontes", "Visual, sons e trilha feitos por código. Mapas: NASA (domínio público) e Solar System "
                                     "Scope (CC BY 4.0). Narração com voz sintética."),
                    "en": ("Sources", "Visuals, sound and music made with code. Maps: NASA (public domain) and Solar System "
                                      "Scope (CC BY 4.0). Narration uses a synthetic voice.")}[idioma]
        if doc:
            creditos = (creditos[0], {"pt": "Ilustrações, mapas, sons e trilha feitos por código (contornos dos mapas: "
                                            "Natural Earth, domínio público). Narração com voz sintética.",
                                      "en": "Illustrations, maps, sound and music made with code (map outlines: Natural "
                                            "Earth, public domain). Narration uses a synthetic voice."}[idioma])
        meta = {"titulo": info_l["titulo"], "tags": info_l.get("tags", []), ("duracao_s" if doc else "duracao_short_s"): round(total),
                "voz": sorted(origens), "checagem": {nome: qc},
                "descricao": f"{info_l['descricao']}\n\n{creditos[0]}:\n{fontes_txt}\n\n{creditos[1]}"}
        if doc and not a.sem_short:                            # o gancho vira um Short vertical (canal/short_doc.py)
            curto = fazer_short(r, idioma, final, tl, todas, pasta)
            if curto:
                meta["checagem"].update(curto.pop("_checagem"))
                meta.update(curto)
        (pasta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"ok {idioma}: {final} · {qc}", flush=True)


if __name__ == "__main__":
    main()
