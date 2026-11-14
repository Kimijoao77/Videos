"""Trilha sonora da Arena dos Reinos, composta aqui em código e tocada com o banco de sons GeneralUser GS
(licença livre para música, inclusive comercial). Gera musica/*.ogg: menu, batalha, tempo extra, vitória e derrota.

Uso: python3 trilha.py CAMINHO/GeneralUser-GS.sf2 PASTA_DE_SAIDA
Cada faixa é escrita como notas (compasso, tempo, duração em tempos, nota MIDI, força) por instrumento; as músicas de
fundo saem em laço perfeito (o eco do fim continua no começo)."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import tinysoundfont

SR = 44100
NOTA = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}
NOTA.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})


def m(nome):
    """'D5' → 74 (dó central = C4 = 60)."""
    n, o = nome[:-1], int(nome[-1])
    return 12 * (o + 1) + NOTA[n]


# acordes (fundamental, terça, quinta) em nomes
ACORDES = {
    "Dm": ("D", "F", "A"), "C": ("C", "E", "G"), "Bb": ("A#", "D", "F"), "F": ("F", "A", "C"), "A": ("A", "C#", "E"),
    "Am": ("A", "C", "E"), "Gm": ("G", "A#", "D"), "G": ("G", "B", "D"), "D": ("D", "F#", "A"), "Em": ("E", "G", "B"),
}


def notas_acorde(ac, oit):
    r, t, q = ACORDES[ac]
    base = 12 * (oit + 1) + NOTA[r]
    return [base, base + (NOTA[t] - NOTA[r]) % 12, base + (NOTA[q] - NOTA[r]) % 12]


class Faixa:
    def __init__(self, bpm, compassos):
        self.bpm, self.compassos = bpm, compassos
        self.trilhas = {}                       # canal → (banco, programa, [(início em tempos, duração, nota, força)])

    def instr(self, canal, programa, banco=0):
        self.trilhas.setdefault(canal, (banco, programa, []))
        return self.trilhas[canal][2]

    def nota(self, canal, comp, tempo, dur, nota, forca=90):
        self.trilhas[canal][2].append((comp * 4 + tempo, dur, nota if isinstance(nota, int) else m(nota), forca))

    def melodia(self, canal, comp, frase, forca=92, oit=0):
        """frase: [(nota ou None para pausa, duração)] seguidas a partir do compasso."""
        t = 0.0
        for n, d in frase:
            if n:
                self.nota(canal, comp + int(t // 4), t % 4, d * 0.96, m(n) + 12 * oit, forca)
            t += d

    @property
    def segundos(self):
        return self.compassos * 4 * 60 / self.bpm


def tocar(faixa, sf, laco=True, cauda=2.5):
    """Toca a faixa no sintetizador e devolve o áudio estéreo (float32). Em laço, toca duas vezes e fica com a segunda."""
    syn = tinysoundfont.Synth(samplerate=SR, gain=-3)
    sfid = syn.sfload(str(sf))
    for canal, (banco, prog, _) in faixa.trilhas.items():
        syn.program_select(canal, sfid, banco, prog, is_drums=(canal == 9))
        syn.control_change(canal, 91, 0)
    seg_tempo = 60 / faixa.bpm
    voltas = 2 if laco else 1
    evs = []
    for v in range(voltas):
        desloc = v * faixa.compassos * 4
        for canal, (_, _, ns) in faixa.trilhas.items():
            for ini, dur, nota, forca in ns:
                evs.append(((ini + desloc) * seg_tempo, 1, canal, nota, forca))
                evs.append(((ini + desloc + dur) * seg_tempo, 0, canal, nota, 0))
    evs.sort(key=lambda e: (e[0], e[1]))
    total = int((voltas * faixa.segundos + cauda) * SR)
    out = np.zeros((total, 2), dtype=np.float32)
    pos = 0
    for t, liga, canal, nota, forca in evs:
        alvo = min(total, int(t * SR))
        if alvo > pos:
            buf = np.frombuffer(syn.generate(alvo - pos), dtype=np.float32).reshape(-1, 2)
            out[pos:pos + len(buf)] = buf
            pos += len(buf)
        if liga:
            syn.noteon(canal, nota, forca)
        else:
            syn.noteoff(canal, nota)
    if pos < total:
        buf = np.frombuffer(syn.generate(total - pos), dtype=np.float32).reshape(-1, 2)
        out[pos:pos + len(buf)] = buf
    return out


def eco(x, seg=1.8, mistura=0.2, semente=1):
    """Reverberação simples: convolução com ruído que morre aos poucos (um para cada lado)."""
    r = np.random.default_rng(semente)
    n = int(seg * SR)
    env = np.exp(-np.linspace(0, 7, n)).astype(np.float32)
    saida = x.copy()
    for c in range(2):
        ir = r.standard_normal(n).astype(np.float32) * env
        ir[: int(0.012 * SR)] = 0                     # pré-atraso
        ir /= np.sqrt((ir ** 2).sum())
        tam = 1 << int(np.ceil(np.log2(len(x) + n)))
        y = np.fft.irfft(np.fft.rfft(x[:, c], tam) * np.fft.rfft(ir, tam), tam)[: len(x)]
        saida[:, c] = x[:, c] * (1 - mistura) + y.astype(np.float32) * mistura * 2.2
    return saida


def salvar(x, caminho, laco_seg=None, q=5):
    if laco_seg:                                  # fica com a segunda volta (já com o eco da primeira no começo)
        n = int(round(laco_seg * SR))
        x = x[n: 2 * n]
    x = x / max(1e-6, np.abs(x).max()) * 0.89
    if not laco_seg:                              # vinheta: some no fim
        f = int(0.25 * SR)
        x[-f:] *= np.linspace(1, 0, f)[:, None]
    wav = caminho.with_suffix(".wav")
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis", "-q:a", str(q), str(caminho)], check=True)
    wav.unlink()
    print(caminho.name, f"{len(x) / SR:.1f}s", f"{caminho.stat().st_size // 1024} KB")


# ------------------------------------------------------------------ instrumentos (General MIDI)
HARPA, CORDAS, CORDAS2, PIZZ, FLAUTA, FLAUTIM, OBOE, TROMPA, TROMPETE, METAIS, TUBA, CORO, TIMPANO, CONTRABAIXO, ALAUDE, CELESTA, SINO = \
    46, 48, 49, 45, 73, 72, 68, 60, 56, 61, 58, 52, 47, 43, 24, 8, 14
# bateria (canal 9): bumbo, caixa, prato, tom grave, tom agudo, pandeiro, chimbal
BUMBO, CAIXA, PRATO, TOM_G, TOM_A, PANDEIRO, CHIMBAL, RUFO = 36, 38, 49, 41, 47, 54, 42, 40


def menu():
    """Salão do Rei: ré dórico, 96 bpm, harpa dedilhada, cordas, flauta e um tambor de mão. 32 compassos (80 s)."""
    f = Faixa(96, 32)
    for c, p in ((0, HARPA), (1, CORDAS), (2, FLAUTA), (3, CONTRABAIXO), (4, OBOE), (5, CELESTA), (9, 0)):
        f.instr(c, p, 128 if c == 9 else 0)
    A = ["Dm", "Dm", "C", "C", "Bb", "F", "Gm", "A", "Dm", "Dm", "C", "C", "Bb", "C", "Dm", "Dm"]
    B = ["F", "C", "Dm", "Am", "Bb", "F", "Gm", "A", "F", "C", "Dm", "Am", "Bb", "C", "Dm", "Dm"]
    for i, ac in enumerate(A + B):
        r, t, q = notas_acorde(ac, 3)
        arp = [r, q, r + 12, t + 12, q + 12, t + 12, r + 12, q]           # harpa em colcheias
        for k, n in enumerate(arp):
            f.nota(0, i, k * 0.5, 0.9, n, 62 if k % 2 else 74)
        for n in notas_acorde(ac, 3)[1:] + [notas_acorde(ac, 2)[0] + 12]:   # cordas: o acorde inteiro, macio
            f.nota(1, i, 0, 3.95, n, 50 if i < 16 else 60)
        f.nota(3, i, 0, 1.9, notas_acorde(ac, 2)[0], 82)
        f.nota(3, i, 2, 1.9, notas_acorde(ac, 2)[0] + (7 if ac not in ("Bb",) else 7), 70)
        # tambor de mão: grave no 1, agudos no 2,5 e 4
        f.nota(9, i, 0, 0.3, TOM_G, 70); f.nota(9, i, 1.5, 0.2, TOM_A, 40); f.nota(9, i, 3, 0.2, TOM_A, 48)
        if i >= 16:
            f.nota(9, i, 1, 0.2, PANDEIRO, 38); f.nota(9, i, 3, 0.2, PANDEIRO, 38)
    M1 = [("D5", 1.5), ("E5", .5), ("F5", 1), ("G5", 1), ("A5", 2), ("G5", 1), ("F5", 1)]
    M2 = [("E5", 1.5), ("F5", .5), ("G5", 1), ("E5", 1), ("C5", 3), (None, 1)]
    M3 = [("F5", 1.5), ("G5", .5), ("F5", 1), ("D5", 1), ("C5", 1), ("D5", 1), ("F5", 2)]
    M4 = [("G5", 1.5), ("F5", .5), ("E5", 1), ("D5", 1), ("C#5", 2), ("E5", 2)]
    M2b = [("E5", 1), ("G5", 1), ("C6", 1), ("G5", 1), ("E5", 2), ("D5", 1), ("C5", 1)]
    M5 = [("D5", 1), ("F5", 1), ("G5", 1), ("A5", 1), ("G5", 1.5), ("F5", .5), ("E5", 1), ("C#5", 1), ("D5", 4), (None, 4)]
    f.melodia(2, 0, M1 + M2 + M3 + M4 + M1 + M2b + M5)
    B1 = [("A5", 1.5), ("C6", .5), ("A5", 1), ("F5", 1), ("G5", 2), ("E5", 2)]
    B2 = [("F5", 1.5), ("G5", .5), ("A5", 1), ("D5", 1), ("E5", 3), (None, 1)]
    B3 = [("F5", 1), ("G5", 1), ("A5", 1), ("A#5", 1), ("A5", 2), ("F5", 2)]
    B4 = [("G5", 1.5), ("A5", .5), ("A#5", 1), ("G5", 1), ("A5", 2), ("C#5", 2)]
    B6 = [("F5", 1), ("E5", 1), ("D5", 1), ("F5", 1), ("E5", 3), (None, 1)]
    B7 = [("D5", 1), ("F5", 1), ("G5", 1), ("A5", 1), ("G5", 1.5), ("F5", .5), ("E5", 2), ("D5", 4), (None, 4)]
    f.melodia(2, 16, B1 + B2 + B3 + B4 + B1 + B6 + B7)
    f.melodia(4, 16, [(n and n[:-1] + str(int(n[-1]) - 1), d) for n, d in B1 + B2], forca=58)   # oboé em contracanto
    for i in (7, 15, 23, 31):                     # celesta brilha no fim das frases
        for k, n in enumerate(["A5", "D6", "F6", "A6"]):
            f.nota(5, i, 2 + k * 0.5, 1.5, n, 50)
    return f


def batalha():
    """Campo de Batalha: ré menor, 132 bpm, cordas em ostinato, trompas na melodia, tímpanos e bateria. 32 compassos."""
    f = Faixa(132, 32)
    for c, p in ((0, CORDAS2), (1, TROMPA), (2, TROMPETE), (3, CONTRABAIXO), (4, TIMPANO), (5, CORO), (6, PIZZ), (9, 0)):
        f.instr(c, p, 128 if c == 9 else 0)
    P = ["Dm", "Dm", "Bb", "C", "Dm", "Dm", "Bb", "A", "Dm", "F", "C", "Bb", "Gm", "Bb", "A", "A"]
    for i, ac in enumerate(P + P):
        r, t, q = notas_acorde(ac, 3)
        osti = [r, r, q, r, r, q, t + 12, q]                                # cordas em colcheias curtas
        for k, n in enumerate(osti):
            f.nota(0, i, k * 0.5, 0.42, n, 96 if k in (0, 3, 6) else 74)
            f.nota(6, i, k * 0.5, 0.3, n - 12, 70)
        f.nota(3, i, 0, 0.9, notas_acorde(ac, 2)[0], 100); f.nota(3, i, 1.5, 0.45, notas_acorde(ac, 2)[0], 86)
        f.nota(3, i, 2, 0.9, notas_acorde(ac, 2)[0], 96); f.nota(3, i, 3.5, 0.45, notas_acorde(ac, 2)[2], 86)
        f.nota(4, i, 0, 0.6, notas_acorde(ac, 2)[0], 104); f.nota(4, i, 2, 0.6, notas_acorde(ac, 2)[2] - 12, 90)
        # bateria: bumbo no 1 e no 2,5, caixa no 2 e 4, chimbal em colcheias
        for b in (0, 1.5, 2.5):
            f.nota(9, i, b, 0.2, BUMBO, 104 if b == 0 else 84)
        for b in (1, 3):
            f.nota(9, i, b, 0.2, CAIXA, 92)
        for k in range(8):
            f.nota(9, i, k * 0.5, 0.1, CHIMBAL, 50 if k % 2 else 64)
        if i % 8 == 0:
            f.nota(9, i, 0, 1, PRATO, 100)
        if i % 8 == 7:                                                       # virada nos toms
            for k, n in enumerate([TOM_A, TOM_A, TOM_G, TOM_G]):
                f.nota(9, i, 2 + k * 0.5, 0.2, n, 96)
        if i >= 16:
            for n in notas_acorde(ac, 4):
                f.nota(5, i, 0, 3.9, n, 58)
    H1 = [("D4", .75), ("D4", .25), ("A4", 1), ("G4", .5), ("F4", .5), ("E4", 1), ("F4", 1.5), ("E4", .5), ("D4", 2)]
    H2 = [("D4", .75), ("D4", .25), ("F4", 1), ("A#4", 1), ("A4", 1), ("G4", 1.5), ("A4", .5), ("G4", 1), ("E4", 1)]
    H3 = [("A4", .75), ("A4", .25), ("D5", 1), ("C5", .5), ("A#4", .5), ("A4", 1), ("A#4", 1.5), ("A4", .5), ("G4", 2)]
    H4 = [("F4", 1), ("G4", 1), ("A4", 1), ("A#4", 1), ("A4", 2), ("C#5", 2)]
    f.melodia(1, 0, H1 + H2 + H3 + H4, forca=100)
    H5 = [("D5", 1.5), ("C5", .5), ("A4", 1), ("F4", 1), ("A4", 1.5), ("G4", .5), ("F4", 2)]
    H6 = [("E4", 1), ("G4", 1), ("C5", 1.5), ("A#4", .5), ("A4", 2), ("F4", 2)]
    H7 = [("G4", 1), ("A#4", 1), ("D5", 1.5), ("C5", .5), ("A#4", 1), ("D5", 1), ("C#5", 1), ("E5", 1)]
    H8 = [("D5", 2), ("A4", 1), ("C#5", 1), ("D5", 3), (None, 1)]
    f.melodia(1, 8, H5 + H6 + H7 + H8, forca=104)
    f.melodia(1, 16, H1 + H2 + H3 + H4, forca=104)
    f.melodia(2, 16, [(n and n[:-1] + str(int(n[-1]) + 1), d) for n, d in H1 + H2], forca=70)   # trompete dobrando
    f.melodia(1, 24, H5 + H6 + H7 + H8, forca=108)
    f.melodia(2, 24, H5 + H6 + H7 + H8, forca=78)
    for i in (3, 7, 11, 15, 19, 23, 27, 31):                                 # chamada de trompete no fim das frases
        f.melodia(2, i, [(None, 2), ("A4", 1 / 3), ("A4", 1 / 3), ("A4", 1 / 3), ("D5", 1)], forca=88)
    return f


def extra():
    """Último Minuto (tempo extra / energia em dobro): 150 bpm, mais tambor, coro e metais. 16 compassos."""
    f = Faixa(150, 16)
    for c, p in ((0, CORDAS2), (1, METAIS), (2, TROMPETE), (3, CONTRABAIXO), (4, TIMPANO), (5, CORO), (9, 0)):
        f.instr(c, p, 128 if c == 9 else 0)
    P = ["Dm", "Bb", "C", "A", "Dm", "Bb", "Gm", "A", "Dm", "F", "C", "Bb", "Gm", "Bb", "A", "A"]
    for i, ac in enumerate(P):
        r, t, q = notas_acorde(ac, 3)
        for k in range(16):                                                 # semicolcheias
            n = [r, r + 12, q, r + 12][k % 4]
            f.nota(0, i, k * 0.25, 0.22, n, 92 if k % 4 == 0 else 70)
        for b in (0, 1, 2, 3):
            f.nota(3, i, b, 0.45, notas_acorde(ac, 2)[0], 100)
            f.nota(9, i, b, 0.2, BUMBO, 108 if b in (0, 2) else 92)
        for b in (1, 3):
            f.nota(9, i, b, 0.2, CAIXA, 104)
        f.nota(9, i, 3.5, 0.1, CAIXA, 80); f.nota(9, i, 3.75, 0.1, CAIXA, 88)
        f.nota(4, i, 0, 0.4, notas_acorde(ac, 2)[0], 112); f.nota(4, i, 2, 0.4, notas_acorde(ac, 2)[0], 100)
        for n in notas_acorde(ac, 4):
            f.nota(5, i, 0, 3.9, n, 72)
            f.nota(1, i, 0, 0.5, n - 12, 104); f.nota(1, i, 1.5, 0.5, n - 12, 96)  # metais em golpes
        if i % 4 == 0:
            f.nota(9, i, 0, 1, PRATO, 110)
    T = [("D5", 1), ("A4", .5), ("D5", .5), ("F5", 1), ("E5", 1), ("D5", 1.5), ("C5", .5), ("A#4", 1), ("A4", 1),
         ("A#4", 1), ("C5", 1), ("D5", 1), ("E5", 1), ("C#5", 2), ("A4", 2)]
    f.melodia(2, 0, T + T, forca=96)
    f.melodia(2, 8, [("F5", 1.5), ("E5", .5), ("D5", 1), ("A4", 1), ("D5", 1.5), ("C5", .5), ("A#4", 2), ("A4", 1), ("A#4", 1), ("C5", 1),
                     ("D5", 1), ("E5", 2), ("C#5", 2), ("D5", 3), (None, 1), ("A4", 1), ("C#5", 1), ("E5", 1), ("A5", 1)], forca=100)
    return f


def vitoria():
    f = Faixa(110, 3)
    for c, p in ((0, METAIS), (1, TROMPETE), (2, CORDAS), (3, TIMPANO), (4, HARPA), (9, 0)):
        f.instr(c, p, 128 if c == 9 else 0)
    f.melodia(1, 0, [("D5", 1 / 3), ("D5", 1 / 3), ("D5", 1 / 3), ("F#5", 1), ("A5", 1), ("D6", 4.5)], forca=108)
    for n in ("D4", "F#4", "A4", "D5"):
        f.nota(0, 0, 1, 1, n, 96); f.nota(0, 0, 3, 5, n, 100); f.nota(2, 0, 3, 5.5, n, 80)
    f.nota(0, 0, 2, 1, "G4", 96); f.nota(0, 0, 2, 1, "B4", 96)
    for k in range(12):
        f.nota(3, 0, 2.5 + k * 0.125, 0.12, "D2", 70 + k * 3)
    f.nota(3, 0, 4, 2, "D2", 120)
    for k, n in enumerate(["D5", "F#5", "A5", "D6", "F#6", "A6"]):
        f.nota(4, 0, 3 + k * 0.17, 3, n, 70)
    f.nota(9, 0, 3, 2, PRATO, 112)
    return f


def derrota():
    f = Faixa(80, 3)
    for c, p in ((0, CORDAS), (1, OBOE), (2, TIMPANO), (3, CONTRABAIXO)):
        f.instr(c, p)
    f.melodia(1, 0, [("A4", 1), ("F4", 1), ("E4", 1), ("D4", 5)], forca=84)
    for n in ("D3", "F3", "A3"):
        f.nota(0, 0, 0, 2, n, 70)
    for n in ("C3", "E3", "G3"):
        f.nota(0, 0, 2, 1, n, 66)
    for n in ("D3", "F3", "A3", "D4"):
        f.nota(0, 0, 3, 5, n, 72)
    f.nota(3, 0, 0, 8, "D2", 80)
    f.nota(2, 0, 3, 2, "D2", 96)
    return f


if __name__ == "__main__":
    sf, saida = Path(sys.argv[1]), Path(sys.argv[2])
    saida.mkdir(parents=True, exist_ok=True)
    so = set(sys.argv[3:])
    for nome, fn, laco, eco_seg, mist in (("menu", menu, True, 2.2, 0.24), ("batalha", batalha, True, 1.5, 0.16), ("extra", extra, True, 1.3, 0.14),
                                          ("vitoria", vitoria, False, 2.0, 0.22), ("derrota", derrota, False, 2.2, 0.24)):
        if so and nome not in so:
            continue
        f = fn()
        x = eco(tocar(f, sf, laco=laco, cauda=3.0), eco_seg, mist)
        salvar(x, saida / f"{nome}.ogg", laco_seg=f.segundos if laco else None)
