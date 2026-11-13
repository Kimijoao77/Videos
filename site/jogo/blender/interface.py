"""Arte da interface do jogo, feita no Blender (Cycles, fundo transparente): ícones 3D (moeda, troféu, coroa, espadas,
engrenagem, cartas, saco de moedas, bandeira, escudo, estrela), os 4 baús (fechado e aberto), o logo em 3D e a arte das
cartas novas (Relâmpago, Gelo, Poção de Cura e Exército de Esqueletos).
Uso: python interface.py PASTA_DO_JOGO FONTE.ttf [nomes...]   (sem nomes, faz tudo)"""
import math
import sys
from pathlib import Path

import bpy
import bmesh  # noqa: E402
from mathutils import Euler, Vector

JOGO = Path(sys.argv[1])
FONTE = sys.argv[2]
QUAIS = set(sys.argv[3:])
UI = JOGO / "img" / "ui"
UI.mkdir(parents=True, exist_ok=True)
CARTAS = JOGO / "cartas"


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (1.0,)


# ------------------------------------------------------------------ cena, luzes e materiais
def cena_nova(res=512, amostras=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = amostras
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "Medium High Contrast"
    w = bpy.data.worlds.new("mundo")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = lin("#8FA8D8")
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    luz("chave", (3.5, -4.5, 6.0), 900, 3.0, "#FFF4E0")
    luz("recorte", (-4.0, 4.0, 3.5), 700, 2.0, "#9CC8FF")
    luz("baixo", (0.0, -5.0, -1.5), 120, 4.0, "#FFE2B0")
    return sc


def luz(nome, pos, energia, tam, cor):
    d = bpy.data.lights.new(nome, "AREA")
    d.energy = energia
    d.size = tam
    d.color = lin(cor)[:3]
    o = bpy.data.objects.new(nome, d)
    o.location = pos
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(o)
    return o


def camera(alvo=(0, 0, 0), dist=6.0, az=-25, el=18, lente=50, orto=None):
    d = bpy.data.cameras.new("cam")
    d.lens = lente
    if orto:
        d.type = "ORTHO"
        d.ortho_scale = orto
    o = bpy.data.objects.new("cam", d)
    a, e = math.radians(az), math.radians(el)
    p = Vector(alvo) + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    o.location = p
    o.rotation_euler = (Vector(alvo) - p).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(o)
    bpy.context.scene.camera = o
    return o


def mat(nome, cor, metal=0.0, rug=0.45, emis=None, forca=0.0, alfa=1.0, transm=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin(cor)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rug
    if emis:
        b.inputs["Emission Color"].default_value = lin(emis)
        b.inputs["Emission Strength"].default_value = forca
    if transm:
        b.inputs["Transmission Weight"].default_value = transm
    if alfa < 1.0:
        b.inputs["Alpha"].default_value = alfa
        m.blend_method = "BLEND"
    return m


def brilho(nome, cor, forca=4.0):
    """Só luz (feixes, faíscas, o brilho de dentro do baú)."""
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = lin(cor)
    e.inputs[1].default_value = forca
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def halo(nome, cor, forca=2.5):
    """Brilho que some nas bordas (esfera com transparência pelo ângulo)."""
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs[0].default_value = 0.35
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1)       # no meio: brilho meio transparente
    cr.color_ramp.elements[1].position = 0.8
    cr.color_ramp.elements[1].color = (1, 1, 1, 1)                # na borda: some
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = lin(cor)
    e.inputs[1].default_value = forca
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Facing"], cr.inputs[0])
    nt.links.new(cr.outputs[0], mx.inputs[0])
    nt.links.new(e.outputs[0], mx.inputs[1])
    nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs[0])
    m.blend_method = "BLEND"
    return m


# ------------------------------------------------------------------ peças
def ligar(o, m=None):
    bpy.context.scene.collection.objects.link(o) if o.name not in bpy.context.scene.collection.objects else None
    if m is not None:
        o.data.materials.clear()
        o.data.materials.append(m)
    return o


def ativo(o):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)


def suave(o, bisel=0.0, seg=3, sub=0):
    ativo(o)
    if bisel:
        md = o.modifiers.new("b", "BEVEL")
        md.width = bisel
        md.segments = seg
        md.limit_method = "ANGLE"
    if sub:
        md = o.modifiers.new("s", "SUBSURF")
        md.levels = md.render_levels = sub
    for p in o.data.polygons:
        p.use_smooth = True
    md = o.modifiers.new("n", "WEIGHTED_NORMAL") if bisel else None
    return o


def caixa(c, s, m, bisel=0.04, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=c, rotation=rot)
    o = bpy.context.object
    o.scale = s
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    return suave(o, bisel)


def cil(c, r, h, m, v=48, rot=(0, 0, 0), r2=None, bisel=0.0):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=c, rotation=rot, vertices=v)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=h, location=c, rotation=rot, vertices=v)
    o = bpy.context.object
    o.data.materials.append(m)
    return suave(o, bisel)


def esfera(c, r, m, esc=(1, 1, 1), seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=c, segments=seg, ring_count=seg // 2)
    o = bpy.context.object
    o.scale = esc
    o.data.materials.append(m)
    return suave(o)


def anel(c, R, r, m, rot=(0, 0, 0), arco=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=c, rotation=rot, major_segments=64, minor_segments=16)
    o = bpy.context.object
    o.data.materials.append(m)
    return suave(o)


def torno(perfil, m, seg=64, loc=(0, 0, 0)):
    """Contorno (r, z) girado em volta de Z (aberto: só a casca)."""
    bm = bmesh.new()
    aneis = []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        aneis.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in perfil])
    for k in range(seg):
        for i in range(len(perfil) - 1):
            a, b = aneis[k], aneis[(k + 1) % seg]
            bm.faces.new((a[i], b[i], b[i + 1], a[i + 1]))
    me = bpy.data.meshes.new("torno")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("torno", me)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    return suave(o)


def prisma(perfil, esp, m, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), bisel=0.03):
    """Polígono 2D (x, y) com espessura (extrudado em Z local), de pé de frente para a câmera."""
    me = bpy.data.meshes.new("prisma")
    n = len(perfil)
    vs = [(x, y, -esp / 2) for x, y in perfil] + [(x, y, esp / 2) for x, y in perfil]
    fs = [list(range(n))[::-1], list(range(n, 2 * n))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    me.from_pydata(vs, [], fs)
    me.update()
    o = bpy.data.objects.new("prisma", me)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    ativo(o)
    md = o.modifiers.new("b", "BEVEL")
    md.width = bisel
    md.segments = 3
    md.limit_method = "ANGLE"
    return o


def contorno(o, esp=0.035):
    """Contorno escuro de desenho animado (casca invertida)."""
    m = bpy.data.materials.get("contorno") or mat("contorno", "#0A1326", rug=1.0)
    m.use_backface_culling = True
    o.data.materials.append(m)
    md = o.modifiers.new("contorno", "SOLIDIFY")
    md.thickness = esp
    md.offset = 1
    md.use_flip_normals = True
    md.use_rim = False
    md.material_offset = len(o.data.materials) - 1
    return o


def render(arq):
    sc = bpy.context.scene
    sc.render.filepath = str(arq)
    bpy.ops.render.render(write_still=True)
    print("ok", arq, flush=True)


OURO = lambda: mat("ouro", "#F6B92B", metal=1.0, rug=0.28)          # noqa: E731
OURO2 = lambda: mat("ouro2", "#D88A12", metal=1.0, rug=0.35)        # noqa: E731
ACO = lambda: mat("aco", "#D3DCE8", metal=1.0, rug=0.22)            # noqa: E731


# ------------------------------------------------------------------ ícones
def moeda(loc=(0, 0, 0), rot=(math.radians(72), 0, math.radians(-18)), r=1.0):
    g = []
    o = cil(loc, r, 0.26 * r, OURO(), 64, rot, bisel=0.06 * r)
    g.append(o)
    # a coroa em relevo nas duas faces
    for lado in (1, -1):
        perfil = [(-0.42, -0.25), (0.42, -0.25), (0.48, 0.22), (0.24, 0.02), (0.0, 0.36), (-0.24, 0.02), (-0.48, 0.22)]
        p = prisma([(x * r, y * r) for x, y in perfil], 0.07 * r, OURO2(), bisel=0.02 * r)
        p.parent = o
        p.location = (0, 0, lado * 0.14 * r)
        p.rotation_euler = (0, 0, 0)
        a = anel((0, 0, 0), 0.8 * r, 0.035 * r, OURO2())
        a.parent = o
        a.location = (0, 0, lado * 0.13 * r)
        g += [p, a]
    return g


def icone_moeda():
    cena_nova(256)
    moeda()
    camera((0, 0, 0), 6.2, -10, 10, 50)
    render(UI / "moeda.png")


def icone_moedas():
    """Pilha de moedas (pacotes da loja)."""
    cena_nova(384)
    for k in range(5):
        cil((0.0, 0.0, -0.9 + 0.27 * k), 1.0, 0.24, OURO(), 64, bisel=0.05)
    for k in range(3):
        cil((1.6, 0.3, -0.9 + 0.27 * k), 1.0, 0.24, OURO(), 64, bisel=0.05)
    moeda((0.6, -1.4, -0.2), (math.radians(70), 0, math.radians(-25)))
    camera((0.6, 0, 0), 9.0, -18, 26, 50)
    render(UI / "moedas.png")


def icone_trofeu():
    cena_nova(256)
    copa = [(0.02, 2.55), (1.05, 2.55), (1.12, 2.45), (1.0, 1.75), (0.72, 1.2), (0.32, 0.92), (0.18, 0.62), (0.2, 0.3), (0.62, 0.18), (0.66, 0.0), (0.02, 0.0)]
    torno(copa, OURO())
    for lado in (1, -1):
        a = anel((lado * 1.05, 0, 1.85), 0.38, 0.09, OURO(), (math.pi / 2, 0, 0))
    caixa((0, 0, -0.25), (1.6, 1.0, 0.5), mat("madeira_esc", "#5A2E16", rug=0.6), 0.06)
    caixa((0, -0.51, -0.25), (0.9, 0.04, 0.22), OURO2(), 0.01)
    camera((0, 0, 1.2), 7.4, -14, 12, 50)
    render(UI / "trofeu.png")


def coroa_obj(c=(0, 0, 0), esc=1.0):
    g = []
    banda = torno([(1.0, 0.0), (1.05, 0.05), (1.05, 0.55), (1.0, 0.6)], OURO(), loc=c)
    g.append(banda)
    for k in range(5):
        a = 2 * math.pi * k / 5 - math.pi / 2
        x, y = c[0] + 0.98 * math.cos(a), c[1] + 0.98 * math.sin(a)
        g.append(cil((x, y, c[2] + 0.95), 0.26, 0.8, OURO(), 24, r2=0.04))
        g.append(esfera((x, y, c[2] + 1.38), 0.11, OURO()))
        g.append(esfera((1.06 * math.cos(a + 0.63) + c[0], 1.06 * math.sin(a + 0.63) + c[1], c[2] + 0.3), 0.12,
                        mat(f"gema{k}", ["#E5243B", "#2F7BFF", "#2FCB6A"][k % 3], rug=0.08)))
    g.append(cil((c[0], c[1], c[2] + 0.05), 0.98, 0.1, mat("veludo", "#B3122E", rug=0.9), 48))
    for o in g:
        o.scale = (esc, esc, esc)
        o.location = Vector(c) + (o.location - Vector(c)) * esc
    return g


def icone_coroa():
    cena_nova(256)
    coroa_obj()
    camera((0, 0, 0.6), 6.4, -12, 22, 50)
    render(UI / "coroa.png")


def espada(c, ang, m_lamina, m_guarda):
    raiz = bpy.data.objects.new("espada", None)
    bpy.context.scene.collection.objects.link(raiz)
    lam = prisma([(-0.17, 0.0), (0.17, 0.0), (0.17, 2.6), (0.0, 3.0), (-0.17, 2.6)], 0.08, m_lamina, bisel=0.025)
    gua = caixa((0, 0, -0.08), (1.05, 0.22, 0.2), m_guarda, 0.05)
    cabo = cil((0, 0, -0.55), 0.1, 0.75, mat("couro", "#6B3518", rug=0.7), 16)
    pomo = esfera((0, 0, -0.98), 0.16, m_guarda)
    for o in (lam, gua, cabo, pomo):
        o.parent = raiz
    raiz.location = c
    raiz.rotation_euler = (0, ang, 0)
    return raiz


def icone_espadas():
    cena_nova(256)
    espada((-0.2, 0, 0.0), math.radians(-38), ACO(), OURO())
    espada((0.2, 0.15, 0.0), math.radians(38), ACO(), OURO())
    camera((0, 0, 0.9), 7.6, 0, 6, 50)
    render(UI / "espadas.png")


def icone_engrenagem():
    cena_nova(256)
    pts = []
    n = 10
    for k in range(n * 4):
        a = 2 * math.pi * k / (n * 4)
        r = 1.0 if (k % 4) in (1, 2) else 0.8
        pts.append((r * math.cos(a), r * math.sin(a)))
    o = prisma(pts, 0.32, mat("ferro", "#B9C4D6", metal=1.0, rug=0.3), rot=(math.radians(70), 0, 0), bisel=0.04)
    cil((0, 0, 0), 0.32, 0.5, mat("buraco", "#2A3550", rug=0.6), 32, (math.radians(70), 0, 0))
    camera((0, 0, 0), 5.2, -10, 8, 50)
    render(UI / "engrenagem.png")


def icone_cartas():
    cena_nova(256)
    cores = ["#2F7BFF", "#F0A23C", "#A04BFF"]
    for k, (ang, cor) in enumerate(zip((-0.32, 0.0, 0.32), cores)):
        moldura = caixa((0, 0, 0), (1.4, 0.06, 1.85), mat(f"carta{k}", cor, rug=0.4), 0.06)
        face = caixa((0, -0.035, 0.12), (1.1, 0.02, 1.25), mat(f"face{k}", "#F4EEDC", rug=0.6), 0.02)
        g = bpy.data.objects.new("c", None)
        bpy.context.scene.collection.objects.link(g)
        moldura.parent = face.parent = g
        g.location = (math.sin(ang) * 1.6, 0.04 * k, -0.4 + math.cos(ang) * 1.0)
        g.rotation_euler = (0, ang, 0)
    camera((0, 0, 0.6), 6.4, 0, 6, 50)
    render(UI / "cartas.png")


def icone_saco():
    cena_nova(256)
    pano = mat("pano", "#A86B2D", rug=0.85)
    esfera((0, 0, 0.0), 1.0, pano, (1.0, 0.9, 0.95))
    cil((0, 0, 0.95), 0.42, 0.45, pano, 32, r2=0.6)
    anel((0, 0, 0.82), 0.44, 0.08, mat("corda", "#E8C27A", rug=0.8))
    moeda((0.0, -0.95, -0.05), (math.radians(90), 0, 0), 0.5)
    moeda((0.9, -0.6, -0.7), (math.radians(70), 0, math.radians(-30)), 0.42)
    camera((0, 0, 0.2), 6.2, -16, 16, 50)
    render(UI / "loja.png")


def icone_bandeira():
    cena_nova(256)
    cil((0, 0, 0.4), 0.08, 3.4, mat("mastro", "#6B3518", rug=0.6), 16)
    esfera((0, 0, 2.15), 0.16, OURO())
    pts = []
    for k in range(17):
        x = 1.9 * k / 16
        pts.append((x, 0.18 * math.sin(k * 0.7)))
    me = bpy.data.meshes.new("pano")
    vs, fs = [], []
    for k, (x, y) in enumerate(pts):
        vs += [(0.08 + x, y, 1.9 - 0.25 * x / 1.9), (0.08 + x, y, 0.8 + 0.25 * x / 1.9)]
    for k in range(len(pts) - 1):
        fs.append((2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1))
    me.from_pydata(vs, [], fs)
    o = bpy.data.objects.new("pano", me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat("bandeira", "#E5243B", rug=0.7))
    ativo(o)
    md = o.modifiers.new("e", "SOLIDIFY")
    md.thickness = 0.05
    suave(o)
    camera((0.8, 0, 1.2), 6.8, -20, 8, 50)
    render(UI / "trilha.png")


def icone_escudo(cor="#2F7BFF", nome="escudo"):
    cena_nova(256)
    perfil = [(-1.0, 1.0), (1.0, 1.0), (1.0, 0.1), (0.0, -1.2), (-1.0, 0.1)]
    prisma(perfil, 0.3, OURO(), bisel=0.08)
    dentro = [(x * 0.8, y * 0.8 + 0.02) for x, y in perfil]
    prisma(dentro, 0.36, mat("face_esc", cor, rug=0.35), bisel=0.05)
    camera((0, 0, 0), 5.4, -12, 8, 50)
    render(UI / f"{nome}.png")


def icone_estrela():
    cena_nova(256)
    pts = []
    for k in range(10):
        a = math.pi / 2 + 2 * math.pi * k / 10
        r = 1.0 if k % 2 == 0 else 0.45
        pts.append((r * math.cos(a), r * math.sin(a)))
    prisma(pts, 0.3, mat("estrela", "#FFD23A", metal=0.6, rug=0.25), bisel=0.08)
    camera((0, 0, 0), 5.0, -14, 8, 50)
    render(UI / "estrela.png")


def icone_relogio():
    cena_nova(256)
    cil((0, 0, 0), 1.0, 0.3, OURO(), 64, (math.pi / 2, 0, 0), bisel=0.05)
    cil((0, -0.12, 0), 0.82, 0.12, mat("mostrador", "#F7F3E6", rug=0.5), 64, (math.pi / 2, 0, 0))
    caixa((0, -0.2, 0.25), (0.08, 0.05, 0.55), mat("pont", "#1A2236", rug=0.5), 0.01)
    caixa((0.18, -0.2, 0.0), (0.42, 0.05, 0.08), mat("pont", "#1A2236", rug=0.5), 0.01)
    cil((0, 0, 1.15), 0.18, 0.3, OURO(), 24)
    camera((0, 0, 0.1), 5.2, -12, 8, 50)
    render(UI / "relogio.png")


# ------------------------------------------------------------------ os baús
BAUS = {
    "madeira": ("#9A5B2A", "#6B3A1A", "#9AA6B8", "#FFE7A0"),
    "prata": ("#8FA6C6", "#5E7398", "#E6EDF6", "#C8F0FF"),
    "ouro": ("#E8A92C", "#B7701A", "#FFE38A", "#FFF1A8"),
    "magico": ("#7B3FD6", "#4E1F9A", "#F6C84A", "#B6F3FF"),
}


def bau(tipo, aberto):
    cena_nova(512, 80)
    corpo_c, escuro_c, metal_c, luz_c = BAUS[tipo]
    corpo = mat("corpo", corpo_c, rug=0.55, metal=0.6 if tipo in ("prata", "ouro") else 0.0)
    escuro = mat("escuro", escuro_c, rug=0.6)
    metal = mat("metal", metal_c, metal=1.0, rug=0.3)
    L, P, A = 2.4, 1.6, 1.15
    # a caixa
    caixa((0, 0, A / 2), (L, P, A), corpo, 0.06)
    caixa((0, 0, A - 0.04), (L - 0.12, P - 0.12, 0.05), mat("vao", "#1B0E06" if not aberto else luz_c, rug=1.0,
                                                             emis=luz_c if aberto else None, forca=6.0 if aberto else 0.0), 0.01)
    for x in (-L / 2 + 0.22, L / 2 - 0.22):
        caixa((x, 0, A / 2), (0.22, P + 0.06, A + 0.04), metal, 0.03)
    caixa((0, 0, 0.1), (L + 0.06, P + 0.06, 0.18), escuro, 0.03)
    # a tampa (meio cilindro deitado no eixo X, gira na dobradiça de trás)
    dob = bpy.data.objects.new("dobradica", None)
    bpy.context.scene.collection.objects.link(dob)
    dob.location = (0, P / 2, A)

    def meio_cil(x0, x1, R, m, nome):
        bm = bmesh.new()
        n = 24
        aneis = []
        for x in (x0, x1):
            aneis.append([bm.verts.new((x, R * math.cos(math.pi * k / n) - P / 2, R * math.sin(math.pi * k / n))) for k in range(n + 1)])
        for k in range(n):
            bm.faces.new((aneis[0][k], aneis[1][k], aneis[1][k + 1], aneis[0][k + 1]))
        bm.faces.new(aneis[0][::-1])
        bm.faces.new(aneis[1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(nome)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(nome, me)
        bpy.context.scene.collection.objects.link(o)
        o.data.materials.append(m)
        o.parent = dob
        suave(o, 0.03)
        return o

    meio_cil(-L / 2, L / 2, P / 2, corpo, "tampa")
    for x in (-L / 2 + 0.22, L / 2 - 0.22):
        meio_cil(x - 0.11, x + 0.11, P / 2 + 0.05, metal, "faixa")
    # a fechadura
    fech = caixa((0, -P / 2 - 0.06, A - 0.05), (0.42, 0.12, 0.5), metal, 0.04)
    caixa((0, -P / 2 - 0.13, A - 0.1), (0.08, 0.02, 0.18), mat("buraco", "#1B0E06"), 0.005)
    if tipo == "magico":
        for k in range(6):
            a = 2 * math.pi * k / 6
            esfera((1.3 * math.cos(a), 1.0 * math.sin(a) - 0.2, 0.3 + 0.9 * (k % 3) / 2), 0.06, brilho(f"faisca{k}", "#B6F3FF", 8.0))
    if tipo == "ouro":
        for x in (-0.55, 0.55):
            esfera((x, -P / 2 - 0.02, A * 0.55), 0.09, mat("rubi", "#E5243B", rug=0.1))
    if aberto:
        dob.rotation_euler = (math.radians(-112), 0, 0)
        # luz saindo do baú
        for k in range(4):
            ang = math.radians(-27 + 18 * k)
            f = cil((0, 0, 0), 0.12, 3.2, halo(f"feixe{k}", luz_c, 1.6), 24, r2=0.42)
            f.location = (math.sin(ang) * 1.5, -0.1, A + 1.55)
            f.rotation_euler = (0, ang, 0)
        lp = bpy.data.lights.new("dentro", "POINT")
        lp.energy = 600
        lp.color = lin(luz_c)[:3]
        lo = bpy.data.objects.new("dentro", lp)
        lo.location = (0, 0, A + 0.5)
        bpy.context.scene.collection.objects.link(lo)
    camera((0, 0, 0.95 if not aberto else 1.5), 8.6 if not aberto else 10.2, -22, 24, 50)
    render(UI / f"bau_{tipo}{'_aberto' if aberto else ''}.png")


# ------------------------------------------------------------------ o logo
def degrade(nome, cima, baixo, z0, z1, metal=0.25, rug=0.32):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = z0
    mr.inputs["From Max"].default_value = z1
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = lin(baixo)
    cr.color_ramp.elements[1].color = lin(cima)
    nt.links.new(tc.outputs["Object"], sp.inputs[0])
    nt.links.new(sp.outputs["Y"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], cr.inputs[0])
    nt.links.new(cr.outputs[0], b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rug
    return m


def logo():
    cena_nova(1024, 64)
    sc = bpy.context.scene
    sc.render.resolution_y = 560
    f = bpy.data.fonts.load(FONTE)
    escuro = mat("contorno_logo", "#0A1326", rug=0.8)
    for txt, y, tam in (("ARENA DOS", 1.6, 1.0), ("REINOS", 0.0, 2.1)):
        for fundo in (True, False):
            bpy.ops.object.text_add(location=(0, 0.14 if fundo else 0, y))
            o = bpy.context.object
            o.data.body = txt
            o.data.font = f
            o.data.size = tam
            o.data.align_x = "CENTER"
            o.data.align_y = "CENTER"
            o.data.extrude = 0.1 if fundo else 0.14
            o.data.offset = 0.075 * tam if fundo else 0.0
            o.data.bevel_depth = 0.02 if fundo else 0.03
            o.data.bevel_resolution = 3
            o.rotation_euler = (math.pi / 2, 0, 0)
            o.data.materials.append(escuro if fundo else degrade("ouro_txt%d" % int(tam * 10), "#FFF07A", "#F08A12", -0.45 * tam, 0.45 * tam))
    espada((-1.25, 0.6, 0.35), math.radians(-58), ACO(), OURO())
    espada((1.25, 0.75, 0.35), math.radians(58), ACO(), OURO())
    camera((0, 0, 0.75), 16.0, 0, 4, 50)
    render(UI / "logo.png")


# ------------------------------------------------------------------ arte das cartas novas
def carta_relampago():
    cena_nova(384, 64)
    nuvem = mat("nuvem", "#7E8DB0", rug=0.9)
    for x, z, r in ((-0.9, 2.2, 0.75), (0.0, 2.45, 0.95), (0.9, 2.2, 0.7), (-0.4, 2.0, 0.6), (0.5, 1.95, 0.6)):
        esfera((x, 0.3, z), r, nuvem)
    raio = [(-0.15, 1.9), (0.42, 1.9), (0.08, 0.75), (0.5, 0.75), (-0.35, -1.6), (-0.02, 0.15), (-0.45, 0.15)]
    prisma(raio, 0.22, brilho("raio", "#FFF4A0", 9.0), bisel=0.03)
    esfera((0, 0.4, 0.4), 1.6, halo("halo_raio", "#FFE45A", 1.8))
    for k in range(6):
        a = 2 * math.pi * k / 6
        cil((0.9 * math.cos(a), -0.2, -1.55 + 0.25 * math.sin(a)), 0.05, 0.35, brilho(f"f{k}", "#FFF4A0", 8.0), 8, (0, a, 0))
    camera((0, 0, 0.45), 8.2, -8, 6, 50)
    render(CARTAS / "relampago.png")


def carta_gelo():
    cena_nova(384, 64)
    gelo = mat("gelo", "#A8E6FF", rug=0.08, emis="#7FD6FF", forca=0.35, transm=0.4)
    for k, (x, z, h, ang) in enumerate(((0, 0, 2.6, 0), (-0.75, -0.2, 1.9, 0.35), (0.8, -0.15, 2.0, -0.38), (-0.35, -0.3, 1.4, 0.75),
                                       (0.45, -0.35, 1.3, -0.8), (0.0, -0.4, 1.0, 0.1))):
        o = cil((0, 0, 0), 0.32, h, gelo, 6, r2=0.32)
        topo = cil((0, 0, h / 2 + 0.25), 0.32, 0.5, gelo, 6, r2=0.0)
        topo.parent = o
        o.location = (x, 0.1 * k, z + h / 2 - 0.9)
        o.rotation_euler = (0, ang, 0)
    esfera((0, 0.6, 0.3), 1.9, halo("halo_gelo", "#7FD6FF", 1.4))
    camera((0, 0, 0.35), 8.0, -10, 8, 50)
    render(CARTAS / "gelo.png")


def carta_cura():
    cena_nova(384, 64)
    vidro = mat("vidro", "#E8F6FF", rug=0.05, transm=0.9)
    torno([(0.02, 0.0), (0.9, 0.05), (1.15, 0.6), (1.1, 1.15), (0.7, 1.6), (0.32, 1.75), (0.3, 2.35), (0.42, 2.45)], vidro, loc=(0, 0, -1.1))
    liquido = mat("liquido", "#FF5FA2", rug=0.1, emis="#FF4F9A", forca=1.4)
    torno([(0.02, 0.06), (0.86, 0.1), (1.08, 0.6), (1.03, 1.08), (0.02, 1.08)], liquido, loc=(0, 0, -1.1))
    cil((0, 0, 1.5), 0.3, 0.45, mat("rolha", "#B07A45", rug=0.8), 24)
    coracao = mat("coracao", "#FF3B6B", rug=0.3, emis="#FF3B6B", forca=0.5)
    for x, z, s in ((-1.3, 1.2, 0.35), (1.35, 0.6, 0.3), (1.0, 1.8, 0.22)):
        esfera((x - 0.12 * s, -0.3, z), 0.2 * s / 0.35, coracao)
        esfera((x + 0.12 * s, -0.3, z), 0.2 * s / 0.35, coracao)
        cil((x, -0.3, z - 0.22 * s / 0.35), 0.28 * s / 0.35, 0.4 * s / 0.35, coracao, 24, (math.pi, 0, 0), r2=0.0)
    for k in range(10):
        a = 2 * math.pi * k / 10
        esfera((1.5 * math.cos(a), -0.4, 0.3 + 1.2 * math.sin(a)), 0.05, brilho(f"b{k}", "#9CFFB8", 9.0))
    esfera((0, 0.5, 0.2), 1.9, halo("halo_cura", "#6CFF9A", 1.2))
    camera((0, 0, 0.3), 8.0, -10, 8, 50)
    render(CARTAS / "cura.png")


def carta_exercito():
    cena_nova(384, 64)
    bpy.ops.import_scene.gltf(filepath=str(JOGO / "modelos" / "esqueleto.glb"))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    acao = bpy.data.actions.get("parado") or bpy.data.actions[0]
    rig.animation_data_create()
    rig.animation_data.action = acao
    bpy.context.scene.frame_set(8)
    raiz = rig
    copias = []
    lugares = [(0, 0), (-0.95, 0.7), (0.95, 0.7), (-1.9, 1.4), (1.9, 1.4), (-0.45, 1.6), (0.5, 1.7)]
    filhos = [o for o in bpy.data.objects if o.parent == rig]
    for k, (x, y) in enumerate(lugares):
        if k == 0:
            r = rig
        else:
            r = rig.copy()
            r.animation_data_create()
            r.animation_data.action = acao
            bpy.context.scene.collection.objects.link(r)
            for f in filhos:
                f2 = f.copy()
                bpy.context.scene.collection.objects.link(f2)
                f2.parent = r
                for md in f2.modifiers:
                    if md.type == "ARMATURE":
                        md.object = r
        r.location = (x, y, 0)
        r.rotation_euler = (0, 0, 0)
        copias.append(r)
    bpy.context.scene.frame_set(8)
    alt = 2.0
    camera((0, 0.9, 0.95), 6.6, 0, 12, 50)
    render(CARTAS / "exercito.png")


TUDO = {
    "moeda": icone_moeda, "moedas": icone_moedas, "trofeu": icone_trofeu, "coroa": icone_coroa, "espadas": icone_espadas,
    "engrenagem": icone_engrenagem, "cartas": icone_cartas, "loja": icone_saco, "trilha": icone_bandeira,
    "escudo": icone_escudo, "estrela": icone_estrela, "relogio": icone_relogio, "logo": logo,
    "relampago": carta_relampago, "gelo": carta_gelo, "cura": carta_cura, "exercito": carta_exercito,
}
for t in BAUS:
    TUDO[f"bau_{t}"] = (lambda t=t: bau(t, False))
    TUDO[f"bau_{t}_aberto"] = (lambda t=t: bau(t, True))

for nome, f in TUDO.items():
    if QUAIS and nome not in QUAIS:
        continue
    try:
        f()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("FALHOU", nome, e, flush=True)
