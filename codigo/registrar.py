"""Registra um vídeo gerado em canal/dados/videos.json (o Nexus mostra na aba Vídeos da Máquina).

Uso (no GitHub, depois de gerar):  python canal/registrar.py <slug> <tag> <pasta com pt-meta.json/en-meta.json> <roteiro>
"""
import datetime as dt, json, sys
from pathlib import Path

RAIZ = Path(__file__).parent
REPO = "Kimijoao77/Engfy"


def main():
    slug, tag, pasta, roteiro = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    r = json.loads(Path(roteiro).read_text(encoding="utf-8"))
    arq = RAIZ / "dados" / "videos.json"
    dados = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"videos": []}
    item = {"slug": slug, "tema": r.get("tema", slug), "status": "gerado", "postado": False,
            "gerado_em": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "release": f"https://github.com/{REPO}/releases/tag/{tag}", "roteiro": roteiro,
            "escrito_por": r.get("escrito_por", "Claude"), "fontes": r.get("fontes", []), "checagem_fatos": r.get("checagem", []),
            "cenas_short": len(r.get("short", []) or r.get("batidas", [])), "cenas_video": len(r.get("cenas", [])), "idiomas": {}}
    for idioma in ("pt", "en"):
        m = pasta / f"{idioma}-meta.json"
        if not m.exists():
            continue
        meta = json.loads(m.read_text(encoding="utf-8"))
        item["idiomas"][idioma] = {
            "titulo": meta.get("titulo", ""), "descricao": meta.get("descricao", ""), "tags": meta.get("tags", []),
            "duracao_short_s": meta.get("duracao_short_s"), "duracao_video_s": meta.get("duracao_s") or None,
            "qualidade": meta.get("checagem", {}), "miniatura": f"canal/saida/{slug}/miniatura-{idioma}.jpg",
            "arquivos": {k: f"{idioma}-{k}.mp4" for k in ("short", "video") if meta.get("checagem", {}).get(k)}}
    antigo = next((v for v in dados["videos"] if v.get("slug") == slug), {})
    for k in ("postado", "postado_em", "youtube"):                 # o que o robô de postagem (ou você) já marcou
        if antigo.get(k):
            item[k] = antigo[k]
    if antigo.get("postado"):
        item["status"] = antigo.get("status", "postado")
    for idioma, info in (antigo.get("idiomas") or {}).items():       # idioma que ainda não saiu desta vez fica como estava
        item["idiomas"].setdefault(idioma, info)
    dados["videos"] = [v for v in dados["videos"] if v.get("slug") != slug] + [item]
    dados["videos"].sort(key=lambda v: v.get("gerado_em", ""), reverse=True)
    dados["atualizado"] = item["gerado_em"]
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print("registrado", slug, list(item["idiomas"]))


if __name__ == "__main__":
    main()
