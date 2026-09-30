"""
Cuisine linéaire (référence IKEA) le long de la cloison nord, qui forme un
angle de ~8° : deux travées alignées sur chaque pan de mur, plan de travail
d'un seul tenant (coupe d'onglet au droit de l'angle).
Ouest -> est : réfrigérateur sous plan, bloc tiroirs, four + plaque, colonne
étroite 20 cm, évier rond (au droit des arrivées d'eau vues sur la vidéo).
Façades blanches type ASPUDDEN, poignées type BILLSBRO, plan EKBACKEN
terracotta à chant clair, 2 meubles hauts (fermé + vitré), desserte
NISSAFORS verte devant la fenêtre.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector
from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import layout as L  # noqa: E402

from lib import (H, P, apply_transform, box, cylinder, extrude_poly, join, lathe, material, set_collection,  # noqa: E402
                 tag, tube, uv_box)
from room_chambre import ceiling_light, diff_mat_emission, frame_matrix, poster_frame, place_all  # noqa: E402

px = L.px
# travées (repère : origine à l'extrémité est du pan, s vers l'ouest, t vers la pièce)
RUN_B = L.Frame(px(409, 503.5), px(281, 484.5), 'cuisine_B')   # pan incliné
RUN_A = L.Frame(px(281, 484.5), px(176.5, 484.5), 'cuisine_A')  # pan droit (côté refend)

D = 0.60        # profondeur des caissons (hors façade)
TOP = 0.88      # dessus des caissons
WT = 0.635      # profondeur du plan de travail
WZ = 0.038      # épaisseur du plan


def plinth_and_carcass(w, name):
    p = [box(name + '_caisson', 0.0, 0.0, 0.08, w, D - 0.002, TOP, 'caisson_cuisine'),
         box(name + '_socle', 0.0, 0.0, 0.0, w, D - 0.05, 0.08, 'aspudden')]
    return p


def front(x0, x1, z0, z1, name, handle='top', glass=False):
    """Façade avec léger cadre (profil fin) + poignée barre BILLSBRO."""
    y0, y1 = D, D + 0.019
    parts = [box(name, x0 + 0.0015, y0, z0 + 0.0015, x1 - 0.0015, y1, z1 - 0.0015, 'aspudden', bevel=0.0015, grain='z')]
    # cadre fin en relief (4 lisières)
    b, e = 0.045, 0.003
    parts += [box(name + '_l', x0 + 0.0015, y1, z0 + 0.0015, x0 + b, y1 + e, z1 - 0.0015, 'aspudden', bevel=0.001, grain='z'),
              box(name + '_r', x1 - b, y1, z0 + 0.0015, x1 - 0.0015, y1 + e, z1 - 0.0015, 'aspudden', bevel=0.001, grain='z'),
              box(name + '_t', x0 + b, y1, z1 - b, x1 - b, y1 + e, z1 - 0.0015, 'aspudden', bevel=0.001),
              box(name + '_b', x0 + b, y1, z0 + 0.0015, x1 - b, y1 + e, z0 + b, 'aspudden', bevel=0.001)]
    if handle == 'top':
        hw = min(0.32, (x1 - x0) * 0.6)
        cx = (x0 + x1) / 2
        parts.append(box(name + '_poignee', cx - hw / 2, y1 + e, z1 - 0.05, cx + hw / 2, y1 + e + 0.022, z1 - 0.038, 'plastique_blanc', bevel=0.003))
    elif handle in ('left', 'right'):
        hx = x0 + 0.05 if handle == 'left' else x1 - 0.05
        parts.append(box(name + '_poignee', hx - 0.006, y1 + e, z0 + 0.08, hx + 0.006, y1 + e + 0.022, z0 + 0.32, 'plastique_blanc', bevel=0.003, grain='z'))
    elif handle == 'bottom':
        hw = min(0.32, (x1 - x0) * 0.6)
        cx = (x0 + x1) / 2
        parts.append(box(name + '_poignee', cx - hw / 2, y1 + e, z0 + 0.04, cx + hw / 2, y1 + e + 0.022, z0 + 0.052, 'plastique_blanc', bevel=0.003))
    return parts


def fridge(w=0.60):
    """Réfrigérateur blanc sous plan (pose libre, 85 cm)."""
    p = [box('frigo', 0.005, 0.02, 0.0, w - 0.005, D + 0.01, 0.845, 'plastique_blanc', bevel=0.012)]
    p.append(box('frigo_porte', 0.01, D + 0.01, 0.02, w - 0.01, D + 0.045, 0.83, 'plastique_blanc', bevel=0.01))
    p.append(box('frigo_poignee', 0.06, D + 0.045, 0.74, w - 0.06, D + 0.07, 0.765, 'plastique_blanc', bevel=0.008))
    p.append(box('frigo_grille', 0.03, D + 0.012, 0.0, w - 0.03, D + 0.02, 0.018, 'plastique_gris'))
    return p


def oven_unit(w=0.60):
    p = plinth_and_carcass(w, 'four')
    # tiroir bas
    p += front(0.0, w, 0.08, 0.20, 'four_tiroir', 'top')
    # four encastré : vitre noire, bandeau inox, deux manettes, poignée
    y = D + 0.002
    p.append(box('four_cadre', 0.005, y, 0.205, w - 0.005, y + 0.02, TOP - 0.005, 'inox', bevel=0.003))
    p.append(box('four_vitre', 0.03, y + 0.02, 0.23, w - 0.03, y + 0.024, TOP - 0.13, 'verre_noir', bevel=0.004))
    p.append(box('four_bandeau', 0.02, y + 0.02, TOP - 0.115, w - 0.02, y + 0.024, TOP - 0.015, 'verre_noir'))
    for cx in (0.09, w - 0.09):
        k = cylinder('manette', 0.018, 0, 0.022, 24, 'inox', bevel=0.003)
        k.matrix_world = Matrix.Translation((cx, y + 0.024, TOP - 0.065)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
        apply_transform(k)
        p.append(k)
    bar = cylinder('four_poignee', 0.008, 0.06, w - 0.06, 16, 'inox')
    bar.matrix_world = Matrix.Translation((0, y + 0.06, TOP - 0.16)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
    apply_transform(bar)
    p.append(bar)
    for cx in (0.06, w - 0.06):
        st = cylinder('four_plot', 0.006, 0, 0.04, 12, 'inox')
        st.matrix_world = Matrix.Translation((cx, y + 0.024, TOP - 0.16)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
        apply_transform(st)
        p.append(st)
    return p


def drawers_unit(w, name, n=2):
    p = plinth_and_carcass(w, name)
    if n == 2:
        p += front(0.0, w, 0.08, 0.465, name + '_t1', 'top')
        p += front(0.0, w, 0.465, TOP, name + '_t2', 'top')
    else:
        p += front(0.0, w, 0.08, 0.36, name + '_t1', 'top')
        p += front(0.0, w, 0.36, 0.62, name + '_t2', 'top')
        p += front(0.0, w, 0.62, TOP, name + '_t3', 'top')
    return p


def narrow_unit(w=0.20):
    p = plinth_and_carcass(w, 'etroit')
    p += front(0.0, w, 0.08, TOP, 'etroit_f', 'right')
    return p


def upper(w, name, glazed=False, z0=1.45, z1=2.25, depth=0.37):
    p = [box(name + '_caisson', 0, 0, z0, w, depth - 0.002, z1, 'caisson_cuisine')]
    y0, y1 = depth, depth + 0.019
    if not glazed:
        n = 2 if w > 0.6 else 1
        for k in range(n):
            a, b = k * w / n, (k + 1) * w / n
            p += [box(f'{name}_porte{k}', a + 0.0015, y0, z0 + 0.0015, b - 0.0015, y1, z1 - 0.0015, 'aspudden', bevel=0.0015, grain='z')]
            hx = b - 0.04 if k == 0 and n == 2 else a + 0.04
            p.append(box(f'{name}_poignee{k}', hx - 0.006, y1, z0 + 0.04, hx + 0.006, y1 + 0.022, z0 + 0.26, 'plastique_blanc', bevel=0.003, grain='z'))
        # intérieur non visible
    else:
        # deux portes vitrées superposées (cadre blanc + verre) et étagères avec vaisselle
        zm = (z0 + z1) / 2
        for k, (a, b) in enumerate(((z0, zm), (zm, z1))):
            e = 0.05
            p += [box(f'{name}_c{k}g', 0.0015, y0, a + 0.0015, e, y1, b - 0.0015, 'aspudden', bevel=0.0015, grain='z'),
                  box(f'{name}_c{k}d', w - e, y0, a + 0.0015, w - 0.0015, y1, b - 0.0015, 'aspudden', bevel=0.0015, grain='z'),
                  box(f'{name}_c{k}h', e, y0, b - e, w - e, y1, b - 0.0015, 'aspudden', bevel=0.0015),
                  box(f'{name}_c{k}b', e, y0, a + 0.0015, w - e, y1, a + e, 'aspudden', bevel=0.0015)]
            p.append(box(f'{name}_poignee{k}', w / 2 - 0.12, y1, a + 0.012, w / 2 + 0.12, y1 + 0.022, a + 0.024, 'plastique_blanc', bevel=0.003))
        # l'intérieur du caisson vitré se voit : parois blanches + étagère
        p.append(box(name + '_etagere', 0.018, 0.0, zm - 0.009, w - 0.018, depth - 0.02, zm + 0.009, 'caisson_cuisine'))
    return p


def glazing(w, name, z0=1.45, z1=2.25, depth=0.37):
    zm = (z0 + z1) / 2
    g = []
    for k, (a, b) in enumerate(((z0, zm), (zm, z1))):
        g.append(box(f'{name}_verre{k}', 0.045, depth + 0.008, a + 0.045, w - 0.045, depth + 0.012, b - 0.045, 'verre_extra'))
    return join(g, name + '_vitrage')


def dishes(w, z0, zm, depth=0.37):
    """Assiettes empilées et verres dans le meuble vitré (éclairés par sonde)."""
    p = []
    for level, zb in ((0, z0 + 0.018), (1, zm + 0.009)):
        for i in range(6):
            pl = lathe('assiette', [(0.0, 0.0), (0.07, 0.0), (0.12, 0.012), (0.125, 0.018), (0.0, 0.006)], 32, 'vaisselle')
            pl.matrix_world = Matrix.Translation((w * 0.34, depth * 0.5, zb + i * 0.014))
            apply_transform(pl)
            p.append(pl)
        for i in range(3):
            gl = lathe('verre', [(0.0, 0.0), (0.03, 0.0), (0.035, 0.11), (0.032, 0.11), (0.027, 0.004), (0.0, 0.004)], 24, 'bouteille_verre')
            gl.matrix_world = Matrix.Translation((w * 0.72 + (i % 2) * 0.06 - 0.03, depth * 0.35 + (i // 2) * 0.1, zb))
            apply_transform(gl)
            p.append(gl)
    return join(p, 'vaisselle')


def worktop():
    """Plan de travail d'un seul tenant (onglet à l'angle), dessus terracotta, chant clair."""
    sA0, sA1 = 0.0, RUN_A.length - 0.005            # du coude au refend
    sB0 = 0.30                                        # extrémité est (avant la niche de la fenêtre)
    a_wall = [RUN_A.pt(sA1, 0.0), RUN_A.pt(sA0, 0.0)]
    b_wall = [RUN_B.pt(RUN_B.length, 0.0), RUN_B.pt(sB0, 0.0)]
    # intersection des deux lignes décalées de WT
    def line(fr, t):
        p0 = fr.pt(0, t)
        return p0, fr.u
    (pa, ua), (pb, ub) = line(RUN_A, WT), line(RUN_B, WT)
    den = ua[0] * ub[1] - ua[1] * ub[0]
    k = ((pb[0] - pa[0]) * ub[1] - (pb[1] - pa[1]) * ub[0]) / den
    corner = (pa[0] + ua[0] * k, pa[1] + ua[1] * k)
    poly = [RUN_A.pt(sA1, 0.0), RUN_A.pt(0.0, 0.0), RUN_B.pt(sB0, 0.0), RUN_B.pt(sB0, WT), corner, RUN_A.pt(sA1, WT)]
    ob = extrude_poly('plan_de_travail', [poly], TOP, TOP + WZ, mat='chant_clair')
    ob.data.materials.append(material('ekbacken'))
    for f in ob.data.polygons:
        if f.normal.z > 0.9:
            f.material_index = 1
    return ob, poly


def sink_and_tap(s_center):
    """Évier rond inox encastré (Ø 45) + robinet col de cygne, au droit des arrivées d'eau."""
    fr = RUN_B
    parts = []
    bowl = lathe('evier', [(0.0, TOP + WZ - 0.18), (0.18, TOP + WZ - 0.18), (0.205, TOP + WZ - 0.12),
                           (0.215, TOP + WZ - 0.004), (0.235, TOP + WZ + 0.002), (0.24, TOP + WZ)], 64, 'inox')
    drain = cylinder('bonde', 0.035, TOP + WZ - 0.182, TOP + WZ - 0.176, 32, 'chrome')
    base = cylinder('robinet_socle', 0.026, TOP + WZ, TOP + WZ + 0.05, 32, 'chrome', bevel=0.004)
    neck = []
    for i in range(18):
        a = math.pi * i / 17
        neck.append((0.0, -0.13 * (1 - math.cos(a)) / 2 * 1.0 if False else 0.0, 0))
    pts = [(0, 0, TOP + WZ + 0.05), (0, 0, TOP + WZ + 0.26)]
    for i in range(1, 15):
        a = math.pi * i / 14
        pts.append((0, 0.09 - 0.09 * math.cos(a), TOP + WZ + 0.26 + 0.09 * math.sin(a)))
    pts.append((0, 0.18, TOP + WZ + 0.2))
    spout = tube('robinet_col', pts, 0.012, 20, 'chrome')
    lever = box('robinet_levier', -0.006, -0.03, TOP + WZ + 0.12, 0.006, 0.0, TOP + WZ + 0.13, 'chrome', bevel=0.004)
    lever2 = box('robinet_levier2', 0.01, -0.012, TOP + WZ + 0.11, 0.06, 0.012, TOP + WZ + 0.125, 'chrome', bevel=0.005)
    Mb = frame_matrix(fr, s_center, 0.33)
    for o in (bowl, drain):
        o.matrix_world = Mb
        apply_transform(o)
    Mt = frame_matrix(fr, s_center, 0.07)
    for o in (base, spout, lever, lever2):
        o.matrix_world = Mt
        apply_transform(o)
    return join([bowl, drain], 'evier'), join([base, spout, lever, lever2], 'robinet')


def hob(s_center):
    h = box('plaque', -0.29, 0.07, TOP + WZ, 0.29, 0.58, TOP + WZ + 0.006, 'verre_noir', bevel=0.003)
    h.matrix_world = frame_matrix(RUN_B, s_center, 0.0)
    apply_transform(h)
    return h


def nissafors():
    """Desserte métallique 3 niveaux verte (50,5 x 30 x 83 cm) sur roulettes."""
    w, d, hh = 0.505, 0.30, 0.83
    p = []
    for zb in (0.12, 0.43, 0.74):
        p.append(box('bac', 0, 0, zb, w, d, zb + 0.012, 'nissafors', bevel=0.004))
        for side in ((0, 0, w, 0.008), (0, d - 0.008, w, d), (0, 0, 0.008, d), (w - 0.008, 0, w, d)):
            p.append(box('rebord', side[0], side[1], zb, side[2], side[3], zb + 0.075, 'nissafors', bevel=0.002))
    for x in (0.012, w - 0.012):
        for y in (0.012, d - 0.012):
            p.append(cylinder('montant', 0.009, 0.07, hh, 16, 'nissafors', cx=x, cy=y))
            p.append(cylinder('roue', 0.03, 0.0, 0.06, 20, 'caoutchouc', cx=x, cy=y))
    return p


def kitchen_accessories():
    """Plantes aromatiques, bouteilles d'huile, coupe de citrons, pot."""
    items = []
    fr = RUN_A
    z = TOP + WZ
    pot = lathe('pot_basilic', [(0, 0), (0.06, 0), (0.07, 0.11), (0.066, 0.115), (0.0, 0.1)], 32, 'gres')
    soil = cylinder('terreau', 0.062, 0.095, 0.1, 24, 'terreau')
    items += [(pot, fr, 1.20, 0.25), (soil, fr, 1.20, 0.25)]
    leaves = basil_leaves()
    items.append((leaves, fr, 1.20, 0.25))
    for i, (col, hgt) in enumerate((('bouteille_huile', 0.30), ('bouteille_verre', 0.26))):
        b = lathe('bouteille', [(0, 0), (0.035, 0), (0.037, 0.01), (0.036, hgt * 0.72), (0.014, hgt * 0.86),
                                (0.013, hgt), (0.0, hgt)], 24, col)
        items.append((b, fr, 1.02 - i * 0.08, 0.12))
    bowl = lathe('coupe', [(0, 0), (0.05, 0), (0.11, 0.07), (0.105, 0.072), (0.045, 0.006), (0, 0.006)], 40, 'gres')
    items.append((bowl, fr, 0.80, 0.30))
    for k in range(5):
        a = k * 1.3
        c = lathe('citron', [(0, -0.03), (0.02, -0.024), (0.031, 0.0), (0.02, 0.024), (0.0, 0.03)], 16, 'citron')
        c.matrix_world = Matrix.Translation((math.cos(a) * 0.045, math.sin(a) * 0.045, 0.045 + (0.02 if k == 4 else 0)))
        apply_transform(c)
        items.append((c, fr, 0.80, 0.30))
    jar = lathe('bocal', [(0, 0), (0.05, 0), (0.05, 0.14), (0.0, 0.14)], 32, 'gres')
    lid = cylinder('couvercle', 0.052, 0.14, 0.16, 32, 'chene')
    items += [(jar, fr, 0.55, 0.14), (lid, fr, 0.55, 0.14)]
    out = []
    for o, f, s, t in items:
        o.matrix_world = frame_matrix(f, s, t, z) @ o.matrix_world
        apply_transform(o)
        out.append(o)
    return out


def basil_leaves():
    import random
    rnd = random.Random(5)
    from lib import mesh_obj
    leaves = []
    cell = (0.75, 0.5, 1.0, 1.0)
    for k in range(34):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.0, 0.09)
        z = rnd.uniform(0.13, 0.26)
        sz = rnd.uniform(0.035, 0.05)
        cx, cy = math.cos(a) * r, math.sin(a) * r
        dx, dy = math.cos(a) * sz, math.sin(a) * sz
        ex, ey = -math.sin(a) * sz * 0.35, math.cos(a) * sz * 0.35
        tilt = rnd.uniform(0.01, 0.03)
        vs = [(cx - ex, cy - ey, z), (cx + ex, cy + ey, z), (cx + dx + ex, cy + dy + ey, z + tilt), (cx + dx - ex, cy + dy - ey, z + tilt)]
        lf = mesh_obj('feuille', vs, [(0, 1, 2, 3)], 'feuillage')
        uvl = lf.data.uv_layers.new(name='UVMap')
        u0, v0, u1, v1 = cell
        for li, uv in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            uvl.data[li].uv = uv
        leaves.append(lf)
    return join(leaves, 'basilic')


def led_strip(fr, s0, s1, z):
    """Réglette LED sous les meubles hauts (émissif + source surfacique)."""
    st = box('led', 0.02, 0.30, z - 0.012, s1 - s0 - 0.02, 0.33, z - 0.002, 'led_ruban')
    st.matrix_world = frame_matrix(fr, s0, 0.0)
    apply_transform(st)
    ld = bpy.data.lights.new('led_cuisine', 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size = s1 - s0 - 0.06
    ld.size_y = 0.03
    ld.energy = 14.0
    ld.color = (1.0, 0.82, 0.6)
    lo = bpy.data.objects.new('led_cuisine', ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.matrix_world = frame_matrix(fr, (s0 + s1) / 2, 0.31, z - 0.015)
    tag(st, room='cuisine', lit='lamp', lamp_group='integre', collide=False)
    tag(lo, room='cuisine', lamp_group='integre')
    diff_mat_emission('led_ruban', (1.0, 0.8, 0.55), 12.0)
    return [st, lo]


def build():
    set_collection('cuisine')
    out = []
    # --- travée A (pan droit) : réfrigérateur contre le refend, bloc tiroirs
    fA = RUN_A
    sw = fA.length - 0.005
    runA = []
    runA.append(('frigo', fridge(), sw - 0.60))
    runA.append(('tiroirs_a', drawers_unit(0.60, 'tiroirs_a', 3), sw - 1.20))
    for name, parts, s0 in runA:
        place_all(parts, frame_matrix(fA, s0, 0.0))
        ob = join(parts, name)
        tag(ob, atlas='cuisine', room='cuisine', collide=True, lit='lightmap', label='Cuisine')
        out.append(ob)
    # fileur au coude
    fil = box('fileur', 0.0, 0.0, 0.08, sw - 1.20, D + 0.019, TOP, 'aspudden')
    place_all([fil], frame_matrix(fA, 0.0, 0.0))
    tag(fil, atlas='cuisine', room='cuisine', collide=True, lit='lightmap')
    out.append(fil)
    # --- travée B (pan incliné), depuis le coude vers l'est : four, colonne étroite, évier
    fB = RUN_B
    sk = fB.length
    runB = [('four', oven_unit(), sk - 0.60), ('etroit', narrow_unit(), sk - 0.80), ('evier_meuble', drawers_unit(0.60, 'evier_meuble', 2), sk - 1.40)]
    for name, parts, s0 in runB:
        place_all(parts, frame_matrix(fB, s0, 0.0))
        ob = join(parts, name)
        tag(ob, atlas='cuisine', room='cuisine', collide=True, lit='lightmap', label='Cuisine')
        out.append(ob)
    # joue de finition côté est
    joue = box('joue', 0.0, 0.0, 0.0, 0.019, D + 0.019, TOP, 'aspudden')
    place_all([joue], frame_matrix(fB, sk - 1.40 - 0.019, 0.0))
    tag(joue, atlas='cuisine', room='cuisine', collide=True, lit='lightmap')
    out.append(joue)
    wt, poly = worktop()
    tag(wt, atlas='cuisine', room='cuisine', collide=True, lit='lightmap')
    out.append(wt)
    hb = hob(sk - 0.30)
    tag(hb, room='cuisine', lit='probe', collide=False)
    out.append(hb)
    sink, tap = sink_and_tap(sk - 1.10)
    for o in (sink, tap):
        tag(o, room='cuisine', lit='probe', collide=False)
    out += [sink, tap]
    # --- meubles hauts sur la travée A : fermé 80 (côté refend) + vitré 60
    closed = upper(0.80, 'haut_ferme')
    place_all(closed, frame_matrix(fA, sw - 0.80, 0.0))
    ob = join(closed, 'haut_ferme')
    tag(ob, atlas='cuisine', room='cuisine', collide=False, lit='lightmap')
    out.append(ob)
    glz = upper(0.60, 'haut_vitre', glazed=True)
    Mg = frame_matrix(fA, sw - 1.40, 0.0)
    place_all(glz, Mg)
    ob = join(glz, 'haut_vitre')
    tag(ob, atlas='cuisine', room='cuisine', collide=False, lit='lightmap')
    out.append(ob)
    gv = glazing(0.60, 'haut_vitre')
    place_all([gv], Mg)
    tag(gv, room='cuisine', lit='glass', collide=False, bake_hide=True)
    ds = dishes(0.60, 1.45, 1.85)
    place_all([ds], Mg)
    tag(ds, room='cuisine', lit='probe', collide=False)
    out += [gv, ds]
    out += led_strip(fA, sw - 1.40, sw, 1.45)
    # --- accessoires, affiche, desserte
    for o in kitchen_accessories():
        tag(o, room='cuisine', lit='probe', collide=False)
        out.append(o)
    pf = poster_frame('affiche_cuisine', 0.30, 0.40, 'affiche_bouquet')
    pf.matrix_world = frame_matrix(fB, 0.55, 0.0, 1.62)
    apply_transform(pf)
    tag(pf, atlas='cuisine', room='cuisine', collide=False, lit='lightmap')
    out.append(pf)
    # desserte dans la niche de la fenêtre (entre le décrochement et le mur nord)
    cart = nissafors()
    niche = L.Frame(px(476, 563), px(476, 510), 'niche')  # face intérieure du mur de la fenêtre
    place_all(cart, frame_matrix(niche, 0.09, 0.03))
    ob = join(cart, 'nissafors')
    tag(ob, atlas='cuisine', room='cuisine', collide=True, lit='lightmap', label='Desserte NISSAFORS')
    out.append(ob)
    # plafonnier
    room = Polygon([r for r in L.PLAN['rooms'] if r['id'] == 'cuisine'][0]['poly'])
    c = room.centroid
    out += ceiling_light('plafonnier_cuisine', (c.x, c.y), 'cuisine')
    return out
