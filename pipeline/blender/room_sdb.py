"""
Salle de bain (existant conservé, d'après la vidéo) : le long du mur
extérieur, depuis la porte : lavabo suspendu rectangulaire, bidet, WC posé
(plaque de commande au mur), puis receveur de douche sur toute la largeur au
fond. Ajouts : paroi de douche en verre transparent, miroir rond
rétroéclairé, porte-serviettes, panier à savon, tapis de bain.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import layout as L  # noqa: E402

from lib import (H, P, apply_transform, box, cylinder, join, lathe, mesh_obj, set_collection, tag, tube,  # noqa: E402
                 triangulate)
from room_chambre import diff_mat_emission, frame_matrix, place_all, rug  # noqa: E402

px = L.px
# mur extérieur (sanitaires) : origine au fond (douche), s vers la porte, t vers la pièce
MUR_SAN = L.Frame(px(293.5, 106.5), px(122, 328.5), 'mur_sanitaires')
# cloison chambre (en face) : origine côté porte, s vers le fond
CLOISON = L.Frame(px(201, 390), px(371, 170), 'cloison_sdb')
WIDTH = 1.35
SHOWER = 0.90


def loft(name, shapes, mat, cap_top=True, cap_bottom=False):
    """Surface passant par des contours (liste de (z, [(x, y)...]) même nombre de points)."""
    verts, faces = [], []
    n = len(shapes[0][1])
    for z, pts in shapes:
        for x, y in pts:
            verts.append((x, y, z))
    for k in range(len(shapes) - 1):
        for i in range(n):
            j = (i + 1) % n
            a, b = k * n + i, k * n + j
            faces.append((a, b, b + n, a + n))
    if cap_top:
        z, pts = shapes[-1]
        base = len(verts)
        verts.append((sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, z))
        for i in range(n):
            faces.append(((len(shapes) - 1) * n + i, (len(shapes) - 1) * n + (i + 1) % n, base))
    ob = mesh_obj(name, verts, faces, mat)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    for p in ob.data.polygons:
        p.use_smooth = True
    from lib import uv_box
    uv_box(ob)
    return ob


def pan_shape(w, d, k=1.0, n=32):
    """Empreinte d'une cuvette : arrière droit contre le mur (y=0), avant arrondi."""
    pts = []
    r = w / 2 * k
    for i in range(n):
        t = i / (n - 1)
        a = math.pi * t
        # demi-ellipse avant
        x = -math.cos(a) * r
        y = (d - r) * k + math.sin(a) * r * 1.25
        pts.append((x, y))
    pts.append((r, 0.01))
    pts.append((-r, 0.01))
    return pts


def toilet(name, bidet=False):
    w, d = 0.36, 0.54 if not bidet else 0.52
    shapes = []
    for z, k in ((0.0, 0.78), (0.10, 0.80), (0.25, 0.9), (0.36, 0.99), (0.40, 1.0)):
        shapes.append((z, pan_shape(w, d, k)))
    body = loft(name, shapes, 'ceramique')
    parts = [body]
    if not bidet:
        seat = [(0.40, pan_shape(w + 0.01, d + 0.005, 1.0)), (0.435, pan_shape(w + 0.01, d + 0.005, 0.98))]
        parts.append(loft(name + '_abattant', seat, 'ceramique'))
    else:
        tap = cylinder('bidet_mitigeur', 0.018, 0.40, 0.48, 24, 'chrome', cx=0.0, cy=0.07)
        spout = box('bidet_bec', -0.01, 0.07, 0.46, 0.01, 0.14, 0.475, 'chrome', bevel=0.004)
        parts += [tap, spout]
    return join(parts, name)


def basin():
    """Vasque rectangulaire suspendue 60 x 45 (d'après la vidéo) + mitigeur + siphon."""
    w, d, h = 0.60, 0.45, 0.14
    z1 = 0.86
    outer = box('vasque', -w / 2, 0.0, z1 - h, w / 2, d, z1, 'ceramique', bevel=0.012, seg=3)
    inner = box('vasque_creux', -w / 2 + 0.035, 0.09, z1 - h + 0.03, w / 2 - 0.035, d - 0.035, z1 + 0.001, 'ceramique', bevel=0.02, seg=3)
    import bmesh
    # creuse la vasque (booléen)
    m = outer.modifiers.new('creux', 'BOOLEAN')
    m.object = inner
    m.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.modifier_apply(modifier='creux')
    bpy.data.objects.remove(inner)
    from lib import smooth_by_angle, uv_box
    smooth_by_angle(outer, 35)
    uv_box(outer)
    parts = [outer]
    parts.append(cylinder('bonde', 0.02, z1 - h + 0.028, z1 - h + 0.034, 24, 'chrome', cx=0.0, cy=0.27))
    tap = [cylinder('mitigeur', 0.02, z1, z1 + 0.16, 32, 'chrome', cx=-0.2, cy=0.045, bevel=0.003),
           box('bec', -0.21, 0.045, z1 + 0.13, -0.19, 0.17, z1 + 0.15, 'chrome', bevel=0.006),
           box('levier', -0.205, 0.0, z1 + 0.17, -0.195, 0.07, z1 + 0.18, 'chrome', bevel=0.004)]
    siphon = [cylinder('siphon', 0.018, 0.40, z1 - h, 24, 'chrome', cx=0.0, cy=0.26),
              cylinder('siphon_bouteille', 0.032, 0.33, 0.47, 24, 'chrome', cx=0.0, cy=0.26, bevel=0.01),
              tube('siphon_mur', [(0.0, 0.26, 0.40), (0.0, 0.0, 0.40)], 0.016, 16, 'chrome')]
    return join(parts + tap + siphon, 'lavabo')


def shower_set():
    """Colonne de douche : pomme de tête Ø 25, barre, douchette, mitigeur (mur gauche)."""
    p = [cylinder('col_barre', 0.012, 0.95, 2.10, 20, 'chrome', cx=0.0, cy=0.05)]
    arm = tube('col_bras', [(0.0, 0.05, 2.10), (0.0, 0.05, 2.14), (0.0, 0.10, 2.16), (0.0, 0.30, 2.16)], 0.011, 16, 'chrome')
    head = cylinder('pomme', 0.125, 2.12, 2.135, 64, 'chrome', cx=0.0, cy=0.33, bevel=0.004)
    mixer = box('mitigeur_douche', -0.09, 0.0, 1.06, 0.09, 0.07, 1.12, 'chrome', bevel=0.015)
    knob = cylinder('manette', 0.024, 0.0, 0.035, 24, 'chrome')
    knob.matrix_world = Matrix.Translation((0.07, 0.07, 1.09)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    apply_transform(knob)
    hand = tube('douchette', [(0.0, 0.07, 1.45), (0.0, 0.1, 1.62), (0.0, 0.12, 1.70)], 0.014, 16, 'chrome')
    hose = tube('flexible', [(0.0, 0.07, 1.10), (0.02, 0.10, 0.95), (0.03, 0.10, 0.80), (0.02, 0.09, 0.95), (0.01, 0.08, 1.2), (0.0, 0.07, 1.45)], 0.006, 8, 'chrome')
    slider = box('curseur', -0.02, 0.03, 1.42, 0.02, 0.08, 1.48, 'chrome', bevel=0.006)
    return join(p + [arm, head, mixer, knob, hand, hose, slider], 'colonne_douche')


def soap_basket():
    p = [box('panier_fond', -0.15, 0.02, 0.0, 0.15, 0.12, 0.004, 'chrome')]
    for y in (0.02, 0.12):
        p.append(tube('panier_bord', [(-0.15, y, 0.04), (0.15, y, 0.04)], 0.003, 8, 'chrome'))
    for x in (-0.15, 0.15):
        p.append(tube('panier_cote', [(x, 0.02, 0.04), (x, 0.12, 0.04)], 0.003, 8, 'chrome'))
    for x in (-0.14 + 0.02 * i for i in range(15)):
        p.append(tube('panier_fil', [(x, 0.02, 0.0), (x, 0.12, 0.0)], 0.0018, 6, 'chrome', caps=False))
    for i, (x, col, hh) in enumerate(((-0.07, 'savon_blanc', 0.17), (0.0, 'savon_ambre', 0.19), (0.075, 'savon_blanc', 0.15))):
        b = lathe('flacon', [(0, 0.004), (0.028, 0.004), (0.03, 0.02), (0.03, hh * 0.8), (0.012, hh * 0.9), (0.01, hh), (0, hh)], 24, col)
        b.matrix_world = Matrix.Translation((x, 0.07, 0.0))
        apply_transform(b)
        p.append(b)
    return join(p, 'panier_savon')


def towel_rail(length=0.6, bars=2):
    p = []
    for k in range(bars):
        z = -0.18 * k
        p.append(cylinder('barre', 0.009, 0, length, 16, 'chrome'))
        p[-1].matrix_world = Matrix.Translation((0, 0.07, z)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
        apply_transform(p[-1])
        for x in (0.0, length):
            p.append(cylinder('support', 0.012, 0, 0.07, 16, 'chrome'))
            p[-1].matrix_world = Matrix.Translation((x, 0.0, z)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
            apply_transform(p[-1])
    return p


def towel(width=0.5, drop=0.55, name='serviette'):
    """Serviette pliée sur une barre : deux pans et un pli arrondi."""
    t = 0.012
    p = [box(name + '_av', 0.0, 0.085, -drop, width, 0.085 + t, 0.0, 'eponge', bevel=0.005),
         box(name + '_ar', 0.0, 0.055 - t, -drop * 0.85, width, 0.055, 0.0, 'eponge', bevel=0.005)]
    arc = tube(name + '_pli', [(0.0, 0.07, 0.01), (width, 0.07, 0.01)], 0.022, 12, 'eponge')
    return join(p + [arc], name)


def shower_screen():
    """Paroi de douche : panneau fixe + porte battante, verre clair 8 mm, profilés chromés."""
    glass, metal = [], []
    zt = 2.0
    y = SHOWER  # plan de la paroi (le long de t)
    # repère local : x = t (largeur), y = s (profondeur), construit puis tourné
    fixed = (0.0, 0.62)
    door = (0.63, WIDTH - 0.01)
    for (a, b), nm in ((fixed, 'fixe'), (door, 'porte')):
        glass.append(box('verre_' + nm, a + 0.004, -0.004, 0.045, b - 0.004, 0.004, zt, 'verre'))
    metal.append(box('profil_mur', -0.0, -0.012, 0.04, 0.02, 0.012, zt, 'chrome'))
    metal.append(box('profil_haut', 0.0, -0.01, zt, 0.62, 0.01, zt + 0.02, 'chrome'))
    for zz in (0.3, 1.7):
        metal.append(box('charniere', door[1] - 0.02, -0.02, zz, door[1] + 0.01, 0.02, zz + 0.08, 'chrome', bevel=0.004))
    metal.append(box('poignee', door[0] + 0.06, -0.05, 0.9, door[0] + 0.075, 0.05, 1.25, 'chrome', bevel=0.005))
    return glass, metal


def mirror_round():
    r = 0.35
    n = 72
    verts = [(0, 0.03, 0)] + [(r * math.cos(2 * math.pi * i / n), 0.03, r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    faces = [(0, i + 1, (i + 1) % n + 1) for i in range(n)]
    mir = mesh_obj('miroir', verts, faces, 'miroir')
    for f in mir.data.polygons:
        if f.normal.y < 0:
            f.flip()
    rim = lathe('miroir_cadre', [(r - 0.004, 0.024), (r + 0.006, 0.024), (r + 0.006, 0.034), (r - 0.004, 0.034)], 72, 'laiton')
    rim.matrix_world = Matrix.Rotation(-math.pi / 2, 4, 'X')
    apply_transform(rim)
    halo = lathe('miroir_led', [(r - 0.03, 0.004), (r - 0.01, 0.004), (r - 0.01, 0.022), (r - 0.03, 0.022)], 72, 'led_ruban')
    halo.matrix_world = Matrix.Rotation(-math.pi / 2, 4, 'X')
    apply_transform(halo)
    return mir, rim, halo


def build():
    set_collection('salle_de_bain')
    out = []
    f = MUR_SAN
    # receveur existant sur toute la largeur du fond
    tray = box('receveur', 0.0, 0.0, 0.0, SHOWER, WIDTH, 0.035, 'receveur', bevel=0.004)
    drain = cylinder('siphon_douche', 0.05, 0.035, 0.037, 32, 'inox', cx=SHOWER * 0.5, cy=0.3)
    place_all([tray, drain], frame_matrix(f, 0.0, 0.0))
    tray = join([tray, drain], 'receveur')
    tag(tray, atlas='sdb', room='sdb', collide=False, lit='lightmap')
    out.append(tray)
    # paroi vitrée au bord du receveur (parallèle à la largeur de la pièce)
    glass, metal = shower_screen()
    Mscr = frame_matrix(f, SHOWER, 0.0) @ Matrix.Rotation(math.pi / 2, 4, 'Z')
    for o in glass + metal:
        o.matrix_world = Mscr
        apply_transform(o)
    g = join(glass, 'paroi_verre')
    m = join(metal, 'paroi_profils')
    tag(g, room='sdb', lit='glass', collide=True, bake_hide=True, label='Paroi de douche')
    tag(m, room='sdb', lit='probe', collide=False)
    out += [g, m]
    col = shower_set()
    col.matrix_world = frame_matrix(f, 0.45, 0.0)
    apply_transform(col)
    tag(col, room='sdb', lit='probe', collide=False)
    out.append(col)
    sb = soap_basket()
    sb.matrix_world = frame_matrix(f, 0.72, 0.0, 1.25)
    apply_transform(sb)
    tag(sb, room='sdb', lit='probe', collide=False)
    out.append(sb)
    # WC, bidet, plaque de commande
    for name, s, bid in (('wc', 1.30, False), ('bidet', 1.86, True)):
        o = toilet(name, bid)
        o.matrix_world = frame_matrix(f, s, 0.0)
        apply_transform(o)
        tag(o, atlas='sdb', room='sdb', collide=True, lit='lightmap', label='WC' if not bid else 'Bidet')
        out.append(o)
    plate = box('plaque_wc', -0.12, 0.0, 0.98, 0.12, 0.012, 1.14, 'plastique_blanc', bevel=0.003)
    b1 = box('bouton1', -0.10, 0.012, 1.0, -0.005, 0.016, 1.12, 'plastique_blanc', bevel=0.004)
    b2 = box('bouton2', 0.005, 0.012, 1.0, 0.10, 0.016, 1.12, 'plastique_blanc', bevel=0.004)
    pl = join([plate, b1, b2], 'plaque_commande')
    pl.matrix_world = frame_matrix(f, 1.30, 0.012)
    apply_transform(pl)
    tag(pl, atlas='sdb', room='sdb', collide=False, lit='lightmap')
    out.append(pl)
    # lavabo + miroir rétroéclairé
    lv = basin()
    lv.matrix_world = frame_matrix(f, 2.78, 0.012)
    apply_transform(lv)
    tag(lv, atlas='sdb', room='sdb', collide=True, lit='lightmap', label='Lavabo')
    out.append(lv)
    mir, rim, halo = mirror_round()
    Mm = frame_matrix(f, 2.78, 0.012, 1.62)
    for o in (mir, rim, halo):
        o.matrix_world = Mm
        apply_transform(o)
    tag(mir, room='sdb', lit='mirror', collide=False)
    tag(rim, room='sdb', lit='probe', collide=False)
    tag(halo, room='sdb', lit='lamp', lamp_group='integre', collide=False)
    ld = bpy.data.lights.new('miroir_led', 'AREA')
    ld.shape = 'DISK'
    ld.size = 0.6
    ld.energy = 10.0
    ld.color = (1.0, 0.85, 0.65)
    lo = bpy.data.objects.new('miroir_led', ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.matrix_world = frame_matrix(f, 2.78, 0.02, 1.62) @ Matrix.Rotation(math.pi / 2, 4, 'X')
    tag(lo, room='sdb', lamp_group='integre')
    out += [mir, rim, halo, lo]
    # porte-serviettes sur la cloison en face, et anneau près du lavabo
    c = CLOISON
    rail = towel_rail(0.6, 2)
    tw = [towel(0.46, 0.5, 'serviette1')]
    tw2 = towel(0.40, 0.42, 'serviette2')
    tw2.matrix_world = Matrix.Translation((0.08, 0.0, -0.18))
    apply_transform(tw2)
    Mr = frame_matrix(c, 0.95, 0.012, 1.25)
    for o in rail + tw + [tw2]:
        o.matrix_world = Mr
        apply_transform(o)
    rj = join(rail, 'porte_serviettes')
    tag(rj, room='sdb', lit='probe', collide=False)
    towels = join(tw + [tw2], 'serviettes')
    tag(towels, atlas='sdb', room='sdb', lit='lightmap', collide=False)
    out += [rj, towels]
    # tapis de bain devant la douche
    mat = rug('tapis_bain', 0.50, 0.80, 'eponge', thick=0.012)
    mat.matrix_world = frame_matrix(f, SHOWER + 0.08, 0.45)
    apply_transform(mat)
    tag(mat, atlas='sdb', room='sdb', collide=False, lit='lightmap')
    out.append(mat)
    # spot saillant cylindrique au plafond
    cx, cz = f.pt(1.9, 0.68)
    spot = cylinder('spot_sdb', 0.045, H - 0.12, H, 40, 'metal_blanc', cx=cx, cy=-cz, bevel=0.003)
    lens = cylinder('spot_sdb_diff', 0.035, H - 0.123, H - 0.119, 40, 'plafonnier_diffuseur', cx=cx, cy=-cz)
    tag(spot, atlas='sdb', room='sdb', lit='lightmap', collide=False)
    tag(lens, room='sdb', lit='lamp', lamp_group='plafonnier', collide=False)
    ld = bpy.data.lights.new('spot_sdb_lum', 'SPOT')
    ld.energy = 30.0
    ld.spot_size = math.radians(100)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.03
    ld.color = (1.0, 0.9, 0.78)
    lo = bpy.data.objects.new('spot_sdb_lum', ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = P(cx, cz, H - 0.125)
    tag(lo, room='sdb', lamp_group='plafonnier')
    out += [spot, lens, lo]
    return out
