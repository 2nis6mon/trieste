"""Sépare des murs les tableaux des ouvertures (joues, linteaux, appuis dans
l'épaisseur du mur) : ils passent en éclairage temps réel dans la visite
(le précalcul y laissait des marbrures). Puis exporte la maquette.
Usage : python separer_tableaux.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402

from build import CACHE  # noqa: E402
from lib import PLAN  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
rooms = [(r['id'], Polygon(r['poly'])) for r in PLAN['rooms']]
murs = bpy.data.objects['murs']
total = 0
for op in PLAN['openings']:
    q = Polygon(op['quad']).buffer(0.015)
    name = 'tableau_' + op['id']
    if name in bpy.data.objects:  # déjà séparé (fichier de précalcul réutilisé) : murs de niche seulement
        name = 'niche_' + op['id']
        if name in bpy.data.objects:
            continue
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = murs
    murs.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(murs.data)
    n = 0
    # direction du mur (plan) : joues et murs de niche lui sont parallèles
    (ax, az), (bx, bz) = op['quad'][0], op['quad'][1]
    L = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
    ux, uz = (bx - ax) / L, (bz - az) / L
    fen = op['type'] in ('window', 'door_glazed')
    for f in bm.faces:
        c = murs.matrix_world @ f.calc_center_median()
        nrm = murs.matrix_world.to_3x3() @ f.normal
        pt = Point(c.x, -c.y)
        sel = q.contains(pt)
        if not sel and fen and q.distance(pt) < 0.9:
            # joue de niche : normale le long du mur de la fenêtre
            sel = abs(nrm.x * ux + (-nrm.y) * uz) > 0.7
        f.select = sel
        n += f.select
    bmesh.update_edit_mesh(murs.data)
    if n:
        bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    if not n:
        continue
    new = [o for o in bpy.context.selected_objects if o is not murs][0]
    new.name = name
    room = 'cuisine' if 'cuisine' in op['id'] else max(rooms, key=lambda r: r[1].intersection(q.buffer(0.4)).area)[0]
    for k in ('atlas', 'bake_only'):
        if k in new:
            del new[k]
    new['lit'] = 'probe'
    new['room'] = room
    total += n
    print(name, n, 'faces ->', room)
print('tableaux séparés :', total, 'faces')
bpy.ops.wm.save_mainfile()
import export  # noqa: E402
export.export()
