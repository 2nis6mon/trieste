"""Rendus de contrôle Cycles (vérification de la géométrie et de l'éclairage)."""
import math
import os

import bpy
from mathutils import Vector

from lib import P


def look_at(cam, target):
    d = (Vector(target) - cam.location)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(name, pos_plan, target_plan, fov_deg=62.0, ortho=None):
    """pos/target : (x, z_plan, hauteur)."""
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if cam.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(cam)
    cam.location = P(*pos_plan)
    look_at(cam, P(*target_plan))
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.type = 'PERSP'
        cd.sensor_fit = 'HORIZONTAL'
        cd.angle = math.radians(fov_deg)
    cd.clip_start = 0.05
    cd.clip_end = 200
    return cam


def render(path, cam, w=960, h=600, samples=48, exposure=0.0, view='AgX'):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 5
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 4
    sc.view_settings.view_transform = view
    sc.view_settings.exposure = exposure
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 90
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
