"""
Outils communs pour la construction de la scène Blender.

Repères :
  plan (x, z)  : mètres, x vers la droite du plan, z vers le bas du plan
  Blender      : X = x, Y = -z, Z = hauteur
  glTF/three   : x = X, y = Z, z = -Y = z du plan  -> identique au plan.
"""
import json
import math
import os

import bmesh
import bpy
import mapbox_earcut as earcut
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'web', 'public', 'data')
TEX = os.path.join(ROOT, 'web', 'public', 'textures')

PLAN = json.load(open(os.path.join(DATA, 'plan.json')))
MATS = {k: v for k, v in json.load(open(os.path.join(DATA, 'materials.json'))).items() if not k.startswith('_')}
H = PLAN['ceiling_height']


def P(x, z, h=0.0):
    return Vector((x, -z, h))


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip('#')
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


# ------------------------------------------------------------------ scène
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.unit_settings.system = 'METRIC'
    return sc


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


CURRENT_COLL = None


def set_collection(name):
    global CURRENT_COLL
    CURRENT_COLL = coll(name)
    return CURRENT_COLL


# ------------------------------------------------------------------ matériaux
_tex_cache = {}


def _img(name, noncolor=False):
    key = (name, noncolor)
    if key in _tex_cache:
        return _tex_cache[key]
    path = os.path.join(TEX, name + '.webp')
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        im.colorspace_settings.name = 'Non-Color'
    _tex_cache[key] = im
    return im


def material(name):
    """Matériau Blender construit depuis materials.json (albédo fidèle pour
    les rebonds de lumière ; pas de carte normale pour le précalcul)."""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    spec = MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    col = hex_lin(spec.get('color', '#ffffff'))
    bsdf.inputs['Base Color'].default_value = (*col, 1)
    bsdf.inputs['Roughness'].default_value = spec.get('roughness', 0.5)
    bsdf.inputs['Metallic'].default_value = spec.get('metalness', 0.0)
    if spec.get('sheen'):
        bsdf.inputs['Sheen Weight'].default_value = spec['sheen'] * 0.5
    if spec.get('clearcoat'):
        bsdf.inputs['Coat Weight'].default_value = spec['clearcoat']
    if 'map' in spec:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = _img(spec['map'])
        tex.interpolation = 'Linear'
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        if spec.get('uv') == 'unit':
            nt.links.new(uvn.outputs['UV'], tex.inputs['Vector'])
        else:
            mp = nt.nodes.new('ShaderNodeMapping')
            s = 1.0 / spec.get('size', 1.0)
            mp.inputs['Scale'].default_value = (s, s, s)
            nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
            nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
        if spec.get('color', '#ffffff').lower() != '#ffffff':
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            nt.links.new(tex.outputs['Color'], mix.inputs['A'])
            mix.inputs['B'].default_value = (*col, 1)
            nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
        else:
            nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if spec.get('alphaTest'):
            nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    if spec.get('lit') == 'glass':
        bsdf.inputs['Transmission Weight'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.0
    m['lit'] = spec.get('lit', 'lightmap')
    return m


def emission_material(name, color_lin, strength):
    """Matériau émissif pour le précalcul (abat-jour allumé, fenêtres de la cour)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    bsdf.inputs['Emission Color'].default_value = (*color_lin, 1)
    bsdf.inputs['Emission Strength'].default_value = strength
    return m


# ------------------------------------------------------------------ maillages
def mesh_obj(name, verts, faces, mat=None, collection=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    (collection or CURRENT_COLL or bpy.context.scene.collection).objects.link(ob)
    if mat:
        ob.data.materials.append(material(mat) if isinstance(mat, str) else mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def bm_to_obj(bm, name, mat=None, collection=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or CURRENT_COLL or bpy.context.scene.collection).objects.link(ob)
    if mat:
        ob.data.materials.append(material(mat) if isinstance(mat, str) else mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def box(name, x0, y0, z0, x1, y1, z1, mat=None, bevel=0.0, seg=2, collection=None, grain='x', uv=True):
    """Pavé aligné (repère local), arêtes adoucies par un chanfrein arrondi."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0), (z0 + z1) / 2 + v.co.z * (z1 - z0)))
    if bevel > 0:
        bw = min(bevel, 0.49 * min(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bw, segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True)
    ob = bm_to_obj(bm, name, mat, collection)
    if bevel > 0:
        smooth_by_angle(ob, 35)
    if uv:
        uv_box(ob, grain=grain)
    return ob


def smooth_by_angle(ob, deg=35):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    # arêtes vives au-delà de l'angle
    bm = bmesh.new()
    bm.from_mesh(me)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            a = e.link_faces[0].normal.angle(e.link_faces[1].normal, 0)
            e.smooth = a < math.radians(deg)
        else:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True


def cylinder(name, r, z0, z1, segs=32, mat=None, cx=0.0, cy=0.0, cap=True, bevel=0.0, r_top=None, collection=None):
    bm = bmesh.new()
    rt = r if r_top is None else r_top
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r, radius2=rt, depth=z1 - z0)
    for v in bm.verts:
        v.co += Vector((cx, cy, (z0 + z1) / 2))
    if bevel > 0:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > 0.5]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=3, profile=0.5, affect='EDGES', clamp_overlap=True)
    ob = bm_to_obj(bm, name, mat, collection)
    smooth_by_angle(ob, 40)
    uv_cyl(ob, cx, cy)
    return ob


def lathe(name, profile, segs=48, mat=None, cx=0.0, cy=0.0, collection=None, close=True):
    """Solide de révolution : profile = [(rayon, z), ...] du bas vers le haut."""
    verts, faces = [], []
    n = len(profile)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ca, sa = math.cos(a), math.sin(a)
        for r, z in profile:
            verts.append((cx + r * ca, cy + r * sa, z))
    for i in range(segs):
        j = (i + 1) % segs
        for k in range(n - 1):
            a, b = i * n + k, j * n + k
            faces.append((a, b, b + 1, a + 1))
    ob = mesh_obj(name, verts, faces, mat, collection)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bm.to_mesh(ob.data)
    bm.free()
    smooth_by_angle(ob, 50)
    uv_cyl(ob, cx, cy)
    return ob


def tube(name, pts, r, segs=12, mat=None, closed=False, collection=None, caps=True):
    """Tube le long d'une polyligne 3D (garde-corps, piètements tubulaires)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    verts, faces = [], []
    prev_n = None
    for i, p in enumerate(pts):
        if closed:
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        elif i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == n - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = ((pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()).normalized()
        if prev_n is None:
            up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            nn = t.cross(up).normalized()
        else:
            nn = (prev_n - t * prev_n.dot(t)).normalized()
        bn = t.cross(nn).normalized()
        prev_n = nn
        for k in range(segs):
            a = 2 * math.pi * k / segs
            verts.append(p + (nn * math.cos(a) + bn * math.sin(a)) * r)
    rings = n if not closed else n
    for i in range(rings - (0 if closed else 1)):
        j = (i + 1) % n
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append((i * segs + k, i * segs + k2, j * segs + k2, j * segs + k))
    if caps and not closed:
        faces.append(tuple(range(segs))[::-1])
        faces.append(tuple(range((n - 1) * segs, n * segs)))
    ob = mesh_obj(name, verts, faces, mat, collection)
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    uv_box(ob)
    return ob


def extrude_poly(name, rings, z0, z1, mat=None, collection=None, top=True, bottom=False, sides=True):
    """Extrusion verticale d'un polygone (plan x, z) avec trous.
    rings = [exterieur, trou1, ...] en coordonnées plan."""
    verts, faces = [], []

    def add_ring_sides(ring):
        base = len(verts)
        m = len(ring)
        # orientation : normale sortante calculée à partir de l'aire signée
        area = sum(ring[i][0] * ring[(i + 1) % m][1] - ring[(i + 1) % m][0] * ring[i][1] for i in range(m))
        for x, z in ring:
            verts.append((x, -z, z0))
            verts.append((x, -z, z1))
        for i in range(m):
            j = (i + 1) % m
            a0, a1, b0, b1 = base + 2 * i, base + 2 * i + 1, base + 2 * j, base + 2 * j + 1
            faces.append((a0, a1, b1, b0) if area > 0 else (a0, b0, b1, a1))
        return area

    if sides:
        for k, ring in enumerate(rings):
            add_ring_sides(ring)
    tris = triangulate(rings)
    for zz, flip in ((z1, False), (z0, True)):
        if (zz == z1 and not top) or (zz == z0 and not bottom):
            continue
        base = len(verts)
        flat = [p for r in rings for p in r]
        for x, z in flat:
            verts.append((x, -z, zz))
        for t in tris:
            a, b, c = t
            faces.append((base + a, base + c, base + b) if not flip else (base + a, base + b, base + c))
    ob = mesh_obj(name, verts, faces, mat, collection)
    fix_normals_outward(ob)
    uv_box(ob)
    return ob


def triangulate(rings):
    """Triangulation (earcut) d'un polygone à trous, indices dans la liste aplatie."""
    flat = np.array([p for r in rings for p in r], dtype=np.float64)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    idx = earcut.triangulate_float64(flat, ends)
    tris = idx.reshape(-1, 3)
    out = []
    for a, b, c in tris:
        # orientation : face vers +Z en Blender (plan z inversé)
        pa, pb, pc = flat[a], flat[b], flat[c]
        cross = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        out.append((int(a), int(b), int(c)) if cross > 0 else (int(a), int(c), int(b)))
    return out


def flat_poly(name, rings, h, up=True, mat=None, collection=None):
    """Polygone horizontal à hauteur h (sol, plafond)."""
    flat = [p for r in rings for p in r]
    verts = [(x, -z, h) for x, z in flat]
    tris = triangulate(rings)
    faces = []
    for a, b, c in tris:
        # triangulate() renvoie des triangles orientés vers -Z Blender (car plan z inversé) ; on corrige
        faces.append((a, b, c))
    ob = mesh_obj(name, verts, faces, mat, collection)
    # oriente toutes les faces
    want = 1 if up else -1
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        f.normal_update()
        if f.normal.z * want < 0:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    uv_box(ob)
    return ob


def fix_normals_outward(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


# ------------------------------------------------------------------ UV
def uv_box(ob, grain='x', scale=1.0, layer='UVMap'):
    """Projection cubique en mètres (repère local de l'objet).
    grain : axe local le long duquel court le fil du bois (axe U de la texture)."""
    me = ob.data
    if layer not in me.uv_layers:
        me.uv_layers.new(name=layer)
    uvl = me.uv_layers[layer]
    ax = {'x': 0, 'y': 1, 'z': 2}[grain]
    for p in me.polygons:
        n = p.normal
        d = max(range(3), key=lambda i: abs(n[i]))
        others = [i for i in range(3) if i != d]
        if ax in others:
            u_ax, v_ax = ax, [i for i in others if i != ax][0]
        else:
            u_ax, v_ax = others
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (co[u_ax] * scale, co[v_ax] * scale)


def uv_cyl(ob, cx=0.0, cy=0.0, layer='UVMap'):
    me = ob.data
    if layer not in me.uv_layers:
        me.uv_layers.new(name=layer)
    uvl = me.uv_layers[layer]
    for p in me.polygons:
        n = p.normal
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7:
                uvl.data[li].uv = (co.x, co.y)
            else:
                r = math.hypot(co.x - cx, co.y - cy)
                a = math.atan2(co.y - cy, co.x - cx)
                uvl.data[li].uv = (a * max(r, 0.01), co.z)


def uv_unit(ob, axis_u='x', axis_v='z', layer='UVMap'):
    """UV 0-1 sur la boîte englobante (affiches, façades)."""
    me = ob.data
    if layer not in me.uv_layers:
        me.uv_layers.new(name=layer)
    uvl = me.uv_layers[layer]
    iu, iv = 'xyz'.index(axis_u[-1]), 'xyz'.index(axis_v[-1])
    su = -1 if axis_u.startswith('-') else 1
    sv = -1 if axis_v.startswith('-') else 1
    cs = [v.co for v in me.vertices]
    umin, umax = min(c[iu] * su for c in cs), max(c[iu] * su for c in cs)
    vmin, vmax = min(c[iv] * sv for c in cs), max(c[iv] * sv for c in cs)
    for li, l in enumerate(me.loops):
        c = me.vertices[l.vertex_index].co
        uvl.data[li].uv = ((c[iu] * su - umin) / max(1e-6, umax - umin), (c[iv] * sv - vmin) / max(1e-6, vmax - vmin))


# ------------------------------------------------------------------ assemblage
def join(objs, name):
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    ctx.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = ctx.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def place(ob, loc, rot_z=0.0):
    """loc en Blender (Vector) ; rot_z en radians autour de Z."""
    ob.matrix_world = Matrix.Translation(loc) @ Matrix.Rotation(rot_z, 4, 'Z') @ ob.matrix_world
    return ob


def apply_transform(ob):
    me = ob.data
    me.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)


def tag(ob, atlas=None, room=None, collide=None, lit=None, **kw):
    if atlas is not None:
        ob['atlas'] = atlas
    if room is not None:
        ob['room'] = room
    if collide is not None:
        ob['collide'] = collide
    if lit is not None:
        ob['lit'] = lit
    for k, v in kw.items():
        ob[k] = v
    return ob


# ------------------------------------------------------------------ repère mural
class WallFrame:
    """Repère local posé contre un mur : origine = a (plan), x le long du mur
    (a -> b), y vers l'intérieur de la pièce (perpendiculaire), z vertical.
    inside_pt : un point du plan situé dans la pièce pour choisir le côté."""

    def __init__(self, a, b, inside_pt):
        a, b = Vector((a[0], -a[1], 0)), Vector((b[0], -b[1], 0))
        ip = Vector((inside_pt[0], -inside_pt[1], 0))
        u = (b - a).normalized()
        perp = Vector((-u.y, u.x, 0))
        self.swapped = (ip - a).dot(perp) < 0
        if self.swapped:
            # repère direct obligatoire : l'origine passe à l'autre extrémité
            a, b = b, a
            u = -u
            perp = Vector((-u.y, u.x, 0))
        self.a, self.b, self.u, self.n = a, b, u, perp
        self.length = (b - a).length
        self.rot = math.atan2(u.y, u.x)

    def matrix(self, s=0.0, off=0.0, h=0.0):
        """Matrice monde pour un objet local placé à s (m) le long du mur,
        décollé de off (m) du mur."""
        loc = self.a + self.u * s + self.n * off + Vector((0, 0, h))
        return Matrix.Translation(loc) @ Matrix.Rotation(self.rot, 4, 'Z')

    def point(self, s, off=0.0):
        p = self.a + self.u * s + self.n * off
        return (p.x, -p.y)


def put(ob, M):
    ob.matrix_world = M @ ob.matrix_world
    return ob


def group_put(objs, M):
    for o in objs:
        if o is not None:
            put(o, M)
    return objs


def plan_pt(name):
    """Coordonnées plan (m) d'un sommet repéré en pixels du plan."""
    return (name[0] / PLAN['px_per_m'], name[1] / PLAN['px_per_m'])


def px(x, y):
    return (x / PLAN['px_per_m'], y / PLAN['px_per_m'])
