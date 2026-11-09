"""Amostras de voz de modelos abertos que rodam no próprio GitHub (sem conta, sem pagar, uso comercial liberado):
- Kokoro (Apache 2.0): leve e rápido;
- Chatterbox Multilingual (MIT): mais expressivo; pode usar uma amostra curta como referência de timbre
  (aqui a referência é a própria saída do Kokoro, para não copiar a voz de ninguém).
E as melhores vozes grátis da Microsoft com o mesmo texto, para comparar.

Uso: python canal/vozes_abertas.py kokoro|chatterbox|edge PASTA
"""
import os
import sys
import time
from pathlib import Path

TEXTO = {
    "pt": "Imagina que, agora mesmo, a gravidade desliga. Só por cinco segundos. Parece pouco, né? "
          "Mas nesses cinco segundos, tudo que não está preso no chão começa a subir. Inclusive você.",
    "en": "Imagine that, right now, gravity just switches off. For only five seconds. Doesn't sound like much, right? "
          "But in those five seconds, everything that isn't bolted down starts to rise. Including you.",
}


def kokoro(saida):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pedidos = [("p", "pt", ["pm_alex", "pm_santa", "pf_dora"]),
               ("a", "en", ["am_michael", "am_fenrir", "am_puck", "af_heart"]),
               ("b", "en", ["bm_george", "bm_fable"])]
    for lang, idioma, vozes in pedidos:
        pipe = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
        for voz in vozes:
            t = time.time()
            partes = []
            for res in pipe(TEXTO[idioma], voice=voz, speed=1.0):
                a = res[2] if isinstance(res, tuple) else res.audio
                partes.append(a.numpy() if hasattr(a, "numpy") else np.asarray(a))
            sf.write(saida / f"{idioma}--kokoro-{voz}.wav", np.concatenate(partes), 24000)
            print(f"kokoro {voz}: {time.time() - t:.1f}s", flush=True)


def chatterbox(saida):
    import torch
    import torchaudio
    carregar = torch.load
    torch.load = lambda *a, **k: carregar(*a, **{**k, "map_location": "cpu"})
    torch.set_num_threads(os.cpu_count() or 2)
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t = time.time()
    m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    print(f"modelo carregado em {time.time() - t:.0f}s", flush=True)
    ref_pt, ref_en = saida / "pt--kokoro-pm_alex.wav", saida / "en--kokoro-am_michael.wav"
    casos = [("pt", ref_pt, 0.5, 0.5, "ref-alex"),
             ("pt", ref_pt, 0.8, 0.3, "ref-alex-animado"),
             ("en", ref_en, 0.5, 0.5, "ref-michael")]
    for idioma, ref, exag, cfg, nome in casos:
        if ref is not None and not ref.exists():
            print("sem referência", ref.name); continue
        t = time.time()
        try:
            wav = m.generate(TEXTO[idioma], language_id=idioma, audio_prompt_path=str(ref) if ref else None,
                             exaggeration=exag, cfg_weight=cfg)
            torchaudio.save(str(saida / f"{idioma}--chatterbox-{nome}.wav"), wav, m.sr)
            print(f"chatterbox {idioma} {nome}: {time.time() - t:.0f}s", flush=True)
        except Exception as e:
            print(f"chatterbox {idioma} {nome} falhou: {e!r}", flush=True)


def edge(saida):
    import asyncio
    import edge_tts

    async def tudo():
        for idioma, voz in (("pt", "pt-BR-AntonioNeural"), ("pt", "pt-BR-ThalitaMultilingualNeural"),
                            ("pt", "pt-BR-FranciscaNeural"), ("en", "en-US-AndrewMultilingualNeural"),
                            ("en", "en-US-BrianMultilingualNeural"), ("en", "en-US-ChristopherNeural")):
            for tentativa in range(3):
                try:
                    await edge_tts.Communicate(TEXTO[idioma], voz).save(str(saida / f"{idioma}--microsoft-{voz.split('-')[2]}.mp3"))
                    break
                except Exception as e:
                    print("edge falhou", voz, e)
                    await asyncio.sleep(3)
    asyncio.run(tudo())


if __name__ == "__main__":
    modo, pasta = sys.argv[1], Path(sys.argv[2] if len(sys.argv) > 2 else "amostras")
    pasta.mkdir(parents=True, exist_ok=True)
    {"kokoro": kokoro, "chatterbox": chatterbox, "edge": edge}[modo](pasta)
