"""Registra em canal/dados/videos.json os documentários que a fábrica já publicou em Releases (canal-<slug>) e que
ainda não estão lá, ou estão com uma versão mais velha. Roda no GitHub (workflow "Canal registro") toda vez que o
fluxo "Canal" termina e uma vez por dia; assim o registro não depende do fim de cada vídeo dar certo.

Uso:  python canal/reconciliar.py      (precisa do gh com acesso ao repositório)
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

RAIZ = Path(__file__).parent
REPO = os.environ.get("REPO_VIDEOS", "Kimijoao77/Engfy")
ARQUIVADOS = {"piloto-roanoke"}            # testes antigos que não voltam para o app


def api(caminho, binario=False):
    cmd = ["gh", "api", caminho] if not binario else ["gh", "api", "-H", "Accept: application/octet-stream", caminho]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        return None
    return r.stdout if binario else json.loads(r.stdout)


def roteiros():
    """slug → caminho do roteiro de documentário (canal/roteiros vence canal/rascunhos)."""
    achados = {}
    for pasta in ("rascunhos", "roteiros"):
        for arq in sorted((RAIZ / pasta).glob("*.json")):
            try:
                r = json.loads(arq.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if r.get("formato") == "doc" and r.get("slug") and r["slug"] not in ARQUIVADOS:
                achados[r["slug"]] = f"canal/{pasta}/{arq.name}"
    return achados


def main():
    arq = RAIZ / "dados" / "videos.json"
    dados = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"videos": []}
    registrados = {v["slug"]: v for v in dados.get("videos", [])}
    mudou = []
    for slug, roteiro in roteiros().items():
        tag = f"canal-{slug}"
        rel = api(f"repos/{REPO}/releases/tags/{tag}")
        if not rel:
            continue
        ativos = {a["name"]: a for a in rel.get("assets", []) if a.get("state") == "uploaded"}
        metas = {n.split("-")[0]: a for n, a in ativos.items() if n.endswith("-meta.json")}
        if not metas:
            continue
        v = registrados.get(slug)
        mais_novo = max(a["updated_at"] for a in metas.values())
        if v and v.get("gerado_em", "") >= mais_novo and set(metas) <= set(v.get("idiomas", {})):
            continue
        baixado = Path(tempfile.mkdtemp(prefix=f"registro-{slug}-"))
        (RAIZ / "saida" / slug).mkdir(parents=True, exist_ok=True)
        for idioma, a in metas.items():
            (baixado / a["name"]).write_bytes(api(f"repos/{REPO}/releases/assets/{a['id']}", binario=True) or b"{}")
            mini = ativos.get(f"{idioma}-miniatura.jpg")
            if mini:
                img = api(f"repos/{REPO}/releases/assets/{mini['id']}", binario=True)
                if img and len(img) > 1000:
                    (RAIZ / "saida" / slug / f"miniatura-{idioma}.jpg").write_bytes(img)
        r = subprocess.run([sys.executable, str(RAIZ / "registrar.py"), slug, tag, str(baixado), roteiro])
        if r.returncode == 0:
            mudou.append(f"{slug} ({', '.join(sorted(metas))})")
    print("registrados:", "; ".join(mudou) if mudou else "nada novo")


if __name__ == "__main__":
    main()
