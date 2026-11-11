"""O ouvido da fábrica (10/11/2026, ideia do dono do canal): o Whisper ouve e mede a voz clonada. Não cria nada.

O Whisper é o modelo aberto de reconhecimento de fala da OpenAI (licença MIT); aqui na versão faster-whisper, que roda
rápido no processador do GitHub. Ele entra em três lugares:

- semelhanca(): o quanto o que ele ouviu bate com o texto (1 = igual). A voz clonada às vezes engole palavra, repete
  ou embola, principalmente com mais emoção; a fábrica descarta essa tentativa e gera de novo.
- tom(): o quanto a voz sobe e desce (desvio do tom em semitons, medido pelo Praat). Fala monótona fica perto de
  1,5; narração viva passa de 2,5. Entre as tentativas certas, fica a mais viva.
- frases_da_gravacao(): as frases da gravação do dono com o tempo, o tom, o ritmo e a pausa depois de cada uma.
  Com isso a fábrica escolhe um trecho de referência para cada tom (pergunta, suspense, narração viva) e copia o
  tamanho das pausas que ele faz quando lê.

Precisa de: pip install faster-whisper praat-parselmouth (sem eles, a fábrica segue sem conferir).
O modelo (OUVIDO_MODELO, padrão "small", ~0,5 GB) vem do Hugging Face na primeira vez.
"""
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

MODELO = os.environ.get("OUVIDO_MODELO", "small")
_modelo = None


def disponivel():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _carregar():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        _modelo = WhisperModel(MODELO, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 2)
    return _modelo


def para_16k(a, sr):
    """Mono float32 a 16 kHz (o que o Whisper espera)."""
    a = np.asarray(a, np.float32)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr == 16000:
        return a
    try:
        import torch
        import torchaudio.functional as AF
        return AF.resample(torch.from_numpy(a), sr, 16000).numpy().astype(np.float32)
    except Exception:  # noqa: BLE001  sem torch: média em blocos + interpolação (bom o bastante para reconhecer fala)
        k = max(1, int(round(sr / 16000)))
        if k > 1:
            a = np.convolve(a, np.ones(k, np.float32) / k, mode="same")
        n = int(len(a) * 16000 / sr)
        return np.interp(np.arange(n) * sr / 16000, np.arange(len(a)), a).astype(np.float32)


def ouvir(a, sr, idioma):
    """Palavras ouvidas: [{"w", "t0", "t1", "p"}] (segundos a partir do começo do áudio; p = confiança)."""
    m = _carregar()
    segs, _ = m.transcribe(para_16k(a, sr), language=idioma, beam_size=5, word_timestamps=True,
                           temperature=0.0, condition_on_previous_text=False, vad_filter=False)
    out = []
    for s in segs:
        for w in s.words or []:
            if w.word.strip():
                out.append({"w": w.word.strip(), "t0": float(w.start), "t1": float(w.end), "p": float(w.probability)})
    return out


def texto(palavras):
    return " ".join(p["w"] for p in palavras)


def normalizar(txt, idioma):
    """Minúsculas, sem acento nem pontuação, números por extenso (o Whisper às vezes escreve "1628")."""
    try:
        import voz as V
        txt = V.por_extenso(txt, idioma)
    except Exception:  # noqa: BLE001
        pass
    txt = unicodedata.normalize("NFD", txt.lower())
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", txt).split())


def semelhanca(esperado, ouvido, idioma):
    """0 a 1, letra a letra (tolera nome estrangeiro escrito de outro jeito; cai com palavra faltando, sobrando ou
    trocada)."""
    a, b = normalizar(esperado, idioma), normalizar(ouvido, idioma)
    if not a:
        return 1.0
    if not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def _f0(a, sr):
    """Tom (Hz) a cada 10 ms; 0 onde não há voz. Praat se tiver; senão, autocorrelação simples."""
    a = np.asarray(a, np.float64).reshape(-1)
    try:
        import parselmouth
        p = parselmouth.Sound(a, sampling_frequency=sr).to_pitch_ac(time_step=0.01, pitch_floor=65.0, pitch_ceiling=420.0)
        return np.asarray(p.selected_array["frequency"], np.float64)
    except ImportError:
        pass
    q = int(sr * 0.04)
    passo = int(sr * 0.01)
    lo, hi = int(sr / 420), int(sr / 65)
    pico = float(np.percentile(np.abs(a), 99)) or 1.0
    f0 = []
    for i in range(0, max(0, len(a) - q), passo):
        x = a[i:i + q] - a[i:i + q].mean()
        if float(np.sqrt(np.mean(x ** 2))) < 0.03 * pico:
            f0.append(0.0)
            continue
        c = np.correlate(x, x, "full")[q - 1:]
        k = lo + int(np.argmax(c[lo:hi]))
        f0.append(sr / k if c[k] > 0.35 * c[0] else 0.0)
    return np.asarray(f0, np.float64)


def tom(a, sr):
    """Quanto a voz varia: {"dp": desvio do tom em semitons, "faixa": p90 - p10 em semitons, "hz": tom mediano,
    "voz": fração do tempo com voz}."""
    f0 = _f0(a, sr)
    v = f0[f0 > 0]
    if len(v) < 15:
        return {"dp": 0.0, "faixa": 0.0, "hz": 0.0, "voz": 0.0}
    st = 12 * np.log2(v / np.median(v))
    st = st[np.abs(st) < 9]                           # pulos de oitava do detector não contam
    if len(st) < 15:
        return {"dp": 0.0, "faixa": 0.0, "hz": float(np.median(v)), "voz": 0.0}
    return {"dp": round(float(np.std(st)), 2), "faixa": round(float(np.percentile(st, 90) - np.percentile(st, 10)), 2),
            "hz": round(float(np.median(v)), 1), "voz": round(len(v) / max(1, len(f0)), 2)}


def _silencio(a, sr, t0, t1):
    """O maior trecho sem fala entre t0 e t1 (segundos): (início, fim). Envelope de 10 ms, limiar relativo."""
    passo = max(1, int(sr * 0.01))
    i0, i1 = max(0, int(t0 * sr)), min(len(a), int(t1 * sr))
    x = a[i0:i1]
    n = len(x) // passo
    if n < 2:
        return t0, t0
    env = np.sqrt((x[:n * passo].reshape(n, passo) ** 2).mean(axis=1) + 1e-12)
    ref = float(np.percentile(np.abs(a), 95)) or 1.0
    baixo = env < 0.06 * ref
    melhor, ini, atual = (0, 0), None, 0
    for k, b in enumerate(list(baixo) + [False]):
        if b:
            ini = k if ini is None else ini
        elif ini is not None:
            if k - ini > melhor[1] - melhor[0]:
                melhor = (ini, k)
            ini = None
    return t0 + melhor[0] * 0.01, t0 + melhor[1] * 0.01


def frases_da_gravacao(wav, idioma="pt"):
    """As frases da gravação: [{"t0", "t1", "pergunta", "letras_s", "pausa", "palavras", "dp", "faixa", "hz"}] e as
    pausas depois de vírgula (segundos). O texto de cada frase fica em "texto" (não vai para o registro público)."""
    import soundfile as sf
    a, sr = sf.read(str(wav), dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    ps = ouvir(a, sr, idioma)
    grupos, atual = [], []
    for w in ps:
        atual.append(w)
        if re.search(r"[.?!…]$", w["w"]):
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    frases = []
    for g in grupos:
        t0, t1 = g[0]["t0"], g[-1]["t1"]
        tx = texto(g)
        frases.append({"t0": round(t0, 2), "t1": round(t1, 2), "texto": tx, "pergunta": tx.rstrip().endswith("?"),
                       "palavras": len(g), "letras_s": round(len(re.sub(r"\W", "", tx)) / max(0.3, t1 - t0), 2),
                       **tom(a[int(t0 * sr):int(t1 * sr)], sr)})
    for f, g in zip(frases[:-1], frases[1:]):              # a pausa de verdade: o silêncio entre as duas frases
        s0, s1 = _silencio(a, sr, f["t1"] - 0.25, g["t0"] + 0.25)
        f["pausa"] = round(max(0.0, s1 - s0), 2)
        f["corte"] = round((s0 + s1) / 2, 2)               # meio do silêncio: bom lugar para cortar a gravação
    virgulas = []
    for w, prox in zip(ps[:-1], ps[1:]):
        if w["w"].endswith(","):
            s0, s1 = _silencio(a, sr, w["t1"] - 0.2, prox["t0"] + 0.2)
            virgulas.append(round(max(0.0, s1 - s0), 2))
    return frases, virgulas, len(a) / sr


PROMPT_S = 6.0      # o Chatterbox tira o jeito de falar (o "prompt" do T3) só dos primeiros 6 s da referência


def escolher_referencias(frases, dur_total, minimo=5.0, maximo=10.0):
    """Trechos da gravação para cada tom, de frases inteiras (cortados no meio dos silêncios). O Chatterbox só copia
    o jeito de falar dos primeiros 6 s da referência, então as frases que dão o tom precisam estar ali:
    viva (o tom que mais sobe e desce), pergunta (uma pergunta nos primeiros 6 s) e tensa (a leitura mais lenta).
    Devolve {tom: {"ini", "fim", "dp", "letras_s", "de", "ate"}}."""
    def corte_antes(i):
        return frases[i - 1]["corte"] if i > 0 and "corte" in frases[i - 1] else max(0.0, frases[i]["t0"] - 0.15)

    def corte_depois(j):
        return frases[j]["corte"] if "corte" in frases[j] else min(dur_total, frases[j]["t1"] + 0.3)

    janelas = []
    for i in range(len(frases)):
        a = corte_antes(i)
        for j in range(i, len(frases)):
            b = corte_depois(j)
            if b - a > maximo:
                break
            if b - a < minimo:
                continue
            no_prompt = [x for x in frases[i:j + 1] if x["t0"] < a + PROMPT_S - 0.5]
            pal = sum(x["palavras"] for x in no_prompt) or 1
            janelas.append({"ini": round(a, 2), "fim": round(b, 2),
                            "dp": round(sum(x["dp"] * x["palavras"] for x in no_prompt) / pal, 2),
                            "letras_s": round(sum(x["letras_s"] * x["palavras"] for x in no_prompt) / pal, 2),
                            "pergunta": any(x["pergunta"] and x["t1"] <= a + PROMPT_S + 0.3 for x in no_prompt),
                            "de": i, "ate": j})
    if not janelas:
        return {}
    out = {"viva": max(janelas, key=lambda w: (w["dp"], -w["ini"])),
           "tensa": min(janelas, key=lambda w: (w["letras_s"], w["ini"]))}
    perg = [w for w in janelas if w["pergunta"]]
    if perg:
        out["pergunta"] = max(perg, key=lambda w: (w["dp"], -w["ini"]))
    return out


def pausas_da_gravacao(frases, virgulas):
    """Pausa típica (mediana) depois de frase e depois de vírgula, nos limites de uma narração (segundos)."""
    ps = [f["pausa"] for f in frases if f.get("pausa") is not None]
    frase = float(np.median(ps)) if ps else 0.5
    virg = float(np.median(virgulas)) if virgulas else 0.2
    return {"frase": round(min(0.85, max(0.35, frase)), 2), "virgula": round(min(0.4, max(0.1, virg)), 2)}


def cortar(origem, ini, fim, destino):
    """Recorte da gravação (wav mono), com 30 ms de entrada e saída suaves."""
    import soundfile as sf
    a, sr = sf.read(str(origem), dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    x = a[int(ini * sr):int(fim * sr)].copy()
    f = min(len(x) // 2, int(sr * 0.03))
    if f:
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(destino), x, sr, subtype="PCM_16")
    return str(destino)
