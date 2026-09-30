"""Perce le plan de travail au droit de l'évier (cuve encastrée visible), puis
exporte la maquette. Usage : python percer_evier.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from build import CACHE  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
wt = bpy.data.objects['plan_de_travail']
ev = bpy.data.objects['evier']
cs = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
cx = sum(c.x for c in cs) / 8
cy = sum(c.y for c in cs) / 8
zt = max(c.z for c in cs)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.214, depth=0.2, location=(cx, cy, zt))
cut = bpy.context.active_object
# caisson sous évier : on dégage la place de la cuve (Ø 42, profondeur 18 cm)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.214, depth=0.42, location=(cx, cy, zt - 0.1))
cut2 = bpy.context.active_object
for ob, c in ((wt, cut), (bpy.data.objects['evier_meuble'], cut2)):
    m = ob.modifiers.new('trou_evier', 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.object = c
    m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=m.name)
bpy.data.objects.remove(cut)
bpy.data.objects.remove(cut2)
print('trou percé', round(cx, 3), round(cy, 3), round(zt, 3), len(wt.data.polygons), 'faces')
bpy.ops.wm.save_mainfile()
import export  # noqa: E402
export.export()
