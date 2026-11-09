"""Trilha de fundo feita por código: um ambiente espacial calmo (acordes suaves, grave e brilhos), sem direitos autorais.

trilha(segundos, saida_wav, semente) grava um WAV estéreo. O volume fica baixo de propósito: gerar.py ainda abaixa
mais quando a voz fala.
"""
import math, wave

import numpy as np

SR = 44100
# lá menor: Am, F, C, G (frequências em Hz da 3ª oitava)
NOTAS = {"A": 220.0, "B": 246.94, "C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23, "G": 392.0}
ACORDES = [("A", "C", "E"), ("F", "A", "C"), ("C", "E", "G"), ("G", "B", "D")]
PROGRESSOES = [[0, 1, 2, 3], [0, 2, 3, 1], [1, 2, 0, 3], [0, 3, 1, 2]]


def _onda(f, t, fase=0.0):
    """Timbre macio: fundamental e dois harmônicos fracos."""
    a = 2 * math.pi * f * t + fase
    return np.sin(a) + 0.28 * np.sin(2 * a) + 0.10 * np.sin(3 * a)


def trilha(segundos, saida, semente=1, dur_acorde=6.0):
    rnd = np.random.default_rng(semente)
    n = int(SR * (segundos + 1.0))
    t = np.arange(n) / SR
    esq, dir_ = np.zeros(n, np.float32), np.zeros(n, np.float32)
    prog = PROGRESSOES[semente % len(PROGRESSOES)]
    passo = int(SR * dur_acorde)
    caixa = np.arange(passo + int(SR * 2)) / SR
    for i, ini in enumerate(range(0, n, passo)):
        acorde = ACORDES[prog[i % len(prog)]]
        fim = min(n, ini + len(caixa))
        tt = caixa[: fim - ini]
        env = np.minimum(1, tt / 2.2) * np.clip((dur_acorde + 2 - tt) / 2.0, 0, 1)    # entra devagar e cruza com o próximo
        for j, nome in enumerate(acorde):
            f = NOTAS[nome] * (0.5 if j == 0 else 1.0)
            for desaf, lado in ((-0.6, 0), (0.7, 1)):                                  # leve desafinação: som largo
                s = _onda(f + desaf, tt, rnd.uniform(0, 6.28)) * env * 0.055
                (esq if lado == 0 else dir_)[ini:fim] += s
        raiz = NOTAS[acorde[0]] / 4                                                     # grave
        g = np.sin(2 * math.pi * raiz * tt) * env * 0.09
        esq[ini:fim] += g; dir_[ini:fim] += g
        for k in range(3):                                                              # brilhos: notas agudas que somem
            ini_b = ini + int(SR * (0.8 + k * 1.9 + rnd.uniform(0, 0.4)))
            if ini_b >= n:
                break
            fb = NOTAS[acorde[rnd.integers(0, 3)]] * 4
            dur_b = min(n - ini_b, int(SR * 2.5))
            tb = np.arange(dur_b) / SR
            b = np.sin(2 * math.pi * fb * tb) * np.exp(-tb * 1.8) * 0.020
            (esq if k % 2 == 0 else dir_)[ini_b:ini_b + dur_b] += b
    # vento espacial: ruído bem filtrado, quase inaudível
    ruido = rnd.normal(size=n).astype(np.float32)
    kernel = np.ones(400, np.float32) / 400
    vento = np.convolve(ruido, kernel, mode="same") * 0.25
    esq += vento; dir_ += np.roll(vento, 2000)
    # entrada e saída suaves
    fade = np.minimum(1, t / 2.0) * np.clip((segundos + 1.0 - t) / 2.5, 0, 1)
    est = np.stack([esq * fade, dir_ * fade], axis=1)
    est = est / max(1e-6, np.abs(est).max()) * 0.32
    with wave.open(str(saida), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((est * 32767).astype(np.int16).tobytes())
    return saida


if __name__ == "__main__":
    import sys
    trilha(float(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else "trilha.wav")
