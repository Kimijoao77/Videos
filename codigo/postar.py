"""Robô de postagem: manda para o YouTube os vídeos que o João aprovou no Nexus (Máquina → Vídeos).

Quem decide é o app, em canal/dados/aprovacoes.json. Só posta o que tem pedido de postagem ("postar"), feito pelo
botão Aprovar e postar (desde 0.80.0); aprovação antiga sem pedido fica esperando o botão Postar.

    "videos": {"<slug>": {"status": "aprovado", "quando": "...",
                          "postar": {"pt": {"quando": "2026-11-09T21:00:00Z"}, "en": {"quando": "agora"}},
                          "pedidos": {"pt": {"acao": "agora" | "tirar" | "tentar", "em": "..."}}}}

O resultado vai para canal/dados/postagens.json (o app mostra) e para canal/dados/videos.json (postado e os links):

    "videos": {"<slug>": {"pt": {"estado": "enviando" | "agendado" | "no_ar" | "tirado" | "erro" | "incerto",
                                 "youtube_id": "...", "url": "https://youtu.be/...", "publicar_em": "...", ...}}}

Regras de segurança:
- nunca posta duas vezes: antes de enviar, grava "enviando" no repositório; se uma rodada cair no meio do envio, o
  estado vira "incerto" e só volta a tentar quando o João tocar em Tentar de novo (depois de olhar o YouTube Studio);
- confere que a chave de cada idioma é mesmo do canal certo (canal/dados/canais-youtube.json) antes de enviar;
- as chaves (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_TOKEN_PT, YT_TOKEN_EN) só existem nos segredos do GitHub e nunca
  aparecem no log.
Agendado = enviado como privado com hora de publicação (publishAt): quem publica na hora é o próprio YouTube.

Short (desde 10/11): todo documentário sai da fábrica também com o Short (o gancho em vertical, <idioma>-short.mp4 na
release). Ele vai como vídeo à parte, sem avisar os inscritos, com o link do documentário na descrição e na mesma hora
de publicação dele, logo depois que o documentário daquele idioma sobe (ou na rodada seguinte, se o Short ficou pronto
depois). O estado fica em "videos" → <slug> → <idioma> → "short"; uma falha no Short nunca mexe no documentário, e o
botão do app "Postar o Short" (pedido "short") tenta de novo.

Limite do dia: desde 2026 o envio de vídeo tem cota própria no Google (100 por dia por projeto), e o canal também
tem um limite diário que o YouTube não publica. Se o YouTube recusar por limite (quotaExceeded/uploadLimitExceeded),
o Short fica "espera" e o documentário fica com erro e "cota"; os dois são reenviados sozinhos a partir do dia
seguinte da cota (vira à meia-noite do Pacífico, 5h de Brasília), na rodada diária das 5h40 ou em qualquer outra.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "canal" / "dados"
APROV, POSTAGENS, VIDEOS = DADOS / "aprovacoes.json", DADOS / "postagens.json", DADOS / "videos.json"
CANAIS, CONFIG = DADOS / "canais-youtube.json", DADOS / "postagem.json"
IDIOMAS = ("pt", "en")
PADRAO = {"categoria": "27", "conteudo_sintetico": False, "avisar_inscritos": True,
          "idioma": {"pt": "pt-BR", "en": "en"}, "minimo_agendar_min": 15}
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
API = "https://www.googleapis.com/youtube/v3"
VALIDADE = None              # segundos que faltam para a última chave lida vencer (None = não vence)
INCERTO_MIN = 45             # "enviando" mais velho que isso = a rodada caiu no meio do envio


def agora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ler_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def ler(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- HTTP (só biblioteca padrão)
class ErroHTTP(Exception):
    def __init__(self, codigo: int, corpo: str):
        super().__init__(f"HTTP {codigo}: {corpo[:300]}")
        self.codigo, self.corpo = codigo, corpo


def http(metodo: str, url: str, token: str | None = None, corpo=None, tipo: str | None = None, cab: dict | None = None,
         tempo: int = 60):
    """Devolve (status, cabeçalhos, texto). Erro HTTP vira ErroHTTP (com o corpo, que traz o motivo do Google)."""
    h = dict(cab or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    dados = corpo
    if isinstance(corpo, (dict, list)):
        dados, tipo = json.dumps(corpo, ensure_ascii=False).encode("utf-8"), "application/json; charset=UTF-8"
    if tipo:
        h["Content-Type"] = tipo
    req = urllib.request.Request(url, data=dados, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        if e.code == 308:                                  # upload retomável: "continue daqui"
            return 308, dict(e.headers), texto
        raise ErroHTTP(e.code, texto) from None


def motivo(e: Exception) -> str:
    """O motivo do Google em português simples (sem nada que pareça chave)."""
    if isinstance(e, ErroHTTP):
        try:
            erro = json.loads(e.corpo).get("error", {})
            razao = ((erro.get("errors") or [{}])[0].get("reason")) or erro.get("status") or ""
            msg = erro.get("message", "") if isinstance(erro, dict) else ""
        except (ValueError, AttributeError):
            razao, msg = "", e.corpo[:120]
        if razao in ("quotaExceeded", "uploadLimitExceeded"):
            return "o YouTube não aceita mais envios hoje (limite do dia); o robô tenta de novo sozinho amanhã cedo"
        if razao == "youtubeSignupRequired":
            return "esta conta não tem canal no YouTube"
        if e.codigo == 401:
            return "a autorização do canal não vale mais: refaça o passo 3 do passo a passo"
        return f"o YouTube recusou ({e.codigo}{f', {razao}' if razao else ''}){f': {msg[:140]}' if msg else ''}"
    return str(e)[:200]


def estourou_cota(e: Exception) -> bool:
    """O YouTube recusou porque acabou o limite do dia (volta sozinho no dia seguinte)."""
    if not isinstance(e, ErroHTTP):
        return False
    try:
        erro = json.loads(e.corpo).get("error", {})
        return ((erro.get("errors") or [{}])[0].get("reason")) in ("quotaExceeded", "uploadLimitExceeded")
    except (ValueError, AttributeError, IndexError):
        return False


def dia_cota(t: dt.datetime):
    """O dia da cota do YouTube: vira à meia-noite do Pacífico (5h de Brasília; 4h no horário de verão de lá)."""
    try:
        from zoneinfo import ZoneInfo
        return t.astimezone(ZoneInfo("America/Los_Angeles")).date()
    except Exception:  # noqa: BLE001
        return (t.astimezone(dt.timezone.utc) - dt.timedelta(hours=8)).date()


# ---------------------------------------------------------------- Google: chave de acesso de cada canal
def formato_refresh(r: str) -> str | None:
    """Erro comum ao colar o segredo: vem o código de autorização ou o access token no lugar do refresh token."""
    if r.startswith("4/"):
        return ("no segredo está o código de autorização (Authorization code), não o refresh token: no Playground, toque em "
                "Exchange authorization code for tokens e copie o campo Refresh token, que começa com 1//")
    if r.startswith("ya29."):
        return "no segredo está o access token, não o refresh token: copie o campo Refresh token, que começa com 1//"
    if not r.startswith("1//"):
        return "o segredo não parece um refresh token (ele começa com 1//): copie de novo o campo Refresh token do Playground"
    return None


def acesso(refresh: str) -> str:
    refresh = refresh.strip()
    if formato_refresh(refresh):
        raise RuntimeError(formato_refresh(refresh))
    corpo = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"].strip(), "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
                                    "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
    try:
        _, _, texto = http("POST", "https://oauth2.googleapis.com/token", corpo=corpo, tipo="application/x-www-form-urlencoded")
    except ErroHTTP as e:
        if "invalid_grant" in e.corpo:
            try:
                desc = str(json.loads(e.corpo).get("error_description") or "")[:80]
            except ValueError:
                desc = ""
            if "expired" in desc.lower() or "revoked" in desc.lower():
                raise RuntimeError("a autorização deste canal venceu ou foi tirada: refaça o passo 3 do passo a passo "
                                   "(e confira se o app do Google está em produção, não em teste)") from None
            raise RuntimeError(f"o Google recusou o refresh token ({desc or 'invalid_grant'}): copie de novo o campo Refresh "
                               "token inteiro do Playground e troque o segredo") from None
        if "invalid_client" in e.corpo or "unauthorized_client" in e.corpo:
            raise RuntimeError("o Google não reconheceu o app: confira os segredos YT_CLIENT_ID e YT_CLIENT_SECRET") from None
        raise RuntimeError(f"o Google recusou a chave ({e.codigo})") from None
    dados = json.loads(texto)
    global VALIDADE
    VALIDADE = dados.get("refresh_token_expires_in")       # só vem quando a chave tem prazo (app do Google em Teste)
    return dados["access_token"]


def revogar(refresh: str) -> str:
    """Cancela no Google a autorização de um canal (chave que vazou ou que vai ser trocada). Depois disso, gere outra."""
    corpo = urllib.parse.urlencode({"token": refresh.strip()}).encode()
    try:
        http("POST", "https://oauth2.googleapis.com/revoke", corpo=corpo, tipo="application/x-www-form-urlencoded")
        return "cancelada"
    except ErroHTTP as e:
        return "já não valia" if "invalid_token" in e.corpo else f"o Google respondeu {e.codigo}"


def canal_da_chave(token: str) -> dict:
    _, _, texto = http("GET", f"{API}/channels?part=id,snippet&mine=true", token)
    itens = json.loads(texto).get("items") or []
    return {"id": itens[0]["id"], "nome": itens[0]["snippet"].get("title", "")} if itens else {}


# ---------------------------------------------------------------- arquivos do vídeo (release privada do Engfy)
def baixar_assets(slug: str, idioma: str, pasta: Path, quais=("video", "capa", "meta")) -> dict:
    """Baixa da release canal-<slug> o que for pedido: <idioma>-video.mp4, <idioma>-short.mp4, <idioma>-capa.jpg (ou
    miniatura) e <idioma>-meta.json."""
    repo = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY", "Kimijoao77/Engfy")
    rel = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/releases/tags/canal-{slug}"], check=True, capture_output=True, text=True).stdout)
    assets = {a["name"]: a["id"] for a in rel.get("assets", [])}
    pasta.mkdir(parents=True, exist_ok=True)
    saida = {}
    todos = {"video": [f"{idioma}-video.mp4"], "short": [f"{idioma}-short.mp4"],
             "capa": [f"{idioma}-capa.jpg", f"{idioma}-miniatura.jpg"], "meta": [f"{idioma}-meta.json"]}
    for chave, nomes in ((k, todos[k]) for k in quais):
        nome = next((n for n in nomes if n in assets), None)
        if not nome:
            if chave == "capa":
                continue
            raise RuntimeError(f"a release canal-{slug} não tem {nomes[0]}")
        destino = pasta / nome
        with open(destino, "wb") as f:
            subprocess.run(["gh", "api", f"repos/{repo}/releases/assets/{assets[nome]}", "-H", "Accept: application/octet-stream"], check=True, stdout=f)
        saida[chave] = destino
    return saida


# ---------------------------------------------------------------- YouTube: enviar, capa, mudar visibilidade
def limpar(texto: str, limite: int) -> str:
    texto = (texto or "").replace("<", "‹").replace(">", "›").strip()
    while len(texto.encode("utf-8")) > limite:
        texto = texto[:-1]
    return texto


def tags_ok(tags: list) -> list:
    saida, total = [], 0
    for t in tags or []:
        t = limpar(str(t), 100)
        custo = len(t) + (2 if " " in t else 0) + (1 if saida else 0)
        if not t or total + custo > 480:
            continue
        saida.append(t); total += custo
    return saida


def status_video(privacidade: str, cfg: dict, publicar_em: dt.datetime | None = None) -> dict:
    s = {"privacyStatus": privacidade, "selfDeclaredMadeForKids": False, "embeddable": True, "license": "youtube",
         "publicStatsViewable": True, "containsSyntheticMedia": bool(cfg.get("conteudo_sintetico"))}
    if publicar_em:
        s["publishAt"] = iso(publicar_em)
    return s


def enviar_video(token: str, arquivo: Path, meta: dict, idioma: str, cfg: dict, publicar_em: dt.datetime | None) -> str:
    """Upload retomável. publicar_em None = público na hora; com data = privado agendado (o YouTube publica)."""
    lang = cfg["idioma"].get(idioma, idioma)
    corpo = {"snippet": {"title": limpar(meta.get("titulo", ""), 100) or "Vídeo", "description": limpar(meta.get("descricao", ""), 4900),
                         "tags": tags_ok(meta.get("tags")), "categoryId": str(cfg.get("categoria", "27")),
                         "defaultLanguage": lang, "defaultAudioLanguage": lang},
             "status": status_video("private" if publicar_em else "public", cfg, publicar_em)}
    tam = arquivo.stat().st_size
    q = urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status", "notifySubscribers": str(bool(cfg.get("avisar_inscritos", True))).lower()})
    _, cab, _ = http("POST", f"{UPLOAD}/videos?{q}", token, corpo, cab={"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(tam)})
    local = cab.get("Location") or cab.get("location")
    if not local:
        raise RuntimeError("o YouTube não devolveu o endereço de envio")
    inicio = 0
    for tentativa in range(6):
        try:
            with open(arquivo, "rb") as f:
                f.seek(inicio)
                h = {"Content-Length": str(tam - inicio)}
                if inicio:
                    h["Content-Range"] = f"bytes {inicio}-{tam - 1}/{tam}"
                st, _, texto = http("PUT", local, token, f, tipo="video/mp4", cab=h, tempo=900)
            if st in (200, 201):
                return json.loads(texto)["id"]
        except ErroHTTP as e:
            if e.codigo not in (500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(min(60, 5 * 2 ** tentativa))
        # onde o envio parou?
        st, cab, texto = http("PUT", local, token, b"", cab={"Content-Range": f"bytes */{tam}"})
        if st in (200, 201):
            return json.loads(texto)["id"]
        faixa = cab.get("Range") or cab.get("range") or ""
        inicio = int(faixa.split("-")[-1]) + 1 if "-" in faixa else 0
    raise RuntimeError("o envio do vídeo caiu 6 vezes seguidas")


def enviar_capa(token: str, video_id: str, capa: Path) -> str | None:
    """Devolve None se deu certo, ou o motivo (o canal precisa estar verificado por telefone para aceitar capa)."""
    try:
        http("POST", f"{UPLOAD}/thumbnails/set?videoId={video_id}", token, capa.read_bytes(), tipo="image/jpeg", tempo=120)
        return None
    except ErroHTTP as e:
        if e.codigo == 403:
            return "o YouTube não aceitou a capa: verifique o canal por telefone (youtube.com/verify) e toque em Mandar a capa de novo"
        return motivo(e)


def mudar_visibilidade(token: str, video_id: str, privacidade: str, cfg: dict) -> None:
    http("PUT", f"{API}/videos?part=status", token, {"id": video_id, "status": status_video(privacidade, cfg)})


# ---------------------------------------------------------------- decisões (sem rede: dá para testar)
def quando_publicar(pedido: dict | None, cfg: dict, t: dt.datetime) -> dt.datetime | None:
    """None = publicar já; data = agendar. Pedido sem data, com data passada ou perto demais = já."""
    q = (pedido or {}).get("quando", "agora")
    d = ler_iso(q) if q != "agora" else None
    if not d or d <= t + dt.timedelta(minutes=int(cfg.get("minimo_agendar_min", 15))):
        return None
    return d


def tarefas(A: dict, P: dict, t: dt.datetime) -> list:
    """O que fazer nesta rodada: [(slug, idioma, tipo, pedido)], tipo = enviar | agora | tirar | tentar | incerto."""
    saida = []
    for slug, a in sorted((A.get("videos") or {}).items()):
        if a.get("status") != "aprovado":
            continue
        for idioma in IDIOMAS:
            ped_postar = (a.get("postar") or {}).get(idioma)
            ped_acao = (a.get("pedidos") or {}).get(idioma)
            p = ((P.get("videos") or {}).get(slug) or {}).get(idioma) or {}
            estado = p.get("estado")
            velho = estado == "enviando" and (t - (ler_iso(p.get("enviado_em")) or t)) >= dt.timedelta(minutes=INCERTO_MIN)
            if ped_acao and ped_acao.get("em") and ped_acao.get("em") != p.get("pedido_feito"):
                acao = ped_acao.get("acao")
                if acao == "tentar" and (estado in ("erro", "incerto") or velho) and not p.get("youtube_id"):
                    saida.append((slug, idioma, "enviar", ped_postar or {"quando": "agora"}))
                    continue
                if acao in ("agora", "tirar", "capa", "short") and p.get("youtube_id"):
                    saida.append((slug, idioma, acao, ped_acao))
                    continue
            if not ped_postar or p.get("youtube_id"):
                continue
            if estado == "erro" and p.get("cota") and dia_cota(ler_iso(p.get("erro_em")) or t) != dia_cota(t):
                saida.append((slug, idioma, "enviar", ped_postar))   # barrado pelo limite ontem: tenta de novo sozinho
                continue
            if estado in ("erro", "incerto"):
                continue
            if estado == "enviando":
                inicio = ler_iso(p.get("enviado_em"))
                if inicio and t - inicio < dt.timedelta(minutes=INCERTO_MIN):
                    continue
                saida.append((slug, idioma, "incerto", None))
                continue
            saida.append((slug, idioma, "enviar", ped_postar))
    return saida


def meta_short(meta: dict, idioma: str, longo: str | None) -> dict:
    """Título, descrição e tags do Short: os do meta.json ("short", feito pela fábrica) com o link do documentário."""
    sh = meta.get("short") or {}
    titulo = (sh.get("titulo") or f"{(meta.get('titulo') or '').strip()} #shorts").strip()
    if len(titulo) > 100:
        titulo = titulo.replace(" #shorts", "")[:91].rstrip(" :,-") + " #shorts"
    base = (sh.get("descricao") or (meta.get("descricao") or "").split("\n\n")[0]).replace("#shorts", "").strip()
    link = f"\n\n{'Documentário completo' if idioma == 'pt' else 'Full documentary'}: https://youtu.be/{longo}" if longo else ""
    return {"titulo": titulo, "descricao": f"{base}{link}\n\n#shorts", "tags": meta.get("tags", [])}


def com_short(V: dict) -> set:
    """(slug, idioma) que têm Short registrado em videos.json (a fábrica fez e o registro anotou o arquivo)."""
    return {(v.get("slug"), i) for v in V.get("videos", []) for i, info in (v.get("idiomas") or {}).items()
            if ((info or {}).get("arquivos") or {}).get("short")}


def pendentes_short(A: dict, P: dict, V: dict, t: dt.datetime) -> list:
    """Shorts que já podem ir: vídeo aprovado, o documentário daquele idioma no YouTube (agendado ou no ar) e o Short
    registrado, ainda não enviado ou barrado pelo limite num dia anterior da cota. Primeiro os de documentário agendado
    (o mais próximo antes), depois os já no ar (o mais novo antes). Short que travou em "enviando" vira incerto (não
    reenvia sozinho)."""
    tem, saida = com_short(V), []
    for slug, a in sorted((A.get("videos") or {}).items()):
        if a.get("status") != "aprovado":
            continue
        for idioma in IDIOMAS:
            p = ((P.get("videos") or {}).get(slug) or {}).get(idioma) or {}
            if not p.get("youtube_id") or p.get("estado") not in ("agendado", "no_ar") or (slug, idioma) not in tem:
                continue
            s = p.get("short") or {}
            q = ler_iso(p.get("publicar_em")) or t
            ordem = (0, q.timestamp()) if p.get("estado") == "agendado" and q > t else (1, -q.timestamp())
            if not s or (s.get("estado") == "espera" and dia_cota(ler_iso(s.get("em")) or t) != dia_cota(t)):
                saida.append((ordem, (slug, idioma, "short", None)))
            elif s.get("estado") == "enviando" and t - (ler_iso(s.get("enviado_em")) or t) >= dt.timedelta(minutes=INCERTO_MIN):
                saida.append(((-1, 0.0), (slug, idioma, "short_incerto", None)))
    return [x for _, x in sorted(saida, key=lambda y: y[0])]


def postar_short(P: dict, slug: str, idioma: str, tok: str, cfg: dict) -> None:
    """Envia o Short de um idioma (o documentário dele já está no YouTube). Uma falha fica só no Short."""
    reg = P["videos"][slug][idioma]
    s = reg.setdefault("short", {})
    if s.get("estado") in ("agendado", "no_ar", "enviando"):
        return
    quando = ler_iso(reg.get("publicar_em"))               # documentário agendado: o Short vai ao ar junto
    publicar_em = quando if reg.get("estado") == "agendado" and quando and quando > agora() + dt.timedelta(minutes=5) else None
    s.clear()
    s.update(estado="enviando", enviado_em=iso(agora()))
    salvar(P, f"Canal: enviando o Short de {slug} ({idioma}) para o YouTube")
    try:
        arqs = baixar_assets(slug, idioma, Path("/tmp/postar") / slug, ("short", "meta"))
        m = meta_short(ler(arqs["meta"], {}), idioma, reg.get("youtube_id"))
        vid = enviar_video(tok, arqs["short"], m, idioma, {**cfg, "avisar_inscritos": False}, publicar_em)
        s.update(estado="agendado" if publicar_em else "no_ar", youtube_id=vid, url=f"https://youtu.be/{vid}",
                 titulo=m["titulo"], publicar_em=iso(publicar_em or agora()))
        print(f"ok {slug} [{idioma}] Short: {s['estado']} {s['url']}")
    except Exception as e:  # noqa: BLE001
        if estourou_cota(e):                               # limite do dia: espera o dia seguinte, sem erro
            s.clear()
            s.update(estado="espera", em=iso(agora()))
            print(f"{slug} [{idioma}] Short: espera (o YouTube disse que acabou o limite do dia)")
        else:
            s.update(estado="erro", erro=motivo(e), erro_em=iso(agora()))
            print(f"ERRO {slug} [{idioma}] Short: {s['erro']}")
    salvar(P, f"Canal: Short de {slug} ({idioma}) {'com erro' if s['estado'] == 'erro' else s['estado'].replace('_', ' ')}")


def aplicar_videos(V: dict, P: dict) -> dict:
    """Marca em videos.json os links e o 'postado' (todos os idiomas pedidos já no YouTube)."""
    for v in V.get("videos", []):
        pv = (P.get("videos") or {}).get(v.get("slug")) or {}
        links = {i: x["url"] for i, x in pv.items() if isinstance(x, dict) and x.get("url") and x.get("estado") in ("agendado", "no_ar", "no_ar_sem_capa")}
        if not links:
            continue
        v.setdefault("youtube", {}).update(links)
        datas = [ler_iso(x.get("publicar_em")) for i, x in pv.items() if isinstance(x, dict) and i in links]
        v["no_ar_em"] = iso(min(d for d in datas if d)) if any(datas) else v.get("no_ar_em")
        v["postado"] = True
    return V


def trocar(P: dict, slug: str, idioma: str, tok: str | None, cfg: dict) -> None:
    """Troca o vídeo de um idioma pelo arquivo novo da release: o YouTube não deixa trocar o arquivo, então envia o novo
    (mesma hora de publicação, se ainda for no futuro) e deixa o antigo privado. Nada é apagado: o antigo fica no
    YouTube Studio como privado e o id dele vai para "anteriores"."""
    reg = ((P.get("videos") or {}).get(slug) or {}).get(idioma) or {}
    velho = reg.get("youtube_id")
    if not tok or not velho:
        print(f"trocar {slug} [{idioma}]: {'sem chave' if not tok else 'não há vídeo enviado'}"); return
    quando = ler_iso(reg.get("publicar_em"))
    publicar_em = quando if reg.get("estado") == "agendado" and quando and quando > agora() + dt.timedelta(minutes=15) else None
    if reg.get("estado") == "tirado":
        print(f"trocar {slug} [{idioma}]: o vídeo está tirado do ar; não troco"); return
    arqs = baixar_assets(slug, idioma, Path("/tmp/postar") / slug)
    meta = ler(arqs["meta"], {})
    novo = enviar_video(tok, arqs["video"], meta, idioma, cfg, publicar_em)
    print(f"trocar {slug} [{idioma}]: enviado https://youtu.be/{novo}")
    reg.update(youtube_id=novo, url=f"https://youtu.be/{novo}", titulo=meta.get("titulo", reg.get("titulo", "")),
               publicar_em=iso(publicar_em or agora()), estado="agendado" if publicar_em else "no_ar", trocado_em=iso(agora()))
    reg["anteriores"] = (reg.get("anteriores") or []) + [velho]
    reg.pop("aviso", None)
    if arqs.get("capa"):
        falha = enviar_capa(tok, novo, arqs["capa"])
        if falha:
            reg["aviso"] = falha
    try:
        mudar_visibilidade(tok, velho, "private", cfg)
        print(f"trocar {slug} [{idioma}]: o antigo ({velho}) ficou privado")
    except Exception as e:  # noqa: BLE001
        reg["aviso"] = f"o vídeo antigo ({velho}) não ficou privado: {motivo(e)}"
        print("ERRO", reg["aviso"])
    salvar(P, f"Canal: {slug} ({idioma}) trocado pelo vídeo novo")


# ---------------------------------------------------------------- git (repetir as mudanças sobre a main mais nova)
def git(*args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=RAIZ, check=check, capture_output=True, text=True)


def normal(P: dict) -> dict:
    """postagens.json sem as datas que mudam a cada conferência (para não fazer commit à toa)."""
    Q = json.loads(json.dumps(P))
    Q.pop("atualizado", None)
    for c in (Q.get("conexao") or {}).values():
        if isinstance(c, dict):
            c.pop("em", None)
    return Q


def atualizar_main() -> None:
    """O checkout é do commit que disparou a rodada: lê a main mais nova (outra rodada pode ter gravado depois)."""
    if not os.environ.get("POSTAR_SEM_GIT"):
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--hard", "origin/main")


def salvar(P: dict, mensagem: str) -> None:
    """Grava postagens.json e videos.json em cima da main mais nova e envia (tenta 5 vezes)."""
    if os.environ.get("POSTAR_SEM_GIT"):
        gravar(POSTAGENS, P); gravar(VIDEOS, aplicar_videos(ler(VIDEOS, {"videos": []}), P)); return
    for tentativa in range(5):
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--hard", "origin/main")
        P0 = ler(POSTAGENS, {})
        antes = json.dumps(normal(P0), sort_keys=True)
        P0.setdefault("videos", {})
        for slug, por_idioma in (P.get("videos") or {}).items():
            P0["videos"].setdefault(slug, {}).update(por_idioma)
        P0["conexao"] = P.get("conexao", P0.get("conexao", {}))
        if json.dumps(normal(P0), sort_keys=True) == antes:
            return
        P0["atualizado"] = iso(agora())
        gravar(POSTAGENS, P0)
        gravar(VIDEOS, aplicar_videos(ler(VIDEOS, {"videos": []}), P0))
        git("add", str(POSTAGENS.relative_to(RAIZ)), str(VIDEOS.relative_to(RAIZ)))
        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return
        git("-c", "user.name=Kimijoao77", "-c", "user.email=leclercjoao3@gmail.com", "commit", "-q", "-m", mensagem)
        if git("push", "-q", "origin", "HEAD:main", check=False).returncode == 0:
            return
        time.sleep(4 + 3 * tentativa)
    raise RuntimeError("não consegui gravar no repositório depois de 5 tentativas")


# ---------------------------------------------------------------- a rodada
def main() -> int:
    global VALIDADE
    atualizar_main()
    t = agora()
    cfg = {**PADRAO, **ler(CONFIG, {})}
    A, P = ler(APROV, {}), ler(POSTAGENS, {})
    P.setdefault("videos", {})
    canais = ler(CANAIS, {})
    pedido_revogar = os.environ.get("POSTAR_REVOGAR", "").strip()
    if pedido_revogar:                                     # rodada manual: só cancela as chaves pedidas
        for i in [x for x in IDIOMAS if x in pedido_revogar.split(",")]:
            refresh = os.environ.get(f"YT_TOKEN_{i.upper()}", "")
            res = revogar(refresh) if refresh.strip() else "sem chave"
            print(f"chave {i}: {res}")
            P.setdefault("conexao", {})[i] = {"ok": False, "erro": "chave cancelada: gere outra no passo 3 do passo a passo e troque o segredo",
                                             "em": iso(t)}
        salvar(P, "Canal: chave do YouTube cancelada")
        return 0
    fila = tarefas(A, P, t)
    V = ler(VIDEOS, {"videos": []})
    ja = {(s, i) for s, i, _, _ in fila}
    fila += [x for x in pendentes_short(A, P, V, t) if (x[0], x[1]) not in ja]
    # Confere as duas chaves em toda rodada, mesmo sem nada para postar: é assim que o app mostra "conectado".
    tem_chave = {i: bool(os.environ.get(f"YT_TOKEN_{i.upper()}")) for i in IDIOMAS}
    if not (os.environ.get("YT_CLIENT_ID") and os.environ.get("YT_CLIENT_SECRET")):
        tem_chave = {i: False for i in IDIOMAS}
    conexao, tokens = {}, {}
    for i in IDIOMAS:
        if not tem_chave[i]:
            conexao[i] = {"ok": False, "erro": "canal ainda não conectado: falta o passo a passo do Google (segredos do GitHub)", "em": iso(t)}
            continue
        try:
            VALIDADE = None
            tok = acesso(os.environ[f"YT_TOKEN_{i.upper()}"])
            dono = canal_da_chave(tok)
            esperado = (canais.get(i) or {}).get("id")
            if not dono:
                raise RuntimeError("a conta autorizada não tem canal no YouTube")
            if esperado and dono["id"] != esperado:
                raise RuntimeError(f"a chave do {'português' if i == 'pt' else 'inglês'} é do canal “{dono['nome']}”, não do "
                                   f"“{canais[i].get('nome', esperado)}”: refaça a autorização escolhendo o canal certo")
            tokens[i] = tok
            conexao[i] = {"ok": True, "canal": dono["nome"], "em": iso(t)}
            if VALIDADE:
                conexao[i]["vence_em"] = iso(t + dt.timedelta(seconds=int(VALIDADE)))
                print(f"conexão {i}: a chave vence em {int(VALIDADE) // 86400} dias: o app do Google ainda está em Teste")
        except Exception as e:  # noqa: BLE001
            conexao[i] = {"ok": False, "erro": motivo(e), "em": iso(t)}
    # A mesma chave nos dois segredos: a conferência do canal já mostra qual dos dois está errado; aqui só explica o porquê.
    if all(tem_chave.values()) and os.environ["YT_TOKEN_PT"].strip() == os.environ["YT_TOKEN_EN"].strip():
        for c in conexao.values():
            if not c["ok"]:
                c["erro"] += " (os segredos YT_TOKEN_PT e YT_TOKEN_EN estão com a mesma chave)"
    P["conexao"] = {**(P.get("conexao") or {}), **conexao}
    for i, c in conexao.items():
        print(f"conexão {i}: {'ok, canal ' + c['canal'] if c['ok'] else c['erro']}")
    pedido_trocar = os.environ.get("POSTAR_TROCAR", "").strip()
    if pedido_trocar:                                      # rodada manual: troca o arquivo de vídeos já enviados
        for item in [x.strip() for x in pedido_trocar.split(",") if ":" in x]:
            slug, idioma = item.split(":", 1)
            trocar(P, slug, idioma, tokens.get(idioma), cfg)
        return 0
    if not fila:
        print("nada para postar")
        salvar(P, "Canal: situação da conexão com o YouTube")
        return 0
    feitos = 0
    for slug, idioma, tipo, pedido in fila:
        reg = P["videos"].setdefault(slug, {}).setdefault(idioma, {})
        if tipo == "incerto":
            reg.update(estado="incerto", erro="a rodada anterior caiu no meio do envio: veja no YouTube Studio se o vídeo subiu. "
                       "Se não subiu, toque em Tentar de novo.")
            salvar(P, f"Canal: envio incerto ({slug}, {idioma})"); continue
        tok = tokens.get(idioma)
        if not tok:
            print(f"{slug} [{idioma}]: {conexao.get(idioma, {}).get('erro', 'sem chave')}"); continue
        try:
            if tipo == "enviar":
                publicar_em = quando_publicar(pedido, cfg, agora())
                reg.clear()
                reg.update(estado="enviando", enviado_em=iso(agora()), pedido_feito=((A["videos"][slug].get("pedidos") or {}).get(idioma) or {}).get("em"))
                salvar(P, f"Canal: enviando {slug} ({idioma}) para o YouTube")
                arqs = baixar_assets(slug, idioma, Path("/tmp/postar") / slug)
                meta = ler(arqs["meta"], {})
                vid = enviar_video(tok, arqs["video"], meta, idioma, cfg, publicar_em)
                reg.update(youtube_id=vid, url=f"https://youtu.be/{vid}", titulo=meta.get("titulo", ""), publicar_em=iso(publicar_em or agora()),
                           estado="agendado" if publicar_em else "no_ar")
                reg.pop("erro", None)
                if arqs.get("capa"):
                    falha = enviar_capa(tok, vid, arqs["capa"])
                    if falha:
                        reg.update(aviso=falha)
                salvar(P, f"Canal: {slug} ({idioma}) {'agendado' if publicar_em else 'no ar'} no YouTube")
                if (slug, idioma) in com_short(V):            # o Short vai logo atrás, com o link do documentário
                    postar_short(P, slug, idioma, tok, cfg)
            elif tipo == "short":
                postar_short(P, slug, idioma, tok, cfg)
                if pedido:
                    reg["pedido_feito"] = pedido.get("em")
                    salvar(P, f"Canal: pedido do Short de {slug} ({idioma})")
            elif tipo == "short_incerto":
                reg.setdefault("short", {}).update(estado="incerto", erro="o envio do Short caiu no meio: veja no YouTube Studio se ele "
                                                   "subiu. Se não subiu, toque em Tentar o Short de novo.")
                salvar(P, f"Canal: envio incerto do Short ({slug}, {idioma})")
            elif tipo == "capa":
                arqs = baixar_assets(slug, idioma, Path("/tmp/postar") / slug)
                falha = enviar_capa(tok, reg["youtube_id"], arqs["capa"]) if arqs.get("capa") else "sem capa na release"
                if falha:
                    reg["aviso"] = falha
                else:
                    reg.pop("aviso", None)
                reg["pedido_feito"] = pedido.get("em")
                salvar(P, f"Canal: capa de {slug} ({idioma})")
            elif tipo == "agora":
                mudar_visibilidade(tok, reg["youtube_id"], "public", cfg)
                reg.update(estado="no_ar", publicar_em=iso(agora()), pedido_feito=pedido.get("em"))
                salvar(P, f"Canal: {slug} ({idioma}) no ar agora")
            elif tipo == "tirar":
                mudar_visibilidade(tok, reg["youtube_id"], "private", cfg)
                reg.update(estado="tirado", tirado_em=iso(agora()), pedido_feito=pedido.get("em"))
                salvar(P, f"Canal: {slug} ({idioma}) tirado do ar (privado)")
            feitos += 1
            if not tipo.startswith("short"):
                print(f"ok {slug} [{idioma}] {tipo}: {reg.get('estado')} {reg.get('url', '')}")
        except Exception as e:  # noqa: BLE001
            if reg.get("youtube_id"):                       # o vídeo já está no YouTube: o estado fica, vira aviso
                reg.update(aviso=motivo(e))
                if tipo == "enviar" and reg.get("estado") == "enviando":
                    reg["estado"] = "agendado" if ler_iso(reg.get("publicar_em")) and ler_iso(reg["publicar_em"]) > agora() else "no_ar"
            else:
                reg.update(estado="erro", erro=motivo(e), erro_em=iso(agora()))
                if estourou_cota(e):                       # reenviado sozinho no dia seguinte (tarefas)
                    reg["cota"] = True
            if tipo in ("agora", "tirar", "capa") and pedido:
                reg["pedido_feito"] = pedido.get("em")
            print(f"ERRO {slug} [{idioma}] {tipo}: {reg.get('erro') or reg.get('aviso')}")
            salvar(P, f"Canal: erro ao postar {slug} ({idioma})")
    if not feitos and conexao:
        salvar(P, "Canal: situação da conexão com o YouTube")
    return 0


if __name__ == "__main__":
    sys.exit(main())
