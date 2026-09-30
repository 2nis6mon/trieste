import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from build import BLEND, VIEWS
from lib import px
import lights, preview as pv
bpy.ops.wm.open_mainfile(filepath=BLEND)
lights.setup_sun('jour'); lights.set_lamps('jour'); lights.setup_portals()
for name, ((x0, z0, h0), (x1, z1, h1), fov) in VIEWS.items():
    a, b = px(x0, z0), px(x1, z1)
    cam = pv.camera('Vue_' + name, (a[0], a[1], h0), (b[0], b[1], h1), fov_deg=fov)
sc = bpy.context.scene
sc.camera = bpy.data.objects['Vue_chambre_lit']
sc.render.engine = 'CYCLES'; sc.cycles.samples = 256; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
for im in bpy.data.images:
    if im.source == 'FILE' and im.filepath: im.filepath = bpy.path.abspath(im.filepath)
bpy.ops.file.pack_all()
out = sys.argv[-1]
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, copy=True)
print('OK', out, os.path.getsize(out) / 1e6, 'Mo', bpy.app.version_string)
