"""Amostras de voz para o João comparar (pedido de 10/11/2026): o mesmo trecho do Vasa (batidas 0 a 3) em cada voz
grátis que dá para gerar sem conta nova, a voz clonada de hoje (do cache da narração) e as amostras oficiais públicas
do Google (Chirp 3 HD, em inglês, outro texto). Nada de amostra pública de comunidade (Fish Audio, ElevenLabs): lá
muitas vozes são clones de pessoas reais, e não pegamos voz de ninguém. Roda no GitHub (repositório Videos, fluxo amostras-voz.yml) e grava
os mp3 em amostras/, que o fluxo manda para a Release privada amostras-voz do Engfy.

Nada de chave no registro: a do Gemini (GEMINI_KEY) só vai no cabeçalho do pedido.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import narrar_clone as N  # noqa: E402  falado_de: as trocas de pronúncia do roteiro e os números por extenso

ROTEIRO = Path("canal/roteiros/o-naufragio-do-vasa.json")
FALAS = 4                      # batidas 0 a 3: uns 25 segundos
SAIDA = Path("amostras")
EDGE = {"pt": [("microsoft-macerio", "pt-BR-MacerioMultilingualNeural"), ("microsoft-thalita", "pt-BR-ThalitaMultilingualNeural"),
               ("microsoft-antonio", "pt-BR-AntonioNeural")],
        "en": [("microsoft-andrew-multilingual", "en-US-AndrewMultilingualNeural"), ("microsoft-brian-multilingual", "en-US-BrianMultilingualNeural"),
               ("microsoft-ava-multilingual", "en-US-AvaMultilingualNeural"), ("microsoft-andrew-atual", "en-US-AndrewNeural")]}
GEMINI = {"modelos": ["gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview"], "vozes": {"pt": "Charon", "en": "Charon"},
          "estilo": {"pt": "Leia como narrador de documentário de mistério: voz animada e envolvente, ritmo natural e um toque de suspense.",
                     "en": "Read this like a mystery documentary narrator: lively and engaging, natural pace, with a touch of suspense."}}
GOOGLE_DEMOS = ["charon", "orus", "fenrir", "algenib", "iapetus"]
UA = {"User-Agent": "Nexus-amostras/1.0"}


def sh(*a):
    subprocess.run([str(x) for x in a], check=True)


def mp3(origem, destino, *antes):
    sh("ffmpeg", "-y", "-v", "error", *antes, "-i", origem, "-ac", "1", "-ar", "44100", "-b:a", "96k", destino)


def textos():
    r = json.loads(ROTEIRO.read_text(encoding="utf-8"))
    return {i: " ".join(N.falado_de(r, b, i) for b in r["batidas"][:FALAS]) for i in ("pt", "en")}


async def edge(txt):
    import edge_tts
    existem = {v["ShortName"] for v in await edge_tts.list_voices()}
    for idioma, vozes in EDGE.items():
        for nome, voz in vozes:
            if voz not in existem:
                print(f"edge: {voz} não existe mais, pulei")
                continue
            arq = SAIDA / f"{idioma}-{nome}.mp3"
            for tentativa in range(4):                       # o serviço às vezes devolve vazio: tenta de novo
                try:
                    await edge_tts.Communicate(txt[idioma], voz).save(str(arq))
                    if arq.exists() and arq.stat().st_size > 1000:
                        print(f"ok {idioma}-{nome}")
                        break
                except Exception as e:  # noqa: BLE001
                    print(f"edge {voz} (tentativa {tentativa + 1}): {type(e).__name__}")
                arq.unlink(missing_ok=True)
                await asyncio.sleep(5 * (tentativa + 1))


def gemini(txt):
    chave = os.environ.get("GEMINI_KEY", "").strip()
    if not chave:
        print("gemini: sem GEMINI_KEY, pulei")
        return
    for idioma in ("pt", "en"):
        corpo = {"contents": [{"parts": [{"text": f"{GEMINI['estilo'][idioma]}\n\n{txt[idioma]}"}]}],
                 "generationConfig": {"responseModalities": ["AUDIO"],
                                      "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI["vozes"][idioma]}}}}}
        for modelo in GEMINI["modelos"]:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                                         data=json.dumps(corpo).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "x-goog-api-key": chave, **UA})
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    d = json.loads(resp.read())
                parte = d["candidates"][0]["content"]["parts"][0]["inlineData"]
                pcm = SAIDA / f"{idioma}-gemini.pcm"
                pcm.write_bytes(base64.b64decode(parte["data"]))
                taxa = next((p.split("=")[1] for p in parte.get("mimeType", "").split(";") if p.strip().startswith("rate=")), "24000")
                mp3(pcm, SAIDA / f"{idioma}-gemini-{GEMINI['vozes'][idioma].lower()}.mp3", "-f", "s16le", "-ar", taxa, "-ac", "1")
                pcm.unlink()
                print(f"ok {idioma}-gemini ({modelo})")
                break
            except urllib.error.HTTPError as e:
                print(f"gemini {modelo} {idioma}: HTTP {e.code} {e.read()[:160].decode('utf-8', 'replace')}")
            except Exception as e:  # noqa: BLE001
                print(f"gemini {modelo} {idioma}: {type(e).__name__}")


def baixar(url, destino, cabecalhos=None):
    req = urllib.request.Request(url, headers={**UA, **(cabecalhos or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        destino.write_bytes(resp.read())


def google_demos():
    for v in GOOGLE_DEMOS:
        wav = SAIDA / f"google-{v}.wav"
        try:
            baixar(f"https://docs.cloud.google.com/static/text-to-speech/docs/audio/chirp3-hd-{v}.wav", wav)
            mp3(wav, SAIDA / f"en-google-chirp3hd-{v}-demo.mp3")
            wav.unlink()
            print(f"ok google {v}")
        except Exception as e:  # noqa: BLE001
            print(f"google {v}: {type(e).__name__} {e}")


def clone():
    """A voz clonada de hoje no mesmo trecho: as falas já guardadas no cache da narração do Vasa (nada é gerado)."""
    env = {**os.environ, "VOZ_FALAS": str(FALAS)}
    r = subprocess.run([sys.executable, "canal/narrar_clone.py", str(ROTEIRO), "pt", "saida"], env=env)
    tmp = Path("saida/o-naufragio-do-vasa/pt/_tmp")
    partes = [tmp / f"b{i:02d}.wav" for i in range(FALAS)]
    if r.returncode or not all(p.exists() for p in partes):
        print("clone: as falas não estavam todas no cache, pulei")
        return
    lista = tmp / "lista.txt"
    sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.35", tmp / "pausa.wav")
    lista.write_text("".join(f"file '{p.resolve()}'\nfile '{(tmp / 'pausa.wav').resolve()}'\n" for p in partes), encoding="utf-8")
    sh("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-ac", "1", "-ar", "44100", "-b:a", "96k",
       SAIDA / "pt-clone-atual.mp3")
    print("ok pt-clone-atual")


def main():
    SAIDA.mkdir(exist_ok=True)
    txt = textos()
    (SAIDA / "textos.json").write_text(json.dumps(txt, ensure_ascii=False, indent=1), encoding="utf-8")
    asyncio.run(edge(txt))
    gemini(txt)
    google_demos()
    clone()
    for p in SAIDA.iterdir():
        if p.stat().st_size == 0:                            # arquivo vazio não sobe para a Release
            p.unlink()
    print("arquivos:", sorted(p.name for p in SAIDA.iterdir()))


if __name__ == "__main__":
    main()
