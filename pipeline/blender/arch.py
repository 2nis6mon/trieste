"""
Architecture : murs (bandes 2,5D découpées par les ouvertures), sols, plafonds,
plinthes, faïence de la salle de bain, fenêtres, portes, terrasse, façades.
Toute la géométrie vient de web/public/data/plan.json.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from shapely import set_precision
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box as sbox
from shapely.ops import unary_union

from lib import (PLAN, H, P, WallFrame, apply_transform, box, cylinder, extrude_poly, flat_poly, join,
                 material, mesh_obj, put, set_collection, smooth_by_angle, tag, triangulate, tube, uv_box, px)

PXM = PLAN['px_per_m']


def poly(coords):
    return Polygon(coords).buffer(0)


def geoms(g):
    if g.is_empty:
        return []
    if isinstance(g, (MultiPolygon,)):
        return list(g.geoms)
    if g.geom_type == 'GeometryCollection':
        return [x for x in g.geoms if x.geom_type == 'Polygon']
    return [g]


def rings_of(p):
    return [list(p.exterior.coords)[:-1]] + [list(h.coords)[:-1] for h in p.interiors]


WALLS = unary_union([poly(w['poly']) for w in PLAN['walls']])
OPEN = {o['id']: o for o in PLAN['openings']}
OPEN_POLY = {o['id']: poly(o['quad']) for o in PLAN['openings']}
ROOMS = {r['id']: poly(r['poly']) for r in PLAN['rooms']}
TERRACE = poly(PLAN['terrace']['poly'])
FLOOR = unary_union([Polygon(f['outer'], f['holes']) for f in PLAN['floor']]).buffer(0)

# Cour intérieure (côté des fenêtres) : zone depuis laquelle les faces
# extérieures des murs sont visibles.
COURTYARD = poly([px(640, 330), px(1700, 330), px(1700, 1750), px(599.5, 1750), px(599.5, 565), px(560, 565)])
VISIBLE = unary_union([FLOOR.buffer(0.005), TERRACE.buffer(0.3), COURTYARD] +
                      [p.buffer(0.02) for p in OPEN_POLY.values()])

DOOR_TYPES = ('door', 'door_entry', 'passage', 'door_glazed')


# ------------------------------------------------------------------ murs
def build_walls():
    """Murs en bandes horizontales. Dans chaque bande, la forme 2D est
    murs + ouvertures « pleines » à cette hauteur (allège sous l'appui,
    linteau au-dessus). Seules les faces visibles sont conservées."""
    cuts = {0.0, H}
    for o in PLAN['openings']:
        if o['sill'] > 0:
            cuts.add(round(o['sill'], 4))
        cuts.add(round(o['head'], 4))
    cuts = sorted(cuts)
    bands = []
    for h0, h1 in zip(cuts[:-1], cuts[1:]):
        parts = [WALLS]
        for oid, o in OPEN.items():
            if h1 <= o['sill'] + 1e-6 or h0 >= o['head'] - 1e-6:
                parts.append(OPEN_POLY[oid].buffer(0.0005, join_style=2))
        shape = set_precision(unary_union(parts).buffer(0), 1e-5)
        bands.append((h0, h1, shape))

    # sommets de toutes les bandes (pour supprimer les jonctions en T)
    all_pts = set()
    for _, _, s in bands:
        for p in geoms(s):
            for r in rings_of(p):
                for q in r:
                    all_pts.add((round(q[0], 5), round(q[1], 5)))
    all_pts = list(all_pts)

    def refine(ring):
        out = []
        m = len(ring)
        for i in range(m):
            a, b = ring[i], ring[(i + 1) % m]
            out.append(a)
            ax, az, bx, bz = a[0], a[1], b[0], b[1]
            L2 = (bx - ax) ** 2 + (bz - az) ** 2
            if L2 < 1e-10:
                continue
            ins = []
            for q in all_pts:
                t = ((q[0] - ax) * (bx - ax) + (q[1] - az) * (bz - az)) / L2
                if 1e-4 < t < 1 - 1e-4:
                    dx = ax + t * (bx - ax) - q[0]
                    dz = az + t * (bz - az) - q[1]
                    if dx * dx + dz * dz < 1e-9:
                        ins.append((t, q))
            for t, q in sorted(ins):
                out.append(q)
        return out

    verts, faces = [], []
    hidden_faces = []
    vidx = {}

    def V(x, z, h):
        k = (round(x, 5), round(z, 5), round(h, 5))
        if k not in vidx:
            vidx[k] = len(verts)
            verts.append((x, -z, h))
        return vidx[k]

    def visible(mx, mz, nx, nz):
        return VISIBLE.contains(Point(mx + nx * 0.03, mz + nz * 0.03))

    # les murs dépassent de 5 cm sous le sol et au-dessus du plafond :
    # aucune fente numérique à la jonction (fuites de lumière au précalcul)
    ext = lambda h: h
    for h0, h1, s in bands:
        h0, h1 = ext(h0), ext(h1)
        for p in geoms(s):
            for ri, ring in enumerate(rings_of(p)):
                ring = refine(ring)
                m = len(ring)
                area = sum(ring[i][0] * ring[(i + 1) % m][1] - ring[(i + 1) % m][0] * ring[i][1] for i in range(m))
                for i in range(m):
                    a, b = ring[i], ring[(i + 1) % m]
                    dx, dz = b[0] - a[0], b[1] - a[1]
                    L = math.hypot(dx, dz)
                    if L < 1e-5:
                        continue
                    # normale sortante (hors du solide) dans le plan (x, z) :
                    # test géométrique (valable pour contours extérieurs et trous)
                    nx, nz = dz / L, -dx / L
                    mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                    if p.buffer(-1e-6).contains(Point(mx + nx * 0.004, mz + nz * 0.004)):
                        nx, nz = -nx, -nz
                    f = [V(a[0], a[1], h0), V(b[0], b[1], h0), V(b[0], b[1], h1), V(a[0], a[1], h1)]
                    if not visible(mx, mz, nx, nz):
                        hidden_faces.append((f, (nx, -nz, 0.0)))
                        continue
                    faces.append((f, (nx, -nz, 0.0)))
    # faces horizontales : dessus d'allège, sous-face de linteau
    for (lo, hi) in zip(bands[:-1], bands[1:]):
        h = lo[1]
        top = lo[2].difference(hi[2])
        bot = hi[2].difference(lo[2])
        for g, up in ((top, True), (bot, False)):
            for p in geoms(set_precision(g, 1e-5)):
                if p.area < 1e-5:
                    continue
                rings = [refine(r) for r in rings_of(p)]
                tris = triangulate(rings)
                flat = [q for r in rings for q in r]
                for t in tris:
                    f = [V(flat[k][0], flat[k][1], h) for k in t]
                    faces.append((f, (0, 0, 1.0 if up else -1.0)))
    # orientation des faces selon la normale voulue
    fl = []
    for f, n in faces:
        a, b, c = (Vector(verts[f[0]]), Vector(verts[f[1]]), Vector(verts[f[2]]))
        fn = (b - a).cross(c - a)
        if fn.dot(Vector(n)) < 0:
            f = f[::-1]
        fl.append(f)
    # faces jamais visibles (côté voisins) : conservées pour le précalcul
    # uniquement, afin que les murs restent des volumes fermés
    hl = []
    for f, n in hidden_faces:
        a, b, c = (Vector(verts[f[0]]), Vector(verts[f[1]]), Vector(verts[f[2]]))
        if (b - a).cross(c - a).dot(Vector(n)) < 0:
            f = f[::-1]
        hl.append(f)
    hid = mesh_obj('murs_caches', verts, hl, 'enduit')
    tag(hid, lit='none', bake_only=True, collide=False)
    ob = mesh_obj('murs', verts, fl, 'enduit')
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges,
                             delimit={'NORMAL'})
    bm.to_mesh(ob.data)
    bm.free()
    uv_box(ob)
    # faces extérieures (sur cour) : enduit de façade
    ob.data.materials.append(material('enduit_ext'))
    for poly_ in ob.data.polygons:
        c = poly_.center
        n = poly_.normal
        if abs(n.z) < 0.5:
            pt = Point(c.x + n.x * 0.03, -(c.y + n.y * 0.03))
            if not FLOOR.buffer(0.01).contains(pt) and not any(q.buffer(0.03).contains(pt) for q in OPEN_POLY.values()):
                poly_.material_index = 1
    tag(ob, atlas='archi', room='all', collide=False, lit='lightmap')
    # faces de façade (enduit extérieur) -> objet séparé, atlas extérieur
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ext_faces = [f for f in bm.faces if f.material_index == 1]
    bm2 = bm.copy()
    bmesh.ops.delete(bm, geom=ext_faces, context='FACES')
    bm.to_mesh(ob.data)
    bm.free()
    bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.material_index != 1], context='FACES')
    me2 = bpy.data.meshes.new('murs_facade')
    bm2.to_mesh(me2)
    bm2.free()
    ob2 = bpy.data.objects.new('murs_facade', me2)
    ob.users_collection[0].objects.link(ob2)
    for m in ob.data.materials:
        me2.materials.append(m)
    tag(ob2, atlas='ext', room='exterieur', collide=False, lit='lightmap')
    return ob


# ------------------------------------------------------------------ sols / plafonds
FLOOR_PARTS = {
    'chambre': ['chambre'],
    'sdb': ['sdb'],
    'sas': ['sas', '@porte_sdb', '@porte_chambre'],
    'sejour': ['sejour', '@passage_sas'],
}


def floor_piece(rid):
    parts = []
    for k in FLOOR_PARTS[rid]:
        if k.startswith('@'):
            parts.append(OPEN_POLY[k[1:]].buffer(0.004, join_style=2))
        else:
            parts.append(ROOMS[k].buffer(0.004, join_style=2))
    g = unary_union(parts).buffer(0).difference(WALLS.buffer(-0.002)).buffer(0)
    # ne pas chevaucher les pièces voisines déjà attribuées
    return set_precision(g, 1e-5)


def build_floors_ceilings():
    """Sols et plafonds par pièce, prolongés de 4 cm sous les murs et dans les
    tableaux des ouvertures (aucun jour entre sol/plafond et murs)."""
    objs = []
    done = None
    under = unary_union([WALLS] + [OPEN_POLY[k] for k, o in OPEN.items()
                                   if o['type'] not in ('door', 'passage')]).buffer(0)
    for rid in ('sas', 'chambre', 'sdb', 'sejour'):
        g = floor_piece(rid)
        g = unary_union([g, g.buffer(0.04, join_style=2).intersection(under)]).buffer(0)
        if done is not None:
            g = g.difference(done).buffer(0)
        done = g if done is None else unary_union([done, g])
        for i, p in enumerate(geoms(g)):
            if p.area < 0.01:
                continue
            f = flat_poly(f'sol_{rid}_{i}', rings_of(p), 0.0, up=True, mat='parquet')
            tag(f, atlas='archi', room=rid, lit='lightmap', kind='sol')
            c = flat_poly(f'plafond_{rid}_{i}', rings_of(p), H, up=False, mat='plafond')
            tag(c, atlas='archi', room=rid, lit='lightmap', kind='plafond')
            objs += [f, c]
    # seuils des portes donnant sur l'extérieur / le palier
    for oid in ('porte_entree', 'porte_terrasse'):
        q = OPEN_POLY[oid]
        s = extrude_poly(f'seuil_{oid}', rings_of(q), -0.01 if oid == 'porte_entree' else -0.05, 0.012, mat='pierre_seuil')
        tag(s, atlas='archi', room='sejour', lit='lightmap')
        objs.append(s)
    return objs


# ------------------------------------------------------------------ plinthes
def build_skirting():
    objs = []
    cut = unary_union([OPEN_POLY[k].buffer(0.035, join_style=2) for k, o in OPEN.items() if o['type'] in DOOR_TYPES])
    for rid in ('chambre', 'sas', 'sejour'):
        g = floor_piece(rid)
        ring_zone = g.difference(g.buffer(-0.012, join_style=2)).difference(cut).buffer(0)
        for i, p in enumerate(geoms(set_precision(ring_zone, 1e-5))):
            if p.area < 1e-5:
                continue
            ob = extrude_poly(f'plinthe_{rid}_{i}', rings_of(p), 0.0, 0.07, mat='plinthe')
            tag(ob, atlas='archi', room=rid, lit='lightmap')
            objs.append(ob)
    return objs


# ------------------------------------------------------------------ faïence SdB
def build_bath_tiles():
    sdb = ROOMS['sdb']
    # axe long de la salle de bain : du SAS (porte) vers le fond (douche)
    a = Vector(px(201, 390))
    b = Vector(px(371, 170))
    u = (b - a).normalized()
    fond = max(Vector(c).dot(u) for c in sdb.exterior.coords)
    zone_douche = None
    pts = list(sdb.exterior.coords)
    # demi-plan « à moins de 0,95 m du mur du fond »
    far = [Vector(c) for c in pts]
    big = 30.0
    n = Vector((-u.y, u.x))
    base = a + u * (fond - 0.95)
    hp = Polygon([tuple(base - n * big), tuple(base + n * big), tuple(base + n * big + u * big), tuple(base - n * big + u * big)])
    door_cut = OPEN_POLY['porte_sdb'].buffer(0.02, join_style=2)
    layer = sdb.difference(sdb.buffer(-0.012, join_style=2)).difference(door_cut).buffer(0)
    zone = layer.intersection(hp).buffer(0)
    rest = layer.difference(hp).buffer(0)
    objs = []
    for i, p in enumerate(geoms(set_precision(rest, 1e-5))):
        if p.area > 1e-6:
            objs.append(extrude_poly(f'faience_{i}', rings_of(p), 0.0, 1.20, mat='carrelage'))
    for i, p in enumerate(geoms(set_precision(zone, 1e-5))):
        if p.area > 1e-6:
            objs.append(extrude_poly(f'faience_douche_{i}', rings_of(p), 0.0, 2.30, mat='carrelage'))
    ob = join(objs, 'faience')
    # UV : projection murale continue (joints alignés)
    uv_box(ob)
    tag(ob, atlas='archi', room='sdb', lit='lightmap')
    return ob, u, fond


# ------------------------------------------------------------------ fenêtres
def opening_frame(o):
    """Repère local d'une ouverture : x le long de A1->A2 (largeur),
    y de la face A vers la face B (épaisseur), z vertical."""
    a1, a2, b2, b1 = [tuple(c) for c in o['quad']]
    mid_b = ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2)
    wf = WallFrame(a1, a2, mid_b)
    return wf


def window(o):
    wf = opening_frame(o)
    W = wf.length
    T = o['thickness']
    d = o.get('frame_depth_from_A', 0.14)
    sill, head = o['sill'], o['head']
    leaves = o.get('leaves', 2)
    transom = o.get('transom', 0.0)
    glazed_door = o['type'] == 'door_glazed'
    parts, glass = [], []
    fw, fd = 0.068, 0.078  # dormant
    sw, sd = 0.062, 0.07   # ouvrant
    z0 = sill + (0.012 if glazed_door else 0.02)
    # tablette intérieure / seuil
    if not glazed_door:
        parts.append(box('tablette', -0.015, -0.025, sill - 0.012, W + 0.015, d + 0.01, sill + 0.02, 'tablette', bevel=0.004))
        parts.append(box('appui_ext', -0.02, d + fd - 0.01, sill - 0.05, W + 0.02, T + 0.05, sill - 0.01, 'pierre_seuil', bevel=0.004))
    # dormant
    y0, y1 = d, d + fd
    # le dormant pénètre de 2 cm dans les tableaux (couvre les écarts de vectorisation)
    parts += [box('dormant_g', -0.02, y0, z0, fw, y1, head + 0.02, 'menuiserie', bevel=0.004, grain='z'),
              box('dormant_d', W - fw, y0, z0, W + 0.02, y1, head + 0.02, 'menuiserie', bevel=0.004, grain='z'),
              box('dormant_h', fw, y0, head - fw, W - fw, y1, head + 0.02, 'menuiserie', bevel=0.004),
              box('dormant_b', fw, y0, z0, W - fw, y1, z0 + (0.03 if glazed_door else fw), 'menuiserie', bevel=0.004)]
    zt = head - transom if transom > 0 else None
    if zt:
        parts.append(box('traverse', fw, y0 + 0.001, zt - 0.035, W - fw, y1 - 0.001, zt + 0.035, 'menuiserie', bevel=0.004))

    def sash(x0, x1, za, zb, name, handle=None):
        ys0, ys1 = d - 0.004, d - 0.004 + sd
        ps = [box(name + '_g', x0, ys0, za, x0 + sw, ys1, zb, 'menuiserie', bevel=0.005, grain='z'),
              box(name + '_d', x1 - sw, ys0, za, x1, ys1, zb, 'menuiserie', bevel=0.005, grain='z'),
              box(name + '_h', x0 + sw, ys0, zb - sw, x1 - sw, ys1, zb, 'menuiserie', bevel=0.005),
              box(name + '_b', x0 + sw, ys0, za, x1 - sw, ys1, za + sw * (1.6 if glazed_door else 1.15), 'menuiserie', bevel=0.005)]
        # parclose (petit profil qui tient le vitrage)
        gi = 0.012
        zb0 = za + sw * (1.6 if glazed_door else 1.15)
        ps += [box(name + '_pg', x0 + sw, ys0 + 0.001, zb0, x0 + sw + gi, ys0 + 0.018, zb - sw, 'menuiserie'),
               box(name + '_pd', x1 - sw - gi, ys0 + 0.001, zb0, x1 - sw, ys0 + 0.018, zb - sw, 'menuiserie'),
               box(name + '_ph', x0 + sw + gi, ys0 + 0.001, zb - sw - gi, x1 - sw - gi, ys0 + 0.018, zb - sw, 'menuiserie'),
               box(name + '_pb', x0 + sw + gi, ys0 + 0.001, zb0, x1 - sw - gi, ys0 + 0.018, zb0 + gi, 'menuiserie')]
        gl = box(name + '_verre', x0 + sw - 0.004, ys0 + 0.03, zb0 - 0.004, x1 - sw + 0.004, ys0 + 0.036, zb - sw + 0.004, 'verre', uv=True)
        glass.append(gl)
        if handle is not None:
            hx, side = handle
            hz = za + min(1.05 - sill, (zb - za) * 0.5) if not glazed_door else 1.05
            base_ = box(name + '_pl', hx - 0.016, ys0 - 0.012, hz - 0.035, hx + 0.016, ys0, hz + 0.035, 'chrome', bevel=0.004)
            lever = box(name + '_poignee', hx - 0.011, ys0 - 0.045, hz - 0.11, hx + 0.011, ys0 - 0.025, hz + 0.008, 'chrome', bevel=0.006)
            stem = box(name + '_tige', hx - 0.008, ys0 - 0.03, hz - 0.008, hx + 0.008, ys0 - 0.01, hz + 0.008, 'chrome', bevel=0.003)
            ps += [base_, lever, stem]
        return ps

    zl0 = z0 + (0.03 if glazed_door else fw) - 0.002
    zl1 = (zt - 0.035 + 0.002) if zt else head - fw + 0.002
    inner0, inner1 = fw - 0.002, W - fw + 0.002
    lw = (inner1 - inner0) / leaves
    for k in range(leaves):
        xa, xb = inner0 + k * lw, inner0 + (k + 1) * lw
        h = None
        if leaves == 1:
            h = (xb - sw / 2 if not glazed_door else xa + sw / 2, 1)
        elif leaves == 2 and k == 1:
            h = (xa + sw / 2, -1)
        elif leaves == 3 and k == 1:
            h = (xb - sw / 2, 1)
        parts += sash(xa, xb, zl0, zl1, f'{o["id"]}_v{k}', h)
    if zt:
        parts += sash(inner0, inner1, zt + 0.035 - 0.002, head - fw + 0.002, f'{o["id"]}_imposte')
    M = wf.matrix()
    for p in parts + glass:
        put(p, M)
        apply_transform(p)
    fr = join(parts, f'fenetre_{o["id"]}')
    tag(fr, room=o['room'], lit='probe', collide=False)
    gl = join(glass, f'vitrage_{o["id"]}')
    tag(gl, room=o['room'], lit='glass', collide=False, bake_hide=True)
    return [fr, gl]


# ------------------------------------------------------------------ portes
def door(o):
    """Porte intérieure : habillage (chambranles), huisserie, vantail ouvert."""
    wf = opening_frame(o)
    W = wf.length
    T = o['thickness']
    head = o['head']
    parts = []
    lin = 0.018
    cw, ct = 0.07, 0.012
    # huisserie (couvre les tableaux)
    parts += [box('huis_g', 0, -0.002, 0, lin, T + 0.002, head, 'porte_blanche', grain='z'),
              box('huis_d', W - lin, -0.002, 0, W, T + 0.002, head, 'porte_blanche', grain='z'),
              box('huis_h', 0, -0.002, head - lin, W, T + 0.002, head, 'porte_blanche')]
    # chambranles des deux côtés
    for y0, y1 in ((-ct, 0.0), (T, T + ct)):
        parts += [box('ch_g', -cw + lin, y0, 0, lin, y1, head + cw - lin, 'porte_blanche', bevel=0.003, grain='z'),
                  box('ch_d', W - lin, y0, 0, W + cw - lin, y1, head + cw - lin, 'porte_blanche', bevel=0.003, grain='z'),
                  box('ch_h', -cw + lin, y0, head - lin, W + cw - lin, y1, head + cw - lin, 'porte_blanche', bevel=0.003)]
    M = wf.matrix()
    for p in parts:
        put(p, M)
        apply_transform(p)
    ob = join(parts, f'porte_{o["id"]}')
    tag(ob, room=o['room'], lit='probe', collide=False)
    out = [ob]
    if o['type'] == 'door':
        leaf = door_leaf(o, W, T, head, lin)
        tag(leaf, room=o['room'], lit='probe', collide=True)
        out.append(leaf)
    return out


def door_leaf(o, W, T, head, lin):
    """Vantail ouvert à 90° : calculé directement dans le repère du plan."""
    a1, a2, b2, b1 = [Vector(c) for c in o['quad']]
    hinge_a1 = o.get('hinge', 'A1') == 'A1'
    to_b = o.get('opens', 'B') == 'B'
    ja, jb = (a1, b1) if hinge_a1 else (a2, b2)       # tableau côté paumelles
    ka, kb = (a2, b2) if hinge_a1 else (a1, b1)       # tableau opposé
    across = ((ka + kb) / 2 - (ja + jb) / 2).normalized()
    face = jb if to_b else ja                          # face vers laquelle on ouvre
    other = ja if to_b else jb
    d_open = (face - other).normalized()
    th = 0.04
    lw = W - 2 * lin - 0.006
    lh = head - lin - 0.012
    piv = face + across * (lin + 0.004 + th / 2) - d_open * (th / 2 + 0.006)
    # repère local : x le long du vantail ouvert, y = épaisseur, z vertical
    parts = [box('vantail', 0, -th / 2, 0.008, lw, th / 2, 0.008 + lh, 'porte_blanche', bevel=0.004, grain='z')]
    hz = 1.05
    for sgn in (-1, 1):
        yy = sgn * th / 2
        parts.append(box('rosace', lw - 0.075, min(yy, yy + sgn * 0.01), hz - 0.025, lw - 0.035, max(yy, yy + sgn * 0.01), hz + 0.025, 'chrome', bevel=0.004))
        y2 = (yy + sgn * 0.045, yy + sgn * 0.063)
        parts.append(box('bequille', lw - 0.17, min(y2), hz - 0.009, lw - 0.045, max(y2), hz + 0.009, 'chrome', bevel=0.007))
        y3 = (yy, yy + sgn * 0.05)
        parts.append(box('carre', lw - 0.064, min(y3), hz - 0.008, lw - 0.047, max(y3), hz + 0.008, 'chrome'))
    leaf = join(parts, f'vantail_{o["id"]}')
    # plan (x, z) -> Blender (x, -z) : la direction d_open devient (dx, -dz)
    ang = math.atan2(-d_open.y, d_open.x)
    leaf.matrix_world = Matrix.Translation(P(piv.x, piv.y)) @ Matrix.Rotation(ang, 4, 'Z')
    apply_transform(leaf)
    return leaf


def entry_door(o):
    """Porte palière blindée : cadre anthracite, vantail blanc, fermée."""
    wf = opening_frame(o)
    W = wf.length
    T = o['thickness']
    head = o['head']
    parts = []
    fw = 0.06
    # cadre métallique (côté intérieur)
    parts += [box('cadre_g', 0, -0.02, 0, fw, T * 0.5, head, 'porte_blindee', bevel=0.003, grain='z'),
              box('cadre_d', W - fw, -0.02, 0, W, T * 0.5, head, 'porte_blindee', bevel=0.003, grain='z'),
              box('cadre_h', 0, -0.02, head - fw, W, T * 0.5, head, 'porte_blindee', bevel=0.003)]
    # couvre-joint intérieur
    parts += [box('cj_g', -0.06, -0.03, 0, 0.0, -0.018, head + 0.06, 'porte_blindee', bevel=0.003, grain='z'),
              box('cj_d', W, -0.03, 0, W + 0.06, -0.018, head + 0.06, 'porte_blindee', bevel=0.003, grain='z'),
              box('cj_h', -0.06, -0.03, head, W + 0.06, -0.018, head + 0.06, 'porte_blindee', bevel=0.003)]
    # vantail (panneau blanc lisse côté intérieur)
    parts.append(box('vantail', fw - 0.004, 0.0, 0.01, W - fw + 0.004, 0.07, head - fw + 0.004, 'porte_blanche', bevel=0.004, grain='z'))
    parts.append(box('joint', fw - 0.006, 0.0, 0.005, W - fw + 0.006, 0.066, 0.012, 'joint_noir'))
    # béquille, cylindre, judas
    hx = W - fw - 0.075
    parts += [box('plaque', hx - 0.03, -0.012, 0.9, hx + 0.03, 0.0, 1.2, 'chrome', bevel=0.006),
              box('bequille', hx - 0.14, -0.06, 1.1 - 0.01, hx + 0.005, -0.042, 1.1 + 0.01, 'chrome', bevel=0.008),
              box('tige', hx - 0.01, -0.045, 1.09, hx + 0.01, -0.01, 1.11, 'chrome'),
              cylinder('judas', 0.012, -0.01, 0.005, 16, 'chrome', cx=W / 2, cy=0.0)]
    parts[-1].matrix_world = Matrix.Translation((0, 0, 0))
    # le judas est un petit disque sur la face intérieure, à 1,55 m
    j = parts.pop()
    bpy.data.objects.remove(j)
    jd = cylinder('judas', 0.013, 0.0, 0.012, 20, 'chrome')
    jd.matrix_world = Matrix.Translation((W / 2, 0.0, 1.55)) @ Matrix.Rotation(math.pi / 2, 4, 'X')
    apply_transform(jd)
    parts.append(jd)
    M = wf.matrix()
    for p in parts:
        put(p, M)
        apply_transform(p)
    ob = join(parts, 'porte_entree')
    tag(ob, room='sejour', lit='probe', collide=False)
    return [ob]


# ------------------------------------------------------------------ terrasse
def build_terrace():
    objs = []
    t = TERRACE.difference(WALLS).buffer(0)
    for i, p in enumerate(geoms(set_precision(t, 1e-5))):
        s = extrude_poly(f'terrasse_{i}', rings_of(p), -0.26, -0.05, mat='terrasse', bottom=True)
        tag(s, atlas='ext', room='terrasse', lit='lightmap')
        objs.append(s)
    rail = PLAN['terrace']['railing']
    # prolonge légèrement le garde-corps jusqu'aux murs
    pts = [(x, z) for x, z in rail]
    top = 1.0 - 0.05
    path_top = [P(x, z, top) for x, z in pts]
    path_bot = [P(x, z, -0.05 + 0.1) for x, z in pts]
    parts = [tube('main_courante', path_top, 0.022, 16, 'garde_corps'),
             tube('lisse_basse', path_bot, 0.012, 10, 'garde_corps')]
    # barreaux tous les 11 cm
    ls = LineString(pts)
    n = int(ls.length / 0.11)
    for k in range(n + 1):
        q = ls.interpolate(k / n, normalized=True)
        parts.append(cylinder('barreau', 0.008, -0.05, top, 8, 'garde_corps', cx=q.x, cy=-q.y))
    rail_ob = join(parts, 'garde_corps')
    tag(rail_ob, atlas='ext', room='terrasse', lit='lightmap')
    objs.append(rail_ob)
    return objs


def build_slabs():
    """Dalles haute et basse + joints étanches mur/plafond et mur/sol
    (enveloppe fermée pour le précalcul, ni exportée ni « lightmappée »)."""
    foot = unary_union([WALLS, FLOOR] + list(OPEN_POLY.values())).buffer(0.02, join_style=2)
    objs = []
    top_shape = unary_union([WALLS] + list(OPEN_POLY.values())).buffer(0)
    low_shape = unary_union([WALLS] + [OPEN_POLY[k] for k, o in OPEN.items() if o['sill'] > 0]).buffer(0)
    for shape, z0, z1, nm in ():
        for i, p in enumerate(geoms(shape)):
            ob = extrude_poly(f'{nm}_{i}', rings_of(p), z0, z1, mat='enduit', bottom=True)
            tag(ob, lit='none', bake_only=True, collide=False)
            objs.append(ob)
    for p in geoms(foot):
        ring = [list(p.exterior.coords)[:-1]]
        for h, name in ((H + 0.04, 'dalle_haute'), (-0.04, 'dalle_basse')):
            ob = extrude_poly(name, ring, h - 0.02 if h > 0 else h - 0.02, h, mat='enduit', bottom=True)
            tag(ob, lit='none', bake_only=True, collide=False)
            objs.append(ob)
    return objs


def build_all():
    set_collection('architecture')
    objs = [build_walls()]
    objs += build_slabs()
    objs += build_floors_ceilings()
    objs += build_skirting()
    tiles, bath_u, bath_far = build_bath_tiles()
    objs.append(tiles)
    set_collection('menuiseries')
    for o in PLAN['openings']:
        if o['type'] in ('window', 'door_glazed'):
            objs += window(o)
        elif o['type'] == 'door_entry':
            objs += entry_door(o)
        else:
            objs += door(o)
    set_collection('terrasse')
    objs += build_terrace()
    return objs
