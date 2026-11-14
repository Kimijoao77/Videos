"""Bichos e dinossauros da leva 3 a partir de modelos livres da internet (Quaternius, CC0: Ultimate Animated Animals,
Animated Dinosaurs e Easy Enemy), retrabalhados um por um no Blender: malha suavizada, pelo e couro pintados nos
vértices (dorso escuro, barriga clara, manchas, sombra nas dobras), olhos com brilho e a peça do time (coleira, manta,
sela, crista...) presa no osso certo. As animações são as do próprio modelo, com os nomes do jogo.
Uso: python bichos_reais.py PASTA_DOS_PACOTES PASTA_DO_JOGO [modelos] [cartas] [previa=PASTA] [so:lobo,rex]"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import bmesh  # noqa: E402  (só existe depois do bpy)
from mathutils import Matrix, Vector, noise

import kit
from kit import TIME, TIME2, caixa, cilindro, cone, esfera, prisma, tr, tubo

PACOTES, JOGO = Path(sys.argv[1]), Path(sys.argv[2])
ARGS = sys.argv[3:]
QUAIS = [a for a in ARGS if not a.startswith(("so:", "previa="))] or ["modelos", "cartas"]
SO = set(next((a[3:].split(",") for a in ARGS if a.startswith("so:")), []))
PREVIA = next((Path(a[7:]) for a in ARGS if a.startswith("previa=")), None)
AZUL = (0.16, 0.45, 0.95)
OURO, COURO, MADEIRA, BRANCO = "#F2B632", "#6B4526", "#7A4E2A", "#F7F3EA"


def toro(R, r, seg=24, an=8):
    vs, fs = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(an):
            b = 2 * math.pi * j / an
            vs.append(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(an):
            fs.append((i * an + j, ((i + 1) % seg) * an + j, ((i + 1) % seg) * an + (j + 1) % an, i * an + (j + 1) % an))
    return vs, fs


def pena(larg, comp, esp=0.03):
    return tr(prisma([(0, 0), (larg, comp * 0.45), (0, comp), (-larg, comp * 0.45)], esp, esp * 0.3), rot=(0, 0, 90))


# ------------------------------------------------------------------ cada bicho
# arq, comprimento no jogo (casas), animações, cores (material → cor; ("cor", "pelo") = com manchas, dorso vivo e barriga
# clara) e as faixas do time: [(osso, posição ao longo do osso 0..1, largura em casas, cor)]
BICHOS = {
    "lobo": dict(tris=4500, arq="animals_pack/Wolf", compr=1.75,
                 anim={"parado": "Idle", "andar": "Gallop", "atacar": "Attack"},
                 cores={"Main": ("#7B838F", "pelo"), "Main_Light": ("#DADFE6", "pelo"), "Eyes_Black": "#131316", "Nose": "#222228"},
                 faixas=[("Neck2", 0.5, 0.11, TIME)]),
    "touro": dict(tris=6500, arq="animals_pack/Bull", compr=2.5,
                  anim={"parado": "Idle", "andar": "Gallop", "atacar": "Attack_Headbutt"},
                  cores={"Main": ("#4B3A32", "pelo"), "Muzzle": "#C8A385", "Hooves": "#2A2320", "Main_Light": ("#7A6254", "pelo"), "Eye_Black": "#141416",
                         "Eye_White": "#F2EEE6", "Horns": "#EFE6D0"},
                  faixas=[("Torso2", 0.5, 0.5, TIME)]),
    "aranha": dict(tris=3600, arq="easy_enemies_pack/Spider", compr=1.2,
                   anim={"parado": "Spider_Idle", "andar": "Spider_Walk", "atacar": "Spider_Attack"},
                   cores={"Material": ("#3A3344", "pelo"), "Material.001": TIME}, faixas=[]),
    "vespa": dict(tris=4200, arq="easy_enemies_pack/Wasp", compr=0.95,
                  anim={"parado": "Wasp_Flying", "andar": "Wasp_Flying", "atacar": "Wasp_Attack"},
                  cores={"Black": "#241E26", "Orange": TIME, "Yellow": "#F7C21E", "LightBlue": "#DCEFFF"}, faixas=[]),
    "raptor": dict(tris=4500, arq="dinosaurs_pack/Velociraptor", compr=2.0,
                   anim={"parado": "Velociraptor_Idle", "andar": "Velociraptor_Run", "atacar": "Velociraptor_Attack", "saltar": "Velociraptor_Jump"},
                   cores={"LightBrown": "#F0D9A8", "Brown": ("#C9813F", "pelo"), "Black": "#17151A"},
                   faixas=[("Neck", 0.45, 0.12, TIME)]),
    "rex": dict(tris=8000, arq="dinosaurs_pack/Trex", compr=4.4,
                anim={"parado": "TRex_Idle", "andar": "TRex_Walk", "atacar": "TRex_Attack"},
                cores={"LightYellow": "#E8D7A2", "LightGreen": ("#7DAA58", "pelo"), "Green": ("#4A7A36", "pelo"), "Black": "#17151A", "Red": "#9A3644"},
                faixas=[("Neck", 0.5, 0.22, TIME), ("Torso", 0.5, 0.3, TIME)]),
    "triceratops": dict(tris=6500, arq="dinosaurs_pack/Triceratops", compr=3.0,
                        anim={"parado": "Triceratops_Idle", "andar": "Triceratops_Walk", "atacar": "Triceratops_Attack"},
                        cores={"LightBrown": "#D9CDB4", "Purple": ("#6F7F90", "pelo"), "Brown": "#F0E6CC"},
                        faixas=[("Neck", 0.5, 0.22, TIME)]),
}


def faixa(bm, lay, malha, arm, osso, pos, larg, cor, cor_time):
    """Faixa do time pintada no corpo em volta de um osso (coleira, cinta): as faces dessa fatia do corpo trocam de cor."""
    b = arm.data.bones[osso]
    para = malha.matrix_world.inverted() @ arm.matrix_world
    h, t = para @ b.head_local, para @ b.tail_local
    eixo = (t - h).normalized()
    larg = larg / malha.matrix_world.to_scale().x         # casas → unidades da malha
    centro = h + eixo * (t - h).length * pos
    perto = sorted((v.co - centro - eixo * (v.co - centro).dot(eixo)).length for v in bm.verts if abs((v.co - centro).dot(eixo)) < larg * 0.5)
    if not perto:
        return
    lim = perto[len(perto) // 2] * 1.7                    # o que passa disso é outra parte do corpo (perna, rabo, babado)
    c = kit.cor_lin(cor)
    magica = cor in (TIME, TIME2) and cor_time is None
    for f in bm.faces:
        d = f.calc_center_median() - centro
        s = d.dot(eixo)
        if abs(s) > larg * 0.5 or (d - eixo * s).length > lim:
            continue
        for lp in f.loops:
            k = 0.8 + 0.35 * max(lp[lay][0], lp[lay][1], lp[lay][2])
            lp[lay] = (min(1.0, c[0] * k), 0.0, min(1.0, c[2] * k), 1.0) if magica else tuple(min(1.0, c[q] * k) for q in range(3)) + (1.0,)


def preparar(nome, cor_time=None):
    """Importa o bicho, suaviza, deixa no tamanho do jogo, pinta e põe as faixas do time. Devolve (raiz, armação, malha, ações)."""
    kit.COR_TIME = cor_time
    B = BICHOS[nome]
    antes = set(bpy.data.objects)
    acoes_antes = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=str(PACOTES / (B["arq"] + ".glb")))
    novos = [o for o in bpy.data.objects if o not in antes]
    for o in list(novos):
        if o.type == "MESH" and o.name.startswith("Icosphere"):
            novos.remove(o)
            bpy.data.objects.remove(o)
    arm = next(o for o in novos if o.type == "ARMATURE")
    malha = next(o for o in novos if o.type == "MESH")
    raiz = arm.parent or arm
    acoes = animacoes(arm, nome, acoes_antes)
    me = malha.data
    mats = [s.material.name if s.material.name in B["cores"] else re.sub(r"\.\d+$", "", s.material.name) for s in malha.material_slots]
    # 1) costura as faces soltas (o modelo vem facetado) e suaviza com uma subdivisão antes dos ossos
    bm = bmesh.new()
    bm.from_mesh(me)
    tam = max((v.co.length for v in bm.verts), default=1.0)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=tam * 2e-4)
    bm.to_mesh(me)
    bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = malha
    malha.select_set(True)
    md = malha.modifiers.new("suave", "SUBSURF")
    md.levels = md.render_levels = 1
    while malha.modifiers[0].name != "suave":
        bpy.ops.object.modifier_move_up(modifier="suave")
    bpy.ops.object.modifier_apply(modifier="suave")
    if len(me.polygons) * 2 > B["tris"]:                  # celular: enxuga a malha até o teto de triângulos do bicho
        md = malha.modifiers.new("enxuga", "DECIMATE")
        md.ratio = B["tris"] / (len(me.polygons) * 2)
        while malha.modifiers[0].name != "enxuga":
            bpy.ops.object.modifier_move_up(modifier="enxuga")
        bpy.ops.object.modifier_apply(modifier="enxuga")
    for p in me.polygons:
        p.use_smooth = True
    # 2) tamanho e lugar pelo bicho parado (a pose de descanso de alguns vem deitada)
    posar(arm, acoes["parado"], 1)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = malha.evaluated_get(dg)
    pts = [ev.matrix_world @ v.co for v in ev.data.vertices]
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    esc = B["compr"] / max(mx.x - mn.x, mx.y - mn.y)
    if mx.x - mn.x > mx.y - mn.y:                         # veio de lado: gira para olhar para -Y
        raiz.rotation_euler = (0, 0, math.radians(-90))
    raiz.scale = (esc, esc, esc)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = malha.evaluated_get(dg)
    pos = [ev.matrix_world @ v.co for v in ev.data.vertices]
    nor = [(ev.matrix_world.to_3x3() @ v.normal).normalized() for v in ev.data.vertices]
    mn = Vector([min(p[i] for p in pos) for i in range(3)])
    mx = Vector([max(p[i] for p in pos) for i in range(3)])
    raiz.location = (raiz.location.x - (mn.x + mx.x) / 2, raiz.location.y - (mn.y + mx.y) / 2, raiz.location.z - mn.z)
    z0, z1 = mn.z, mx.z
    # 3) pintura nos vértices: cor do material, dorso vivo, barriga clara, manchas e sombra nas dobras
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    lay = bm.loops.layers.float_color.get("Col") or bm.loops.layers.float_color.new("Col")
    dobra = {}
    for v in bm.verts:
        s, n = 0.0, 0
        for e in v.link_edges:
            d = e.other_vert(v).co - v.co
            if d.length > 1e-12:
                s += v.normal.dot(d.normalized())
                n += 1
        dobra[v.index] = max(0.0, s / n) if n else 0.0
    for f in bm.faces:
        esp = B["cores"].get(mats[f.material_index], "#888888")
        pelo = isinstance(esp, tuple)
        cor = esp[0] if pelo else esp
        magica = cor in (TIME, TIME2) and cor_time is None
        c = kit.cor_lin(cor)
        for lp in f.loops:
            i = lp.vert.index
            w, nz = pos[i], nor[i].z
            k = 0.88 + 0.18 * (w.z - z0) / (z1 - z0 + 1e-9)
            k *= 1 - 0.5 * min(1.0, dobra[i] * 1.5)
            clara = 0.0
            if pelo:
                k *= 1 + 0.08 * noise.noise(w * (20 / B["compr"]))
                k *= 0.9 + 0.14 * max(0.0, nz)
                clara = max(0.0, -nz - 0.2) * 0.5
            if magica:
                lp[lay] = (min(1.0, c[0] * k), 0.0, min(1.0, c[2] * k), 1.0)
            else:
                lp[lay] = tuple(min(1.0, c[j] * k + (1 - c[j] * k) * clara * 0.4) for j in range(3)) + (1.0,)
    for osso, p, larg, cor in B["faixas"]:
        faixa(bm, lay, malha, arm, osso, p, larg, cor, cor_time)
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(kit.material())
    arm.animation_data.action = None
    for t in arm.animation_data.nla_tracks:
        t.mute = False
    return raiz, arm, malha, acoes


def animacoes(arm, nome, manter=()):
    """Fica só com as animações do jogo, com os nomes do jogo."""
    quero = BICHOS[nome]["anim"]
    ad = arm.animation_data
    achou = {}
    for tr_ in list(ad.nla_tracks):
        a = tr_.strips[0].action
        base = re.sub(r"\.\d+$", "", a.name)
        curto = base.split("|")[1] if "|" in base else base
        curto = curto.rsplit("_", 1)[0] if curto.endswith(("Armature", "AnimalArmature", "SpiderArmature", "WaspArmature")) else curto
        usos = [k for k, v in quero.items() if v == curto]
        if not usos:
            ad.nla_tracks.remove(tr_)
            continue
        achou[usos[0]] = a
        tr_.name = tr_.strips[0].name = a.name = usos[0]
        for extra in usos[1:]:                            # a mesma animação com dois nomes (vespa: parado = andar)
            b = a.copy()
            b.name = extra
            t2 = ad.nla_tracks.new()
            t2.name = extra
            t2.strips.new(extra, 1, b).name = extra
            achou[extra] = b
    ad.action = None
    usadas = set(achou.values())
    for a in list(bpy.data.actions):
        if a not in usadas and a not in manter:
            bpy.data.actions.remove(a)
    return achou


def exportar(arq):
    bpy.ops.export_scene.gltf(filepath=str(arq), export_format="GLB", export_apply=False, export_yup=True,
                              export_vertex_color="MATERIAL", export_materials="EXPORT", export_normals=True,
                              export_animations=True, export_animation_mode="ACTIONS", export_force_sampling=True,
                              export_optimize_animation_size=True, export_def_bones=False, export_cameras=False, export_lights=False)


def posar(arm, a, quadro):
    for t in arm.animation_data.nla_tracks:
        t.mute = True
    arm.animation_data.action = a
    bpy.context.scene.frame_set(quadro)


if PREVIA:
    PREVIA.mkdir(parents=True, exist_ok=True)
    for nome, B in BICHOS.items():
        if SO and nome not in SO:
            continue
        kit.limpar()
        raiz, arm, malha, ac = preparar(nome, AZUL)
        alt = B["compr"] * 0.6
        for qual, az in (("parado", -35), ("andar", -90), ("atacar", -145)):
            a = ac[qual]
            posar(arm, a, max(1, int(a.frame_range[1] * 0.45)))
            kit.foto(PREVIA / f"{nome}_{qual}.png", alvo=(0, 0, alt * 0.55), dist=max(2.0, B["compr"] * 2.0), az=az, el=16, larg=420, alt=420, amostras=12)
        print("prévia", nome, len(malha.data.polygons), "faces", sorted(ac), flush=True)

if "modelos" in QUAIS:
    for nome in BICHOS:
        if SO and nome not in SO:
            continue
        kit.limpar()
        raiz, arm, malha, ac = preparar(nome)
        arq = JOGO / "modelos" / f"{nome}.glb"
        exportar(arq)
        print("modelo", nome, arq.stat().st_size // 1024, "kB", sorted(ac), flush=True)


# ------------------------------------------------------------------ arte das cartas (em azul, fundo transparente)
CARTAS = {
    "lobos": ("lobo", [(0.05, 0, 0, "atacar", 0.3), (-0.85, 0.65, 22, "andar", 0.3), (0.9, 0.75, -18, "parado", 0.2)], (0, 0.3, 0.42), 4.8, -22, 12),
    "touro": ("touro", [(0, 0, 0, "andar", 0.35)], (0, 0, 0.75), 4.8, -28, 10),
    "aranhas": ("aranha", [(0, 0, 0, "atacar", 0.4), (-0.85, 0.7, 25, "andar", 0.3), (0.85, 0.75, -25, "andar", 0.7), (0.05, 1.4, 0, "parado", 0.2)], (0, 0.55, 0.22), 5.0, -20, 24),
    "vespas": ("vespa", [(0, 0, 0, "atacar", 0.4), (-0.85, 0.6, 20, "andar", 0.2), (0.85, 0.65, -20, "andar", 0.6)], (0, 0.3, 0.5), 4.2, -18, 10),
    "raptores": ("raptor", [(0.45, 0, -10, "atacar", 0.45), (-0.6, 0.9, 18, "andar", 0.4)], (0, 0.3, 0.6), 4.8, -26, 10),
    "rex": ("rex", [(0, 0, 0, "atacar", 0.3)], (0, 0, 1.3), 8.4, -30, 8),
    "triceratops": ("triceratops", [(0, 0, 0, "andar", 0.3)], (0, 0, 0.8), 5.8, -30, 10),
}
if "cartas" in QUAIS:
    for carta, (nome, onde, alvo, dist, az, el) in CARTAS.items():
        if SO and carta not in SO and nome not in SO:
            continue
        kit.limpar()
        for x, y, giro, qual, fr in onde:
            raiz, arm, malha, ac = preparar(nome, AZUL)
            raiz.location = (raiz.location.x + x, raiz.location.y + y, raiz.location.z)
            raiz.rotation_euler = (0, 0, raiz.rotation_euler.z + math.radians(giro))
            for t in arm.animation_data.nla_tracks:
                t.mute = True
            a = ac[qual].copy()                           # cada bicho numa hora diferente da animação
            for fc in a.fcurves:
                for kp in fc.keyframe_points:
                    kp.co.x -= fr * ac[qual].frame_range[1] - 1
                    kp.handle_left.x -= fr * ac[qual].frame_range[1] - 1
                    kp.handle_right.x -= fr * ac[qual].frame_range[1] - 1
            arm.animation_data.action = a
        bpy.context.scene.frame_set(1)
        kit.foto(JOGO / "cartas" / f"{carta}.png", alvo=alvo, dist=dist, az=az, el=el, larg=512, alt=512, amostras=48, transparente=True)
        print("carta", carta, flush=True)
