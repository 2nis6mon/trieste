"""
Mobilier v2 (indications du propriétaire, octobre 2026) :
- chambre : PAX 100 + 50 cm, profondeur 37 cm, portes TONSTAD blanc cassé, centré sur son mur ;
- entrée (séjour, mur ouest) : PAX 3 x 100 cm, 60 cm, 248 cm, collé au retour côté porte palière ;
- chevets : lampes Artemide Eclisse orange ;
- meuble TV : enfilade vintage pieds compas (164 x 46 x 56 cm), TV 45", lampe Artemide Nessino blanche ;
- à côté du canapé : applique Artemide Tolomeo Mega (structure alu/inox, diffuseur beige) ;
- douche : tapis Simeas écru (La Redoute Intérieurs, 50 x 80) ;
- desserte : machine Nespresso Inissia noire.
Toutes les sources lumineuses : 2700 K.

Usage : python meubles_v2.py  (remplace les objets dans pipeline/cache/appartement_lm.blend
puis exporte la maquette ; les meubles sont éclairés en temps réel, pas de précalcul).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import layout as L  # noqa: E402
from lib import apply_transform, box, cylinder, join, lathe, material, tag, tube  # noqa: E402
from room_chambre import frame_matrix  # noqa: E402

# 2700 K vu par un appareil réglé sur 4000 K (balance des blancs d'intérieur)
K2700 = (1.0, 0.63, 0.25)


def light(name, energy, kind='POINT', size=0.03):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = K2700
    ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def place(objs, M):
    for o in objs:
        o.matrix_world = M @ o.matrix_world
        if o.type == 'MESH':
            apply_transform(o)


# ------------------------------------------------------------------ PAX / TONSTAD
def pax_tonstad(widths, D, H_tot, hinges, name):
    """Caissons PAX 236 cm (+ bandeau jusqu'à H_tot), portes TONSTAD 50 x 229 blanc
    cassé à bords arrondis et prise de main intégrée (rainure verticale côté ouverture).
    Local : x le long du mur, y vers la pièce (façade en y = D), z."""
    Wt = sum(widths)
    p = [box('caisson', 0, 0.0, 0, Wt, D - 0.02, 2.36, 'blanc_caisson', bevel=0.002),
         box('plinthe', 0.01, 0.0, 0, Wt - 0.01, D - 0.03, 0.022, 'blanc_caisson')]
    if H_tot > 2.361:
        p.append(box('bandeau', 0, 0.0, 2.36, Wt, D, H_tot, 'tonstad', bevel=0.003))
    doors, x = [], 0.0
    for w in widths:
        n = 2 if w > 0.75 else 1
        for k in range(n):
            doors.append((x + k * w / n, x + (k + 1) * w / n))
        x += w
    for i, ((a, b), hg) in enumerate(zip(doors, hinges)):
        p.append(box(f'porte_{i}', a + 0.0015, D - 0.02, 0.025, b - 0.0015, D, 2.315, 'tonstad', bevel=0.006, seg=3, grain='z'))
        # prise intégrée : rainure le long du chant côté ouverture (hauteur de main)
        e0, e1 = (b - 0.03, b - 0.008) if hg == 'L' else (a + 0.008, a + 0.03)
        p.append(box(f'prise_{i}', e0, D - 0.004, 0.90, e1, D + 0.0004, 1.30, 'tonstad_prise', bevel=0.003))
    return join(p, name)


# ------------------------------------------------------------------ luminaires Artemide
def eclisse(name):
    """Artemide Eclisse (Magistretti, 1967) orange : socle, sphère Ø 12 ouverte
    vers l'avant, coque intérieure claire (diffuse la nuit). H 18 cm."""
    R, zc = 0.06, 0.115
    base = lathe(name + '_pied', [(0, 0), (0.06, 0), (0.06, 0.006), (0.045, 0.02), (0.012, 0.03),
                                  (0.011, 0.058), (0.0, 0.058)], 48, 'eclisse_orange')
    prof = [(R * math.sin(math.radians(a)), R * math.cos(math.radians(a))) for a in range(50, 181, 10)]
    shell = lathe(name + '_coque', prof, 48, 'eclisse_orange', close=False)
    inner = lathe(name + '_dome', [(r * 0.94, z * 0.94) for r, z in prof], 48, 'eclisse_interieur', close=False)
    M = Matrix.Translation((0, 0, zc)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')  # ouverture vers +y
    for o in (shell, inner):
        o.matrix_world = M
        apply_transform(o)
    body = join([base, shell], name + '_pied')
    lo = light(name + '_lum', 9.0)
    lo.matrix_world = Matrix.Translation((0, 0.01, zc))
    return body, inner, lo


def nessino(name):
    """Artemide Nessino blanche (Mattioli, 1967) : pied évasé, dôme Ø 32, H 22 cm."""
    base = lathe(name + '_pied', [(0, 0), (0.075, 0), (0.075, 0.006), (0.032, 0.02), (0.019, 0.125), (0.0, 0.125)],
                 48, 'nessino_pied')
    dome = lathe(name + '_dome', [(0.004, 0.122), (0.152, 0.122), (0.16, 0.128), (0.156, 0.155), (0.135, 0.185),
                                  (0.09, 0.208), (0.0, 0.22)], 64, 'nessino')
    lo = light(name + '_lum', 9.0)
    lo.matrix_world = Matrix.Translation((0, 0, 0.15))
    return base, dome, lo


def tolomeo_mega_wall(name):
    """Artemide Tolomeo Mega, version murale : platine, bras articulé aluminium
    (finition inox), diffuseur tronconique Ø 36 beige. Local : y sort du mur."""
    plate = box(name + '_platine', -0.04, 0.0, 1.66, 0.04, 0.025, 1.90, 'inox', bevel=0.004)
    knuckle = cylinder('articulation', 0.016, 1.76, 1.82, 20, 'inox', cy=0.04)
    arm1 = tube('bras', [(0, 0.04, 1.79), (0, 0.42, 2.06)], 0.009, 12, 'inox')
    joint = cylinder('rotule', 0.014, 2.04, 2.08, 16, 'inox', cy=0.42)
    arm2 = tube('avant_bras', [(0, 0.42, 2.06), (0, 0.80, 1.86)], 0.008, 12, 'inox')
    hub = cylinder('moyeu', 0.022, 1.80, 1.86, 20, 'inox', cy=0.80)
    pied = join([plate, knuckle, arm1, joint, arm2, hub], name + '_pied')
    shade = lathe(name + '_abat_jour', [(0.15, 1.80), (0.165, 1.66), (0.18, 1.50)], 64, 'tolomeo_diffuseur', close=False)
    shade.matrix_world = Matrix.Translation((0, 0.80, 0))
    apply_transform(shade)
    lo = light(name + '_lum', 20.0, size=0.06)
    lo.matrix_world = Matrix.Translation((0, 0.80, 1.66))
    return pied, shade, lo


# ------------------------------------------------------------------ séjour : enfilade + TV
def enfilade(name, W=1.64, D=0.46, H=0.56):
    """Enfilade vintage années 60-70 (Côte & Vintage) : bois exotique teinte teck,
    2 portes + 2 tiroirs, pieds compas à sabots laiton."""
    z0 = 0.20
    p = [box('caisson', 0.0, 0.0, z0, W, D - 0.02, H - 0.016, 'teck', bevel=0.004),
         box('plateau', -0.006, -0.004, H - 0.016, W + 0.006, D + 0.004, H, 'teck', bevel=0.005)]
    dw = 0.56
    fronts = [(0.008, dw, z0 + 0.012, H - 0.022), (W - dw, W - 0.008, z0 + 0.012, H - 0.022)]
    mid0, mid1 = dw + 0.006, W - dw - 0.006
    zm = (z0 + 0.012 + H - 0.022) / 2
    fronts += [(mid0, mid1, z0 + 0.012, zm - 0.003), (mid0, mid1, zm + 0.003, H - 0.022)]
    for i, (a, b, za, zb) in enumerate(fronts):
        p.append(box(f'facade_{i}', a, D - 0.02, za, b, D, zb, 'teck', bevel=0.003, grain='x'))
        if i < 2:   # prises verticales des portes, côté centre
            hx = b - 0.04 if i == 0 else a + 0.04
            p.append(box('prise', hx - 0.006, D, zm - 0.07, hx + 0.006, D + 0.014, zm + 0.07, 'teck', bevel=0.004))
        else:       # prises horizontales des tiroirs
            cx = (a + b) / 2
            zz = zb - 0.035
            p.append(box('prise', cx - 0.07, D, zz - 0.006, cx + 0.07, D + 0.014, zz + 0.006, 'teck', bevel=0.004))
    for x, sx in ((0.13, -1), (W - 0.13, 1)):
        for y, sy in ((0.09, -1), (D - 0.09, 1)):
            top, foot = (x, y, z0), (x + sx * 0.06, y + sy * 0.035, 0.0)
            mid = tuple(top[k] + (foot[k] - top[k]) * 0.82 for k in range(3))
            p.append(tube('pied', [top, mid], 0.017, 14, 'teck'))
            p.append(tube('sabot', [mid, foot], 0.012, 14, 'laiton'))
    return p


def television(diag_in=45):
    w = diag_in * 0.0254 * 0.8716
    h = diag_in * 0.0254 * 0.4903
    p = [box('tv', -w / 2, -0.03, 0.07, w / 2, 0.0, 0.07 + h, 'plastique_gris', bevel=0.004),
         box('tv_pied_g', -w / 2 + 0.1, -0.11, 0.0, -w / 2 + 0.13, 0.05, 0.012, 'metal_noir'),
         box('tv_pied_d', w / 2 - 0.13, -0.11, 0.0, w / 2 - 0.1, 0.05, 0.012, 'metal_noir'),
         box('tv_col', -0.05, -0.05, 0.0, 0.05, -0.02, 0.09, 'metal_noir')]
    screen = box('ecran', -w / 2 + 0.008, 0.0, 0.078, w / 2 - 0.008, 0.002, 0.07 + h - 0.008, 'ecran_tv')
    return p, screen


def nespresso_inissia(name):
    """Nespresso Inissia noire, 12 x 23 x 32 cm. Local : centre au sol, façade +y."""
    p = [box('corps', -0.06, -0.16, 0.0, 0.06, 0.09, 0.215, 'nespresso_noir', bevel=0.022, seg=4),
         box('tete', -0.058, 0.07, 0.14, 0.058, 0.155, 0.225, 'nespresso_noir', bevel=0.02, seg=4),
         box('levier', -0.022, -0.02, 0.215, 0.022, 0.15, 0.236, 'nespresso_noir', bevel=0.008),
         box('bac', -0.055, 0.09, 0.0, 0.055, 0.16, 0.018, 'nespresso_noir', bevel=0.006),
         box('grille', -0.048, 0.095, 0.018, 0.048, 0.155, 0.021, 'nespresso_grille'),
         cylinder('bec', 0.009, 0.125, 0.142, 16, 'nespresso_grille', cy=0.118)]
    return join(p, name)


# ------------------------------------------------------------------ application
def remove(*names):
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o)


def main():
    from build import CACHE
    import room_sejour as RS
    bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, 'appartement_lm.blend'))
    remove('nespresso', 'pax_chambre', 'pax_sejour', 'meuble_tv', 'television', 'ecran', 'pot_pothos', 'pothos_feuillage',
           'affiche_sej_2', 'lampadaire_pied', 'lampadaire_abat_jour', 'lampadaire_lum',
           *[f'lampe_{k}_{p}' for k in ('chevet_1', 'chevet_2', 'tv') for p in ('pied', 'dome', 'lum')])
    out = []
    # --- chambre : PAX 150 x 37, centré sur son mur
    fr = L.CH_MUR_NE
    W = 1.50
    px_ = pax_tonstad((1.0, 0.5), 0.37, 2.36, ['L', 'R', 'R'], 'pax_chambre')
    place([px_], frame_matrix(fr, (fr.length - W) / 2, 0.008))
    tag(px_, room='chambre', collide=True, lit='probe', label='PAX 150x236x37, portes TONSTAD')
    out.append(px_)
    # --- chevets : Eclisse orange (ouverture vers le lit)
    C = L.CHAMBRE
    for key, dx in (('chevet_1', 0.13), ('chevet_2', 0.2)):
        c = C[key]
        M = frame_matrix(c['frame'], c['s0'], c['t0']) @ Matrix.Translation((dx, 0.2, 0.67))
        body, inner, lo = eclisse('lampe_' + key)
        rot = Matrix.Rotation(math.radians(-35 if key == 'chevet_1' else 35), 4, 'Z')
        place([body, inner, lo], M @ rot)
        tag(body, room='chambre', lit='probe', collide=False)
        tag(inner, room='chambre', lit='lamp', lamp_group='appoint', collide=False)
        tag(lo, room='chambre', lamp_group='appoint')
    # --- entrée : PAX 3 x 100, collé au retour du mur côté porte palière
    fr = RS.MUR_OUEST
    ps = pax_tonstad((1.0, 1.0, 1.0), 0.60, 2.48, ['L', 'R'] * 3, 'pax_sejour')
    place([ps], frame_matrix(fr, fr.length - 3.0 - 0.004, 0.008))
    tag(ps, room='sejour', collide=True, lit='probe', label='PAX 300x248x60, portes TONSTAD')
    # --- enfilade + TV 45" + Nessino, contre le bloc sud
    fr = RS.BLOC_SUD
    Wf = 1.64
    s0 = fr.length - Wf - 0.02
    parts = enfilade('meuble_tv', Wf)
    place(parts, frame_matrix(fr, s0, 0.01))
    tvu = join(parts, 'meuble_tv')
    tag(tvu, room='sejour', collide=True, lit='probe', label='Enfilade vintage 164x46x56')
    sofa_cx = RS.MUR_CANAPE.pt((RS.MUR_CANAPE.length - 2.0) / 2 + 1.0)[0]
    s_tv = min(max(fr.o[0] - sofa_cx, s0 + 0.55), s0 + Wf - 0.52)
    tvp, screen = television(45)
    place(tvp + [screen], frame_matrix(fr, s_tv, 0.21, 0.56))
    tvj = join(tvp, 'television')
    tag(tvj, room='sejour', collide=False, lit='probe')
    tag(screen, room='sejour', lit='probe', collide=False)
    base, dome, lo = nessino('lampe_tv')
    place([base, dome, lo], frame_matrix(fr, s0 + 0.22, 0.23, 0.56))
    tag(base, room='sejour', lit='probe', collide=False)
    tag(dome, room='sejour', lit='lamp', lamp_group='appoint', collide=False)
    tag(lo, room='sejour', lamp_group='appoint')
    from room_chambre import poster_frame
    pf = poster_frame('affiche_sej_2', 0.40, 0.50, 'affiche_soleil')
    pf.matrix_world = frame_matrix(fr, s_tv, 0.0, 1.55)
    apply_transform(pf)
    tag(pf, room='sejour', collide=False, lit='probe')
    # --- applique Tolomeo Mega au bout du canapé
    fr = RS.MUR_CANAPE
    s_sofa = (fr.length - 2.0) / 2
    pied, shade, lo = tolomeo_mega_wall('lampadaire')
    place([pied, shade, lo], frame_matrix(fr, s_sofa + 2.0 + 0.05, 0.0))
    tag(pied, room='sejour', lit='probe', collide=False)
    tag(shade, room='sejour', lit='lamp', lamp_group='appoint', collide=False)
    tag(lo, room='sejour', lamp_group='appoint')
    # --- tapis de douche Simeas écru (même emprise 50 x 80)
    tb = bpy.data.objects['tapis_bain']
    tb.data.materials.clear()
    tb.data.materials.append(material('simeas'))
    # --- Nespresso Inissia sur le plateau haut de la desserte (profondeur le long du plateau)
    niche = L.Frame(L.px(476, 563), L.px(476, 510), 'niche')
    ns = nespresso_inissia('nespresso')
    place([ns], frame_matrix(niche, 0.09, 0.03) @ Matrix.Translation((0.2525, 0.15, 0.752))
          @ Matrix.Rotation(math.pi / 2, 4, 'Z'))
    tag(ns, room='cuisine', lit='probe', collide=False)
    # --- toutes les lampes à 2700 K
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.get('lamp_group'):
            o.data.color = K2700
    bpy.ops.wm.save_mainfile()
    import export
    export.export()


if __name__ == '__main__':
    main()
