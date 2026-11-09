"""Amostras das vozes Google Chirp 3 HD (precisa do segredo GOOGLE_TTS_KEY), numeradas num vídeo por idioma.

Uso: python canal/vozes_google.py PASTA
Sai: PASTA/vozes-google-pt.mp4, PASTA/vozes-google-en.mp4 (o número e o nome da voz aparecem na tela).
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import voz as V  # noqa: E402

FONTES = Path(__file__).parent / "fontes"
TEXTO = {
    "pt": "Imagina que o Sol some. Agora. Neste segundo. E o mais assustador: por oito minutos e vinte segundos, "
          "você não ia perceber nada.",
    "en": "Imagine the Sun just vanishes. Right now. This second. And here's the scary part: for eight minutes and "
          "twenty seconds, you wouldn't notice a thing.",
}
VOZES = [("Charon", "grave"), ("Fenrir", "firme"), ("Orus", "grave"), ("Puck", "animada"), ("Iapetus", "calma"),
         ("Enceladus", "sussurrada"), ("Algieba", "suave"), ("Sadaltager", "clara"), ("Kore", "feminina"),
         ("Aoede", "feminina"), ("Zephyr", "feminina")]


def cartao(n, titulo, sub, arq):
    im = Image.new("RGB", (1080, 1080), (10, 15, 44))
    d = ImageDraw.Draw(im)
    d.text((540, 380), str(n), font=ImageFont.truetype(str(FONTES / "Unbounded-Black.ttf"), 260), fill=(255, 196, 0), anchor="mm")
    d.text((540, 640), titulo, font=ImageFont.truetype(str(FONTES / "Unbounded-Bold.ttf"), 64), fill=(236, 240, 255), anchor="mm")
    d.text((540, 730), sub, font=ImageFont.truetype(str(FONTES / "Unbounded-Medium.ttf"), 40), fill=(126, 226, 255), anchor="mm")
    im.save(arq)


def main(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    for idioma in ("pt", "en"):
        partes, n = [], 0
        for nome, jeito in VOZES:
            wav = pasta / f"{idioma}-{nome}.wav"
            try:
                V._google(TEXTO[idioma], idioma, wav, nome)
            except Exception as e:
                print("falhou", idioma, nome, str(e)[:200], flush=True)
                continue
            n += 1
            png = pasta / f"c-{idioma}-{n}.png"
            cartao(n, f"Google {nome}", jeito if idioma == "pt" else "Chirp 3 HD", png)
            parte = pasta / f"p-{idioma}-{n:02d}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", png, "-i", wav, "-af", "apad=pad_dur=0.8",
                            "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-r", "10", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest", parte], check=True)
            partes.append(parte)
            print("ok", idioma, n, nome, flush=True)
        if partes:
            lista = pasta / f"lista-{idioma}.txt"
            lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy",
                            pasta / f"vozes-google-{idioma}.mp4"], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "amostras"))
