"""
Éclairage : ciel physique + soleil de Trieste (position calculée), nuit,
lampes intérieures (déclarées par les modules de mobilier).

Orientation : plan cadastral (rose des vents) -> le haut du plan regarde
l'azimut 70,9° ; les fenêtres sur cour regardent le SSE (~161°).
"""
import datetime
import math

import bpy
import numpy as np
from mathutils import Vector

from lib import PLAN, hex_lin

LAT, LON = 45.652, 13.776  # Trieste
UP_AZ = PLAN['plan_up_azimuth_deg']

MODES = {
    # 21 juin, heure légale d'été (UTC+2)
    'jour': dict(label='Jour', date=(2026, 6, 21), time_local=13.5, dni_dhi=7.5,
                 sun_color=(1.0, 0.975, 0.93), exposure=0.0),
    'soir': dict(label='Fin de journée', date=(2026, 6, 21), time_local=19.6, dni_dhi=6.0,
                 sun_color=(1.0, 0.70, 0.43), exposure=0.0),
    'nuit': dict(label='Nuit', night=True, exposure=0.0),
}


def sun_position(lat, lon, y, mo, d, hour_utc):
    """Azimut (depuis le nord, sens horaire) et hauteur du soleil, en degrés (NOAA)."""
    n = datetime.date(y, mo, d).timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1 + (hour_utc - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
           + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = hour_utc * 60 + eqt + 4 * lon
    ha = math.radians(tst / 4 - 180)
    phi = math.radians(lat)
    cz = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(ha)
    zen = math.acos(max(-1, min(1, cz)))
    az = math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(phi) - math.tan(dec) * math.cos(phi))) + 180
    return az % 360, 90 - math.degrees(zen)


def az_el_to_blender(az, el):
    """Vecteur unitaire vers le soleil dans le repère Blender."""
    th = math.radians(az - UP_AZ)  # angle horaire depuis le haut du plan
    ce = math.cos(math.radians(el))
    return Vector((math.sin(th) * ce, math.cos(th) * ce, math.sin(math.radians(el))))


def mode_sun(mode):
    m = MODES[mode]
    if m.get('night'):
        return None
    y, mo, d = m['date']
    az, el = sun_position(LAT, LON, y, mo, d, m['time_local'] - 2.0)
    return az, el


def _world(name):
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w, nt, bg


def sky_world(mode, az, el):
    w, nt, bg = _world('ciel_' + mode)
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_disc = False
    sky.sun_elevation = math.radians(el)
    # la rotation du ciel est calée par mesure (voir calibrate_sky_rotation)
    d = az_el_to_blender(az, el)
    sky.sun_rotation = math.atan2(d.x, d.y) + SKY_ROT_OFFSET
    sky.altitude = 40.0
    sky.air_density = 1.0
    sky.aerosol_density = 1.2 if mode == 'jour' else 1.8
    nt.links.new(sky.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    return w


SKY_ROT_OFFSET = 0.0


def night_world():
    w, nt, bg = _world('ciel_nuit')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    # hauteur normalisée : Generated.z en coordonnées d'environnement = direction
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mp = nt.nodes.new('ShaderNodeMapRange')
    nt.links.new(sep.outputs['Z'], mp.inputs['Value'])
    mp.inputs['From Min'].default_value = 0.0
    mp.inputs['From Max'].default_value = 0.45
    nt.links.new(mp.outputs['Result'], ramp.inputs['Fac'])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.030, 0.022, 0.018, 1)   # halo orangé de la ville à l'horizon
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.0022, 0.0035, 0.0085, 1)  # bleu nuit au zénith
    nt.links.new(ramp.outputs['Color'], bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    return w


def world_irradiance(world, res=(256, 128)):
    """Éclairement horizontal diffus du ciel (intégration d'un rendu équirectangulaire)."""
    sc = bpy.context.scene
    old = (sc.world, sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath,
           sc.cycles.samples, sc.render.image_settings.file_format)
    sc.world = world
    cd = bpy.data.cameras.new('cam_ciel')
    cd.type = 'PANO'
    cd.panorama_type = 'EQUIRECTANGULAR'
    cam = bpy.data.objects.new('cam_ciel', cd)
    sc.collection.objects.link(cam)
    cam.location = (0, 0, 500.0)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.camera = cam
    hidden = []
    for o in sc.objects:
        if o.type in ('MESH', 'LIGHT') and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.image_settings.file_format = 'OPEN_EXR'
    import tempfile, os
    path = os.path.join(tempfile.gettempdir(), 'ciel_irr.exr')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(res[1], res[0], 4)[..., :3]
    bpy.data.images.remove(im)
    for o in hidden:
        o.hide_render = False
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cd)
    sc.world, sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath, sc.cycles.samples, sc.render.image_settings.file_format = old
    Hh, Ww = res[1], res[0]
    # lignes du bas vers le haut (pixels Blender) : v=0 en bas -> élévation -90°
    el = (np.arange(Hh) + 0.5) / Hh * math.pi - math.pi / 2
    dw = (2 * math.pi / Ww) * (math.pi / Hh) * np.cos(el)
    lum = a @ np.array([0.2126, 0.7152, 0.0722])
    up = el > 0
    E = float(((lum * (np.sin(el) * dw)[:, None])[up]).sum())
    col = (a[up] * (np.sin(el) * dw)[up][:, None, None]).sum(axis=(0, 1))
    return E, col / max(1e-9, col.max()), a


def setup_sun(mode):
    """Crée/ajuste la lampe soleil et le ciel du mode. Retourne des infos."""
    sc = bpy.context.scene
    sun = bpy.data.objects.get('Soleil')
    if sun is None:
        ld = bpy.data.lights.new('Soleil', 'SUN')
        sun = bpy.data.objects.new('Soleil', ld)
        sc.collection.objects.link(sun)
    m = MODES[mode]
    if m.get('night'):
        sc.world = night_world()
        sun.hide_render = True
        return dict(mode=mode, sun=None)
    az, el = mode_sun(mode)
    w = sky_world(mode, az, el)
    sc.world = w
    E_sky, _, _ = world_irradiance(w)
    d = az_el_to_blender(az, el)
    sun.hide_render = False
    sun.data.angle = math.radians(0.53)
    sun.data.color = m['sun_color']
    # rapport éclairement direct normal / diffus horizontal d'un ciel clair
    sun.data.energy = m['dni_dhi'] * E_sky
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return dict(mode=mode, az=az, el=el, E_sky=E_sky, sun_strength=sun.data.energy, sun_dir=tuple(d))


def set_lamps(mode, ceiling=False):
    """Allume/éteint les lampes intérieures et les émissifs selon le mode."""
    night = MODES[mode].get('night', False)
    for o in bpy.data.objects:
        g = o.get('lamp_group')
        if g is None:
            continue
        blind = o.get('room') in ('sdb', 'sas')  # pièces aveugles : éclairées aussi le jour
        on = (night and (g in ('appoint', 'integre') or (g == 'plafonnier' and ceiling))) or \
             (not night and blind and g == 'plafonnier')
        if o.type == 'LIGHT':
            o.hide_render = not on
        else:
            # abat-jour / diffuseurs émissifs : force selon l'état
            for slot in o.material_slots:
                mt = slot.material
                if mt and 'emit_strength' in mt:
                    bsdf = mt.node_tree.nodes.get('Principled BSDF')
                    bsdf.inputs['Emission Strength'].default_value = mt['emit_strength'] if on else 0.0
    # fenêtres éclairées des façades de la cour
    for mt in bpy.data.materials:
        if mt.get('night_emit') is not None:
            bsdf = mt.node_tree.nodes.get('Principled BSDF')
            bsdf.inputs['Emission Strength'].default_value = mt['night_emit'] if night else 0.0


def setup_portals():
    """Portails de lumière (Cycles) sur chaque fenêtre et porte-fenêtre : le ciel
    est échantillonné à travers les ouvertures (bruit fortement réduit)."""
    from mathutils import Matrix
    for o in [o for o in bpy.data.objects if o.name.startswith('portail_')]:
        bpy.data.objects.remove(o)
    for op in PLAN['openings']:
        if op['type'] not in ('window', 'door_glazed'):
            continue
        a1, a2, b2, b1 = [Vector((c[0], -c[1], 0)) for c in op['quad']]
        u = (a2 - a1)
        W = u.length
        u.normalize()
        mid_a = (a1 + a2) / 2
        mid_b = (b1 + b2) / 2
        n_in = (mid_a - mid_b).normalized()  # vers l'intérieur
        h0, h1 = op['sill'], op['head']
        ld = bpy.data.lights.new('portail_' + op['id'], 'AREA')
        ld.shape = 'RECTANGLE'
        ld.size = W
        ld.size_y = h1 - h0
        ld.cycles.is_portal = True
        ob = bpy.data.objects.new('portail_' + op['id'], ld)
        bpy.context.scene.collection.objects.link(ob)
        # la lumière surfacique émet selon -Z local : -Z = vers l'intérieur
        z = -n_in
        x = u
        y = z.cross(x)
        M = Matrix((x, y, z)).transposed().to_4x4()
        ob.matrix_world = Matrix.Translation(mid_b + (mid_a - mid_b) * 0.5 + Vector((0, 0, (h0 + h1) / 2))) @ M
        ob['bake_only'] = True
