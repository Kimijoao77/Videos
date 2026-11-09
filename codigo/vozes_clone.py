"""Teste cego de CLONE da voz do dono do canal: modelos abertos e grátis (rodando no GitHub, só processador) copiam o
timbre, o ritmo e as pausas da gravação dele e falam um texto DIFERENTE do que ele leu.

Candidatas (todas com licença que permite canal monetizado):
  • Qwen3-TTS Base 1.7B e 0.6B (Alibaba, Apache 2.0): clona a partir de um trecho com a transcrição.
  • Pocket TTS (Kyutai): pequeno, mais rápido que o tempo real, modelo próprio de português.
  • Chatterbox Multilingual (Resemble AI, MIT).
  • MOSS-TTS-Nano (OpenMOSS, Apache 2.0): 0,1B, 48 kHz.

A gravação fica em REFS/<nome>.<ext> (+ REFS/<nome>.txt com o texto lido). Saem numeradas e embaralhadas; o mapa
número → modelo fica em mapa.json.

Uso: python canal/vozes_clone.py PASTA preparar|qwen|pocket|chatterbox|moss|montar
Ambiente: REF=<nome> (padrão joao), REFS=<pasta das gravações> (padrão canal/vozes/ref)
"""
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

TEXTO_NOVO = {
    "pt": "A ilha era pequena, cercada por pântanos e florestas de pinheiros. Os colonos tinham construído casas simples, "
          "uma cerca de troncos e um pequeno forte. Mas, quando White voltou, as casas estavam desmontadas, como se alguém "
          "tivesse levado tudo com calma, sem pressa nenhuma. Ninguém sabe dizer para onde eles foram.",
    "en": "The island was small, surrounded by marshes and pine forests. The colonists had built simple houses, a wall of "
          "logs and a small fort. But when White came back, the houses had been taken apart, as if someone had packed "
          "everything calmly, in no hurry at all. No one can say where they went.",
}
LINGUA = {"pt": "Portuguese", "en": "English"}


def _log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _sh(*a):
    subprocess.run([str(x) for x in a], check=True)


def _estado(pasta):
    arq = pasta / "estado.json"
    return json.loads(arq.read_text()) if arq.exists() else {"candidatas": {"pt": [], "en": []}}


def _gravar(pasta, est):
    (pasta / "estado.json").write_text(json.dumps(est, ensure_ascii=False, indent=1))


def _add(pasta, idi, arq, descr):
    est = _estado(pasta)
    est["candidatas"][idi].append([str(arq), descr])
    _gravar(pasta, est)
    _log("ok", idi, descr)


def _pausas(wav, minimo=0.3):
    """Pausas reais da gravação: [(início, fim)] com pelo menos `minimo` segundos abaixo de −38 dB."""
    import re
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=noise=-38dB:d={minimo}", "-f", "null", "-"],
                       capture_output=True, text=True)
    ini = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    fim = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    return list(zip(ini, fim))


def _corte(wav, texto, dur, inicio=7.5, fim=16.0):
    """Onde cortar o trecho de referência: no primeiro fim de frase depois de `inicio` segundos que caia numa pausa
    real e longa (a estimativa de tempo, pela fração de letras já faladas, erra mais quanto mais longe do começo;
    por isso vale a primeira frase que bate, não a mais longa). Devolve (segundo do corte, nº de palavras)."""
    import re
    palavras = texto.split()
    letras = [len(re.sub(r"\W", "", w)) + 1 for w in palavras]
    total = sum(letras)
    pausas = [(a, b) for a, b in _pausas(wav) if b - a >= 0.5]
    acum = 0
    for i, w in enumerate(palavras):
        acum += letras[i]
        if w[-1:] not in ".?!":
            continue
        est = dur * acum / total
        if est < inicio or est > fim:
            continue
        perto = [(abs(a - est), a) for a, b in pausas if abs(a - est) < 1.2 and a >= inicio - 1.5]
        if perto:
            return min(perto)[1] + 0.12, i + 1
    return min(dur, 12.0), len(palavras)


def preparar(pasta):
    """Limpa a gravação (corta silêncio, tira chiado grave, nivela o volume) e separa um trecho de 8 a 15 s que
    termina num fim de frase, com a transcrição exata desse trecho (o Qwen precisa dela)."""
    import voz as V
    nome = os.environ.get("REF", "joao")
    refs = Path(os.environ.get("REFS", AQUI / "vozes" / "ref"))
    gravs = [p for p in refs.glob(f"{nome}.*") if p.suffix.lower() != ".txt"]
    if not gravs:
        sys.exit(f"não achei a gravação {nome}.* em {refs}")
    texto = (refs / f"{nome}.txt").read_text(encoding="utf-8").strip()
    longa = pasta / "ref-longa.wav"
    _sh("ffmpeg", "-v", "error", "-y", "-i", gravs[0], "-ac", "1", "-ar", "24000",
        "-af", "highpass=f=70,afftdn=nf=-25,"
               "silenceremove=start_periods=1:start_duration=0.15:start_threshold=-40dB:start_silence=0.15,"
               "areverse,silenceremove=start_periods=1:start_duration=0.15:start_threshold=-40dB:start_silence=0.3,"
               "areverse,loudnorm=I=-18:TP=-1.5:LRA=11", "-c:a", "pcm_s16le", longa)
    dur = V.duracao(longa)
    corte, n = _corte(longa, texto, dur)
    curta = pasta / "ref-curta.wav"
    _sh("ffmpeg", "-v", "error", "-y", "-i", longa, "-t", f"{corte + 0.25:.2f}", "-c:a", "pcm_s16le", curta)
    palavras = texto.split()
    est = {"candidatas": {"pt": [], "en": []}, "ref_longa": str(longa), "texto_longa": texto,
           "ref_curta": str(curta), "texto_curta": " ".join(palavras[:n]), "dur_longa": dur, "dur_curta": corte}
    _gravar(pasta, est)
    _log("referência:", f"{dur:.1f}s no total, trecho de {corte:.1f}s",
         "" if os.environ.get("CANAL_PUBLICO") else est["texto_curta"])     # registro público: sem o texto lido


def qwen(pasta):
    import gc
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    est = _estado(pasta)
    for modelo, dtype, casos in (
            ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", torch.bfloat16, [("pt", "curta"), ("pt", "longa"), ("en", "curta")]),
            ("Qwen/Qwen3-TTS-12Hz-0.6B-Base", torch.float32, [("pt", "curta")])):
        t0 = time.time()
        m = Qwen3TTSModel.from_pretrained(modelo, device_map="cpu", dtype=dtype)
        _log("carregou", modelo, f"{time.time() - t0:.0f}s")
        for idi, qual in casos:
            t0 = time.time()
            try:
                w, sr = sf.read(est[f"ref_{qual}"], dtype="float32")
                prompt = m.create_voice_clone_prompt(ref_audio=(w, sr), ref_text=est[f"texto_{qual}"])
                wavs, sr2 = m.generate_voice_clone(text=TEXTO_NOVO[idi], language=LINGUA[idi], voice_clone_prompt=prompt)
                saida = pasta / f"qwen-{modelo.split('-')[-2]}-{idi}-{qual}.wav"
                sf.write(str(saida), np.asarray(wavs[0], np.float32), sr2)
                _add(pasta, idi, saida, f"Qwen3-TTS {modelo.split('-')[-2]} (referência {qual}) {time.time() - t0:.0f}s")
            except Exception as e:
                _log("falhou", modelo, idi, qual, str(e)[:200])
        del m
        gc.collect()


def pocket(pasta):
    import soundfile as sf
    from pocket_tts import TTSModel
    est = _estado(pasta)
    for idi, linguas in (("pt", ["portuguese_24l", "portuguese"]), ("en", ["english"])):
        m = None
        for lingua in linguas:
            try:
                m = TTSModel.load_model(language=lingua)
                break
            except Exception as e:
                _log("pocket não carregou", lingua, str(e)[:200])
        if m is None:
            continue
        t0 = time.time()
        try:
            st = m.get_state_for_audio_prompt(est["ref_curta"])
            audio = m.generate_audio(st, TEXTO_NOVO[idi])
            saida = pasta / f"pocket-{idi}.wav"
            sf.write(str(saida), audio.detach().cpu().numpy(), m.sample_rate)
            _add(pasta, idi, saida, f"Pocket TTS ({lingua}) {time.time() - t0:.0f}s")
        except Exception as e:
            _log("falhou pocket", idi, str(e)[:200])


def chatterbox(pasta):
    import torch
    import torchaudio
    carregar = torch.load
    torch.load = lambda *a, **k: carregar(*a, **{**k, "map_location": "cpu"})
    torch.set_num_threads(os.cpu_count() or 2)
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    est = _estado(pasta)
    m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    for idi in ("pt", "en"):
        t0 = time.time()
        try:
            wav = m.generate(TEXTO_NOVO[idi], language_id=idi, audio_prompt_path=est["ref_curta"], exaggeration=0.5, cfg_weight=0.5)
            saida = pasta / f"chatterbox-{idi}.wav"
            torchaudio.save(str(saida), wav, m.sr)
            _add(pasta, idi, saida, f"Chatterbox Multilingual {time.time() - t0:.0f}s")
        except Exception as e:
            _log("falhou chatterbox", idi, str(e)[:200])


def moss(pasta):
    """Usa a linha de comando do MOSS-TTS-Nano (instalado do repositório oficial pelo fluxo)."""
    est = _estado(pasta)
    trabalho = pasta / "moss"
    trabalho.mkdir(exist_ok=True)
    for idi in ("pt",):
        t0 = time.time()
        try:
            subprocess.run(["moss-tts-nano", "generate", "--prompt-speech", est["ref_curta"], "--text", TEXTO_NOVO[idi]],
                           check=True, cwd=trabalho)
            saidas = sorted((trabalho / "generated_audio").glob("*.wav"), key=lambda p: p.stat().st_mtime)
            if not saidas:
                raise RuntimeError("não gerou o arquivo")
            saida = pasta / f"moss-{idi}.wav"
            saidas[-1].rename(saida)
            _add(pasta, idi, saida, f"MOSS-TTS-Nano {time.time() - t0:.0f}s")
        except Exception as e:
            _log("falhou moss", idi, str(e)[:300])


def montar(pasta):
    import vozes_cego as VC
    est = _estado(pasta)
    pub = pasta / "pub"
    pub.mkdir(exist_ok=True)
    mapa = {}
    for idi in ("pt", "en"):
        lista = est["candidatas"][idi][:]
        random.Random(1587 + len(idi)).shuffle(lista)
        partes = []
        for n, (arq, descr) in enumerate(lista, 1):
            wav = pasta / f"n-{idi}-{n:02d}.wav"
            _sh("ffmpeg", "-v", "error", "-y", "-i", arq, "-ar", "44100", "-ac", "1", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", wav)
            _sh("ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", pub / f"clone-{idi}-{n:02d}.mp3")
            png = pasta / f"c-{idi}-{n}.png"
            VC.cartao(n, png)
            parte = pasta / f"p-{idi}-{n:02d}.mp4"
            _sh("ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", png, "-i", wav, "-af", "apad=pad_dur=1.0", "-c:v", "libx264",
                "-tune", "stillimage", "-preset", "veryfast", "-r", "10", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-ar", "44100", "-shortest", parte)
            partes.append(parte)
            mapa[f"{idi}-{n:02d}"] = descr
        if partes:
            lst = pasta / f"lista-{idi}.txt"
            lst.write_text("".join(f"file '{p.name}'\n" for p in partes))
            _sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", pub / f"clone-{idi}.mp4")
    (pub / "mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1))
    _log("pronto:", json.dumps(mapa, ensure_ascii=False))


ETAPAS = {"preparar": preparar, "qwen": qwen, "pocket": pocket, "chatterbox": chatterbox, "moss": moss, "montar": montar}

if __name__ == "__main__":
    pasta = Path(sys.argv[1])
    pasta.mkdir(parents=True, exist_ok=True)
    ETAPAS[sys.argv[2]](pasta)
