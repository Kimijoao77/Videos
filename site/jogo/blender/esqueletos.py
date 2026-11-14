"""Prepara os esqueletos do pacote KayKit Skeletons (Kay Lousberg, CC0) para o jogo: põe a arma na mão (osso
handslot), junta o corpo num objeto só, fica só com as animações usadas e exporta um GLB por personagem.
Com "fotos", tira também a foto da carta. Uso: python esqueletos.py PASTA_DO_PACOTE PASTA_DO_JOGO [fotos]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector

import kit

BASE = Path(sys.argv[1]) / "addons" / "kaykit_character_pack_skeletons"
JOGO = Path(sys.argv[2])
FOTOS = "fotos" in sys.argv
SO = set(next((a[3:].split(",") for a in sys.argv if a.startswith("so:")), []))
D = (0, -0.079, 0)                                   # onde a arma fica no osso da mão (igual ao pacote dos aventureiros)

# saída: (personagem, [(arma, osso, posição)], {nome no jogo: animação}, pose da carta (animação, quadro))
QUEM = {
    "esqueleto": ("Skeleton_Minion", [("Skeleton_Blade", "handslot.r", D)],
                  {"parado": "Idle", "andar": "Running_A", "atacar": "1H_Melee_Attack_Chop", "nascer": "Spawn_Ground_Skeletons"}, ("1H_Melee_Attack_Chop", 8)),
    "guerreiro": ("Skeleton_Warrior", [("Skeleton_Axe", "handslot.r", D), ("Skeleton_Shield_Large_A", "handslot.l", (0, -0.095, 0.156))],
                  {"parado": "Idle_Combat", "andar": "Walking_D_Skeletons", "atacar": "2H_Melee_Attack_Spin", "nascer": "Spawn_Ground_Skeletons"}, ("Idle_Combat", 2)),
    "necromante": ("Skeleton_Mage", [("Skeleton_Staff", "handslot.r", D)],
                   {"parado": "Idle", "andar": "Walking_D_Skeletons", "atacar": "Spellcast_Shoot", "invocar": "Spellcast_Summon", "nascer": "Spawn_Air"},
                   ("Spellcast_Summon", 14)),
    "assassino": ("Skeleton_Rogue", [("Skeleton_Blade", "handslot.r", D), ("Skeleton_Blade", "handslot.l", D)],
                  {"parado": "Idle_Combat", "andar": "Running_C", "atacar": "Dualwield_Melee_Attack_Stab", "saltar": "1H_Melee_Attack_Jump_Chop",
                   "nascer": "Spawn_Ground_Skeletons"}, ("1H_Melee_Attack_Jump_Chop", 12)),
}

medidas = json.loads((JOGO / "modelos" / "kaykit.json").read_text())
for saida, (arq, armas, anims, pose) in QUEM.items():
    if SO and saida not in SO:
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(BASE / "Characters" / "gltf" / f"{arq}.glb"))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.parent is None:
            bpy.data.objects.remove(o)                   # a bolinha solta do pacote
    corpo = [o for o in bpy.data.objects if o.type == "MESH" and o.parent_type != "BONE"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in corpo:
        o.select_set(True)
    bpy.context.view_layer.objects.active = corpo[0]
    bpy.ops.object.join()
    corpo[0].name = "corpo"
    for (arma, osso, pos) in armas:
        antes = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(BASE / "Assets" / "gltf" / f"{arma}.gltf"))
        for o in set(bpy.data.objects) - antes:
            if o.type != "MESH":
                continue
            o.parent = rig
            o.parent_type = "BONE"
            o.parent_bone = osso
            o.matrix_parent_inverse.identity()
            o.location = pos
            o.rotation_euler = (0, 0, 0)
            o.name = arma
    bpy.context.view_layer.update()
    zs = [(o.matrix_world @ Vector(c)).z for o in bpy.data.objects if o.type == "MESH" and o.parent_type != "BONE" for c in o.bound_box]
    medidas[saida] = round(max(zs), 3)
    quero = {v: k for k, v in anims.items()}
    ad = rig.animation_data
    acao_pose = bpy.data.actions.get(pose[0] + "_Rig").copy()
    acao_pose.name = "_pose"
    for tr in list(ad.nla_tracks):
        if tr.name in quero:
            tr.strips[0].action.name = quero[tr.name]
            tr.strips[0].name = quero[tr.name]
            tr.name = quero[tr.name]
            tr.mute = False
        else:
            ad.nla_tracks.remove(tr)
    if FOTOS:
        ad.action = acao_pose
        for tr in ad.nla_tracks:
            tr.mute = True
        bpy.context.scene.frame_set(pose[1])
        alt = medidas[saida]
        kit.foto(JOGO / "cartas" / f"{saida}.png", alvo=(0, 0, alt * 0.48), dist=alt * 3.1, az=-30, el=10, larg=512, alt=512, amostras=48, transparente=True)
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
    print("esqueleto", saida, medidas[saida], (JOGO / "modelos" / f"{saida}.glb").stat().st_size // 1024, "kB", flush=True)

(JOGO / "modelos" / "kaykit.json").write_text(json.dumps(medidas))
