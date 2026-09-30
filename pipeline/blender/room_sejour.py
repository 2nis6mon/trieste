"""
Séjour / salle à manger : placard type PAX 350x248x60 (mur ouest), table
ronde Ø 90 plateau verre sur pied central chromé, 4 chaises type Cesca
(cannage, piètement tubulaire) rentrées sous la table, canapé-lit gris-beige
contre le mur en retrait, petit meuble TV contre la séparation de la
cuisine, tapis, lampadaire, affiches, plantes, 2 plafonniers.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import layout as L  # noqa: E402

from lib import (H, P, apply_transform, box, cylinder, join, lathe, mesh_obj, set_collection, tag, tube,  # noqa: E402
                 uv_box)
from room_chambre import (ceiling_light, diff_mat_emission, frame_matrix, mushroom_lamp, pax, place_all,  # noqa: E402
                          poster_frame, rug, vase_eucalyptus)
import cloth  # noqa: E402

px = L.px
MUR_OUEST = L.Frame(px(34.5, 440), px(34.5, 733), 'mur_ouest')        # s vers le sud, n vers l'est
MUR_CANAPE = L.Frame(px(199, 833.5), px(488, 833.5), 'mur_canape')    # s vers l'est, n vers le nord
BLOC_SUD = L.Frame(px(473, 637.5), px(292, 637.5), 'bloc_sud')        # s vers l'ouest, n vers le sud
TABLE_C = px(205, 655)


# ------------------------------------------------------------------ table + chaises
def table():
    p = [cylinder('plateau', 0.45, 0.738, 0.75, 96, 'verre_extra', bevel=0.003)]
    col = [cylinder('fut', 0.03, 0.02, 0.738, 32, 'chrome'),
           lathe('embase', [(0.0, 0.0), (0.22, 0.0), (0.225, 0.006), (0.215, 0.018), (0.03, 0.03), (0.0, 0.03)], 64, 'chrome'),
           lathe('platine', [(0.0, 0.72), (0.12, 0.72), (0.12, 0.735), (0.0, 0.738)], 48, 'chrome')]
    return p[0], col


def cesca():
    """Chaise cantilever type Cesca. Local : x largeur, y vers l'avant, z."""
    parts, cane = [], []
    r = 0.0115
    for sx in (-0.215, 0.215):
        pts = [(sx, -0.20, r), (sx, 0.20, r)]
        for i in range(1, 7):
            a = math.pi / 2 * i / 6
            pts.append((sx, 0.20 + 0.07 * math.sin(a), r + 0.07 * (1 - math.cos(a))))
        pts += [(sx, 0.275, 0.35)]
        for i in range(1, 7):
            a = math.pi / 2 * i / 6
            pts.append((sx, 0.275 - 0.07 * (1 - math.cos(a)), 0.35 + 0.07 * math.sin(a)))
        pts += [(sx, -0.14, 0.42)]
        for i in range(1, 6):
            a = math.pi / 2 * i / 5
            pts.append((sx, -0.14 - 0.06 * math.sin(a), 0.42 + 0.06 * (1 - math.cos(a))))
        pts += [(sx, -0.225, 0.62)]
        parts.append(tube('tube', pts, r, 14, 'chrome'))
    parts.append(tube('traverse', [(-0.215, -0.20, r), (0.215, -0.20, r)], r, 14, 'chrome'))
    # assise : cadre bois noir + cannage
    zs = 0.435
    fw = 0.028
    parts += [box('assise_av', -0.235, 0.21, zs, 0.235, 0.21 + fw, zs + 0.03, 'bois_noir', bevel=0.006),
              box('assise_ar', -0.235, -0.21, zs, 0.235, -0.21 + fw, zs + 0.03, 'bois_noir', bevel=0.006),
              box('assise_g', -0.235, -0.21 + fw, zs, -0.235 + fw, 0.21, zs + 0.03, 'bois_noir', bevel=0.006, grain='y'),
              box('assise_d', 0.235 - fw, -0.21 + fw, zs, 0.235, 0.21, zs + 0.03, 'bois_noir', bevel=0.006, grain='y')]
    c = mesh_obj('cannage_assise', [(-0.21, -0.185, zs + 0.02), (0.21, -0.185, zs + 0.02), (0.21, 0.212, zs + 0.02), (-0.21, 0.212, zs + 0.02)],
                 [(0, 1, 2, 3)], 'cannage')
    uv_box(c)
    cane.append(c)
    # dossier incliné, légèrement cintré
    back = []
    zb0, zb1 = 0.60, 0.80
    for i in range(9):
        t = i / 8
        x = -0.235 + 0.47 * t
        y = -0.235 - 0.02 * (1 - (2 * t - 1) ** 2)
        back.append((x, y))
    fr_parts = []
    for (x0, y0), (x1, y1) in zip(back[:-1], back[1:]):
        for za, zb in ((zb0, zb0 + fw), (zb1 - fw, zb1)):
            v = [(x0, y0, za), (x1, y1, za), (x1, y1, zb), (x0, y0, zb)]
            fr_parts.append(box('dos_seg', min(x0, x1), min(y0, y1) - 0.012, za, max(x0, x1), max(y0, y1) + 0.012, zb, 'bois_noir'))
    fr_parts += [box('dos_g', -0.24, -0.25, zb0, -0.235 + fw, -0.22, zb1, 'bois_noir', bevel=0.005, grain='z'),
                 box('dos_d', 0.235 - fw, -0.25, zb0, 0.24, -0.22, zb1, 'bois_noir', bevel=0.005, grain='z')]
    verts, faces = [], []
    for i, (x, y) in enumerate(back):
        verts += [(x, y, zb0 + fw * 0.5), (x, y, zb1 - fw * 0.5)]
    for i in range(len(back) - 1):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    cb = mesh_obj('cannage_dos', verts, faces, 'cannage')
    uv_box(cb, grain='x')
    cane.append(cb)
    ob = join(parts + fr_parts, 'cesca')
    # inclinaison du dossier (8°) autour de l'arrière de l'assise
    return ob, join(cane, 'cesca_cannage')


# ------------------------------------------------------------------ canapé
def sofa(w=2.00, d=0.92):
    """Canapé-lit simple : accoudoirs droits, 2 coussins d'assise et 2 de dossier."""
    p = []
    arm = 0.16
    p.append(box('socle', arm - 0.02, 0.02, 0.05, w - arm + 0.02, d - 0.02, 0.26, 'canape', bevel=0.02))
    p.append(box('dos', 0.0, 0.0, 0.05, w, 0.2, 0.60, 'canape', bevel=0.04, seg=4))
    for x0 in (0.0, w - arm):
        p.append(box('accoudoir', x0, 0.0, 0.05, x0 + arm, d, 0.62, 'canape', bevel=0.05, seg=4))
    cw = (w - 2 * arm) / 2
    for k in range(2):
        x0 = arm + k * cw
        p.append(box('coussin_assise', x0 + 0.004, 0.19, 0.26, x0 + cw - 0.004, d - 0.01, 0.44, 'canape', bevel=0.055, seg=5))
        p.append(box('coussin_dos', x0 + 0.006, 0.06, 0.40, x0 + cw - 0.006, 0.25, 0.84, 'canape', bevel=0.07, seg=5))
    for x in (0.06, w - 0.06):
        for y in (0.06, d - 0.06):
            p.append(cylinder('pied', 0.02, 0.0, 0.05, 16, 'bois_noir', cx=x, cy=y))
    return p


def throw_on_sofa():
    """Plaid posé en travers de l'accoudoir (simulation de tissu)."""
    return None


# ------------------------------------------------------------------ meuble TV
def tv_unit(w=1.20, d=0.40, hh=0.52):
    p = [box('caisson', 0.0, 0.0, 0.14, w, d, hh - 0.025, 'meuble_tv', bevel=0.004),
         box('dessus', -0.005, -0.005, hh - 0.025, w + 0.005, d + 0.005, hh, 'chene', bevel=0.004)]
    for k in range(2):
        x0 = k * w / 2
        p.append(box('porte', x0 + 0.002, d, 0.142, x0 + w / 2 - 0.002, d + 0.018, hh - 0.028, 'meuble_tv', bevel=0.002))
    for x in (0.05, w - 0.05):
        for y in (0.05, d - 0.05):
            p.append(cylinder('pied', 0.017, 0.0, 0.14, 16, 'chene', cx=x, cy=y, r_top=0.022))
    return p


def television(diag_in=50):
    w = diag_in * 0.0254 * 0.8716
    h = diag_in * 0.0254 * 0.4903
    p = [box('tv', -w / 2, -0.03, 0.08, w / 2, 0.0, 0.08 + h, 'plastique_gris', bevel=0.004),
         box('tv_pied_g', -w / 2 + 0.1, -0.12, 0.0, -w / 2 + 0.13, 0.06, 0.012, 'metal_noir'),
         box('tv_pied_d', w / 2 - 0.13, -0.12, 0.0, w / 2 - 0.1, 0.06, 0.012, 'metal_noir'),
         box('tv_col', -0.05, -0.05, 0.0, 0.05, -0.02, 0.1, 'metal_noir')]
    screen = box('ecran', -w / 2 + 0.008, 0.0, 0.088, w / 2 - 0.008, 0.002, 0.08 + h - 0.008, 'ecran_tv')
    return p, screen


def floor_lamp():
    """Lampadaire : pied laiton, abat-jour en lin (émissif la nuit)."""
    base = lathe('lampadaire_pied', [(0, 0), (0.14, 0), (0.14, 0.018), (0.012, 0.025), (0.009, 1.40), (0, 1.40)], 48, 'laiton')
    shade = lathe('lampadaire_abat_jour', [(0.19, 1.30), (0.205, 1.30), (0.17, 1.58), (0.155, 1.58), (0.185, 1.31)], 64, 'abat_jour_lin')
    ld = bpy.data.lights.new('lampadaire_lum', 'POINT')
    ld.energy = 28.0
    ld.shadow_soft_size = 0.06
    ld.color = (1.0, 0.76, 0.5)
    lo = bpy.data.objects.new('lampadaire_lum', ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (0, 0, 1.43)
    return base, shade, lo


def olive_tree():
    """Petit olivier en pot (tronc + rameaux + feuilles alpha)."""
    import random
    rnd = random.Random(11)
    pot = lathe('pot_olivier', [(0, 0), (0.15, 0), (0.18, 0.36), (0.19, 0.38), (0.17, 0.38), (0.0, 0.34)], 48, 'gres_terracotta')
    soil = cylinder('terreau_olivier', 0.165, 0.33, 0.345, 32, 'terreau')
    trunk = tube('tronc', [(0, 0, 0.33), (0.02, 0.01, 0.7), (-0.01, 0.02, 1.0), (0.01, 0.0, 1.2)], 0.025, 10, 'tige')
    branches, leaves = [trunk], []
    cell = (0.0, 0.5, 0.25, 1.0)
    for b in range(9):
        a = rnd.uniform(0, 2 * math.pi)
        z0 = rnd.uniform(0.95, 1.2)
        L_ = rnd.uniform(0.25, 0.45)
        pts = [(0, 0, z0)]
        for i in range(1, 5):
            t = i / 4
            pts.append((math.cos(a) * L_ * t, math.sin(a) * L_ * t, z0 + L_ * t * rnd.uniform(0.4, 0.9)))
        branches.append(tube('rameau', pts, 0.008, 6, 'tige', caps=False))
        for i in range(1, len(pts)):
            for k in range(11):
                q = Vector(pts[i]) + Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), rnd.uniform(-0.05, 0.05)))
                ang = rnd.uniform(0, 2 * math.pi)
                sz = 0.07
                d = Vector((math.cos(ang), math.sin(ang), rnd.uniform(-0.4, 0.4))).normalized() * sz
                e = Vector((-math.sin(ang), math.cos(ang), 0)) * sz * 0.38
                vs = [q - e, q + e, q + d + e, q + d - e]
                lf = mesh_obj('feuille', [tuple(v) for v in vs], [(0, 1, 2, 3)], 'feuillage')
                uvl = lf.data.uv_layers.new(name='UVMap')
                u0, v0, u1, v1 = cell
                for li, uv in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                    uvl.data[li].uv = uv
                leaves.append(lf)
    return join([pot, soil], 'olivier_pot'), join(branches + leaves, 'olivier_feuillage')


def pothos():
    """Pothos retombant dans un pot en grès (sur le meuble TV)."""
    import random
    rnd = random.Random(21)
    pot = lathe('pot_pothos', [(0, 0), (0.07, 0), (0.09, 0.13), (0.0, 0.12)], 40, 'gres')
    stems, leaves = [], []
    cell = (0.5, 0.5, 0.75, 1.0)
    for s in range(7):
        a = rnd.uniform(-1.2, 1.2) + (math.pi if s % 3 == 0 else 0)
        L_ = rnd.uniform(0.3, 0.55)
        pts = []
        for i in range(10):
            t = i / 9
            pts.append((math.cos(a) * (0.05 + 0.25 * t), math.sin(a) * (0.05 + 0.25 * t) + 0.02, 0.14 + 0.05 * math.sin(t * 3) - L_ * max(0, t - 0.3) * 1.2))
        stems.append(tube('tige', pts, 0.003, 5, 'tige', caps=False))
        for i in range(1, 10, 1):
            q = Vector(pts[i])
            ang = a + rnd.uniform(-1.5, 1.5)
            sz = rnd.uniform(0.05, 0.075)
            d = Vector((math.cos(ang), math.sin(ang), -0.3)).normalized() * sz
            e = Vector((-math.sin(ang), math.cos(ang), 0)) * sz * 0.45
            vs = [q - e, q + e, q + d + e, q + d - e]
            lf = mesh_obj('feuille', [tuple(v) for v in vs], [(0, 1, 2, 3)], 'feuillage')
            uvl = lf.data.uv_layers.new(name='UVMap')
            u0, v0, u1, v1 = cell
            for li, uv in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                uvl.data[li].uv = uv
            leaves.append(lf)
    return pot, join(stems + leaves, 'pothos_feuillage')


def build():
    set_collection('sejour')
    out = []
    # --- placard PAX 350 (mur ouest), dégagé du passage vers le dégagement
    M = frame_matrix(MUR_OUEST, 0.20, 0.008)
    pax_ob = pax((1.0, 1.0, 1.0, 0.5), name='pax_sejour')
    # repère mural : x le long du mur (vers le sud) ; le PAX est construit x->y ; façade en +y
    place_all([pax_ob], M)
    tag(pax_ob, atlas='sejour', room='sejour', collide=True, lit='lightmap', label='Placard type PAX 350x248x60')
    out.append(pax_ob)
    # --- table + chaises rentrées
    tx, tz = TABLE_C
    top, col = table()
    for o in [top] + col:
        o.matrix_world = Matrix.Translation(P(tx, tz))
        apply_transform(o)
    colj = join(col, 'table_pied')
    tag(colj, room='sejour', lit='probe', collide=True, label='Table ronde Ø 90')
    tag(top, room='sejour', lit='glass', collide=False)
    out += [top, colj]
    for i, ang in enumerate((45, 135, 225, 315)):
        ch, cane = cesca()
        a = math.radians(ang)
        # chaise orientée vers le centre, assise avant sous le bord du plateau
        dist = 0.58  # avant de l'assise ~5 cm sous le bord du plateau
        cx, cz = tx + math.cos(a) * dist, tz + math.sin(a) * dist
        rot = math.atan2(math.cos(a), math.sin(a))  # l'avant (+y local) regarde le centre de la table
        M = Matrix.Translation(P(cx, cz)) @ Matrix.Rotation(rot, 4, 'Z')
        for o in (ch, cane):
            o.matrix_world = M
            apply_transform(o)
        tag(ch, atlas='sejour', room='sejour', collide=True, lit='lightmap', label='Chaise type Cesca')
        tag(cane, room='sejour', lit='probe', collide=False)
        out += [ch, cane]
    vase, plant = vase_eucalyptus('eucalyptus_table', seed=4)
    for o in (vase, plant):
        o.matrix_world = Matrix.Translation(P(tx + 0.05, tz - 0.06, 0.75))
        apply_transform(o)
        tag(o, room='sejour', lit='probe', collide=False)
    out += [vase, plant]
    # --- canapé contre le mur en retrait, centré
    sw_ = 2.00
    s0 = (MUR_CANAPE.length - sw_) / 2
    parts = sofa(sw_)
    place_all(parts, frame_matrix(MUR_CANAPE, s0, 0.02))
    so = join(parts, 'canape')
    tag(so, atlas='sejour', room='sejour', collide=True, lit='lightmap', label='Canapé-lit')
    out.append(so)
    # coussins déco sur le canapé
    for i, (x, m, ang) in enumerate(((0.33, 'coussin_terracotta', 12), (0.60, 'coussin_sauge', -6))):
        c = cloth.pillow(f'coussin_canape_{i}', 0.42, 0.42, thick=0.06, cell=0.02, pressure=3.2, frames=26, mat=m, bending=3.0)
        c.matrix_world = (frame_matrix(MUR_CANAPE, s0 + x, 0.33, 0.62) @ Matrix.Rotation(math.radians(-70), 4, 'X')
                          @ Matrix.Rotation(math.radians(ang), 4, 'Z') @ Matrix.Scale(0.85, 4, (0, 0, 1)))
        apply_transform(c)
        c['lm_from_uv0'] = True
        tag(c, atlas='sejour', room='sejour', collide=False, lit='lightmap')
        out.append(c)
    # plaid plié sur l'accoudoir ouest
    pl = box('plaid', 0.0, 0.10, 0.60, 0.20, 0.80, 0.66, 'plaid', bevel=0.025, seg=4)
    pl2 = box('plaid_retombee', -0.03, 0.12, 0.30, 0.0, 0.78, 0.64, 'plaid', bevel=0.012, seg=3)
    place_all([pl, pl2], frame_matrix(MUR_CANAPE, s0 - 0.02, 0.02))
    pj = join([pl, pl2], 'plaid')
    tag(pj, atlas='sejour', room='sejour', collide=False, lit='lightmap')
    out.append(pj)
    # --- tapis entre canapé et TV
    rg = rug('tapis_sejour', 2.30, 1.60, 'tapis_sejour')
    place_all([rg], frame_matrix(MUR_CANAPE, s0 + sw_ / 2 - 1.15, 0.55))
    tag(rg, atlas='sejour', room='sejour', collide=False, lit='lightmap')
    out.append(rg)
    # --- lampadaire à l'extrémité est du canapé
    base, shade, light = floor_lamp()
    M = frame_matrix(MUR_CANAPE, s0 + sw_ + 0.24, 0.30)
    for o in (base, shade):
        o.matrix_world = M
        apply_transform(o)
    light.matrix_world = M @ light.matrix_world
    tag(base, room='sejour', lit='probe', collide=True, label='Lampadaire')
    tag(shade, room='sejour', lit='lamp', lamp_group='appoint', collide=False)
    tag(light, room='sejour', lamp_group='appoint')
    diff_mat_emission('abat_jour_lin', (1.0, 0.8, 0.58), 3.0)
    out += [base, shade, light]
    # --- meuble TV contre le bloc (face sud), centré sur le canapé
    fr = BLOC_SUD
    sofa_cx = MUR_CANAPE.pt(s0 + sw_ / 2)[0]
    s_tv = (fr.o[0] - sofa_cx) - 0.60
    parts = tv_unit()
    place_all(parts, frame_matrix(fr, s_tv, 0.01))
    tvu = join(parts, 'meuble_tv')
    tag(tvu, atlas='sejour', room='sejour', collide=True, lit='lightmap', label='Meuble TV')
    out.append(tvu)
    tvp, screen = television(50)
    Mtv = frame_matrix(fr, s_tv + 0.60, 0.22, 0.52)
    place_all(tvp + [screen], Mtv)
    tvj = join(tvp, 'television')
    tag(tvj, atlas='sejour', room='sejour', collide=False, lit='lightmap')
    tag(screen, room='sejour', lit='probe', collide=False)
    out += [tvj, screen]
    body, dome, lum = mushroom_lamp('lampe_tv')
    Ml = frame_matrix(fr, s_tv + 1.08, 0.22, 0.52)
    for o in (body, dome):
        o.matrix_world = Ml
        apply_transform(o)
    lum.matrix_world = Ml @ lum.matrix_world
    tag(body, atlas='sejour', room='sejour', lit='lightmap', collide=False)
    tag(dome, room='sejour', lit='lamp', lamp_group='appoint', collide=False)
    tag(lum, room='sejour', lamp_group='appoint')
    out += [body, dome, lum]
    pot, leaves = pothos()
    Mp = frame_matrix(fr, s_tv + 0.13, 0.2, 0.52)
    for o in (pot, leaves):
        o.matrix_world = Mp
        apply_transform(o)
        tag(o, room='sejour', lit='probe', collide=False)
    out += [pot, leaves]
    # --- affiches au-dessus du canapé
    for i, (ds, art) in enumerate(((-0.28, 'affiche_cercles'), (0.28, 'affiche_formes'))):
        pf = poster_frame(f'affiche_sej_{i}', 0.40, 0.50, art)
        pf.matrix_world = frame_matrix(MUR_CANAPE, s0 + sw_ / 2 + ds, 0.0, 1.45)
        apply_transform(pf)
        tag(pf, atlas='sejour', room='sejour', collide=False, lit='lightmap')
        out.append(pf)
    pf = poster_frame('affiche_sej_2', 0.40, 0.50, 'affiche_soleil')
    pf.matrix_world = frame_matrix(fr, s_tv + 0.60 + 0.2, 0.0, 1.55)
    apply_transform(pf)
    tag(pf, atlas='sejour', room='sejour', collide=False, lit='lightmap')
    out.append(pf)
    # --- olivier près de la fenêtre (angle sud-est)
    pot, fol = olive_tree()
    Mo = Matrix.Translation(P(*px(555, 790)))
    for o in (pot, fol):
        o.matrix_world = Mo
        apply_transform(o)
    tag(pot, atlas='sejour', room='sejour', lit='lightmap', collide=True, label='Olivier')
    tag(fol, room='sejour', lit='probe', collide=False)
    out += [pot, fol]
    # --- plafonniers : coin salon et coin repas
    out += ceiling_light('plafonnier_salon', px(390, 735), 'sejour')
    out += ceiling_light('plafonnier_repas', px(150, 640), 'sejour')
    return out
