"""Escolhe o que a fábrica vai gerar e grava as saídas do passo em $GITHUB_OUTPUT.

- Rodada à mão com um roteiro: gera esse roteiro, nos idiomas pedidos.
- Rodada sozinha (horário): procura no repositório do canal os roteiros de canal/roteiros/ que mudaram nos últimos
  3 dias e ainda não têm os vídeos na Release canal-<slug>. Pega o mais antigo. Um roteiro que falhou 2 vezes
  seguidas só é gerado de novo à mão (para não ficar tentando sem parar).

Roda com o checkout do repositório do canal na pasta atual (canal/roteiros) e GH_TOKEN com acesso a ele.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

CANAL = os.environ.get("CANAL_REPO", "Kimijoao77/Engfy")
DIAS = 3
MAX_FALHAS = 2


def api(caminho):
    p = subprocess.run(["gh", "api", caminho], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout) if p.stdout.strip() else None


def ativos(slug):
    rel = api(f"repos/{CANAL}/releases/tags/canal-{slug}") or {}
    return {a["name"] for a in rel.get("assets", [])}


def falhas(slug, nomes):
    if "fabrica-falhas.json" not in nomes:
        return 0
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run(["gh", "release", "download", f"canal-{slug}", "-R", CANAL, "-p", "fabrica-falhas.json",
                            "-D", d], capture_output=True, text=True)
        try:
            return int(json.loads((Path(d) / "fabrica-falhas.json").read_text()).get("falhas", 0)) if p.returncode == 0 else 0
        except (OSError, ValueError):
            return 0


def idiomas_de(txt):
    return [x.strip() for x in (txt or "pt,en").split(",") if x.strip() in ("pt", "en")]


def recentes():
    """Roteiros de canal/roteiros/ que mudaram nos últimos dias, do mais antigo para o mais novo."""
    desde = (datetime.now(timezone.utc) - timedelta(days=DIAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    vistos = {}
    for c in api(f"repos/{CANAL}/commits?path=canal/roteiros&since={desde}&per_page=30") or []:
        info = api(f"repos/{CANAL}/commits/{c['sha']}") or {}
        quando = (info.get("commit") or {}).get("committer", {}).get("date", "")
        for f in info.get("files", []):
            nome = f.get("filename", "")
            if nome.startswith("canal/roteiros/") and nome.endswith(".json") and f.get("status") != "removed":
                vistos[nome] = min(quando, vistos.get(nome, quando))
    return [nome for nome, _ in sorted(vistos.items(), key=lambda x: x[1])]


def saida(**kv):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def main():
    pedido = os.environ.get("ROTEIRO", "").strip()
    if pedido:
        alvo, ids = Path(pedido), idiomas_de(os.environ.get("IDIOMAS"))
        if not alvo.is_file():
            sys.exit(f"roteiro não encontrado no repositório do canal: {pedido}")
    else:
        alvo, ids = None, []
        for nome in recentes():
            arq = Path(nome)
            if not arq.is_file():
                continue
            r = json.loads(arq.read_text(encoding="utf-8"))
            if r.get("formato") != "doc":
                continue
            nomes = ativos(r["slug"])
            faltam = [l for l in ("pt", "en") if f"{l}-video.mp4" not in nomes]
            if not faltam:
                continue
            n = falhas(r["slug"], nomes)
            if n >= MAX_FALHAS:
                print(f"{arq.name}: falhou {n} vezes seguidas; só gero de novo à mão")
                continue
            alvo, ids = arq, faltam
            break
        if alvo is None:
            print("nenhum roteiro novo")
            saida(fazer="false", idiomas='["pt"]')        # a matriz do próximo passo precisa de algo válido
            return
    r = json.loads(alvo.read_text(encoding="utf-8"))
    print(f"vou gerar {alvo} em {', '.join(ids)}")
    saida(fazer="true", roteiro=str(alvo), slug=r["slug"], versao=r.get("versao", 1),
          motor=(r.get("voz") or {}).get("motor", "edge"), idiomas=json.dumps(ids))


if __name__ == "__main__":
    main()
