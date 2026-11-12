"""Narração: voz grátis (edge-tts) em WAV, com o tempo de cada palavra (para a legenda animada).

Regra do projeto: a única IA que cria conteúdo é o Claude (ele escreve o roteiro); a voz só lê esse texto.
"""
import asyncio, difflib, re, subprocess, unicodedata

VOZ = {"pt": "pt-BR-AntonioNeural", "en": "en-US-AndrewNeural"}


def _sh(*cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)   # nunca fica esperando o teclado
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    return r.stdout


def duracao(arq):
    return float(_sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arq).strip())


def _norm(w):
    w = unicodedata.normalize("NFKD", w.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", w)


async def _edge(texto, idioma, mp3):
    import edge_tts
    try:
        com = edge_tts.Communicate(texto, VOZ[idioma], rate="+6%", boundary="WordBoundary")
    except TypeError:
        com = edge_tts.Communicate(texto, VOZ[idioma], rate="+6%")
    pal = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] in ("WordBoundary", "SentenceBoundary"):
                n = len(ch["text"].split())
                for i, w in enumerate(ch["text"].split()):  # frase: espalha as palavras dentro dela
                    pal.append({"w": w, "t": ch["offset"] / 1e7 + i * ch["duration"] / 1e7 / n, "d": ch["duration"] / 1e7 / n})
    return pal


def _casar(palavras_roteiro, faladas, dur):
    """Dá a cada palavra do roteiro o tempo da palavra falada correspondente; as sem par são interpoladas."""
    a = [_norm(w) for w in palavras_roteiro]
    b = [_norm(o["w"]) for o in faladas]
    tempos = [None] * len(a)
    for bloco in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            o = faladas[bloco.b + k]
            tempos[bloco.a + k] = (o["t"], o["d"])
    conhecidos = [i for i, x in enumerate(tempos) if x]
    if not conhecidos:
        passo = dur / max(1, len(a))
        return [{"w": w, "t": i * passo, "d": passo} for i, w in enumerate(palavras_roteiro)]
    for i in range(len(a)):  # interpola quem ficou sem tempo entre os vizinhos conhecidos
        if tempos[i]:
            continue
        ant = max([j for j in conhecidos if j < i], default=None)
        pro = min([j for j in conhecidos if j > i], default=None)
        t0 = tempos[ant][0] + tempos[ant][1] if ant is not None else 0.0
        t1 = tempos[pro][0] if pro is not None else dur
        n0 = ant if ant is not None else -1
        n1 = pro if pro is not None else len(a)
        passo = max(0.05, (t1 - t0) / (n1 - n0))
        tempos[i] = (t0 + (i - n0 - 1) * passo, passo)
    return [{"w": w, "t": t, "d": d} for w, (t, d) in zip(palavras_roteiro, tempos)]


_KOKORO = {}


def _kokoro(texto, idioma, wav, voz, velocidade=1.0):
    """Kokoro (modelo aberto, Apache 2.0) rodando no próprio GitHub. Tempo das palavras: o do modelo (inglês) ou
    repartido dentro de cada trecho pelo tamanho das palavras (português)."""
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    lang = "b" if voz.startswith("b") else ("p" if idioma == "pt" else "a")
    if lang not in _KOKORO:
        _KOKORO[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    partes, faladas, t = [], [], 0.0
    for res in _KOKORO[lang](texto, voice=voz, speed=velocidade):
        audio = res.audio
        audio = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
        dur = len(audio) / 24000
        toks = getattr(res, "tokens", None) or []
        if toks and all(getattr(k, "start_ts", None) is not None for k in toks):
            for k in toks:
                if re.search(r"\w", k.text or ""):
                    faladas.append({"w": k.text, "t": t + k.start_ts, "d": max(0.05, k.end_ts - k.start_ts)})
        else:
            ws = (res.graphemes or "").split()
            pesos = [len(re.sub(r"\W", "", w)) + 1.5 for w in ws]
            total = sum(pesos) or 1
            tt, util = t + 0.04, max(0.1, dur - 0.12)
            for w, k in zip(ws, pesos):
                d = util * k / total
                faladas.append({"w": w, "t": tt, "d": d})
                tt += d
        partes.append(audio.astype(np.float32))
        t += dur
    bruto = wav.with_suffix(".k.wav")
    sf.write(str(bruto), np.concatenate(partes) if partes else np.zeros(2400, np.float32), 24000)
    _sh("ffmpeg", "-y", "-v", "error", "-i", bruto, "-ar", "44100", "-ac", "1", wav)
    return faladas


def tempos_por_pausas(wav, texto):
    """Tempo de cada palavra quando o motor de voz não informa: acha as pausas no áudio e casa com a pontuação do
    texto (cada trecho entre vírgulas/pontos termina numa pausa); dentro do trecho, reparte pelo tamanho das palavras."""
    import wave as _w
    import numpy as np
    with _w.open(str(wav)) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(axis=1)
    passo = int(sr * 0.01)
    n = max(1, len(a) // passo)
    env = np.sqrt((a[: n * passo].reshape(n, passo) ** 2).mean(axis=1) + 1e-12)
    limiar = max(0.012, 0.08 * float(np.percentile(env, 95)))
    fala = env > limiar
    if not fala.any():
        return []
    ini_f, fim_f = int(np.argmax(fala)), int(n - np.argmax(fala[::-1]))
    pausas = []                                                     # (início, fim) em segundos, só por dentro da fala
    k = ini_f
    while k < fim_f:
        if not fala[k]:
            j = k
            while j < fim_f and not fala[j]:
                j += 1
            if j - k >= 12:                                         # 120 ms ou mais
                pausas.append((k * 0.01, j * 0.01))
            k = j
        else:
            k += 1
    palavras = texto.split()
    trechos, atual = [], []
    for w in palavras:
        atual.append(w)
        if re.search(r"[,.;:!?…—]$", w):
            trechos.append(atual)
            atual = []
    if atual:
        trechos.append(atual)

    def peso(ws):
        return sum(len(re.sub(r"\W", "", w)) + 1.2 for w in ws)

    s0, s1 = ini_f * 0.01, fim_f * 0.01
    total = sum(peso(t) for t in trechos) or 1
    esperados, acum = [], 0.0
    for t in trechos[:-1]:
        acum += peso(t)
        esperados.append(s0 + (s1 - s0) * acum / total)
    # casa limites de trecho com pausas, em ordem (alinhamento por programação dinâmica):
    # casar custa o desvio relativo ao quadrado; deixar um limite sem pausa custa 0,06; pausa sobrando não custa
    B, Pn, Lt = len(esperados), len(pausas), max(0.1, s1 - s0)
    INF = 1e9
    custo = [[INF] * (Pn + 1) for _ in range(B + 1)]
    volta = [[None] * (Pn + 1) for _ in range(B + 1)]
    for j in range(Pn + 1):
        custo[0][j] = 0.0
    for i in range(1, B + 1):
        custo[i][0] = custo[i - 1][0] + 0.06
        volta[i][0] = ("pula_limite", i - 1, 0)
        for j in range(1, Pn + 1):
            m = (pausas[j - 1][0] + pausas[j - 1][1]) / 2
            opcoes = [(custo[i - 1][j - 1] + ((esperados[i - 1] - m) / Lt) ** 2, ("casa", i - 1, j - 1)),
                      (custo[i - 1][j] + 0.06, ("pula_limite", i - 1, j)),
                      (custo[i][j - 1], ("pula_pausa", i, j - 1))]
            custo[i][j], volta[i][j] = min(opcoes, key=lambda o: o[0])
    limites = [None] * B
    i, j = B, Pn
    while i > 0:
        tipo, pi, pj = volta[i][j]
        if tipo == "casa":
            limites[i - 1] = pausas[j - 1]
        i, j = pi, pj
    limites = [lim if lim else (e, e) for lim, e in zip(limites, esperados)]
    limites.sort()
    out, ini = [], s0
    for k, t in enumerate(trechos):
        fim = limites[k][0] if k < len(limites) else s1
        prox = limites[k][1] if k < len(limites) else s1
        util = max(0.05, fim - ini)
        pt = peso(t) or 1
        tt = ini
        for w in t:
            d = util * (len(re.sub(r"\W", "", w)) + 1.2) / pt
            out.append({"w": w, "t": tt, "d": d})
            tt += d
        ini = prox
    return out


_TOKEN_GOOGLE = {}


def _google_credencial():
    """Como entrar na API de voz do Google, a partir do segredo GOOGLE_TTS_KEY: o JSON de uma conta de serviço
    (vira um token que vale 1 hora) ou uma chave de API clássica (AIza…). Devolve (params, cabeçalhos)."""
    import json
    import os
    import time
    s = os.environ.get("GOOGLE_TTS_KEY", "").strip()
    if not s:
        raise RuntimeError("falta o segredo GOOGLE_TTS_KEY")
    if not s.startswith("{"):
        return {"key": s}, {}
    if _TOKEN_GOOGLE.get("ate", 0) < time.time() + 120:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        cred = service_account.Credentials.from_service_account_info(
            json.loads(s), scopes=["https://www.googleapis.com/auth/cloud-platform"])
        cred.refresh(Request())
        _TOKEN_GOOGLE.update(token=cred.token, ate=time.time() + 3000, projeto=json.loads(s).get("project_id", ""))
    cab = {"Authorization": f"Bearer {_TOKEN_GOOGLE['token']}"}
    if _TOKEN_GOOGLE.get("projeto"):
        cab["x-goog-user-project"] = _TOKEN_GOOGLE["projeto"]
    return {}, cab


def _google(texto, idioma, wav, voz, velocidade=1.0):
    """Google Cloud Text-to-Speech (vozes Chirp 3 HD). O acesso fica no segredo GOOGLE_TTS_KEY do GitHub."""
    import base64
    import requests
    params, cab = _google_credencial()
    lingua = {"pt": "pt-BR", "en": "en-US"}[idioma]
    nome = voz if "-" in (voz or "") else f"{lingua}-Chirp3-HD-{voz or 'Charon'}"
    corpo = {"input": {"text": texto}, "voice": {"languageCode": lingua, "name": nome},
             "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 44100}}
    if abs(velocidade - 1.0) > 1e-3:
        corpo["audioConfig"]["speakingRate"] = velocidade
    for tentativa in range(4):
        r = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize", params=params, headers=cab, json=corpo, timeout=120)
        if r.status_code == 200:
            break
        if r.status_code == 400 and "speakingRate" in corpo["audioConfig"]:
            corpo["audioConfig"].pop("speakingRate")                 # voz que não aceita mudar a velocidade
            continue
        if r.status_code in (429, 500, 503):
            import time
            time.sleep(5 * (tentativa + 1))
            continue
        raise RuntimeError(f"Google TTS {r.status_code}: {r.text[:300]}")
    else:
        raise RuntimeError(f"Google TTS {r.status_code}: {r.text[:300]}")
    bruto = wav.with_suffix(".g.wav")
    bruto.write_bytes(base64.b64decode(r.json()["audioContent"]))
    _sh("ffmpeg", "-y", "-v", "error", "-i", bruto, "-ar", "44100", "-ac", "1", wav)
    return tempos_por_pausas(wav, texto)


def _elevenlabs(texto, idioma, wav, voz, velocidade=1.0, modelo="eleven_multilingual_v2"):
    """ElevenLabs (segredo ELEVENLABS_API_KEY no GitHub). voz = id da voz na conta. A própria API devolve o tempo de
    cada letra, então o tempo das palavras sai exato (sem adivinhar pelas pausas)."""
    import base64
    import os
    import time
    import requests
    chave = os.environ.get("ELEVENLABS_API_KEY", "")
    if not chave:
        raise RuntimeError("falta o segredo ELEVENLABS_API_KEY")
    ajustes = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}
    if abs(velocidade - 1.0) > 1e-3:
        ajustes["speed"] = velocidade
    corpo = {"text": texto, "model_id": modelo, "voice_settings": ajustes}
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps"
    for tentativa in range(4):
        r = requests.post(url, params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": chave}, json=corpo, timeout=180)
        if r.status_code == 200:
            break
        if r.status_code in (429, 500, 502, 503):
            time.sleep(5 * (tentativa + 1))
            continue
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    else:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    j = r.json()
    mp3 = wav.with_suffix(".el.mp3")
    mp3.write_bytes(base64.b64decode(j["audio_base64"]))
    _sh("ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "44100", "-ac", "1", wav)
    faladas = []
    al = j.get("alignment") or j.get("normalized_alignment")
    if al:
        palavra, t0, t1 = "", 0.0, 0.0
        for ch, a, b in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
            if ch.isspace():
                if palavra:
                    faladas.append({"w": palavra, "t": t0, "d": max(0.02, t1 - t0)})
                    palavra = ""
                continue
            if not palavra:
                t0 = a
            palavra += ch
            t1 = b
        if palavra:
            faladas.append({"w": palavra, "t": t0, "d": max(0.02, t1 - t0)})
    return faladas or tempos_por_pausas(wav, texto)


def _speechify(texto, idioma, wav, voz, modelo="simba-3.5"):
    """Speechify (segredo SPEECHIFY_API_KEY no GitHub, 10/11/2026). voz = id da voz do catálogo (ex.: fabio-agent).
    A API devolve as marcas de fala (tempo de cada palavra); sem elas, o tempo sai pelas pausas."""
    import base64
    import os
    import time
    import requests
    chave = os.environ.get("SPEECHIFY_API_KEY", "")
    if not chave:
        raise RuntimeError("falta o segredo SPEECHIFY_API_KEY")
    corpo = {"input": texto, "voice_id": voz, "model": modelo, "language": {"pt": "pt-BR", "en": "en-US"}[idioma],
             "audio_format": "mp3"}
    for tentativa in range(5):
        r = requests.post("https://api.speechify.ai/v1/audio/speech", headers={"Authorization": f"Bearer {chave}"},
                          json=corpo, timeout=180)
        if r.status_code == 200:
            break
        if r.status_code in (429, 500, 502, 503):
            time.sleep(3 * (tentativa + 1))
            continue
        raise RuntimeError(f"Speechify {r.status_code}: {r.text[:300]}")
    else:
        raise RuntimeError(f"Speechify {r.status_code}: {r.text[:300]}")
    marcas = None
    if r.headers.get("content-type", "").startswith("audio"):
        audio = r.content
    else:
        j = r.json()
        audio = base64.b64decode(j.get("audio_data", ""))
        marcas = j.get("speech_marks")
    mp3 = wav.with_suffix(".sf.mp3")
    mp3.write_bytes(audio)
    _sh("ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "44100", "-ac", "1", wav)
    palavras = []

    def achar(no):
        if isinstance(no, dict):
            if no.get("type") == "word" and "start_time" in no:
                palavras.append(no)
            for v in no.values():
                achar(v)
        elif isinstance(no, list):
            for v in no:
                achar(v)
    achar(marcas)
    if not palavras:
        return tempos_por_pausas(wav, texto)
    dur = duracao(wav)
    fim = max(float(p.get("end_time", p["start_time"])) for p in palavras)
    esc = 1000.0 if fim > dur * 3 else 1.0                   # milissegundos ou segundos
    return [{"w": str(p.get("value", "")), "t": float(p["start_time"]) / esc,
             "d": max(0.02, (float(p.get("end_time", p["start_time"])) - float(p["start_time"])) / esc)} for p in palavras]


_MESES_EN = "January|February|March|April|May|June|July|August|September|October|November|December"


def por_extenso(texto, idioma):
    """Escreve os números por extenso (anos, datas, quantidades), porque os motores de voz clonada leem melhor assim.
    Sem o pacote num2words, devolve o texto como está."""
    try:
        from num2words import num2words
    except ImportError:
        return texto
    if idioma == "en":
        texto = re.sub(r"\b(1[1-9])00s\b", lambda m: num2words(int(m.group(1)), lang="en") + " hundreds", texto)
        texto = re.sub(r"\b(" + _MESES_EN + r") (\d{1,2})\b",
                       lambda m: m.group(1) + " " + num2words(int(m.group(2)), lang="en", to="ordinal"), texto)
        texto = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", lambda m: num2words(int(m.group(1)), lang="en", to="ordinal"), texto)
        return re.sub(r"\b\d+\b", lambda m: num2words(int(m.group(0)), lang="en",
                                                       to="year" if 1100 <= int(m.group(0)) <= 2099 else "cardinal"), texto)
    return re.sub(r"\b\d+\b", lambda m: num2words(int(m.group(0)), lang="pt_BR").replace(",", ""), texto)


def narrar(texto, idioma, pasta, nome, offline=False, motor="edge", voz=None, velocidade=1.0, trocas=None):
    """Gera <pasta>/<nome>.wav. Devolve (duração, palavras com tempo, de onde veio a voz).
    motor: edge (Microsoft, grátis), kokoro (modelo aberto rodando no GitHub), google (Chirp 3 HD), elevenlabs ou
    clone (a voz do dono do canal, gerada antes por narrar_clone.py: aqui só lê o arquivo e acha o tempo das palavras);
    voz: nome (ou id) da voz no motor."""
    wav = pasta / f"{nome}.wav"
    palavras = texto.split()
    if motor == "speechify" and not offline:
        falado = texto
        for de, para in (trocas or {}).items():               # "pronuncia" do roteiro: só para a voz, a legenda fica igual
            falado = re.sub(rf"\b{re.escape(de)}\b", para, falado)
        faladas = _speechify(falado, idioma, wav, voz)
        dur = duracao(wav)
        return dur, _casar(palavras, faladas, dur), f"speechify-{voz}"
    if motor == "elevenlabs" and not offline:
        faladas = _elevenlabs(texto, idioma, wav, voz, velocidade)
        dur = duracao(wav)
        return dur, _casar(palavras, faladas, dur), "elevenlabs"
    if motor == "google" and not offline:
        faladas = _google(texto, idioma, wav, voz, velocidade)
        dur = duracao(wav)
        return dur, _casar(palavras, faladas, dur), "google-chirp3hd"
    if motor == "kokoro" and not offline:
        faladas = _kokoro(texto, idioma, wav, voz or {"pt": "pm_alex", "en": "am_michael"}[idioma], velocidade)
        dur = duracao(wav)
        return dur, _casar(palavras, faladas, dur), "kokoro"
    if motor == "clone" and wav.exists():          # gerada antes por narrar_clone.py (a voz clonada do dono do canal)
        dur = duracao(wav)
        peso = " ".join(re.sub(r"[\s-]+", "", por_extenso(w, idioma)) for w in palavras)   # número conta como falado
        faladas = tempos_por_pausas(wav, peso)
        if len(faladas) == len(palavras):
            return dur, [{"w": w, "t": f["t"], "d": f["d"]} for w, f in zip(palavras, faladas)], f"clone-{voz}"
        return dur, _casar(palavras, faladas, dur), f"clone-{voz}"
    if motor == "clone" and not offline:
        raise RuntimeError(f"falta a narração clonada {wav.name}: rode canal/narrar_clone.py antes do filme.py")
    if voz:
        VOZ[idioma] = voz
    if offline:
        dur = max(1.5, len(palavras) / 2.6)
        _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{dur:.2f}", wav)
        passo = dur / len(palavras)
        return dur, [{"w": w, "t": i * passo, "d": passo} for i, w in enumerate(palavras)], "silêncio"
    mp3 = pasta / f"{nome}.mp3"
    import time
    for tentativa in range(7):                        # a voz grátis às vezes não responde: espera e tenta de novo
        try:
            faladas = asyncio.run(asyncio.wait_for(_edge(texto, idioma, mp3), 120))
            break
        except Exception as e:
            print("  a voz falhou, tentando de novo:", e, flush=True)
            time.sleep(2 + 3 * tentativa)
    else:
        raise RuntimeError("a voz não respondeu")
    _sh("ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "44100", "-ac", "1", wav)
    dur = duracao(wav)
    if len(faladas) < max(2, len(palavras) // 3):          # a voz não mandou o tempo das palavras: acha pelas pausas
        faladas = tempos_por_pausas(wav, texto) or faladas
    return dur, _casar(palavras, faladas, dur), "edge"
