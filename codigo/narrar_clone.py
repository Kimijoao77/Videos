"""Narração com a voz clonada do dono do canal: modelos abertos e grátis rodando no GitHub (só processador) copiam
o timbre e o jeito de falar da gravação dele e leem o roteiro. Nada roda no computador dele.

Gera <SAIDA>/<slug>/<idioma>/_tmp/bNN.wav (uma por batida); depois o filme.py usa esses arquivos (motor "clone").
No roteiro:  "voz": {"motor": "clone", "pt": "chatterbox", "en": "chatterbox"}
  chatterbox  Chatterbox Multilingual (Resemble AI, MIT): a escolhida para o português (teste cego, voz 2) e, desde
              08/11/2026, também para o inglês (era a voz 1 do teste cego em inglês)
  qwen-1.7b   Qwen3-TTS 1.7B Base (Alibaba, Apache 2.0): ganhou o teste cego em inglês, mas no Roanoke inteiro não
              parava no fim da frase em metade das falas (seguia fazendo som até o limite). Fica de reserva até isso
              ser consertado
  qwen-0.6b   Qwen3-TTS 0.6B Base: reserva para o português (teste cego, voz 3), guardada a pedido do dono do canal

A referência é a gravação do ramo 'vozes' (REFS/<REF>.*), limpa e cortada igual ao teste (vozes_clone.preparar).
Os números vão por extenso (voz.por_extenso). Nomes estrangeiros que a voz lê errado vão no roteiro em
"pronuncia": {"pt": {"Virginia": "Virgínia", "Dare": "Dér"}}: a troca vale só para a voz (as etiquetas ficam com a
grafia certa) e precisa manter o número de palavras (o tempo das etiquetas conta as palavras da fala). Cada fala é conferida (duração esperada e pausas longas demais) e
refeita até 3 vezes se sair estranha. As falas prontas ficam na release privada canal-narracao-<slug> (nome = hash
do texto, do motor e da referência): se a geração cair no meio, a próxima rodada continua de onde parou, e mudar
uma fala só gera ela de novo.

Ritmo natural (desde 10/11/2026, "voz": {..., "ritmo": "natural"}): frase por frase, com o trecho da gravação que
combina com o tom de cada fala, as pausas que o dono faz quando lê e o Whisper conferindo cada frase (ver
narrar_natural e canal/ouvido.py).

Uso: python canal/narrar_clone.py ROTEIRO IDIOMA SAIDA [--verificar]   (--verificar: só diz se falta alguma fala)
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
import voz as V            # noqa: E402
import vozes_clone as VC   # noqa: E402

VERSAO = 1                                  # mude para gerar todas as falas de novo
# Jeito de falar (Chatterbox). "calma" é a voz de antes de 09/11/2026 e fica como cópia de segurança: as falas dela
# continuam guardadas e a chave delas não mudou. "animada" (09/11, o dono achou a voz desanimada): mais emoção e
# ritmo mais solto, como a Resemble recomenda para fala expressiva. No roteiro: "voz": {..., "estilo": "animada"};
# para testar sem mexer no roteiro: VOZ_ESTILO=animada e VOZ_FALAS=4 (só as 4 primeiras falas).
ESTILOS = {"calma": {"exaggeration": 0.5, "cfg_weight": 0.5}, "animada": {"exaggeration": 0.72, "cfg_weight": 0.3},
           "empolgada": {"exaggeration": 1.0, "cfg_weight": 0.25, "temperature": 0.9},  # 09/11: a animada ainda soou desanimada
           # "viva" (09/11): o modelo copia o jeito da gravação; em vez do começo dela, usa os 10 s mais vivos (mais
           # variação de tom e de volume), com emoção alta e a fala 6 % mais rápida no fim (sem mudar o tom da voz)
           "viva": {"exaggeration": 0.85, "cfg_weight": 0.3, "temperature": 0.85},
           # "solta" (09/11, pedido do dono: "simule que minha voz é mais animada"): a gravação passa antes por um
           # ajuste de entonação (PSOLA no Praat: tom 1,8× mais variado e 1,5 semitom mais alto, 5 % mais rápida),
           # e o clone copia esse jeito mais animado. Usa o trecho do começo, que termina numa pausa (sem o "mon")
           "solta": {"exaggeration": 0.7, "cfg_weight": 0.35, "temperature": 0.8}}
TEMPO = {"viva": 1.06}
MOTORES = ("chatterbox", "qwen-1.7b", "qwen-0.6b", "edge")
# "edge" (09/11/2026): voz nativa grátis da Microsoft (não é clone). Usada no inglês: o clone da voz do dono fica com
# sotaque brasileiro em inglês. As falas passam pelas mesmas conferências e pelo mesmo cache.
VOZ_EDGE = {"pt": "pt-BR-AntonioNeural", "en": "en-US-AndrewNeural"}
RAPIDA = float(os.environ.get("VOZ_RAPIDA") or 0.93)   # fala com menos de 93 % do tempo esperado = rápida demais (emenda palavras): refaz; se continuar, desacelera
LINGUA = {"pt": "Portuguese", "en": "English"}
LETRAS_POR_SEGUNDO = 19.0                   # medido no teste cego (as duas vozes escolhidas falam ~19 letras/s)


def _log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def L(x, idioma):
    if isinstance(x, dict):
        return x.get(idioma) or x.get("pt") or ""
    return x or ""


def falado_de(r, b, idioma):
    """O que a voz lê na batida: a fala com as trocas de "pronuncia" do roteiro e os números por extenso."""
    texto = L(b["fala"], idioma)
    for de, para in ((r.get("pronuncia") or {}).get(idioma) or {}).items():
        texto = re.sub(rf"(?<!\w){re.escape(de)}(?!\w)", para, texto)
    return V.por_extenso(texto, idioma)


class Cache:
    """Falas já geradas, guardadas como arquivos de uma release privada do repositório."""

    def __init__(self, tag):
        self.tag, self.ativos = tag, {}
        # CANAL_REPO: a fábrica roda no repositório público Kimijoao77/Videos, mas as falas ficam no Engfy (privado)
        repo = os.environ.get("CANAL_REPO") or os.environ.get("GITHUB_REPOSITORY", "")
        self.repo = repo if shutil.which("gh") else ""
        if not self.repo:
            _log("sem cache (fora do GitHub)")
            return
        r = subprocess.run(["gh", "api", f"repos/{self.repo}/releases/tags/{tag}", "--jq",
                            '.assets[] | select(.state == "uploaded" and .size > 1000) | "\\(.name)\\t\\(.id)\\t\\(.size)"'],
                           capture_output=True, text=True)
        if r.returncode:
            subprocess.run(["gh", "release", "create", tag, "-R", self.repo, "--prerelease", "--title",
                            "Canal: narração com a voz clonada (guardada)", "--notes",
                            "Falas geradas com a voz clonada do dono do canal, guardadas para não gerar de novo. "
                            "Pode apagar quando o vídeo estiver pronto."], capture_output=True, text=True)
        else:
            for ln in r.stdout.splitlines():
                nome, id_, tam = ln.split("\t")
                self.ativos[nome] = (id_, int(tam))
        _log(f"cache {tag}: {len(self.ativos)} falas guardadas")

    def baixar(self, chave, destino):
        item = self.ativos.get(f"{chave}.wav")
        if not item:
            return False
        for _ in range(3):
            with open(destino, "wb") as f:
                r = subprocess.run(["gh", "api", "-H", "Accept: application/octet-stream",
                                    f"repos/{self.repo}/releases/assets/{item[0]}"], stdout=f)
            if r.returncode == 0 and destino.stat().st_size == item[1]:
                try:
                    with wave.open(str(destino)) as w:
                        if w.getnframes() > 0:
                            return True
                except Exception:
                    pass
        return False

    def subir(self, chave, arq):
        if not self.repo:
            return
        alvo = arq.parent / f"{chave}.wav"
        shutil.copyfile(arq, alvo)
        for tentativa in range(3):
            r = subprocess.run(["gh", "release", "upload", self.tag, str(alvo), "--clobber", "-R", self.repo],
                               capture_output=True, text=True)
            if r.returncode == 0:
                break
            _log("não guardou no cache, tentando de novo:", r.stderr.strip()[:200])
            time.sleep(5 + 5 * tentativa)
        alvo.unlink(missing_ok=True)


def carregar(motor, est, idioma, estilo="calma"):
    """Carrega o modelo uma vez e devolve gerar(texto, semente) -> (áudio float32 mono, taxa)."""
    t0 = time.time()
    if motor == "edge":
        import asyncio
        import tempfile
        import edge_tts
        import soundfile as sf
        voz = os.environ.get("VOZ_EDGE") or VOZ_EDGE[idioma]
        _log(f"voz nativa {voz}")

        def um_pedaco(texto, d, tentativas):
            """Um trecho pelo serviço da Microsoft; ele às vezes devolve vazio: espera e tenta de novo."""
            mp3, wav = Path(d) / "f.mp3", Path(d) / "f.wav"
            for tentativa in range(tentativas):
                try:
                    asyncio.run(edge_tts.Communicate(texto, voz, rate="+3%").save(str(mp3)))
                    break
                except Exception as ex:  # noqa: BLE001
                    if tentativa == tentativas - 1:
                        raise
                    espera = (5, 10, 20, 30, 45, 60, 60, 60, 60)[min(tentativa, 8)]   # o bloqueio do serviço dura alguns minutos
                    _log(f"voz nativa falhou ({type(ex).__name__}), tentando de novo em {espera}s")
                    time.sleep(espera)
            time.sleep(1.5)                                  # sem pressa: chamadas seguidas demais fazem o serviço recusar
            V._sh("ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", "24000", wav)
            return sf.read(str(wav), dtype="float32")

        def gerar(texto, semente):
            with tempfile.TemporaryDirectory() as d:
                try:
                    return um_pedaco(texto, d, 8)
                except Exception:  # noqa: BLE001
                    # a fala inteira não veio: pede em pedaços (frases e vírgulas) e junta com uma pausa curta
                    partes = [x.strip() for x in re.split(r"(?<=[.,;:?!])\s+", texto) if x.strip()]
                    if len(partes) < 2:
                        return um_pedaco(texto, d, 8)          # frase única: mais uma rodada de tentativas
                    _log(f"voz nativa: fala inteira falhou, pedindo em {len(partes)} pedaços")
                    audios, sr = [], 24000
                    for parte in partes:
                        a, sr = um_pedaco(parte, d, 8)
                        audios += [aparar(a, sr), np.zeros(int(sr * 0.18), np.float32)]
                    return np.concatenate(audios[:-1]), sr
        return gerar
    import torch
    torch.set_num_threads(os.cpu_count() or 2)
    if motor == "chatterbox":
        carregar_ = torch.load
        torch.load = lambda *a, **k: carregar_(*a, **{**k, "map_location": "cpu"})
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
        _log(f"carregou o Chatterbox em {time.time() - t0:.0f}s")

        def gerar(texto, semente):
            torch.manual_seed(semente)
            wav = m.generate(texto, language_id=idioma, audio_prompt_path=est["ref_curta"], **ESTILOS[estilo])
            return wav.squeeze(0).detach().cpu().numpy().astype(np.float32), m.sr
        return gerar
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel
    nome, dtype = {"qwen-1.7b": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", torch.bfloat16),
                   "qwen-0.6b": ("Qwen/Qwen3-TTS-12Hz-0.6B-Base", torch.float32)}[motor]
    m = Qwen3TTSModel.from_pretrained(nome, device_map="cpu", dtype=dtype)
    w, sr = sf.read(est["ref_curta"], dtype="float32")
    prompt = m.create_voice_clone_prompt(ref_audio=(w, sr), ref_text=est["texto_curta"])
    _log(f"carregou {nome} em {time.time() - t0:.0f}s")

    def gerar(texto, semente):
        torch.manual_seed(semente)
        # limite de quadros (12,5 por segundo): no máximo ~2,2× a duração esperada. Sem isso, quando o modelo não acha o
        # fim da frase ele fala até o limite padrão (8192 quadros, 11 minutos de áudio, mais de 1 hora de processador)
        limite = int(12.5 * max(2.0, len(texto) / LETRAS_POR_SEGUNDO) * 2.2) + 40
        wavs, sr2 = m.generate_voice_clone(text=texto, language=LINGUA[idioma], voice_clone_prompt=prompt, max_new_tokens=limite)
        return np.asarray(wavs[0], np.float32).reshape(-1), sr2
    return gerar


def animar(origem, destino, faixa=1.8, semitons=1.5, tempo=1.05):
    """A mesma gravação com a entonação mais solta: o tom varia `faixa` vezes mais em volta da média, sobe `semitons`
    e a fala fica `tempo` vezes mais rápida (PSOLA do Praat, sem trocar a voz)."""
    import parselmouth
    from parselmouth.praat import call
    snd = parselmouth.Sound(str(origem))
    man = call(snd, "To Manipulation", 0.01, 70, 400)
    tier = call(man, "Extract pitch tier")
    pitch = snd.to_pitch(0.01, 70, 400)
    media = call(pitch, "Get mean", 0, 0, "Hertz")
    alvo = media * 2 ** (semitons / 12)
    for i in range(1, int(call(tier, "Get number of points")) + 1):
        t = call(tier, "Get time from index", i)
        f = call(tier, "Get value at index", i)
        novo = alvo * (f / media) ** faixa
        call(tier, "Remove point", i)
        call(tier, "Add point", t, max(60.0, min(450.0, novo)))
    call([tier, man], "Replace pitch tier")
    dur = call(man, "Extract duration tier")
    call(dur, "Add point", 0, 1 / tempo)
    call([dur, man], "Replace duration tier")
    out = call(man, "Get resynthesis (overlap-add)")
    out.save(str(destino), "WAV")
    _log(f"gravação animada: tom {faixa}× mais variado, +{semitons} semitom, {tempo}× mais rápida")
    return str(destino)


def trecho_vivo(longa, destino, dur=10.0):
    """Os `dur` segundos mais vivos da gravação: mais variação de tom (F0 por autocorrelação) e de volume."""
    import soundfile as sf
    a, sr = sf.read(str(longa), dtype="float32")
    a = a if a.ndim == 1 else a.mean(1)
    q = int(sr * 0.04)
    f0, vol = [], []
    for i in range(0, len(a) - q, q):
        x = a[i:i + q] - a[i:i + q].mean()
        e = float(np.sqrt(np.mean(x ** 2)))
        vol.append(e)
        if e < 0.01:
            f0.append(np.nan)
            continue
        c = np.correlate(x, x, "full")[q - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        k = lo + int(np.argmax(c[lo:hi]))
        f0.append(sr / k if c[k] > 0.3 * c[0] else np.nan)
    f0, vol = np.array(f0), np.array(vol)
    n = int(dur / 0.04)
    if len(f0) <= n:
        shutil.copy(longa, destino)
        return str(destino)
    melhor, ini = -1.0, 0
    for j in range(0, len(f0) - n, 5):
        w = f0[j:j + n]
        ok = w[~np.isnan(w)]
        if len(ok) < n * 0.35:
            continue
        nota = float(np.std(np.log(ok))) + 0.5 * float(np.std(vol[j:j + n]) / (np.mean(vol[j:j + n]) + 1e-6))
        if nota > melhor:
            melhor, ini = nota, j
    V._sh("ffmpeg", "-y", "-v", "error", "-ss", f"{ini * 0.04:.2f}", "-t", f"{dur:.2f}", "-i", str(longa), "-c:a", "pcm_s16le", str(destino))
    _log(f"trecho vivo da gravação: {ini * 0.04:.1f}s a {ini * 0.04 + dur:.1f}s")
    return str(destino)


def _envelope(a, sr):
    passo = max(1, int(sr * 0.01))
    n = max(1, len(a) // passo)
    env = np.sqrt((a[:n * passo].reshape(n, passo) ** 2).mean(axis=1) + 1e-12)
    return env, passo


def aparar(a, sr, limiar_db=-45.0, folga=0.06):
    """Corta o silêncio do começo e do fim, deixando `folga` segundos."""
    a = np.asarray(a, np.float32).reshape(-1)
    env, passo = _envelope(a, sr)
    fala = env > 10 ** (limiar_db / 20)
    if not fala.any():
        return a
    k = int(folga * sr / passo)
    i0 = max(0, int(np.argmax(fala)) - k) * passo
    i1 = min(len(a), (len(fala) - int(np.argmax(fala[::-1])) + k) * passo)
    return a[i0:i1]


def avaliar(a, sr, texto, minimo=1.0):
    """Problemas da fala gerada (duração fora do esperado, pausa longa demais) e uma nota (menor = melhor)."""
    dur = len(a) / sr
    esperado = max(minimo, len(texto) / LETRAS_POR_SEGUNDO)
    razao = dur / esperado
    env, passo = _envelope(a, sr)
    fala = env > max(10 ** (-40 / 20), 0.06 * float(np.percentile(env, 95)))
    maior, atual = 0, 0
    for f in fala:
        atual = 0 if f else atual + 1
        maior = max(maior, atual)
    pausa = maior * passo / sr
    problemas = []
    if 0.6 <= razao < RAPIDA:
        problemas.append(f"rápida demais ({dur:.1f}s para ~{esperado:.1f}s)")
    if not 0.6 <= razao <= 1.7:
        problemas.append(f"{dur:.1f}s para ~{esperado:.1f}s")
    if pausa > 1.6:
        problemas.append(f"pausa de {pausa:.1f}s")
    return problemas, abs(math.log(max(razao, 1e-3))) + max(0.0, pausa - 1.0)


def finalizar(a, sr, destino, tempo=1.0):
    """Volume igual em todas as falas (−20 dB na voz, pico até −1 dB), 44,1 kHz mono 16 bits."""
    import soundfile as sf
    env, passo = _envelope(a, sr)
    fala = np.repeat(env > 0.1 * float(np.percentile(env, 95)), passo)[: len(a)]
    rms = float(np.sqrt(np.mean(a[: len(fala)][fala] ** 2))) if fala.any() else float(np.sqrt(np.mean(a ** 2)))
    ganho = 10 ** (-20 / 20) / max(rms, 1e-6)
    pico = float(np.abs(a).max()) * ganho
    if pico > 10 ** (-1 / 20):
        ganho *= 10 ** (-1 / 20) / pico
    a = a * ganho
    f = min(len(a) // 2, int(sr * 0.01))
    if f:
        a[:f] *= np.linspace(0, 1, f)
        a[-f:] *= np.linspace(1, 0, f)
    bruto = destino.with_suffix(".bruto.wav")
    sf.write(str(bruto), a, sr, subtype="PCM_16")
    filtro = "highpass=f=60" + (f",atempo={tempo:.3f}" if abs(tempo - 1) > 1e-3 else "")
    V._sh("ffmpeg", "-y", "-v", "error", "-i", bruto, "-af", filtro, "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", destino)
    bruto.unlink(missing_ok=True)


# ------------------------------------------------------------------ ritmo natural (10/11/2026)
# O dono do canal achou a voz linear, sem pausa e corrida: o clone falava a ~176 palavras por minuto com 19 % de
# silêncio, e ele lê a ~146 contando as pausas. No roteiro: "voz": {..., "ritmo": "natural"} e, em cada batida,
# "tom": narra (padrão) | tenso | impacto | leve; frase que termina em "?" ganha o tom de pergunta sozinha.
# Cada frase é gerada sozinha, com o trecho da gravação que combina com o tom (o Whisper acha as frases da gravação,
# canal/ouvido.py), e o Whisper confere o que a voz disse: tentativa errada é descartada e, entre as certas, fica a
# de tom mais variado. As frases se juntam com as pausas que o dono faz quando lê (medidas na gravação).
VERSAO_NATURAL = "n1"                      # mude para gerar de novo todas as falas do ritmo natural
TONS = {"narra": {"ref": "viva", "exaggeration": 0.6, "cfg_weight": 0.4, "temperature": 0.8},
        "tenso": {"ref": "tensa", "exaggeration": 0.5, "cfg_weight": 0.3, "temperature": 0.75, "tempo": 0.96},
        "impacto": {"ref": "viva", "exaggeration": 0.85, "cfg_weight": 0.3, "temperature": 0.8},
        "leve": {"ref": "viva", "exaggeration": 0.75, "cfg_weight": 0.45, "temperature": 0.9},
        "pergunta": {"ref": "pergunta", "exaggeration": 0.65, "cfg_weight": 0.4, "temperature": 0.8}}
TONS_DO_ROTEIRO = ("narra", "tenso", "impacto", "leve")
ALVO_TOM = float(os.environ.get("VOZ_ALVO_TOM") or 2.1)   # semitons: abaixo disso a frase soa reta (tenta mais uma)
# (o clone fica em ~2,0 a 2,3 quase sempre, então tentar de novo atrás de mais tom quase não adianta: o que deixa a
# voz viva é o realce, feito depois; a segunda tentativa fica para as frases bem retas)
SEMELHANCA_MIN = 0.88                      # o Whisper precisa ouvir pelo menos isso do texto (1 = igual)
PAUSA_FIM = {".": 1.0, "?": 1.25, "!": 1.1, "…": 1.45}   # pausa depois da frase, vezes a pausa típica do dono
FOLGA = 0.06                               # aparar() deixa 60 ms de silêncio em cada ponta da frase


# Realce do tom (10/11/2026): o clone sai com o tom quase reto (desvio de ~2 semitons nas falas do Vasa; a voz nativa
# em inglês tem ~4). Com "voz": {..., "realce": 3.0}, cada fala tem as subidas e descidas do tom esticadas até o alvo
# (no máximo 1,8 vez), sem mexer no tremido fino da voz nem na duração (PSOLA do Praat). É feito ao pegar a fala (do
# cache ou recém-gerada), então mudar o alvo não gera a voz de novo. O tom da batida ajusta o alvo e o tenso fica um
# semitom mais grave.
REALCE_TOM = {"narra": 0.0, "tenso": -0.4, "impacto": 0.4, "leve": 0.3}
SEMITOM_TOM = {"tenso": -1.0}


def realcar_tom(a, sr, alvo, semitons=0.0, maximo=1.8, janela=0.15):
    """Devolve (áudio, fator): o contorno do tom (média de ~150 ms) esticado em volta do tom mediano até o desvio
    chegar em `alvo` semitons; a variação fina em volta do contorno fica como estava."""
    import parselmouth
    from parselmouth.praat import call
    import ouvido as O
    t = O.tom(a, sr)
    if t["dp"] <= 0 or t["hz"] <= 0 or (t["dp"] >= alvo and abs(semitons) < 0.05):
        return a, 1.0
    snd = parselmouth.Sound(np.asarray(a, np.float64), sampling_frequency=sr)
    man = call(snd, "To Manipulation", 0.01, 65, 420)
    tier = call(man, "Extract pitch tier")
    n = int(call(tier, "Get number of points"))
    if n < 5:
        return a, 1.0
    ts = np.array([call(tier, "Get time from index", i) for i in range(1, n + 1)])
    lg = np.log2([call(tier, "Get value at index", i) for i in range(1, n + 1)])
    med = math.log2(t["hz"])
    bom = np.abs(12 * (lg - med)) < 9                   # pulos de oitava do detector ficam de fora (o Praat interpola)
    ts, lg = ts[bom], lg[bom]
    if len(ts) < 5:
        return a, 1.0
    suave = np.array([lg[np.abs(ts - x) <= janela / 2].mean() for x in ts])
    v_suave, v_fino = float(np.var(suave - med)), float(np.var(lg - suave))
    parte = v_suave / max(1e-9, v_suave + v_fino)        # quanto da variação é contorno (o resto é tremido fino)
    # desvio depois ≈ dp · raiz(parte·k² + 1 − parte): acha o k que leva ao alvo
    k = math.sqrt(max(0.0, (alvo / t["dp"]) ** 2 - (1 - parte)) / parte) if parte > 0.05 else 1.0
    k = min(maximo, max(1.0, k))
    if k < 1.03 and abs(semitons) < 0.05:
        return a, 1.0
    novo = 2 ** (med + (suave - med) * k + (lg - suave) + semitons / 12)
    nt = call("Create PitchTier", "realce", snd.xmin, snd.xmax)
    for x, f in zip(ts, novo):
        call(nt, "Add point", float(x), float(min(450.0, max(55.0, f))))
    call([nt, man], "Replace pitch tier")
    out = call(man, "Get resynthesis (overlap-add)")
    return np.asarray(out.values[0], np.float32)[: len(a)], k


def realcar_arquivo(arq, alvo, tom="narra"):
    """Realce do tom numa fala pronta (wav de finalizar), no lugar. Devolve (desvio antes, desvio depois, fator)."""
    import soundfile as sf
    import ouvido as O
    a, sr = sf.read(str(arq), dtype="float32")
    antes = O.tom(a, sr)["dp"]
    b, k = realcar_tom(a, sr, alvo + REALCE_TOM.get(tom, 0.0), SEMITOM_TOM.get(tom, 0.0))
    depois = O.tom(b, sr)["dp"]
    if k > 1.0 and depois < antes:              # fala curta com o tom mal medido: o realce piorou, fica a original
        return antes, antes, 1.0
    pico = float(np.abs(b).max()) or 1.0
    if pico > 0.98:
        b = b * (0.98 / pico)
    sf.write(str(arq), b, sr, subtype="PCM_16")
    return antes, depois, k


def gravacao_original():
    """A gravação do dono como veio (o hash dela entra na chave das falas: não muda com versão do ffmpeg)."""
    refs = Path(os.environ.get("REFS", AQUI / "vozes" / "ref"))
    nome = os.environ.get("REF", "joao")
    gravs = sorted(p for p in refs.glob(f"{nome}.*") if p.suffix.lower() != ".txt")
    if not gravs:
        sys.exit(f"não achei a gravação {nome}.* em {refs}")
    return gravs[0]


def dividir_frases(texto):
    return [x.strip() for x in re.split(r"(?<=[.?!…])\s+", texto.strip()) if x.strip()]


def tom_da_frase(frase, tom_batida):
    if frase.rstrip().endswith("?") and tom_batida in ("narra", "leve"):
        return "pergunta"
    return tom_batida


def chave_natural(motor, h_grav, idioma, tom, falado):
    return hashlib.sha1(f"{VERSAO_NATURAL}|{motor}|{h_grav}|{idioma}|{tom}|{falado}".encode()).hexdigest()[:16]


def pausa_depois(frase, tipica, rng):
    """Silêncio a inserir depois da frase (sem contar as folgas que aparar() já deixou)."""
    alvo = tipica * PAUSA_FIM.get(frase.rstrip()[-1:], 1.0) * rng.uniform(0.88, 1.12)
    return max(0.12, alvo - 2 * FOLGA)


def preparar_tons(est, pasta):
    """Acha as frases da gravação com o Whisper, corta um trecho por tom e mede as pausas do dono.
    Grava est["refs_tom"] ({tom: wav}) e est["pausas"] ({"frase": s, "virgula": s})."""
    import ouvido as O
    est["refs_tom"], est["pausas"] = {}, {"frase": 0.5, "virgula": 0.2}
    if not O.disponivel():
        _log("sem o Whisper: todos os tons usam o trecho de sempre, com pausas de 0,5 s")
        return est
    t0 = time.time()
    frases, virgulas, dur = O.frases_da_gravacao(est["ref_longa"], "pt")
    for nome, w in O.escolher_referencias(frases, dur).items():
        est["refs_tom"][nome] = O.cortar(est["ref_longa"], w["ini"], w["fim"], pasta / f"ref-{nome}.wav")
        _log(f"referência '{nome}': frases {w['de']} a {w['ate']} ({w['fim'] - w['ini']:.1f}s), tom {w['dp']:.1f} st, "
             f"{w['letras_s']:.1f} letras/s")
    est["pausas"] = O.pausas_da_gravacao(frases, virgulas)
    _log(f"gravação ouvida em {time.time() - t0:.0f}s: {len(frases)} frases, tom típico "
         f"{float(np.median([f['dp'] for f in frases] or [0])):.1f} st, pausa depois de frase {est['pausas']['frase']:.2f}s, "
         f"depois de vírgula {est['pausas']['virgula']:.2f}s")
    return est


def carregar_chatterbox():
    import torch
    torch.set_num_threads(os.cpu_count() or 2)
    carregar_ = torch.load
    torch.load = lambda *a, **k: carregar_(*a, **{**k, "map_location": "cpu"})
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t0 = time.time()
    m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    _log(f"carregou o Chatterbox em {time.time() - t0:.0f}s")

    def gerar(texto, semente, tom, est, idioma):
        t = TONS[tom]
        ref = est["refs_tom"].get(t["ref"]) or est["refs_tom"].get("viva") or est["ref_curta"]
        torch.manual_seed(semente)
        wav = m.generate(texto, language_id=idioma, audio_prompt_path=ref, exaggeration=t["exaggeration"],
                         cfg_weight=t["cfg_weight"], temperature=t["temperature"])
        return wav.squeeze(0).detach().cpu().numpy().astype(np.float32), m.sr
    return gerar


def melhor_frase(gerar, frase, tom, semente, est, idioma, ouvir):
    """Até 3 tentativas da frase: fica a certa (duração, pausas e o Whisper) de tom mais variado."""
    import ouvido as O
    melhor = None
    for tentativa in range(3):
        a, sr = gerar(frase, semente + tentativa, tom, est, idioma)
        a = aparar(a, sr, folga=FOLGA)
        problemas, nota = avaliar(a, sr, frase, minimo=0.5)
        sem = O.semelhanca(frase, O.texto(O.ouvir(a, sr, idioma)), idioma) if ouvir else None
        if sem is not None and sem < SEMELHANCA_MIN:
            problemas.append(f"o Whisper ouviu {sem:.0%} do texto")
        t = O.tom(a, sr)
        nota += len(problemas) + 4.0 * max(0.0, 0.97 - (1.0 if sem is None else sem)) - 0.3 * min(t["dp"], 4.0)
        if melhor is None or nota < melhor["nota"]:
            melhor = {"a": a, "sr": sr, "nota": nota, "sem": sem, "dp": t["dp"], "problemas": problemas}
        if not problemas and (t["dp"] >= ALVO_TOM or tentativa >= 1):
            break
        motivo = "; ".join(problemas) or f"tom reto ({t['dp']:.1f} st)"
        _log(f"   frase refeita ({motivo})")
    melhor["tentativas"] = tentativa + 1
    return melhor


def narrar_natural(r, cfg, idioma, motor, est, tmp, verificar):
    """O ritmo natural (só com o Chatterbox): uma fala por batida, feita de frases com pausas e tom."""
    import random
    import ouvido as O
    h_grav = hashlib.sha1(gravacao_original().read_bytes()).hexdigest()[:12]
    cache = Cache(f"canal-narracao-{r['slug']}")
    if int(os.environ.get("VOZ_FALAS") or 0):
        r["batidas"] = r["batidas"][:int(os.environ["VOZ_FALAS"])]
    tons = [b.get("tom") or "narra" for b in r["batidas"]]
    ruins = sorted({t for t in tons if t not in TONS_DO_ROTEIRO})
    if ruins:
        sys.exit(f"tom desconhecido: {', '.join(ruins)} (há {', '.join(TONS_DO_ROTEIRO)})")
    chaves = [chave_natural(motor, h_grav, idioma, t, falado_de(r, b, idioma)) for b, t in zip(r["batidas"], tons)]
    if verificar:
        faltam = [i for i, k in enumerate(chaves) if f"{k}.wav" not in cache.ativos]
        _log(f"ritmo natural: faltam {len(faltam)} de {len(chaves)} falas")
        sys.exit(10 if faltam else 0)
    _log(f"voz {motor}, ritmo natural (frases com pausas e tom por batida)")
    gerar, ouvir, relatorio, novas, t_ini = None, False, [], 0, time.time()
    realce = float(os.environ.get("VOZ_REALCE") or cfg.get("realce") or 0)

    def realcar(i, destino, tom_b):
        if not realce:
            return
        try:
            antes, depois, k = realcar_arquivo(destino, realce, tom_b)
            _log(f"[{i:02d}] tom realçado: {antes:.1f} → {depois:.1f} st ({k:.2f}×)")
        except ImportError as ex:                            # sem o Praat nesta máquina: segue sem o realce
            _log(f"[{i:02d}] sem realce do tom ({ex.name} não instalado)")

    for i, (b, tom_b, chave) in enumerate(zip(r["batidas"], tons, chaves)):
        destino = tmp / f"b{i:02d}.wav"
        if cache.baixar(chave, destino):
            _log(f"[{i:02d}] guardada")
            realcar(i, destino, tom_b)
            continue
        if gerar is None:
            preparar_tons(est, tmp / "ref")
            ouvir = O.disponivel()
            gerar = carregar_chatterbox()
        falado = falado_de(r, b, idioma)
        frases = dividir_frases(falado)
        rng = random.Random(1000 * i + 7)
        t0, pedacos, medidas, sr = time.time(), [], [], 24000
        for k, fr in enumerate(frases):
            tom_f = tom_da_frase(fr, tom_b)
            m = melhor_frase(gerar, fr, tom_f, 1000 * i + 10 * k, est, idioma, ouvir)
            sr = m["sr"]
            pedacos.append(m["a"])
            pausa = pausa_depois(fr, est["pausas"]["frase"], rng) if k < len(frases) - 1 else 0.0
            if pausa:
                pedacos.append(np.zeros(int(sr * pausa), np.float32))
            medidas.append({"tom": tom_f, "s": round(len(m["a"]) / sr, 2), "pausa": round(pausa + 2 * FOLGA, 2) if pausa else 0,
                            "semelhanca": None if m["sem"] is None else round(m["sem"], 3), "dp": m["dp"],
                            "tentativas": m["tentativas"], "problemas": m["problemas"]})
        a = np.concatenate(pedacos)
        fala_s = sum(x["s"] for x in medidas)
        razao = fala_s / max(1.0, len(falado) / LETRAS_POR_SEGUNDO)
        tempo = TONS[tom_b].get("tempo", 1.0)
        if razao < RAPIDA:                                   # ainda corrida: desacelera a fala inteira
            tempo *= max(0.85, razao)
            _log(f"[{i:02d}] desacelerada para {tempo:.2f}×")
        finalizar(a, sr, destino, tempo)
        cache.subir(chave, destino)                          # o cache guarda a fala sem o realce
        realcar(i, destino, tom_b)
        novas += 1
        relatorio.append({"batida": i, "tom": tom_b, "frases": medidas, "tempo": round(tempo, 3)})
        dps = ", ".join(f"{x['dp']:.1f}" for x in medidas)
        _log(f"[{i:02d}] {len(a) / sr:.1f}s ({len(frases)} frases, tom {dps} st) em {time.time() - t0:.0f}s")
    if relatorio:
        arq = tmp.parent / "voz-relatorio.json"
        antigo = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
        arq.write_text(json.dumps(antigo + relatorio, ensure_ascii=False, indent=1), encoding="utf-8")
    _log(f"pronto: {len(chaves)} falas ({novas} novas) em {(time.time() - t_ini) / 60:.0f} min")


def main():
    roteiro, idioma, saida = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    verificar = "--verificar" in sys.argv[4:]
    r = json.loads(roteiro.read_text(encoding="utf-8"))
    cfg = r.get("voz") or {}
    motor = cfg.get(idioma)
    if cfg.get("motor") != "clone" or motor not in MOTORES:
        sys.exit(f"o roteiro não usa voz clonada em {idioma} (voz: {cfg})")
    tmp = saida / r["slug"] / idioma / "_tmp"
    ref = tmp / "ref"
    ref.mkdir(parents=True, exist_ok=True)
    VC.preparar(ref)
    est = json.loads((ref / "estado.json").read_text(encoding="utf-8"))
    if cfg.get("ritmo") == "natural" and motor == "chatterbox":
        narrar_natural(r, cfg, idioma, motor, est, tmp, verificar)
        return
    if (os.environ.get("VOZ_ESTILO") or cfg.get("estilo")) == "viva":
        est["ref_curta"] = trecho_vivo(est["ref_longa"], ref / "ref-viva.wav")
    if (os.environ.get("VOZ_ESTILO") or cfg.get("estilo")) == "solta":
        est["ref_curta"] = animar(est["ref_curta"], ref / "ref-solta.wav")
    h_ref = hashlib.sha1(Path(est["ref_curta"]).read_bytes()).hexdigest()[:12]
    cache = Cache(f"canal-narracao-{r['slug']}")
    estilo = os.environ.get("VOZ_ESTILO") or cfg.get("estilo") or "calma"
    if estilo not in ESTILOS:
        sys.exit(f"estilo de voz desconhecido: {estilo} (há {', '.join(ESTILOS)})")
    if int(os.environ.get("VOZ_FALAS") or 0):
        r["batidas"] = r["batidas"][:int(os.environ["VOZ_FALAS"])]
    marca = "" if estilo == "calma" else f"{estilo}|"          # calma: a mesma chave de antes (as falas guardadas valem)
    _log(f"voz {motor}, estilo {estilo}")
    gerar, t_ini, novas = None, time.time(), 0
    refazer = bool(os.environ.get("VOZ_REFAZER_RAPIDAS")) and motor != "edge"
    if verificar and refazer:                                # vai medir as guardadas e pode precisar refazer
        sys.exit(10)
    if verificar:                                            # 0 = tudo guardado; 10 = falta gerar alguma fala
        faltam = [i for i, b in enumerate(r["batidas"]) if f"{hashlib.sha1(f'{VERSAO}|{motor}|{h_ref}|{idioma}|{marca}{falado_de(r, b, idioma)}'.encode()).hexdigest()[:16]}.wav" not in cache.ativos]
        _log(f"faltam {len(faltam)} de {len(r['batidas'])} falas")
        sys.exit(10 if faltam else 0)
    for i, b in enumerate(r["batidas"]):
        falado = falado_de(r, b, idioma)
        chave = hashlib.sha1(f"{VERSAO}|{motor}|{h_ref}|{idioma}|{marca}{falado}".encode()).hexdigest()[:16]
        destino = tmp / f"b{i:02d}.wav"
        if cache.baixar(chave, destino):
            if not refazer:
                _log(f"[{i:02d}] guardada")
                continue
            import soundfile as sf
            a0, sr0 = sf.read(str(destino), dtype="float32")
            razao0 = (len(a0) / sr0) / max(1.0, len(falado) / LETRAS_POR_SEGUNDO)
            if razao0 >= RAPIDA:
                _log(f"[{i:02d}] guardada")
                continue
            _log(f"[{i:02d}] guardada, mas rápida demais ({razao0:.2f} do tempo esperado): refazendo")
        if gerar is None:
            gerar = carregar(motor, est, idioma, estilo)
        t0, melhor = time.time(), None
        for tentativa in range(3):
            a, sr = gerar(falado, 1000 * i + tentativa + (500 if refazer else 0))
            a = aparar(a, sr)
            problemas, nota = avaliar(a, sr, falado)
            if melhor is None or nota < melhor[0]:
                melhor = (nota, a, sr)
            if not problemas:
                break
            _log(f"[{i:02d}] refazendo ({'; '.join(problemas)})")
        tempo = TEMPO.get(estilo, 1.0)
        razao = (len(melhor[1]) / melhor[2]) / max(1.0, len(falado) / LETRAS_POR_SEGUNDO)
        if motor != "edge" and razao < RAPIDA:                 # ainda rápida: desacelera até o ritmo normal, sem mudar o tom
            tempo *= max(0.8, razao / 1.0)
            _log(f"[{i:02d}] desacelerada para {tempo:.2f}×")
        finalizar(melhor[1], melhor[2], destino, tempo)
        cache.subir(chave, destino)
        novas += 1
        texto_log = "" if os.environ.get("CANAL_PUBLICO") else f": {falado[:70]}"   # registro público: sem o texto
        _log(f"[{i:02d}] {len(melhor[1]) / melhor[2]:.1f}s de fala em {time.time() - t0:.0f}s{texto_log}")
    _log(f"pronto: {len(r['batidas'])} falas ({novas} novas) em {(time.time() - t_ini) / 60:.0f} min")


if __name__ == "__main__":
    main()
