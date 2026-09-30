"""
Précalcul de l'éclairage (lightmaps) avec Cycles.

Chaque objet « lit=lightmap » porte une étiquette « atlas ». Les objets d'un
même atlas partagent une texture d'éclairage (UV « LM » empaquetés ensemble).
Pour chaque mode (jour / soir / nuit / nuit_plafonniers) :
  cuisson DIFFUSE (direct + indirect, sans couleur) -> éclairement,
  débruitage OIDN guidé par les normales, encodage sRGB 8 bits + facteur.
"""
import json
import math
import os
import time

import bpy
import numpy as np
from PIL import Image

from lib import ROOT

CACHE = os.path.join(ROOT, 'pipeline', 'cache')
OUT = os.path.join(ROOT, 'web', 'public', 'lightmaps')

# résolution des atlas (pixels) ; texel visé ~1 cm (chambre) à 5 cm (extérieur)
ATLAS_RES = {'archi': 1024, 'chambre': 1024, 'sejour': 1024, 'cuisine': 1024, 'sdb': 1024, 'sas': 512, 'ext': 1024}
# échantillons par texel (relatif au réglage global SPP)
ATLAS_SPP = {'chambre': 1.0, 'archi': 0.8, 'sejour': 0.8, 'cuisine': 0.6, 'sdb': 0.5, 'sas': 0.5, 'ext': 0.3}


def atlas_objects():
    groups = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.get('lit') == 'lightmap' and o.get('atlas'):
            groups.setdefault(o['atlas'], []).append(o)
    return groups


def select_only(objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def make_lightmap_uvs(groups):
    for name, objs in groups.items():
        t = time.time()
        for o in objs:
            me = o.data
            if 'LM' in me.uv_layers:
                me.uv_layers.remove(me.uv_layers['LM'])
            lm = me.uv_layers.new(name='LM')
            me.uv_layers.active = lm
        res = ATLAS_RES.get(name, 1024)
        # 1) dépliage par objet : tissus = UV continus d'origine, autres = projection « smart »
        for o in objs:
            if o.get('lm_from_uv0'):
                src, dst = o.data.uv_layers['UVMap'], o.data.uv_layers['LM']
                for i, d in enumerate(src.data):
                    dst.data[i].uv = d.uv
                continue
            select_only([o])
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                                     correct_aspect=True, scale_to_bounds=False)
            bpy.ops.object.mode_set(mode='OBJECT')
        # 2) densité de texels uniforme puis empaquetage commun
        select_only(objs)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, margin_method='FRACTION',
                                margin=6.0 / res, shape_method='CONCAVE')
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in objs:
            o.data.uv_layers['UVMap'].active = True
            o.data.uv_layers['UVMap'].active_render = True
        print(f'  UV {name}: {len(objs)} objets, {time.time() - t:.1f}s', flush=True)


def _target_nodes(objs, img):
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            nt = m.node_tree
            n = nt.nodes.get('LM_TARGET')
            if n is None:
                n = nt.nodes.new('ShaderNodeTexImage')
                n.name = 'LM_TARGET'
                uv = nt.nodes.new('ShaderNodeUVMap')
                uv.uv_map = 'LM'
                nt.links.new(uv.outputs['UV'], n.inputs['Vector'])
            n.image = img
            nt.nodes.active = n


def bake_atlas(name, objs, kind='DIFFUSE', samples=128):
    res = ATLAS_RES.get(name, 1024)
    img = bpy.data.images.new(f'lm_{name}_{kind}', res, res, float_buffer=True, alpha=True)
    img.generated_color = (0, 0, 0, 0)
    _target_nodes(objs, img)
    select_only(objs)
    sc = bpy.context.scene
    sc.cycles.samples = samples
    b = sc.render.bake
    b.margin = 8
    b.margin_type = 'EXTEND'
    b.use_clear = True
    b.target = 'IMAGE_TEXTURES'
    if kind == 'DIFFUSE':
        b.use_pass_direct = True
        b.use_pass_indirect = True
        b.use_pass_color = False
        bpy.ops.object.bake(type='DIFFUSE', uv_layer='LM')
    else:
        b.normal_space = 'OBJECT'
        bpy.ops.object.bake(type='NORMAL', uv_layer='LM', normal_space='OBJECT')
    a = np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4)
    bpy.data.images.remove(img)
    return a


def denoise(lm, nrm):
    """OIDN (nœud Denoise du compositeur) guidé par les normales."""
    res = lm.shape[0]
    sc = bpy.context.scene
    tmp = os.path.join(CACHE, 'tmp')
    os.makedirs(tmp, exist_ok=True)
    ims = []
    for arr, nm in ((lm, 'lm'), (nrm, 'nrm')):
        im = bpy.data.images.new('dn_' + nm, res, res, float_buffer=True, alpha=True)
        im.pixels.foreach_set(arr.ravel())
        ims.append(im)
    ng = bpy.data.node_groups.new('dn', 'CompositorNodeTree')
    old = sc.compositing_node_group
    sc.compositing_node_group = ng
    a = ng.nodes.new('CompositorNodeImage')
    a.image = ims[0]
    n = ng.nodes.new('CompositorNodeImage')
    n.image = ims[1]
    dn = ng.nodes.new('CompositorNodeDenoise')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    go = ng.nodes.new('NodeGroupOutput')
    ng.links.new(a.outputs[0], dn.inputs['Image'])
    ng.links.new(n.outputs[0], dn.inputs['Normal'])
    try:
        dn.inputs['HDR'].default_value = True
    except Exception:
        pass
    ng.links.new(dn.outputs[0], go.inputs[0])
    r = sc.render
    keep = (r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, r.image_settings.file_format, sc.camera)
    r.resolution_x = r.resolution_y = res
    r.resolution_percentage = 100
    r.image_settings.file_format = 'OPEN_EXR'
    r.image_settings.color_depth = '32'
    path = os.path.join(tmp, 'dn.exr')
    r.filepath = path
    if sc.camera is None:
        cd = bpy.data.cameras.new('dn_cam')
        cam = bpy.data.objects.new('dn_cam', cd)
        sc.collection.objects.link(cam)
        sc.camera = cam
    # rendu du compositeur seul : on masque toute la géométrie
    hidden = [o for o in sc.objects if not o.hide_render]
    for o in hidden:
        o.hide_render = True
    samples = sc.cycles.samples
    sc.cycles.samples = 1
    bpy.ops.render.render(write_still=True)
    sc.cycles.samples = samples
    for o in hidden:
        o.hide_render = False
    out = bpy.data.images.load(path)
    d = np.array(out.pixels[:], dtype=np.float32).reshape(res, res, 4)
    bpy.data.images.remove(out)
    for im in ims:
        bpy.data.images.remove(im)
    sc.compositing_node_group = old
    bpy.data.node_groups.remove(ng)
    r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, r.image_settings.file_format, sc.camera = keep
    d[..., 3] = lm[..., 3]
    return d


LOG_K = 1024.0


def encode(arr, path):
    """Éclairement linéaire -> 8 bits logarithmiques (tramé) + facteur.
    v = log(1 + K L/s) / log(1 + K)  ;  décodage : L = s ((1+K)^v - 1) / K
    (précision relative ~2 % sur une plage de 1 à 1000)."""
    rgb = np.maximum(arr[..., :3], 0)
    valid = arr[..., 3] > 0.5
    lum = rgb.max(axis=-1)
    scale = float(np.percentile(lum[valid], 99.5)) * 1.25 if valid.any() else 1.0
    scale = max(scale, 1e-6)
    v = np.log1p(LOG_K * np.clip(rgb / scale, 0, 1)) / np.log1p(LOG_K)
    s = v * 255 + np.random.default_rng(0).uniform(-0.5, 0.5, v.shape)
    u8 = np.clip(s + 0.5, 0, 255).astype(np.uint8)[::-1]  # Blender : origine en bas
    Image.fromarray(u8, 'RGB').save(path, 'WEBP', quality=90, method=6)
    return scale


def bake_mode(mode, groups, samples, ceiling=False, normals=None):
    import lights
    info = lights.setup_sun(mode)
    lights.set_lamps(mode, ceiling=ceiling)
    tag_ = mode + ('_plafonniers' if ceiling else '')
    os.makedirs(os.path.join(OUT, tag_), exist_ok=True)
    man = {'info': {k: v for k, v in info.items() if isinstance(v, (int, float, str))}, 'atlas': {}}
    for name, objs in groups.items():
        t = time.time()
        lm = bake_atlas(name, objs, 'DIFFUSE', max(16, int(samples * ATLAS_SPP.get(name, 1.0))))
        np.save(os.path.join(CACHE, f'lm_{tag_}_{name}.npy'), lm.astype(np.float16))
        if normals is not None and name in normals:
            lm = denoise(lm, normals[name])
        sc = encode(lm, os.path.join(OUT, tag_, name + '.webp'))
        man['atlas'][name] = {'file': f'lightmaps/{tag_}/{name}.webp', 'intensity': sc}
        print(f'  [{tag_}] {name}: {time.time() - t:.0f}s  échelle {sc:.3f}', flush=True)
    return tag_, man


def run(modes, samples=128):
    sc = bpy.context.scene
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 6
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.use_denoising = False
    for o in bpy.data.objects:
        if o.get('bake_hide'):
            o.hide_render = True
    groups = atlas_objects()
    make_lightmap_uvs(groups)
    normals = {}
    for name, objs in groups.items():
        normals[name] = bake_atlas(name, objs, 'NORMAL', 1)
    mpath = os.path.join(OUT, 'manifest.json')
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for m in modes:
        ceiling = m.endswith('+plafonniers')
        mode = m.replace('+plafonniers', '')
        tag_, man = bake_mode(mode, groups, samples, ceiling=ceiling, normals=normals)
        manifest[tag_] = man
        with open(mpath, 'w') as f:
            json.dump(manifest, f, indent=1)
    for o in bpy.data.objects:
        if o.get('bake_hide'):
            o.hide_render = False


def reencode():
    """Ré-encode les lightmaps à partir des données flottantes sauvegardées
    (débruitage OIDN + encodage), sans refaire le précalcul."""
    import glob
    groups = atlas_objects()
    normals = {name: bake_atlas(name, objs, 'NORMAL', 1) for name, objs in groups.items()}
    mpath = os.path.join(OUT, 'manifest.json')
    manifest = json.load(open(mpath))
    for tag_, man in manifest.items():
        for name in list(man['atlas']):
            f = os.path.join(CACHE, f'lm_{tag_}_{name}.npy')
            if not os.path.exists(f):
                continue
            lm = np.load(f).astype(np.float32)
            if name in normals:
                lm = denoise(lm, normals[name])
            sc = encode(lm, os.path.join(OUT, tag_, name + '.webp'))
            man['atlas'][name]['intensity'] = sc
            print(f'  ré-encodage {tag_}/{name} échelle {sc:.3f}', flush=True)
    for man in manifest.values():
        man['log_k'] = LOG_K
    json.dump(manifest, open(mpath, 'w'), indent=1)
