"""Transforma um .md numa página do site com o visual do app (passo a passo, sobre, privacidade, termos).
uso: python3 pagina.py <md> <html> "<título>" "<descrição>" [voltar]"""
import html as H
import sys

import markdown

md_arq, html_arq, titulo, descricao = sys.argv[1:5]
voltar = '<a class="voltar-pc" href="./">‹ Máquina no computador</a>\n' if sys.argv[5:6] == ["voltar"] else ""
corpo = markdown.markdown(open(md_arq, encoding="utf-8").read(), extensions=["tables", "sane_lists"])
corpo = corpo.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')
pagina = f"""<!doctype html>
<html lang="pt-BR" data-modo="maquina">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{H.escape(titulo)} · Nexus</title>
  <meta name="description" content="{H.escape(descricao)}">
  <link rel="stylesheet" href="estilo.css">
  <style>
    body {{ height: auto; overflow: auto; -webkit-user-select: text; user-select: text; }}
    main {{ max-width: 720px; margin: 0 auto; padding: 24px 16px 40px; line-height: 1.6; font-size: 16px; }}
    h1 {{ font: 800 30px/1.15 var(--display); margin: 8px 0 12px; }}
    h2 {{ font: 700 21px/1.25 var(--display); margin: 34px 0 10px; padding-top: 18px; border-top: 2px solid var(--linha); }}
    p, li {{ color: var(--tinta); }} li {{ margin: 6px 0; }} ol, ul {{ padding-left: 22px; }}
    a {{ color: var(--acento-texto); font-weight: 700; }}
    code {{ font: 600 14px ui-monospace, monospace; background: var(--superficie-2); padding: 2px 6px; border-radius: 6px; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 15px; }}
    th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--linha); }}
    hr {{ border: 0; border-top: 2px dashed var(--linha); margin: 36px 0 16px; }}
    hr + p {{ font-size: 13.5px; color: var(--tinta-2); }}
    .voltar-pc {{ display: inline-block; margin-bottom: 8px; font-weight: 700; }}
    .rodape {{ max-width: 720px; margin: 0 auto; padding: 18px 16px 48px; display: flex; flex-wrap: wrap; gap: 8px 20px;
              border-top: 2px solid var(--linha); font-size: 14px; }}
    .rodape a {{ color: var(--tinta-2); font-weight: 700; }}
  </style>
</head>
<body><main>{voltar}{corpo}
</main>
<footer class="rodape"><a href="sobre.html">Nexus Canal</a><a href="privacidade.html">Política de privacidade</a><a href="termos.html">Termos de uso</a><a href="conectar.html">Conectar os canais</a><a href="./">Máquina no computador</a></footer>
</body>
</html>
"""
open(html_arq, "w", encoding="utf-8").write(pagina)
print(f"{html_arq} ok")
