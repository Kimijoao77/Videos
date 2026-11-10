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
    def __init__(self, dono=None, falhar_envio=False, falhar_capa=None, falhar_short=False):
        self.enviados, self.capas, self.visib, self.n, self.metas = [], [], [], 0, []
        self.falhar_short = falhar_short
        self.dono = dono or {"tok-pt": {"id": "UC_PT", "nome": "Aqui Há Dragões"}, "tok-en": {"id": "UC_EN", "nome": "Here Be Dragons"}}
        self.falhar_envio, self.falhar_capa = falhar_envio, falhar_capa

    def instalar(self, pasta: Path):
        R.acesso = lambda refresh: {"refresh-pt": "tok-pt", "refresh-en": "tok-en"}[refresh]
        R.canal_da_chave = lambda tok: self.dono[tok]
        def baixar(slug, idioma, _p, quais=("video", "capa", "meta")):
            d = pasta / "assets" / slug / idioma; d.mkdir(parents=True, exist_ok=True)
            (d / "v.mp4").write_bytes(b"video"); (d / "c.jpg").write_bytes(b"capa"); (d / "s.mp4").write_bytes(b"short")
            (d / "m.json").write_text(json.dumps({"titulo": f"Título {idioma}", "descricao": "Desc\n\nFontes", "tags": ["a", "b"],
                                                   "short": {"titulo": f"Título {idioma} #shorts", "descricao": "Desc"}}))
            todos = {"video": d / "v.mp4", "capa": d / "c.jpg", "meta": d / "m.json", "short": d / "s.mp4"}
            return {k: todos[k] for k in quais}
        R.baixar_assets = baixar
        def enviar(tok, arq, meta, idioma, cfg, publicar_em):
            short = arq.name == "s.mp4"
            falha = self.falhar_short if short else self.falhar_envio
            if falha == "cota":
                raise R.ErroHTTP(403, '{"error":{"errors":[{"reason":"quotaExceeded"}],"message":"q"}}')
            if falha:
                raise R.ErroHTTP(503, '{"error":{"errors":[{"reason":"backendError"}],"message":"x"}}')
            self.n += 1; self.metas.append((meta, cfg.get("avisar_inscritos", True)))
            if short:
                self.shorts = getattr(self, "shorts", []) + [(idioma, publicar_em)]; return f"SHORT{self.n}"
            self.enviados.append((tok, idioma, publicar_em)); return f"VID{self.n}"
        R.enviar_video = enviar
        R.enviar_capa = lambda tok, vid, capa: (self.capas.append(vid), self.falhar_capa)[1]
        R.mudar_visibilidade = lambda tok, vid, priv, cfg: self.visib.append((vid, priv))
        R.agora = lambda: T0


def preparar(aprov, postagens=None, videos=None):
    pasta = Path(tempfile.mkdtemp())
    for nome, obj in (("aprovacoes.json", aprov), ("postagens.json", postagens or {}), ("videos.json", videos or {"videos": [{"slug": "roanoke"}]}),
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
# 12. com Short registrado: o documentário sobe e o Short vai logo atrás, na mesma hora, sem avisar os inscritos
COM_SHORT = {"videos": [{"slug": "roanoke", "idiomas": {"pt": {"arquivos": {"video": "pt-video.mp4", "short": "pt-short.mp4"}},
                                                         "en": {"arquivos": {"video": "en-video.mp4", "short": "en-short.mp4"}}}}]}
pasta = preparar(PEDIDO, videos=COM_SHORT); com_chaves(); F = Falso(); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]
assert [i for _, i, _ in F.enviados] == ["pt", "en"] and F.shorts == [("pt", F.enviados[0][2]), ("en", None)], (F.enviados, F.shorts)
assert P["pt"]["estado"] == "agendado" and P["pt"]["short"]["estado"] == "agendado" and P["en"]["short"]["estado"] == "no_ar", P
assert P["pt"]["short"]["url"].startswith("https://youtu.be/SHORT") and P["pt"]["short"]["publicar_em"] == P["pt"]["publicar_em"]
m_short = [m for m, _ in F.metas if m["titulo"].endswith("#shorts")]
assert len(m_short) == 2 and all(av is False for m, av in F.metas if m["titulo"].endswith("#shorts")), F.metas
assert "https://youtu.be/VID1" in m_short[0]["descricao"] and m_short[0]["descricao"].endswith("#shorts") and "Fontes" not in m_short[0]["descricao"]
R.main(); assert len(F.shorts) == 2 and len(F.enviados) == 2, "postou o Short duas vezes!"

# 13. o Short falhou: o documentário fica como está; o pedido "short" do app tenta de novo
pasta = preparar(PEDIDO, videos=COM_SHORT); F = Falso(falhar_short=True); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]
assert P["pt"]["estado"] == "agendado" and P["pt"]["short"]["estado"] == "erro" and "503" in P["pt"]["short"]["erro"], P
R.main(); assert not getattr(F, "shorts", []), "Short com erro não tenta sozinho"
F.falhar_short = False
A = ler(R.APROV); A["videos"]["roanoke"]["pedidos"] = {"pt": {"acao": "short", "em": "2026-11-09T12:40:00Z"}}; R.APROV.write_text(json.dumps(A))
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]
assert F.shorts == [("pt", dt.datetime(2026, 11, 9, 21, 0, tzinfo=dt.timezone.utc))] and P["pt"]["short"]["estado"] == "agendado", P
assert P["pt"]["pedido_feito"] == "2026-11-09T12:40:00Z" and P["en"]["short"]["estado"] == "erro"
R.main(); assert len(F.shorts) == 1, "o pedido do Short só vale uma vez"

# 14. o Short ficou pronto depois que o documentário já tinha subido: vai na próxima rodada; travado em "enviando" vira incerto
feito = {"videos": {"roanoke": {"pt": {"estado": "no_ar", "youtube_id": "ABC", "url": "https://youtu.be/ABC", "publicar_em": "2026-11-09T11:00:00Z"},
                                "en": {"estado": "no_ar", "youtube_id": "DEF", "url": "https://youtu.be/DEF", "publicar_em": "2026-11-09T11:00:00Z",
                                       "short": {"estado": "enviando", "enviado_em": "2026-11-09T10:00:00Z"}}}}}
pasta = preparar(PEDIDO, feito, COM_SHORT); F = Falso(); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]
assert F.enviados == [] and F.shorts == [("pt", None)] and P["pt"]["short"]["estado"] == "no_ar", (F.shorts, P)
assert P["en"]["short"]["estado"] == "incerto" and "Studio" in P["en"]["short"]["erro"], P
assert "https://youtu.be/ABC" in F.metas[0][0]["descricao"]
# 14b. documentário tirado do ar: o Short não vai
feito["videos"]["roanoke"]["pt"]["estado"] = "tirado"; feito["videos"]["roanoke"]["en"].pop("short")
pasta = preparar(PEDIDO, feito, COM_SHORT); F = Falso(); F.instalar(pasta)
R.main(); assert getattr(F, "shorts", []) == [("en", None)], F.__dict__.get("shorts")

# 15. título do Short sempre com #shorts e até 100 letras; sem link enquanto o documentário não subiu
m = R.meta_short({"titulo": "x" * 120, "descricao": "Um.\n\nFontes"}, "pt", None)
assert len(m["titulo"]) <= 100 and m["titulo"].endswith(" #shorts") and m["descricao"] == "Um.\n\n#shorts", m
assert "Full documentary: https://youtu.be/Q" in R.meta_short({"titulo": "T"}, "en", "Q")["descricao"]

# 16. o dia da cota vira à meia-noite do Pacífico
assert str(R.dia_cota(dt.datetime(2026, 11, 10, 7, 59, tzinfo=dt.timezone.utc))) == "2026-11-09"
assert str(R.dia_cota(dt.datetime(2026, 11, 10, 8, 0, tzinfo=dt.timezone.utc))) == "2026-11-10"

# 18. o YouTube barrou o documentário pelo limite do dia: erro com "cota"; não insiste no mesmo dia; no dia seguinte vai sozinho
pasta = preparar({"videos": {"roanoke": {"status": "aprovado", "postar": {"pt": {"quando": "agora"}}}}}); F = Falso(falhar_envio="cota"); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]["pt"]
assert P["estado"] == "erro" and P.get("cota") is True and "limite do dia" in P["erro"], P
F.falhar_envio = False
R.main(); assert F.enviados == [], "no mesmo dia não tenta de novo"
R.agora = lambda: T0 + dt.timedelta(days=1)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]["pt"]
assert [i for _, i, _ in F.enviados] == ["pt"] and P["estado"] == "no_ar" and "cota" not in P, P

# 19. o YouTube barrou o Short pelo limite: fica "espera" (sem erro) e sobe sozinho depois
pasta = preparar(PEDIDO, videos=COM_SHORT); F = Falso(falhar_short="cota"); F.instalar(pasta)
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]
assert P["pt"]["short"]["estado"] == "espera" and P["en"]["short"]["estado"] == "espera" and len(F.enviados) == 2, P
F.falhar_short = False; R.main(); assert not getattr(F, "shorts", []), "no mesmo dia da cota o Short não insiste"
R.agora = lambda: T0 + dt.timedelta(hours=21)                # 09:00 UTC do dia seguinte: a cota já virou
R.main(); P = ler(R.POSTAGENS)["videos"]["roanoke"]
assert [i for i, _ in F.shorts] == ["pt", "en"] and P["pt"]["short"]["estado"] == "no_ar" and P["en"]["short"]["estado"] == "no_ar", P

# 20. documentário agendado para daqui a 10 min: o Short vai junto (margem de 5 min); ordem: agendado mais próximo antes, depois o mais novo no ar
perto = {"videos": {"roanoke": {"pt": {"estado": "agendado", "youtube_id": "ABC", "url": "https://youtu.be/ABC", "enviado_em": "2026-11-08T12:00:00Z",
                                       "publicar_em": "2026-11-09T12:10:00Z"}}}}
pasta = preparar({"videos": {"roanoke": {"status": "aprovado", "postar": {"pt": {"quando": "2026-11-09T12:10:00Z"}}}}}, perto, COM_SHORT); F = Falso(); F.instalar(pasta)
R.main(); assert F.shorts == [("pt", dt.datetime(2026, 11, 9, 12, 10, tzinfo=dt.timezone.utc))], F.shorts
V3 = {"videos": [{"slug": s, "idiomas": {"pt": {"arquivos": {"short": "pt-short.mp4"}}}} for s in ("a", "b", "c")]}
A3 = {"videos": {s: {"status": "aprovado"} for s in ("a", "b", "c")}}
P3 = {"videos": {"a": {"pt": {"estado": "no_ar", "youtube_id": "A", "publicar_em": "2026-11-01T12:00:00Z"}},
                 "b": {"pt": {"estado": "agendado", "youtube_id": "B", "publicar_em": "2026-11-10T00:00:00Z"}},
                 "c": {"pt": {"estado": "no_ar", "youtube_id": "C", "publicar_em": "2026-11-08T12:00:00Z",
                              "short": {"estado": "espera", "em": "2026-11-08T12:00:00Z"}}}}}
assert [x[0] for x in R.pendentes_short(A3, P3, V3, T0)] == ["b", "c", "a"], R.pendentes_short(A3, P3, V3, T0)
print("postar: todos os testes passaram")
