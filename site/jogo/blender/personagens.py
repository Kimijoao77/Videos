"""Os personagens do jogo (fantasia medieval, desenho arredondado). Cada função devolve um Modelo do kit.
Medidas "normalizadas": o personagem tem ~1 de altura e a escala do Modelo dá o tamanho final em casas."""
import math
import random

from kit import (TIME, TIME2, Modelo, caixa, capsula, cilindro, cone, esfera, prisma, rx, torno, tr, tubo)

PELE, PELE2 = "#F4C7A1", "#E0A47E"
ACO, ACO2 = "#C3CCD9", "#8E99AB"
OURO = "#F2B632"
COURO, COURO2 = "#8A5A36", "#5E3B22"
MADEIRA, MADEIRA2 = "#A8713F", "#7A4E2A"
PRETO = "#231F26"
BRANCO = "#F7F3EA"


def esqueleto(m, pele=PELE, alt_ombro=0.555, larg_ombro=0.25, perna="#3B3F52", bota=COURO2, braco=None, mao=None,
              r_braco=0.062, r_perna=0.075, r_cabeca=0.2, z_cabeca=0.80, pernas=True, comp_braco=0.25, z_pescoco=0.61,
              r_mao=0.072, giro_d=0, giro_e=0, sep_perna=0.1):
    """Peças articuladas básicas: corpo, cabeça, braços e pernas (sem o tronco, que cada personagem desenha).
    giro_d / giro_e: o braço já nasce girado para a frente (graus) em volta do ombro."""
    m.peca("perna_d", (-sep_perna, 0, 0.31))
    m.peca("perna_e", (sep_perna, 0, 0.31))
    m.peca("corpo", (0, 0, 0.30))
    m.peca("cabeca", (0, 0, z_pescoco), "corpo")
    m.peca("braco_d", (-larg_ombro, 0, alt_ombro), "corpo")
    m.peca("braco_e", (larg_ombro, 0, alt_ombro), "corpo")
    if pernas:
        for lado, p in ((-1, "perna_d"), (1, "perna_e")):
            m.add(p, tr(capsula(r_perna, 0.27), (sep_perna * lado, 0, 0.06)), perna)
            m.add(p, tr(esfera(1), (sep_perna * lado, -0.035, 0.062), esc=(r_perna * 1.17, r_perna * 1.8, 0.07)), bota, (0.75, 1.0))
    m.ombro, m.mao = {}, {}
    for lado, p, giro in ((-1, "braco_d", giro_d), (1, "braco_e", giro_e)):
        piv = (larg_ombro * lado, 0, alt_ombro)
        m.ombro[p] = (piv, -giro)
        m.add(p, rx(tr(capsula(r_braco, comp_braco), (larg_ombro * lado + 0.012 * lado, 0, alt_ombro - comp_braco + 0.03), rot=(0, -5 * lado, 0)), piv, -giro),
              braco or pele)
        pm = (larg_ombro * lado + 0.03 * lado, 0, alt_ombro - comp_braco + 0.01)
        m.add(p, rx(tr(esfera(r_mao), pm), piv, -giro), mao or pele, (0.85, 1.05))
        m.mao[p] = rx(([pm], []), piv, -giro)[0][0]
    m.add("cabeca", tr(esfera(r_cabeca, 20, 12), (0, 0, z_cabeca), esc=(1.05, 1.0, 0.96)), pele, (0.86, 1.05))
    m.alt = z_cabeca + r_cabeca + 0.05
    return m


def rosto(m, z=0.80, y=-0.185, olho=0.075, r=0.2, sobrancelha="#5B3A21", brava=0.0, nariz=True, pele2=PELE2):
    k = r / 0.2
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(1, 12, 8), (olho * lado * k, y * k + 0.004, z + 0.012 * k), esc=(0.03 * k, 0.018 * k, 0.042 * k)), PRETO, (1, 1))
        m.add("cabeca", tr(esfera(0.011 * k, 8, 6), ((olho * lado - 0.008) * k, y * k - 0.012, z + 0.03 * k)), BRANCO, (1, 1))
        if sobrancelha:
            m.add("cabeca", tr(caixa(0.075 * k, 0.022 * k, 0.02 * k, 0.008), (olho * lado * k, y * k - 0.006, z + 0.078 * k), rot=(0, (12 + brava) * lado, 0)),
                  sobrancelha, (1, 1))
    if nariz:
        m.add("cabeca", tr(esfera(0.034 * k, 10, 8), (0, y * k - 0.022, z - 0.035 * k)), pele2, (0.95, 1.05))


def cavaleiro():
    m = esqueleto(Modelo("cavaleiro", 1.7), braco=ACO2, mao=ACO, perna="#4A5166", bota=ACO2)
    rosto(m, brava=6)
    # tronco: saiote do time, cinto e peitoral de aço
    m.add("corpo", tr(torno([(0, 0.26), (0.19, 0.255), (0.228, 0.30), (0.222, 0.44), (0, 0.44)], 18), esc=(1, 0.84, 1)), TIME)
    m.add("corpo", tr(torno([(0, 0.42), (0.218, 0.43), (0.226, 0.50), (0.2, 0.575), (0.13, 0.625), (0, 0.64)], 18), esc=(1, 0.84, 1)), ACO, (0.78, 1.08))
    m.add("corpo", tr(cilindro(0.232, 0.232, 0.045, 18, 0.01), (0, 0, 0.405), esc=(1, 0.84, 1)), COURO2, (1, 1))
    m.add("corpo", tr(caixa(0.07, 0.03, 0.06, 0.012), (0, -0.196, 0.428)), OURO, (0.9, 1.05))
    m.add("corpo", tr(prisma([(0, 0.6), (0.05, 0.54), (0, 0.47), (-0.05, 0.54)], 0.02, 0.006), (0, -0.172, 0), rot=(-8, 0, 0)), TIME, (1, 1))
    # ombreiras
    for lado, p in ((-1, "braco_d"), (1, "braco_e")):
        m.add(p, tr(esfera(1, 14, 8), (0.262 * lado, 0, 0.578), esc=(0.1, 0.105, 0.075)), ACO, (0.8, 1.08))
    # elmo com crista do time
    m.add("cabeca", torno([(0.214, 0.865), (0.216, 0.9), (0.19, 0.97), (0.12, 1.015), (0, 1.03)], 20), ACO, (0.82, 1.1))
    m.add("cabeca", tr(cilindro(0.232, 0.232, 0.04, 20, 0.012), (0, 0, 0.85)), ACO2, (1, 1))
    m.add("cabeca", tr(caixa(0.04, 0.03, 0.12, 0.01), (0, -0.218, 0.83)), ACO2, (0.9, 1.05))
    crista = [(0, 0.25 * math.cos(math.radians(a)), 0.80 + 0.25 * math.sin(math.radians(a))) for a in range(125, 14, -10)]
    m.add("cabeca", tubo(crista, [0.02, 0.04, 0.05, 0.055, 0.055, 0.055, 0.05, 0.05, 0.045, 0.04, 0.03, 0.02][:len(crista)], 10), TIME, (0.85, 1.1))
    # bigode
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(1, 10, 6), (0.05 * lado, -0.2, 0.728), rot=(0, -18 * lado, 0), esc=(0.055, 0.03, 0.024)), "#7A4A22", (1, 1))
    # espada na mão direita
    px, py, pz = -0.285, -0.04, 0.31
    esp = lambda f, cor, g=(0.9, 1.08): m.add("braco_d", tr(f, (px, py, pz), rot=(38, 0, 6)), cor, g)  # noqa: E731
    esp(tr(cilindro(0.022, 0.022, 0.11, 10), (0, 0, -0.055)), COURO2)
    esp(tr(esfera(0.034, 10, 6), (0, 0, -0.07)), OURO)
    esp(tr(caixa(0.2, 0.045, 0.04, 0.014), (0, 0, 0.065)), OURO)
    esp(prisma([(-0.045, 0.08), (0.045, 0.08), (0.045, 0.56), (0, 0.66), (-0.045, 0.56)], 0.024, 0.008), "#DDE5EE", (0.8, 1.1))
    # escudo no braço esquerdo
    ex, ey, ez = 0.315, -0.1, 0.42
    forma = [(-0.15, 0.17), (0.15, 0.17), (0.15, -0.02), (0.1, -0.13), (0, -0.21), (-0.1, -0.13), (-0.15, -0.02)]
    m.add("braco_e", tr(prisma([(x * 1.1, z * 1.08) for x, z in forma], 0.035, 0.01), (ex, ey + 0.012, ez), rot=(0, 0, -18)), ACO2, (0.85, 1.05))
    m.add("braco_e", tr(prisma(forma, 0.04, 0.012), (ex, ey - 0.008, ez), rot=(0, 0, -18)), TIME, (0.8, 1.1))
    m.add("braco_e", tr(esfera(0.045, 12, 8), (ex - 0.012, ey - 0.03, ez + 0.02), esc=(1, 0.6, 1)), OURO, (0.9, 1.05))
    return m


def arqueiro():
    m = esqueleto(Modelo("arqueiro", 1.45), braco="#9A6B43", perna="#5A4632", giro_e=82, giro_d=30, r_perna=0.068)
    rosto(m, sobrancelha="#B5642A")
    m.add("corpo", tr(torno([(0, 0.27), (0.17, 0.275), (0.2, 0.33), (0.188, 0.46), (0.165, 0.57), (0.1, 0.625), (0, 0.64)], 18), esc=(1, 0.82, 1)), "#9A6B43")
    m.add("corpo", tr(cilindro(0.2, 0.2, 0.04, 18, 0.01), (0, 0, 0.40), esc=(1, 0.82, 1)), COURO2, (1, 1))
    # capa curta nas costas e aljava
    m.add("corpo", tr(prisma([(-0.16, 0.62), (0.16, 0.62), (0.21, 0.3), (0.07, 0.25), (0, 0.3), (-0.07, 0.25), (-0.21, 0.3)], 0.03, 0.01), (0, 0.185, 0), rot=(10, 0, 0)), TIME2, (0.8, 1.1))
    m.add("corpo", tr(cilindro(0.055, 0.06, 0.3, 12, 0.01), (-0.07, 0.24, 0.38), rot=(0, 18, 0)), COURO2)
    for k in range(3):
        m.add("corpo", tr(cilindro(0.01, 0.01, 0.1, 6), (-0.16 + 0.03 * k, 0.24 + 0.02 * (k % 2), 0.66), rot=(0, 18, 0)), MADEIRA2, (1, 1))
        m.add("corpo", tr(esfera(1, 8, 5), (-0.19 + 0.03 * k, 0.24 + 0.02 * (k % 2), 0.765), rot=(0, 18, 0), esc=(0.02, 0.008, 0.035)), BRANCO, (1, 1))
    # capuz do time com ponta
    m.add("cabeca", tr(esfera(0.232, 20, 12), (0, 0.05, 0.825), esc=(1.02, 1, 1)), TIME, (0.78, 1.08))
    m.add("cabeca", tr(cone(0.1, 0.24, 12), (0, 0.13, 0.97), rot=(-62, 0, 0)), TIME, (0.9, 1.1))
    m.add("cabeca", tr(esfera(1, 12, 8), (0, -0.165, 0.915), esc=(0.13, 0.05, 0.05)), "#D97B2B", (1, 1))        # franja
    # arco na mão esquerda (o braço já está estendido para a frente)
    hx, hy, hz = m.mao["braco_e"]
    r = 0.34
    pts = [(hx, hy + r - 0.01 + r * math.cos(math.radians(a)), hz + r * math.sin(math.radians(a))) for a in range(118, 243, 12)]
    m.add("braco_e", tubo(pts, [0.012, 0.02, 0.024, 0.026, 0.028, 0.03, 0.028, 0.026, 0.024, 0.02, 0.012][:len(pts)], 8), MADEIRA, (0.85, 1.1))
    m.add("braco_e", tubo([pts[0], pts[-1]], 0.006, 6), BRANCO, (1, 1))
    m.add("braco_e", tr(cilindro(0.034, 0.034, 0.09, 8, 0.008), (hx, hy - 0.01, hz - 0.045)), COURO2, (1, 1))
    return m


def gigante():
    m = esqueleto(Modelo("gigante", 2.7), larg_ombro=0.345, alt_ombro=0.6, r_braco=0.092, comp_braco=0.31, r_perna=0.105,
                  r_cabeca=0.165, z_cabeca=0.82, z_pescoco=0.67, r_mao=0.115, perna="#6B4A32", bota=COURO2, sep_perna=0.14)
    rosto(m, z=0.835, olho=0.075, r=0.165, sobrancelha="#6B3F1D", brava=10)
    m.add("corpo", tr(torno([(0, 0.24), (0.25, 0.25), (0.325, 0.34), (0.33, 0.46), (0.295, 0.58), (0.19, 0.665), (0, 0.69)], 20), esc=(1, 0.86, 1)), TIME, (0.72, 1.08))
    m.add("corpo", tr(cilindro(0.338, 0.338, 0.06, 20, 0.012), (0, 0, 0.345), esc=(1, 0.86, 1)), COURO2, (1, 1))
    m.add("corpo", tr(caixa(0.11, 0.035, 0.085, 0.015), (0, -0.287, 0.375)), OURO, (0.9, 1.05))
    for lado in (-1, 1):                              # alças de couro cruzando o peito
        m.add("corpo", tr(caixa(0.06, 0.03, 0.34, 0.012), (0.1 * lado, -0.245, 0.55), rot=(-14, 28 * lado, 0)), COURO, (0.9, 1.05))
        m.add("cabeca", tr(esfera(0.045, 10, 8), (0.168 * lado, 0, 0.82)), PELE2, (0.95, 1.05))            # orelhas
    # barba cheia e bigode
    m.add("cabeca", tr(esfera(1, 16, 10), (0, -0.085, 0.735), esc=(0.165, 0.12, 0.13)), "#7A4A22", (0.8, 1.05))
    m.add("cabeca", tr(esfera(1, 12, 8), (0, -0.12, 0.66), esc=(0.1, 0.08, 0.09)), "#7A4A22", (0.8, 1.0))
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(1, 10, 6), (0.05 * lado, -0.165, 0.775), rot=(0, -20 * lado, 0), esc=(0.06, 0.035, 0.028)), "#8A5628", (1, 1))
    # braceletes
    for lado, p in ((-1, "braco_d"), (1, "braco_e")):
        m.add(p, tr(cilindro(0.1, 0.1, 0.07, 14, 0.01), (0.37 * lado, 0, 0.345)), COURO2, (1, 1))
    m.alt = 1.02
    return m


def mago():
    m = esqueleto(Modelo("mago", 1.6), braco=TIME2, pernas=False, giro_d=38, r_braco=0.07)
    rosto(m, sobrancelha=BRANCO)
    m.add("corpo", tr(torno([(0, 0.02), (0.27, 0.02), (0.285, 0.06), (0.21, 0.4), (0.19, 0.56), (0.115, 0.63), (0, 0.645)], 20), esc=(1, 0.88, 1)), TIME, (0.68, 1.1))
    m.add("corpo", tr(cilindro(0.29, 0.29, 0.04, 20, 0.012), (0, 0, 0.02), esc=(1, 0.88, 1)), OURO, (1, 1))
    m.add("corpo", tr(cilindro(0.215, 0.215, 0.04, 20, 0.012), (0, 0, 0.385), esc=(1, 0.88, 1)), OURO, (1, 1))
    # chapéu pontudo com aba
    m.add("cabeca", torno([(0, 0.925), (0.34, 0.92), (0.35, 0.94), (0.21, 0.975), (0, 0.975)], 22), TIME2, (0.9, 1.1))
    m.add("cabeca", torno([(0.205, 0.96), (0.16, 1.1), (0.085, 1.24), (0, 1.3)], 18), TIME2, (0.85, 1.15))
    m.add("cabeca", tr(cone(0.075, 0.2, 10), (0, 0.02, 1.25), rot=(-55, 0, 0)), TIME2, (1, 1.1))
    m.add("cabeca", tr(cilindro(0.212, 0.2, 0.05, 18, 0.01), (0, 0, 0.965)), OURO, (1, 1))
    # barba e bigode brancos
    m.add("cabeca", tr(torno([(0, 0.46), (0.05, 0.52), (0.12, 0.66), (0.15, 0.74), (0.12, 0.775), (0, 0.78)], 14), (0, -0.115, 0), esc=(1, 0.6, 1)), BRANCO, (0.85, 1.05))
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(1, 10, 6), (0.055 * lado, -0.2, 0.735), rot=(0, -22 * lado, 0), esc=(0.07, 0.035, 0.028)), BRANCO, (1, 1))
    # cajado com a pedra mágica
    hx, hy, hz = m.mao["braco_d"]
    m.add("braco_d", tubo([(hx, hy - 0.03, 0.03), (hx, hy - 0.03, 0.6), (hx + 0.01, hy - 0.03, 0.98)], [0.02, 0.024, 0.026], 8), MADEIRA2, (0.85, 1.1))
    for a in range(0, 360, 120):
        m.add("braco_d", tr(cone(0.022, 0.12, 6), (hx + 0.01 + 0.05 * math.cos(math.radians(a)), hy - 0.03 + 0.05 * math.sin(math.radians(a)), 0.97),
                            rot=(18 * math.sin(math.radians(a)), -18 * math.cos(math.radians(a)), 0)), OURO, (1, 1))
    m.add("braco_d", tr(esfera(0.065, 14, 10), (hx + 0.01, hy - 0.03, 1.07)), "#59E8FF", (1.0, 1.25))
    m.alt = 1.3
    return m


def campones():
    m = esqueleto(Modelo("campones", 1.25), braco=TIME, perna="#6B5B4B", giro_d=28)
    rosto(m, sobrancelha="#8A5628", pele2="#E58B6B")
    m.add("corpo", tr(torno([(0, 0.27), (0.18, 0.275), (0.212, 0.34), (0.205, 0.46), (0.178, 0.57), (0.11, 0.625), (0, 0.64)], 18), esc=(1, 0.84, 1)), TIME, (0.75, 1.08))
    m.add("corpo", tr(torno([(0, 0.265), (0.19, 0.265), (0.22, 0.33), (0.215, 0.43), (0, 0.43)], 18), esc=(1, 0.86, 1)), "#6B5B4B", (0.85, 1.05))
    for lado in (-1, 1):                              # suspensórios
        m.add("corpo", tr(caixa(0.04, 0.02, 0.22, 0.008), (0.085 * lado, -0.158, 0.52), rot=(-10, 0, 0)), "#6B5B4B", (1, 1))
    # chapéu de palha
    m.add("cabeca", torno([(0, 0.915), (0.33, 0.9), (0.345, 0.915), (0.2, 0.955), (0, 0.955)], 20), "#E8C768", (0.85, 1.05))
    m.add("cabeca", torno([(0.2, 0.94), (0.19, 1.02), (0.13, 1.07), (0, 1.085)], 18), "#E8C768", (0.9, 1.08))
    m.add("cabeca", tr(cilindro(0.204, 0.2, 0.04, 18, 0.008), (0, 0, 0.95)), TIME2, (1, 1))
    # forcado
    hx, hy, hz = m.mao["braco_d"]
    m.add("braco_d", tubo([(hx, hy - 0.02, 0.08), (hx, hy - 0.02, 0.86)], 0.02, 8), MADEIRA, (0.85, 1.1))
    m.add("braco_d", tr(caixa(0.2, 0.03, 0.03, 0.008), (hx, hy - 0.02, 0.86)), ACO2, (1, 1))
    for k in (-1, 0, 1):
        m.add("braco_d", tr(cone(0.016, 0.2, 6), (hx + 0.085 * k, hy - 0.02, 0.865)), ACO, (0.9, 1.1))
    m.alt = 1.1
    return m


def dragao():
    """Dragão de faces retas (low-poly), no estilo dos personagens do pacote: pescoço, focinho, chifres, placas nas
    costas, quatro patas com garras, asas de morcego com dedos e cauda com ponta de flecha."""
    m = Modelo("dragao", 1.0)
    V, V2, CREME, OSSO = "#4FA65B", "#3B8A4E", "#F0DFA8", "#F3EAD2"
    F = dict(liso=False)
    m.peca("corpo", (0, 0, 0.55))
    m.peca("cabeca", (0, -0.6, 1.02), "corpo")
    m.peca("asa_d", (-0.2, 0.0, 0.82), "corpo")
    m.peca("asa_e", (0.2, 0.0, 0.82), "corpo")
    m.peca("cauda", (0, 0.42, 0.55), "corpo")

    def placa(peca, y, z, tam, inc=0):                 # placa triangular nas costas (fina em x)
        m.add(peca, tr(prisma([(-0.5 * tam, 0), (0.5 * tam, 0), (0.22 * tam, 1.05 * tam)], 0.035, 0.008), (0, y, z), rot=(inc, 0, 90)), TIME, (0.85, 1.15), **F)

    # tronco, peito e barriga clara
    m.add("corpo", tr(esfera(1, 10, 6), (0, 0.02, 0.56), esc=(0.31, 0.5, 0.3)), V, (0.72, 1.08), **F)
    m.add("corpo", tr(esfera(1, 10, 6), (0, -0.24, 0.6), esc=(0.29, 0.3, 0.3)), V, (0.75, 1.08), **F)
    m.add("corpo", tr(esfera(1, 10, 6), (0, -0.08, 0.47), esc=(0.25, 0.46, 0.24)), CREME, (0.82, 1.05), **F)
    # pescoço (com a faixa clara na frente)
    m.add("corpo", tubo([(0, -0.36, 0.7), (0, -0.52, 0.88), (0, -0.6, 1.04)], [0.19, 0.15, 0.135], 8), V, (0.8, 1.06), **F)
    m.add("corpo", tubo([(0, -0.43, 0.63), (0, -0.585, 0.83), (0, -0.665, 1.0)], [0.14, 0.11, 0.095], 8), CREME, (0.85, 1.05), **F)
    for (y, z, t, inc) in ((-0.42, 0.9, 0.13, -30), (-0.2, 0.86, 0.17, 0), (0.02, 0.86, 0.19, 0), (0.24, 0.82, 0.17, 12), (0.42, 0.74, 0.13, 25)):
        placa("corpo", y, z, t, inc)
    # patas com garras (penduradas, porque ele voa)
    for lado in (-1, 1):
        for (y, z, g) in ((-0.26, 0.36, 0.9), (0.24, 0.38, 1.12)):
            m.add("corpo", tr(esfera(1, 8, 5), (0.21 * lado, y, z), esc=(0.105 * g, 0.13 * g, 0.16 * g)), V2, (0.78, 1.05), **F)
            m.add("corpo", tr(esfera(1, 8, 5), (0.22 * lado, y - 0.07 * g, z - 0.17 * g), esc=(0.085 * g, 0.12 * g, 0.06 * g)), V2, (0.8, 1.05), **F)
            for k in (-1, 0, 1):
                m.add("corpo", tr(cone(0.022 * g, 0.09 * g, 5), ((0.22 + 0.05 * k) * lado, y - 0.17 * g, z - 0.19 * g), rot=(115, 0, 0)), OSSO, (1, 1), **F)

    # cabeça: crânio, focinho comprido, mandíbula, olhos bravos, chifres
    m.add("cabeca", tr(caixa(0.36, 0.36, 0.3, 0.08, 1), (0, -0.7, 1.14)), V, (0.82, 1.08), **F)
    m.add("cabeca", tr(caixa(0.27, 0.36, 0.17, 0.05, 1), (0, -0.98, 1.1), rot=(-4, 0, 0)), V, (0.85, 1.08), **F)
    m.add("cabeca", tr(caixa(0.23, 0.34, 0.07, 0.025, 1), (0, -0.95, 0.975), rot=(9, 0, 0)), CREME, (0.9, 1.05), **F)
    m.add("cabeca", tr(caixa(0.3, 0.2, 0.1, 0.03, 1), (0, -0.7, 0.99)), CREME, (0.9, 1.05), **F)
    for lado in (-1, 1):
        m.add("cabeca", tr(esfera(0.026, 6, 4), (0.075 * lado, -1.15, 1.17)), PRETO, (1, 1), **F)                      # narinas
        m.add("cabeca", tr(caixa(0.09, 0.1, 0.06, 0.02, 1), (0.075 * lado, -1.1, 1.185)), V2, (1, 1), **F)
        m.add("cabeca", tr(esfera(1, 8, 6), (0.17 * lado, -0.79, 1.19), esc=(0.045, 0.075, 0.07)), "#FFE27A", (1.0, 1.1))  # olho amarelo
        m.add("cabeca", tr(esfera(1, 6, 5), (0.2 * lado, -0.8, 1.19), esc=(0.025, 0.025, 0.06)), PRETO, (1, 1))          # pupila em fenda
        m.add("cabeca", tr(caixa(0.07, 0.24, 0.06, 0.02, 1), (0.175 * lado, -0.78, 1.275), rot=(-16, 0, 0)), V2, (1, 1), **F)   # sobrancelha brava
        m.add("cabeca", tr(cone(0.065, 0.34, 6), (0.12 * lado, -0.6, 1.26), rot=(-58, 0, -14 * lado)), OSSO, (0.85, 1.05), **F)  # chifre
        m.add("cabeca", tr(cone(0.04, 0.17, 5), (0.185 * lado, -0.6, 1.1), rot=(-80, 0, -40 * lado)), OSSO, (0.9, 1.05), **F)   # espinho da bochecha
        for y in (-1.1, -1.0, -0.9):                                                                                    # dentes
            m.add("cabeca", tr(cone(0.02, 0.06, 4), (0.115 * lado, y, 1.025), rot=(180, 0, 0)), BRANCO, (1, 1), **F)
    placa("cabeca", -0.64, 1.27, 0.12, -20)

    # asas: braço, três dedos e a membrana do time entre eles
    def asa(lado):
        P = lambda x, y, z: (x * lado, y, z)                                 # noqa: E731
        ombro, pulso = P(0.2, 0.0, 0.82), P(0.62, -0.14, 1.16)
        d1, d2, d3, tras = P(1.28, -0.22, 1.1), P(1.16, 0.3, 0.94), P(0.82, 0.56, 0.78), P(0.22, 0.4, 0.7)
        meio = lambda a, b, q=0.24: tuple((a[i] + b[i]) / 2 * (1 - q) + pulso[i] * q for i in range(3))     # noqa: E731
        borda = [d1, meio(d1, d2), d2, meio(d2, d3), d3, meio(d3, tras, 0.12), tras]
        vs = [pulso, ombro] + borda
        fs = [(0, k + 2, k + 3) for k in range(len(borda) - 1)] + [(1, 0, len(vs) - 1)]
        baixo = [(x, y, z - 0.02) for x, y, z in vs]
        n = len(vs)
        faces = fs + [tuple(reversed([i + n for i in f])) for f in fs]
        forma = (vs + baixo, faces if lado > 0 else [tuple(reversed(f)) for f in faces])
        peca = "asa_e" if lado > 0 else "asa_d"
        m.add(peca, forma, TIME, (0.7, 1.12), **F)
        m.add(peca, tubo([ombro, pulso], [0.06, 0.045], 6), V2, (1, 1), **F)
        for d in (d1, d2, d3):
            m.add(peca, tubo([pulso, d], [0.04, 0.015], 5), V2, (1, 1), **F)
        m.add(peca, tr(cone(0.035, 0.13, 5), pulso, rot=(-30, 0, -25 * lado)), OSSO, (1, 1), **F)             # garra do pulso
    asa(1)
    asa(-1)

    # cauda com placas e ponta de flecha
    m.add("cauda", tubo([(0, 0.38, 0.55), (0, 0.7, 0.5), (0, 0.98, 0.56), (0, 1.2, 0.7)], [0.21, 0.145, 0.09, 0.05], 8), V, (0.8, 1.06), **F)
    placa("cauda", 0.62, 0.64, 0.12, 14)
    placa("cauda", 0.84, 0.62, 0.1, -8)
    m.add("cauda", tr(prisma([(-0.16, 0), (0, 0.1), (0.16, 0), (0, -0.26)], 0.04, 0.01), (0, 1.3, 0.76), rot=(-58, 0, 90)), TIME, (0.9, 1.15), **F)
    m.alt = 1.45
    return m


def balista():
    m = Modelo("balista", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.peca("topo", (0, 0, 0.62), "corpo")
    m.add("corpo", tr(caixa(0.86, 1.05, 0.16, 0.04), (0, 0, 0.26)), MADEIRA, (0.85, 1.05))
    for sx in (-1, 1):
        m.add("corpo", tr(caixa(0.06, 0.62, 0.3, 0.02), (0.47 * sx, 0, 0.42)), TIME, (0.8, 1.1))
        for sy in (-1, 1):
            m.add("corpo", tr(cilindro(0.2, 0.2, 0.1, 14, 0.02), (0.45 * sx, 0.36 * sy, 0.2), rot=(0, 90, 0)), MADEIRA2, (0.8, 1.05))
            m.add("corpo", tr(cilindro(0.06, 0.06, 0.13, 8, 0.01), (0.45 * sx, 0.36 * sy, 0.2), rot=(0, 90, 0)), ACO2, (1, 1))
    m.add("corpo", tr(cilindro(0.13, 0.1, 0.3, 12, 0.02), (0, 0, 0.33)), MADEIRA2, (0.9, 1.05))
    m.add("topo", tr(caixa(0.17, 1.25, 0.15, 0.03), (0, 0.02, 0.7)), MADEIRA, (0.9, 1.08))
    pts = [(0.86 * math.cos(math.radians(a)), 0.2 + 0.86 * math.sin(math.radians(a)), 0.74) for a in range(215, 326, 10)]
    m.add("topo", tubo(pts, [0.03, 0.04, 0.05, 0.055, 0.06, 0.065, 0.065, 0.06, 0.055, 0.05, 0.04, 0.03][:len(pts)], 8), MADEIRA2, (1, 1))
    m.add("topo", tubo([pts[0], (0, 0.3, 0.76), pts[-1]], 0.012, 6), BRANCO, (1, 1))
    m.add("topo", tr(cilindro(0.03, 0.03, 0.95, 8), (0, 0.32, 0.8), rot=(90, 0, 0)), MADEIRA2, (1, 1))
    m.add("topo", tr(cone(0.065, 0.2, 8), (0, -0.62, 0.8), rot=(90, 0, 0)), ACO, (1, 1))
    m.alt = 1.0
    return m


PEDRA, PEDRA2, PEDRA3 = "#CFC8BA", "#A9A294", "#8B8578"


def torre():
    m = Modelo("torre", 0.86)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", torno([(0, 0), (1.5, 0), (1.55, 0.16), (1.33, 0.55), (1.22, 0.8), (1.17, 2.7), (1.38, 3.0), (1.44, 3.1), (1.44, 3.3), (0, 3.3)], 28), PEDRA, (0.7, 1.06))
    m.add("corpo", tr(cilindro(1.24, 1.22, 0.14, 28, 0.03), (0, 0, 1.6)), PEDRA2, (1, 1))
    random.seed(4)
    for k in range(16):                               # pedras soltas na parede
        a = random.uniform(0, 2 * math.pi)
        z = random.uniform(0.9, 2.5)
        m.add("corpo", tr(caixa(0.3, 0.1, 0.17, 0.03), (1.17 * math.sin(a), -1.17 * math.cos(a), z), rot=(0, 0, math.degrees(a))), PEDRA2, (1, 1))
    for k in range(8):                                # ameias
        a = 2 * math.pi * (k + 0.5) / 8
        m.add("corpo", tr(caixa(0.52, 0.3, 0.46, 0.06), (1.27 * math.sin(a), -1.27 * math.cos(a), 3.5), rot=(0, 0, math.degrees(a))), PEDRA, (0.85, 1.06))
    # telhado do time sobre quatro postes
    for k in range(4):
        a = 2 * math.pi * (k + 0.5) / 4
        m.add("corpo", tr(cilindro(0.075, 0.075, 0.95, 8), (0.86 * math.sin(a), -0.86 * math.cos(a), 3.3)), MADEIRA2, (1, 1))
    m.add("corpo", torno([(0, 4.15), (1.3, 4.15), (1.36, 4.25), (0.7, 4.85), (0.25, 5.35), (0, 5.5)], 24), TIME, (0.78, 1.12))
    m.add("corpo", tr(esfera(0.13, 12, 8), (0, 0, 5.55)), OURO, (1, 1))
    # porta, janela e a flâmula
    arco_p = [(-0.36, 0), (0.36, 0), (0.36, 0.62), (0.25, 0.86), (0, 0.97), (-0.25, 0.86), (-0.36, 0.62)]
    m.add("corpo", tr(prisma(arco_p, 0.12, 0.02), (0, -1.36, 0)), COURO2, (0.85, 1.05))
    m.add("corpo", tr(esfera(0.045, 8, 6), (0.2, -1.43, 0.45)), OURO, (1, 1))
    m.add("corpo", tr(caixa(0.16, 0.1, 0.42, 0.03), (0, -1.16, 2.25)), PRETO, (1, 1))
    for a in (90, -90, 180):
        r_ = math.radians(a)
        m.add("corpo", tr(caixa(0.16, 0.1, 0.42, 0.03), (1.16 * math.sin(r_), -1.16 * math.cos(r_), 2.0), rot=(0, 0, a)), PRETO, (1, 1))
    m.add("corpo", tr(prisma([(-0.3, 1.55), (0.3, 1.55), (0.3, 0.9), (0, 0.68), (-0.3, 0.9)], 0.05, 0.012), (0, -1.47, 1.45), rot=(-7, 0, 0)), TIME, (0.82, 1.1))
    m.add("corpo", tr(cilindro(0.04, 0.04, 0.72, 8), (-0.36, -1.5, 3.02), rot=(0, 90, 0)), OURO, (1, 1))
    m.add("corpo", tr(esfera(0.1, 10, 8), (0, -1.5, 2.62), esc=(1, 0.4, 1)), OURO, (1, 1))
    m.alt = 5.6
    return m


def castelo():
    m = Modelo("castelo", 0.86)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", tr(caixa(3.5, 3.5, 2.7, 0.22, 3), (0, 0, 1.35)), PEDRA, (0.7, 1.06))
    m.add("corpo", tr(caixa(3.8, 3.8, 0.34, 0.08), (0, 0, 2.8)), PEDRA2, (0.95, 1.05))
    for k in range(-2, 3):                            # ameias em volta
        for s in (-1, 1):
            if abs(k) < 2:
                m.add("corpo", tr(caixa(0.48, 0.3, 0.42, 0.06), (0.76 * k, 1.72 * s, 3.17)), PEDRA, (0.85, 1.06))
                m.add("corpo", tr(caixa(0.3, 0.48, 0.42, 0.06), (1.72 * s, 0.76 * k, 3.17)), PEDRA, (0.85, 1.06))
    for sx in (-1, 1):
        for sy in (-1, 1):                            # torrinhas dos cantos
            m.add("corpo", tr(torno([(0, 0), (0.72, 0), (0.75, 0.15), (0.64, 0.5), (0.62, 3.3), (0.74, 3.5), (0.74, 3.7), (0, 3.7)], 18), (1.72 * sx, 1.72 * sy, 0)), PEDRA, (0.72, 1.06))
            m.add("corpo", tr(torno([(0, 3.7), (0.8, 3.7), (0.84, 3.78), (0.36, 4.5), (0, 4.95)], 18), (1.72 * sx, 1.72 * sy, 0)), TIME, (0.78, 1.12))
            m.add("corpo", tr(esfera(0.09, 10, 8), (1.72 * sx, 1.72 * sy, 4.98)), OURO, (1, 1))
            m.add("corpo", tr(caixa(0.14, 0.1, 0.36, 0.03), (1.72 * sx, 1.72 * sy - 0.63, 2.3)), PRETO, (1, 1))
    # torre do meio, com telhado grande e a coroa
    m.add("corpo", torno([(0, 2.7), (1.12, 2.7), (1.1, 4.1), (1.28, 4.35), (1.28, 4.55), (0, 4.55)], 26), PEDRA, (0.8, 1.06))
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        m.add("corpo", tr(caixa(0.46, 0.26, 0.36, 0.05), (1.14 * math.sin(a), -1.14 * math.cos(a), 4.7), rot=(0, 0, math.degrees(a))), PEDRA, (0.9, 1.06))
    m.add("corpo", torno([(0, 4.55), (0.95, 4.55), (1.0, 4.65), (0.5, 5.45), (0.16, 6.1), (0, 6.25)], 24), TIME, (0.78, 1.12))
    m.add("corpo", tr(cilindro(0.3, 0.34, 0.2, 14, 0.03), (0, 0, 6.2)), OURO, (0.9, 1.08))
    for k in range(5):
        a = 2 * math.pi * k / 5
        m.add("corpo", tr(cone(0.09, 0.26, 6), (0.27 * math.sin(a), -0.27 * math.cos(a), 6.36)), OURO, (1, 1.1))
    m.add("corpo", tr(caixa(0.18, 0.1, 0.46, 0.03), (0, -1.1, 3.55)), PRETO, (1, 1))
    # portão, escudo dourado e flâmulas
    arco_p = [(-0.62, 0), (0.62, 0), (0.62, 1.0), (0.44, 1.38), (0, 1.56), (-0.44, 1.38), (-0.62, 1.0)]
    m.add("corpo", tr(prisma([(x * 1.16, z * 1.08) for x, z in arco_p], 0.1, 0.02), (0, -1.73, 0)), PEDRA3, (0.9, 1.05))
    m.add("corpo", tr(prisma(arco_p, 0.14, 0.02), (0, -1.76, 0)), COURO2, (0.8, 1.05))
    for x in (-0.3, 0.3):
        for z in (0.35, 0.85):
            m.add("corpo", tr(esfera(0.05, 8, 6), (x, -1.84, z)), OURO, (1, 1))
    m.add("corpo", tr(prisma([(-0.3, 0.3), (0.3, 0.3), (0.3, 0), (0, -0.3), (-0.3, 0)], 0.08, 0.02), (0, -1.8, 2.15)), OURO, (0.85, 1.1))
    for sx in (-1, 1):
        m.add("corpo", tr(prisma([(-0.26, 0.6), (0.26, 0.6), (0.26, -0.3), (0, -0.52), (-0.26, -0.3)], 0.05, 0.012), (1.02 * sx, -1.8, 1.75)), TIME, (0.82, 1.1))
    m.alt = 6.4
    return m


def ruina():
    m = Modelo("ruina", 0.86)
    m.peca("corpo", (0, 0, 0))
    random.seed(11)
    m.add("corpo", torno([(0, 0), (1.5, 0), (1.52, 0.14), (1.3, 0.5), (1.24, 0.62), (0, 0.62)], 24), PEDRA2, (0.7, 1.0))
    for k in range(5):                                # pedaços de parede em pé
        a = 2 * math.pi * k / 5 + 0.3
        h = random.uniform(0.5, 1.3)
        m.add("corpo", tr(caixa(0.7, 0.3, h, 0.07), (1.08 * math.sin(a), -1.08 * math.cos(a), 0.6 + h / 2), rot=(random.uniform(-8, 8), 0, math.degrees(a))), PEDRA, (0.75, 1.02))
    for k in range(14):                               # entulho
        a = random.uniform(0, 2 * math.pi)
        d = random.uniform(0.1, 1.9)
        s = random.uniform(0.22, 0.5)
        m.add("corpo", tr(caixa(s, s * random.uniform(0.7, 1.2), s * random.uniform(0.5, 0.9), 0.06),
                          (d * math.sin(a), -d * math.cos(a), (0.68 if d < 1.2 else 0.12) + s * 0.25),
                          rot=(random.uniform(-25, 25), random.uniform(-25, 25), random.uniform(0, 90))), random.choice([PEDRA, PEDRA2, PEDRA3]), (0.85, 1.05))
    m.alt = 2.0
    return m


def bola_fogo():
    """Meteoro de fogo: miolo branco-amarelo na frente e línguas de fogo compridas para trás (voa para -Y)."""
    m = Modelo("bola_fogo", 1.0)
    m.peca("corpo", (0, 0, 0.5))
    F = dict(liso=False)
    m.add("corpo", tr(esfera(0.3, 8, 5), (0, 0.04, 0.5)), "#FF7A1A", (1.0, 1.2), **F)
    m.add("corpo", tr(esfera(0.24, 8, 5), (0, -0.1, 0.5)), "#FFC83D", (1.1, 1.3), **F)
    m.add("corpo", tr(esfera(0.15, 8, 5), (0, -0.22, 0.5)), "#FFF6C8", (1.3, 1.4), **F)
    random.seed(5)
    for k in range(16):                               # línguas de fogo: em volta e para trás
        a = 2 * math.pi * k / 16 + random.uniform(-0.15, 0.15)
        r = random.uniform(0.14, 0.27)
        comp = random.uniform(0.45, 0.95)
        m.add("corpo", tr(cone(random.uniform(0.09, 0.15), comp, 5), (r * math.cos(a), 0.1, 0.5 + r * math.sin(a)),
                          rot=(-90 + 26 * math.sin(a) * (r / 0.27), 0, -26 * math.cos(a) * (r / 0.27))),
              ["#E8421A", "#FF7A1A", "#FFA52E"][k % 3], (1.0, 1.25), **F)
    m.add("corpo", tr(cone(0.2, 1.1, 6), (0, 0.15, 0.5), rot=(-90, 0, 0)), "#FFC83D", (1.1, 1.3), **F)
    m.alt = 1.0
    return m


# ------------------------------------------------------------------ cenário
def arvore():
    m = Modelo("arvore", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", tubo([(0, 0, 0), (0.03, 0, 0.7), (0, 0.02, 1.3)], [0.2, 0.14, 0.1], 10), MADEIRA2, (0.8, 1.05))
    for (x, y, z, r, c) in ((0, 0, 1.75, 0.8, "#4FA348"), (0.45, 0.1, 1.45, 0.52, "#3F8E3E"), (-0.42, -0.12, 1.5, 0.55, "#5DB552"), (0.05, -0.1, 2.3, 0.5, "#6CC25C")):
        m.add("corpo", tr(esfera(r, 14, 9), (x, y, z), esc=(1, 1, 0.85)), c, (0.72, 1.1))
    m.alt = 2.8
    return m


def pinheiro():
    m = Modelo("pinheiro", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", cilindro(0.14, 0.1, 0.6, 10), MADEIRA2, (0.8, 1.05))
    for k, (z, r, h) in enumerate(((0.45, 0.72, 0.95), (1.05, 0.56, 0.85), (1.6, 0.38, 0.8))):
        m.add("corpo", tr(torno([(0, 0), (r, 0), (r * 0.94, 0.08), (0, h)], 14), (0, 0, z)), ["#2F7A45", "#38894D", "#439A57"][k], (0.75, 1.12))
    m.alt = 2.5
    return m


def pedra():
    m = Modelo("pedra", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", tr(esfera(1, 10, 7), (0, 0, 0.22), rot=(8, 0, 20), esc=(0.5, 0.4, 0.32)), "#9AA0A6", (0.75, 1.08))
    m.add("corpo", tr(esfera(1, 9, 6), (0.38, 0.1, 0.13), rot=(0, 10, 50), esc=(0.26, 0.22, 0.18)), "#878D94", (0.75, 1.08))
    m.alt = 0.6
    return m


def arbusto():
    m = Modelo("arbusto", 1.0)
    m.peca("corpo", (0, 0, 0))
    for (x, y, z, r, c) in ((0, 0, 0.28, 0.38, "#4FA348"), (0.3, 0.05, 0.22, 0.28, "#3F8E3E"), (-0.28, -0.05, 0.22, 0.27, "#5DB552")):
        m.add("corpo", tr(esfera(r, 12, 8), (x, y, z), esc=(1, 1, 0.8)), c, (0.72, 1.1))
    m.alt = 0.7
    return m


def ponte():
    """Ponte de pedra sobre o rio: 2 casas de largura (x) e 2,6 de comprimento (y)."""
    m = Modelo("ponte", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", tr(caixa(2.1, 2.9, 0.34, 0.07), (0, 0, 0.0)), "#B9B1A2", (0.8, 1.05))
    for k in range(-3, 4):                            # tábuas
        m.add("corpo", tr(caixa(1.86, 0.34, 0.08, 0.02), (0, 0.39 * k, 0.17)), MADEIRA if k % 2 else "#B47C48", (0.92, 1.05))
    for sx in (-1, 1):
        m.add("corpo", tr(caixa(0.2, 2.9, 0.3, 0.06), (1.02 * sx, 0, 0.26)), PEDRA2, (0.85, 1.05))
        for sy in (-1, 1):
            m.add("corpo", tr(cilindro(0.17, 0.15, 0.62, 10, 0.04), (1.02 * sx, 1.36 * sy, 0.0)), PEDRA, (0.8, 1.06))
            m.add("corpo", tr(esfera(0.13, 10, 8), (1.02 * sx, 1.36 * sy, 0.68)), PEDRA3, (0.9, 1.05))
    m.alt = 0.8
    return m


def cerca():
    m = Modelo("cerca", 1.0)
    m.peca("corpo", (0, 0, 0))
    for x in (-0.5, 0.5):
        m.add("corpo", tr(cilindro(0.07, 0.06, 0.6, 8, 0.02), (x, 0, 0)), MADEIRA2, (0.8, 1.05))
    for z in (0.22, 0.45):
        m.add("corpo", tr(caixa(1.25, 0.05, 0.09, 0.02), (0, 0, z), rot=(0, 2 if z < 0.3 else -3, 0)), MADEIRA, (0.9, 1.05))
    m.alt = 0.6
    return m


def flecha():
    """Aponta para a frente (-Y do Blender = +Z do jogo)."""
    m = Modelo("flecha", 1.0)
    m.peca("corpo", (0, 0, 0))
    m.add("corpo", tr(cilindro(0.02, 0.02, 0.6, 6), (0, 0.3, 0), rot=(90, 0, 0)), MADEIRA2, (1, 1))
    m.add("corpo", tr(cone(0.05, 0.14, 6), (0, -0.3, 0), rot=(90, 0, 0)), ACO, (1, 1))
    for a in (0, 90):
        m.add("corpo", tr(caixa(0.012, 0.16, 0.1, 0.0), (0, 0.24, 0), rot=(0, a, 0)), BRANCO, (1, 1))
    m.alt = 0.3
    return m


# cavaleiro, besteiro, gigante, mago e bandido vêm do pacote KayKit (kaykit.py); os de cima ficam como reserva
TROPAS = ["dragao"]
# torres, castelo, catapulta, ruína e árvores vêm do pacote KayKit Medieval Hexagon (hexagono.py)
PREDIOS = []
OBJETOS = ["bola_fogo", "flecha", "ponte"]
