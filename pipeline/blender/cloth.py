"""Simulations de tissu (oreillers gonflés, couette drapée) avec Blender."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import CURRENT_COLL, bm_to_obj, material, uv_box


def _run(ob, frames):
    sc = bpy.context.scene
    sc.frame_start = 1
    sc.frame_end = frames
    for f in range(1, frames + 1):
        sc.frame_set(f)
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    ctx.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        if m.type == 'CLOTH':
            bpy.ops.object.modifier_apply(modifier=m.name)
    sc.frame_set(1)


def pillow(name, w, d, thick=0.03, cell=0.022, pressure=4.0, shrink=0.02, frames=24, mat=None, seed=0):
    """Oreiller : enveloppe fermée gonflée par pression (coutures sur le pourtour).
    Repère local : x largeur, y profondeur, z épaisseur, centré à l'origine."""
    nx, ny = max(2, int(round(w / cell))), max(2, int(round(d / cell)))
    verts, faces = [], []
    for zz in (thick / 2, -thick / 2):
        for j in range(ny + 1):
            for i in range(nx + 1):
                verts.append((-w / 2 + i * w / nx, -d / 2 + j * d / ny, zz))
    off = (nx + 1) * (ny + 1)
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))                 # dessus
            faces.append((off + a, off + a + nx + 1, off + a + nx + 2, off + a + 1))  # dessous
    # pourtour (anneau de bord commun aux deux nappes)
    ring = [(i, 0) for i in range(nx)] + [(nx, j) for j in range(ny)] + \
           [(i, ny) for i in range(nx, 0, -1)] + [(0, j) for j in range(ny, 0, -1)]
    idx = [j * (nx + 1) + i for i, j in ring]
    for k in range(len(idx)):
        a, b = idx[k], idx[(k + 1) % len(idx)]
        faces.append((a, off + a, off + b, b))
    from lib import mesh_obj
    ob = mesh_obj(name, verts, faces, mat)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    uv_box(ob)
    mod = ob.modifiers.new('cloth', 'CLOTH')
    s = mod.settings
    s.quality = 6
    s.mass = 0.3
    s.tension_stiffness = 12
    s.compression_stiffness = 12
    s.shear_stiffness = 6
    s.bending_stiffness = 0.4
    s.use_pressure = True
    s.uniform_pressure_force = pressure
    s.shrink_min = shrink
    s.effector_weights.gravity = 0.0
    s.use_sewing_springs = False
    mod.collision_settings.use_collision = False
    _run(ob, frames)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def add_collider(ob, thickness=0.004, friction=5.0):
    m = ob.modifiers.new('collision', 'COLLISION')
    ob.collision.thickness_outer = thickness
    ob.collision.cloth_friction = friction
    ob.collision.damping = 0.8
    return m


def remove_collider(ob):
    for m in list(ob.modifiers):
        if m.type == 'COLLISION':
            ob.modifiers.remove(m)


def drape(ob, frames=60, mass=0.5, bending=1.2, stiffness=15, pin_group=None, self_collision=False,
          distance=0.006, quality=8, air=1.0):
    mod = ob.modifiers.new('cloth', 'CLOTH')
    s = mod.settings
    s.quality = quality
    s.mass = mass
    s.air_damping = air
    s.tension_stiffness = stiffness
    s.compression_stiffness = stiffness
    s.shear_stiffness = stiffness * 0.5
    s.bending_stiffness = bending
    if pin_group:
        s.vertex_group_mass = pin_group
    c = mod.collision_settings
    c.use_collision = True
    c.distance_min = distance
    c.collision_quality = 4
    c.use_self_collision = self_collision
    if self_collision:
        c.self_distance_min = distance
    _run(ob, frames)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def grid(name, w, l, cell, mat=None, z=0.0):
    """Nappe rectangulaire (x : largeur, y : longueur), UV en mètres."""
    nx, ny = max(2, int(round(w / cell))), max(2, int(round(l / cell)))
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((i * w / nx, j * l / ny, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    from lib import mesh_obj
    ob = mesh_obj(name, verts, faces, mat)
    uvl = ob.data.uv_layers.new(name='UVMap')
    for li, lp in enumerate(ob.data.loops):
        co = ob.data.vertices[lp.vertex_index].co
        uvl.data[li].uv = (co.x, co.y)
    return ob, nx, ny
