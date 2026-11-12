"""Pesquisa de mercado para os canais dark, pela API do YouTube (YouTube Data API v3).

Uso:
  python canal/pesquisa.py nichos   → compara ~22 nichos em português (BR) e inglês (EUA) e salva canal/dados/nichos.json
  python canal/pesquisa.py temas    → o que está em alta nos nichos escolhidos, em canal/dados/temas.json
  python canal/pesquisa.py canais   → confere se já existem canais com os nomes pensados (variável CANAIS="Nome 1;Nome 2"),
                                       em canal/dados/canais.json (cerca de 101 unidades por nome)
  python canal/pesquisa.py consultas → testa buscas avulsas (variável CONSULTAS="pt|o que aconteceria se;en|what if"),
                                       em canal/dados/consultas.json (cerca de 102 unidades por busca)

Segredo: YOUTUBE_API_KEY.
Sem nenhuma IA aqui: a recomendação e as ideias de vídeo são escritas pelo Claude, lendo estes dados.
Cota: a API dá 10.000 unidades por dia; a pesquisa de nichos gasta cerca de 4.700 e a de temas cerca de 500.
"""
import datetime as dt, json, math, os, re, statistics, sys, unicodedata
from pathlib import Path

import requests

API = "https://www.googleapis.com/youtube/v3/"
CHAVE = os.environ.get("YOUTUBE_API_KEY", "")
DADOS = Path(__file__).parent / "dados"
CONFIG = Path(__file__).parent / "config.json"

# animavel: 2 = dá para fazer 100% por código, 1 = em parte, 0 = depende de imagem real
# rpm: 1 baixo, 2 médio, 3 alto (estimativa pelo tipo de anunciante); venda: potencial de vender produtos/afiliados (0 a 2)
NICHOS = [
    {"id": "e_se", "nome": "E se…? (ciência absurda)", "animavel": 2, "rpm": 2, "venda": 1, "pt": "o que aconteceria se", "en": "what if"},
    {"id": "curiosidades", "nome": "Curiosidades e fatos", "animavel": 2, "rpm": 2, "venda": 1, "pt": "curiosidades que você não sabia", "en": "facts you didn't know"},
    {"id": "espaco", "nome": "Espaço e universo", "animavel": 2, "rpm": 2, "venda": 1, "pt": "universo explicado", "en": "space explained"},
    {"id": "corpo", "nome": "Corpo humano", "animavel": 2, "rpm": 2, "venda": 1, "pt": "corpo humano curiosidades", "en": "human body facts"},
    {"id": "escala", "nome": "Comparações de tamanho e escala", "animavel": 2, "rpm": 2, "venda": 0, "pt": "comparação de tamanho", "en": "size comparison"},
    {"id": "dinheiro", "nome": "Dinheiro e finanças pessoais", "animavel": 2, "rpm": 3, "venda": 2, "pt": "educação financeira", "en": "personal finance explained"},
    {"id": "ricos", "nome": "Bilionários e riqueza", "animavel": 2, "rpm": 3, "venda": 2, "pt": "como os bilionários ficaram ricos", "en": "how billionaires got rich"},
    {"id": "empresas", "nome": "Histórias de empresas", "animavel": 1, "rpm": 3, "venda": 1, "pt": "história da empresa", "en": "company history documentary"},
    {"id": "economia_mapas", "nome": "Países e economia em mapas", "animavel": 2, "rpm": 2, "venda": 0, "pt": "por que o país é rico", "en": "geography explained"},
    {"id": "historia", "nome": "História explicada", "animavel": 1, "rpm": 2, "venda": 1, "pt": "história explicada", "en": "history explained"},
    {"id": "misterios", "nome": "Mistérios e enigmas", "animavel": 1, "rpm": 1, "venda": 0, "pt": "mistérios não resolvidos", "en": "unsolved mysteries"},
    {"id": "tecnologia", "nome": "Tecnologia e IA explicadas", "animavel": 2, "rpm": 3, "venda": 2, "pt": "inteligência artificial explicada", "en": "AI explained"},
    {"id": "psicologia", "nome": "Psicologia e comportamento", "animavel": 2, "rpm": 2, "venda": 2, "pt": "psicologia curiosidades", "en": "psychology facts"},
    {"id": "estoicismo", "nome": "Estoicismo e motivação", "animavel": 1, "rpm": 2, "venda": 2, "pt": "estoicismo", "en": "stoicism"},
    {"id": "produtividade", "nome": "Produtividade e estudos", "animavel": 2, "rpm": 3, "venda": 2, "pt": "como estudar melhor", "en": "productivity tips"},
    {"id": "animais", "nome": "Animais", "animavel": 1, "rpm": 1, "venda": 1, "pt": "animais curiosidades", "en": "animal facts"},
    {"id": "quiz", "nome": "Quiz e desafios", "animavel": 2, "rpm": 1, "venda": 0, "pt": "quiz conhecimentos gerais", "en": "general knowledge quiz"},
    {"id": "como_funciona", "nome": "Como funciona (engenharia)", "animavel": 2, "rpm": 2, "venda": 1, "pt": "como funciona", "en": "how it works"},
    {"id": "biblia", "nome": "Histórias bíblicas", "animavel": 1, "rpm": 2, "venda": 1, "pt": "histórias bíblicas", "en": "bible stories"},
    {"id": "saude", "nome": "Hábitos e saúde (sem promessas)", "animavel": 2, "rpm": 3, "venda": 2, "pt": "hábitos saudáveis", "en": "healthy habits explained"},
    {"id": "top10", "nome": "Rankings e top 10", "animavel": 1, "rpm": 1, "venda": 1, "pt": "top 10", "en": "top 10"},
    {"id": "reddit", "nome": "Histórias narradas (estilo Reddit)", "animavel": 1, "rpm": 1, "venda": 0, "pt": "histórias do reddit", "en": "reddit stories"},
    # canais de histórias (pedido em 08/11): terror, suspense, fantasia e stickman
    {"id": "terror", "nome": "Histórias de terror", "animavel": 1, "rpm": 1, "venda": 0, "pt": "história de terror", "en": "scary stories"},
    {"id": "terror_animado", "nome": "Terror animado", "animavel": 1, "rpm": 1, "venda": 0, "pt": "história de terror animada", "en": "horror story animation"},
    {"id": "creepypasta", "nome": "Creepypasta", "animavel": 1, "rpm": 1, "venda": 0, "pt": "creepypasta", "en": "creepypasta"},
    {"id": "lendas", "nome": "Lendas urbanas e folclore", "animavel": 1, "rpm": 1, "venda": 0, "pt": "lendas urbanas", "en": "urban legends"},
    {"id": "suspense", "nome": "Contos de suspense", "animavel": 1, "rpm": 1, "venda": 0, "pt": "conto de suspense", "en": "suspense short story"},
    {"id": "fantasia", "nome": "Contos de fantasia", "animavel": 1, "rpm": 1, "venda": 0, "pt": "conto de fantasia", "en": "fantasy story"},
    {"id": "stickman", "nome": "Animação stickman", "animavel": 2, "rpm": 1, "venda": 0, "pt": "animação stickman", "en": "stickman animation"},
    {"id": "stickman_historia", "nome": "Histórias com stickman", "animavel": 2, "rpm": 1, "venda": 0, "pt": "história stickman", "en": "stickman story"},
    # documentários longos no estilo "Por que…" (referência: Oceanverse, 08/11)
    {"id": "doc_historia", "nome": "Documentário de história", "animavel": 1, "rpm": 2, "venda": 1, "pt": "documentário história", "en": "history documentary"},
    {"id": "doc_misterios", "nome": "Mistérios da história", "animavel": 1, "rpm": 2, "venda": 0, "pt": "mistérios da história", "en": "history mysteries"},
    {"id": "doc_animais", "nome": "Documentário de animais", "animavel": 1, "rpm": 2, "venda": 1, "pt": "documentário animais", "en": "animal documentary"},
    {"id": "doc_corpo", "nome": "Documentário do corpo humano", "animavel": 1, "rpm": 2, "venda": 1, "pt": "documentário corpo humano", "en": "human body documentary"},
]
IDIOMAS = {"pt": {"regiao": "BR", "lang": "pt"}, "en": {"regiao": "US", "lang": "en"}}


class SemCota(Exception):
    pass


def get(recurso, **p):
    p["key"] = CHAVE
    r = requests.get(API + recurso, params=p, timeout=40)
    if r.status_code == 403 and "quota" in r.text.lower():
        raise SemCota("a cota diária da API do YouTube acabou")
    if r.status_code != 200:
        raise RuntimeError(f"YouTube API {recurso} {r.status_code}: {r.text[:300]}")
    return r.json()


def segundos(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def agora():
    return dt.datetime.now(dt.timezone.utc)


def buscar(q, idioma, dias, maximo=50):
    """Vídeos mais vistos de uma busca nos últimos `dias`, com estatísticas do vídeo e do canal."""
    cfg = IDIOMAS[idioma]
    depois = (agora() - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = get("search", part="snippet", q=q, type="video", order="viewCount", publishedAfter=depois,
            relevanceLanguage=cfg["lang"], regionCode=cfg["regiao"], maxResults=maximo)
    ids = [i["id"]["videoId"] for i in s.get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:
        return []
    vids = get("videos", part="statistics,contentDetails,snippet", id=",".join(ids)).get("items", [])
    canais_ids = sorted({v["snippet"]["channelId"] for v in vids})
    canais = {}
    for i in range(0, len(canais_ids), 50):
        for c in get("channels", part="statistics,snippet", id=",".join(canais_ids[i:i + 50])).get("items", []):
            canais[c["id"]] = c
    out = []
    for v in vids:
        sn, st = v["snippet"], v.get("statistics", {})
        audio = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "").lower()
        if audio and not audio.startswith(cfg["lang"]):
            continue  # vídeo em outra língua
        c = canais.get(sn["channelId"], {})
        cst = c.get("statistics", {})
        criado = c.get("snippet", {}).get("publishedAt")
        idade = (agora() - dt.datetime.fromisoformat(criado.replace("Z", "+00:00"))).days if criado else None
        out.append({
            "id": v["id"], "titulo": sn.get("title", ""), "canal": sn.get("channelTitle", ""), "canal_id": sn["channelId"],
            "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0) or 0),
            "duracao": segundos(v.get("contentDetails", {}).get("duration")),
            "publicado": sn.get("publishedAt", "")[:10],
            "inscritos": None if cst.get("hiddenSubscriberCount") else int(cst.get("subscriberCount", 0) or 0),
            "videos_canal": int(cst.get("videoCount", 0) or 0), "idade_canal_dias": idade,
        })
    return out


def metricas(vids):
    if not vids:
        return None
    views = [v["views"] for v in vids]
    total = sum(views) or 1
    pequeno = [v for v in vids if v["inscritos"] is not None and v["inscritos"] < 100_000]
    novo = [v for v in vids if v["idade_canal_dias"] is not None and v["idade_canal_dias"] < 365]
    longos = [v for v in vids if v["duracao"] > 240]
    curtos = [v for v in vids if 0 < v["duracao"] <= 180]
    razao = [v["views"] / v["inscritos"] for v in vids if v["inscritos"]]
    return {
        "videos": len(vids), "canais": len({v["canal_id"] for v in vids}),
        "views_mediana": int(statistics.median(views)), "views_p75": int(sorted(views)[int(len(views) * 0.75) - 1]),
        "parte_views_canais_pequenos": round(sum(v["views"] for v in pequeno) / total, 3),
        "videos_de_canais_novos": round(len(novo) / len(vids), 3),
        "parte_longos": round(len(longos) / len(vids), 3),
        "views_mediana_longos": int(statistics.median([v["views"] for v in longos])) if longos else 0,
        "views_mediana_shorts": int(statistics.median([v["views"] for v in curtos])) if curtos else 0,
        "views_por_inscrito_mediana": round(statistics.median(razao), 2) if razao else None,
    }


def nota(n, m, idioma):
    """Nota de 0 a 100: alcance × chance de canal novo crescer × dinheiro × dá para fazer por código × confiança.

    Confiança: com menos de 30 vídeos achados, a busca é fraca naquele idioma e a nota cai (3 vídeos não provam nada).
    """
    if not m:
        return 0
    confianca = min(1.0, m["videos"] / 30) ** 0.5
    alcance = min(1.0, math.log10(1 + m["views_mediana"]) / 6)  # 1 milhão de views na mediana = nota cheia
    chance = min(1.0, 0.25 + 0.5 * m["parte_views_canais_pequenos"] + 0.6 * m["videos_de_canais_novos"])
    dinheiro = (0.55 + 0.15 * n["rpm"] + (0.1 * n["venda"] if idioma == "pt" else 0.04 * n["venda"]))
    codigo = {2: 1.0, 1: 0.8, 0: 0.5}[n["animavel"]]
    longos = 0.8 + 0.2 * m["parte_longos"]  # vídeo longo é onde está a receita de anúncio
    return round(100 * alcance * chance * min(1.2, dinheiro) / 1.2 * codigo * longos * confianca, 1)


def exemplos(vids, k=5):
    """Vídeos que provam a oportunidade: muitos views em canal pequeno ou novo."""
    def peso(v):
        return v["views"] / max(1000, v["inscritos"] or 10**7)
    return [{"titulo": v["titulo"], "canal": v["canal"], "views": v["views"], "inscritos": v["inscritos"],
             "idade_canal_dias": v["idade_canal_dias"], "duracao": v["duracao"], "url": f"https://youtu.be/{v['id']}"}
            for v in sorted(vids, key=peso, reverse=True)[:k]]


def nichos():
    res = {"atualizado": agora().strftime("%Y-%m-%dT%H:%M:%SZ"), "janela_dias": 30, "pt": [], "en": [], "erros": []}
    for idioma in ("pt", "en"):
        for n in NICHOS:
            print(f"[{idioma}] {n['nome']}…")
            try:
                vids = buscar(n[idioma], idioma, 30)
            except SemCota as e:
                res["erros"].append(str(e)); break
            except Exception as e:
                res["erros"].append(f"{n['id']}/{idioma}: {e}"); continue
            m = metricas(vids)
            res[idioma].append({"id": n["id"], "nome": n["nome"], "busca": n[idioma], "animavel": n["animavel"], "rpm": n["rpm"],
                                "venda": n["venda"], "nota": nota(n, m, idioma), "metricas": m, "exemplos": exemplos(vids)})
        res[idioma].sort(key=lambda x: x["nota"], reverse=True)
    resumo = {i: [{k: x[k] for k in ("id", "nome", "nota", "metricas", "animavel", "rpm", "venda")} for x in res[i][:10]] for i in ("pt", "en")}
    res["resumo_top10"] = resumo
    DADOS.mkdir(exist_ok=True)
    (DADOS / "nichos.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for i in ("pt", "en"):
        print(i, [(x["id"], x["nota"]) for x in res[i][:5]])


def temas():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    escolhidos = cfg.get("nichos") or {}
    if not escolhidos and (DADOS / "nichos.json").exists():  # sem escolha ainda: usa o 1º de cada idioma da última pesquisa
        n = json.loads((DADOS / "nichos.json").read_text(encoding="utf-8"))
        escolhidos = {i: n[i][0]["id"] for i in ("pt", "en") if n.get(i)}
    res = {"atualizado": agora().strftime("%Y-%m-%dT%H:%M:%SZ"), "idiomas": {}}
    for idioma, nid in escolhidos.items():
        n = next((x for x in NICHOS if x["id"] == nid), None)
        if not n:
            continue
        print(f"[{idioma}] em alta em {n['nome']}…")
        vids = buscar(n[idioma], idioma, 7, 25)
        top = sorted(vids, key=lambda v: v["views"], reverse=True)[:15]
        cfgi = IDIOMAS[idioma]
        pop = get("videos", part="snippet,statistics", chart="mostPopular", regionCode=cfgi["regiao"], maxResults=25).get("items", [])
        geral = [{"titulo": v["snippet"]["title"], "views": int(v["statistics"].get("viewCount", 0)), "url": f"https://youtu.be/{v['id']}"} for v in pop]
        res["idiomas"][idioma] = {"nicho": nid, "nome": n["nome"],
                                  "em_alta": [{k: v[k] for k in ("titulo", "canal", "views", "inscritos", "publicado")} | {"url": f"https://youtu.be/{v['id']}"} for v in top],
                                  "populares_pais": geral[:10]}
    DADOS.mkdir(exist_ok=True)
    (DADOS / "temas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok temas", {i: len(x["em_alta"]) for i, x in res["idiomas"].items()})
    try:
        numeros()
    except Exception as e:
        print("números dos canais falharam:", e)


def analytics(idioma):
    """Horas assistidas e inscritos ganhos/perdidos desde o começo (YouTube Analytics; os números chegam com 1 a 2 dias de atraso).
    Usa a chave do robô de postagem (segredos YT_*); sem ela ou com erro, devolve None e o app mostra o que havia."""
    refresh = os.environ.get(f"YT_TOKEN_{idioma.upper()}", "").strip()
    if not (refresh and os.environ.get("YT_CLIENT_ID") and os.environ.get("YT_CLIENT_SECRET")):
        return None
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import postar
        tok = postar.acesso(refresh)
        hoje = agora().strftime("%Y-%m-%d")
        r = requests.get("https://youtubeanalytics.googleapis.com/v2/reports", timeout=40, headers={"Authorization": f"Bearer {tok}"},
                         params={"ids": "channel==MINE", "startDate": "2026-01-01", "endDate": hoje,
                                 "metrics": "views,estimatedMinutesWatched,subscribersGained,subscribersLost"})
        if r.status_code != 200:
            print(f"analytics {idioma}: {r.status_code}")
            return None
        linha = (r.json().get("rows") or [[0, 0, 0, 0]])[0]
        return {"views": int(linha[0]), "horas": round(float(linha[1]) / 60, 1), "ganhos": int(linha[2]), "perdidos": int(linha[3]),
                "ate": hoje, "em": agora().strftime("%Y-%m-%dT%H:%M:%SZ")}
    except Exception as e:  # noqa: BLE001
        print(f"analytics {idioma} falhou: {type(e).__name__}")
        return None


def id_do_canal_robos(cfg, arq):
    """Circuit Cabin (0.95.0): o canal é criado e o 1º vídeo postado na mão; quando o app marca o vídeo como postado
    (canal/pixel/dados/postados.json), o id do canal sai do próprio vídeo e fica guardado em canais-youtube.json."""
    r = cfg.get("robos")
    if not isinstance(r, dict) or r.get("id"):
        return
    post = DADOS.parent / "pixel" / "dados" / "postados.json"
    try:
        urls = [x.get("url", "") for x in json.loads(post.read_text(encoding="utf-8")).values() if isinstance(x, dict)]
    except (OSError, ValueError):
        return
    vids = [m.group(1) for u in urls for m in [re.search(r"(?:youtu\.be/|[?&]v=|/shorts/|/live/)([\w-]{11})", u or "")] if m]
    if not vids:
        return
    it = get("videos", part="snippet", id=vids[0]).get("items", [])
    if it:
        r["id"] = it[0]["snippet"]["channelId"]
        r["link"] = f"https://www.youtube.com/channel/{r['id']}"
        arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("Circuit Cabin: canal", r["id"])


def canal_ytdlp(cid):
    """Sem chave da API (12/11/2026: o fluxo roda no repositório público Videos, que não tem a chave): os números
    públicos pela página do canal, com o yt-dlp. Os Shorts mostram as views quase na hora (a API atrasa em canal novo)."""
    import subprocess
    out = {"nome": "", "handle": "", "inscritos": None, "views": 0, "videos": 0, "por_video": {}}
    for aba in ("videos", "shorts", "streams"):
        try:
            r = subprocess.run(["yt-dlp", "--flat-playlist", "--dump-single-json", "--playlist-end", "300",
                                f"https://www.youtube.com/channel/{cid}/{aba}"], capture_output=True, text=True, timeout=240)
            j = json.loads(r.stdout or "{}") or {}
        except Exception as e:  # noqa: BLE001
            print(f"yt-dlp {cid}/{aba}: {type(e).__name__}")
            continue
        if not j:                                   # canal sem essa aba (sem Shorts, sem lives)
            continue
        out["nome"] = out["nome"] or j.get("channel") or j.get("uploader") or ""
        out["handle"] = out["handle"] or (j.get("uploader_id") or "")
        if j.get("channel_follower_count") is not None:
            out["inscritos"] = int(j["channel_follower_count"])
        for e in j.get("entries") or []:
            if e.get("id") and e["id"] not in out["por_video"]:
                out["por_video"][e["id"]] = int(e.get("view_count") or 0)
    out["videos"] = len(out["por_video"])
    out["views"] = sum(out["por_video"].values())
    return out


def numeros():
    """Inscritos, views e vídeos de cada canal (canal/dados/canais-youtube.json), 1 unidade de cota.
    pt e en são os Dragões; desde 0.95.0 também lince (Lince Lunar) e robos (Circuit Cabin).
    Sem YOUTUBE_API_KEY (desde 12/11/2026 roda no repositório público Videos), usa o yt-dlp (canal_ytdlp)."""
    arq = DADOS / "canais-youtube.json"
    if not arq.exists():
        return
    cfg = json.loads(arq.read_text(encoding="utf-8"))
    try:
        id_do_canal_robos(cfg, arq)
    except Exception as e:  # noqa: BLE001
        print("id do Circuit Cabin falhou:", type(e).__name__)
    ids = {i: cfg[i]["id"] for i in ("pt", "en", "lince", "robos") if isinstance(cfg.get(i), dict) and cfg[i].get("id")}
    if not ids:
        return
    res = {"atualizado": agora().strftime("%Y-%m-%dT%H:%M:%SZ"), "canais": {}}
    publico = {}
    if not CHAVE:
        try:
            velho = json.loads((DADOS / "canal-numeros.json").read_text(encoding="utf-8")).get("canais") or {}
        except (OSError, ValueError):
            velho = {}
        for idioma, cid in ids.items():
            publico[cid] = canal_ytdlp(cid)
            if publico[cid]["inscritos"] is None:          # a página nem sempre mostra: fica o último número conhecido
                publico[cid]["inscritos"] = (velho.get(idioma) or {}).get("inscritos")
        itens = {cid: {"snippet": {"title": p["nome"] or cfg[i].get("nome"), "customUrl": p["handle"]},
                       "statistics": {"subscriberCount": p["inscritos"] or 0, "hiddenSubscriberCount": p["inscritos"] is None,
                                      "viewCount": p["views"], "videoCount": p["videos"]}}
                 for i, cid in ids.items() for p in [publico[cid]] if p["por_video"] or p["inscritos"] is not None}
    else:
        itens = {c["id"]: c for c in get("channels", part="snippet,statistics", id=",".join(ids.values())).get("items", [])}
    for idioma, cid in ids.items():
        c = itens.get(cid)
        if not c:
            continue
        st = c.get("statistics", {})
        res["canais"][idioma] = {"nome": c["snippet"].get("title"), "handle": c["snippet"].get("customUrl") or cfg[idioma].get("handle"),
                                 "id": cid, "inscritos": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0),
                                 "views": int(st.get("viewCount", 0) or 0), "videos": int(st.get("videoCount", 0) or 0)}
    # 0.80.0: views, curtidas e comentários de cada vídeo que o robô de postagem mandou (1 unidade a cada 50 vídeos);
    # 0.92.3: e dos Shorts deles
    post = (DADOS / "postagens.json")
    vids = {y["youtube_id"] for v in (json.loads(post.read_text(encoding="utf-8")).get("videos", {}) if post.exists() else {}).values()
            for x in v.values() if isinstance(x, dict) for y in (x, x.get("short") or {}) if y.get("youtube_id")}
    # 0.95.0: e os do Lince Lunar e do Circuit Cabin (o app Canais mostra as views do último vídeo de cada canal)
    for arq_c, chave in ((DADOS.parent / "lince" / "dados" / "canal.json", "videos"),):
        try:
            vids |= {v["youtube_id"] for v in json.loads(arq_c.read_text(encoding="utf-8")).get(chave, []) if v.get("youtube_id")}
        except (OSError, ValueError):
            pass
    try:
        for x in json.loads((DADOS.parent / "pixel" / "dados" / "postados.json").read_text(encoding="utf-8")).values():
            m = re.search(r"(?:youtu\.be/|[?&]v=|/shorts/|/live/)([\w-]{11})", (x or {}).get("url", "") if isinstance(x, dict) else "")
            if m:
                vids.add(m.group(1))
    except (OSError, ValueError):
        pass
    vids = sorted(vids)
    if vids and not CHAVE:
        todos = {k: v for p in publico.values() for k, v in p["por_video"].items()}
        antigo_v = {}
        try:
            antigo_v = json.loads((DADOS / "canal-numeros.json").read_text(encoding="utf-8")).get("videos") or {}
        except (OSError, ValueError):
            pass
        res["videos"] = {v: {"views": todos[v], "curtidas": (antigo_v.get(v) or {}).get("curtidas", 0),
                             "comentarios": (antigo_v.get(v) or {}).get("comentarios", 0)} for v in vids if v in todos}
    elif vids:
        res["videos"] = {}
        for k in range(0, len(vids), 50):
            for it in get("videos", part="statistics", id=",".join(vids[k:k + 50])).get("items", []):
                st = it.get("statistics", {})
                res["videos"][it["id"]] = {"views": int(st.get("viewCount", 0) or 0), "curtidas": int(st.get("likeCount", 0) or 0),
                                           "comentarios": int(st.get("commentCount", 0) or 0)}
    # 0.85.0: histórico (para o "+N nas últimas 24 h" do app) e horas assistidas (YouTube Analytics, com a chave do robô de postagem)
    antigo = {}
    try:
        antigo = json.loads((DADOS / "canal-numeros.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    t = int(agora().timestamp())
    for idioma, c in res["canais"].items():
        h = list(((antigo.get("canais") or {}).get(idioma) or {}).get("historico") or [])
        if h and t - h[-1][0] < 30 * 60:
            h = h[:-1]
        c["historico"] = (h + [[t, c["inscritos"] or 0, c["views"]]])[-400:]
        an = analytics(idioma) if idioma in ("pt", "en") else None
        if an is None:
            an = ((antigo.get("canais") or {}).get(idioma) or {}).get("analytics")
        if an:
            c["analytics"] = an
    (DADOS / "canal-numeros.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok números", {i: (x["inscritos"], x["views"]) for i, x in res["canais"].items()}, f"{len(res.get('videos', {}))} vídeos")


def consultas():
    pedidas = [c.split("|", 1) for c in os.environ.get("CONSULTAS", "").split(";") if "|" in c]
    janela = int(os.environ.get("JANELA") or 30)
    res = {"atualizado": agora().strftime("%Y-%m-%dT%H:%M:%SZ"), "janela_dias": janela, "consultas": [], "erros": []}
    for idioma, q in pedidas:
        idioma, q = idioma.strip(), q.strip()
        if idioma not in IDIOMAS or not q:
            continue
        print(f"[{idioma}] {q}…")
        try:
            vids = buscar(q, idioma, janela)
        except Exception as e:
            res["erros"].append(f"{idioma}/{q}: {e}")
            if isinstance(e, SemCota):
                break
            continue
        mais_vistos = sorted(vids, key=lambda v: v["views"], reverse=True)[:12]
        res["consultas"].append({"idioma": idioma, "busca": q, "metricas": metricas(vids), "exemplos": exemplos(vids, 8),
                                 "mais_vistos": [{k: v[k] for k in ("titulo", "canal", "views", "inscritos", "idade_canal_dias", "duracao")}
                                                 | {"url": f"https://youtu.be/{v['id']}"} for v in mais_vistos]})
    DADOS.mkdir(exist_ok=True)
    nome = re.sub(r"[^a-z0-9_-]", "", os.environ.get("ARQUIVO") or "consultas") or "consultas"
    (DADOS / f"{nome}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok consultas", nome, len(res["consultas"]), res["erros"])


def canais():
    nomes = [n.strip() for n in os.environ.get("CANAIS", "").split(";") if n.strip()]
    res = {"atualizado": agora().strftime("%Y-%m-%dT%H:%M:%SZ"), "nomes": [], "erros": []}
    for nome in nomes:
        print(f"canal: {nome}…")
        info = []
        if re.fullmatch(r"UC[\w-]{22}", nome):            # ID de canal: nome, @ e números do canal (1 unidade de cota)
            try:
                h = get("channels", part="snippet,statistics", id=nome).get("items", [])
                sn, st = (h[0]["snippet"], h[0].get("statistics", {})) if h else ({}, {})
                res["nomes"].append({"nome": nome, "id": nome, "titulo": sn.get("title"), "handle": sn.get("customUrl"),
                                     "pais": sn.get("country"), "inscritos": st.get("subscriberCount"), "videos": st.get("videoCount"),
                                     "existe": bool(h)})
            except Exception as e:
                res["erros"].append(f"{nome}: {str(e)[:120]}")
            continue
        if not nome.startswith("@"):                      # "@Algo" confere só o @ (sem busca: a busca tem cota diária própria)
            try:
                s = get("search", part="snippet", q=nome, type="channel", maxResults=8)
                ids = [i["id"]["channelId"] for i in s.get("items", []) if i.get("id", {}).get("channelId")]
                info = get("channels", part="snippet,statistics", id=",".join(ids)).get("items", []) if ids else []
            except Exception as e:
                res["erros"].append(f"{nome}: {str(e)[:120]}")
                if isinstance(e, SemCota):
                    break
        achados = []
        for c in info:
            sn, st = c["snippet"], c.get("statistics", {})
            titulo = sn.get("title", "")
            achados.append({"titulo": titulo, "handle": sn.get("customUrl", ""),
                            "inscritos": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0),
                            "videos": int(st.get("videoCount", 0) or 0), "descricao": (sn.get("description") or "")[:140],
                            "mesmo_nome": titulo.strip().lower() == nome.lower()})
        achados.sort(key=lambda a: (not a["mesmo_nome"], -(a["inscritos"] or 0)))
        handle = nome[1:] if nome.startswith("@") else "".join(p[:1].upper() + p[1:] for p in re.sub(
            r"[^A-Za-z0-9 ]", "", unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()).split())
        dono = None
        try:                                              # o @ já tem dono? (1 unidade de cota)
            h = get("channels", part="snippet,statistics", forHandle="@" + handle).get("items", [])
            if h:
                sn, st = h[0]["snippet"], h[0].get("statistics", {})
                dono = {"titulo": sn.get("title", ""), "inscritos": None if st.get("hiddenSubscriberCount") else
                        int(st.get("subscriberCount", 0) or 0), "videos": int(st.get("videoCount", 0) or 0)}
        except Exception as e:
            res["erros"].append(f"@{handle}: {e}")
        res["nomes"].append({"nome": nome, "handle": "@" + handle, "handle_livre": dono is None, "handle_dono": dono,
                             "canais": achados})
    DADOS.mkdir(exist_ok=True)
    (DADOS / "canais.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok canais", len(res["nomes"]), res["erros"])


def referencias():
    """Estuda vídeos de referência (links ou IDs em VIDEOS, separados por ;) e os canais deles, sem usar busca
    (gasta só ~10 unidades por canal): dados do vídeo, do canal e dos até 200 últimos vídeos do canal."""
    brutos = [x.strip() for x in os.environ.get("VIDEOS", "").replace(",", ";").split(";") if x.strip()]
    ids = []
    for x in brutos:
        m = re.search(r"(?:v=|youtu\.be/|shorts/|live/)([\w-]{11})", x)
        ids.append(m.group(1) if m else x[-11:])
    res = {"atualizado": agora().strftime("%Y-%m-%dT%H:%M:%SZ"), "videos": [], "canais": [], "erros": []}
    if not ids:
        res["erros"].append("nenhum vídeo em VIDEOS")
    try:
        itens = get("videos", part="snippet,statistics,contentDetails", id=",".join(ids)).get("items", []) if ids else []
    except Exception as e:
        itens = []
        res["erros"].append(f"videos: {e}")
    canais_ids = []
    for v in itens:
        sn, st = v["snippet"], v.get("statistics", {})
        res["videos"].append({"id": v["id"], "url": f"https://youtu.be/{v['id']}", "titulo": sn.get("title", ""),
                              "canal": sn.get("channelTitle", ""), "canal_id": sn["channelId"],
                              "publicado": sn.get("publishedAt", "")[:10], "duracao": segundos(v["contentDetails"].get("duration")),
                              "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0) or 0),
                              "comentarios": int(st.get("commentCount", 0) or 0), "tags": sn.get("tags", [])[:25],
                              "idioma": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
                              "descricao": (sn.get("description") or "")[:2500]})
        if sn["channelId"] not in canais_ids:
            canais_ids.append(sn["channelId"])
    for cid in canais_ids:
        try:
            c = get("channels", part="snippet,statistics,contentDetails", id=cid)["items"][0]
            sn, st = c["snippet"], c.get("statistics", {})
            subidos = c["contentDetails"]["relatedPlaylists"]["uploads"]
            vids, token = [], None
            for _ in range(4):
                p = {"part": "contentDetails", "playlistId": subidos, "maxResults": 50}
                if token:
                    p["pageToken"] = token
                r = get("playlistItems", **p)
                lista = [i["contentDetails"]["videoId"] for i in r.get("items", [])]
                if lista:
                    for v in get("videos", part="snippet,statistics,contentDetails", id=",".join(lista)).get("items", []):
                        vids.append({"id": v["id"], "titulo": v["snippet"].get("title", ""), "publicado": v["snippet"].get("publishedAt", "")[:10],
                                     "duracao": segundos(v["contentDetails"].get("duration")), "views": int(v.get("statistics", {}).get("viewCount", 0))})
                token = r.get("nextPageToken")
                if not token:
                    break
            curtos = [v for v in vids if 0 < v["duracao"] <= 180]
            longos = [v for v in vids if v["duracao"] > 180]
            hoje = agora().date()
            ult90 = [v for v in vids if v["publicado"] and (hoje - dt.date.fromisoformat(v["publicado"])).days <= 90]
            criado = sn.get("publishedAt", "")[:10]
            res["canais"].append({
                "id": cid, "titulo": sn.get("title", ""), "handle": sn.get("customUrl", ""), "criado": criado,
                "pais": sn.get("country"), "descricao": (sn.get("description") or "")[:1200],
                "inscritos": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0),
                "views_total": int(st.get("viewCount", 0) or 0), "videos_total": int(st.get("videoCount", 0) or 0),
                "analisados": len(vids), "curtos": len(curtos), "longos": len(longos),
                "mediana_views_curtos": int(statistics.median([v["views"] for v in curtos])) if curtos else 0,
                "mediana_views_longos": int(statistics.median([v["views"] for v in longos])) if longos else 0,
                "duracao_mediana_longos_min": round(statistics.median([v["duracao"] for v in longos]) / 60, 1) if longos else 0,
                "videos_ultimos_90_dias": len(ult90),
                "mais_vistos": sorted(vids, key=lambda v: v["views"], reverse=True)[:20],
                "recentes": vids[:20],
            })
        except Exception as e:
            res["erros"].append(f"canal {cid}: {e}")
    # imagens para estudar a estética: miniaturas e os quadros de pré-visualização (storyboard) do 1º vídeo
    pasta = DADOS / "referencias"
    pasta.mkdir(parents=True, exist_ok=True)
    for v in itens:
        th = v["snippet"].get("thumbnails", {})
        url = (th.get("maxres") or th.get("high") or th.get("medium") or {}).get("url")
        if url:
            try:
                r = requests.get(url, timeout=30)
                if r.ok:
                    (pasta / f"{v['id']}-miniatura.jpg").write_bytes(r.content)
            except Exception as e:
                res["erros"].append(f"miniatura {v['id']}: {e}")
    for c in res["canais"]:
        for v in c["mais_vistos"][:6]:
            try:
                r = requests.get(f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg", timeout=30)
                if r.ok:
                    (pasta / f"{v['id']}-miniatura.jpg").write_bytes(r.content)
            except Exception:
                pass
    if ids:
        try:
            res["storyboard"] = storyboard(ids[0], pasta)
        except Exception as e:
            res["erros"].append(f"storyboard: {e}")
    DADOS.mkdir(exist_ok=True)
    (DADOS / "referencias.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok referencias", len(res["videos"]), len(res["canais"]), res["erros"])


def storyboard(vid, pasta, max_folhas=12):
    """Baixa as folhas de pré-visualização do vídeo (as miniaturas da barra de progresso), só para estudar o visual."""
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
         "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    pag = requests.get(f"https://www.youtube.com/watch?v={vid}&hl=pt", headers=h, cookies={"CONSENT": "YES+1"}, timeout=40).text
    m = re.search(r'"playerStoryboardSpecRenderer":\{"spec":"([^"]+)"', pag)
    if not m:
        return {"ok": False, "motivo": "sem storyboard na página", "tamanho_pagina": len(pag)}
    spec = m.group(1).replace("\\u0026", "&")
    partes = spec.split("|")
    base = partes[0]
    niveis = [p.split("#") for p in partes[1:]]
    L = len(niveis) - 1                                       # o nível mais detalhado
    w, hh, total, cols, linhas, intervalo, nome, sigh = niveis[L][:8]
    por_folha = int(cols) * int(linhas)
    n_folhas = (int(total) + por_folha - 1) // por_folha
    salvas = []
    passo = max(1, n_folhas // max_folhas)
    for k in range(0, n_folhas, passo):
        url = base.replace("$L", str(L)).replace("$N", nome.replace("$M", str(k))) + "&sigh=" + sigh
        r = requests.get(url, headers=h, timeout=30)
        if r.ok and r.content[:3] == b"\xff\xd8\xff":
            arq = pasta / f"{vid}-sb-{k:03d}.jpg"
            arq.write_bytes(r.content)
            salvas.append(arq.name)
    return {"ok": bool(salvas), "quadro": f"{w}x{hh}", "quadros_total": int(total), "grade": f"{cols}x{linhas}",
            "intervalo_ms": int(intervalo), "folhas": salvas}


if __name__ == "__main__":
    if not CHAVE and (sys.argv[1:2] or ["nichos"])[0] != "numeros":  # os números funcionam sem chave (yt-dlp); o resto não: avisa e sai sem erro (para o GitHub não mandar e-mail de falha todo dia)
        print("falta o segredo YOUTUBE_API_KEY no GitHub (Settings > Secrets and variables > Actions); nada pesquisado")
        sys.exit(0)
    {"nichos": nichos, "temas": temas, "consultas": consultas, "canais": canais, "referencias": referencias, "numeros": numeros}[sys.argv[1] if len(sys.argv) > 1 else "nichos"]()
