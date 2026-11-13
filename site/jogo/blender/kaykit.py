"""Prepara os personagens do pacote KayKit Adventurers (Kay Lousberg, CC0) para o jogo: fica só com as armas e as
animações usadas, junta o corpo num objeto só (menos chamadas de desenho) e exporta um GLB leve por personagem.
Também tira a foto da carta. Uso: python kaykit.py PASTA_DO_PACOTE PASTA_DO_JOGO [fotos]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector

import kit

PACOTE = Path(sys.argv[1]) / "addons" / "kaykit_character_pack_adventures" / "Characters" / "gltf"
JOGO = Path(sys.argv[2])
FOTOS = "fotos" in sys.argv

# saída: (arquivo, acessórios que ficam, {nome no jogo: animação do pacote}, pose da carta (animação, quadro))
QUEM = {
    "cavaleiro": ("Knight", ["1H_Sword", "Round_Shield", "Knight_Helmet", "Knight_Cape"],
                  {"parado": "Idle", "andar": "Walking_A", "atacar": "1H_Melee_Attack_Chop"}, ("1H_Melee_Attack_Chop", 6)),
    "besteiro": ("Rogue_Hooded", ["2H_Crossbow", "Rogue_Cape"],
                 {"parado": "2H_Ranged_Aiming", "andar": "Walking_A", "atacar": "2H_Ranged_Shoot"}, ("2H_Ranged_Aiming", 2)),
    "gigante": ("Barbarian", ["2H_Axe", "Barbarian_Hat", "Barbarian_Cape"],
                {"parado": "2H_Melee_Idle", "andar": "Walking_A", "atacar": "2H_Melee_Attack_Chop"}, ("2H_Melee_Idle", 4)),
    "mago": ("Mage", ["2H_Staff", "Mage_Hat", "Mage_Cape"],
             {"parado": "Idle", "andar": "Walking_A", "atacar": "Spellcast_Shoot"}, ("Spellcast_Raise", 10)),
    "bandido": ("Rogue", ["Knife", "Knife_Offhand", "Rogue_Cape"],
                {"parado": "Idle", "andar": "Running_A", "atacar": "1H_Melee_Attack_Stab"}, ("Running_A", 4)),
}

medidas = {}
for saida, (arq, manter, anims, pose) in QUEM.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(PACOTE / f"{arq}.glb"))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    corpo = []
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        if o.parent_type == "BONE" or o.parent is None:      # acessório preso num osso (ou a bolinha solta)
            if o.name not in manter:
                bpy.data.objects.remove(o)
        else:
            corpo.append(o)
    # junta as partes do corpo num objeto só
    bpy.ops.object.select_all(action="DESELECT")
    for o in corpo:
        o.select_set(True)
    bpy.context.view_layer.objects.active = corpo[0]
    bpy.ops.object.join()
    corpo[0].name = "corpo"
    # altura (com a pose de descanso)
    zs = [(o.matrix_world @ Vector(c)).z for o in bpy.data.objects if o.type == "MESH" for c in o.bound_box]
    medidas[saida] = round(max(zs), 3)
    # só as animações usadas, com o nome do jogo
    quero = {v: k for k, v in anims.items()}
    ad = rig.animation_data
    acao_pose = bpy.data.actions.get(pose[0] + "_Rig").copy()
    acao_pose.name = "_pose"
    for tr in list(ad.nla_tracks):
        nome = tr.name
        if nome in quero:
            tr.name = quero[nome]
            tr.strips[0].name = quero[nome]
            tr.strips[0].action.name = quero[nome]
            tr.mute = False
        else:
            ad.nla_tracks.remove(tr)
    if FOTOS:
        (JOGO / "cartas").mkdir(exist_ok=True)
        ad.action = acao_pose
        for tr in ad.nla_tracks:
            tr.mute = True
        bpy.context.scene.frame_set(pose[1])
        alt = medidas[saida]
        kit.foto(JOGO / "cartas" / f"{saida}.png", alvo=(0, 0, alt * 0.52), dist=alt * 2.35, az=-30, el=10, larg=256, alt=256, amostras=40, transparente=True)
        for o in list(bpy.data.objects):
            if o.name.startswith("_foto"):
                bpy.data.objects.remove(o)
        ad.action = None
        for tr in ad.nla_tracks:
            tr.mute = False
    for a in list(bpy.data.actions):
        if a.name not in anims:
            bpy.data.actions.remove(a)
    bpy.ops.export_scene.gltf(filepath=str(JOGO / "modelos" / f"{saida}.glb"), export_format="GLB", export_yup=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_cameras=False, export_lights=False, export_optimize_animation_size=True,
                              export_force_sampling=True, export_def_bones=False)
    print("kaykit", saida, medidas[saida], (JOGO / "modelos" / f"{saida}.glb").stat().st_size // 1024, "kB", flush=True)

(JOGO / "modelos" / "kaykit.json").write_text(json.dumps(medidas))
