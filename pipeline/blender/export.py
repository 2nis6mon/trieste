"""
Export glTF (GLB) + données de navigation.
  web/public/models/appartement.glb   (UV0 = textures en mètres, UV1 = lightmap)
  web/public/data/obstacles.json      (emprises au sol des meubles, pour les collisions et le mini-plan)
  web/public/data/lampes.json         (points lumineux, pour l'éclat nocturne)
"""
import json
import os

import bpy
import numpy as np
from scipy.spatial import ConvexHull

from lib import ROOT


def export(path=None):
    path = path or os.path.join(ROOT, 'web', 'public', 'models', 'appartement.glb')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    obstacles, lamps = [], []
    for o in list(bpy.data.objects):
        if o.type == 'LIGHT':
            if o.get('lamp_group'):
                p = o.matrix_world.translation
                lamps.append(dict(name=o.name, group=o['lamp_group'], room=o.get('room', ''),
                                  pos=[round(p.x, 3), round(p.z, 3), round(-p.y, 3)],
                                  color=list(o.data.color), power=o.data.energy, type=o.data.type))
            bpy.data.objects.remove(o)
            continue
        if o.type == 'CAMERA' or o.get('bake_only'):
            bpy.data.objects.remove(o)
            continue
        if o.type == 'MESH' and o.get('collide'):
            co = np.array([o.matrix_world @ v.co for v in o.data.vertices])
            sel = co[(co[:, 2] > 0.04) & (co[:, 2] < 1.9)]
            if len(sel) >= 3:
                pts = np.stack([sel[:, 0], -sel[:, 1]], 1)
                hull = ConvexHull(pts)
                obstacles.append(dict(name=o.name, label=o.get('label', o.name), room=o.get('room', ''),
                                      poly=[[round(float(pts[i, 0]), 3), round(float(pts[i, 1]), 3)] for i in hull.vertices],
                                      top=round(float(co[:, 2].max()), 3)))
    data = os.path.join(ROOT, 'web', 'public', 'data')
    json.dump(obstacles, open(os.path.join(data, 'obstacles.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(lamps, open(os.path.join(data, 'lampes.json'), 'w'), indent=1, ensure_ascii=False)
    # UV actifs : UVMap -> TEXCOORD_0, LM -> TEXCOORD_1
    for o in bpy.data.objects:
        if o.type == 'MESH':
            uvs = o.data.uv_layers
            if 'UVMap' in uvs:
                uvs.active = uvs['UVMap']
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_extras=True, export_yup=True,
                              export_materials='EXPORT', export_image_format='NONE', export_texcoords=True,
                              export_normals=True, export_apply=True, export_lights=False, export_cameras=False,
                              use_selection=False)
    print('GLB', path, round(os.path.getsize(path) / 1e6, 2), 'Mo ;', len(obstacles), 'obstacles ;', len(lamps), 'lampes')
