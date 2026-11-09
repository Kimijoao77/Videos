"""Monta os vídeos do canal a partir de um roteiro (JSON), em português e inglês (versão 2).

Uso:  python canal/gerar.py canal/roteiros/<slug>.json [--saida canal/saida] [--offline] [--idiomas pt,en]

Cada cena do roteiro tem a narração (pt/en) e um "visual":
  {"tipo": "cena", "nome": "queda", "params": {...}}      cena da marca desenhada por código (cenas.py: o catálogo está lá)
  {"tipo": "anim", "nome": "tsunami", "params": {...}}    cena antiga desenhada por código (animacoes.py)
  {"tipo": "foto", "busca": "Nokia 3310"}                 foto real (Wikimedia); sem foto, um cartão com o texto
  {"tipo": "numero", "valor": {...}, "legenda": {...}}     número grande animado
  {"tipo": "linha_tempo", "titulo": {...}, "eventos": [{"data": "1865", "texto": {...}}]}
  {"tipo": "grafico", "estilo": "linha|barras", "titulo": {...}, "rotulos": [...], "series": [{"nome": {...}, "valores": [...]}],
   "unidade": "%", "fonte": "..."}
  {"tipo": "citacao", "texto": {...}, "autor": "..."}       só frases reais, com autor
Textos {...} podem ser {"pt": "...", "en": "..."} ou um texto só.
Roteiros antigos (cena com "busca") continuam funcionando; o antigo tipo "ia" vira um cartão com o texto.
Regra do projeto: a única IA é o Claude, que escreve o roteiro. Nada de imagem de IA: o visual é feito por código.

Sai em <saida>/<slug>/<idioma>/: video.mp4, short.mp4, miniatura.jpg, meta.json (título, descrição com fontes e créditos, tags e checagem).
"""
import argparse, hashlib, json, os, random, re, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import graficos as G  # noqa: E402
import voz as V  # noqa: E402
import animacoes as AN  # noqa: E402
import cenas as CN  # noqa: E402
import marca as MC  # noqa: E402
import trilha as TR  # noqa: E402

FPS = 30
PAUSA = 0.35
UA = "CanalHistoriasBot/0.2 (https://github.com/Kimijoao77)"
MUSICA = Path(__file__).parent / "musica"


def L(x, idioma):
    if isinstance(x, dict):
        return x.get(idioma) or x.get("pt") or ""
    return x or ""


def sh(*cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr[-3000:])
        raise RuntimeError(f"falhou: {' '.join(map(str, cmd[:6]))}…")
    return r.stdout + r.stderr


# ------------------------------------------------------------------ imagens e vídeos
def _baixar(url, dest, headers=None):
    import requests
    r = requests.get(url, headers={"User-Agent": UA, **(headers or {})}, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)


def foto_wikimedia(termo, texto, pasta, usados):
    import requests
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers={"User-Agent": UA}, timeout=30, params={
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{termo} filetype:bitmap",
            "gsrnamespace": 6, "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 2400})
        paginas = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    except Exception as e:
        print("  busca no Wikimedia falhou:", termo, e)
        return None, None
    tentou = 0
    for p in paginas:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 900 or p["title"] in usados:
            continue
        if tentou >= 4:
            break
        tentou += 1
        meta = ii.get("extmetadata", {})
        licenca = (meta.get("LicenseShortName") or {}).get("value", "")
        autor = re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()[:80]
        dest = pasta / ("w_" + hashlib.md5(p["title"].encode()).hexdigest()[:10] + ".jpg")
        try:
            _baixar(ii.get("thumburl") or ii["url"], dest)
            Image.open(dest).convert("RGB").save(dest, quality=92)
        except Exception as e:
            print("  download falhou:", p["title"], e)
            continue
        usados.add(p["title"])
        return dest, f"{p['title'].removeprefix('File:')} — {autor or 'autor desconhecido'} ({licenca or 'Wikimedia Commons'})"
    return None, None


def video_pexels(termo, pasta, vertical, usados):
    chave = os.environ.get("PEXELS_API_KEY")
    if not chave or not termo:
        return None, None
    import requests
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": chave}, timeout=30,
                         params={"query": termo, "orientation": "portrait" if vertical else "landscape", "per_page": 8})
        videos = r.json().get("videos", [])
    except Exception as e:
        print("  busca no Pexels falhou:", e)
        return None, None
    for v in videos:
        if v["id"] in usados or v.get("duration", 0) < 4:
            continue
        arqs = sorted([f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 720],
                      key=lambda f: abs((f.get("height") or 0) - (1920 if vertical else 1080)))
        if not arqs:
            continue
        dest = pasta / f"p_{v['id']}.mp4"
        try:
            _baixar(arqs[0]["link"], dest)
        except Exception as e:
            print("  download do Pexels falhou:", e)
            continue
        usados.add(v["id"])
        return dest, f"Vídeo: {v.get('user', {}).get('name', 'Pexels')} (Pexels)"
    return None, None


def cobrir(img, w, h):
    iw, ih = img.size
    k = max(w / iw, h / ih)
    img = img.resize((max(w, round(iw * k)), max(h, round(ih * k))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def quadro_foto(arq, w, h, vertical):
    """Foto preenchendo a tela; no vertical, a foto inteira no meio com a mesma borrada atrás."""
    img = Image.open(arq).convert("RGB")
    if not vertical:
        return ImageEnhance.Brightness(cobrir(img, w, h)).enhance(0.85)
    fundo = ImageEnhance.Brightness(cobrir(img, w, h).filter(ImageFilter.GaussianBlur(50))).enhance(0.45)
    frente = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
    if frente.height > h * 0.6:
        frente = cobrir(frente, w, int(h * 0.6))
    fundo.paste(frente, (0, int(h * 0.40 - frente.height / 2)))
    return fundo


def selo(texto, w, h, vertical):
    camada = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not texto:
        return camada
    d = ImageDraw.Draw(camada)
    f = G.fonte("black", int(h * (0.032 if vertical else 0.042)))
    x0, y0 = int(w * 0.05), int(h * (0.08 if vertical else 0.07))
    bx = d.textbbox((0, 0), texto, font=f)
    pad = int(f.size * 0.45)
    d.rounded_rectangle([x0, y0, x0 + bx[2] + 2 * pad, y0 + bx[3] + 2 * pad], radius=pad // 2, fill=G.AMARELO + (245,))
    d.text((x0 + pad, y0 + pad - bx[1] // 2), texto, font=f, fill=(12, 14, 20))
    return camada


def clipe_foto(arq, dur, saida, w, h, mov, vertical, selo_png):
    """Foto parada vira vídeo: zoom lento + leve deslocamento, entrada e saída suaves."""
    base = quadro_foto(arq, int(w * 1.25), int(h * 1.25), vertical) if not vertical else quadro_foto(arq, w, h, True).resize((int(w * 1.25), int(h * 1.25)))
    src = saida.with_suffix(".png")
    base.save(src)
    n = max(1, round(dur * FPS))
    z = {"in": f"1+0.10*on/{n}", "out": f"1.10-0.10*on/{n}"}[mov]
    dx = {"in": "iw/2-(iw/zoom/2)", "out": f"(iw-iw/zoom)*on/{n}"}[mov]
    filtro = (f"[0]zoompan=z='{z}':d=1:x='{dx}':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={FPS},"
              f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0, dur - 0.25):.2f}:d=0.25[v]")
    ent = ["-loop", "1", "-framerate", FPS, "-i", src]
    if selo_png:
        ent += ["-i", selo_png]
        filtro += ";[v][1]overlay=0:0[v]"
    sh("ffmpeg", "-y", "-v", "error", *ent, "-filter_complex", filtro, "-map", "[v]", "-frames:v", n,
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", FPS, saida)


def clipe_video(arq, dur, saida, w, h, selo_png):
    filtro = (f"[0]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},eq=brightness=-0.04,"
              f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0, dur - 0.25):.2f}:d=0.25[v]")
    ent = ["-stream_loop", "-1", "-i", arq]
    if selo_png:
        ent += ["-i", selo_png]
        filtro += ";[v][1]overlay=0:0[v]"
    sh("ffmpeg", "-y", "-v", "error", *ent, "-filter_complex", filtro, "-map", "[v]", "-t", f"{dur:.3f}", "-an",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", saida)


def cartao(texto, w, h, saida, dur):
    G.citacao(texto, "", dur, w, h, saida, vertical=h > w, aspas=False)


# ------------------------------------------------------------------ legenda animada
def ass_t(s):
    s = max(0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def legenda(palavras_com_tempo, arq, w, h, vertical):
    """Legenda em blocos curtos; a palavra que está sendo falada fica amarela."""
    tam = int(h * (0.045 if vertical else 0.058))
    margem = int(h * (0.27 if vertical else 0.07))
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,Inter Black,{tam},&H00FFFFFF,&H00FFFFFF,&H00101010,&H78000000,-1,0,0,0,100,100,0,0,1,{max(3, tam // 11)},2,2,80,80,{margem},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    max_chars = 20 if vertical else 34
    blocos, atual = [], []
    for p in palavras_com_tempo:
        atual.append(p)
        if len(" ".join(x["w"] for x in atual)) >= max_chars or re.search(r"[.!?;:]$", p["w"]):
            blocos.append(atual); atual = []
    if atual:
        blocos.append(atual)
    linhas = []
    for bi, b in enumerate(blocos):
        fim_bloco = b[-1]["t"] + b[-1]["d"] + 0.2
        if bi + 1 < len(blocos):
            fim_bloco = min(fim_bloco, blocos[bi + 1][0]["t"])
        for i, p in enumerate(b):
            ini = p["t"]
            fim = b[i + 1]["t"] if i + 1 < len(b) else fim_bloco
            if fim <= ini:
                continue
            ws = [x["w"].upper() if vertical else x["w"] for x in b]
            txt = " ".join(("{\\c&H00C4FF&}" + x + "{\\c&HFFFFFF&}") if j == i else x for j, x in enumerate(ws))
            linhas.append(f"Dialogue: 0,{ass_t(ini)},{ass_t(fim)},Base,,0,0,0,,{txt}")
    arq.write_text(cab + "\n".join(linhas) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ montagem
def visual_da(cena):
    v = cena.get("visual")
    if v:
        return v
    return {"tipo": "foto", "busca": cena.get("busca")}


def render_cena(i, cena, idioma, dur, w, h, vertical, tmp, cache, usados, creditos, offline):
    v = visual_da(cena)
    tipo = v.get("tipo", "foto")
    saida = tmp / f"cena{i:02d}.mp4"
    dest_txt = L(cena.get(f"destaque_{idioma}") or cena.get("destaque"), idioma)
    sel = None
    if dest_txt and tipo in ("foto", "ia", "video"):
        sel = tmp / f"selo{i:02d}.png"
        selo(dest_txt, w, h, vertical).save(sel)
    if tipo == "numero":
        G.numero(L(v.get("valor"), idioma), L(v.get("legenda"), idioma), dur, w, h, saida, vertical); return saida
    if tipo == "linha_tempo":
        ev = [{"data": e.get("data", ""), "texto": L(e.get("texto"), idioma)} for e in v.get("eventos", [])]
        G.linha_tempo(L(v.get("titulo"), idioma), ev, dur, w, h, saida, vertical); return saida
    if tipo == "grafico":
        se = [{"nome": L(s.get("nome"), idioma), "valores": s.get("valores", [])} for s in v.get("series", [])]
        G.grafico(L(v.get("titulo"), idioma), v.get("estilo", "linha"), v.get("rotulos", []), se, L(v.get("unidade"), idioma),
                  L(v.get("fonte"), idioma), dur, w, h, saida, vertical); return saida
    if tipo == "cena":  # cena da marca (cenas.py)
        params = {k: (L(x, idioma) if isinstance(x, dict) else x) for k, x in (v.get("params") or {}).items()}
        params["_idioma"] = idioma
        CN.render(v["nome"], params, dur, w, h, saida); return saida
    if tipo == "anim":  # cena 100% desenhada por código (animacoes.py)
        params = {k: L(x, idioma) for k, x in (v.get("params") or {}).items()}
        AN.render(v["nome"], params, dur, w, h, saida); return saida
    if tipo == "citacao":
        G.citacao(L(v.get("texto"), idioma), L(v.get("autor"), idioma), dur, w, h, saida, vertical); return saida
    # foto / ia / video: procura uma vez e reaproveita no outro idioma
    chave = cena.get("_id")
    if chave not in cache:
        arq, cred, eh_video = None, None, False
        pasta = tmp.parent.parent
        if not offline:
            if tipo == "foto" and v.get("busca"):
                arq, cred = foto_wikimedia(v["busca"], cena.get("pt", ""), pasta, usados)
            if not arq and (tipo == "video" or tipo == "foto") and v.get("busca"):
                arq, cred = video_pexels(v.get("busca_video") or v["busca"], pasta, vertical, usados)
                eh_video = bool(arq)
        cache[chave] = (arq, cred, eh_video)
    arq, cred, eh_video = cache[chave]
    if cred and cred not in creditos:
        creditos.append(cred)
    if not arq:
        cartao(dest_txt or L(cena.get(idioma), idioma)[:80], w, h, saida, dur); return saida
    if eh_video:
        clipe_video(arq, dur, saida, w, h, sel)
    else:
        clipe_foto(arq, dur, saida, w, h, "in" if i % 2 == 0 else "out", vertical, sel)
    return saida


def montar(cenas, idioma, pasta, nome, w, h, offline, cache, usados, creditos, final_txt=None):
    vertical = h > w
    tmp = pasta / f"_{nome}"
    tmp.mkdir(parents=True, exist_ok=True)
    clipes, wavs, palavras, t, vozes = [], [], [], 0.0, set()
    for i, c in enumerate(cenas):
        print(f"  [{idioma}/{nome}] cena {i + 1}/{len(cenas)} ({visual_da(c).get('tipo', 'foto')})")
        texto = L(c.get(idioma), idioma)
        dur, pal, origem = V.narrar(texto, idioma, tmp, f"voz{i:02d}", offline)
        vozes.add(origem)
        total = dur + PAUSA
        clipes.append(render_cena(i, c, idioma, total, w, h, vertical, tmp, cache, usados, creditos, offline))
        pad = tmp / f"voz{i:02d}_p.wav"
        sh("ffmpeg", "-y", "-v", "error", "-i", tmp / f"voz{i:02d}.wav", "-af", f"apad=pad_dur={PAUSA}", "-t", f"{total:.3f}", pad)
        wavs.append(pad)
        palavras += [{"w": p["w"], "t": t + p["t"], "d": p["d"]} for p in pal]
        t += total
    if final_txt:
        arq = tmp / "fim.mp4"
        CN.render("fim", {"texto": final_txt, "_idioma": idioma}, 2.5, w, h, arq)
        clipes.append(arq)
        sil = tmp / "fim.wav"
        sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "2.5", sil)
        wavs.append(sil)
        t += 2.5
    (tmp / "clipes.txt").write_text("".join(f"file '{p.name}'\n" for p in clipes))
    (tmp / "vozes.txt").write_text("".join(f"file '{p.name}'\n" for p in wavs))
    sh("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", tmp / "vozes.txt", tmp / "voz.wav")
    ass = tmp / "legenda.ass"
    legenda(palavras, ass, w, h, vertical)
    audio = tmp / "voz.wav"
    musicas = sorted(MUSICA.glob("*.mp3")) + sorted(MUSICA.glob("*.m4a")) if MUSICA.exists() else []
    if not musicas and not offline:  # sem música na pasta: trilha feita por código
        musicas = [TR.trilha(t + 2, tmp / "trilha.wav", semente=len(cenas) + len(nome))]
    if musicas:  # música baixinha, que abaixa mais quando a voz fala
        m = random.Random(nome + str(len(cenas))).choice(musicas)
        sh("ffmpeg", "-y", "-v", "error", "-i", tmp / "voz.wav", "-stream_loop", "-1", "-i", m, "-filter_complex",
           "[1:a]volume=0.22,aresample=44100[m];[m][0:a]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600[md];"
           f"[0:a][md]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={max(0, t - 2):.2f}:d=2[a]",
           "-map", "[a]", "-t", f"{t:.3f}", tmp / "mix.wav")
        audio = tmp / "mix.wav"
    final = pasta / f"{nome}.mp4"
    sh("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", tmp / "clipes.txt", "-i", audio, "-vf", f"ass={ass}",
       "-map", "0:v", "-map", "1:a", "-r", FPS,
       "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", "-shortest", final)
    return final, t, vozes


def checar(arq):
    """Controle de qualidade: tela preta e silêncio longos."""
    log = sh("ffmpeg", "-v", "info", "-i", arq, "-vf", "blackdetect=d=1.5:pix_th=0.06", "-af", "silencedetect=n=-45dB:d=3", "-f", "null", "-")
    pretas = re.findall(r"black_duration:([\d.]+)", log)
    silencios = re.findall(r"silence_duration: ([\d.]+)", log)
    return {"telas_pretas": [round(float(x), 1) for x in pretas], "silencios": [round(float(x), 1) for x in silencios],
            "ok": not pretas and not [x for x in silencios if float(x) > 4.0]}  # o cartão final do Short tem 2,5 s sem voz


def miniatura_marca(r, idioma, pasta):
    """Capa no estilo do canal: um quadro de uma cena (cenas.py) + 2 ou 3 linhas curtas (marca.miniatura)."""
    m = r.get("miniatura") or {}
    if not m.get("cena"):
        return False
    params = {k: (L(x, idioma) if isinstance(x, dict) else x) for k, x in (m.get("params") or {}).items()}
    params.pop("rotulo", None)
    params["_idioma"] = idioma
    dur = 6.0
    quadro = CN.CENAS[m["cena"]](float(m.get("t", 0.6)) * dur, dur, 1280, 720, params)
    linhas = L(m.get("linhas"), idioma) or [r[idioma]["miniatura"].upper()]
    MC.miniatura(quadro, linhas, destaque=tuple(m.get("destaque", [len(linhas) - 1])), lado=m.get("lado", "esquerda")).save(pasta / "miniatura.jpg", quality=92)
    return True


def miniatura(info, cache, slug, pasta, offline):
    W, H = 1280, 720
    arq = next((a for (a, _, v) in cache.values() if a and not v), None)
    base = ImageEnhance.Brightness(cobrir(Image.open(arq).convert("RGB"), W, H)).enhance(0.75) if arq else G.fundo(W, H)
    d = ImageDraw.Draw(base, "RGBA")
    d.rectangle([0, int(H * 0.52), W, H], fill=(0, 0, 0, 150))
    palavras = info["miniatura"].upper().split()
    linhas, atual = [], ""
    for p in palavras:
        if len(atual + " " + p) > 13 and atual:
            linhas.append(atual); atual = p
        else:
            atual = (atual + " " + p).strip()
    linhas.append(atual)
    f = G.fonte("black", 120 if len(linhas) <= 2 else 92)
    y = H - 36 - len(linhas) * (f.size + 6)
    for i, l in enumerate(linhas):
        d.text((48, y + i * (f.size + 6)), l, font=f, fill=G.AMARELO if i == len(linhas) - 1 else (255, 255, 255),
               stroke_width=5, stroke_fill=(0, 0, 0))
    d.rectangle([0, 0, W, 10], fill=G.AMARELO)
    base.save(pasta / "miniatura.jpg", quality=92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roteiro")
    ap.add_argument("--saida", default="canal/saida")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--idiomas", default="pt,en")
    ap.add_argument("--so-short", action="store_true")
    a = ap.parse_args()
    r = json.loads(Path(a.roteiro).read_text(encoding="utf-8"))
    r.setdefault("cenas", [])
    for i, c in enumerate(r["cenas"]):
        c["_id"] = f"c{i}"
    for i, c in enumerate(r.get("short", [])):
        c["_id"] = f"s{i}"
        busca = visual_da(c).get("busca")  # o Short reaproveita a imagem da cena com a mesma busca
        par = next((x for x in r["cenas"] if busca and visual_da(x).get("busca") == busca), None)
        if par:
            c["_id"] = par["_id"]
    raiz = Path(a.saida) / r["slug"]
    cache, usados = {}, set()
    for idioma in a.idiomas.split(","):
        pasta = raiz / idioma
        pasta.mkdir(parents=True, exist_ok=True)
        info = r[idioma]
        creditos, dur, vozes, qc = [], 0, set(), {}
        if not a.so_short and r["cenas"]:
            arq, dur, vozes = montar(r["cenas"], idioma, pasta, "video", 1920, 1080, a.offline, cache, usados, creditos)
            qc["video"] = checar(arq)
        arq, dur_short, v2 = montar(r.get("short", []), idioma, pasta, "short", 1080, 1920, a.offline, cache, usados, creditos,
                                    final_txt=info.get("chamada_short"))
        qc["short"] = checar(arq)
        if not miniatura_marca(r, idioma, pasta):
            miniatura(info, cache, r["slug"], pasta, a.offline)
        fontes = "\n".join(f"- {u}" for u in r.get("fontes", []))
        cred = "\n".join(f"- {c}" for c in creditos)
        rot = {"pt": ("Fontes", "Imagens", "Animações e trilha feitas por código. Narração com voz sintética."),
               "en": ("Sources", "Images", "Animations and music made with code. Narration uses a synthetic voice.")}[idioma]
        meta = {"titulo": info["titulo"], "tags": info.get("tags", []), "duracao_s": round(dur), "duracao_short_s": round(dur_short),
                "voz": sorted(vozes | v2), "checagem": qc,
                "descricao": f"{info['descricao']}\n\n{rot[0]}:\n{fontes}\n\n" + (f"{rot[1]}:\n{cred}\n\n" if cred else "") + rot[2]}
        (pasta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"ok {idioma}: {pasta} · checagem: {'ok' if all(x['ok'] for x in qc.values()) else qc}")


if __name__ == "__main__":
    main()
