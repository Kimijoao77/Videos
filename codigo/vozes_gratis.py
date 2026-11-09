"""Teste cego de vozes GRÁTIS: modelos abertos rodando no próprio GitHub (sem chave, sem cartão).

Candidatas:
  • Qwen3-TTS (Alibaba, jan/2026, licença Apache 2.0, fala português): o modelo "VoiceDesign" cria um narrador a
    partir de uma descrição em texto; gravamos um trecho curto dessa voz e o modelo "Base" clona ela para o texto
    todo (assim a voz fica igual em todas as cenas do vídeo, que é como a fábrica vai usar).
  • Qwen3-TTS com as vozes prontas do modelo "CustomVoice".
  • Pocket TTS (Kyutai): pequeno, mais rápido que o tempo real no processador, voz pronta em português e clone.
  • Supertonic 3 (Supertone, licença OpenRAIL-M): 31 línguas, roda em ONNX no processador.
  • Controles, para comparar às cegas: Microsoft Antonio (PT) e Andrew (EN).

Tudo sai embaralhado e numerado; o mapa número → voz fica em mapa.json (para o Claude).
Uso: python canal/vozes_gratis.py PASTA desenho|clone|prontas|pocket|supertonic|montar (cada etapa num passo, para uma falha não
derrubar as outras)
"""
import gc
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import vozes_cego as VC  # noqa: E402  (mesmo trecho e o mesmo cartão numerado)

TEXTO = VC.TEXTO
REF = {
    "pt": "Em agosto de 1590, um navio inglês chegou a uma pequena ilha na costa da América do Norte.",
    "en": "In August 1590, an English ship reached a small island off the coast of North America.",
}
LINGUA = {"pt": "Portuguese", "en": "English"}
DESENHOS = {
    "pt": [
        ("narrador-grave", "Brazilian Portuguese male narrator, about 45 years old, deep and warm voice, native Brazilian accent, "
                           "documentary storyteller for history mysteries, calm measured pace, clear diction, serious and captivating tone"),
        ("narrador-jovem", "Brazilian Portuguese male, about 30 years old, confident clear voice, native Brazilian accent from São Paulo, "
                           "YouTube history channel narrator, engaging and slightly intense, medium pace"),
        ("narradora", "Brazilian Portuguese female narrator, about 35 years old, smooth low voice, native Brazilian accent, "
                      "documentary narration with suspense, calm and intimate, clear diction"),
    ],
    "en": [
        ("narrator-deep", "American male documentary narrator, about 45 years old, deep warm voice, calm measured pace, "
                          "serious and captivating, history mystery storytelling"),
        ("narrator-young", "American male, about 30 years old, clear confident voice, YouTube history channel narrator, "
                           "engaging and slightly intense, medium pace"),
    ],
}
PRONTAS = ["Ryan", "Uncle_Fu"]
CACHE = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))


def _log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _carregar(nome, dtype):
    import torch
    from qwen_tts import Qwen3TTSModel
    t0 = time.time()
    m = Qwen3TTSModel.from_pretrained(nome, device_map="cpu", dtype=getattr(torch, dtype))
    _log("carregou", nome, dtype, f"{time.time() - t0:.0f}s")
    return m


def _soltar(m):
    del m
    gc.collect()
    shutil.rmtree(CACHE / "hub", ignore_errors=True)            # libera o disco para o próximo modelo


def _salvar(wavs, sr, arq):
    w = np.asarray(wavs[0], np.float32)
    sf.write(str(arq), w, sr)
    return w, sr


def _estado(pasta):
    arq = pasta / "tmp" / "estado.json"
    return json.loads(arq.read_text()) if arq.exists() else {"refs": {}, "candidatas": {"pt": [], "en": []}}


def _gravar(pasta, est):
    (pasta / "tmp" / "estado.json").write_text(json.dumps(est, ensure_ascii=False, indent=1))


def desenho(pasta):
    """1) Desenhar os narradores (modelo grande; bfloat16 para caber nos 8 GB do GitHub)."""
    tmp = pasta / "tmp"
    est = _estado(pasta)
    m = None
    for dt in ("bfloat16", "float32"):
        try:
            m = _carregar("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", dt)
            break
        except Exception as e:
            _log("VoiceDesign falhou em", dt, str(e)[:200])
    if m is None:
        return
    for idi, lista in DESENHOS.items():
        for nome, descr in lista:
            t0 = time.time()
            try:
                wavs, sr = m.generate_voice_design(text=REF[idi], language=LINGUA[idi], instruct=descr)
                arq = tmp / f"ref-{idi}-{nome}.wav"
                _salvar(wavs, sr, arq)
                est["refs"][f"{idi}|{nome}"] = str(arq)
                _gravar(pasta, est)
                _log("referência", idi, nome, f"{time.time() - t0:.0f}s")
            except Exception as e:
                _log("falhou referência", idi, nome, str(e)[:200])
    _soltar(m)


def clone(pasta):
    """2) Clonar cada narrador desenhado para o texto inteiro (modelo Base pequeno, float32)."""
    tmp = pasta / "tmp"
    est = _estado(pasta)
    if not est["refs"]:
        _log("sem referências para clonar")
        return
    m = _carregar("Qwen/Qwen3-TTS-12Hz-0.6B-Base", "float32")
    for chave, arq in est["refs"].items():
        idi, nome = chave.split("|")
        t0 = time.time()
        try:
            w, sr = sf.read(arq, dtype="float32")
            prompt = m.create_voice_clone_prompt(ref_audio=(w, sr), ref_text=REF[idi])
            wavs, sr2 = m.generate_voice_clone(text=TEXTO[idi], language=LINGUA[idi], voice_clone_prompt=prompt)
            saida = tmp / f"qwen-{idi}-{nome}.wav"
            _salvar(wavs, sr2, saida)
            est["candidatas"][idi].append([str(saida), f"Qwen3-TTS desenhada + clonada: {nome}"])
            _gravar(pasta, est)
            shutil.copy(arq, pasta / f"referencia-{idi}-{nome}.wav")
            _log("clonada", idi, nome, f"{time.time() - t0:.0f}s")
        except Exception as e:
            _log("falhou clone", idi, nome, str(e)[:200])
    _soltar(m)


def prontas(pasta):
    """3) As vozes prontas do Qwen3-TTS (CustomVoice)."""
    tmp = pasta / "tmp"
    est = _estado(pasta)
    m = _carregar("Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", "float32")
    for idi in ("pt", "en"):
        for nome in PRONTAS:
            t0 = time.time()
            try:
                wavs, sr = m.generate_custom_voice(text=TEXTO[idi], language=LINGUA[idi], speaker=nome)
                saida = tmp / f"pronta-{idi}-{nome}.wav"
                _salvar(wavs, sr, saida)
                est["candidatas"][idi].append([str(saida), f"Qwen3-TTS voz pronta: {nome}"])
                _gravar(pasta, est)
                _log("pronta", idi, nome, f"{time.time() - t0:.0f}s")
            except Exception as e:
                _log("falhou pronta", idi, nome, str(e)[:200])
    _soltar(m)


def pocket(pasta):
    """4) Pocket TTS (Kyutai): roda mais rápido que o tempo real no processador. Voz pronta 'rafael' em português,
    vozes prontas em inglês e o clone do narrador grave desenhado no passo 1 (se existir)."""
    from pocket_tts import TTSModel
    tmp = pasta / "tmp"
    est = _estado(pasta)
    for idi, linguas, vozes in (("pt", ["portuguese_24l", "portuguese"], ["rafael"]), ("en", ["english"], ["jean", "javert"])):
        m = None
        for lingua in linguas:
            try:
                t0 = time.time()
                m = TTSModel.load_model(language=lingua)
                _log("pocket carregou", lingua, f"{time.time() - t0:.0f}s")
                break
            except Exception as e:
                _log("pocket não carregou", lingua, str(e)[:200])
        if m is None:
            continue
        fontes = [(v, v) for v in vozes]
        for chave, arq in est["refs"].items():
            ri, nome = chave.split("|")
            if ri == idi and nome in ("narrador-grave", "narrator-deep"):
                fontes.append((f"clone-{nome}", arq))
        for rot, voz in fontes:
            t0 = time.time()
            try:
                st = m.get_state_for_audio_prompt(voz)
                audio = m.generate_audio(st, TEXTO[idi])
                saida = tmp / f"pocket-{idi}-{rot}.wav"
                sf.write(str(saida), audio.detach().cpu().numpy().astype(np.float32), m.sample_rate)
                est["candidatas"][idi].append([str(saida), f"Pocket TTS ({lingua}): {rot}"])
                _gravar(pasta, est)
                _log("pocket", idi, rot, f"{time.time() - t0:.0f}s")
            except Exception as e:
                _log("falhou pocket", idi, rot, str(e)[:200])
        del m
        gc.collect()


def supertonic(pasta):
    """5) Supertonic 3 (Supertone, 31 línguas, ONNX no processador): duas vozes masculinas prontas."""
    from supertonic import TTS
    tmp = pasta / "tmp"
    est = _estado(pasta)
    tts = TTS(model="supertonic-3", auto_download=True)
    nomes = list(tts.voice_style_names)
    _log("supertonic vozes:", nomes)
    homens = [n for n in nomes if n.upper().startswith("M")][:2] or nomes[:2]
    for idi in ("pt", "en"):
        for n in homens:
            t0 = time.time()
            try:
                wav, _ = tts.synthesize(TEXTO[idi], voice_style=tts.get_voice_style(n), lang=idi)
                saida = tmp / f"supertonic-{idi}-{n}.wav"
                tts.save_audio(wav, str(saida))
                est["candidatas"][idi].append([str(saida), f"Supertonic 3: {n}"])
                _gravar(pasta, est)
                _log("supertonic", idi, n, f"{time.time() - t0:.0f}s")
            except Exception as e:
                _log("falhou supertonic", idi, n, str(e)[:200])


def montar(pasta):
    """6) Controles da Microsoft, embaralhar, numerar e montar os vídeos."""
    import asyncio
    import edge_tts
    tmp = pasta / "tmp"
    est = _estado(pasta)
    for idi, vozes in (("pt", ["pt-BR-AntonioNeural"]), ("en", ["en-US-AndrewMultilingualNeural"])):
        for v in vozes:
            mp3 = tmp / f"edge-{idi}-{v}.mp3"
            for tentativa in range(5):
                try:
                    asyncio.run(edge_tts.Communicate(TEXTO[idi], v).save(str(mp3)))
                    break
                except Exception as e:
                    _log("edge falhou", v, str(e)[:120])
                    time.sleep(3)
            if mp3.exists() and mp3.stat().st_size > 2000:
                est["candidatas"][idi].append([str(mp3), f"Microsoft {v} (controle)"])
    mapa = {}
    for idi in ("pt", "en"):
        lista = est["candidatas"][idi][:]
        random.Random(2026 + len(idi)).shuffle(lista)
        partes = []
        for n, (arq, descr) in enumerate(lista, 1):
            wav = tmp / f"n-{idi}-{n:02d}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", arq, "-ar", "44100", "-ac", "1",
                            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", wav], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", pasta / f"{idi}-{n:02d}.mp3"], check=True)
            png = tmp / f"c-{idi}-{n}.png"
            VC.cartao(n, png)
            parte = tmp / f"p-{idi}-{n:02d}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", png, "-i", wav, "-af", "apad=pad_dur=1.0",
                            "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-r", "10", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest", parte], check=True)
            partes.append(parte)
            mapa[f"{idi}-{n:02d}"] = descr
        if partes:
            lst = tmp / f"lista-{idi}.txt"
            lst.write_text("".join(f"file '{p.name}'\n" for p in partes))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                            pasta / f"gratis-{idi}.mp4"], check=True)
    (pasta / "mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1))
    _log("pronto:", json.dumps(mapa, ensure_ascii=False))


ETAPAS = {"desenho": desenho, "clone": clone, "prontas": prontas, "pocket": pocket, "supertonic": supertonic, "montar": montar}


def main(pasta, etapa):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tmp").mkdir(exist_ok=True)
    ETAPAS[etapa](pasta)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
