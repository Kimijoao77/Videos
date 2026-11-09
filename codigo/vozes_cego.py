"""Teste cego de vozes: o mesmo trecho do Roanoke em várias vozes pagas/boas (Google Chirp 3 HD e ElevenLabs, as que
tiverem chave), embaralhadas e numeradas. O vídeo e os mp3 mostram só o número; o mapa número → voz fica em
mapa.json (para o Claude saber qual foi a escolhida).

Uso: python canal/vozes_cego.py PASTA
Segredos: GOOGLE_TTS_KEY e/ou ELEVENLABS_API_KEY (motor sem chave é pulado).
Sai: PASTA/cego-pt.mp4, PASTA/cego-en.mp4, PASTA/pt-01.mp3 …, PASTA/mapa.json
"""
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import voz as V  # noqa: E402

FONTES = Path(__file__).parent / "fontes"
TEXTO = {
    "pt": "Em agosto de 1590, um navio inglês chegou a uma pequena ilha na costa da América do Norte. A bordo estava "
          "John White. Três anos antes, ele tinha deixado ali mais de cem colonos. Mas quando White desembarcou, não "
          "havia ninguém. Nenhuma pessoa. Nenhum corpo. Nenhum sinal de luta.",
    "en": "In August 1590, an English ship reached a small island off the coast of North America. On board was John "
          "White. Three years earlier, he had left more than a hundred colonists there. But when White came ashore, "
          "there was no one. No people. No bodies. No sign of a fight.",
}
GOOGLE = ["Charon", "Orus", "Fenrir", "Iapetus", "Algenib", "Alnilam", "Rasalgethi", "Schedar", "Umbriel", "Enceladus",
          "Kore", "Sulafat"]
NARRACAO = ("narrat", "documentar", "informative", "education", "audiobook", "story", "deep", "authoritative")
API = "https://api.elevenlabs.io/v1"


def _eleven(caminho, metodo="get", **kw):
    import requests
    r = requests.request(metodo, API + caminho, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def _narrador(v):
    rot = " ".join(str(x) for x in (v.get("labels") or {}).values()) + " " + str(v.get("description") or "")
    rot += " " + str(v.get("use_case") or "") + " " + str(v.get("descriptive") or "")
    return any(p in rot.lower() for p in NARRACAO)


def vozes_eleven():
    """Escolhe as vozes da ElevenLabs: prontas com cara de narrador (servem para os dois idiomas) e, para o
    português, as vozes brasileiras mais usadas da biblioteca (adicionadas à conta)."""
    escolha = {"pt": [], "en": []}
    try:
        minhas = _eleven("/voices").get("voices", [])
    except Exception as e:
        print("ElevenLabs: não listou as vozes:", str(e)[:200], flush=True)
        return escolha
    prontas = [v for v in minhas if v.get("category") == "premade"]
    prontas.sort(key=lambda v: (not _narrador(v), (v.get("labels") or {}).get("gender") != "male"))
    for v in prontas[:5]:
        escolha["en"].append((v["voice_id"], v["name"]))
    for v in prontas[:2]:
        escolha["pt"].append((v["voice_id"], v["name"]))
    try:
        lib = _eleven("/shared-voices", params={"language": "pt", "page_size": 100, "sort": "usage_character_count_1y"}).get("voices", [])
    except Exception as e:
        print("ElevenLabs: biblioteca indisponível:", str(e)[:200], flush=True)
        lib = []
    br = [v for v in lib if "bra" in (str(v.get("accent")) + str(v.get("locale"))).lower() and v.get("free_users_allowed", True)]
    br.sort(key=lambda v: (not _narrador(v), v.get("gender") != "male", -(v.get("usage_character_count_1y") or 0)))
    for v in br[:5]:
        try:
            novo = _eleven(f"/voices/add/{v['public_owner_id']}/{v['voice_id']}", "post", json={"new_name": f"teste {v['name']}"[:40]})
            escolha["pt"].append((novo.get("voice_id", v["voice_id"]), f"{v['name']} (biblioteca, {v.get('accent')})"))
        except Exception as e:
            print("ElevenLabs: não deu para adicionar", v.get("name"), str(e)[:160], flush=True)
    return escolha


def cartao(n, arq):
    im = Image.new("RGB", (1280, 720), (24, 22, 30))
    d = ImageDraw.Draw(im)
    d.text((640, 330), str(n), font=ImageFont.truetype(str(FONTES / "Poppins-Black.ttf"), 300), fill=(242, 192, 56), anchor="mm")
    d.text((640, 560), "voz", font=ImageFont.truetype(str(FONTES / "Poppins-Bold.ttf"), 54), fill=(240, 229, 204), anchor="mm")
    im.save(arq)


def main(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    candidatas = {"pt": [], "en": []}
    if os.environ.get("GOOGLE_TTS_KEY"):
        for idi in ("pt", "en"):
            candidatas[idi] += [("google", nome, f"Google Chirp 3 HD {nome}") for nome in GOOGLE]
    if os.environ.get("ELEVENLABS_API_KEY"):
        for idi, lista in vozes_eleven().items():
            candidatas[idi] += [("elevenlabs", vid, f"ElevenLabs {nome}") for vid, nome in lista]
    if not any(candidatas.values()):
        sys.exit("Nenhuma chave de voz encontrada (GOOGLE_TTS_KEY ou ELEVENLABS_API_KEY).")
    mapa = {}
    for idi in ("pt", "en"):
        lista = candidatas[idi][:]
        random.Random(1590 + len(idi)).shuffle(lista)
        partes, n = [], 0
        for motor, voz, rotulo in lista:
            wav = pasta / f"tmp-{idi}-{n + 1:02d}.wav"
            try:
                if motor == "google":
                    V._google(TEXTO[idi], idi, wav, voz)
                else:
                    V._elevenlabs(TEXTO[idi], idi, wav, voz)
            except Exception as e:
                print("falhou", idi, rotulo, str(e)[:200], flush=True)
                continue
            n += 1
            mapa[f"{idi}-{n:02d}"] = {"motor": motor, "voz": voz, "nome": rotulo}
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", pasta / f"{idi}-{n:02d}.mp3"], check=True)
            png = pasta / f"c-{idi}-{n}.png"
            cartao(n, png)
            parte = pasta / f"p-{idi}-{n:02d}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", png, "-i", wav, "-af", "apad=pad_dur=1.0",
                            "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-r", "10", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest", parte], check=True)
            partes.append(parte)
            print("ok", idi, n, flush=True)
        if partes:
            lista_txt = pasta / f"lista-{idi}.txt"
            lista_txt.write_text("".join(f"file '{p.name}'\n" for p in partes))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista_txt, "-c", "copy",
                            pasta / f"cego-{idi}.mp4"], check=True)
    (pasta / "mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1))
    for f in pasta.glob("tmp-*"):
        f.unlink()
    for f in pasta.glob("*.el.mp3"):
        f.unlink()
    for f in pasta.glob("*.g.wav"):
        f.unlink()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
