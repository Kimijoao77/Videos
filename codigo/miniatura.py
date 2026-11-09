"""Refaz a miniatura (e a capa) de um vídeo já gerado, sem renderizar o vídeo de novo: quando o estilo da miniatura
muda ou quando a "capa" do roteiro muda. Usa os tempos estimados das falas (só mexe no instante da cena da capa).
No GitHub: Actions > Canal miniatura (sobe para a Release do vídeo e atualiza a imagem que o app mostra).

Uso:  python canal/miniatura.py <roteiro.json> [--idiomas pt,en] [--saida DIR]
      → DIR/<idioma>-miniatura.jpg e DIR/<idioma>-capa.jpg
"""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import conferir_roteiro as CR  # noqa: E402
import filme as F  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    r = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    idiomas = sys.argv[sys.argv.index("--idiomas") + 1].split(",") if "--idiomas" in sys.argv else ["pt", "en"]
    saida = Path(sys.argv[sys.argv.index("--saida") + 1]) if "--saida" in sys.argv else Path("miniaturas")
    saida.mkdir(parents=True, exist_ok=True)
    for idioma in [i.strip() for i in idiomas if i.strip()]:
        tl, pals = CR.linha_do_tempo(r, idioma)
        rb = F.resolver(r["batidas"], idioma, pals, tl)
        tmp = Path(tempfile.mkdtemp())
        F.miniatura_doc(dict(r, batidas=rb), idioma, tl, tmp)
        (tmp / "miniatura.jpg").replace(saida / f"{idioma}-miniatura.jpg")
        (tmp / "capa.jpg").replace(saida / f"{idioma}-capa.jpg")
        print(f"{idioma}: {saida / f'{idioma}-miniatura.jpg'}")


if __name__ == "__main__":
    main()
