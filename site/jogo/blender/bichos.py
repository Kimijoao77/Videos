"""Cartas da leva 3, modeladas uma por uma no Blender por código (kit.py): lobo, touro, aranha, vespa, raptor,
tiranossauro, tricerátops, bárbaro e caçadora ganham ossos e animações próprias (parado, andar, atacar e, no raptor,
saltar) que vão dentro do GLB; espírito de fogo, canhão, estábulo, poço mágico, barril de bandidos, meteoro e lápides
são peças articuladas que o jogo anima (o canhão gira, as portas do estábulo abrem, a chama do espírito tremula).
Medidas em casas da arena; frente = -Y do Blender (vira +Z no jogo); a cor do time é a cor mágica (magenta) do kit.
Uso: python bichos.py PASTA_DO_JOGO [modelos] [cartas] [previa=PASTA] [so:lobo,touro]"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector

import kit
import personagens as P
from kit import TIME, TIME2, Modelo, caixa, capsula, cilindro, cone, esfera, prisma, torno, tr, tubo, rx

JOGO = Path(sys.argv[1])
ARGS = sys.argv[2:]
QUAIS = [a for a in ARGS if not a.startswith(("so:", "previa="))] or ["modelos", "cartas"]
SO = set(next((a[3:].split(",") for a in ARGS if a.startswith("so:")), []))
PREVIA = next((Path(a[7:]) for a in ARGS if a.startswith("previa=")), None)
AZUL = (0.16, 0.45, 0.95)

BRANCO, PRETO, OURO = P.BRANCO, P.PRETO, P.OURO
COURO, COURO2, MADEIRA, MADEIRA2 = P.COURO, P.COURO2, P.MADEIRA, P.MADEIRA2
PEDRA, PEDRA2 = "#9E9B96", "#7A7772"
FERRO, FERRO2 = "#3A3F47", "#23272D"


# ------------------------------------------------------------------ formas e detalhes que se repetem
def toro(R, r, seg=24, an=8):
    """Argola deitada (em volta do eixo Z)."""
    vs, fs = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(an):
            b = 2 * math.pi * j / an
            vs.append(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(an):
            i2, j2 = (i + 1) % seg, (j + 1) % an
            fs.append((i * an + j, i2 * an + j, i2 * an + j2, i * an + j2))
    return vs, fs


def olho(m, peca, pos, lado, r, iris="#F5C542", brava=0.0, sobr=None):
    """Olho de desenho: branco, íris, pupila, brilho e (se tiver) a sobrancelha brava por cima."""
    x, y, z = pos
    m.add(peca, tr(esfera(1, 14, 10), (x, y, z), esc=(r * 0.9, r * 0.75, r * 1.1)), BRANCO, (0.92, 1.05))
    m.add(peca, tr(esfera(1, 12, 8), (x + 0.1 * r * lado, y - 0.42 * r, z - 0.05 * r), esc=(r * 0.62, r * 0.42, r * 0.8)), iris, (0.85, 1.15))
    m.add(peca, tr(esfera(1, 10, 6), (x + 0.14 * r * lado, y - 0.7 * r, z - 0.05 * r), esc=(r * 0.3, r * 0.2, r * 0.5)), PRETO, (1, 1))
    m.add(peca, tr(esfera(r * 0.17, 6, 5), (x + 0.02 * r * lado, y - 0.76 * r, z + 0.4 * r)), BRANCO, (1.3, 1.3))
    if sobr:
        m.add(peca, tr(caixa(r * 2.3, r * 0.6, r * 0.5, r * 0.18), (x, y - 0.2 * r, z + 1.08 * r), rot=(0, -brava * lado, 0)), sobr, (1, 1))


def pena(larg, comp, esp=0.016):
    """Pena achatada de lado (no plano YZ), apontando para +Z."""
    return tr(prisma([(0, 0), (larg, comp * 0.45), (0, comp), (-larg, comp * 0.45)], esp, esp * 0.35), rot=(0, 0, 90))


# ------------------------------------------------------------------ ossos e animações
def seno(t, f=1.0, fase=0.0):
    return math.sin(2 * math.pi * (f * t + fase))


def curva(t, pts):
    """Valor que passa pelos pontos (t, v) com entrada e saída suaves."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            q = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
            q = q * q * (3 - 2 * q)
            return v0 + (v1 - v0) * q
    return pts[-1][1]


def pernas4(t, amp, galope=False, nomes=("pfd", "pfe", "ptd", "pte")):
    """Quatro patas: trote (diagonais juntas) ou galope (as da frente juntas, depois as de trás)."""
    fases = (0, 0.12, 0.5, 0.62) if galope else (0, 0.5, 0.5, 0)
    return {n: (amp * seno(t, 1, f), 0, 0) for n, f in zip(nomes, fases)}


def armar(m, raiz):
    """Troca a hierarquia de peças por um esqueleto: um osso por peça (no pivô, apontando para trás, assim os eixos do
    osso são os do mundo) e cada malha presa no seu osso."""
    bpy.context.view_layer.update()
    dados = bpy.data.armatures.new(m.nome + "_ossos")
    arm = bpy.data.objects.new(m.nome, dados)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for nome in m.ordem:
        b = dados.edit_bones.new(nome)
        b.head = m.pecas[nome]["pivo"]
        b.tail = m.pecas[nome]["pivo"] + Vector((0, 0.05, 0))
        b.roll = 0.0
    for nome in m.ordem:
        pai = m.pecas[nome]["pai"]
        if pai:
            dados.edit_bones[nome].parent = dados.edit_bones[pai]
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    for nome, o in m.objs.items():
        if o.type != "MESH":
            continue
        mw = o.matrix_world.copy()
        o.parent = arm
        o.parent_type = "BONE"
        o.parent_bone = nome
        o.matrix_world = mw
        o.name = "m_" + nome
    for o in list(m.objs.values()):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    bpy.data.objects.remove(raiz)
    return arm


def acao(arm, nome, n, f):
    """Grava a ação com n quadros (24 por segundo). f(t), t de 0 a 1, devolve {osso: (rx, ry, rz)} em graus ou
    {osso: ((rx, ry, rz), (x, y, z))}; ossos que faltam ficam no lugar. Vai para uma trilha do NLA (o exportador
    leva cada trilha como uma animação com o nome dela)."""
    ad = arm.animation_data or arm.animation_data_create()
    a = bpy.data.actions.new(nome)
    a.use_fake_user = True
    ad.action = a
    for q in range(n + 1):
        val = f(q / n)
        for pb in arm.pose.bones:
            pb.rotation_mode = "XYZ"
            v = val.get(pb.name, (0, 0, 0))
            rot, loc = (v[0], v[1]) if len(v) == 2 else (v, (0, 0, 0))
            pb.rotation_euler = [math.radians(x) for x in rot]
            pb.location = loc
            pb.keyframe_insert("rotation_euler", frame=q + 1)
            pb.keyframe_insert("location", frame=q + 1)
    trilha = ad.nla_tracks.new()
    trilha.name = nome
    trilha.strips.new(nome, 1, a)
    ad.action = None
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    return a


def exportar_animado(arq):
    bpy.ops.export_scene.gltf(filepath=str(arq), export_format="GLB", export_apply=True, export_yup=True,
                              export_vertex_color="MATERIAL", export_materials="EXPORT", export_normals=True,
                              export_animations=True, export_animation_mode="ACTIONS", export_force_sampling=True,
                              export_optimize_animation_size=True, export_def_bones=False, export_cameras=False, export_lights=False)


def posar(arm, a, quadro):
    ad = arm.animation_data
    for t in ad.nla_tracks:
        t.mute = True
    ad.action = a
    bpy.context.scene.frame_set(quadro)


# ================================================================== bichos (com ossos)
def lobo():
    m = Modelo("lobo", 1.0)
    PEL, PEL2, CLARO, ROSA = "#8F98A6", "#5F6775", "#DDE2E9", "#E7A3A8"
    m.peca("corpo", (0, 0, 0.5))
    m.peca("cabeca", (0, -0.34, 0.66), "corpo")
    m.peca("queixo", (0, -0.55, 0.66), "cabeca")
    m.peca("cauda", (0, 0.4, 0.62), "corpo")
    PERNAS = (("pfd", -0.115, -0.25), ("pfe", 0.115, -0.25), ("ptd", -0.12, 0.27), ("pte", 0.12, 0.27))
    for nome, x, y in PERNAS:
        m.peca(nome, (x, y, 0.46), "corpo")
    # tronco: peito alto, cintura fina e garupa; peito e barriga claros, dorso escuro
    m.add("corpo", tr(esfera(1, 18, 10), (0, 0.06, 0.52), rot=(-5, 0, 0), esc=(0.17, 0.4, 0.16)), PEL, (0.72, 1.06))
    m.add("corpo", tr(esfera(1, 16, 10), (0, -0.2, 0.56), esc=(0.2, 0.21, 0.2)), PEL, (0.74, 1.06))
    m.add("corpo", tr(esfera(1, 14, 8), (0, 0.26, 0.53), esc=(0.165, 0.18, 0.16)), PEL, (0.74, 1.05))
    m.add("corpo", tr(esfera(1, 14, 8), (0, -0.3, 0.5), esc=(0.14, 0.12, 0.15)), CLARO, (0.85, 1.05))
    m.add("corpo", tr(esfera(1, 14, 8), (0, 0.02, 0.41), esc=(0.12, 0.3, 0.07)), CLARO, (0.9, 1.05))
    m.add("corpo", tr(esfera(1, 14, 8), (0, 0.04, 0.635), esc=(0.1, 0.36, 0.06)), PEL2, (0.9, 1.05))
    for lado in (-1, 1):                                  # juba
        m.add("corpo", tr(esfera(1, 12, 8), (0.13 * lado, -0.3, 0.6), esc=(0.08, 0.1, 0.13)), PEL, (0.8, 1.05))
    m.add("corpo", tr(esfera(1, 12, 8), (0, -0.27, 0.7), esc=(0.12, 0.12, 0.07)), PEL2, (0.85, 1.05))
    # coleira e lenço do time
    m.add("corpo", tr(toro(0.15, 0.024, 24, 8), (0, -0.36, 0.62), rot=(49, 0, 0)), TIME, (0.9, 1.05))
    m.add("corpo", tr(prisma([(-0.12, 0), (0.12, 0), (0.0, -0.16)], 0.02, 0.006), (0, -0.43, 0.56), rot=(-25, 0, 0)), TIME, (0.8, 1.1))
    m.add("corpo", tr(esfera(0.022, 8, 6), (0, -0.46, 0.55)), OURO, (1, 1.1))
    # cabeça: crânio, bochechas, focinho, nariz, orelhas, olhos bravos e presas
    m.add("cabeca", tr(esfera(1, 16, 10), (0, -0.5, 0.76), esc=(0.145, 0.16, 0.135)), PEL, (0.78, 1.06))
    m.add("cabeca", tr(esfera(1, 14, 8), (0, -0.47, 0.69), esc=(0.165, 0.12, 0.1)), CLARO, (0.85, 1.05))
    m.add("cabeca", tr(caixa(0.12, 0.2, 0.085, 0.04), (0, -0.66, 0.72), rot=(6, 0, 0)), PEL, (0.85, 1.05))
    m.add("cabeca", tr(caixa(0.105, 0.17, 0.03, 0.012), (0, -0.67, 0.682), rot=(6, 0, 0)), CLARO, (0.9, 1.05))
    m.add("cabeca", tr(esfera(1, 10, 8), (0, -0.765, 0.745), esc=(0.042, 0.032, 0.032)), PRETO, (1, 1.2))
    for lado in (-1, 1):
        m.add("cabeca", tr(cone(0.058, 0.15, 8), (0.08 * lado, -0.46, 0.85), rot=(-12, 16 * lado, 0), esc=(1, 0.55, 1)), PEL2, (0.85, 1.1))
        m.add("cabeca", tr(cone(0.036, 0.1, 8), (0.08 * lado, -0.478, 0.86), rot=(-12, 16 * lado, 0), esc=(1, 0.4, 1)), ROSA, (1, 1))
        olho(m, "cabeca", (0.075 * lado, -0.622, 0.79), lado, 0.03, "#F2C230", brava=18, sobr=PEL2)
        m.add("cabeca", tr(cone(0.014, 0.05, 6), (0.04 * lado, -0.72, 0.69), rot=(180, 0, 0)), BRANCO, (1, 1))
    m.add("queixo", tr(caixa(0.095, 0.15, 0.035, 0.012), (0, -0.635, 0.645), rot=(-4, 0, 0)), CLARO, (0.9, 1.05))
    for lado in (-1, 1):
        m.add("queixo", tr(cone(0.012, 0.04, 6), (0.035 * lado, -0.69, 0.655)), BRANCO, (1, 1))
    # patas
    for nome, x, y in PERNAS:
        tras = y > 0
        m.add(nome, tr(esfera(1, 10, 8), (x, y + (0.02 if tras else 0), 0.42), esc=(0.07, 0.11 if tras else 0.09, 0.12)), PEL, (0.8, 1.05))
        m.add(nome, tr(capsula(0.042, 0.36, 10), (x, y + (0.02 if tras else -0.01), 0.04)), PEL, (0.72, 1.0))
        m.add(nome, tr(esfera(1, 10, 6), (x, y - 0.035, 0.035), esc=(0.05, 0.07, 0.04)), CLARO, (0.85, 1.0))
    # cauda peluda com a ponta clara
    cau = [(0, 0.36, 0.6), (0, 0.52, 0.66), (0, 0.68, 0.68), (0, 0.8, 0.64)]
    m.add("cauda", tubo(cau, [0.045, 0.075, 0.07, 0.03], 10), PEL, (0.8, 1.05))
    m.add("cauda", tr(esfera(1, 10, 8), (0, 0.79, 0.645), esc=(0.05, 0.08, 0.05)), CLARO, (0.9, 1.05))

    def parado(t):
        s = seno(t)
        return {"corpo": ((0.8 * s, 0, 0), (0, 0, 0.006 * s)), "cabeca": (2 * seno(t, 2), 0, 10 * seno(t, 1, 0.1)),
                "queixo": (4 + 4 * seno(t, 4), 0, 0), "cauda": (8, 0, 14 * seno(t, 2))}

    def andar(t):
        return {**pernas4(t, 34, galope=True), "corpo": ((3 * seno(t, 2), 0, 0), (0, 0, 0.03 * (0.5 - 0.5 * math.cos(4 * math.pi * t)))),
                "cabeca": (-4 * seno(t, 2), 0, 0), "cauda": (14, 0, 12 * seno(t)), "queixo": (6, 0, 0)}

    def atacar(t):
        frente = curva(t, [(0, 0), (0.28, -20), (0.42, 10), (1, 0)])
        tras = curva(t, [(0, 0), (0.28, 15), (0.42, -10), (1, 0)])
        return {"corpo": ((curva(t, [(0, 0), (0.28, -5), (0.42, 9), (1, 0)]), 0, 0),
                          (0, curva(t, [(0, 0), (0.28, 0.06), (0.42, -0.16), (1, 0)]), curva(t, [(0, 0), (0.28, -0.03), (0.42, 0.02), (1, 0)]))),
                "cabeca": (curva(t, [(0, 0), (0.28, -12), (0.42, 14), (1, 0)]), 0, 0),
                "queixo": (curva(t, [(0, 0), (0.28, 32), (0.44, 0), (1, 0)]), 0, 0),
                "pfd": (frente, 0, 0), "pfe": (frente, 0, 0), "ptd": (tras, 0, 0), "pte": (tras, 0, 0),
                "cauda": (curva(t, [(0, 10), (0.3, 25), (1, 10)]), 0, 0)}
    return m, {"parado": (48, parado), "andar": (14, andar), "atacar": (18, atacar)}


def touro():
    m = Modelo("touro", 1.0)
    PEL, PEL2, FOC, CHIFRE, CASCO = "#4E3C34", "#2F2522", "#C8A385", "#F0E7D2", "#2A2320"
    m.peca("corpo", (0, 0, 0.82))
    m.peca("cabeca", (0, -0.62, 1.0), "corpo")
    m.peca("cauda", (0, 0.74, 1.0), "corpo")
    PERNAS = (("pfd", -0.21, -0.42), ("pfe", 0.21, -0.42), ("ptd", -0.21, 0.46), ("pte", 0.21, 0.46))
    for nome, x, y in PERNAS:
        m.peca(nome, (x, y, 0.72), "corpo")
    m.add("corpo", tr(esfera(1, 20, 12), (0, 0.12, 0.88), esc=(0.34, 0.62, 0.34)), PEL, (0.72, 1.06))
    m.add("corpo", tr(esfera(1, 18, 10), (0, -0.32, 0.96), esc=(0.38, 0.36, 0.42)), PEL, (0.72, 1.06))      # corcova
    m.add("corpo", tr(esfera(1, 16, 10), (0, -0.5, 0.82), esc=(0.28, 0.24, 0.3)), PEL, (0.72, 1.05))        # peito
    m.add("corpo", tr(esfera(1, 14, 8), (0, -0.55, 0.6), esc=(0.12, 0.14, 0.12)), PEL2, (0.85, 1.05))       # barbela
    # manta do time nas costas, com a barra dourada e um medalhão de cada lado
    m.add("corpo", tr(esfera(1, 20, 10), (0, 0.1, 1.1), esc=(0.37, 0.42, 0.12)), TIME, (0.85, 1.1))
    for lado in (-1, 1):
        m.add("corpo", tr(caixa(0.035, 0.62, 0.3, 0.012), (0.345 * lado, 0.1, 0.95), rot=(0, 6 * lado, 0)), TIME, (0.75, 1.0))
        m.add("corpo", tr(caixa(0.045, 0.64, 0.035, 0.012), (0.36 * lado, 0.1, 0.8), rot=(0, 6 * lado, 0)), OURO, (1, 1))
        m.add("corpo", tr(esfera(0.045, 10, 8), (0.37 * lado, 0.1, 0.96)), OURO, (0.9, 1.1))
    # cabeça baixa de brigão: focinho claro, argola no nariz, olhos vermelhos e chifres grandes
    m.add("cabeca", tr(caixa(0.34, 0.36, 0.32, 0.12, 3), (0, -0.82, 0.94), rot=(22, 0, 0)), PEL, (0.8, 1.06))
    m.add("cabeca", tr(esfera(1, 16, 10), (0, -0.98, 0.8), esc=(0.2, 0.15, 0.15)), FOC, (0.85, 1.05))
    m.add("cabeca", tr(esfera(1, 14, 8), (0, -0.78, 1.12), esc=(0.12, 0.1, 0.06)), PEL2, (0.9, 1.05))       # topete
    m.add("cabeca", tr(toro(0.055, 0.012, 18, 6), (0, -1.11, 0.74), rot=(90, 0, 0)), OURO, (1, 1.1))
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(1, 8, 6), (0.07 * lado, -1.115, 0.82), esc=(0.03, 0.02, 0.025)), PRETO, (1, 1))
        olho(m, "cabeca", (0.16 * lado, -0.9, 1.03), lado, 0.045, "#E53935", brava=24, sobr=PEL2)
        ch = [(0.14 * lado, -0.78, 1.1), (0.3 * lado, -0.8, 1.14), (0.43 * lado, -0.86, 1.25), (0.48 * lado, -0.94, 1.4)]
        m.add("cabeca", tubo(ch, [0.06, 0.05, 0.035, 0.008], 10), CHIFRE, (0.8, 1.06))
        m.add("cabeca", tr(esfera(1, 10, 6), (0.23 * lado, -0.74, 1.02), rot=(0, 0, 25 * lado), esc=(0.1, 0.04, 0.05)), PEL, (0.85, 1.05))
    for nome, x, y in PERNAS:
        tras = y > 0
        m.add(nome, tr(esfera(1, 12, 8), (x, y, 0.66), esc=(0.12, 0.2 if tras else 0.16, 0.2)), PEL, (0.75, 1.05))
        m.add(nome, tr(capsula(0.075, 0.55, 10), (x, y, 0.08)), PEL, (0.7, 1.0))
        m.add(nome, tr(esfera(1, 10, 8), (x, y, 0.17), esc=(0.088, 0.088, 0.06)), FOC, (0.85, 1.0))
        m.add(nome, tr(cilindro(0.085, 0.095, 0.1, 12, 0.02), (x, y - 0.01, 0.0)), CASCO, (0.8, 1.0))
    cau = [(0, 0.72, 1.0), (0, 0.8, 0.88), (0, 0.84, 0.66), (0, 0.83, 0.48)]
    m.add("cauda", tubo(cau, [0.035, 0.028, 0.022, 0.018], 8), PEL, (0.85, 1.0))
    m.add("cauda", tr(esfera(1, 10, 8), (0, 0.83, 0.42), esc=(0.06, 0.06, 0.1)), PEL2, (0.85, 1.0))

    def parado(t):
        s = seno(t)
        return {"corpo": ((0.6 * s, 0, 0), (0, 0, 0.008 * s)), "cabeca": (6 + 3 * seno(t, 2), 0, 6 * seno(t, 1, 0.3)),
                "cauda": (5, 0, 22 * seno(t, 2))}

    def andar(t):                                         # carga: galope pesado de cabeça baixa
        return {**pernas4(t, 36, galope=True), "corpo": ((4 * seno(t, 2, 0.1), 0, 0), (0, 0, 0.045 * (0.5 - 0.5 * math.cos(4 * math.pi * t)))),
                "cabeca": (12 + 4 * seno(t, 2), 0, 0), "cauda": (35, 0, 10 * seno(t))}

    def atacar(t):                                        # cabeçada
        frente = curva(t, [(0, 0), (0.3, -12), (0.46, 18), (1, 0)])
        tras = curva(t, [(0, 0), (0.3, 10), (0.46, -14), (1, 0)])
        return {"cabeca": (curva(t, [(0, 6), (0.3, -22), (0.46, 32), (1, 6)]), 0, 0),
                "corpo": ((curva(t, [(0, 0), (0.3, -5), (0.46, 6), (1, 0)]), 0, 0), (0, curva(t, [(0, 0), (0.3, 0.1), (0.46, -0.24), (1, 0)]), 0)),
                "pfd": (frente, 0, 0), "pfe": (frente, 0, 0), "ptd": (tras, 0, 0), "pte": (tras, 0, 0),
                "cauda": (curva(t, [(0, 5), (0.4, 40), (1, 5)]), 0, 0)}
    return m, {"parado": (48, parado), "andar": (12, andar), "atacar": (18, atacar)}


def aranha():
    m = Modelo("aranha", 1.0)
    C1, C2, PERNA, OLHO = "#3D3547", "#27212E", "#4A4155", "#FF3B3B"
    m.peca("corpo", (0, 0, 0.3))
    m.peca("presas", (0, -0.27, 0.29), "corpo")
    PERNAS = []
    for i, (y, dy) in enumerate(((-0.17, -0.28), (-0.08, -0.1), (0.01, 0.08), (0.09, 0.26))):
        for lado, ld in ((-1, "d"), (1, "e")):
            nome = f"p{i}{ld}"
            m.peca(nome, (0.1 * lado, y, 0.31), "corpo")
            PERNAS.append((nome, i, lado))
            a, jo, pe = (0.1 * lado, y, 0.31), (0.33 * lado, y + dy * 0.45, 0.5), (0.52 * lado, y + dy, 0.02)
            m.add(nome, tubo([a, jo], [0.032, 0.027], 8), PERNA, (0.85, 1.05))
            m.add(nome, tubo([jo, ((jo[0] + pe[0]) / 2, (jo[1] + pe[1]) / 2, 0.3), pe], [0.027, 0.02, 0.01], 8), PERNA, (0.85, 1.05))
            m.add(nome, tr(esfera(0.035, 8, 6), jo), C1, (0.9, 1.1))
    m.add("corpo", tr(esfera(1, 18, 12), (0, 0.27, 0.36), esc=(0.24, 0.3, 0.22)), C1, (0.7, 1.08))            # abdome
    for y, e in ((0.18, 1.0), (0.36, 0.9)):                                                                   # ampulheta do time
        m.add("corpo", tr(esfera(1, 12, 8), (0, y, 0.555 - abs(y - 0.27) * 0.25), esc=(0.085 * e, 0.075 * e, 0.03)), TIME, (0.9, 1.15))
    m.add("corpo", tr(esfera(1, 16, 10), (0, -0.09, 0.32), esc=(0.16, 0.17, 0.12)), C2, (0.75, 1.1))          # tórax
    m.add("corpo", tr(esfera(1, 14, 8), (0, -0.22, 0.33), esc=(0.11, 0.09, 0.09)), C2, (0.8, 1.08))           # cabeça
    for lado in (-1, 1):                                  # dois olhos grandes e quatro pequenos, vermelhos
        m.add("corpo", tr(esfera(1, 10, 8), (0.04 * lado, -0.295, 0.37), esc=(0.03, 0.022, 0.03)), OLHO, (1.1, 1.4))
        m.add("corpo", tr(esfera(0.009, 6, 5), (0.034 * lado, -0.316, 0.385)), BRANCO, (1.3, 1.3))
        for x, z in ((0.085, 0.385), (0.03, 0.415)):
            m.add("corpo", tr(esfera(0.014, 8, 6), (x * lado, -0.275, z)), OLHO, (1.1, 1.4))
        m.add("presas", tr(esfera(1, 10, 8), (0.035 * lado, -0.3, 0.29), esc=(0.03, 0.03, 0.04)), C2, (0.9, 1.05))
        m.add("presas", tr(cone(0.022, 0.09, 8), (0.035 * lado, -0.31, 0.27), rot=(160, 0, 0)), "#1A161E", (1, 1.3))
    m.add("corpo", tr(cone(0.04, 0.08, 8), (0, 0.56, 0.33), rot=(-100, 0, 0)), C2, (0.9, 1.05))              # fiandeiras

    def pernas(t, amp, lev):
        out = {}
        for nome, i, lado in PERNAS:
            ph = ((i % 2) * 0.5 + (0 if lado < 0 else 0.5)) % 1
            phi = amp * seno(t, 1, ph)
            lift = lev * max(0.0, math.cos(2 * math.pi * (t + ph)))
            out[nome] = (0, -lado * lift, -lado * phi)
        return out

    def parado(t):
        return {**pernas(t, 2, 0), "corpo": ((0, 0, 0), (0, 0, 0.006 * seno(t))), "presas": (6 * seno(t, 2), 0, 0)}

    def andar(t):
        return {**pernas(t, 16, 14), "corpo": ((0, 2 * seno(t, 2), 0), (0, 0, 0.012 * seno(t, 4)))}

    def atacar(t):
        out = pernas(0, 0, 0)
        for nome, i, lado in PERNAS:
            if i == 0:
                out[nome] = (0, -lado * curva(t, [(0, 0), (0.3, 40), (0.5, -5), (1, 0)]), 0)
        out["corpo"] = ((curva(t, [(0, 0), (0.3, -16), (0.5, 10), (1, 0)]), 0, 0),
                        (0, curva(t, [(0, 0), (0.3, 0.05), (0.5, -0.1), (1, 0)]), curva(t, [(0, 0), (0.3, 0.04), (0.5, -0.01), (1, 0)])))
        out["presas"] = (curva(t, [(0, 0), (0.3, -35), (0.5, 15), (1, 0)]), 0, 0)
        return out
    return m, {"parado": (40, parado), "andar": (12, andar), "atacar": (14, atacar)}


def vespa():
    m = Modelo("vespa", 1.0)
    AM, PR, ASA, OLHO = "#F7C21E", "#221C24", "#DCEFFF", "#2E2440"
    m.peca("corpo", (0, 0, 0))
    m.peca("cabeca", (0, -0.13, 0.03), "corpo")
    m.peca("cauda", (0, 0.11, -0.01), "corpo")
    m.peca("asa_d", (-0.05, 0.0, 0.1), "corpo")
    m.peca("asa_e", (0.05, 0.0, 0.1), "corpo")
    m.add("corpo", tr(esfera(1, 16, 10), (0, 0, 0.02), esc=(0.12, 0.14, 0.12)), TIME, (0.75, 1.1))       # tórax peludo do time
    m.add("corpo", tr(esfera(1, 12, 8), (0, 0.02, 0.11), esc=(0.075, 0.09, 0.04)), TIME2, (0.9, 1.05))
    for lado in (-1, 1):
        for y in (-0.05, 0.0, 0.05):
            m.add("corpo", tubo([(0.05 * lado, y, -0.06), (0.11 * lado, y + 0.01, -0.12), (0.1 * lado, y + 0.04, -0.23)], [0.014, 0.011, 0.007], 6), PR, (0.9, 1.0))
    m.add("cabeca", tr(esfera(1, 14, 10), (0, -0.21, 0.05), esc=(0.1, 0.085, 0.09)), AM, (0.85, 1.1))
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(1, 12, 8), (0.066 * lado, -0.235, 0.07), rot=(0, 0, -20 * lado), esc=(0.045, 0.05, 0.065)), OLHO, (0.9, 1.3))
        m.add("cabeca", tr(esfera(0.012, 6, 5), (0.072 * lado, -0.272, 0.1)), BRANCO, (1.3, 1.3))
        m.add("cabeca", tr(caixa(0.07, 0.02, 0.018, 0.006), (0.05 * lado, -0.255, 0.13), rot=(0, -22 * lado, 0)), PR, (1, 1))   # sobrancelha brava
        m.add("cabeca", tubo([(0.03 * lado, -0.27, 0.11), (0.06 * lado, -0.33, 0.2), (0.1 * lado, -0.37, 0.22)], [0.008, 0.006, 0.005], 6), PR, (1, 1))
        m.add("cabeca", tr(cone(0.016, 0.05, 6), (0.025 * lado, -0.29, 0.0), rot=(150, 0, 15 * lado)), PR, (1, 1))
    for y, z, r, cor in ((0.15, -0.03, 0.08, PR), (0.23, -0.07, 0.105, AM), (0.31, -0.11, 0.1, PR), (0.38, -0.15, 0.085, AM), (0.44, -0.185, 0.06, PR)):
        m.add("cauda", tr(esfera(1, 14, 10), (0, y, z), rot=(-25, 0, 0), esc=(r, r * 0.9, r)), cor, (0.8, 1.12))
    m.add("cauda", tr(cone(0.025, 0.1, 8), (0, 0.47, -0.21), rot=(-125, 0, 0)), PR, (1, 1.2))
    for lado, p in ((-1, "asa_d"), (1, "asa_e")):
        m.add(p, tr(esfera(1, 16, 6), (0.2 * lado, 0.04, 0.13), rot=(0, 0, -18 * lado), esc=(0.2, 0.075, 0.008)), ASA, (0.95, 1.1))
        m.add(p, tr(esfera(1, 14, 6), (0.16 * lado, 0.12, 0.115), rot=(0, 0, -32 * lado), esc=(0.14, 0.05, 0.007)), ASA, (0.95, 1.1))

    def voo(t, bob=0.035, incl=0.0):
        bate = 42 * seno(t, 4)
        return {"asa_d": (0, bate, 0), "asa_e": (0, -bate, 0), "corpo": ((incl + 4 * seno(t), 0, 0), (0, 0, bob * seno(t))),
                "cauda": (5 * seno(t, 1, 0.2), 0, 0)}

    def atacar(t):
        v = voo(t)
        v["cauda"] = (curva(t, [(0, 0), (0.25, 15), (0.45, -60), (1, 0)]), 0, 0)
        v["corpo"] = ((curva(t, [(0, 0), (0.25, -10), (0.45, 18), (1, 0)]), 0, 0), (0, curva(t, [(0, 0), (0.45, -0.08), (1, 0)]), 0))
        return v
    return m, {"parado": (12, lambda t: voo(t, 0.04)), "andar": (12, lambda t: voo(t, 0.025, 10)), "atacar": (12, atacar)}


def raptor():
    m = Modelo("raptor", 1.0)
    PEL, LIS, BAR, GAR = "#D58B46", "#8C4F27", "#F4DDB0", "#F6EEDA"
    m.peca("corpo", (0, 0, 0.62))
    m.peca("cabeca", (0, -0.36, 0.78), "corpo")
    m.peca("queixo", (0, -0.6, 0.98), "cabeca")
    m.peca("cauda", (0, 0.22, 0.66), "corpo")
    m.peca("perna_d", (-0.11, 0.04, 0.6), "corpo")
    m.peca("perna_e", (0.11, 0.04, 0.6), "corpo")
    m.peca("braco_d", (-0.1, -0.26, 0.66), "corpo")
    m.peca("braco_e", (0.1, -0.26, 0.66), "corpo")
    m.add("corpo", tr(esfera(1, 18, 10), (0, -0.04, 0.68), rot=(-12, 0, 0), esc=(0.155, 0.33, 0.165)), PEL, (0.72, 1.06))
    m.add("corpo", tr(esfera(1, 14, 8), (0, -0.08, 0.6), rot=(-12, 0, 0), esc=(0.115, 0.26, 0.09)), BAR, (0.9, 1.05))
    for y in (-0.16, -0.02, 0.12):                       # listras no dorso
        m.add("corpo", tr(caixa(0.2, 0.045, 0.03, 0.012), (0, y, 0.826 - (y + 0.04) * 0.21), rot=(-12, 0, 0)), LIS, (1, 1))
    m.add("cabeca", tubo([(0, -0.3, 0.74), (0, -0.42, 0.86), (0, -0.5, 0.98)], [0.1, 0.075, 0.065], 12), PEL, (0.8, 1.05))
    m.add("cabeca", tr(esfera(1, 14, 10), (0, -0.55, 1.03), esc=(0.09, 0.12, 0.085)), PEL, (0.8, 1.06))
    m.add("cabeca", tr(caixa(0.095, 0.21, 0.07, 0.03), (0, -0.69, 1.005), rot=(5, 0, 0)), PEL, (0.85, 1.05))
    m.add("cabeca", tr(caixa(0.08, 0.18, 0.02, 0.008), (0, -0.69, 0.972), rot=(5, 0, 0)), "#7A2433", (1, 1))
    for lado in (-1, 1):
        olho(m, "cabeca", (0.062 * lado, -0.6, 1.07), lado, 0.026, "#F5D33A", brava=22, sobr=LIS)
        m.add("cabeca", tr(esfera(1, 6, 5), (0.03 * lado, -0.795, 1.025), esc=(0.012, 0.01, 0.008)), PRETO, (1, 1))
        for k in range(4):
            m.add("cabeca", tr(cone(0.011, 0.035, 5), (0.04 * lado, -0.77 + 0.045 * k, 0.975), rot=(180, 0, 0)), BRANCO, (1, 1))
    for y, z, ang, tam in ((-0.5, 1.1, -55, 1.0), (-0.45, 1.09, -65, 1.15), (-0.4, 1.06, -75, 1.0), (-0.36, 1.02, -82, 0.8)):
        m.add("cabeca", tr(pena(0.035, 0.2), (0, y, z), rot=(ang, 0, 0), esc=tam), TIME, (0.85, 1.15))     # crista de penas do time
    m.add("queixo", tr(caixa(0.08, 0.17, 0.035, 0.012), (0, -0.7, 0.955), rot=(-3, 0, 0)), BAR, (0.85, 1.05))
    for lado in (-1, 1):
        for k in range(3):
            m.add("queixo", tr(cone(0.01, 0.03, 5), (0.032 * lado, -0.765 + 0.05 * k, 0.968)), BRANCO, (1, 1))
    for lado, p in ((-1, "braco_d"), (1, "braco_e")):
        x = 0.1 * lado
        m.add(p, tubo([(x, -0.26, 0.66), (x * 1.25, -0.33, 0.6), (x * 1.2, -0.41, 0.58)], [0.035, 0.026, 0.02], 8), PEL, (0.85, 1.05))
        for k in (-1, 1):
            m.add(p, tr(cone(0.01, 0.05, 5), (x * 1.2 + 0.015 * k, -0.425, 0.575), rot=(120, 0, 0)), GAR, (1, 1))
        m.add(p, tr(pena(0.03, 0.16), (x * 1.18, -0.3, 0.63), rot=(-150, 0, 0)), TIME, (0.85, 1.1))
    for lado, p in ((-1, "perna_d"), (1, "perna_e")):
        x = 0.11 * lado
        m.add(p, tr(esfera(1, 12, 8), (x, 0.06, 0.52), rot=(18, 0, 0), esc=(0.075, 0.12, 0.15)), PEL, (0.78, 1.05))
        m.add(p, tubo([(x, 0.08, 0.42), (x, 0.15, 0.22), (x, 0.11, 0.07)], [0.048, 0.034, 0.03], 8), PEL, (0.8, 1.0))
        m.add(p, tr(caixa(0.07, 0.16, 0.045, 0.02), (x, 0.03, 0.03)), PEL, (0.8, 1.0))
        for k in (-1, 0, 1):
            m.add(p, tr(cone(0.012, 0.05, 5), (x + 0.022 * k, -0.06, 0.02), rot=(95, 0, 0)), GAR, (1, 1))
        m.add(p, tubo([(x, 0.0, 0.06), (x, -0.04, 0.12), (x, -0.08, 0.13)], [0.016, 0.012, 0.004], 6), GAR, (1, 1))   # garra-foice
    cau = [(0, 0.2, 0.68), (0, 0.42, 0.72), (0, 0.66, 0.75), (0, 0.9, 0.74)]
    m.add("cauda", tubo(cau, [0.115, 0.08, 0.05, 0.015], 12), PEL, (0.8, 1.05))
    for (y, z, R) in ((0.36, 0.71, 0.088), (0.52, 0.735, 0.066), (0.68, 0.752, 0.046)):
        m.add("cauda", tr(toro(R, 0.012, 16, 5), (0, y, z), rot=(90, 0, 0)), LIS, (1, 1))
    m.add("cauda", tr(pena(0.05, 0.22), (0, 0.88, 0.75), rot=(-80, 0, 0)), TIME, (0.85, 1.1))

    def parado(t):
        s = seno(t)
        return {"corpo": ((1 * s, 0, 0), (0, 0, 0.008 * s)), "cabeca": (3 * seno(t, 2), 0, 16 * seno(t, 1, 0.15)),
                "queixo": (3 + 3 * seno(t, 3), 0, 0), "cauda": (2 * s, 0, 8 * seno(t, 1, 0.4)), "braco_d": (6 * s, 0, 0), "braco_e": (6 * s, 0, 0)}

    def andar(t):
        return {"perna_d": (40 * seno(t), 0, 0), "perna_e": (-40 * seno(t), 0, 0),
                "corpo": ((3 * seno(t, 2), 0, 0), (0, 0, 0.04 * (0.5 - 0.5 * math.cos(4 * math.pi * t)))),
                "cabeca": (-3 * seno(t, 2), 0, 0), "cauda": (4 * seno(t, 2, 0.25), 0, 9 * seno(t)),
                "braco_d": (-10 + 8 * seno(t), 0, 0), "braco_e": (-10 - 8 * seno(t), 0, 0), "queixo": (5, 0, 0)}

    def atacar(t):
        bracos = curva(t, [(0, 0), (0.25, -40), (0.45, -10), (1, 0)])
        return {"corpo": ((curva(t, [(0, 0), (0.25, -8), (0.45, 14), (1, 0)]), 0, 0), (0, curva(t, [(0, 0), (0.25, 0.05), (0.45, -0.17), (1, 0)]), 0)),
                "cabeca": (curva(t, [(0, 0), (0.25, -12), (0.45, 12), (1, 0)]), 0, 0),
                "queixo": (curva(t, [(0, 0), (0.27, 34), (0.46, 0), (1, 0)]), 0, 0),
                "braco_d": (bracos, 0, 0), "braco_e": (bracos, 0, 0),
                "perna_d": (curva(t, [(0, 0), (0.25, 10), (0.45, -18), (1, 0)]), 0, 0), "perna_e": (curva(t, [(0, 0), (0.25, 6), (0.45, 14), (1, 0)]), 0, 0),
                "cauda": (curva(t, [(0, 0), (0.25, 12), (0.45, -8), (1, 0)]), 0, 0)}

    def saltar(t):
        bracos = curva(t, [(0, 0), (0.35, -50), (1, 0)])
        return {"corpo": ((curva(t, [(0, 0), (0.2, 8), (0.35, -14), (0.8, -4), (1, 0)]), 0, 0), (0, 0, curva(t, [(0, 0), (0.2, -0.08), (0.35, 0.02), (1, 0)]))),
                "perna_d": (curva(t, [(0, 0), (0.2, 22), (0.35, -40), (0.85, -25), (1, 0)]), 0, 0),
                "perna_e": (curva(t, [(0, 0), (0.2, 22), (0.35, -30), (0.85, -35), (1, 0)]), 0, 0),
                "braco_d": (bracos, 0, 0), "braco_e": (bracos, 0, 0),
                "cauda": (curva(t, [(0, 0), (0.35, 18), (1, 0)]), 0, 0), "queixo": (curva(t, [(0, 0), (0.4, 25), (1, 0)]), 0, 0)}
    return m, {"parado": (40, parado), "andar": (10, andar), "atacar": (14, atacar), "saltar": (14, saltar)}


def rex():
    m = Modelo("rex", 1.0)
    V, V2, BAR, OLHO = "#5F9746", "#3E6E2E", "#EBDDA9", "#FFC83D"
    m.peca("corpo", (0, 0.05, 1.3))
    m.peca("cabeca", (0, -0.62, 1.72), "corpo")
    m.peca("queixo", (0, -0.86, 1.96), "cabeca")
    m.peca("cauda", (0, 0.62, 1.4), "corpo")
    m.peca("cauda2", (0, 1.32, 1.28), "cauda")
    m.peca("perna_d", (-0.3, 0.12, 1.2), "corpo")
    m.peca("perna_e", (0.3, 0.12, 1.2), "corpo")
    m.peca("braco_d", (-0.27, -0.5, 1.45), "corpo")
    m.peca("braco_e", (0.27, -0.5, 1.45), "corpo")
    m.add("corpo", tr(esfera(1, 22, 12), (0, 0.02, 1.45), rot=(-14, 0, 0), esc=(0.46, 0.82, 0.52)), V, (0.72, 1.06))
    m.add("corpo", tr(esfera(1, 18, 10), (0, -0.42, 1.58), esc=(0.42, 0.42, 0.5)), V, (0.74, 1.06))
    m.add("corpo", tr(esfera(1, 18, 10), (0, -0.2, 1.22), rot=(-18, 0, 0), esc=(0.34, 0.62, 0.3)), BAR, (0.9, 1.05))
    for y, z in ((-0.55, 2.03), (-0.3, 2.0), (-0.05, 1.95), (0.22, 1.86), (0.46, 1.78)):
        m.add("corpo", tr(cone(0.07, 0.13, 6), (0, y, z), rot=(-15, 0, 0), esc=(0.5, 1, 1)), V2, (0.9, 1.05))   # placas nas costas
    # sela do time, correias e a bandeirinha
    m.add("corpo", tr(caixa(0.62, 0.5, 0.09, 0.035), (0, 0.06, 1.94), rot=(-10, 0, 0)), TIME, (0.85, 1.1))
    m.add("corpo", tr(caixa(0.66, 0.54, 0.035, 0.012), (0, 0.06, 1.895), rot=(-10, 0, 0)), OURO, (1, 1))
    for lado in (-1, 1):
        m.add("corpo", tr(caixa(0.035, 0.08, 0.6, 0.012), (0.44 * lado, 0.06, 1.62), rot=(-10, -18 * lado, 0)), COURO2, (0.9, 1.0))
    m.add("corpo", tr(cilindro(0.025, 0.02, 0.9, 8), (0, 0.22, 1.95)), MADEIRA2, (0.85, 1.05))
    m.add("corpo", tr(prisma([(0, 0), (0.42, -0.04), (0.3, -0.16), (0.42, -0.28), (0, -0.3)], 0.025, 0.008), (0, 0.24, 2.82), rot=(0, 0, 90)), TIME, (0.85, 1.12))
    m.add("corpo", tr(esfera(0.045, 8, 6), (0, 0.22, 2.86)), OURO, (1, 1.1))
    # cabeça: pescoço grosso, crânio comprido, olhos bravos, narinas e dentes
    m.add("cabeca", tubo([(0, -0.5, 1.62), (0, -0.7, 1.82), (0, -0.84, 1.98)], [0.34, 0.29, 0.26], 16), V, (0.8, 1.05))
    m.add("cabeca", tr(caixa(0.46, 0.72, 0.38, 0.15, 3), (0, -1.12, 2.1), rot=(4, 0, 0)), V, (0.82, 1.06))
    m.add("cabeca", tr(esfera(1, 14, 8), (0, -0.95, 2.27), esc=(0.2, 0.32, 0.1)), V2, (0.9, 1.05))
    m.add("cabeca", tr(caixa(0.4, 0.62, 0.05, 0.02), (0, -1.15, 1.93), rot=(4, 0, 0)), "#7A2433", (1, 1))
    for lado in (-1, 1):
        olho(m, "cabeca", (0.205 * lado, -0.98, 2.2), lado, 0.06, OLHO, brava=26, sobr=V2)
        m.add("cabeca", tr(esfera(1, 8, 6), (0.08 * lado, -1.475, 2.17), esc=(0.03, 0.02, 0.02)), PRETO, (1, 1))
        for k in range(6):
            m.add("cabeca", tr(cone(0.024, 0.075, 6), (0.18 * lado, -1.42 + 0.085 * k, 1.92), rot=(180, 0, 0)), BRANCO, (1, 1))
    m.add("queixo", tr(caixa(0.4, 0.62, 0.13, 0.05), (0, -1.18, 1.86), rot=(2, 0, 0)), BAR, (0.85, 1.05))
    m.add("queixo", tr(caixa(0.3, 0.5, 0.03, 0.01), (0, -1.16, 1.925)), "#B84A5A", (1, 1))
    for lado in (-1, 1):
        for k in range(5):
            m.add("queixo", tr(cone(0.02, 0.06, 6), (0.16 * lado, -1.38 + 0.085 * k, 1.92)), BRANCO, (1, 1))
    for lado, p in ((-1, "braco_d"), (1, "braco_e")):
        x = 0.27 * lado
        m.add(p, tubo([(x, -0.5, 1.45), (x * 1.12, -0.66, 1.34), (x * 1.1, -0.78, 1.38)], [0.075, 0.055, 0.045], 8), V, (0.85, 1.05))
        for k in (-1, 1):
            m.add(p, tr(cone(0.018, 0.07, 5), (x * 1.1 + 0.025 * k, -0.82, 1.38), rot=(100, 0, 0)), BRANCO, (1, 1))
    for lado, p in ((-1, "perna_d"), (1, "perna_e")):
        x = 0.315 * lado
        m.add(p, tr(esfera(1, 16, 10), (x, 0.14, 1.02), rot=(20, 0, 0), esc=(0.2, 0.32, 0.4)), V, (0.75, 1.05))
        m.add(p, tubo([(x, 0.22, 0.75), (x, 0.32, 0.38), (x, 0.22, 0.13)], [0.14, 0.1, 0.09], 10), V2, (0.85, 1.0))
        m.add(p, tr(caixa(0.22, 0.36, 0.1, 0.04), (x, 0.06, 0.05)), V2, (0.85, 1.0))
        for k in (-1, 0, 1):
            m.add(p, tr(cone(0.035, 0.11, 6), (x + 0.07 * k, -0.13, 0.04), rot=(95, 0, 0)), BRANCO, (1, 1))
    m.add("cauda", tubo([(0, 0.55, 1.42), (0, 0.95, 1.38), (0, 1.35, 1.28)], [0.36, 0.28, 0.2], 14), V, (0.78, 1.05))
    m.add("cauda", tubo([(0, 0.62, 1.66), (0, 0.95, 1.62), (0, 1.3, 1.46)], [0.12, 0.1, 0.07], 8), V2, (0.9, 1.05))
    m.add("cauda2", tubo([(0, 1.3, 1.28), (0, 1.65, 1.18), (0, 2.0, 1.08)], [0.2, 0.12, 0.03], 12), V, (0.78, 1.05))

    def parado(t):
        s = seno(t)
        return {"corpo": ((0.8 * s, 0, 0), (0, 0, 0.012 * s)), "cabeca": (3 * seno(t, 2), 0, 10 * seno(t, 1, 0.2)),
                "queixo": (5 + 5 * seno(t, 2), 0, 0), "cauda": (2 * s, 0, 6 * seno(t, 1, 0.5)), "cauda2": (2 * s, 0, 10 * seno(t, 1, 0.35)),
                "braco_d": (8 * s, 0, 0), "braco_e": (8 * s, 0, 0)}

    def andar(t):
        return {"perna_d": (24 * seno(t), 0, 0), "perna_e": (-24 * seno(t), 0, 0),
                "corpo": ((2 * seno(t, 2), 3 * seno(t), 3 * seno(t)), (0, 0, 0.06 * (0.5 - 0.5 * math.cos(4 * math.pi * t)))),
                "cabeca": (4 * seno(t, 2, 0.1), 0, -4 * seno(t)), "queixo": (6, 0, 0),
                "cauda": (2 * seno(t, 2), 0, -6 * seno(t)), "cauda2": (2 * seno(t, 2), 0, -11 * seno(t, 1, -0.12)),
                "braco_d": (10 * seno(t), 0, 0), "braco_e": (-10 * seno(t), 0, 0)}

    def atacar(t):
        bracos = curva(t, [(0, 0), (0.3, -30), (1, 0)])
        return {"cabeca": (curva(t, [(0, 0), (0.3, -24), (0.5, 26), (1, 0)]), 0, 0),
                "queixo": (curva(t, [(0, 0), (0.3, 40), (0.5, 0), (1, 0)]), 0, 0),
                "corpo": ((curva(t, [(0, 0), (0.3, -6), (0.5, 8), (1, 0)]), 0, 0), (0, curva(t, [(0, 0), (0.3, 0.12), (0.5, -0.3), (1, 0)]), 0)),
                "cauda": (curva(t, [(0, 0), (0.3, 8), (0.5, -6), (1, 0)]), 0, 0), "cauda2": (curva(t, [(0, 0), (0.35, 10), (0.55, -8), (1, 0)]), 0, 0),
                "perna_d": (curva(t, [(0, 0), (0.3, 6), (0.5, -10), (1, 0)]), 0, 0), "perna_e": (curva(t, [(0, 0), (0.3, -6), (0.5, 12), (1, 0)]), 0, 0),
                "braco_d": (bracos, 0, 0), "braco_e": (bracos, 0, 0)}
    return m, {"parado": (48, parado), "andar": (28, andar), "atacar": (22, atacar)}


def triceratops():
    m = Modelo("triceratops", 1.0)
    PEL, PEL2, BAR, CHI, BICO = "#71808F", "#4F5E6C", "#C7CFD7", "#F2E8CC", "#3B3430"
    m.peca("corpo", (0, 0, 0.82))
    m.peca("cabeca", (0, -0.74, 0.92), "corpo")
    m.peca("cauda", (0, 0.8, 0.9), "corpo")
    PERNAS = (("pfd", -0.29, -0.45), ("pfe", 0.29, -0.45), ("ptd", -0.31, 0.45), ("pte", 0.31, 0.45))
    for nome, x, y in PERNAS:
        m.peca(nome, (x, y, 0.66), "corpo")
    m.add("corpo", tr(esfera(1, 22, 12), (0, 0.05, 0.95), esc=(0.48, 0.82, 0.46)), PEL, (0.72, 1.06))
    m.add("corpo", tr(esfera(1, 16, 10), (0, 0.0, 0.72), esc=(0.38, 0.66, 0.24)), BAR, (0.88, 1.05))
    for k in range(6):                                   # calombos no dorso
        y = -0.5 + 0.2 * k
        z = 0.95 + 0.46 * math.sqrt(max(0.0, 1 - ((y - 0.05) / 0.82) ** 2)) - 0.015
        m.add("corpo", tr(esfera(1, 10, 6), (0, y, z), esc=(0.12, 0.09, 0.05)), PEL2, (0.9, 1.05))
    m.add("cabeca", tr(esfera(1, 18, 10), (0, -1.0, 0.88), esc=(0.28, 0.36, 0.26)), PEL, (0.8, 1.06))
    m.add("cabeca", tr(cone(0.13, 0.3, 12), (0, -1.28, 0.8), rot=(105, 0, 0), esc=(1, 0.8, 1)), BICO, (0.85, 1.1))     # bico
    m.add("cabeca", tr(cone(0.065, 0.2, 10), (0, -1.24, 0.98), rot=(55, 0, 0)), CHI, (0.85, 1.1))                       # chifre do nariz
    for lado in (-1, 1):
        m.add("cabeca", tr(cone(0.07, 0.6, 12), (0.13 * lado, -1.02, 1.08), rot=(68, 0, -8 * lado)), CHI, (0.8, 1.12))
        olho(m, "cabeca", (0.2 * lado, -1.16, 0.98), lado, 0.042, "#FFB347", brava=20, sobr=PEL2)
    # babado na cor do time, com a borda de calombos claros
    bab = [(-0.56, 0.0), (-0.62, 0.24), (-0.5, 0.48), (-0.26, 0.62), (0, 0.66), (0.26, 0.62), (0.5, 0.48), (0.62, 0.24), (0.56, 0.0)]
    bab = [(x * 0.82, z * 0.82) for x, z in bab]
    m.add("cabeca", tr(prisma(bab + [(0.25, -0.07), (-0.25, -0.07)], 0.06, 0.02), (0, -0.86, 0.95), rot=(-16, 0, 0)), TIME, (0.75, 1.15))
    for x, z in bab:
        m.add("cabeca", tr(tr(esfera(1, 8, 6), (x * 1.04, 0, z * 1.04), esc=(0.055, 0.045, 0.055)), (0, -0.86, 0.95), rot=(-16, 0, 0)), CHI, (0.9, 1.05))
    for nome, x, y in PERNAS:
        m.add(nome, tr(esfera(1, 12, 8), (x, y, 0.6), esc=(0.16, 0.2, 0.22)), PEL, (0.75, 1.05))
        m.add(nome, tr(capsula(0.12, 0.58, 12), (x, y, 0.06)), PEL, (0.72, 1.0))
        m.add(nome, tr(cilindro(0.14, 0.15, 0.08, 14, 0.02), (x, y - 0.01, 0.0)), BICO, (0.85, 1.0))
        for k in (-1, 0, 1):
            m.add(nome, tr(esfera(1, 8, 6), (x + 0.07 * k, y - 0.13, 0.04), esc=(0.04, 0.035, 0.035)), CHI, (0.9, 1.05))
    m.add("cauda", tubo([(0, 0.78, 0.92), (0, 1.08, 0.84), (0, 1.36, 0.7)], [0.22, 0.13, 0.03], 12), PEL, (0.78, 1.05))

    def parado(t):
        s = seno(t)
        return {"corpo": ((0.6 * s, 0, 0), (0, 0, 0.01 * s)), "cabeca": (3 * seno(t, 2), 0, 9 * seno(t, 1, 0.2)), "cauda": (0, 0, 10 * seno(t, 1, 0.4))}

    def andar(t):
        return {**pernas4(t, 22), "corpo": ((0, 2 * seno(t, 2), 0), (0, 0, 0.03 * (0.5 - 0.5 * math.cos(4 * math.pi * t)))),
                "cabeca": (3 * seno(t, 2), 0, 0), "cauda": (0, 0, 9 * seno(t))}

    def atacar(t):
        frente = curva(t, [(0, 0), (0.3, -10), (0.5, 15), (1, 0)])
        tras = curva(t, [(0, 0), (0.3, 8), (0.5, -12), (1, 0)])
        return {"cabeca": (curva(t, [(0, 0), (0.3, 24), (0.5, -18), (1, 0)]), 0, 0),
                "corpo": ((curva(t, [(0, 0), (0.3, 4), (0.5, -3), (1, 0)]), 0, 0), (0, curva(t, [(0, 0), (0.3, 0.06), (0.5, -0.26), (1, 0)]), 0)),
                "pfd": (frente, 0, 0), "pfe": (frente, 0, 0), "ptd": (tras, 0, 0), "pte": (tras, 0, 0),
                "cauda": (curva(t, [(0, 0), (0.4, 12), (1, 0)]), 0, 0)}
    return m, {"parado": (48, parado), "andar": (22, andar), "atacar": (18, atacar)}


# ================================================================== gente (com ossos)
def barbaro():
    m = P.esqueleto(Modelo("barbaro", 2.0), larg_ombro=0.29, alt_ombro=0.58, r_braco=0.078, comp_braco=0.27, r_perna=0.088,
                    r_cabeca=0.185, z_cabeca=0.8, z_pescoco=0.64, r_mao=0.08, perna="#5B4535", bota=COURO2, sep_perna=0.11, giro_d=24)
    P.rosto(m, sobrancelha="#C0561E", brava=12, r=0.185)
    RUIVO, URSO = "#C2581F", "#7A5634"
    m.add("corpo", tr(torno([(0, 0.25), (0.2, 0.26), (0.26, 0.34), (0.27, 0.46), (0.245, 0.57), (0.16, 0.635), (0, 0.65)], 18), esc=(1, 0.82, 1)), P.PELE, (0.74, 1.06))
    m.add("corpo", tr(torno([(0, 0.17), (0.235, 0.15), (0.26, 0.2), (0.25, 0.34), (0, 0.34)], 18), esc=(1, 0.86, 1)), TIME, (0.75, 1.06))   # saiote
    m.add("corpo", tr(cilindro(0.258, 0.258, 0.05, 18, 0.012), (0, 0, 0.32), esc=(1, 0.86, 1)), COURO2, (1, 1))
    m.add("corpo", tr(caixa(0.09, 0.035, 0.07, 0.015), (0, -0.225, 0.345)), OURO, (0.9, 1.05))
    m.add("corpo", tr(caixa(0.06, 0.03, 0.44, 0.012), (0.02, -0.205, 0.5), rot=(-12, 32, 0)), COURO, (0.9, 1.05))
    m.add("corpo", tr(esfera(1, 14, 8), (0.2, 0.0, 0.6), esc=(0.16, 0.15, 0.1)), URSO, (0.8, 1.05))           # pele de urso no ombro
    m.add("corpo", tr(esfera(1, 12, 8), (0.0, 0.13, 0.56), esc=(0.21, 0.08, 0.13)), URSO, (0.8, 1.05))
    # capacete com chifres
    m.add("cabeca", torno([(0.196, 0.86), (0.2, 0.9), (0.17, 0.96), (0.1, 0.995), (0, 1.005)], 20), P.ACO2, (0.85, 1.1))
    m.add("cabeca", tr(cilindro(0.205, 0.205, 0.04, 20, 0.012), (0, 0, 0.855)), OURO, (1, 1))
    for lado in (-1, 1):
        ch = [(0.17 * lado, 0, 0.93), (0.27 * lado, -0.01, 0.97), (0.33 * lado, -0.02, 1.07), (0.33 * lado, -0.03, 1.17)]
        m.add("cabeca", tubo(ch, [0.045, 0.036, 0.024, 0.006], 8), BRANCO, (0.85, 1.05))
    # barba ruiva com tranças, bigode e cabelo atrás
    m.add("cabeca", tr(esfera(1, 16, 10), (0, -0.09, 0.72), esc=(0.17, 0.12, 0.15)), RUIVO, (0.8, 1.05))
    m.add("cabeca", tr(esfera(1, 14, 8), (0, 0.1, 0.78), esc=(0.18, 0.12, 0.17)), RUIVO, (0.8, 1.05))
    for lado in (-1, 1):
        m.add("cabeca", tubo([(0.06 * lado, -0.16, 0.66), (0.065 * lado, -0.17, 0.58), (0.06 * lado, -0.16, 0.52)], [0.035, 0.03, 0.022], 8), RUIVO, (0.85, 1.05))
        m.add("cabeca", tr(cilindro(0.032, 0.032, 0.025, 8), (0.065 * lado, -0.17, 0.555)), OURO, (1, 1))
        m.add("cabeca", tr(esfera(1, 10, 6), (0.05 * lado, -0.185, 0.77), rot=(0, -20 * lado, 0), esc=(0.06, 0.03, 0.026)), RUIVO, (1, 1))
    # espadão na mão direita e braceletes
    hx, hy, hz = m.mao["braco_d"]
    esp = lambda f, cor, g=(0.9, 1.08): m.add("braco_d", tr(f, (hx, hy - 0.03, hz), rot=(40, 0, 6)), cor, g)   # noqa: E731
    esp(tr(cilindro(0.024, 0.024, 0.14, 10), (0, 0, -0.07)), COURO2)
    esp(tr(esfera(0.036, 10, 6), (0, 0, -0.085)), OURO)
    esp(tr(caixa(0.24, 0.05, 0.045, 0.016), (0, 0, 0.075)), OURO)
    esp(prisma([(-0.055, 0.09), (0.055, 0.09), (0.06, 0.62), (0, 0.74), (-0.06, 0.62)], 0.028, 0.009), "#DDE5EE", (0.8, 1.1))
    for lado, p in ((-1, "braco_d"), (1, "braco_e")):
        piv, ang = m.ombro[p]
        m.add(p, rx(tr(cilindro(0.088, 0.088, 0.07, 12, 0.01), (0.3 * lado, 0, 0.36)), piv, ang), COURO2, (1, 1))

    def parado(t):
        s = seno(t)
        return {"corpo": ((0, 0, 2 * s), (0, 0, 0.006 * s)), "cabeca": (2 * seno(t, 2), 0, 5 * seno(t, 1, 0.3)),
                "braco_d": (3 * s, 0, 0), "braco_e": (-3 * s, 0, 0)}

    def andar(t):
        s = seno(t)
        return {"perna_d": (32 * s, 0, 0), "perna_e": (-32 * s, 0, 0), "braco_d": (-14 * s, 0, 0), "braco_e": (26 * s, 0, 0),
                "corpo": ((4, 0, 5 * s), (0, 0, 0.022 * (0.5 - 0.5 * math.cos(4 * math.pi * t)))), "cabeca": (0, 0, -3 * s)}

    def atacar(t):                                       # golpe de cima para baixo com o espadão
        return {"braco_d": (curva(t, [(0, 0), (0.32, -150), (0.48, -60), (0.62, -40), (1, 0)]), 0, 0),
                "braco_e": (curva(t, [(0, 0), (0.32, -50), (0.48, 20), (1, 0)]), 0, 0),
                "corpo": ((curva(t, [(0, 0), (0.32, -8), (0.48, 14), (1, 0)]), 0, curva(t, [(0, 0), (0.32, 12), (0.48, -10), (1, 0)])),
                          (0, curva(t, [(0, 0), (0.48, -0.05), (1, 0)]), 0)),
                "perna_d": (curva(t, [(0, 0), (0.32, 10), (0.48, -6), (1, 0)]), 0, 0), "perna_e": (curva(t, [(0, 0), (0.32, -14), (0.48, 8), (1, 0)]), 0, 0),
                "cabeca": (curva(t, [(0, 0), (0.32, -6), (0.48, 8), (1, 0)]), 0, 0)}
    return m, {"parado": (48, parado), "andar": (16, andar), "atacar": (18, atacar)}


def cacadora():
    m = P.esqueleto(Modelo("cacadora", 1.85), larg_ombro=0.22, alt_ombro=0.56, r_braco=0.058, comp_braco=0.25, r_perna=0.066,
                    r_cabeca=0.2, perna="#4E3E30", bota=COURO2, braco="#7A5A3A", giro_e=80, giro_d=34, sep_perna=0.092)
    P.rosto(m, sobrancelha="#7A2E14", brava=4)
    CAB, TUN, SAIA = "#8E3A1C", "#7A5A3A", "#5E7A3A"
    m.add("corpo", tr(torno([(0, 0.27), (0.17, 0.275), (0.195, 0.33), (0.18, 0.44), (0.17, 0.53), (0.15, 0.6), (0.09, 0.63), (0, 0.64)], 18), esc=(1, 0.8, 1)), TUN, (0.78, 1.08))
    m.add("corpo", tr(torno([(0, 0.19), (0.2, 0.17), (0.215, 0.22), (0.195, 0.33), (0, 0.33)], 18), esc=(1, 0.84, 1)), SAIA, (0.8, 1.05))
    m.add("corpo", tr(cilindro(0.2, 0.2, 0.04, 18, 0.01), (0, 0, 0.4), esc=(1, 0.82, 1)), COURO2, (1, 1))
    m.add("corpo", tr(caixa(0.06, 0.03, 0.05, 0.012), (0, -0.165, 0.42)), OURO, (1, 1))
    # capa e capuz caído nos ombros, na cor do time
    m.add("corpo", tr(prisma([(-0.18, 0.62), (0.18, 0.62), (0.24, 0.12), (0.08, 0.06), (0, 0.1), (-0.08, 0.06), (-0.24, 0.12)], 0.03, 0.01), (0, 0.17, 0), rot=(8, 0, 0)), TIME, (0.75, 1.1))
    m.add("corpo", tr(toro(0.15, 0.05, 20, 8), (0, 0.02, 0.625), esc=(1, 0.85, 0.8)), TIME, (0.85, 1.1))
    # aljava com flechas nas costas
    m.add("corpo", tr(cilindro(0.05, 0.055, 0.3, 12, 0.01), (-0.08, 0.21, 0.36), rot=(0, 20, 0)), COURO2, (0.85, 1.05))
    for k in range(3):
        m.add("corpo", tr(cilindro(0.009, 0.009, 0.1, 6), (-0.13 - 0.025 * k, 0.21 + 0.015 * (k % 2), 0.64), rot=(0, 20, 0)), MADEIRA2, (1, 1))
        m.add("corpo", tr(cone(0.018, 0.04, 6), (-0.165 - 0.025 * k, 0.21 + 0.015 * (k % 2), 0.73), rot=(0, 20, 0)), TIME, (1, 1))
    # cabelo: topo, franja e rabo de cavalo com fita do time
    m.add("cabeca", tr(esfera(0.205, 20, 12), (0, 0.06, 0.85)), CAB, (0.78, 1.08))
    m.add("cabeca", tr(esfera(1, 12, 8), (-0.05, -0.15, 0.94), rot=(0, 25, 0), esc=(0.13, 0.06, 0.05)), CAB, (1, 1))
    m.add("cabeca", tr(cilindro(0.042, 0.042, 0.04, 10), (0, 0.235, 0.86), rot=(-70, 0, 0)), TIME, (1, 1))
    m.add("cabeca", tubo([(0, 0.25, 0.86), (0, 0.3, 0.78), (0, 0.32, 0.64), (0, 0.3, 0.52)], [0.055, 0.06, 0.045, 0.02], 10), CAB, (0.8, 1.05))
    for lado in (-1, 1):                                  # cílios
        m.add("cabeca", tr(caixa(0.06, 0.012, 0.012, 0.004), ((0.075 * lado + 0.02 * lado), -0.186, 0.852), rot=(0, 18 * lado, 0)), PRETO, (1, 1))
    # arco grande na mão esquerda
    hx, hy, hz = m.mao["braco_e"]
    r = 0.4
    pts = [(hx, hy + r - 0.01 + r * math.cos(math.radians(a)), hz + r * math.sin(math.radians(a))) for a in range(116, 245, 12)]
    m.add("braco_e", tubo(pts, [0.012, 0.02, 0.024, 0.027, 0.03, 0.032, 0.03, 0.027, 0.024, 0.02, 0.012][:len(pts)], 8), MADEIRA, (0.85, 1.1))
    m.add("braco_e", tubo([pts[0], pts[-1]], 0.006, 6), BRANCO, (1, 1))
    m.add("braco_e", tr(cilindro(0.036, 0.036, 0.1, 8, 0.008), (hx, hy - 0.01, hz - 0.05)), TIME, (1, 1))

    def parado(t):
        s = seno(t)
        return {"corpo": ((0, 0, 2 * s), (0, 0, 0.005 * s)), "cabeca": (0, 0, 6 * seno(t, 1, 0.25)), "braco_e": (2 * s, 0, 0), "braco_d": (-2 * s, 0, 0)}

    def andar(t):
        s = seno(t)
        return {"perna_d": (30 * s, 0, 0), "perna_e": (-30 * s, 0, 0), "braco_d": (-12 * s, 0, 0), "braco_e": (4 * s, 0, 0),
                "corpo": ((3, 0, 4 * s), (0, 0, 0.02 * (0.5 - 0.5 * math.cos(4 * math.pi * t))))}

    def atacar(t):                                       # puxa a corda, mira e solta
        return {"braco_d": (curva(t, [(0, 0), (0.35, 40), (0.42, -20), (0.6, -8), (1, 0)]), 0, curva(t, [(0, 0), (0.35, 18), (0.42, 0), (1, 0)])),
                "braco_e": (curva(t, [(0, 0), (0.35, -6), (0.45, 4), (1, 0)]), 0, 0),
                "corpo": ((curva(t, [(0, 0), (0.35, -3), (0.45, 3), (1, 0)]), 0, curva(t, [(0, 0), (0.35, 10), (0.5, 4), (1, 0)])), (0, 0, 0)),
                "cabeca": (0, 0, curva(t, [(0, 0), (0.35, -8), (1, 0)]))}
    return m, {"parado": (48, parado), "andar": (16, andar), "atacar": (14, atacar)}


# ================================================================== peças que o jogo anima (sem ossos)
def espirito():
    m = Modelo("espirito", 1.0)
    F1, F2, F3, ROSTO = "#FF6A1A", "#FFA63A", "#FFE58A", "#5A1A08"
    m.peca("corpo", (0, 0, 0.5))
    m.peca("chama", (0, 0, 0.62), "corpo")
    m.add("corpo", tr(esfera(0.28, 20, 14), (0, 0, 0.5)), F2, (0.85, 1.25))
    m.add("corpo", tr(esfera(0.2, 16, 10), (0, 0.0, 0.62)), F3, (0.95, 1.2))
    for lado in (-1, 1):
        m.add("corpo", tr(esfera(1, 10, 8), (0.085 * lado, -0.272, 0.55), esc=(0.04, 0.02, 0.062)), ROSTO, (1, 1))
        m.add("corpo", tr(esfera(0.013, 6, 5), (0.078 * lado, -0.292, 0.575)), BRANCO, (1.3, 1.3))
        m.add("corpo", tr(caixa(0.075, 0.015, 0.022, 0.007), (0.088 * lado, -0.262, 0.63), rot=(0, -20 * lado, 0)), ROSTO, (1, 1))
    m.add("corpo", tr(prisma([(-0.075, 0.0), (0.075, 0.0), (0.045, -0.04), (0, -0.05), (-0.045, -0.04)], 0.02, 0.006), (0, -0.272, 0.46)), ROSTO, (1, 1))

    def gota(r, h):
        return torno([(0, 0), (r * 0.8, h * 0.08), (r, h * 0.25), (r * 0.7, h * 0.55), (r * 0.3, h * 0.82), (0, h)], 12)
    m.add("chama", tr(gota(0.17, 0.62), (0, 0.06, 0.56), rot=(-22, 0, 0)), F1, (0.85, 1.35))
    m.add("chama", tr(gota(0.1, 0.44), (0, 0.02, 0.6), rot=(-18, 0, 0)), F3, (0.95, 1.2))
    for k in range(6):
        a = 2 * math.pi * k / 6
        m.add("chama", tr(gota(0.08, 0.3), (0.17 * math.cos(a), 0.17 * math.sin(a) + 0.05, 0.58), rot=(-25 - 10 * math.sin(a), 25 * math.cos(a), 0)), F1, (0.85, 1.35))
    m.add("chama", tr(gota(0.13, 0.45), (0, 0.2, 0.45), rot=(-100, 0, 0)), F1, (0.85, 1.3))      # rabo de fogo
    return m, None


def canhao():
    m = Modelo("canhao", 1.0)
    m.peca("base", (0, 0, 0))
    m.peca("giro", (0, 0, 0.2), "base")
    m.peca("cano", (0, -0.02, 0.62), "giro")
    m.add("base", tr(cilindro(0.66, 0.7, 0.1, 24, 0.02), (0, 0, 0)), PEDRA, (0.8, 1.0))
    m.add("base", tr(cilindro(0.6, 0.62, 0.1, 24, 0.02), (0, 0, 0.1)), MADEIRA2, (0.85, 1.0))
    for k in range(8):
        a = 2 * math.pi * k / 8
        m.add("base", tr(esfera(0.03, 8, 6), (0.55 * math.cos(a), 0.55 * math.sin(a), 0.2)), FERRO, (1, 1.1))
    lat = [(-0.36, 0.0), (0.3, 0.0), (0.3, 0.14), (0.12, 0.34), (-0.1, 0.36), (-0.36, 0.2)]
    for lado in (-1, 1):
        m.add("giro", tr(tr(prisma(lat, 0.07, 0.015), rot=(0, 0, 90)), (0.2 * lado, 0, 0.22)), MADEIRA, (0.8, 1.05))
        m.add("giro", tr(tr(prisma([(x * 0.86, z * 0.8 + 0.02) for x, z in lat], 0.012, 0.004), rot=(0, 0, 90)), (0.24 * lado, 0, 0.24)), TIME, (0.85, 1.1))
        for y in (-0.18, 0.0, 0.16):
            m.add("giro", tr(esfera(0.022, 8, 6), (0.25 * lado, y, 0.34)), OURO, (1, 1.1))
        for y in (-0.22, 0.2):                           # rodas com aro de ferro
            m.add("giro", tr(cilindro(0.13, 0.13, 0.06, 16, 0.01), (0.27 * lado - 0.03, y, 0.13), rot=(0, 90, 0)), MADEIRA2, (0.85, 1.05))
            m.add("giro", tr(toro(0.13, 0.018, 18, 6), (0.27 * lado, y, 0.13), rot=(0, 90, 0)), FERRO, (0.9, 1.1))
            m.add("giro", tr(esfera(0.03, 8, 6), (0.3 * lado, y, 0.13)), FERRO, (1, 1))
    for y in (-0.22, 0.2):
        m.add("giro", tr(cilindro(0.025, 0.025, 0.56, 8), (-0.28, y, 0.13), rot=(0, 90, 0)), FERRO, (1, 1))
    m.add("giro", tr(cilindro(0.04, 0.04, 0.48, 10), (-0.24, -0.02, 0.62), rot=(0, 90, 0)), FERRO, (1, 1))   # munhões
    perfil = [(0, -0.42), (0.1, -0.42), (0.14, -0.37), (0.16, -0.3), (0.16, -0.12), (0.145, -0.06), (0.12, 0.38), (0.135, 0.42),
              (0.14, 0.5), (0.105, 0.5), (0.09, 0.47), (0, 0.47)]
    cano = lambda f: tr(f, (0, -0.02, 0.62), rot=(82, 0, 0))    # noqa: E731  deitado, apontando para a frente e um pouco para cima
    m.add("cano", cano(torno(perfil, 20)), FERRO, (0.7, 1.15))
    m.add("cano", cano(tr(esfera(0.07, 10, 8), (0, 0, -0.47))), FERRO, (0.9, 1.1))
    m.add("cano", cano(tr(toro(0.142, 0.024, 20, 6), (0, 0, 0.12))), TIME, (0.9, 1.1))
    m.add("cano", cano(tr(toro(0.163, 0.02, 20, 6), (0, 0, -0.25))), OURO, (1, 1.1))
    m.add("cano", cano(tr(cilindro(0.1, 0.1, 0.02, 16), (0, 0, 0.455))), "#0E0F12", (1, 1))
    return m, None


def estabulo():
    m = Modelo("estabulo", 1.0)
    PAREDE, TABUA, ESC, FENO = "#B07A44", "#8A5A30", "#2A1F1A", "#E9C866"
    m.peca("corpo", (0, 0, 0))
    m.peca("porta_d", (-0.34, -0.655, 0.12), "corpo")
    m.peca("porta_e", (0.34, -0.655, 0.12), "corpo")
    m.add("corpo", tr(caixa(1.76, 1.36, 0.16, 0.04), (0, 0, 0.08)), PEDRA, (0.75, 1.0))
    m.add("corpo", tr(caixa(1.6, 1.22, 0.95, 0.03), (0, 0, 0.62)), PAREDE, (0.78, 1.05))
    for x in (-0.79, 0.79):
        for y in (-0.6, 0.6):
            m.add("corpo", tr(caixa(0.12, 0.12, 1.0, 0.02), (x, y, 0.64)), TABUA, (0.8, 1.0))
    for k in range(-3, 4):                               # frisos das tábuas nas laterais e atrás
        for lado in (-1, 1):
            m.add("corpo", tr(caixa(0.012, 0.02, 0.9, 0.004), (0.802 * lado, 0.16 * k, 0.62)), TABUA, (1, 1))
        m.add("corpo", tr(caixa(0.02, 0.012, 0.9, 0.004), (0.21 * k, 0.612, 0.62)), TABUA, (1, 1))
    m.add("corpo", tr(caixa(0.72, 0.03, 0.86, 0.01), (0, -0.6, 0.55)), ESC, (1, 1))
    m.add("corpo", tr(caixa(0.86, 0.07, 0.08, 0.02), (0, -0.63, 1.0)), TABUA, (0.85, 1.0))
    for lado, p in ((-1, "porta_d"), (1, "porta_e")):
        cx = 0.17 * lado
        m.add(p, tr(caixa(0.33, 0.05, 0.82, 0.015), (cx, -0.655, 0.53)), TABUA, (0.8, 1.05))
        for s in (-1, 1):
            m.add(p, tr(caixa(0.05, 0.02, 0.84, 0.01), (cx, -0.685, 0.53), rot=(0, 22 * s, 0)), PAREDE, (0.9, 1.05))
        m.add(p, tr(esfera(0.022, 8, 6), (0.04 * lado, -0.69, 0.55)), FERRO, (1, 1))
    # telhado na cor do time, cumeeira e as empenas
    for lado in (-1, 1):
        m.add("corpo", tr(caixa(0.98, 1.5, 0.07, 0.025), (0.43 * lado, 0, 1.36), rot=(0, 32 * lado, 0)), TIME, (0.75, 1.1))
    m.add("corpo", tr(cilindro(0.06, 0.06, 1.56, 10), (0, 0.78, 1.64), rot=(90, 0, 0)), TABUA, (0.85, 1.0))
    for y in (-0.6, 0.6):
        m.add("corpo", tr(prisma([(-0.8, 0), (0.8, 0), (0, 0.52)], 0.06, 0.01), (0, y, 1.09)), PAREDE, (0.85, 1.05))
    m.add("corpo", tr(caixa(0.3, 0.03, 0.22, 0.01), (0, -0.635, 1.27)), ESC, (1, 1))           # janela do feno
    m.add("corpo", tr(esfera(1, 10, 6), (0, -0.64, 1.2), esc=(0.14, 0.05, 0.05)), FENO, (0.9, 1.1))
    # estandarte do time com uma pegada, fardos de feno e o cocho
    m.add("corpo", tr(caixa(0.2, 0.02, 0.44, 0.006), (-0.6, -0.68, 0.72)), TIME, (0.8, 1.1))
    m.add("corpo", tr(esfera(1, 10, 8), (-0.6, -0.695, 0.68), esc=(0.05, 0.01, 0.045)), OURO, (1, 1))
    for dx, dz in ((-0.045, 0.75), (0.0, 0.77), (0.045, 0.75)):
        m.add("corpo", tr(esfera(0.018, 8, 6), (-0.6 + dx, -0.695, dz)), OURO, (1, 1))
    m.add("corpo", tr(caixa(0.36, 0.26, 0.24, 0.05), (0.7, -0.88, 0.12)), FENO, (0.8, 1.05))
    m.add("corpo", tr(caixa(0.3, 0.22, 0.2, 0.05), (0.66, -0.86, 0.33), rot=(0, 0, 12)), FENO, (0.82, 1.05))
    m.add("corpo", tr(caixa(0.2, 0.5, 0.15, 0.02), (-0.93, 0.15, 0.075)), TABUA, (0.85, 1.0))
    m.add("corpo", tr(caixa(0.15, 0.44, 0.02, 0.006), (-0.93, 0.15, 0.14)), "#5FB8E8", (1, 1.1))
    m.add("corpo", tr(cilindro(0.02, 0.02, 0.5, 8), (0, -0.62, 1.62)), MADEIRA2, (1, 1))
    m.add("corpo", tr(prisma([(0, 0), (0.3, -0.03), (0.22, -0.11), (0.3, -0.2), (0, -0.22)], 0.02, 0.006), (0, -0.62, 2.1), rot=(0, 0, 90)), TIME, (0.85, 1.12))
    return m, None


def poco():
    m = Modelo("poco", 1.0)
    AGUA = "#62F0FF"
    m.peca("corpo", (0, 0, 0))
    m.peca("agua", (0, 0, 0.42), "corpo")
    m.peca("manivela", (0.58, 0, 1.22), "corpo")
    m.peca("balde", (0, 0, 1.2), "corpo")
    for fila in range(2):                                # muro redondo: duas fileiras de pedras desencontradas
        for k in range(12):
            a = 2 * math.pi * (k + 0.5 * fila) / 12
            m.add("corpo", tr(caixa(0.27, 0.16, 0.24, 0.05), (0.5 * math.cos(a), 0.5 * math.sin(a), 0.13 + 0.24 * fila), rot=(0, 0, math.degrees(a) + 90)),
                  PEDRA if (k + fila) % 2 == 0 else PEDRA2, (0.8, 1.05))
    m.add("corpo", tr(toro(0.5, 0.065, 28, 8), (0, 0, 0.52)), PEDRA, (0.85, 1.05))
    m.add("corpo", tr(cilindro(0.44, 0.44, 0.4, 24), (0, 0, 0.02)), "#1A2430", (1, 1))
    for a in (0.6, 2.2, 4.1):                            # runas brilhando nas pedras
        m.add("corpo", tr(esfera(1, 8, 6), (0.585 * math.cos(a), 0.585 * math.sin(a), 0.3), rot=(0, 0, math.degrees(a)), esc=(0.012, 0.05, 0.05)), AGUA, (1.2, 1.4))
    m.add("agua", tr(cilindro(0.43, 0.43, 0.03, 24), (0, 0, 0.42)), AGUA, (1.1, 1.3))
    for lado in (-1, 1):
        m.add("corpo", tr(caixa(0.09, 0.09, 1.12, 0.02), (0.52 * lado, 0, 1.0)), MADEIRA2, (0.8, 1.05))
    m.add("corpo", tr(cilindro(0.06, 0.06, 1.0, 12), (-0.5, 0, 1.22), rot=(0, 90, 0)), MADEIRA, (0.85, 1.05))
    for x in (-0.06, 0.0, 0.06):
        m.add("corpo", tr(toro(0.065, 0.012, 12, 5), (x, 0, 1.22), rot=(0, 90, 0)), "#C9A66B", (1, 1))
    m.add("manivela", tr(caixa(0.03, 0.03, 0.2, 0.008), (0.6, 0, 1.13)), FERRO, (1, 1))
    m.add("manivela", tr(cilindro(0.022, 0.022, 0.12, 8), (0.6, 0, 1.04), rot=(0, 90, 0)), MADEIRA2, (1, 1))
    m.add("balde", tubo([(0, 0, 1.16), (0, 0, 0.9)], 0.008, 5), "#C9A66B", (1, 1))
    m.add("balde", tr(torno([(0, 0), (0.09, 0), (0.11, 0.15), (0.115, 0.16), (0, 0.16)], 14), (0, 0, 0.74)), MADEIRA, (0.85, 1.05))
    m.add("balde", tr(toro(0.105, 0.012, 14, 5), (0, 0, 0.82)), FERRO, (1, 1))
    for lado in (-1, 1):                                 # telhadinho do time
        m.add("corpo", tr(caixa(1.25, 0.5, 0.05, 0.02), (0, 0.2 * lado, 1.66), rot=(-35 * lado, 0, 0)), TIME, (0.75, 1.1))
    m.add("corpo", tr(cilindro(0.035, 0.035, 1.3, 8), (-0.65, 0, 1.8), rot=(0, 90, 0)), MADEIRA2, (1, 1))
    m.add("corpo", tr(caixa(0.16, 0.02, 0.3, 0.006), (0.52, -0.06, 1.24)), TIME, (0.8, 1.1))
    m.add("corpo", tr(esfera(0.03, 8, 6), (0.52, -0.075, 1.27)), OURO, (1, 1.1))
    return m, None


def barril():
    m = Modelo("barril", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", torno([(0, -0.36), (0.24, -0.36), (0.29, -0.2), (0.31, 0), (0.29, 0.2), (0.24, 0.36), (0, 0.36)], 20), "#9A6236", (0.8, 1.05))
    for k in range(10):                                   # frestas entre as tábuas
        a = 2 * math.pi * k / 10
        pts = [(rr * 1.01 * math.cos(a), rr * 1.01 * math.sin(a), z) for rr, z in ((0.25, -0.33), (0.29, -0.2), (0.31, 0), (0.29, 0.2), (0.25, 0.33))]
        m.add("corpo", tubo(pts, 0.009, 5), "#6E4424", (1, 1))
    for z, R in ((-0.27, 0.272), (0.27, 0.272), (-0.11, 0.304), (0.11, 0.304)):
        m.add("corpo", tr(toro(R, 0.022, 24, 6), (0, 0, z)), FERRO, (0.9, 1.1))
    m.add("corpo", tr(toro(0.316, 0.03, 24, 6), (0, 0, 0)), TIME, (0.9, 1.1))
    m.add("corpo", tr(cilindro(0.23, 0.23, 0.02, 20), (0, 0, 0.35)), "#7A4A26", (1, 1))
    # máscara de bandido pintada
    m.add("corpo", tr(prisma([(-0.17, 0.03), (0.17, 0.03), (0.15, -0.05), (0.04, -0.04), (0, -0.07), (-0.04, -0.04), (-0.15, -0.05)], 0.03, 0.006),
                       (0, -0.3, 0.19)), "#1E1A22", (1, 1))
    for lado in (-1, 1):
        m.add("corpo", tr(esfera(1, 8, 6), (0.075 * lado, -0.318, 0.185), esc=(0.03, 0.01, 0.02)), BRANCO, (1, 1))
    return m, None


def meteoro():
    m = Modelo("meteoro", 1.0)
    m.peca("corpo", (0, 0, 0))
    rnd = random.Random(7)

    def forma(x, y, z):
        return 1 + 0.16 * math.sin(3.1 * x + 1.7 * y) * math.cos(2.3 * z + 0.4) + 0.08 * math.sin(7 * y + 2 * z)

    def sup(a, b, k=1.0):
        x, y, z = 0.5 * math.cos(b) * math.cos(a), 0.5 * math.cos(b) * math.sin(a), 0.5 * math.sin(b)
        n = forma(x, y, z) * k
        return (x * n, y * n, z * n * 0.92)
    vs, fs = esfera(0.5, 18, 12)
    m.add("corpo", ([(x * forma(x, y, z), y * forma(x, y, z), z * forma(x, y, z) * 0.92) for x, y, z in vs], fs), "#4B3B35", (0.7, 1.15), liso=False)
    for k in range(16):                                   # veios de lava
        a0, b0 = rnd.uniform(0, 6.28), rnd.uniform(-1.0, 1.0)
        pts, b = [], b0
        for j in range(6):
            b = max(-1.3, min(1.3, b + rnd.uniform(-0.22, 0.22)))
            pts.append(sup(a0 + 0.26 * j, b, 1.012))
        m.add("corpo", tubo(pts, [0.03, 0.026, 0.024, 0.022, 0.018, 0.01], 5), "#FF7A1F", (1, 1.3))
    for k in range(12):
        a, b = rnd.uniform(0, 6.28), rnd.uniform(-1.1, 1.1)
        m.add("corpo", tr(esfera(rnd.uniform(0.05, 0.08), 8, 6), sup(a, b, 0.98)), "#FFB347", (1.1, 1.3))
    return m, None


def lapides():
    m = Modelo("lapides", 1.0)
    G, G2, MUSGO, TERRA = "#A3A6AE", "#7D818B", "#6E9B4A", "#6B4F35"
    for nome in ("lapide_a", "lapide_b", "lapide_c"):
        m.peca(nome, (0, 0, 0))
        m.add(nome, tr(esfera(1, 14, 8), (0, 0.02, 0.0), esc=(0.32, 0.26, 0.08)), TERRA, (0.8, 1.0))
    m.add("lapide_a", prisma([(-0.2, 0), (0.2, 0), (0.2, 0.4), (0.15, 0.5), (0.08, 0.55), (0, 0.565), (-0.08, 0.55), (-0.15, 0.5), (-0.2, 0.4)], 0.12, 0.025), G, (0.78, 1.05))
    m.add("lapide_a", tr(caixa(0.05, 0.02, 0.24, 0.006), (0, -0.065, 0.32)), G2, (1, 1))
    m.add("lapide_a", tr(caixa(0.16, 0.02, 0.05, 0.006), (0, -0.065, 0.37)), G2, (1, 1))
    m.add("lapide_a", tr(esfera(1, 10, 6), (-0.12, -0.045, 0.05), esc=(0.1, 0.06, 0.05)), MUSGO, (0.9, 1.05))
    m.add("lapide_b", tr(caixa(0.1, 0.1, 0.62, 0.02), (0, 0, 0.31)), G, (0.78, 1.05))
    m.add("lapide_b", tr(caixa(0.38, 0.1, 0.1, 0.02), (0, 0, 0.44)), G, (0.85, 1.05))
    m.add("lapide_b", tr(esfera(1, 10, 6), (0.05, -0.05, 0.04), esc=(0.08, 0.05, 0.05)), MUSGO, (0.9, 1.05))
    m.add("lapide_c", prisma([(-0.22, 0), (0.22, 0), (0.22, 0.32), (0.12, 0.4), (0.05, 0.33), (-0.04, 0.44), (-0.22, 0.36)], 0.13, 0.02), G2, (0.75, 1.05))
    m.add("lapide_c", tr(esfera(1, 10, 6), (0.12, -0.05, 0.06), esc=(0.09, 0.05, 0.05)), MUSGO, (0.9, 1.05))
    return m, None


# 14/11/2026: os bichos e dinossauros do jogo passaram a vir de blender/bichos_reais.py (modelos da internet retrabalhados) e
# o bárbaro e a caçadora de blender/kaykit.py; as versões daqui ficam só de referência (rode com so:lobo para gerar uma).
PROPRIOS = {"lobo": lobo, "touro": touro, "aranha": aranha, "vespa": vespa, "raptor": raptor, "rex": rex, "triceratops": triceratops,
            "barbaro": barbaro, "cacadora": cacadora}
MODELOS = {"espirito": espirito, "canhao": canhao, "estabulo": estabulo, "poco": poco, "barril": barril, "meteoro": meteoro, "lapides": lapides}
MODELOS.update({k: v for k, v in PROPRIOS.items() if k in SO})


def construir(nome, cor=None):
    """Monta o modelo (cor None = magenta do time, para o jogo). Devolve (objeto de cima, {ação: Action})."""
    kit.COR_TIME = cor
    m, anims = MODELOS[nome]()
    raiz = m.montar()
    if not anims:
        return raiz, {}
    arm = armar(m, raiz)
    return arm, {k: acao(arm, k, n, f) for k, (n, f) in anims.items()}


# ------------------------------------------------------------------ modelos do jogo
if "modelos" in QUAIS:
    for nome in MODELOS:
        if SO and nome not in SO:
            continue
        kit.limpar()
        obj, acoes = construir(nome)
        arq = JOGO / "modelos" / f"{nome}.glb"
        if acoes:
            exportar_animado(arq)
        else:
            kit.exportar(arq)
        print("modelo", nome, arq.stat().st_size // 1024, "kB", sorted(acoes), flush=True)

# ------------------------------------------------------------------ prévias para conferir (com chão, poucas amostras)
if PREVIA:
    PREVIA.mkdir(parents=True, exist_ok=True)
    for nome in MODELOS:
        if SO and nome not in SO:
            continue
        kit.limpar()
        obj, acoes = construir(nome, AZUL)
        alt = max((o.matrix_world @ Vector(c)).z for o in bpy.data.objects if o.type == "MESH" for c in o.bound_box)
        for qual, az in (("atacar", -35), ("andar", -90)):
            if acoes:
                a = acoes.get(qual) or acoes["parado"]
                posar(obj, a, max(1, int(a.frame_range[1] * 0.42)))
            elif qual == "andar":
                continue
            kit.foto(PREVIA / f"{nome}_{qual}.png", alvo=(0, 0, alt * 0.45), dist=max(2.2, alt * 2.6), az=az, el=14, larg=420, alt=420, amostras=12)
        print("prévia", nome, flush=True)

# ------------------------------------------------------------------ arte das cartas (em azul, fundo transparente)
# carta: (modelo, [(x, y, giro, ação, quadro)], alvo, distância, azimute, elevação)
CARTAS = {
    "espiritos": ("espirito", [(0, 0, 0, None, 0), (-0.55, 0.42, 15, None, 0), (0.56, 0.46, -15, None, 0)], (0, 0.2, 0.62), 3.25, -20, 8),
    "canhao": ("canhao", [(0, 0, 0, None, 0)], (0, 0, 0.42), 3.0, -36, 18),
    "estabulo": ("estabulo", [(0, 0, 0, None, 0)], (0, 0, 0.9), 5.2, -34, 16),
    "poco": ("poco", [(0, 0, 0, None, 0)], (0, 0, 0.92), 4.2, -32, 14),
}
if "cartas" in QUAIS:
    for carta, (nome, onde, alvo, dist, az, el) in CARTAS.items():
        if SO and carta not in SO and nome not in SO:
            continue
        kit.limpar()
        for x, y, giro, qual, quadro in onde:
            obj, acoes = construir(nome, AZUL)
            obj.location = (x, y, 0)
            obj.rotation_euler = (0, 0, math.radians(giro))
            if acoes and qual:
                posar(obj, acoes[qual], quadro)
        bpy.context.scene.frame_set(onde[0][4] or 1)
        kit.foto(JOGO / "cartas" / f"{carta}.png", alvo=alvo, dist=dist, az=az, el=el, larg=512, alt=512, amostras=48, transparente=True)
        print("carta", carta, flush=True)


# ------------------------------------------------------------------ arte das magias (cena de ícone do interface.py)
def arte_magias():
    sys.argv = [sys.argv[0], str(JOGO), ""]              # o interface.py lê a pasta do jogo (a fonte não é usada aqui)
    import interface as I
    R = lambda *g: tuple(math.radians(v) for v in g)     # noqa: E731
    rnd = random.Random(3)
    feitas = []

    def quer(n):
        return not SO or n in SO

    if quer("tornado"):
        I.cena_nova(384, 64)
        vento, vento2 = I.mat("vento", "#DCE6F0", rug=0.6, emis="#B8C8DA", forca=0.25), I.mat("vento2", "#A3B2C4", rug=0.7)
        for k in range(10):
            I.anel((0.14 * math.sin(k * 0.9), 0, -1.45 + k * 0.36), 0.22 + 0.17 * k, 0.085 + 0.013 * k, vento if k % 2 == 0 else vento2,
                   rot=R(8 * math.sin(k), 6 * math.cos(k), 0))
        tabua, folha = I.mat("tabua", "#A8713F", rug=0.8), I.mat("folha", "#6FBF4A", rug=0.7)
        for k in range(9):
            a, z = rnd.uniform(0, 6.28), rnd.uniform(-1.0, 1.9)
            p = (1.45 * math.cos(a), 1.45 * math.sin(a) * 0.6, z)
            if k % 2:
                I.caixa(p, (0.42, 0.1, 0.05), tabua, 0.01, rot=R(rnd.uniform(0, 90), rnd.uniform(0, 90), rnd.uniform(0, 90)))
            else:
                I.esfera(p, 0.1, folha, (1.4, 0.8, 0.3))
        I.esfera((0, 0.6, 0.3), 2.3, I.halo("halo_tornado", "#9FC4FF", 1.0))
        I.camera((0, 0, 0.3), 8.6, -8, 8, 50)
        I.render(JOGO / "cartas" / "tornado.png")
        feitas.append("tornado")

    if quer("terremoto"):
        I.cena_nova(384, 64)
        terra, grama, lava = I.mat("terra", "#5E4028", rug=0.95), I.mat("grama", "#4E9A3A", rug=0.85), I.brilho("lava", "#FF6A1A", 12.0)
        I.cil((0, 0, -0.62), 1.45, 0.3, lava, 48)
        n = 7
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n + 0.05, 2 * math.pi * (k + 1) / n - 0.05
            meio = (a0 + a1) / 2
            pts = [(0.12 * math.cos(meio), 0.12 * math.sin(meio))] + [(1.6 * math.cos(a0 + (a1 - a0) * j / 6), 1.6 * math.sin(a0 + (a1 - a0) * j / 6)) for j in range(7)]
            sobe, inc = rnd.uniform(-0.1, 0.25), rnd.uniform(-12, 12)
            loc = (0.1 * math.cos(meio), 0.1 * math.sin(meio), -0.45 + sobe)
            I.prisma(pts, 0.5, terra, loc=loc, rot=R(inc, -inc * 0.6, 0), bisel=0.04)
            I.prisma(pts, 0.1, grama, loc=(loc[0], loc[1], loc[2] + 0.29), rot=R(inc, -inc * 0.6, 0), bisel=0.03)
        pedra = I.mat("pedra", "#8E8A86", rug=0.85)
        for k in range(7):
            a = rnd.uniform(0, 6.28)
            I.esfera((rnd.uniform(0.2, 1.1) * math.cos(a), rnd.uniform(0.2, 1.1) * math.sin(a), rnd.uniform(0.3, 1.5)), rnd.uniform(0.09, 0.17), pedra,
                     (1, rnd.uniform(0.7, 1.2), rnd.uniform(0.7, 1.1)), 12)
        poeira = I.mat("poeira_t", "#C9A77A", rug=1.0)
        for k in range(6):
            a = 2 * math.pi * k / 6 + 0.3
            I.esfera((1.5 * math.cos(a), 1.5 * math.sin(a), -0.15), rnd.uniform(0.25, 0.4), poeira, (1, 1, 0.75))
        I.camera((0, 0, -0.25), 7.6, -18, 34, 50)
        I.render(JOGO / "cartas" / "terremoto.png")
        feitas.append("terremoto")

    if quer("escudo"):
        I.cena_nova(384, 64)
        forma = [(0, -1.35), (0.72, -0.75), (1.0, 0.1), (0.95, 0.95), (0, 1.15), (-0.95, 0.95), (-1.0, 0.1), (-0.72, -0.75)]
        I.prisma([(x * 1.1, y * 1.08) for x, y in forma], 0.16, I.OURO(), loc=(0, 0.08, 0.15), bisel=0.05)
        I.prisma(forma, 0.24, I.mat("azul", "#2F7BFF", metal=0.2, rug=0.35), loc=(0, 0, 0.15), bisel=0.06)
        estrela = [(0.42 * math.cos(math.radians(90 + 36 * k)) * (1 if k % 2 == 0 else 0.45), 0.42 * math.sin(math.radians(90 + 36 * k)) * (1 if k % 2 == 0 else 0.45))
                   for k in range(10)]
        I.prisma(estrela, 0.1, I.OURO(), loc=(0, -0.16, 0.25), bisel=0.03)
        for k in range(12):
            a = 2 * math.pi * k / 12
            I.esfera((1.55 * math.cos(a), -0.3, 0.2 + 1.45 * math.sin(a)), 0.045 + 0.02 * (k % 3), I.brilho(f"brilho{k}", "#BFE6FF", 6.0))
        I.esfera((0, 0.4, 0.2), 2.0, I.halo("halo_escudo", "#7FC4FF", 1.6))
        I.camera((0, 0, 0.15), 8.4, -10, 6, 50)
        I.render(JOGO / "cartas" / "escudo.png")
        feitas.append("escudo")

    if quer("meteoro"):
        I.cena_nova(384, 64)
        pedra, _ = construir("meteoro", AZUL)
        pedra.location, pedra.scale = (0.35, 0, 0.35), (2.3, 2.3, 2.3)
        for k, (cor, forca, r, h) in enumerate((("#FF5A1F", 5.0, 0.95, 3.2), ("#FF9A2A", 6.0, 0.7, 2.6), ("#FFE27A", 8.0, 0.42, 2.0))):
            I.cil((1.25 + 0.15 * k, 0.4 + 0.1 * k, 1.45 + 0.1 * k), r, h, I.brilho(f"fogo{k}", cor, forca), 32, rot=R(0, 42, 0), r2=0.0)
        for k in range(10):
            I.esfera((rnd.uniform(-0.9, 1.6), rnd.uniform(-0.4, 0.4), rnd.uniform(-1.2, 1.6)), rnd.uniform(0.03, 0.07), I.brilho(f"brasa{k}", "#FFC24A", 8.0))
        I.esfera((0.3, 0.6, 0.4), 2.2, I.halo("halo_meteoro", "#FF8A3A", 1.4))
        I.camera((0.25, 0, 0.3), 8.6, -10, 6, 50)
        I.render(JOGO / "cartas" / "meteoro.png")
        feitas.append("meteoro")

    if quer("barril"):
        I.cena_nova(384, 64)
        b, _ = construir("barril", AZUL)
        b.location, b.scale, b.rotation_euler = (0, 0, 0.25), (2.6, 2.6, 2.6), R(-24, 18, 30)
        linha = I.brilho("risco", "#FFFFFF", 3.0)
        for k in range(6):
            I.cil((-1.1 - 0.12 * k, 0.4, -0.6 + 0.32 * k), 0.025, 1.1 + 0.15 * (k % 3), linha, 8, rot=R(0, -55, 0))
        poeira = I.mat("poeira", "#E8D7A8", rug=1.0)
        for k in range(5):
            I.esfera((0.2 + rnd.uniform(-0.9, 0.9), 0.3, -1.25 + rnd.uniform(-0.1, 0.15)), rnd.uniform(0.18, 0.32), poeira, (1, 1, 0.7))
        I.esfera((0, 0.6, 0.2), 2.0, I.halo("halo_barril", "#FFD27A", 1.0))
        I.camera((0, 0, 0.1), 8.2, -10, 10, 50)
        I.render(JOGO / "cartas" / "barril.png")
        feitas.append("barril")

    if quer("cemiterio"):
        I.cena_nova(384, 64)
        raiz, _ = construir("lapides", AZUL)
        raiz.scale = (2.0, 2.0, 2.0)
        for nome, loc, giro in (("lapide_a", (0, 0, 0), 0), ("lapide_b", (-0.6, 0.3, 0), 18), ("lapide_c", (0.6, 0.28, 0), -16)):
            o = bpy.data.objects[nome]
            o.location, o.rotation_euler = loc, R(0, 0, giro)
        osso = I.mat("osso", "#F2EEE2", rug=0.5)
        bx, by = 0.0, -0.75                               # mão de esqueleto saindo da terra
        I.cil((bx, by, -0.25), 0.07, 0.6, osso, 16, rot=R(-8, 0, 0))
        I.esfera((bx, by - 0.04, 0.08), 0.13, osso, (1, 0.7, 1))
        for k in range(4):
            a = math.radians(-30 + 20 * k)
            I.cil((bx + 0.17 * math.sin(a), by - 0.06, 0.26 + 0.02 * math.cos(a)), 0.026, 0.3, osso, 10, rot=R(-10, a * 57.3 * 0.6, 0))
        I.cil((bx - 0.17, by - 0.05, 0.14), 0.026, 0.22, osso, 10, rot=R(0, -60, 0))
        terra = I.mat("terra", "#6B4F35", rug=0.95)
        I.esfera((bx, by, -0.42), 0.35, terra, (1.3, 1.0, 0.45))
        for k in range(9):
            a = rnd.uniform(0, 6.28)
            I.esfera((1.3 * math.cos(a), -0.3 + 0.2 * math.sin(a), rnd.uniform(0.0, 1.5)), rnd.uniform(0.04, 0.08), I.brilho(f"alma{k}", "#9FFFD0", 7.0))
        I.esfera((0, 0.5, 0.3), 2.1, I.halo("halo_cemiterio", "#9B7DFF", 1.3))
        I.camera((0, 0, 0.35), 7.6, -12, 10, 50)
        I.render(JOGO / "cartas" / "cemiterio.png")
        feitas.append("cemiterio")
    return feitas


if "magias" in QUAIS or "cartas" in QUAIS:
    print("magias", arte_magias(), flush=True)
