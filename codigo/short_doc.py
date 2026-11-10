"""Short vertical (1080×1920) feito do começo de um documentário do Aqui Há Dragões / Here Be Dragons.

O gancho do documentário (do começo até o cartão de título, fechando numa troca de batida até 75 s) vira um Short: o
vídeo deitado fica no meio, em cima dele mesmo ampliado e desfocado; no alto vão o nome do canal e a frase da
miniatura (capa.linhas do roteiro); embaixo, a legenda palavra a palavra (a palavra falada em amarelo); no fim, 1,6 s
com o convite para o documentário completo. Usa a imagem e o som do vídeo já pronto (não desenha as cenas de novo):
leva poucos minutos.

O filme.py chama fazer() logo depois de montar cada documentário, e no modo --so-short (para um vídeo que já estava
pronto antes de existir o Short: lá ele renderiza de novo só o gancho). Se o Short falhar, o documentário segue normal.
"""
import json
import math
import re
import subprocess
from pathlib import Path

from PIL import Image

W, H, FPS = 1080, 1920, 30
MAXIMO = 75.0            # o gancho fecha numa troca de batida até aqui (Shorts vão até 3 min; o gancho costuma dar 50 a 65 s)
CAUDA = 1.6              # segundos finais com o convite para o documentário
VIDEO_Y = 596            # topo do vídeo deitado (1080×608), um pouco acima do meio
TOPO_Y, LEGENDA_Y = 300, 1470
CANAL = {"pt": "AQUI HÁ DRAGÕES", "en": "HERE BE DRAGONS"}
CONVITE = {"pt": ["DOCUMENTÁRIO", "COMPLETO NO CANAL"], "en": ["FULL DOCUMENTARY", "ON THE CHANNEL"]}
BRANCO, AMARELO = (255, 255, 255), (255, 196, 0)


def L(x, idioma):
    if isinstance(x, dict):
        return x.get(idioma) or x.get("pt") or ""
    return x or ""


def ponto_de_corte(batidas, tl, maximo=MAXIMO):
    """Até onde vai o gancho: o começo do cartão de título (a partir da 4ª batida), fechando numa troca de batida que
    caiba em `maximo` segundos. Devolve (segundos, quantas batidas entram)."""
    k = next((i for i, b in enumerate(batidas) if b.get("cena") == "titulo" and i >= 3), None)
    limite = min(tl[k][0] if k is not None else tl[-1][1], maximo)
    fins = [(fim, i + 1) for i, (_, fim) in enumerate(tl) if fim <= limite + 1e-6]
    if fins:
        return fins[-1]
    return min(limite, tl[0][1]), 1


def duracao(arq):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def blocos_legenda(palavras, fim, max_palavras=3, max_chars=16):
    """Palavras com tempo ({w, t, d}, segundos do vídeo) em blocos curtos que aparecem um de cada vez."""
    blocos, atual = [], []
    for p in [p for p in palavras if p["t"] < fim]:
        atual.append(p)
        txt = " ".join(x["w"] for x in atual)
        if len(atual) >= max_palavras or len(txt) >= max_chars or re.search(r"[.!?,;:…]$", p["w"]):
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    out = []
    for i, b in enumerate(blocos):
        ini, ate = b[0]["t"], b[-1]["t"] + b[-1]["d"] + 0.35
        if i + 1 < len(blocos):
            ate = min(ate, blocos[i + 1][0]["t"])
        out.append({"p": b, "ini": ini, "fim": min(ate, fim)})
    return out


class Camadas:
    """Tudo o que vai por cima do vídeo, quadro a quadro (RGBA 1080×1920): nome do canal, frase da capa, legenda e
    o convite do fim. As partes fixas são desenhadas uma vez só."""

    def __init__(self, F, r, idioma, palavras, fim):
        self.F, self.idioma, self.fim = F, idioma, fim
        self.base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nome = F.texto_rgba([[(CANAL.get(idioma, ""), BRANCO)]], F.fonte("bold", 36), None, contorno=5)
        F.colar(self.base, nome, W / 2, 110)
        capa = r.get("capa") or {}
        linhas = L(capa.get("linhas"), idioma) or [L((r.get(idioma) or {}).get("titulo"), idioma)]
        destaque = set(capa.get("destaque") or [])
        fnt = F.fonte("black", 96)
        todas = []
        for i, ln in enumerate(linhas):
            cor = AMARELO if i in destaque else BRANCO
            todas += F.quebra([(w, cor) for w in str(ln).upper().split()], fnt, W * 0.9)
        if todas:
            F.colar(self.base, F.texto_rgba(todas, fnt, None, contorno=9), W / 2, TOPO_Y)
        self.fnt_leg = F.fonte("extrabold", 70)
        self.blocos = blocos_legenda(palavras, fim)
        self.cache = {}
        fc = F.fonte("black", 64)
        conv = CONVITE.get(idioma, CONVITE["en"])
        linhas_c = (F.quebra([(w, BRANCO) for w in conv[0].split()], fc, W * 0.88)
                    + F.quebra([(w, AMARELO) for w in conv[1].split()], fc, W * 0.88))
        self.convite = F.texto_rgba(linhas_c, fc, None, contorno=9)

    def legenda(self, T):
        for bi, b in enumerate(self.blocos):
            if b["ini"] <= T < b["fim"]:
                break
        else:
            return None
        ativa = max([k for k, p in enumerate(b["p"]) if p["t"] <= T + 0.03] or [0])
        chave = (bi, ativa)
        if chave not in self.cache:
            pal = [(re.sub(r"[,;:]$", "", p["w"]).upper(), AMARELO if k == ativa else BRANCO) for k, p in enumerate(b["p"])]
            self.cache = {k: v for k, v in self.cache.items() if k[0] >= bi - 1}
            self.cache[chave] = self.F.texto_rgba(self.F.quebra(pal, self.fnt_leg, W * 0.86), self.fnt_leg, None)
        k = (T - b["ini"]) / 0.16
        return self.cache[chave], (0.82 + 0.18 * min(1.0, k) if k < 1 else 1.0), min(1.0, k * 3)

    def quadro(self, T):
        img = self.base.copy()
        if T < self.fim:
            leg = self.legenda(T)
            if leg:
                camada, esc, alfa = leg
                self.F.colar(img, camada, W / 2, LEGENDA_Y, escala=esc, alfa=alfa)
        else:                                                   # o convite, em cima do último quadro parado
            k = min(1.0, (T - self.fim) / 0.25)
            self.F.colar(img, self.convite, W / 2, LEGENDA_Y, escala=0.9 + 0.1 * k, alfa=k)
        return img


def fazer(r, idioma, video, tl, palavras, saida, maximo=MAXIMO):
    """Faz o Short de `video` (o documentário pronto, 1920×1080 com som). tl: [(início, fim)] de cada batida em
    segundos; palavras: [{w, t, d}] com t em segundos do vídeo. Devolve a checagem com a duração do Short."""
    import filme as F                                           # os mesmos textos e fontes da fábrica
    fim, n = ponto_de_corte(r["batidas"], tl, maximo)
    dur_video = duracao(video)
    if dur_video:
        fim = min(fim, dur_video - 0.05)
    total = fim + CAUDA
    camadas = Camadas(F, r, idioma, palavras, fim)
    filtro = (f"[0:v]fps={FPS},split=2[a][b];"
              f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=26,"
              f"eq=brightness=-0.12:saturation=0.85[fundo];"
              f"[b]scale={W}:-2[meio];"
              f"[fundo][meio]overlay=0:{VIDEO_Y}[base];"
              f"[base]tpad=stop_mode=clone:stop_duration={CAUDA}[parado];"
              f"[parado][1:v]overlay=0:0:format=auto,format=yuv420p[v];"
              f"[0:a]afade=t=out:st={max(0.0, fim - 0.15):.3f}:d=0.15,apad=pad_dur={CAUDA}[som]")
    saida = Path(saida)
    proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-t", f"{fim:.3f}", "-i", str(video),
                             "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-filter_complex", filtro, "-map", "[v]", "-map", "[som]", "-t", f"{total:.3f}",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "10M", "-bufsize", "20M",
                             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(saida)],
                            stdin=subprocess.PIPE)
    try:
        for f in range(int(math.ceil(total * FPS))):
            proc.stdin.write(camadas.quadro(f / FPS).tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    if proc.wait() or not saida.exists():
        raise RuntimeError("o ffmpeg não montou o Short")
    qc = F.checar(saida, total)
    qc.update({"duracao_s": round(duracao(saida) or total, 1), "corte_s": round(fim, 2), "batidas": n})
    return qc


def meta_short(info_l, idioma):
    """Título e descrição do Short (o robô de postagem acrescenta o link do documentário quando ele estiver no ar)."""
    titulo = (info_l.get("short_titulo") or info_l.get("titulo") or "").strip()
    if len(titulo) > 91:
        titulo = titulo[:90].rstrip(" :,-")
    desc = (info_l.get("descricao") or "").split("\n\n")[0].strip()
    return {"titulo": f"{titulo} #shorts", "descricao": desc}


if __name__ == "__main__":                                       # teste: python canal/short_doc.py roteiro.json pt video.mp4 tempos.json saida.mp4
    import sys
    rot = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    tempos = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
    print(fazer(rot, sys.argv[2], sys.argv[3], tempos["tl"], tempos["palavras"], sys.argv[5]))
