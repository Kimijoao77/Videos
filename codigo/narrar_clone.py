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


def avaliar(a, sr, texto):
    """Problemas da fala gerada (duração fora do esperado, pausa longa demais) e uma nota (menor = melhor)."""
    dur = len(a) / sr
    esperado = max(1.0, len(texto) / LETRAS_POR_SEGUNDO)
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
