"""Confere um roteiro de documentário antes de mandar para a fábrica (o Claude roda isto sempre, nas tarefas da escala).

Uso:  python canal/conferir_roteiro.py canal/roteiros/<slug>.json                 só confere (rápido)
      python canal/conferir_roteiro.py canal/roteiros/<slug>.json --quadros DIR   e desenha um quadro de cada batida
                                                                                 (folhas DIR/folha-pt-01.jpg...) e a
                                                                                 miniatura (DIR/miniatura-pt.jpg)
Opções: --idiomas pt,en (padrão: pt nos quadros; a conferência é sempre nos dois).

Sai com erro (código 1) se tiver ERRO; AVISO é para olhar e decidir. As durações são estimadas pela velocidade da voz
clonada medida no Roanoke (português: 18,2 letras por segundo).
Precisa de: pip install numpy pillow numba num2words
"""
import json, re, sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

LETRAS_POR_S = {"pt": 18.2, "en": 15.5}     # fala da voz clonada (pt medido no Roanoke; en estimado)
VOZ_PADRAO = {"motor": "clone", "pt": "chatterbox", "en": "edge"}   # 10/11: no inglês, a voz americana nativa (o clone ficou com sotaque)
COMUNS = {"zoom", "pan", "etiquetas"}
ESTILOS = {"papel", "amarelo", "vermelho"}
TRANSICOES = {"corte", "zoom", "flash", "fade"}
erros, avisos = [], []


def erro(msg):
    erros.append(msg)


def aviso(msg):
    avisos.append(msg)


def L(x, idioma):
    return x.get(idioma, x.get("pt")) if isinstance(x, dict) else x


def parametros_das_cenas():
    """cena → parâmetros que ela lê (tirados do código de cenas2d.py, contando as funções que ela chama, para não
    ficar desatualizado quando surgir cena nova)."""
    src = (AQUI / "cenas2d.py").read_text(encoding="utf-8")
    funcs = sorted((m.start(), m.group(1)) for m in re.finditer(r"^def (\w+)\(", src, re.M))
    corpos = {}
    for k, (ini, fn) in enumerate(funcs):
        corpos[fn] = src[ini: funcs[k + 1][0] if k + 1 < len(funcs) else len(src)]
    chaves = {fn: set(re.findall(r'p\.get\("(\w+)"', c)) | set(re.findall(r'p\["(\w+)"\]', c)) for fn, c in corpos.items()}
    chama = {fn: {x for x in re.findall(r"\b(\w+)\(", c) if x in corpos and x != fn} for fn, c in corpos.items()}
    extras = {"mapa": {"rota", "rota_t", "rota2", "rota2_t"}}      # lidas em laço: for chave in ("rota", "rota2")
    cat = re.search(r"CENAS = \{(.*?)\}", src, re.S).group(1)
    out = {}
    for nome, fn in re.findall(r'"(\w+)": (\w+)', cat):
        vistos, fila, ps = set(), [fn], set(extras.get(nome, ()))
        while fila:
            f = fila.pop()
            if f in vistos:
                continue
            vistos.add(f)
            ps |= chaves.get(f, set())
            fila += [x for x in chama.get(f, ()) if not x.startswith(("fundo", "etiqueta"))]
        out[nome] = ps
    return out


def palavras(fala):
    return [w for w in re.split(r"\s+", fala.strip()) if w]


def indice_ok(valor, falas, onde):
    """valor: índice de palavra (int) ou {"pt": i, "en": j}; confere nos dois idiomas."""
    for idioma in ("pt", "en"):
        v = L(valor, idioma)
        n = len(palavras(falas[idioma]))
        if not isinstance(v, int):
            erro(f"{onde}: índice de palavra precisa ser número inteiro (veio {v!r})")
        elif not 0 <= v < n:
            erro(f"{onde}: palavra {v} não existe em {idioma} (a fala tem {n} palavras: 0 a {n - 1})")


def conferir(r, arq):
    cenas = parametros_das_cenas()
    if r.get("formato") != "doc":
        erro('"formato" precisa ser "doc"')
    if r.get("versao") != 2:
        erro('"versao" precisa ser 2')
    slug = r.get("slug", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        erro(f'"slug" inválido: {slug!r} (só letras minúsculas, números e hífen)')
    if Path(arq).stem != slug:
        erro(f"o arquivo precisa se chamar {slug}.json")
    voz = r.get("voz") or {}
    if {k: voz.get(k) for k in VOZ_PADRAO} != VOZ_PADRAO:
        aviso(f"voz diferente da escolhida pelo dono {VOZ_PADRAO}: {voz}")
    for idioma in ("pt", "en"):
        info = r.get(idioma) or {}
        t = info.get("titulo", "")
        if not t:
            erro(f"{idioma}.titulo vazio")
        elif len(t) > 100:
            erro(f"{idioma}.titulo tem {len(t)} letras (o YouTube aceita 100)")
        elif len(t) > 70:
            aviso(f"{idioma}.titulo tem {len(t)} letras: acima de 70 aparece cortado")
        if len(info.get("descricao", "")) < 80:
            erro(f"{idioma}.descricao curta demais (2 a 3 frases que contam o que o vídeo mostra)")
        tags = info.get("tags") or []
        if len(tags) < 5:
            aviso(f"{idioma}.tags: só {len(tags)}")
        if sum(len(x) + 2 for x in tags) > 450:
            erro(f"{idioma}.tags passam de 450 letras somadas (o YouTube aceita 500)")
    if len(r.get("fontes") or []) < 3:
        erro("fontes: pelo menos 3 links que confirmam os fatos")
    if any(not str(u).startswith("https://") for u in r.get("fontes") or []):
        erro("fontes: todos os links começam com https://")
    if len(r.get("checagem") or []) < 6:
        erro("checagem: uma linha por fato conferido (número, data, nome) e de onde veio")

    B = r.get("batidas") or []
    if not 35 <= len(B) <= 110:
        aviso(f"{len(B)} batidas (o Roanoke tem 64 para 6 min 48 s)")
    n_cap = 0
    for i, b in enumerate(B):
        onde = f"batida {i}"
        falas = b.get("fala") or {}
        if not isinstance(falas, dict) or not falas.get("pt") or not falas.get("en"):
            erro(f"{onde}: fala precisa de pt e en")
            continue
        for idioma in ("pt", "en"):
            if len(falas[idioma]) > 240:
                aviso(f"{onde}: fala em {idioma} com {len(falas[idioma])} letras; divida em duas batidas (a voz clonada erra mais em frase longa)")
        cena = b.get("cena")
        if cena not in cenas:
            erro(f"{onde}: cena {cena!r} não existe (cenas: {', '.join(sorted(cenas))})")
            continue
        n_cap += cena == "capitulo"
        p = b.get("params") or {}
        conhecidos = cenas[cena] | COMUNS
        for k, v in p.items():
            base = k[: -len("_palavra")] if k.endswith("_palavra") else k
            if base not in conhecidos:
                aviso(f"{onde}: a cena {cena} não usa o parâmetro {k!r} (usa: {', '.join(sorted(conhecidos))})")
            if k.endswith("_palavra"):
                indice_ok(v, falas, f"{onde} {k}")
        if "fundo" in p and p["fundo"] not in cenas:
            erro(f"{onde}: fundo {p['fundo']!r} não é uma cena")
        posicoes = []
        for j, e in enumerate(p.get("etiquetas") or []):
            o = f"{onde} etiqueta {j}"
            if not e.get("texto"):
                erro(f"{o}: sem texto")
            for idioma in ("pt", "en"):
                tx = str(L(e.get("texto", ""), idioma))
                if len(tx) > 42:
                    aviso(f"{o}: texto em {idioma} com {len(tx)} letras (etiqueta é curta: até ~40)")
            x, y = e.get("x", 0.5), e.get("y", 0.2)
            if not (0.03 <= x <= 0.97 and 0.03 <= y <= 0.97):
                erro(f"{o}: x/y fora da tela ({x}, {y}); use frações de 0,05 a 0,95")
            if e.get("estilo", "papel") not in ESTILOS:
                erro(f"{o}: estilo {e.get('estilo')!r} (use papel, amarelo ou vermelho)")
            if "em_palavra" in e:
                indice_ok(e["em_palavra"], falas, o)
            elif not 0 <= float(e.get("em", 0)) <= 0.95:
                erro(f"{o}: em={e.get('em')} (fração da batida, de 0 a 0,95)")
            for (x2, y2, j2) in posicoes:
                if abs(x - x2) < 0.16 and abs(y - y2) < 0.07:
                    aviso(f"{o}: muito perto da etiqueta {j2} (pode sobrepor)")
            posicoes.append((x, y, j))
        for s in b.get("sons") or []:
            import sons as SN
            if s.get("nome") not in SN.EFEITOS:
                erro(f"{onde}: som {s.get('nome')!r} não existe ({', '.join(SN.EFEITOS)})")
            if "em_palavra" in s:
                indice_ok(s["em_palavra"], falas, f"{onde} som")
        tri = b.get("trilha")
        if tri:
            if tri.get("tipo") not in ("corte", "tensao"):
                erro(f"{onde}: trilha tipo {tri.get('tipo')!r} (corte ou tensao)")
            if "em_palavra" in tri:
                indice_ok(tri["em_palavra"], falas, f"{onde} trilha")
        if b.get("transicao", "fade") not in TRANSICOES:
            erro(f"{onde}: transicao {b.get('transicao')!r} ({', '.join(sorted(TRANSICOES))})")
        if not 0 <= float(b.get("respiro", 0.12)) <= 3:
            erro(f"{onde}: respiro {b.get('respiro')} (0 a 3 segundos)")
    if B and B[0].get("cena") == "capitulo":
        aviso("a 1ª batida é um capítulo: comece pelo gancho (a imagem mais forte), o título vem depois")
    if n_cap and not 2 <= n_cap <= 6:
        aviso(f"{n_cap} capítulos (o Roanoke tem 4)")

    capa = r.get("capa") or {}
    if not isinstance(capa.get("batida"), int) or not 0 <= capa["batida"] < len(B):
        erro("capa.batida precisa apontar para uma batida que existe")
    for idioma in ("pt", "en"):
        linhas = L(capa.get("linhas") or {}, idioma) or []
        if not 1 <= len(linhas) <= 3:
            erro(f"capa.linhas.{idioma}: 1 a 3 linhas curtas")
        try:
            import cenas2d as C2
            f = C2.fonte("Black", 92)
            for ln in linhas:
                w = f.getlength(ln.upper()) + 48
                if w > 1230:
                    erro(f"capa: a linha {ln!r} ({idioma}) não cabe na miniatura ({w:.0f} de 1230 px); encurte")
        except Exception as e:
            aviso(f"não consegui medir as linhas da capa ({e})")

    # duração estimada
    import voz as V
    for idioma in ("pt", "en"):
        letras = sum(len(V.por_extenso(b["fala"][idioma], idioma)) for b in B if isinstance(b.get("fala"), dict) and b["fala"].get(idioma))
        dur = letras / LETRAS_POR_S[idioma] + sum(float(b.get("respiro", 0.12)) for b in B) + float(r.get("cauda", 0.5))
        print(f"{idioma}: ~{dur / 60:.1f} min ({letras} letras faladas)")
        if idioma == "pt" and not 5.5 * 60 <= dur <= 11 * 60:
            aviso(f"duração estimada em português {dur / 60:.1f} min (alvo: 6 a 10 min)")


def linha_do_tempo(r, idioma):
    """Tempos estimados de cada batida e de cada palavra (pela velocidade da voz clonada), sem narrar."""
    import voz as V
    tl, pals, t = [], [], 0.0
    for b in r["batidas"]:
        fala = V.por_extenso(b["fala"][idioma], idioma)
        d = len(fala) / LETRAS_POR_S[idioma]
        ws = palavras(b["fala"][idioma])
        pals.append([{"w": x, "t": d * k / max(1, len(ws)), "d": d / max(1, len(ws))} for k, x in enumerate(ws)])
        fim = t + d + float(b.get("respiro", 0.12))
        tl.append((t, fim))
        t = fim
    tl[-1] = (tl[-1][0], t + float(r.get("cauda", 0.5)))
    return tl, pals


def quadros(r, pasta, idiomas):
    import numpy as np
    from PIL import Image, ImageDraw
    import filme as F
    import cenas2d as C2
    import planeta as PL
    import voz as V
    F.W, F.H = 1920, 1080
    F.POS.update({"bloom": 0.35, "vinheta": 0.3, "grao": 0.006})
    pasta.mkdir(parents=True, exist_ok=True)
    w, h = 960, 540
    for idioma in idiomas:
        B = r["batidas"]
        tl, pals = linha_do_tempo(r, idioma)
        rb = F.resolver(B, idioma, pals, tl)
        imgs = []
        for i, (b, (ini, fim)) in enumerate(zip(rb, tl)):
            dur = fim - ini
            ems = [float(e.get("em", 0)) for e in (b["params"].get("etiquetas") or [])]
            tq = dur * min(0.92, max(0.55, (max(ems) if ems else 0) + 0.12))
            q = np.empty((h, w, 3), np.float32)
            try:
                F.CENAS[b["cena"]](q, tq, dur, F._params(b, idioma), {"W": w, "H": h, "T": ini + tq, "idioma": idioma})
                img = Image.fromarray(PL.finalizar(q, 0, **F.POS)).convert("RGB")
            except Exception as e:
                erro(f"batida {i}: a cena {b['cena']} quebrou ao desenhar ({type(e).__name__}: {e})")
                img = Image.new("RGB", (w, h), (90, 0, 0))
            d = ImageDraw.Draw(img)
            d.rectangle((0, 0, 58, 34), fill=(0, 0, 0))
            d.text((8, 6), f"{i}", fill=(255, 255, 255), font=C2.fonte("Bold", 22))
            imgs.append(img.resize((480, 270)))
        for k in range(0, len(imgs), 20):
            folha = Image.new("RGB", (480 * 4, 270 * 5), (20, 20, 20))
            for n, im in enumerate(imgs[k:k + 20]):
                folha.paste(im, ((n % 4) * 480, (n // 4) * 270))
            folha.save(pasta / f"folha-{idioma}-{k // 20 + 1:02d}.jpg", quality=85)
        tmp = pasta / f"_mini-{idioma}"
        tmp.mkdir(exist_ok=True)
        F.miniatura_doc(dict(r, batidas=rb), idioma, tl, tmp)
        (tmp / "miniatura.jpg").replace(pasta / f"miniatura-{idioma}.jpg")
        for x in tmp.iterdir():
            x.unlink()
        tmp.rmdir()
        print(f"quadros {idioma}: {len(imgs)} batidas em {pasta}/folha-{idioma}-*.jpg e {pasta}/miniatura-{idioma}.jpg")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    arq = sys.argv[1]
    r = json.loads(Path(arq).read_text(encoding="utf-8"))
    conferir(r, arq)
    if "--quadros" in sys.argv and not erros:
        ids = sys.argv[sys.argv.index("--idiomas") + 1].split(",") if "--idiomas" in sys.argv else ["pt"]
        quadros(r, Path(sys.argv[sys.argv.index("--quadros") + 1]), ids)
    for a in avisos:
        print("AVISO:", a)
    for e in erros:
        print("ERRO:", e)
    print(f"{len(erros)} erro(s), {len(avisos)} aviso(s)")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
