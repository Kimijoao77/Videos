"""Cópia da Evolução no Google Drive (17/11/2026). Pedido do João: o plano é de anos, e os dados não podem depender só
da conta do GitHub. Roda uma vez por dia no Actions deste repositório (evolucao-drive.yml):

- baixa as cópias públicas do repositório evolucao-hyperliquid (Releases copias-geracoes e copias-diarias) e a
  memória das gerações (a pasta memoria/ da main, com o histórico inteiro de todos os robôs);
- manda para a pasta "Evolução - cópias" do Drive toda cópia de geração fechada que ainda não está lá e, uma vez por
  semana, a cópia diária mais nova; a memória das gerações é regravada por cima a cada vez (é pequena);
- guarda as 12 cópias completas mais novas e manda as mais velhas para a lixeira do Drive.

A chave é de um projeto do Google só para isto (separado do YouTube), com o escopo drive.file: ela só enxerga os
arquivos que ela mesma criou, nada do resto do Drive. Secrets: GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET e GDRIVE_TOKEN
(o refresh token). Sem eles, não faz nada.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone

import requests

REPO = "Kimijoao77/evolucao-hyperliquid"
PASTA = "Evolução - cópias"
MANTER = 12
DRIVE = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"


def saida(chave: str, valor: str) -> None:
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{chave}={valor}\n")


def token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": os.environ["GDRIVE_CLIENT_ID"], "client_secret": os.environ["GDRIVE_CLIENT_SECRET"],
        "refresh_token": os.environ["GDRIVE_TOKEN"], "grant_type": "refresh_token"})
    if r.status_code != 200:
        erro = r.json().get("error", r.status_code) if r.headers.get("content-type", "").startswith("application/json") else r.status_code
        sys.exit(f"Drive: a chave não funcionou ({erro}). Se for invalid_grant, o refresh token venceu ou foi revogado: gere outro.")
    return r.json()["access_token"]


class Drive:
    def __init__(self, tk: str):
        self.h = {"Authorization": f"Bearer {tk}"}

    def listar(self, q: str) -> list[dict]:
        r = requests.get(DRIVE, headers=self.h, timeout=30, params={
            "q": q, "fields": "files(id,name,createdTime,size)", "pageSize": 1000, "orderBy": "createdTime desc"})
        r.raise_for_status()
        return r.json().get("files", [])

    def pasta(self) -> str:
        nome = PASTA.replace("'", "\\'")
        achou = self.listar(f"name = '{nome}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        if achou:
            return achou[0]["id"]
        r = requests.post(DRIVE, headers=self.h, timeout=30, json={"name": PASTA, "mimeType": "application/vnd.google-apps.folder"})
        r.raise_for_status()
        print(f"Drive: pasta '{PASTA}' criada")
        return r.json()["id"]

    def enviar(self, nome: str, dados: bytes, pasta: str, por_cima: str | None = None) -> None:
        if por_cima:
            ini = requests.patch(f"{UPLOAD}/{por_cima}?uploadType=resumable", headers=self.h, json={}, timeout=30)
        else:
            ini = requests.post(f"{UPLOAD}?uploadType=resumable", headers=self.h, json={"name": nome, "parents": [pasta]}, timeout=30)
        ini.raise_for_status()
        r = requests.put(ini.headers["Location"], data=dados, timeout=600, headers={"Content-Type": "application/gzip"})
        r.raise_for_status()
        print(f"Drive: enviado {nome} ({len(dados) / 1e6:.1f} MB)")

    def lixeira(self, fid: str) -> None:
        requests.patch(f"{DRIVE}/{fid}", headers=self.h, json={"trashed": True}, timeout=30).raise_for_status()


def gh(caminho: str) -> dict | None:
    h = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    r = requests.get(f"https://api.github.com/repos/{REPO}/{caminho}", headers=h, timeout=30)
    return r.json() if r.status_code == 200 else None


def baixar(url: str) -> bytes:
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    return r.content


def memoria() -> bytes:
    """Só a pasta memoria/ da main, compactada de novo."""
    bruto = baixar(f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/main")
    saida_tar = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(bruto), mode="r:gz") as t, tarfile.open(fileobj=saida_tar, mode="w:gz") as novo:
        for m in t.getmembers():
            partes = m.name.split("/", 1)
            if len(partes) == 2 and partes[1].startswith("memoria/") and m.isfile():
                m.name = partes[1]
                novo.addfile(m, t.extractfile(m))
    return saida_tar.getvalue()


def main() -> int:
    if not all(os.environ.get(k) for k in ("GDRIVE_CLIENT_ID", "GDRIVE_CLIENT_SECRET", "GDRIVE_TOKEN")):
        print("Drive: ainda sem a chave (secrets GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET e GDRIVE_TOKEN). Nada a fazer.")
        saida("ok", "0")
        return 0
    d = Drive(token())
    pasta = d.pasta()
    tem = d.listar(f"'{pasta}' in parents and trashed = false")
    nomes = {f["name"] for f in tem}

    # 1. cada geração fechada
    geracoes = (gh("releases/tags/copias-geracoes") or {}).get("assets", [])
    for a in sorted(geracoes, key=lambda a: a["name"]):
        if a["name"] not in nomes:
            d.enviar(a["name"], baixar(a["browser_download_url"]), pasta)
            nomes.add(a["name"])

    # 2. uma por semana (a diária mais nova)
    agora = datetime.now(timezone.utc)
    semanais = [f for f in tem if f["name"].startswith("estado-semana-")]
    recente = any(datetime.fromisoformat(f["createdTime"].replace("Z", "+00:00")) > agora - timedelta(days=7) for f in semanais)
    if not recente:
        diarias = sorted((a for a in (gh("releases/tags/copias-diarias") or {}).get("assets", [])
                          if a["name"].startswith("estado-2")), key=lambda a: a["name"])
        if diarias:
            ult = diarias[-1]
            d.enviar("estado-semana-" + ult["name"][len("estado-"):], baixar(ult["browser_download_url"]), pasta)

    # 3. a memória das gerações, por cima
    mem = next((f for f in tem if f["name"] == "memoria-das-geracoes.tgz"), None)
    d.enviar("memoria-das-geracoes.tgz", memoria(), pasta, por_cima=mem["id"] if mem else None)

    # 4. guarda as 12 cópias completas mais novas
    completas = [f for f in d.listar(f"'{pasta}' in parents and trashed = false") if f["name"].startswith("estado-")]
    for f in completas[MANTER:]:
        d.lixeira(f["id"])
        print(f"Drive: {f['name']} foi para a lixeira (fica lá 30 dias)")
    total = sum(int(f.get("size") or 0) for f in completas[:MANTER])
    print(f"Drive: ok, {min(len(completas), MANTER)} cópias completas ({total / 1e6:.0f} MB) e a memória das gerações")
    saida("ok", "1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
