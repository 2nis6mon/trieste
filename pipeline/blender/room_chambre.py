"""
Chambre : lit IKEA MANDAL 160x200 (bouleau/blanc, 4 tiroirs), matelas,
parure motif NÅLBJÖRNBÄR (couette drapée par simulation, 2 oreillers gonflés),
2 coussins, 2 chevets NORDKISA (bambou 40x40x67), placard type PAX
250x248x60, tapis tricoté, 2 affiches, lampes champignon, plafonnier.
Implantation : pipeline/layout.py (contrôlée en 2D).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import layout as L  # noqa: E402

import cloth  # noqa: E402
from lib import (P, apply_transform, box, cylinder, join, lathe, material, mesh_obj, set_collection,  # noqa: E402
                 smooth_by_angle, tag, tube, uv_box, uv_unit, H)


def frame_matrix(fr, s, t, h=0.0):
    x, z = fr.pt(s, t)
    return Matrix.Translation(P(x, z, h)) @ Matrix.Rotation(fr.rot, 4, 'Z')


def place_all(objs, M):
    for o in objs:
        o.matrix_world = M @ o.matrix_world
        apply_transform(o)
    return objs


# ------------------------------------------------------------------ MANDAL
def mandal():
    """Cadre 160 x 202 x 27 cm. Local : x largeur, y de la tête (0) au pied, z."""
    W, Lg, Hh = 1.60, 2.02, 0.27
    t = 0.018
    p = []
    # socle en retrait (ombre portée sous le cadre)
    p.append(box('socle', 0.03, 0.03, 0.0, W - 0.03, Lg - 0.03, 0.02, 'blanc_caisson'))
    # panneaux de tête et de pied (bouleau)
    p.append(box('tete', 0, 0, 0.02, W, t, Hh, 'bouleau', bevel=0.002))
    p.append(box('pied', 0, Lg - t, 0.02, W, Lg, Hh, 'bouleau', bevel=0.002))
    for side, (x0, x1) in (('g', (0, t)), ('d', (W - t, W))):
        # cadre bouleau autour des deux tiroirs
        p.append(box('rail_haut_' + side, x0, t, Hh - 0.03, x1, Lg - t, Hh, 'bouleau', bevel=0.002))
        p.append(box('rail_bas_' + side, x0, t, 0.02, x1, Lg - t, 0.042, 'bouleau', bevel=0.002))
        p.append(box('montant_m_' + side, x0, Lg / 2 - 0.022, 0.042, x1, Lg / 2 + 0.022, Hh - 0.03, 'bouleau', bevel=0.002, grain='z'))
        p.append(box('montant_a_' + side, x0, t, 0.042, x1, t + 0.045, Hh - 0.03, 'bouleau', bevel=0.002, grain='z'))
        p.append(box('montant_b_' + side, x0, Lg - t - 0.045, 0.042, x1, Lg - t, Hh - 0.03, 'bouleau', bevel=0.002, grain='z'))
        # façades de tiroir blanches, légèrement en retrait, jeu de 3 mm
        xs = (x0 + 0.002, x1 + 0.002) if side == 'g' else (x0 - 0.002, x1 - 0.002)
        for k, (y0, y1) in enumerate(((t + 0.048, Lg / 2 - 0.025), (Lg / 2 + 0.025, Lg - t - 0.048))):
            p.append(box(f'tiroir_{side}{k}', xs[0], y0, 0.045, xs[1], y1, Hh - 0.033, 'blanc_meuble', bevel=0.0025))
            # prise de main : fente sous le rail haut (ombre)
            gx = (x0 - 0.001, x0 + 0.004) if side == 'g' else (x1 - 0.004, x1 + 0.001)
    # traverse centrale + lattes (visibles par les côtés)
    p.append(box('traverse', W / 2 - 0.03, t, 0.2, W / 2 + 0.03, Lg - t, 0.245, 'bouleau'))
    return join(p, 'mandal')


def mattress():
    W, Lg = 1.60, 2.00
    z0, z1 = 0.255, 0.455
    m = box('matelas', 0, 0.01, z0, W, 0.01 + Lg, z1, 'drap', bevel=0.035, seg=4)
    # passepoil (couture) en haut et en bas
    r = 0.035
    parts = [m]
    for zz in (z1 - 0.012, z0 + 0.012):
        pts = []
        for cx, cy, a0 in ((W - r, 0.01 + r, -90), (W - r, 0.01 + Lg - r, 0), (r, 0.01 + Lg - r, 90), (r, 0.01 + r, 180)):
            for k in range(7):
                a = math.radians(a0 + k * 15)
                pts.append((cx + (r - 0.002) * math.cos(a), cy + (r - 0.002) * math.sin(a), zz))
        parts.append(tube('passepoil', pts, 0.0045, 8, 'drap', closed=True))
    return join(parts, 'matelas')


# ------------------------------------------------------------------ textiles
def pillows_and_duvet(bed_objs):
    """Oreillers gonflés (pression), couette drapée (côtés et pied), coussins."""
    mat_ob, frame_ob = bed_objs
    floor = box('sol_sim', -2, -2, -0.05, 4, 5, 0.0, 'enduit', uv=False)
    wall = box('mur_sim', -1, -0.3, 0, 2.6, 0.0, 1.6, 'enduit', uv=False)
    for o in (floor, wall, frame_ob, mat_ob):
        cloth.add_collider(o, 0.004, friction=40)
    # oreillers 65 x 65
    pillows = []
    for i, x in enumerate((0.43, 1.17)):
        pl = cloth.pillow(f'oreiller_{i}', 0.60, 0.60, thick=0.07, cell=0.02, pressure=3.0, shrink=0.0, frames=30, mat='parure', bending=3.0)
        pl.matrix_world = (Matrix.Translation((x, 0.17, 0.455 + 0.29)) @ Matrix.Rotation(math.radians(-66 + 4 * i), 4, 'X')
                           @ Matrix.Rotation(math.radians(2 - 4 * i), 4, 'Y') @ Matrix.Scale(0.82, 4, (0, 0, 1)))
        apply_transform(pl)
        pillows.append(pl)
    # couette 220 x 210, bord haut à 42 cm de la tête
    duv, nx, ny = cloth.grid('couette', 2.2, 2.05, 0.03, 'parure', z=0.47)
    duv.matrix_world = Matrix.Translation((-0.30, 0.48, 0))
    apply_transform(duv)
    vg = duv.vertex_groups.new(name='epingle')
    ids = [v.index for v in duv.data.vertices if 0.08 < v.co.x < 1.52 and 0.56 < v.co.y < 1.9]
    vg.add(ids, 1.0, 'REPLACE')
    # transition douce de l'épinglage
    for v in duv.data.vertices:
        dx = min(v.co.x - 0.08, 1.52 - v.co.x)
        dy = min(v.co.y - 0.56, 1.9 - v.co.y)
        d = min(dx, dy)
        if -0.12 < d <= 0:
            vg.add([v.index], 1.0 + d / 0.12, 'REPLACE')
    cloth.drape(duv, frames=70, mass=0.55, bending=4.0, stiffness=18, pin_group='epingle', distance=0.012, quality=5)
    print('  couette : sommets réparés', cloth.repair(duv, 0.03, zmin=0.02))
    # volume : lissage des plis de simulation, épaisseur 3,5 cm vers le bas, subdivision
    sm = duv.modifiers.new('lisse', 'SMOOTH')
    sm.factor = 0.6
    sm.iterations = 6
    so = duv.modifiers.new('ep', 'SOLIDIFY')
    so.thickness = 0.035
    so.offset = -1
    so.use_rim = True
    so.use_even_offset = False
    sub = duv.modifiers.new('sub', 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    _apply_mods(duv)
    # légère bouffance (moelleux de la couette)
    import random
    rnd = random.Random(3)
    bump = [(rnd.uniform(0, 1.6), rnd.uniform(0.4, 2.4), rnd.uniform(0.15, 0.35), rnd.uniform(-0.008, 0.012)) for _ in range(40)]
    for v in duv.data.vertices:
        if v.normal.z > 0.6:
            dz = sum(a * math.exp(-((v.co.x - bx) ** 2 + (v.co.y - by) ** 2) / (2 * r * r)) for bx, by, r, a in bump)
            v.co.z += dz
    for pp in duv.data.polygons:
        pp.use_smooth = True
    # coussins déco posés devant les oreillers
    cushions = []
    for i, (x, m) in enumerate(((0.55, 'coussin_sauge'), (1.05, 'coussin_terracotta'))):
        c = cloth.pillow(f'coussin_{i}', 0.42, 0.42, thick=0.06, cell=0.018, pressure=3.2, frames=28, mat=m, bending=3.0)
        c.matrix_world = (Matrix.Translation((x, 0.40, 0.49 + 0.20)) @ Matrix.Rotation(math.radians(-72 + 8 * i), 4, 'X')
                          @ Matrix.Rotation(math.radians(-8 + 18 * i), 4, 'Z') @ Matrix.Scale(0.85, 4, (0, 0, 1)))
        apply_transform(c)
        cushions.append(c)
    for o in (floor, wall):
        bpy.data.objects.remove(o)
    for o in (frame_ob, mat_ob):
        cloth.remove_collider(o)
    return pillows, duv, cushions


def _apply_mods(ob):
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    ctx.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


# ------------------------------------------------------------------ NORDKISA
def nordkisa():
    """Chevet 40 x 40 x 67 : plateau, tiroir, niche ouverte, tablette basse,
    4 pieds. Local : x largeur, y profondeur (0 = côté mur), z."""
    W, D, Hh = 0.40, 0.40, 0.67
    p = []
    lg = 0.032
    for x0 in (0.0, W - lg):
        for y0 in (0.0, D - lg):
            p.append(box('pied', x0, y0, 0, x0 + lg, y0 + lg, Hh - 0.02, 'bambou', bevel=0.003, grain='z'))
    p.append(box('plateau', -0.004, -0.004, Hh - 0.02, W + 0.004, D + 0.004, Hh, 'bambou', bevel=0.004))
    # caisson du tiroir
    p.append(box('caisson', lg, lg, Hh - 0.17, W - lg, D - lg, Hh - 0.02, 'bambou'))
    p.append(box('facade', lg + 0.002, D - lg, Hh - 0.165, W - lg - 0.002, D - 0.012, Hh - 0.028, 'bambou', bevel=0.002))
    # prise de main : bouton bambou
    b = cylinder('bouton', 0.012, 0, 0.018, 20, 'bambou', bevel=0.003)
    b.matrix_world = Matrix.Translation((W / 2, D - 0.012, Hh - 0.097)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    apply_transform(b)
    p.append(b)
    p.append(box('tablette_mi', lg, lg, 0.30, W - lg, D - lg, 0.318, 'bambou'))
    p.append(box('tablette_basse', lg, lg, 0.08, W - lg, D - lg, 0.098, 'bambou'))
    p.append(box('fond', lg, 0.004, 0.098, W - lg, 0.012, Hh - 0.17, 'bambou', grain='z'))
    return join(p, 'nordkisa')


def mushroom_lamp(name):
    """Lampe champignon (opaline) ; retourne (corps, abat-jour, lumière)."""
    base = lathe(name + '_pied', [(0, 0), (0.065, 0), (0.07, 0.006), (0.066, 0.016), (0.014, 0.022),
                                  (0.012, 0.21), (0.0, 0.21)], 40, 'lampe_opale')
    shade = lathe(name + '_dome', [(0.004, 0.205), (0.11, 0.205), (0.112, 0.212), (0.105, 0.245),
                                   (0.085, 0.275), (0.05, 0.294), (0.0, 0.30)], 48, 'lampe_opale')
    ld = bpy.data.lights.new(name + '_lum', 'POINT')
    ld.energy = 9.0
    ld.shadow_soft_size = 0.035
    ld.color = (1.0, 0.78, 0.52)
    lo = bpy.data.objects.new(name + '_lum', ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (0, 0, 0.19)
    return base, shade, lo


def ceiling_light(name, pos_plan, room):
    """Plafonnier rond Ø 35 cm (anneau blanc, diffuseur opale) + source surfacique."""
    x, z = pos_plan
    body = cylinder(name + '_corps', 0.175, H - 0.075, H, 64, 'metal_blanc', bevel=0.006)
    diff = cylinder(name + '_diff', 0.165, H - 0.082, H - 0.07, 64, 'plafonnier_diffuseur', bevel=0.004)
    for o in (body, diff):
        o.matrix_world = Matrix.Translation(P(x, z))
        apply_transform(o)
    ld = bpy.data.lights.new(name + '_lum', 'AREA')
    ld.shape = 'DISK'
    ld.size = 0.30
    ld.energy = 55.0
    ld.color = (1.0, 0.88, 0.72)
    lo = bpy.data.objects.new(name + '_lum', ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = P(x, z, H - 0.085)
    tag(body, atlas=room, room=room, lit='lightmap', collide=False)
    tag(diff, room=room, lit='lamp', lamp_group='plafonnier', collide=False)
    tag(lo, room=room, lamp_group='plafonnier')
    diff_mat_emission('plafonnier_diffuseur', (1.0, 0.9, 0.78), 6.0)
    return [body, diff, lo]


def diff_mat_emission(mname, col, strength):
    m = material(mname)
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Emission Color'].default_value = (*col, 1)
    bsdf.inputs['Emission Strength'].default_value = 0.0
    m['emit_strength'] = strength


# ------------------------------------------------------------------ PAX
def pax(width_modules=(1.0, 1.0, 0.5), H_tot=2.48, D=0.60, hinges=None, name='pax'):
    """Placard type PAX : caissons 236 cm + joue haute jusqu'à 248 cm,
    portes FORSAND blanches 229 cm, poignées barres inox verticales.
    Local : x le long du mur, y vers la pièce (façade en y = D), z."""
    Wt = sum(width_modules)
    p = []
    p.append(box('caisson', 0, 0.0, 0, Wt, D - 0.02, 2.36, 'blanc_caisson', bevel=0.002))
    p.append(box('bandeau', 0, 0.0, 2.36, Wt, D, H_tot, 'blanc_meuble', bevel=0.002))
    p.append(box('plinthe', 0.01, 0.0, 0, Wt - 0.01, D - 0.03, 0.022, 'blanc_caisson'))
    doors = []
    x = 0.0
    for w in width_modules:
        n = 2 if w > 0.75 else 1
        for k in range(n):
            doors.append((x + k * w / n, x + (k + 1) * w / n))
        x += w
    if hinges is None:
        hinges = []
        for i, (a, b) in enumerate(doors):
            hinges.append('L' if i % 2 == 0 else 'R')
    for i, ((a, b), hg) in enumerate(zip(doors, hinges)):
        p.append(box(f'porte_{i}', a + 0.0015, D - 0.02, 0.025, b - 0.0015, D, 2.319, 'blanc_meuble', bevel=0.0015, grain='z'))
        hx = b - 0.045 if hg == 'L' else a + 0.045
        # poignée barre Ø 12 mm, 32 cm, sur plots
        bar = cylinder('barre', 0.006, 0.97, 1.33, 16, 'inox')
        bar.matrix_world = Matrix.Translation((hx, D + 0.034, 0))
        apply_transform(bar)
        p.append(bar)
        for zz in (1.0, 1.30):
            st = cylinder('plot', 0.005, 0, 0.034, 12, 'inox')
            st.matrix_world = Matrix.Translation((hx, D, zz)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
            apply_transform(st)
            p.append(st)
    return join(p, name)


# ------------------------------------------------------------------ déco
def rug(name, w, l, mat, thick=0.014):
    r = box(name, 0, 0, 0.001, w, l, thick, mat, bevel=0.006, seg=3)
    return r


def poster_frame(name, w, h, art, depth=0.025, border=0.022, mat_w=0.05):
    """Cadre chêne + passe-partout + affiche. Local : x largeur, y = épaisseur
    (dos contre le mur en y=0), z hauteur (centre en 0)."""
    p = []
    b = border
    p += [box('c_g', -w / 2, 0, -h / 2, -w / 2 + b, depth, h / 2, 'cadre_chene', bevel=0.002, grain='z'),
          box('c_d', w / 2 - b, 0, -h / 2, w / 2, depth, h / 2, 'cadre_chene', bevel=0.002, grain='z'),
          box('c_h', -w / 2 + b, 0, h / 2 - b, w / 2 - b, depth, h / 2, 'cadre_chene', bevel=0.002),
          box('c_b', -w / 2 + b, 0, -h / 2, w / 2 - b, depth, -h / 2 + b, 'cadre_chene', bevel=0.002)]
    p.append(box('pp', -w / 2 + b, 0.004, -h / 2 + b, w / 2 - b, depth - 0.008, h / 2 - b, 'passe_partout'))
    iw, ih = w / 2 - b - mat_w, h / 2 - b - mat_w
    art_ob = mesh_obj('affiche', [(-iw, depth - 0.0075, -ih), (iw, depth - 0.0075, -ih), (iw, depth - 0.0075, ih), (-iw, depth - 0.0075, ih)],
                      [(0, 3, 2, 1)], art)
    uv_unit(art_ob, 'x', 'z')
    p.append(art_ob)
    return join(p, name)


def vase_eucalyptus(name, seed=1):
    import random
    rnd = random.Random(seed)
    vase = lathe(name + '_vase', [(0, 0), (0.035, 0), (0.042, 0.03), (0.04, 0.09), (0.022, 0.13), (0.02, 0.145),
                                  (0.017, 0.145), (0.018, 0.13), (0.0, 0.13)], 32, 'gres')
    stems, leaves = [], []
    leaf_uv = (0.25, 0.5, 0.5, 1.0)  # cellule « euca » de l'atlas feuilles
    for k in range(7):
        a = rnd.uniform(0, 2 * math.pi)
        tilt = rnd.uniform(0.12, 0.45)
        Lh = rnd.uniform(0.22, 0.34)
        pts = []
        for i in range(8):
            t = i / 7
            pts.append((math.cos(a) * tilt * Lh * t * t * 1.4, math.sin(a) * tilt * Lh * t * t * 1.4, 0.10 + Lh * t))
        stems.append(tube('tige', pts, 0.0018, 5, 'tige', caps=False))
        for i in range(2, 8):
            px_, py_, pz_ = pts[i]
            for sgn in (-1, 1):
                sz = rnd.uniform(0.022, 0.032)
                ang = a + sgn * 1.4 + rnd.uniform(-0.3, 0.3)
                cx, cy = px_ + math.cos(ang) * sz * 0.6, py_ + math.sin(ang) * sz * 0.6
                dx, dy = math.cos(ang) * sz * 0.5, math.sin(ang) * sz * 0.5
                ex, ey = -math.sin(ang) * sz * 0.5, math.cos(ang) * sz * 0.5
                dz = rnd.uniform(-0.01, 0.01)
                vs = [(cx - dx - ex * 0.2, cy - dy - ey * 0.2, pz_ - 0.004), (cx + dx, cy + dy, pz_ + dz - 0.004),
                      (cx + dx + ex * 0.4, cy + dy + ey * 0.4, pz_ + dz + sz * 0.9), (cx - dx, cy - dy, pz_ + sz * 0.9)]
                lf = mesh_obj('feuille', vs, [(0, 1, 2, 3)], 'feuillage')
                uvl = lf.data.uv_layers.new(name='UVMap')
                u0, v0, u1, v1 = leaf_uv
                for li, uv in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                    uvl.data[li].uv = uv
                leaves.append(lf)
    plant = join(stems + leaves, name + '_feuillage')
    return vase, plant


def books(name):
    p = [box('livre1', 0, 0, 0, 0.16, 0.23, 0.028, 'livre_sauge', bevel=0.002),
         box('livre2', 0.01, 0.005, 0.028, 0.155, 0.215, 0.048, 'livre_beige', bevel=0.002)]
    return join(p, name)


# ------------------------------------------------------------------ assemblage
def build():
    set_collection('chambre')
    C = L.CHAMBRE
    out = []
    # --- lit
    fr = C['lit']['frame']
    M_bed = frame_matrix(fr, C['lit']['s0'], C['lit']['t0'])
    frame_ob = mandal()
    mat_ob = mattress()
    pillows, duv, cushions = pillows_and_duvet((mat_ob, frame_ob))
    bed_objs = [frame_ob, mat_ob, duv] + pillows + cushions
    place_all(bed_objs, M_bed)
    tag(frame_ob, atlas='chambre', room='chambre', collide=True, lit='lightmap', label='Lit MANDAL 160x200')
    for o in [mat_ob, duv] + pillows + cushions:
        tag(o, atlas='chambre', room='chambre', collide=False, lit='lightmap')
    for o in [duv] + pillows + cushions:
        o['lm_from_uv0'] = True
    out += bed_objs
    # --- chevets + lampes + déco
    for key, deco in (('chevet_1', 'plante'), ('chevet_2', 'livres')):
        c = C[key]
        M = frame_matrix(c['frame'], c['s0'], c['t0'])
        ns = nordkisa()
        place_all([ns], M)
        tag(ns, atlas='chambre', room='chambre', collide=True, lit='lightmap', label='Chevet NORDKISA')
        body, shade, light = mushroom_lamp('lampe_' + key)
        for o in (body, shade):
            o.matrix_world = M @ Matrix.Translation((0.2 if key == 'chevet_2' else 0.13, 0.2, 0.67))
            apply_transform(o)
        light.matrix_world = M @ Matrix.Translation((0.2 if key == 'chevet_2' else 0.13, 0.2, 0.67)) @ light.matrix_world
        tag(body, atlas='chambre', room='chambre', lit='lightmap', collide=False)
        tag(shade, room='chambre', lit='lamp', lamp_group='appoint', collide=False)
        tag(light, room='chambre', lamp_group='appoint')
        out += [ns, body, shade, light]
        if deco == 'plante':
            vase, plant = vase_eucalyptus('eucalyptus')
            for o in (vase, plant):
                o.matrix_world = M @ Matrix.Translation((0.31, 0.24, 0.67))
                apply_transform(o)
                tag(o, room='chambre', lit='probe', collide=False)
            out += [vase, plant]
        else:
            bk = books('livres')
            bk.matrix_world = M @ Matrix.Translation((0.06, 0.03, 0.67)) @ Matrix.Rotation(0.12, 4, 'Z')
            apply_transform(bk)
            tag(bk, atlas='chambre', room='chambre', lit='lightmap', collide=False)
            out.append(bk)
    diff_mat_emission('lampe_opale', (1.0, 0.82, 0.62), 4.0)
    # --- placard
    c = C['pax']
    M = frame_matrix(c['frame'], c['s0'], c['t0'])
    px_ = pax((1.0, 1.0, 0.5), hinges=['L', 'R', 'L', 'R', 'L'], name='pax_chambre')
    # module de 50 cm côté cloison, paumelles côté opposé à la cloison (débattement libre)
    place_all([px_], M)
    tag(px_, atlas='chambre', room='chambre', collide=True, lit='lightmap', label='Placard type PAX 250x248x60')
    out.append(px_)
    # --- tapis
    c = C['tapis']
    rg = rug('tapis_chambre', c['s1'] - c['s0'], c['t1'] - c['t0'], 'tapis_chambre')
    place_all([rg], frame_matrix(c['frame'], c['s0'], c['t0']))
    tag(rg, atlas='chambre', room='chambre', collide=False, lit='lightmap')
    out.append(rg)
    # --- affiches au-dessus du lit
    fr = L.CH_CLOISON
    bc = C['lit']['s0'] + 0.80
    for i, (ds, art) in enumerate(((-0.26, 'affiche_feuille'), (0.26, 'affiche_arche'))):
        pf = poster_frame(f'affiche_ch_{i}', 0.40, 0.50, art)
        pf.matrix_world = frame_matrix(fr, bc + ds, 0.0, 1.32)
        apply_transform(pf)
        tag(pf, atlas='chambre', room='chambre', collide=False, lit='lightmap')
        out.append(pf)
    # --- plafonnier au centre de la pièce
    from shapely.geometry import Polygon
    room = Polygon([r for r in L.PLAN['rooms'] if r['id'] == 'chambre'][0]['poly'])
    cpt = room.centroid
    out += ceiling_light('plafonnier_chambre', (cpt.x, cpt.y), 'chambre')
    return out
