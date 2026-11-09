"""Minutos do GitHub Actions gastos neste mês no repositório. Repositório privado no plano grátis tem 2.000 por mês;
quando acabam, tudo para até o mês virar (a fábrica, a pesquisa diária, o registro e o APK do app). Repositório
público não gasta minutos.

Grava canal/dados/minutos.json (o app mostra na aba Escala) e, com --guarda, sai com erro quando um vídeo novo não
cabe no que sobra, guardando uma reserva para o resto (a fábrica chama isso antes de começar).

Uso:  python canal/minutos.py                    atualiza canal/dados/minutos.json
      python canal/minutos.py --guarda pt,en     idem e erro se o vídeo nesses idiomas não cabe
"""
import datetime as dt, json, math, os, subprocess, sys
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "Kimijoao77/Engfy")
ARQ = Path(__file__).parent / "dados" / "minutos.json"
LIMITE = 2000          # plano grátis, repositório privado
RESERVA = 100          # para a pesquisa diária, o registro e o APK do app até o mês virar (era 150; 100 desde 09/11)
CUSTO = {"pt": 150, "en": 160}   # um documentário de ~7 min com a voz clonada (Chatterbox nos dois idiomas): narração
                                 # ~100 min + cenas ~45 min por idioma (medido no Roanoke)


def api(caminho):
    r = subprocess.run(["gh", "api", caminho], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"gh api {caminho}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def minutos_do_run(rid, agora):
    m = 0
    for j in api(f"repos/{REPO}/actions/runs/{rid}/jobs?per_page=100").get("jobs", []):
        if not j.get("started_at"):
            continue
        a = dt.datetime.fromisoformat(j["started_at"].replace("Z", "+00:00"))
        b = dt.datetime.fromisoformat(j["completed_at"].replace("Z", "+00:00")) if j.get("completed_at") else agora
        s = (b - a).total_seconds()
        if s > 0:
            m += math.ceil(s / 60)                  # o GitHub cobra cada job arredondado para o minuto de cima
    return m


def contar():
    agora = dt.datetime.now(dt.timezone.utc)
    mes = agora.strftime("%Y-%m")
    antigo = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    feitos = antigo.get("runs", {}) if antigo.get("mes") == mes else {}
    runs, andamento, pagina = {}, 0, 1
    while True:
        lista = api(f"repos/{REPO}/actions/runs?created=>={mes}-01&per_page=100&page={pagina}").get("workflow_runs", [])
        for r in lista:
            rid = str(r["id"])
            if r["status"] == "completed":
                runs[rid] = feitos[rid] if rid in feitos else minutos_do_run(rid, agora)
            else:
                andamento += minutos_do_run(rid, agora)
        if len(lista) < 100:
            break
        pagina += 1
    publico = not api(f"repos/{REPO}").get("private", True)
    usados = sum(runs.values())
    sobra = LIMITE - usados - andamento - RESERVA
    return {"mes": mes, "atualizado": agora.strftime("%Y-%m-%dT%H:%M:%SZ"), "publico": publico, "limite": LIMITE,
            "usados": usados, "em_andamento": andamento, "reserva": RESERVA, "custo_video": sum(CUSTO.values()),
            "videos_que_cabem": None if publico else max(0, sobra // sum(CUSTO.values())), "runs": runs}


def main():
    guarda = "--guarda" in sys.argv
    idiomas = sys.argv[sys.argv.index("--guarda") + 1].split(",") if guarda and len(sys.argv) > sys.argv.index("--guarda") + 1 else ["pt", "en"]
    try:
        info = contar()
    except Exception as e:                          # sem acesso à API: não trava a fábrica por isso
        print(f"não consegui contar os minutos: {e}")
        return
    if not guarda:
        ARQ.write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    custo = sum(CUSTO.get(i, 160) for i in idiomas if i)
    gasto = info["usados"] + info["em_andamento"]
    situacao = "repositório público: não conta" if info["publico"] else "cabem %s vídeo(s)" % info["videos_que_cabem"]
    print(f"minutos em {info['mes']}: {gasto} de {LIMITE} ({situacao})")
    if guarda and not info["publico"] and gasto + custo + RESERVA > LIMITE:
        print(f"::error::Este vídeo gastaria uns {custo} minutos e o mês só tem {LIMITE - gasto} sobrando "
              f"(guardando {RESERVA} para o app e a pesquisa). A fábrica parou aqui para não travar o resto. "
              "Saída: mudar a fábrica para o repositório público (opção B) ou rodar de novo com forcar=sim.")
        sys.exit(1)


if __name__ == "__main__":
    main()
