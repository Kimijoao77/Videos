"""Amostras de voz para comparar (só as vozes grátis da Microsoft, via edge-tts). Saem em amostras/."""
import asyncio, os, sys
from pathlib import Path

import edge_tts

TEXTO = {
    "pt": "E se você nunca mais precisasse dormir? Nas primeiras noites, parece um superpoder. Mas no terceiro dia, "
          "o seu cérebro começa a desligar sozinho, por alguns segundos, sem você nem perceber.",
    "en": "What if you never had to sleep again? The first few nights feel like a superpower. But by day three, "
          "your brain starts shutting down on its own, for a few seconds at a time, without you even noticing.",
}
EN_ESCOLHIDAS = ["en-US-AndrewNeural", "en-US-AndrewMultilingualNeural", "en-US-BrianMultilingualNeural", "en-US-ChristopherNeural",
                 "en-US-GuyNeural", "en-US-EricNeural", "en-US-AvaMultilingualNeural", "en-US-EmmaMultilingualNeural"]


async def main(saida):
    saida.mkdir(exist_ok=True)
    vozes = await edge_tts.list_voices()
    nomes = {v["ShortName"] for v in vozes}
    pt = sorted(v["ShortName"] for v in vozes if v["Locale"] == "pt-BR")
    multi = sorted(v["ShortName"] for v in vozes if "Multilingual" in v["ShortName"] and v["Locale"].startswith(("en-US", "pt-")))
    print("pt-BR:", pt)
    print("multilíngues:", multi)
    pedidos = [("pt", v, r) for v in pt for r in ("+0%",)] + [("pt", v, "+0%") for v in multi if v.startswith("en-US") and v in ("en-US-AndrewMultilingualNeural", "en-US-BrianMultilingualNeural", "en-US-AvaMultilingualNeural")]
    pedidos += [("en", v, "+0%") for v in EN_ESCOLHIDAS if v in nomes]
    for idioma, voz, rate in pedidos:
        arq = saida / f"{idioma}--{voz}.mp3"
        try:
            await edge_tts.Communicate(TEXTO[idioma], voz, rate=rate).save(str(arq))
            print("ok", arq.name)
        except Exception as e:
            print("falhou", voz, e)


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else "amostras")))
