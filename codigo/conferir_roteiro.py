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
import json, re, sys, unicodedata
from collections import Counter, defaultdict
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
    if not 10 <= len(B) <= 110:
        aviso(f"{len(B)} batidas (alvo: 50 a 75 para 7 a 10 min)")
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
    for idioma in ("pt", "en"):
        dur = estimar_duracao(r, idioma)
        print(f"{idioma}: ~{dur / 60:.1f} min")
        if idioma == "pt" and len(B) >= 30 and not 6.5 * 60 <= dur <= 11 * 60:
            aviso(f"duração estimada em português {dur / 60:.1f} min (alvo: 7 a 10 min)")
    conferir_estilo(r)


# ------------------------------------------------------------------ estilo (10/11/2026)
# O dono achou os vídeos repetitivos, densos, sem pausa e com cara de texto de IA. Estas conferências acusam o que
# causou isso no Vasa (ver "Como escrever" no ROTEIRO.md).
FORMULAS = {                       # fórmulas de texto de IA: ERRO
    "pt": [r"\bneste (v[ií]deo|document[aá]rio)\b", r"\bvamos (descobrir|explorar|mergulhar|desvendar|entender|conhecer)\b",
           r"\bpara entender\b[^.?!…]*\b(precisa|precisamos|temos que)\b",
           r"\bagora,? (a gente|n[oó]s) (pode|podemos) voltar\b", r"\bum detalhe (fazia|faz|fez) toda a diferen[cç]a\b",
           r"\b[eé] aqui que (tudo|a hist[oó]ria)\b", r"\ba hist[oó]ria n[aã]o (termina|acaba|para) (a[ií]|por a[ií])\b",
           r"\bmudaria (tudo )?para sempre\b", r"\bprepare-se\b", r"\bsem mais delongas\b", r"\bfique at[eé] o final\b"],
    "en": [r"\bin this (video|documentary)\b", r"\blet'?s (dive|explore|uncover|take a (closer )?look)\b", r"\bdelve\b",
           r"\blittle did (they|he|she|anyone) know\b", r"\bbuckle up\b", r"\bthe story doesn'?t (end|stop) there\b",
           r"\bto understand\b[^.?!…]*\bwe (need|have) to\b", r"\bchanged? (\w+ )?forever\b", r"\bstay (tuned|until the end)\b"],
}
GASTAS = {                         # palavras de redação: AVISO
    "pt": [r"\bintrigante", r"\bfascinante", r"\benigm[aá]tic", r"\bjornada\b", r"\bdesvendar", r"\bcrucia(l|is)\b",
           r"\bfundamenta(l|is)\b", r"\bvale (lembrar|ressaltar|destacar)\b", r"\bcuriosamente\b", r"\bum[a]? verdadeir[oa]\b",
           r"\bno cora[cç][aã]o d", r"\bacredite\b", r"\bspoiler\b", r"\bsimplesmente\b", r"\bliteralmente\b"],
    "en": [r"\btapestry\b", r"\btestament to\b", r"\bjourney\b", r"\bunravel", r"\bfascinating\b", r"\bintriguing\b",
           r"\benigmatic\b", r"\bit'?s worth noting\b", r"\bin the heart of\b", r"\bcrucial\b", r"\bsimply\b", r"\bliterally\b"],
}
TIQUES = {                         # construções que viram tique: no máximo 1 por vídeo
    "pt": [(r"\bn[aã]o era\b[^.?!…]{0,60}[.…]\s+era\b", "Não era X. Era Y."), (r"\btalvez \w+ demais\b", "Talvez X demais.")],
    "en": [(r"\b(it|this|that) wasn'?t\b[^.?!…]{0,60}[.…]\s+it was\b", "It wasn't X. It was Y."), (r"\bmaybe too \w+\b", "Maybe too X.")],
}
PARADAS = {
    "pt": "a o os as um uma uns umas de do da dos das em no na nos nas num numa por pelo pela pelos pelas para pra pro com "
          "sem e ou mas que se ele ela eles elas lhe isso isto esse essa este esta aquele aquela foi era e ser ter tinha tem "
          "ha ja nao mais muito muita bem so tambem quando como onde quem qual seu sua seus suas dele dela ao aos ate ainda "
          "depois antes entao ai la aqui ali eu voce a gente nos ia vai vao estava estavam".split(),
    "en": "a an the of to in on at by for with without and or but that this these those it its he she they them his her "
          "their was were is are be been had has have not no more very so just also when how where who which as from into "
          "out up then there here still after before you we".split(),
}
NUMEROS = {
    "pt": set("dois duas tres quatro cinco seis sete oito nove dez onze doze treze catorze quatorze quinze dezesseis "
              "dezessete dezoito dezenove vinte trinta quarenta cinquenta sessenta setenta oitenta noventa cem cento "
              "duzentos duzentas trezentos trezentas quatrocentos quinhentos seiscentos setecentos oitocentos novecentos "
              "mil milhao milhoes bilhao bilhoes duzia".split()),
    "en": set("two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
              "eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion "
              "dozen".split()),
}
TONS_ROTEIRO = {"narra", "tenso", "impacto", "leve"}
PAUSA_FRASE = 0.55                 # pausa entre frases no ritmo natural (a do dono, medida na gravação: ~0,5 a 0,7 s)


def _sem_acento(txt):
    t = unicodedata.normalize("NFD", txt.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tokens(txt):
    return re.findall(r"[a-z0-9]+", _sem_acento(txt))


def frases_de(txt):
    return [x for x in re.split(r"(?<=[.?!…])\s+", txt.strip()) if x.strip()]


def contar_numeros(txt, idioma):
    """Números e datas falados (uma data inteira, "10 de agosto de 1628", conta como um)."""
    t = re.sub(r"\b\d{1,2} de \w+ de \d{3,4}\b", " 0 ", txt)
    t = re.sub(r"\b[A-Z][a-z]+ \d{1,2}, \d{3,4}\b", " 0 ", t)
    n = len(re.findall(r"\d[\d.,]*", t))
    seguidos = False
    for w in tokens(re.sub(r"\d[\d.,]*", " ", t)):
        if w in NUMEROS[idioma]:
            n += 0 if seguidos else 1
            seguidos = True
        elif w not in ("e", "and"):
            seguidos = False
    return n


def nomes_de(txt):
    """Nomes próprios (palavras com maiúscula fora do começo da frase; seguidas contam como um nome)."""
    out = []
    for f in re.split(r"(?<=[.?!…:])\s+", txt.strip()):
        atual = []
        for k, w in enumerate(f.split()):
            w2 = w.strip(",;:()\"'“”‘’.?!…")
            if k > 0 and w2[:1].isupper() and not w2.isupper():
                atual.append(w2)
                if re.search(r"[,;:.?!…]$", w):
                    out.append(" ".join(atual))
                    atual = []
            elif atual:
                out.append(" ".join(atual))
                atual = []
        if atual:
            out.append(" ".join(atual))
    return [x for x in out if x not in ("Sua Majestade", "Majestade", "Deus")]


def estimar_duracao(r, idioma):
    """Segundos de vídeo: fala (letras por segundo da voz) + pausas entre as frases (ritmo natural) + respiros."""
    import voz as V
    natural = (r.get("voz") or {}).get("ritmo") == "natural"
    padrao = 0.5 if natural else 0.12
    total = float(r.get("cauda", 0.5))
    for b in r.get("batidas") or []:
        fala = L(b.get("fala") or {}, idioma) or ""
        total += len(V.por_extenso(fala, idioma)) / LETRAS_POR_S[idioma] + float(b.get("respiro", padrao))
        if natural and idioma == "pt":
            total += PAUSA_FRASE * max(0, len(frases_de(fala)) - 1)
    return total


def conferir_estilo(r):
    B = [b for b in r.get("batidas") or [] if isinstance(b.get("fala"), dict)]
    if not B:
        return
    voz = r.get("voz") or {}
    if voz.get("ritmo") != "natural":
        aviso('voz: use "ritmo": "natural" (frases com pausas e tom por batida; desde 10/11/2026)')
    tons = [b.get("tom", "narra") for b in B]
    for i, t in enumerate(tons):
        if t not in TONS_ROTEIRO:
            erro(f"batida {i}: tom {t!r} (use {', '.join(sorted(TONS_ROTEIRO))})")
    if len(B) >= 30 and sum(t != "narra" for t in tons) < 0.1 * len(B):
        aviso(f"só {sum(t != 'narra' for t in tons)} batidas com tom diferente de narra: marque tenso, impacto ou leve onde a história pede (1 de cada 4 ou 5)")
    for idioma in ("pt", "en"):
        falas = [L(b["fala"], idioma) or "" for b in B]
        for i, f in enumerate(falas):
            for rx in FORMULAS[idioma]:
                m = re.search(rx, f, re.I)
                if m:
                    erro(f"batida {i} ({idioma}): fórmula de texto de IA: {m.group(0)!r}")
            for rx in GASTAS[idioma]:
                m = re.search(rx, f, re.I)
                if m:
                    aviso(f"batida {i} ({idioma}): palavra de redação {m.group(0)!r} (fale como gente)")
        tudo = " ".join(falas)
        for rx, nome in TIQUES[idioma]:
            n = len(re.findall(rx, tudo, re.I))
            if n > 1:
                aviso(f"{idioma}: a construção {nome!r} aparece {n} vezes (no máximo 1 por vídeo)")
        # repetição: trechos de 4 palavras em batidas diferentes
        onde = defaultdict(set)
        for i, f in enumerate(falas):
            ts = tokens(f)
            for k in range(len(ts) - 3):
                g = ts[k:k + 4]
                if sum(w not in PARADAS[idioma] for w in g) >= 2:
                    onde[" ".join(g)].add(i)
        rep = sorted(((g, sorted(v)) for g, v in onde.items() if len(v) >= 2), key=lambda x: (-len(x[1]), x[1]))
        juntos = []                                       # "a b c d" e "b c d e" nas mesmas batidas = um trecho só
        for g, v in rep:
            if not any(set(v) == set(v2) and (g.split()[:3] == g2.split()[1:] or g.split()[1:] == g2.split()[:3]) for g2, v2 in juntos):
                juntos.append((g, v))
        for g, v in juntos[:8]:
            (erro if len(v) >= 3 else aviso)(f"{idioma}: repetido nas batidas {', '.join(map(str, v))}: \"{g}\"")
        if len(juntos) >= 6:
            erro(f"{idioma}: {len(juntos)} trechos repetidos: o texto está repetitivo (conte cada coisa uma vez)")
        # gancho recontado depois do título
        k_tit = next((i for i, b in enumerate(B) if b.get("cena") == "titulo"), None)
        if k_tit:
            conteudo = lambda f: {w for w in tokens(f) if w not in PARADAS[idioma] and len(w) >= 5}  # noqa: E731
            gancho = [conteudo(f) for f in falas[:k_tit]]
            for i in range(k_tit + 1, len(falas)):
                c = conteudo(falas[i])
                for j, g in enumerate(gancho):
                    comuns = c & g
                    if len(comuns) >= 3:
                        aviso(f"{idioma}: a batida {i} conta de novo a batida {j} do gancho ({', '.join(sorted(comuns))}): mostre o que o gancho não mostrou")
                        break
        # densidade: números, nomes, perguntas
        nums = [contar_numeros(f, idioma) for f in falas]
        for i, n in enumerate(nums):
            if n >= 3:
                erro(f"batida {i} ({idioma}): {n} números ou datas numa fala só (no máximo 1)")
        if sum(nums) > 35:
            erro(f"{idioma}: {sum(nums)} números e datas no vídeo (alvo: até 25; arredonde e corte os que não mudam a história)")
        elif sum(nums) > 25:
            aviso(f"{idioma}: {sum(nums)} números e datas no vídeo (alvo: até 25)")
        if idioma == "pt":
            por_batida = [set(nomes_de(f)) for f in falas]
            for i, ns in enumerate(por_batida):
                if len(ns) >= 3:
                    aviso(f"batida {i}: {len(ns)} nomes próprios numa fala ({', '.join(sorted(ns))})")
            todos = set().union(*por_batida)
            if len(todos) > 18:
                erro(f"{len(todos)} nomes próprios diferentes no vídeo (alvo: até 12; chame as pessoas pelo papel)")
            elif len(todos) > 12:
                aviso(f"{len(todos)} nomes próprios diferentes no vídeo (alvo: até 12): {', '.join(sorted(todos))}")
            perguntas = tudo.count("?")
            if perguntas > 5:
                aviso(f"{perguntas} perguntas no texto (até 4 ou 5: a do gancho, uma ou duas no meio e a do fim)")
            # ritmo: tamanho das frases
            frases = [len(fr.split()) for f in falas for fr in frases_de(f)]
            if len(frases) >= 20:
                media = sum(frases) / len(frases)
                dp = (sum((x - media) ** 2 for x in frases) / len(frases)) ** 0.5
                curtas = sum(x <= 4 for x in frases) / len(frases)
                duas = sum(len(frases_de(f)) == 2 for f in falas) / len(falas)
                if dp / media < 0.45:
                    aviso(f"frases todas do mesmo tamanho (variação {dp / media:.2f}; alvo acima de 0,45): misture frase bem curta com frase longa")
                if curtas < 0.08:
                    aviso(f"só {curtas:.0%} de frases curtas (até 4 palavras); elas dão o respiro e o impacto")
                if duas > 0.6:
                    aviso(f"{duas:.0%} das falas têm exatamente duas frases: o ritmo fica de fórmula")
            # gancho cabe no Short
            if k_tit:
                pal = sum(len(f.split()) for f in falas[:k_tit])
                if pal > 170:
                    aviso(f"gancho com {pal} palavras até o título: passa de 75 s e o Short sai cortado (alvo: até 160)")
            dur = estimar_duracao(r, "pt")
            ppm = sum(len(f.split()) for f in falas) / max(1e-6, dur / 60)
            print(f"ritmo: ~{ppm:.0f} palavras por minuto em português (alvo: 130 a 155; o dono lê a ~146)")
            if ppm > 165:
                erro(f"texto denso demais: ~{ppm:.0f} palavras por minuto (alvo: 130 a 155): corte informação ou ponha pausas")
            elif ppm > 155:
                aviso(f"texto um pouco denso: ~{ppm:.0f} palavras por minuto (alvo: 130 a 155)")
            elif ppm < 115:
                aviso(f"ritmo lento demais: ~{ppm:.0f} palavras por minuto")
    # cenas: variedade
    if len(B) >= 30:
        uso = Counter(b.get("cena") for b in B if b.get("cena") not in ("titulo", "capitulo"))
        for cena, n in uso.most_common():
            if n > 0.25 * len(B):
                erro(f"a cena {cena} está em {n} de {len(B)} batidas: o vídeo fica repetitivo (no máximo 1 de cada 5)")
            elif n > 0.2 * len(B):
                aviso(f"a cena {cena} está em {n} de {len(B)} batidas (no máximo 1 de cada 5)")
    def quadro(b):                         # o que muda o desenho (câmera e etiquetas não contam)
        return json.dumps({k: v for k, v in (b.get("params") or {}).items() if k not in ("etiquetas", "zoom", "pan")}, sort_keys=True)
    seguidas = 1
    for i in range(1, len(B) + 1):
        if i < len(B) and B[i].get("cena") == B[i - 1].get("cena"):
            seguidas += 1
            continue
        if seguidas >= 3:
            trecho = B[i - seguidas:i]
            iguais = any(quadro(trecho[k]) == quadro(trecho[k + 1]) == quadro(trecho[k + 2]) for k in range(len(trecho) - 2))
            if seguidas >= 5 or iguais:
                aviso(f"batidas {i - seguidas} a {i - 1}: a mesma cena ({trecho[0].get('cena')}) {seguidas} vezes seguidas"
                      + (" com o mesmo desenho" if iguais else ""))
        seguidas = 1


def linha_do_tempo(r, idioma):
    """Tempos estimados de cada batida e de cada palavra (pela velocidade da voz clonada), sem narrar."""
    import voz as V
    tl, pals, t = [], [], 0.0
    for b in r["batidas"]:
        fala = V.por_extenso(b["fala"][idioma], idioma)
        d = len(fala) / LETRAS_POR_S[idioma]
        ws = palavras(b["fala"][idioma])
        pals.append([{"w": x, "t": d * k / max(1, len(ws)), "d": d / max(1, len(ws))} for k, x in enumerate(ws)])
        fim = t + d + float(b.get("respiro", 0.5 if (r.get("voz") or {}).get("ritmo") == "natural" else 0.12))
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
