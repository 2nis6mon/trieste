"""
Extérieur : cour intérieure (plan cadastral : « cortile interno ») bordée
d'immeubles triestins, visible depuis les fenêtres. Géométrie estimée
(aucun relevé) : voir docs/DIMENSIONS.md.
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Vector
from shapely.geometry import Polygon
from shapely.ops import unary_union

from lib import MATS, PLAN, P, box, flat_poly, join, material, mesh_obj, px, set_collection, tag, TEX

MANIFEST = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'textures', 'manifest.json')))
GROUND = -16.5   # sol de la cour (5 étages x 3,30 m sous le plancher du 5e)

# Contour de la cour (pixels du plan) : A = angle NE de la terrasse, puis
# façade du voisin 824/36 (dans l'alignement du mur mitoyen), façade opposée,
# façade basse, et notre façade au droit du séjour.
A = px(664, 364)
B = px(1640, 1154)
C = px(1640, 1760)
D = px(599.5, 1760)
E = px(599.5, 832)

FACADES = [
    # (nom, p0, p1, matériau, hauteur du sommet)
    ('voisin_nord_est', A, B, 'facade_nord', 6.6),
    ('immeuble_en_face', B, C, 'facade_est', 6.6),
    ('immeuble_bas', C, D, 'facade_sud', 0.0),
    ('notre_immeuble', D, E, 'facade_ouest', 6.6),
]


def facade_plane(name, p0, p1, mat, top):
    """Plan vertical texturé (UV : u = abscisse / largeur du motif)."""
    spec = MANIFEST[mat]
    Wt, Ht = spec['size_m']
    a, b = P(*p0), P(*p1)
    L = (b - a).length
    verts = [(a.x, a.y, GROUND), (b.x, b.y, GROUND), (b.x, b.y, top), (a.x, a.y, top)]
    ob = mesh_obj(name, verts, [(0, 1, 2, 3)], mat)
    # orientation vers l'intérieur de la cour
    c = Vector(px(1100, 1300))
    cc = P(c.x, c.y)
    n = ob.data.polygons[0].normal
    mid = (a + b) / 2
    if n.dot(Vector((cc.x - mid.x, cc.y - mid.y, 0))) < 0:
        ob.data.polygons[0].flip()
    uvl = ob.data.uv_layers.new(name='UVMap')
    me = ob.data
    for li, l in enumerate(me.loops):
        v = me.vertices[l.vertex_index].co
        s = (Vector((v.x, v.y, 0)) - Vector((a.x, a.y, 0))).length
        uvl.data[li].uv = (s / Wt, (v.z - GROUND) / Ht)
    # corniche
    cor = box(name + '_corniche', 0, -0.35, -0.28, L, 0.0, 0.0, 'enduit_ext', bevel=0.03)
    d = (b - a).normalized()
    nrm = Vector(ob.data.polygons[0].normal)
    rot = math.atan2(d.y, d.x)
    from mathutils import Matrix
    M = Matrix.Translation(Vector((a.x, a.y, top))) @ Matrix.Rotation(rot, 4, 'Z')
    cor.matrix_world = M
    # la corniche doit déborder côté cour
    if Vector((-d.y, d.x, 0)).dot(nrm) > 0:
        cor.matrix_world = M @ Matrix.Scale(-1, 4, (0, 1, 0))
    return ob, cor


def build_all():
    set_collection('exterieur')
    objs = []
    for name, p0, p1, mat, top in FACADES:
        f, c = facade_plane(name, p0, p1, mat, top)
        tag(f, atlas='ext', room='exterieur', lit='lightmap')
        tag(c, atlas='ext', room='exterieur', lit='lightmap')
        objs += [f, c]
    # sol de la cour
    court = Polygon([A, B, C, D, E, px(599.5, 565), px(560, 480), px(600, 380)]).buffer(0)
    g = flat_poly('sol_cour', [list(court.exterior.coords)[:-1]], GROUND, up=True, mat='sol_cour')
    tag(g, atlas='ext', room='exterieur', lit='lightmap')
    objs.append(g)
    # notre façade sous la terrasse et sous le séjour (étages inférieurs)
    rail = PLAN['terrace']['railing']
    pts = [tuple(p) for p in rail] + [px(599.5, 565), px(599.5, 832)]
    verts, faces = [], []
    for i, (x, z) in enumerate(pts):
        verts += [(x, -z, GROUND), (x, -z, -0.26)]
    for i in range(len(pts) - 1):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    lower = mesh_obj('facade_inferieure', verts, faces, 'facade_ouest')
    uvl = lower.data.uv_layers.new(name='UVMap')
    Wt, Ht = MANIFEST['facade_ouest']['size_m']
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + math.dist(pts[i - 1], pts[i]))
    for li, l in enumerate(lower.data.loops):
        vi = l.vertex_index
        uvl.data[li].uv = (acc[vi // 2] / Wt, (lower.data.vertices[vi].co.z - GROUND) / Ht)
    # orienter vers la cour
    bm = bmesh.new()
    bm.from_mesh(lower.data)
    for f in bm.faces:
        cc = f.calc_center_median()
        if f.normal.x < 0:
            f.normal_flip()
    bm.to_mesh(lower.data)
    bm.free()
    tag(lower, atlas='ext', room='exterieur', lit='lightmap')
    objs.append(lower)
    # étage supérieur au-dessus de notre appartement (bandeau + mur)
    verts, faces = [], []
    upper_pts = [px(599.5, 832), px(599.5, 565)] + [tuple(p) for p in rail[::-1]]
    for i, (x, z) in enumerate(upper_pts):
        verts += [(x, -z, 2.70), (x, -z, 6.6)]
    for i in range(len(upper_pts) - 1):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    upper = mesh_obj('facade_superieure', verts, faces, 'facade_ouest')
    uvl = upper.data.uv_layers.new(name='UVMap')
    acc = [0.0]
    for i in range(1, len(upper_pts)):
        acc.append(acc[-1] + math.dist(upper_pts[i - 1], upper_pts[i]))
    for li, l in enumerate(upper.data.loops):
        vi = l.vertex_index
        uvl.data[li].uv = (acc[vi // 2] / Wt, (upper.data.vertices[vi].co.z - GROUND) / Ht)
    bm = bmesh.new()
    bm.from_mesh(upper.data)
    for f in bm.faces:
        if f.normal.x < 0:
            f.normal_flip()
    bm.to_mesh(upper.data)
    bm.free()
    tag(upper, atlas='ext', room='exterieur', lit='lightmap')
    objs.append(upper)
    return objs


def facade_night_emission():
    """Fenêtres éclairées la nuit : carte émissive sur les matériaux de façade."""
    for name in ('facade_nord', 'facade_est', 'facade_sud', 'facade_ouest'):
        m = material(name)
        nt = m.node_tree
        if nt.nodes.get('emit_tex'):
            continue
        bsdf = nt.nodes.get('Principled BSDF')
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.name = 'emit_tex'
        tex.image = bpy.data.images.load(os.path.join(TEX, MATS[name]['emissiveMap'] + '.webp'), check_existing=True)
        uvn = [n for n in nt.nodes if n.type == 'UVMAP'][0]
        nt.links.new(uvn.outputs['UV'], tex.inputs['Vector'])
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = 0.0
        m['night_emit'] = 2.0
