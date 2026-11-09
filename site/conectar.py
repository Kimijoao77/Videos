"""Transforma canal/POSTAGEM.md (do repositório privado) na página conectar.html do site. uso: python3 conectar.py <md> <html>"""
import sys
import markdown

md = open(sys.argv[1], encoding="utf-8").read()
corpo = markdown.markdown(md, extensions=["tables", "sane_lists"])
corpo = corpo.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')
html = f"""<!doctype html>
<html lang="pt-BR" data-modo="maquina">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conectar os canais · Nexus</title>
  <meta name="description" content="Passo a passo para ligar o robô de postagem do Nexus aos canais do YouTube.">
  <link rel="stylesheet" href="estilo.css">
  <style>
    body {{ height: auto; overflow: auto; -webkit-user-select: text; user-select: text; }}
    main {{ max-width: 720px; margin: 0 auto; padding: 24px 16px 64px; line-height: 1.6; font-size: 16px; }}
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
  </style>
</head>
<body><main><a class="voltar-pc" href="./">‹ Máquina no computador</a>
{corpo}
</main></body>
</html>
"""
open(sys.argv[2], "w", encoding="utf-8").write(html)
print("conectar.html ok")
