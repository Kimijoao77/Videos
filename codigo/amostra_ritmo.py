"""Junta as falas narradas de um roteiro numa amostra só (mp3), com as pausas que o vídeo teria, e mede o ritmo:
palavras por minuto, quanto do tempo é silêncio e o quanto a voz sobe e desce (tom, em semitons). Serve para
comparar o antes e o depois do ritmo natural (10/11/2026). O relatório só tem números (o registro é público).

Uso: python canal/amostra_ritmo.py ROTEIRO IDIOMA SAIDA NOME [--falas N] [--realce ALVO]
     lê SAIDA/<slug>/<idioma>/_tmp/bNN.wav (narrar_clone.py) e grava SAIDA/NOME.mp3 e SAIDA/NOME.json;
     --realce: estica o tom de cada fala até ALVO semitons (narrar_clone.realcar_tom) numa cópia, antes de juntar
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ouvido as O  # noqa: E402


def respiro_padrao(r):
    return 0.5 if (r.get("voz") or {}).get("ritmo") == "natural" else 0.12


def ler(arq):
    import soundfile as sf
    a, sr = sf.read(str(arq), dtype="float32")
    return (a.mean(axis=1) if a.ndim > 1 else a), sr


def silencio(a, sr):
    passo = int(sr * 0.02)
    n = len(a) // passo
    env = np.sqrt((a[:n * passo].reshape(n, passo) ** 2).mean(axis=1) + 1e-12)
    return float((env < 0.05 * np.percentile(env, 95)).mean())


def main():
    roteiro, idioma, saida, nome = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    r = json.loads(roteiro.read_text(encoding="utf-8"))
    falas = int(sys.argv[sys.argv.index("--falas") + 1]) if "--falas" in sys.argv else len(r["batidas"])
    B = r["batidas"][:falas]
    tmp = saida / r["slug"] / idioma / "_tmp"
    realce = float(sys.argv[sys.argv.index("--realce") + 1]) if "--realce" in sys.argv else 0.0
    pedacos, tons, sr0 = [], [], None
    for i, b in enumerate(B):
        arq = tmp / f"b{i:02d}.wav"
        if realce:
            import shutil
            import narrar_clone as N
            copia = saida / f"_realce-{i:02d}.wav"
            shutil.copy(arq, copia)
            N.realcar_arquivo(copia, realce, b.get("tom") or "narra")
            arq = copia
        a, sr = ler(arq)
        if realce:
            arq.unlink()
        sr0 = sr0 or sr
        tons.append(O.tom(a, sr)["dp"])
        pedacos += [a, np.zeros(int(sr * float(b.get("respiro", respiro_padrao(r)))), np.float32)]
    tudo = np.concatenate(pedacos)
    import soundfile as sf
    wav = saida / f"{nome}.wav"
    sf.write(str(wav), tudo, sr0, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "44100", "-b:a", "128k",
                    str(saida / f"{nome}.mp3")], check=True)
    wav.unlink()
    dur = len(tudo) / sr0
    palavras = sum(len((b["fala"].get(idioma) or "").split()) for b in B)
    rel = {"nome": nome, "slug": r["slug"], "falas": len(B), "segundos": round(dur, 1), "palavras": palavras,
           "palavras_por_minuto": round(palavras / (dur / 60), 1), "silencio": round(silencio(tudo, sr0), 3),
           "tom_mediano_st": round(float(np.median(tons)), 2), "tom_por_fala_st": tons,
           "ritmo": (r.get("voz") or {}).get("ritmo", "antigo"), "realce": realce}
    extra = saida / r["slug"] / idioma / "voz-relatorio.json"
    if extra.exists():                                   # ritmo natural: o que o Whisper ouviu e as tentativas
        frases = [f for x in json.loads(extra.read_text(encoding="utf-8")) for f in x["frases"]]
        sems = [f["semelhanca"] for f in frases if f.get("semelhanca") is not None]
        rel.update({"frases": len(frases), "tentativas": sum(f["tentativas"] for f in frases),
                    "semelhanca_min": min(sems) if sems else None, "semelhanca_media": round(float(np.mean(sems)), 3) if sems else None,
                    "frases_com_problema": sum(bool(f["problemas"]) for f in frases),
                    "tom_frases_st": [f["dp"] for f in frases], "pausas_s": [f["pausa"] for f in frases if f["pausa"]]})
    (saida / f"{nome}.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rel.items() if not isinstance(v, list)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
