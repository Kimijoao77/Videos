"""Kit de modelagem por código (Blender/bpy) para os personagens do jogo: formas arredondadas de desenho animado
(torno, esfera, cápsula, caixa de cantos redondos, tubo, prisma), cada personagem dividido em peças articuladas
(corpo, cabeça, braços, pernas, arma...) com o pivô na junta, para o jogo animar girando as peças.

A cor vai nos vértices (um material só para tudo, poucas chamadas de desenho no celular), com um degradê de baixo
para cima em cada forma. A cor do time é uma cor "mágica" (magenta): o jogo troca por azul ou vermelho ao carregar.
Frente do personagem: -Y do Blender (vira +Z no glTF/Three.js). Unidade: 1 = 1 casa da arena."""
import math

import bpy
import bmesh  # noqa: E402  (só existe depois do bpy)
from mathutils import Matrix, Vector

TIME = "TIME"            # cor do time (clara)
TIME2 = "TIME2"          # cor do time (escura)
COR_TIME = None          # None = exporta a cor mágica; (r, g, b) em sRGB 0..1 = pinta de verdade (para as fotos)


def srgb_lin(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def cor_lin(c):
    """'#RRGGBB', TIME/TIME2 ou (r, g, b) sRGB → (r, g, b) linear."""
    if c in (TIME, TIME2):
        k = 1.0 if c == TIME else 0.55
        if COR_TIME is None:
            return (k, 0.0, k)                      # magenta mágico: o brilho (k) é o tom
        return tuple(srgb_lin(v) * (1.0 if c == TIME else 0.5) for v in COR_TIME)
    if isinstance(c, str):
        c = c.lstrip("#")
        c = tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(srgb_lin(v) for v in c)


# ------------------------------------------------------------------ formas (devolvem (vértices, faces))
def torno(perfil, seg=16):
    """Gira o perfil [(raio, z), ...] em volta do eixo Z. Raio 0 na ponta vira polo."""
    vs, fs, aneis = [], [], []
    for r, z in perfil:
        if r <= 1e-6:
            aneis.append([len(vs)])
            vs.append((0.0, 0.0, z))
        else:
            ini = len(vs)
            for k in range(seg):
                a = 2 * math.pi * k / seg
                vs.append((r * math.cos(a), r * math.sin(a), z))
            aneis.append(list(range(ini, ini + seg)))
    for a, b in zip(aneis, aneis[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for k in range(seg):
            k2 = (k + 1) % seg
            if len(a) == 1:
                fs.append((a[0], b[k2], b[k]))
            elif len(b) == 1:
                fs.append((a[k], a[k2], b[0]))
            else:
                fs.append((a[k], a[k2], b[k2], b[k]))
    # tampa as pontas abertas
    if len(aneis[0]) > 1:
        fs.append(tuple(reversed(aneis[0])))
    if len(aneis[-1]) > 1:
        fs.append(tuple(aneis[-1]))
    return vs, fs


def esfera(r=1.0, seg=16, an=10):
    return torno([(r * math.sin(math.pi * k / an), -r * math.cos(math.pi * k / an)) for k in range(an + 1)], seg)


def capsula(r, h, seg=14, an=5):
    """Cilindro de pontas redondas, em pé, de z=0 a z=h (h inclui as pontas)."""
    h = max(h, 2 * r + 1e-4)
    p = [(r * math.sin(math.pi / 2 * k / an), r - r * math.cos(math.pi / 2 * k / an)) for k in range(an + 1)]
    p += [(r * math.cos(math.pi / 2 * k / an), h - r + r * math.sin(math.pi / 2 * k / an)) for k in range(an + 1)]
    return torno(p, seg)


def cilindro(r1, r2, h, seg=16, borda=0.0):
    """Tronco de cone de z=0 a z=h; 'borda' arredonda as quinas."""
    b = min(borda, h / 3, r1 * 0.9 if r1 else borda, r2 * 0.9 if r2 else borda)
    if b > 0:
        p = [(0, 0), (r1 - b, 0), (r1, b), (r2, h - b), (r2 - b, h), (0, h)]
    else:
        p = [(0, 0), (r1, 0), (r2, h), (0, h)]
    return torno([q for q in p if not (q[0] <= 0 and q not in ((0, 0), (0, h)))], seg)


def cone(r, h, seg=14):
    return torno([(0, 0), (r, 0), (0, h)], seg)


def caixa(sx, sy, sz, bisel=0.0, seg=2):
    """Caixa centrada na origem, com as quinas arredondadas."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    b = min(bisel, sx * 0.49, sy * 0.49, sz * 0.49)
    if b > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=seg, profile=0.5, affect="EDGES")
    bm.verts.index_update()
    vs = [tuple(v.co) for v in bm.verts]
    fs = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return vs, fs


def prisma(contorno, esp, bisel=0.0):
    """Contorno 2D (x, z) no plano de frente, com espessura em Y (centrado)."""
    bm = bmesh.new()
    n = len(contorno)
    a = [bm.verts.new((x, -esp / 2, z)) for x, z in contorno]
    b = [bm.verts.new((x, esp / 2, z)) for x, z in contorno]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for k in range(n):
        k2 = (k + 1) % n
        bm.faces.new((a[k2], a[k], b[k], b[k2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bisel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bisel, esp * 0.45), segments=2, profile=0.5, affect="EDGES")
    bm.verts.index_update()
    vs = [tuple(v.co) for v in bm.verts]
    fs = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return vs, fs


def tubo(pontos, raios, seg=10):
    """Tubo que segue os pontos (x, y, z); raios: um número ou um por ponto. Pontas fechadas."""
    pts = [Vector(p) for p in pontos]
    if not isinstance(raios, (list, tuple)):
        raios = [raios] * len(pts)
    vs, fs, aneis = [], [], []
    ref = Vector((0, 0, 1))
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if abs(d.dot(ref)) > 0.95:
            ref = Vector((1, 0, 0))
        u = d.cross(ref).normalized()
        w = d.cross(u).normalized()
        ini = len(vs)
        for k in range(seg):
            a = 2 * math.pi * k / seg
            vs.append(tuple(p + (u * math.cos(a) + w * math.sin(a)) * raios[i]))
        aneis.append(list(range(ini, ini + seg)))
    for a, b in zip(aneis, aneis[1:]):
        for k in range(seg):
            k2 = (k + 1) % seg
            fs.append((a[k], a[k2], b[k2], b[k]))
    fs.append(tuple(reversed(aneis[0])))
    fs.append(tuple(aneis[-1]))
    return vs, fs


def arco(r, a0, a1, n=10, plano="xz"):
    """Pontos de um arco de círculo (graus), para usar com tubo()."""
    out = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        c, s = r * math.cos(a), r * math.sin(a)
        out.append({"xz": (c, 0, s), "xy": (c, s, 0), "yz": (0, c, s)}[plano])
    return out


def tr(forma, pos=(0, 0, 0), rot=(0, 0, 0), esc=(1, 1, 1)):
    """Escala, gira (graus, ordem X depois Y depois Z) e move uma forma."""
    vs, fs = forma
    if not isinstance(esc, (list, tuple)):
        esc = (esc, esc, esc)
    m = (Matrix.Translation(pos) @ Matrix.Rotation(math.radians(rot[2]), 4, "Z") @ Matrix.Rotation(math.radians(rot[1]), 4, "Y")
         @ Matrix.Rotation(math.radians(rot[0]), 4, "X") @ Matrix.Diagonal((*esc, 1)))
    out = [tuple(m @ Vector(v)) for v in vs]
    if esc[0] * esc[1] * esc[2] < 0:
        fs = [tuple(reversed(f)) for f in fs]
    return out, fs


def rx(forma, pivo, ang):
    """Gira a forma em volta do eixo X que passa pelo pivô (ang em graus; negativo = para a frente)."""
    vs, fs = forma
    m = Matrix.Translation(pivo) @ Matrix.Rotation(math.radians(ang), 4, "X") @ Matrix.Translation([-v for v in pivo])
    return [tuple(m @ Vector(v)) for v in vs], fs


def espelho(forma):
    """Espelha em X (o lado esquerdo vira o direito)."""
    vs, fs = forma
    return [(-x, y, z) for x, y, z in vs], [tuple(reversed(f)) for f in fs]


# ------------------------------------------------------------------ modelo = peças articuladas
class Modelo:
    def __init__(self, nome, escala=1.0):
        self.nome, self.e = nome, escala
        self.pecas = {}          # nome → dict(pivo, pai, bm)
        self.ordem = []

    def peca(self, nome, pivo=(0, 0, 0), pai=None):
        bm = bmesh.new()
        bm.loops.layers.float_color.new("Col")
        self.pecas[nome] = dict(pivo=Vector(pivo) * self.e, pai=pai, bm=bm)
        self.ordem.append(nome)
        return nome

    def add(self, peca, forma, cor, grad=(0.8, 1.06), liso=True):
        """Junta uma forma (em coordenadas do modelo, antes da escala) numa peça, com cor e degradê vertical."""
        p = self.pecas[peca]
        bm = p["bm"]
        lay = bm.loops.layers.float_color["Col"]
        vs, fs = forma
        c = cor_lin(cor)
        magica = cor in (TIME, TIME2) and COR_TIME is None
        zs = [v[2] for v in vs]
        z0, z1 = min(zs), max(zs)
        novos = [bm.verts.new(Vector(v) * self.e - p["pivo"]) for v in vs]
        for f in fs:
            try:
                face = bm.faces.new([novos[i] for i in f])
            except ValueError:
                continue
            face.smooth = liso
            for lp, i in zip(face.loops, f):
                t = (vs[i][2] - z0) / (z1 - z0) if z1 > z0 else 1.0
                g = grad[0] + (grad[1] - grad[0]) * t
                if magica:                           # o degradê entra no brilho do magenta
                    lp[lay] = (min(1.0, c[0] * g), 0.0, min(1.0, c[2] * g), 1.0)
                else:
                    lp[lay] = (min(1.0, c[0] * g), min(1.0, c[1] * g), min(1.0, c[2] * g), 1.0)

    def montar(self, colecao=None):
        """Cria os objetos do Blender (hierarquia de peças). Devolve o objeto raiz."""
        colecao = colecao or bpy.context.scene.collection
        raiz = bpy.data.objects.new(self.nome, None)
        colecao.objects.link(raiz)
        objs = {}
        for nome in self.ordem:
            p = self.pecas[nome]
            bm = p["bm"]
            if not bm.verts:                         # peça sem desenho (ex.: pernas escondidas): só o pivô
                bm.free()
                o = bpy.data.objects.new(nome, None)
                colecao.objects.link(o)
                pai = objs.get(p["pai"])
                o.parent = pai or raiz
                o.location = p["pivo"] - (self.pecas[p["pai"]]["pivo"] if pai else Vector((0, 0, 0)))
                objs[nome] = o
                continue
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            me = bpy.data.meshes.new(f"{self.nome}_{nome}")
            bm.to_mesh(me)
            bm.free()
            if hasattr(me, "set_sharp_from_angle"):
                me.set_sharp_from_angle(angle=math.radians(48))
            me.materials.append(material())
            o = bpy.data.objects.new(nome, me)
            colecao.objects.link(o)
            pai = objs.get(p["pai"])
            o.parent = pai or raiz
            o.location = p["pivo"] - (self.pecas[p["pai"]]["pivo"] if pai else Vector((0, 0, 0)))
            objs[nome] = o
        self.objs = objs
        return raiz


def material():
    m = bpy.data.materials.get("cor")
    if m:
        return m
    m = bpy.data.materials.new("cor")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    at = nt.nodes.new("ShaderNodeVertexColor")
    at.layer_name = "Col"
    nt.links.new(at.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.75
    return m


def limpar():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def exportar(arq):
    bpy.ops.export_scene.gltf(filepath=str(arq), export_format="GLB", export_apply=True, export_yup=True,
                              export_vertex_color="MATERIAL", export_materials="EXPORT", export_normals=True,
                              export_animations=False, export_cameras=False, export_lights=False)


# ------------------------------------------------------------------ fotos (conferência e arte das cartas)
def foto(arq, alvo=(0, 0, 0.8), dist=4.2, az=-28, el=18, larg=420, alt=520, fundo=None, amostras=28, lente=60, transparente=False):
    cena = bpy.context.scene
    cena.render.engine = "CYCLES"
    cena.cycles.device = "CPU"
    cena.cycles.samples = amostras
    cena.cycles.use_denoising = True
    cena.render.resolution_x, cena.render.resolution_y = larg, alt
    cena.render.film_transparent = transparente
    cena.view_settings.view_transform = "Standard"
    for o in list(bpy.data.objects):
        if o.name.startswith("_foto"):
            bpy.data.objects.remove(o)
    mundo = bpy.data.worlds.get("m") or bpy.data.worlds.new("m")
    cena.world = mundo
    mundo.use_nodes = True
    bg = mundo.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*(cor_lin(fundo) if fundo else (0.55, 0.62, 0.75)), 1)
    bg.inputs[1].default_value = 0.7
    sd = bpy.data.lights.new("_foto_sol", "SUN")
    sd.energy = 2.4
    sd.angle = math.radians(12)
    sol = bpy.data.objects.new("_foto_sol", sd)
    sol.rotation_euler = (math.radians(48), 0, math.radians(az - 35))
    cena.collection.objects.link(sol)
    if not transparente:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
        chao = bpy.context.object
        chao.name = "_foto_chao"
        mc = bpy.data.materials.new("_foto_chao")
        mc.use_nodes = True
        mc.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*(cor_lin(fundo) if fundo else (0.42, 0.5, 0.62)), 1)
        mc.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
        chao.data.materials.append(mc)
    cd = bpy.data.cameras.new("_foto_cam")
    cd.lens = lente
    cam = bpy.data.objects.new("_foto_cam", cd)
    a, e = math.radians(az), math.radians(el)
    alvo = Vector(alvo)
    cam.location = alvo + Vector((dist * math.sin(a) * math.cos(e), -dist * math.cos(a) * math.cos(e), dist * math.sin(e)))
    cam.rotation_euler = (alvo - cam.location).to_track_quat("-Z", "Y").to_euler()
    cena.collection.objects.link(cam)
    cena.camera = cam
    cena.render.filepath = str(arq)
    bpy.ops.render.render(write_still=True)
