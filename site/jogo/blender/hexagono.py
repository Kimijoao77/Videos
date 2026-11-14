"""Prepara as construções e a natureza do pacote KayKit Medieval Hexagon (Kay Lousberg, CC0) para o jogo: castelo,
torre e torre com catapulta em azul e vermelho, a ruína, árvores e pedra, já no tamanho da arena (1 = 1 casa).
Com "fotos", tira também a foto da carta da catapulta. Uso: python hexagono.py PASTA_DO_PACOTE PASTA_DO_JOGO [fotos]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy

import kit

PACOTE = Path(sys.argv[1]) / "addons" / "kaykit_medieval_hexagon_pack" / "Assets" / "gltf"
JOGO = Path(sys.argv[2])
# saída: (arquivo do pacote, escala)
QUAIS = {"ruina": ("buildings/neutral/building_destroyed", 1.9), "pedra_cat": ("buildings/neutral/projectile_catapult", 1.6),
         "arvore": ("decoration/nature/tree_single_B", 2.6), "pinheiro": ("decoration/nature/tree_single_A", 2.8),
         "pedra": ("decoration/nature/rock_single_B", 3.0), "bosque": ("decoration/nature/trees_B_large", 2.6)}
for cor, pt in (("blue", "azul"), ("red", "vermelho")):
    QUAIS[f"castelo_{pt}"] = (f"buildings/{cor}/building_castle_{cor}", 1.65)
    QUAIS[f"torre_{pt}"] = (f"buildings/{cor}/building_tower_B_{cor}", 2.0)
    QUAIS[f"catapulta_{pt}"] = (f"buildings/{cor}/building_tower_catapult_{cor}", 1.3)
    QUAIS[f"quartel_{pt}"] = (f"buildings/{cor}/building_barracks_{cor}", 1.35)
    QUAIS[f"mina_{pt}"] = (f"buildings/{cor}/building_mine_{cor}", 1.3)
    QUAIS[f"torre_arq_{pt}"] = (f"buildings/{cor}/building_tower_A_{cor}", 1.55)
SO = set(next((a[3:].split(",") for a in sys.argv if a.startswith("so:")), []))
FOTO = {"catapulta_azul": ("catapulta", (0, 0, 1.35), 7.4), "quartel_azul": ("quartel", (0, 0, 1.0), 7.0),
        "mina_azul": ("mina", (0, 0, 0.9), 6.6), "torre_arq_azul": ("torre_arq", (0, 0, 1.6), 8.2)}

for saida, (arq, esc) in QUAIS.items():
    if SO and not any(saida.startswith(x) for x in SO):
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(PACOTE / f"{arq}.gltf"))
    for o in bpy.data.objects:
        if o.parent is None:
            o.scale = (esc, esc, esc)
        nome = o.name
        for tira in ("_blue", "_red"):
            nome = nome.replace(tira, "")
        o.name = nome
    if "fotos" in sys.argv and saida in FOTO:
        carta, alvo, dist = FOTO[saida]
        kit.foto(JOGO / "cartas" / f"{carta}.png", alvo=alvo, dist=dist, az=-32, el=16, larg=512, alt=512, amostras=48, transparente=True)
        for o in list(bpy.data.objects):
            if o.name.startswith("_foto"):
                bpy.data.objects.remove(o)
    bpy.ops.export_scene.gltf(filepath=str(JOGO / "modelos" / f"{saida}.glb"), export_format="GLB", export_yup=True, export_animations=False,
                              export_cameras=False, export_lights=False)
    print("hexagono", saida, (JOGO / "modelos" / f"{saida}.glb").stat().st_size // 1024, "kB", flush=True)
