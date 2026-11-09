"""Sons e trilha feitos por código (sem direitos autorais): efeitos de cinema e uma trilha escura de ficção científica.

Efeitos (mono, float32, 44,1 kHz): whoosh (passagem), impacto (grave com estrondo), subida (tensão que cresce),
tique (relógio), brilho (notas agudas com eco), sumico (sucção + silêncio), queda (grave que desce).
trilha(segundos, eventos) devolve estéreo (N×2) com acordes largos, grave, pulso e brilhos; eventos ajustam a trilha:
  {"tipo": "corte", "t": 3.2, "dur": 1.2}     a trilha some de repente e volta devagar
  {"tipo": "tensao", "t": 5, "ate": 12}         pulso de batida grave nesse trecho
"""
import math

import numpy as np
from numba import njit

SR = 44100


@njit(cache=True, fastmath=True)
def _svf(x, corte, q, modo):
    """Filtro de estado variável com frequência de corte variando no tempo (corte: array em Hz).
    modo 0 = passa-baixa, 1 = passa-banda, 2 = passa-alta."""
    y = np.empty_like(x)
    lp = 0.0
    bp = 0.0
    for n in range(x.shape[0]):
        f = 2.0 * math.sin(math.pi * min(corte[n], SR * 0.22) / SR)
        hp = x[n] - lp - q * bp
        bp += f * hp
        lp += f * bp
        y[n] = lp if modo == 0 else (bp if modo == 1 else hp)
    return y


def _t(seg):
    return np.arange(int(SR * seg), dtype=np.float32) / SR


def _ruido(n, semente):
    return np.random.default_rng(semente).normal(0, 1, n).astype(np.float32)


def _norm(x, pico=0.9):
    m = float(np.abs(x).max()) or 1.0
    return (x / m * pico).astype(np.float32)


def eco(x, seg=1.8, mistura=0.35, semente=3):
    """Reverb simples: convolução com ruído que decai (FFT)."""
    n = int(SR * seg)
    ir = _ruido(n, semente) * np.exp(-np.arange(n, dtype=np.float32) / (SR * seg / 6.5))
    ir[0] = 0
    ir /= np.sqrt((ir ** 2).sum()) or 1
    m = len(x) + n
    tam = 1 << (m - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, tam) * np.fft.rfft(ir, tam), tam)[:m].astype(np.float32)
    seco = np.concatenate([x, np.zeros(n, np.float32)])
    return seco * (1 - mistura) + y * mistura * 3.0


def whoosh(dur=0.7, semente=1, sobe=True):
    t = _t(dur)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    f = (300 + 3200 * (t / dur) ** 1.4) if sobe else (3500 - 3100 * (t / dur) ** 0.7)
    x = _svf(_ruido(len(t), semente), f.astype(np.float32), 0.6, 1) * env
    return _norm(eco(x, 0.9, 0.25), 0.6)


def impacto(dur=2.2, semente=2):
    t = _t(dur)
    f = 32 + 60 * np.exp(-t * 9)
    fase = 2 * np.pi * np.cumsum(f) / SR
    grave = np.sin(fase) * np.exp(-t * 2.2)
    estalo = _svf(_ruido(len(t), semente), (200 + 4000 * np.exp(-t * 18)).astype(np.float32), 0.7, 0) * np.exp(-t * 6)
    x = grave * 0.9 + estalo * 0.6
    return _norm(eco(x.astype(np.float32), 2.4, 0.3), 0.95)


def subida(dur=2.4, semente=4):
    t = _t(dur)
    k = t / dur
    f = (400 + 6000 * k ** 2).astype(np.float32)
    ruido = _svf(_ruido(len(t), semente), f, 0.5, 1) * k ** 2
    tom = np.sin(2 * np.pi * np.cumsum(110 + 330 * k ** 2) / SR) * k ** 3 * 0.35
    x = (ruido + tom).astype(np.float32)
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02), dtype=np.float32)
    return _norm(x, 0.7)


def tique(semente=5):
    t = _t(0.06)
    x = _svf(_ruido(len(t), semente), np.full(len(t), 5000, np.float32), 0.3, 1) * np.exp(-t * 120)
    x += np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90) * 0.5
    return _norm(x.astype(np.float32), 0.5)


def brilho(semente=6, notas=(1318.5, 1760.0, 2637.0)):
    t = _t(1.4)
    x = np.zeros(len(t), np.float32)
    for i, f in enumerate(notas):
        ini = int(SR * 0.07 * i)
        tt = t[: len(t) - ini]
        x[ini:] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3.5) * 0.5).astype(np.float32)
    return _norm(eco(x, 2.5, 0.45), 0.45)


def sumico(dur=1.2, semente=7):
    """Sucção (ruído que desce e some) para quando algo desaparece."""
    t = _t(dur)
    k = t / dur
    f = (5000 * (1 - k) ** 2 + 80).astype(np.float32)
    x = _svf(_ruido(len(t), semente), f, 0.4, 0) * (1 - k) ** 0.5 * np.minimum(1, t / 0.05)
    grave = np.sin(2 * np.pi * np.cumsum(90 * (1 - k) + 25) / SR) * (1 - k) * 0.8
    return _norm((x + grave).astype(np.float32), 0.85)


def queda(dur=1.6, semente=8):
    t = _t(dur)
    f = 70 * np.exp(-t * 1.2) + 22
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.02) * np.exp(-t * 1.4)
    return _norm(x.astype(np.float32), 0.9)


EFEITOS = {"whoosh": whoosh, "impacto": impacto, "subida": subida, "tique": tique, "brilho": brilho,
           "sumico": sumico, "queda": queda}


def efeito(nome, **kw):
    return EFEITOS[nome](**kw)


# ------------------------------------------------------------------ trilha
NOTA = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _hz(nome, oitava):
    return 440.0 * 2 ** ((NOTA[nome] + 12 * (oitava + 1) - 69) / 12)


# ré menor sombrio: Dm(add9) → B♭maj7 → Gm → A (sus4 → A)
ACORDES = [
    [("D", 2), ("A", 2), ("E", 3), ("F", 3), ("A", 3)],
    [("A#", 1), ("F", 2), ("D", 3), ("A", 3)],
    [("G", 1), ("D", 2), ("A#", 2), ("D", 3), ("F", 3)],
    [("A", 1), ("E", 2), ("D", 3), ("E", 3), ("A", 3)],
]


def _pad(f, t, semente):
    """Serra suave (8 harmônicos) com duas vozes desafinadas."""
    rnd = np.random.default_rng(semente)
    x = np.zeros(len(t), np.float32)
    for desaf in (-0.18, 0.21):
        ff = f * 2 ** (desaf / 12)
        fase = rnd.uniform(0, 6.28)
        for h in range(1, 9):
            x += (np.sin(2 * np.pi * ff * h * t + fase * h) / h).astype(np.float32)
    return x


def trilha(segundos, eventos=(), semente=1, dur_acorde=5.0):
    n = int(SR * (segundos + 0.5))
    t = np.arange(n, dtype=np.float32) / SR
    esq = np.zeros(n, np.float32)
    dir_ = np.zeros(n, np.float32)
    passo = int(SR * dur_acorde)
    folga = int(SR * 2.5)
    for i, ini in enumerate(range(0, n, passo)):
        acorde = ACORDES[(i + semente) % len(ACORDES)]
        fim = min(n, ini + passo + folga)
        tt = t[: fim - ini]
        env = np.minimum(1, tt / 1.8) * np.clip((dur_acorde + 2.5 - tt) / 2.5, 0, 1)
        som = np.zeros(len(tt), np.float32)
        for j, (nome, oit) in enumerate(acorde):
            som += _pad(_hz(nome, oit), tt, semente * 31 + i * 7 + j) * (0.9 if j == 0 else 0.55)
        # filtro que abre e fecha devagar (respiração do pad)
        corte = (500 + 900 * (0.5 + 0.5 * np.sin(2 * np.pi * (tt / 9.0 + i * 0.3)))).astype(np.float32)
        som = _svf(som, corte, 0.8, 0) * env
        esq[ini:fim] += som * 0.9
        dir_[ini:fim] += np.roll(som, 300) * 0.9
        raiz = _hz(acorde[0][0], 0)                                  # grave fundo
        g = np.sin(2 * np.pi * raiz * tt) * env * 1.6
        esq[ini:fim] += g
        dir_[ini:fim] += g
    # brilhos agudos esparsos
    rnd = np.random.default_rng(semente + 99)
    for k in range(int(segundos / 2.2)):
        ini = int(SR * (1.0 + k * 2.2 + rnd.uniform(0, 0.8)))
        if ini >= n:
            break
        acorde = ACORDES[(ini // passo + semente) % len(ACORDES)]
        nome, oit = acorde[rnd.integers(1, len(acorde))]
        f = _hz(nome, oit + 3)
        d = min(n - ini, int(SR * 2.0))
        tb = t[:d]
        b = (np.sin(2 * np.pi * f * tb) * np.exp(-tb * 2.2) * 0.35).astype(np.float32)
        (esq if k % 2 else dir_)[ini:ini + d] += b
    # pulso (batida grave) nos trechos de tensão
    pulso = np.zeros(n, np.float32)
    for e in eventos:
        if e.get("tipo") != "tensao":
            continue
        bpm = e.get("bpm", 72)
        a, b = float(e["t"]), float(e.get("ate", e["t"] + 6))
        tk = a
        while tk < b:
            i0 = int(SR * tk)
            d = min(n - i0, int(SR * 0.5))
            if d <= 0:
                break
            tb = t[:d]
            batida = np.sin(2 * np.pi * (45 + 60 * np.exp(-tb * 30)) * tb) * np.exp(-tb * 9)
            pulso[i0:i0 + d] += batida.astype(np.float32) * 2.2
            tk += 60.0 / bpm
    esq += pulso
    dir_ += pulso
    est = np.stack([esq, dir_], 1)
    est = np.stack([eco(est[:, 0], 3.0, 0.4, 11)[:n], eco(est[:, 1], 3.0, 0.4, 12)[:n]], 1)
    # cortes (silêncio súbito e volta devagar) e entrada/saída suaves
    vol = np.minimum(1, t / 1.5) * np.clip((segundos + 0.5 - t) / 2.0, 0, 1)
    for e in eventos:
        if e.get("tipo") != "corte":
            continue
        a, d = float(e["t"]), float(e.get("dur", 1.5))
        k = np.ones(n, np.float32)
        dentro = (t >= a) & (t < a + d)
        k[dentro] = 0.0
        volta = (t >= a + d) & (t < a + d + 2.5)
        k[volta] = ((t[volta] - a - d) / 2.5) ** 2
        vol = vol * k
    est *= vol[:, None]
    return _norm(est, 0.5)
