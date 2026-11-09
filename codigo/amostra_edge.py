"""Amostra das vozes nativas grátis da Microsoft (edge-tts) com as primeiras falas de um roteiro, para comparar com a
voz clonada (09/11/2026: o dono achou que o clone soa como estrangeiro falando português).

Uso: python canal/amostra_edge.py ROTEIRO SAIDA [N_FALAS]
Sai: SAIDA/<slug>-voz-edge-<voz>.mp3 (uma por voz), com 0,7 s entre as falas.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from narrar_clone import falado_de  # noqa: E402

VOZES = {"pt": [("pt-BR-AntonioNeural", "+8%", "+2Hz"), ("pt-BR-MacerioMultilingualNeural", "+6%", "+0Hz"),
                ("pt-BR-ThalitaMultilingualNeural", "+6%", "+0Hz"), ("pt-BR-FranciscaNeural", "+8%", "+0Hz")],
         "en": [("en-US-AndrewMultilingualNeural", "+6%", "+0Hz"), ("en-US-BrianMultilingualNeural", "+6%", "+0Hz"),
                ("en-US-AvaMultilingualNeural", "+6%", "+0Hz")]}


async def falar(texto, voz, rate, pitch, mp3):
    import edge_tts
    await edge_tts.Communicate(texto, voz, rate=rate, pitch=pitch).save(str(mp3))


def main():
    r = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    saida = Path(sys.argv[2]); saida.mkdir(parents=True, exist_ok=True)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    tmp = saida / "_edge"; tmp.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.7", str(tmp / "pausa.mp3")], check=True)
    for idioma, vozes in VOZES.items():
        if not all(isinstance(b.get("fala"), dict) and b["fala"].get(idioma) for b in r["batidas"][:n]):
            continue                                   # roteiro sem esse idioma
        falas = [falado_de(r, b, idioma) for b in r["batidas"][:n]]
        for voz, rate, pitch in vozes:
            partes = []
            try:
                for i, t in enumerate(falas):
                    mp3 = tmp / f"{voz}-{i}.mp3"
                    asyncio.run(falar(t, voz, rate, pitch, mp3))
                    partes += [mp3, tmp / "pausa.mp3"]
            except Exception as ex:  # noqa: BLE001
                print("sem a voz", voz, str(ex)[:80], flush=True)
                continue
            lista = tmp / "lista.txt"
            lista.write_text("".join(f"file '{p.resolve()}'\n" for p in partes))
            nome = voz.split("-")[2].replace("Neural", "").replace("Multilingual", "").lower()
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-ar", "44100", "-ac", "1",
                            "-c:a", "libmp3lame", "-b:a", "160k", str(saida / f"{r['slug']}-voz-edge-{idioma}-{nome}.mp3")], check=True)
            print("pronta:", idioma, voz, flush=True)


if __name__ == "__main__":
    main()
