"""Testes do robô de postagem sem rede, sem git e sem YouTube: python3 canal/teste_postar.py"""
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import postar as R  # noqa: E402

os.environ["POSTAR_SEM_GIT"] = "1"
T0 = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.timezone.utc)
CANAIS = {"pt": {"nome": "Aqui Há Dragões", "id": "UC_PT"}, "en": {"nome": "Here Be Dragons", "id": "UC_EN"}}


class Falso:
    """YouTube e Google de mentira: registra o que o robô pediu."""
    def __init__(self, dono=None, falhar_envio=False, falhar_capa=None):
        self.enviados, self.capas, self.visib, self.n = [], [], [], 0
        self.dono = dono or {"tok-pt": {"id": "UC_PT", "nome": "Aqui Há Dragões"}, "tok-en": {"id": "UC_EN", "nome": "Here Be Dragons"}}
        self.falhar_envio, self.falhar_capa = falhar_envio, falhar_capa

    def instalar(self, pasta: Path):
        R.acesso = lambda refresh: {"refresh-pt": "tok-pt", "refresh-en": "tok-en"}[refresh]
        R.canal_da_chave = lambda tok: self.dono[tok]
        def baixar(slug, idioma, _p):
            d = pasta / "assets" / slug / idioma; d.mkdir(parents=True, exist_ok=True)
            (d / "v.mp4").write_bytes(b"video"); (d / "c.jpg").write_bytes(b"capa")
            (d / "m.json").write_text(json.dumps({"titulo": f"Título {idioma}", "descricao": "Desc", "tags": ["a", "b"]}))
            return {"video": d / "v.mp4", "capa": d / "c.jpg", "meta": d / "m.json"}
        R.baixar_assets = baixar
        def enviar(tok, arq, meta, idioma, cfg, publicar_em):
            if self.falhar_envio:
                raise R.ErroHTTP(503, '{"error":{"errors":[{"reason":"backendError"}],"message":"x"}}')
            self.n += 1; self.enviados.append((tok, idioma, publicar_em)); return f"VID{self.n}"
        R.enviar_video = enviar
        R.enviar_capa = lambda tok, vid, capa: (self.capas.append(vid), self.falhar_capa)[1]
        R.mudar_visibilidade = lambda tok, vid, priv, cfg: self.visib.append((vid, priv))
        R.agora = lambda: T0


def preparar(aprov, postagens=None):
    pasta = Path(tempfile.mkdtemp())
    for nome, obj in (("aprovacoes.json", aprov), ("postagens.json", postagens or {}), ("videos.json", {"videos": [{"slug": "roanoke"}]}),
                      ("canais-youtube.json", CANAIS)):
        (pasta / nome).write_text(json.dumps(obj), encoding="utf-8")
    R.APROV, R.POSTAGENS, R.VIDEOS, R.CANAIS, R.CONFIG = (pasta / "aprovacoes.json", pasta / "postagens.json", pasta / "videos.json",
                                                         pasta / "canais-youtube.json", pasta / "postagem.json")
    return pasta


def com_chaves(sim=True):
    for k, v in {"YT_CLIENT_ID": "cid", "YT_CLIENT_SECRET": "sec", "YT_TOKEN_PT": "refresh-pt", "YT_TOKEN_EN": "refresh-en"}.items():
        if sim:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


def ler(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


PEDIDO = {"videos": {"roanoke": {"status": "aprovado", "postar": {"pt": {"quando": "2026-11-09T21:00:00Z"}, "en": {"quando": "agora"}}}}}

# 1. aprovação antiga (sem pedido de postar) não posta nada
pasta = preparar({"videos": {"roanoke": {"status": "aprovado", "quando": "x"}}}); com_chaves(); F = Falso(); F.instalar(pasta)
assert R.main() == 0 and F.enviados == [] and not ler(R.POSTAGENS).get("videos"), "aprovação sem pedido não pode postar"
assert {i: c["ok"] for i, c in ler(R.POSTAGENS)["conexao"].items()} == {"pt": True, "en": True}, "sem nada para postar, ainda confere a conexão"

# 1b. só a chave do português: ele aparece conectado e o inglês fica esperando, sem erro
pasta = preparar({"videos": {}}); com_chaves(); os.environ.pop("YT_TOKEN_EN"); F = Falso(); F.instalar(pasta)
R.main(); C = ler(R.POSTAGENS)["conexao"]
assert C["pt"] == {"ok": True, "canal": "Aqui Há Dragões", "em": C["pt"]["em"]} and C["en"]["ok"] is False and "não conectado" in C["en"]["erro"], C
com_chaves()

# 2. vetado não posta
pasta = preparar({"videos": {"roanoke": {"status": "vetado", "postar": {"pt": {"quando": "agora"}}}}}); F = Falso(); F.instalar(pasta)
assert R.main() == 0 and F.enviados == []

# 3. sem as chaves: não posta, grava que falta conectar
pasta = preparar(PEDIDO); com_chaves(False); F = Falso(); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)
assert F.enviados == [] and P["conexao"]["pt"]["ok"] is False and "passo a passo" in P["conexao"]["pt"]["erro"], P

# 4. com as chaves: PT agendado para as 18h de Brasília, EN no ar agora; capa enviada; videos.json marcado
pasta = preparar(PEDIDO); com_chaves(); F = Falso(); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS); V = ler(R.VIDEOS)
assert [(i, p is None) for _, i, p in F.enviados] == [("pt", False), ("en", True)], F.enviados
assert F.enviados[0][2] == dt.datetime(2026, 11, 9, 21, 0, tzinfo=dt.timezone.utc)
assert P["videos"]["roanoke"]["pt"]["estado"] == "agendado" and P["videos"]["roanoke"]["en"]["estado"] == "no_ar"
assert P["videos"]["roanoke"]["pt"]["url"].startswith("https://youtu.be/VID") and F.capas == ["VID1", "VID2"]
assert V["videos"][0]["postado"] is True and set(V["videos"][0]["youtube"]) == {"pt", "en"}
# 4b. rodar de novo não posta outra vez
R.main(); assert len(F.enviados) == 2, "postou duas vezes!"

# 5. chave do canal errado: não envia nada naquele idioma
pasta = preparar(PEDIDO); com_chaves(); F = Falso(dono={"tok-pt": {"id": "UC_EN", "nome": "Here Be Dragons"}, "tok-en": {"id": "UC_EN", "nome": "Here Be Dragons"}}); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)
assert [i for _, i, _ in F.enviados] == ["en"] and P["conexao"]["pt"]["ok"] is False and "canal certo" in P["conexao"]["pt"]["erro"], P

# 6. envio falhou: estado erro; não tenta sozinho; "Tentar de novo" tenta
pasta = preparar(PEDIDO); com_chaves(); F = Falso(falhar_envio=True); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)
assert P["videos"]["roanoke"]["pt"]["estado"] == "erro" and "503" in P["videos"]["roanoke"]["pt"]["erro"]
F.falhar_envio = False; R.main(); assert F.enviados == [], "não pode tentar de novo sem pedido"
A = ler(R.APROV); A["videos"]["roanoke"]["pedidos"] = {"pt": {"acao": "tentar", "em": "2026-11-09T12:30:00Z"}}; R.APROV.write_text(json.dumps(A))
R.main(); P = ler(R.POSTAGENS)
assert [i for _, i, _ in F.enviados] == ["pt"] and P["videos"]["roanoke"]["pt"]["estado"] == "agendado", P
R.main(); assert len(F.enviados) == 1, "o pedido de tentar só vale uma vez"

# 7. "enviando" de uma rodada que caiu: vira incerto depois de 45 min (e não reenvia)
velho = {"videos": {"roanoke": {"pt": {"estado": "enviando", "enviado_em": "2026-11-09T11:00:00Z"}}}}
pasta = preparar({"videos": {"roanoke": {"status": "aprovado", "postar": {"pt": {"quando": "agora"}}}}}, velho); com_chaves(); F = Falso(); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)
assert F.enviados == [] and P["videos"]["roanoke"]["pt"]["estado"] == "incerto", P
recente = {"videos": {"roanoke": {"pt": {"estado": "enviando", "enviado_em": "2026-11-09T11:50:00Z"}}}}
pasta = preparar({"videos": {"roanoke": {"status": "aprovado", "postar": {"pt": {"quando": "agora"}}}}}, recente); F = Falso(); F.instalar(pasta)
R.main(); assert F.enviados == [] and ler(R.POSTAGENS)["videos"]["roanoke"]["pt"]["estado"] == "enviando"

# 8. tirar do ar e postar agora (pedidos do app)
feito = {"videos": {"roanoke": {"pt": {"estado": "agendado", "youtube_id": "ABC", "url": "https://youtu.be/ABC", "publicar_em": "2026-11-09T21:00:00Z"}}}}
ap = {"videos": {"roanoke": {"status": "aprovado", "postar": {"pt": {"quando": "2026-11-09T21:00:00Z"}}, "pedidos": {"pt": {"acao": "agora", "em": "2026-11-09T12:00:00Z"}}}}}
pasta = preparar(ap, feito); F = Falso(); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)
assert F.visib == [("ABC", "public")] and P["videos"]["roanoke"]["pt"]["estado"] == "no_ar" and F.enviados == []
R.main(); assert F.visib == [("ABC", "public")], "pedido feito não repete"
A = ler(R.APROV); A["videos"]["roanoke"]["pedidos"]["pt"] = {"acao": "tirar", "em": "2026-11-09T13:00:00Z"}; R.APROV.write_text(json.dumps(A))
R.main(); assert F.visib[-1] == ("ABC", "private") and ler(R.POSTAGENS)["videos"]["roanoke"]["pt"]["estado"] == "tirado"

# 9. capa recusada (canal sem verificação): o vídeo fica, com aviso
pasta = preparar({"videos": {"roanoke": {"status": "aprovado", "postar": {"en": {"quando": "agora"}}}}}); F = Falso(falhar_capa="verifique o canal por telefone"); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]["en"]
assert P["estado"] == "no_ar" and "telefone" in P["aviso"], P

# 10. horário perto demais vira "agora"; descrição e tags dentro dos limites
assert R.quando_publicar({"quando": "2026-11-09T12:05:00Z"}, R.PADRAO, T0) is None
assert R.quando_publicar({"quando": "2026-11-09T13:00:00Z"}, R.PADRAO, T0) == dt.datetime(2026, 11, 9, 13, tzinfo=dt.timezone.utc)
assert len(R.limpar("x" * 6000, 4900).encode()) <= 4900 and "<" not in R.limpar("a<b>", 10)
assert sum(len(x) + 1 for x in R.tags_ok(["tag longa " * 3] * 40)) <= 500
# 10b. rodada manual de cancelar a chave: chama o Google só para o idioma pedido e marca no app
pasta = preparar(PEDIDO); com_chaves(); F = Falso(); F.instalar(pasta); cancelados = []
R.revogar = lambda r: (cancelados.append(r), "cancelada")[1]
os.environ["POSTAR_REVOGAR"] = "pt"; R.main(); del os.environ["POSTAR_REVOGAR"]
C = ler(R.POSTAGENS)["conexao"]
assert cancelados == ["refresh-pt"] and F.enviados == [] and C["pt"]["ok"] is False and "cancelada" in C["pt"]["erro"] and "en" not in C, C

# 10c. a mesma chave colada nos dois segredos: o inglês avisa e não usa
pasta = preparar({"videos": {}}); com_chaves(); os.environ["YT_TOKEN_EN"] = "refresh-pt"; F = Falso(); F.instalar(pasta)
R.main(); C = ler(R.POSTAGENS)["conexao"]
assert C["pt"]["ok"] is True and C["en"]["ok"] is False and "Aqui Há Dragões" in C["en"]["erro"] and "mesma chave" in C["en"]["erro"], C
com_chaves()

# 11. segredo colado errado: avisa qual campo copiar, sem mostrar a chave
assert "Exchange" in R.formato_refresh("4/0Axyz") and "access token" in R.formato_refresh("ya29.abc")
assert R.formato_refresh("xyz") and R.formato_refresh("1//0gabc") is None
print("postar: todos os testes passaram")
