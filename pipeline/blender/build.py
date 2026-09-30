"""
Construction complète de la scène.

  python build.py scene            -> pipeline/cache/appartement.blend
  python build.py preview [mode]   -> rendus Cycles de contrôle (docs/controle/)
  python build.py bake [modes...]  -> lightmaps (web/public/lightmaps/)
  python build.py export           -> web/public/models/appartement.glb
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402

from lib import ROOT, px, reset_scene  # noqa: E402

CACHE = os.path.join(ROOT, 'pipeline', 'cache')
BLEND = os.path.join(CACHE, 'appartement.blend')
os.makedirs(CACHE, exist_ok=True)

ROOMS = ['chambre', 'cuisine', 'sejour', 'sdb', 'sas']


def build_scene(rooms=None):
    import arch
    import exterior
    t = time.time()
    reset_scene()
    arch.build_all()
    exterior.build_all()
    exterior.facade_night_emission()
    for r in rooms or ROOMS:
        try:
            mod = __import__('room_' + r)
        except ImportError:
            print('pièce non encore modélisée :', r)
            continue
        t1 = time.time()
        mod.build()
        print(f'  {r}: {time.time() - t1:.1f}s', flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f'scène construite en {time.time() - t:.1f}s -> {BLEND}')


VIEWS = {
    # nom : (position plan px + hauteur, cible plan px + hauteur, fov horizontal)
    'chambre_porte': ((215, 455, 1.6), (500, 300, 1.05), 70),
    'chambre_fenetres': ((300, 300, 1.6), (520, 430, 1.2), 70),
    'chambre_lit': ((500, 400, 1.5), (260, 290, 0.8), 68),
    'chambre_cote': ((400, 470, 1.1), (300, 330, 0.35), 60),
    'sejour_fenetre': ((223, 714, 1.6), (588, 700, 1.3), 72),
    'sejour_entree': ((506, 766, 1.6), (74, 670, 1.1), 72),
    'cuisine': ((305, 591, 1.6), (342, 491, 1.0), 72),
    'sdb': ((202, 331, 1.6), (327, 164, 1.1), 72),
    'buanderie': ((164, 446, 1.6), (82, 380, 1.1), 72),
}


def preview(mode='jour', views=None, samples=64, w=1100, h=720):
    import lights
    import preview as pv
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    info = lights.setup_sun(mode)
    lights.set_lamps(mode)
    print(info)
    out = os.path.join(ROOT, 'docs', 'controle')
    os.makedirs(out, exist_ok=True)
    if views == ['dessus']:
        for o in bpy.data.objects:
            if o.get('kind') == 'plafond' or (o.name.startswith(('dalle', 'joint', 'plafonnier'))):
                o.hide_render = True
        cam = pv.camera('cam_top', (4.6, 7.2, 30.0), (4.6, 7.2, 0.0), ortho=11.5)
        pv.render(os.path.join(out, f'dessus_{mode}.jpg'), cam, 900, 1000, samples=samples)
        return
    for name in views or VIEWS:
        (x0, z0, h0), (x1, z1, h1), fov = VIEWS[name]
        a, b = px(x0, z0), px(x1, z1)
        cam = pv.camera('cam_' + name, (a[0], a[1], h0), (b[0], b[1], h1), fov_deg=fov)
        t = time.time()
        pv.render(os.path.join(out, f'{name}_{mode}.jpg'), cam, w, h, samples=samples,
                  exposure=float(os.environ.get('EXPO', '0')))
        print(name, f'{time.time() - t:.0f}s', flush=True)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'scene'
    if cmd == 'scene':
        build_scene(sys.argv[2:] or None)
    elif cmd == 'bake':
        import bake
        bpy.ops.wm.open_mainfile(filepath=BLEND)
        bake.run(sys.argv[2:] or ['jour', 'soir', 'nuit', 'nuit+plafonniers'], samples=int(os.environ.get('SPP', '128')))
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
    elif cmd == 'bake-archi':
        import bake
        bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
        bake.run_archi(sys.argv[2:] or ['jour', 'soir', 'nuit', 'nuit+plafonniers'], samples=int(os.environ.get('SPP', '128')))
    elif cmd == 'reencode':
        import bake
        bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
        bake.reencode()
    elif cmd == 'export':
        import export
        bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
        export.export()
    elif cmd == 'preview':
        mode = sys.argv[2] if len(sys.argv) > 2 else 'jour'
        preview(mode, sys.argv[3:] or None, samples=int(os.environ.get('SPP', '64')))
