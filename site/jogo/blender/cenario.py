"""Junta num arquivo só (modelos/cenario.glb) as peças de cenário do pacote KayKit Medieval Hexagon (Kay Lousberg, CC0):
casas, moinho, igreja, muralhas, barracas, barris, montanhas, nuvens, plantas do rio... Cada peça vira um grupo com o
nome do jogo, no tamanho original do pacote (o jogo escolhe a escala). Todas usam a mesma textura de paleta (15 kB).
Uso: python cenario.py PASTA_DO_PACOTE PASTA_DO_JOGO"""
import sys
from pathlib import Path

import bpy

G = Path(sys.argv[1]) / "addons" / "kaykit_medieval_hexagon_pack" / "Assets" / "gltf"
JOGO = Path(sys.argv[2])
B, N, P, NAT = "buildings", "buildings/neutral", "decoration/props", "decoration/nature"
PECAS = {
    # vila
    "casa_a": f"{B}/green/building_home_A_green", "casa_b": f"{B}/yellow/building_home_B_yellow", "casa_c": f"{B}/yellow/building_home_A_yellow",
    "moinho": f"{B}/yellow/building_windmill_yellow", "poco": f"{B}/green/building_well_green", "mercado": f"{B}/yellow/building_market_yellow",
    "taverna": f"{B}/green/building_tavern_green", "igreja": f"{B}/yellow/building_church_yellow", "ferreiro": f"{B}/green/building_blacksmith_green",
    "quartel": f"{B}/yellow/building_barracks_yellow", "moinho_agua": f"{B}/green/building_watermill_green", "serraria": f"{B}/yellow/building_lumbermill_yellow",
    "mina": f"{B}/green/building_mine_green", "arquearia": f"{B}/green/building_archeryrange_green", "celeiro": f"{N}/building_grain",
    "andaime": f"{N}/building_scaffolding", "palco": f"{N}/building_stage_A", "torre_vigia": f"{B}/yellow/building_tower_A_yellow",
    # muros e cercas
    "muro": f"{N}/wall_straight", "muro_portao": f"{N}/wall_straight_gate", "muro_canto": f"{N}/wall_corner_A_outside",
    "cerca_madeira": f"{N}/fence_wood_straight", "cerca_pedra": f"{N}/fence_stone_straight",
    # objetos
    "barril": f"{P}/barrel", "balde_flechas": f"{P}/bucket_arrows", "caixa": f"{P}/crate_A_big", "caixa_p": f"{P}/crate_B_small",
    "caixote": f"{P}/crate_long_A", "bandeira_azul": f"{P}/flag_blue", "bandeira_vermelho": f"{P}/flag_red", "bandeira_amarela": f"{P}/flag_yellow",
    "saco": f"{P}/sack", "alvo": f"{P}/target", "tenda": f"{P}/tent", "armas": f"{P}/weaponrack", "carrinho": f"{P}/wheelbarrow",
    "toras": f"{P}/resource_lumber", "pedras_cortadas": f"{P}/resource_stone", "palete": f"{P}/pallet",
    # natureza
    "nuvem": f"{NAT}/cloud_big", "nuvem_p": f"{NAT}/cloud_small", "colina": f"{NAT}/hills_A_trees", "colina_b": f"{NAT}/hills_B_trees",
    "colina_nua": f"{NAT}/hills_C", "montanha": f"{NAT}/mountain_A_grass_trees", "montanha_b": f"{NAT}/mountain_B_grass",
    "montanha_c": f"{NAT}/mountain_C", "montanha_nua": f"{NAT}/mountain_A", "rocha_a": f"{NAT}/rock_single_A", "rocha_c": f"{NAT}/rock_single_C",
    "rocha_d": f"{NAT}/rock_single_D", "rocha_e": f"{NAT}/rock_single_E", "toco": f"{NAT}/tree_single_A_cut", "tocos": f"{NAT}/trees_A_cut",
    "arvores_m": f"{NAT}/trees_A_medium", "arvores_p": f"{NAT}/trees_B_small", "arvores_g": f"{NAT}/trees_A_large",
    "lirio": f"{NAT}/waterlily_A", "lirio_b": f"{NAT}/waterlily_B", "planta_agua": f"{NAT}/waterplant_B", "junco": f"{NAT}/waterplant_C",
}
bpy.ops.wm.read_factory_settings(use_empty=True)
for k, (nome, arq) in enumerate(PECAS.items()):
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(G / f"{arq}.gltf"))
    novos = [o for o in bpy.data.objects if o not in antes]
    grupo = bpy.data.objects.new(nome, None)
    bpy.context.scene.collection.objects.link(grupo)
    for o in novos:
        o.name = f"{nome}__{o.name}"
        if o.parent is None:
            o.parent = grupo
    caixa = [0, 0]
    for o in novos:
        if o.type == "MESH":
            zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
            caixa = [min(caixa[0], min(zs)), max(caixa[1], max(zs))]
    print(nome, "altura", round(caixa[1], 2), "base", round(caixa[0], 2), flush=True)
bpy.ops.export_scene.gltf(filepath=str(JOGO / "modelos" / "cenario.glb"), export_format="GLB", export_yup=True, export_animations=False,
                          export_cameras=False, export_lights=False)
print("cenario.glb", (JOGO / "modelos" / "cenario.glb").stat().st_size // 1024, "kB")
