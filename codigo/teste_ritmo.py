"""Testes do ritmo natural e das conferências de estilo (10/11/2026). Rodam sem voz, sem Whisper e sem internet:
python3 -m pytest canal/teste_ritmo.py -q   (precisa de numpy, soundfile, num2words; o realce precisa do Praat:
pip install praat-parselmouth)."""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import conferir_roteiro as CR  # noqa: E402
import narrar_clone as N  # noqa: E402
import ouvido as O  # noqa: E402

SR = 24000


def vogal(f0, sr=SR):
    fase = 2 * np.pi * np.cumsum(f0) / sr
    return (0.3 * np.sin(fase) + 0.15 * np.sin(2 * fase) + 0.08 * np.sin(3 * fase)).astype(np.float32)


def test_frases_e_tons():
    assert N.dividir_frases("Veio a segunda rajada. Dessa vez, ele não voltou… E quem levou a culpa? Ninguém.") == \
        ["Veio a segunda rajada.", "Dessa vez, ele não voltou…", "E quem levou a culpa?", "Ninguém."]
    assert N.tom_da_frase("E quem levou a culpa?", "narra") == "pergunta"
    assert N.tom_da_frase("E quem levou a culpa?", "tenso") == "tenso"
    assert N.tom_da_frase("Veio a segunda rajada.", "leve") == "leve"


def test_pausas_entre_frases():
    rng = random.Random(1)
    ponto = [N.pausa_depois("Fim.", 0.55, rng) for _ in range(50)]
    pergunta = [N.pausa_depois("Quem?", 0.55, rng) for _ in range(50)]
    retic = [N.pausa_depois("E aí…", 0.55, rng) for _ in range(50)]
    assert 0.3 < np.mean(ponto) < 0.5                 # 0,55 s menos as folgas de 60 ms de cada lado
    assert np.mean(ponto) < np.mean(pergunta) < np.mean(retic)


def test_chave_natural_muda_com_tom_e_texto():
    a = N.chave_natural("chatterbox", "abc", "pt", "narra", "Olá.")
    assert a == N.chave_natural("chatterbox", "abc", "pt", "narra", "Olá.")
    assert a != N.chave_natural("chatterbox", "abc", "pt", "tenso", "Olá.")
    assert a != N.chave_natural("chatterbox", "abc", "pt", "narra", "Olá!")


def test_tom_mede_variacao():
    t = np.arange(int(SR * 2.0)) / SR
    reta = O.tom(vogal(np.full_like(t, 120.0)), SR)
    viva = O.tom(vogal(120 * 2 ** (3 * np.sin(2 * np.pi * 0.8 * t) / 12)), SR)
    assert reta["dp"] < 0.3 < 1.5 < viva["dp"]
    assert abs(reta["hz"] - 120) < 3


def test_semelhanca_tolera_nome_e_numero():
    assert O.semelhanca("O nome dele era Vássa.", "O nome dele era Vasa.", "pt") > 0.95
    assert O.semelhanca("em mil seiscentos e vinte e oito", "em 1628", "pt") > 0.95
    assert O.semelhanca("Veio a segunda rajada.", "Veio a rajada.", "pt") < 0.9
    assert O.semelhanca("Veio a segunda rajada.", "", "pt") == 0.0


def frases_falsas():
    return [{"t0": 0.2, "t1": 6.8, "pergunta": False, "palavras": 18, "letras_s": 15.0, "dp": 1.8, "pausa": 0.6, "corte": 7.1},
            {"t0": 7.4, "t1": 9.0, "pergunta": False, "palavras": 4, "letras_s": 14.0, "dp": 2.0, "pausa": 0.5, "corte": 9.25},
            {"t0": 9.5, "t1": 15.5, "pergunta": False, "palavras": 16, "letras_s": 16.5, "dp": 2.9, "pausa": 0.7, "corte": 15.85},
            {"t0": 16.2, "t1": 19.0, "pergunta": False, "palavras": 9, "letras_s": 11.0, "dp": 2.2, "pausa": 0.8, "corte": 19.4},
            {"t0": 19.8, "t1": 21.9, "pergunta": True, "palavras": 6, "letras_s": 14.5, "dp": 3.1, "pausa": 0.9, "corte": 22.35},
            {"t0": 22.8, "t1": 30.0, "pergunta": False, "palavras": 20, "letras_s": 15.5, "dp": 2.4}]


def test_referencias_por_tom():
    refs = O.escolher_referencias(frases_falsas(), 30.5)
    assert set(refs) == {"viva", "tensa", "pergunta"}
    for w in refs.values():
        assert 5.0 <= w["fim"] - w["ini"] <= 10.0
    assert refs["viva"]["de"] == 2                        # a frase de tom mais variado abre a referência
    p = refs["pergunta"]
    assert p["de"] <= 4 <= p["ate"] and 21.9 <= p["ini"] + O.PROMPT_S + 0.3   # a pergunta cabe nos 6 s do jeito de falar
    assert O.pausas_da_gravacao(frases_falsas(), [0.15, 0.22, 0.3]) == {"frase": 0.7, "virgula": 0.22}


def test_realce_estica_o_tom():
    pytest.importorskip("parselmouth")
    t = np.arange(int(SR * 2.5)) / SR
    a = vogal(120 * 2 ** (1.6 * np.sin(2 * np.pi * 0.7 * t) / 12))
    antes = O.tom(a, SR)["dp"]
    b, k = N.realcar_tom(a, SR, 3.0)
    assert len(b) == len(a) and 1.2 < k <= 1.8
    assert O.tom(b, SR)["dp"] > antes + 0.5
    c, k2 = N.realcar_tom(b, SR, 1.0)                     # já variado o bastante: não mexe
    assert k2 == 1.0 and c is b


def roteiro(falas, **voz):
    return {"voz": {"motor": "clone", "pt": "chatterbox", "en": "edge", **voz},
            "batidas": [{"fala": {"pt": f, "en": f}, "cena": "mar_navio"} for f in falas]}


def test_conferidor_acusa_formula_e_repeticao():
    CR.erros.clear()
    CR.avisos.clear()
    r = roteiro(["Neste vídeo, vamos descobrir o que houve.", "O navio afundou a pouco mais de um quilômetro.",
                 "Ele tinha navegado pouco mais de um quilômetro.", "Navegou pouco mais de um quilômetro só."])
    CR.conferir_estilo(r)
    assert any("fórmula de texto de IA" in e for e in CR.erros)
    assert any("pouco mais de um" in e for e in CR.erros + CR.avisos)


def test_conferidor_conta_numeros_e_nomes():
    assert CR.contar_numeros("Em 10 de agosto de 1628, 64 canhões.", "pt") == 2
    assert CR.contar_numeros("mais de setecentas esculturas e dois mil e quinhentos homens", "pt") == 1
    assert CR.nomes_de("O rei Gustavo Adolfo brigava com a Polônia pelo mar Báltico.") == ["Gustavo Adolfo", "Polônia", "Báltico"]


def test_amostra_do_vasa_passa_no_conferidor():
    CR.erros.clear()
    CR.avisos.clear()
    arq = Path(__file__).parent / "rascunhos" / "amostra-vasa-v3.json"
    CR.conferir_estilo(json.loads(arq.read_text(encoding="utf-8")))
    assert not CR.erros
