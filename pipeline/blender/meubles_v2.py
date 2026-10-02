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
from lib import P, apply_transform, box, cylinder, join, lathe, material, tag, tube  # noqa: E402
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
# Géométrie du fabricant (fichiers .3ds fournis par le propriétaire, téléchargés
# chez Artemide ; non versionnés : pipeline/assets/artemide/, voir .gitignore).
ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'artemide')


def import_3ds(fname, parts, decimate=1.0, split=None):
    """parts : {nom de pièce 3ds: (objet cible, matériau)} ; les pièces absentes
    sont ignorées. split(face_centroid_mm) -> matériau permet de couper une pièce.
    Retourne {objet cible: objet Blender} (mètres, z vertical, origine du fichier)."""
    from lire_3ds import lire
    import numpy as np
    from lib import material as getmat, mesh_obj, smooth_by_angle
    objs, _ = lire(os.path.join(ART, fname))
    groups = {}
    for o in objs:
        if o['name'] not in parts:
            continue
        tgt, mname = parts[o['name']]
        v = o['verts'] * 0.001
        f = o['faces']
        if split is not None:
            cen = o['verts'][f].mean(1)
            mats = [split(c) for c in cen]
        else:
            mats = [mname] * len(f)
        groups.setdefault(tgt, []).append((v, f, mats))
    out = {}
    for tgt, lst in groups.items():
        V, F, M, off = [], [], [], 0
        for v, f, mats in lst:
            V.append(v)
            F.append(f + off)
            M += mats
            off += len(v)
        V = np.concatenate(V)
        F = np.concatenate(F)
        ob = mesh_obj(tgt, V.tolist(), F.tolist())
        names = sorted(set(M))
        for n in names:
            ob.data.materials.append(getmat(n))
        idx = {n: i for i, n in enumerate(names)}
        ob.data.polygons.foreach_set('material_index', [idx[m] for m in M])
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.00005)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        if decimate < 1.0:
            m = ob.modifiers.new('decimer', 'DECIMATE')
            m.ratio = decimate
            bpy.ops.object.modifier_apply(modifier=m.name)
        smooth_by_angle(ob, 35)
        ob.select_set(False)
        out[tgt] = ob
    return out


def eclisse(name):
    """Artemide Eclisse orange (Magistretti, 1967), géométrie Artemide.
    Ouverture du globe orientée vers +y local (le lit)."""
    pied, dome = name + '_pied', name + '_dome'
    o = import_3ds('Eclisse.3ds', {
        'Obj_000001': (pied, 'plastique_blanc'),   # douille
        'Obj_000002': (pied, 'metal_noir'),
        'Obj_000003': (pied, 'eclisse_orange'),    # col
        'Obj_000004': (pied, 'caoutchouc'),        # semelle
        'Obj_000005': (pied, 'eclisse_orange'),    # globe extérieur
        'Obj_000006': (pied, 'eclisse_orange'),    # socle
        'Obj_000008': (pied, 'metal_noir'),        # bague crantée
        'Obj_000007': (dome, 'eclisse_interieur'),  # coque intérieure tournante
        'brep_8': (dome, 'ampoule'),
    }, decimate=0.3)
    R = Matrix.Rotation(math.pi / 2, 4, 'Z')  # le fichier ouvre vers +x
    for ob in o.values():
        ob.matrix_world = R
        apply_transform(ob)
    lo = light(name + '_lum', 9.0)
    lo.matrix_world = Matrix.Translation((0, 0, 0.115))
    return o[pied], o[dome], lo


def nessino(name):
    """Artemide Nessino blanche (Mattioli, 1967), géométrie Artemide (Ø 32, H 22)."""
    pied, dome = name + '_pied', name + '_dome'
    o = import_3ds('Nessino.3ds', {'Obj_000001': (dome, None)}, decimate=0.5,
                   split=lambda c: 'nessino_pied' if c[2] < 118 else 'nessino')
    ob = o[dome]
    # pied et dôme dans deux objets (le dôme est diffusant la nuit)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    ob.active_material_index = [m.name for m in ob.data.materials].index('nessino_pied')
    bpy.ops.object.material_slot_select()
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    base = [x for x in bpy.data.objects if x.name.startswith(dome + '.')][0]
    base.name = pied
    for x in (ob, base):
        x.select_set(False)
    lo = light(name + '_lum', 9.0)
    lo.matrix_world = Matrix.Translation((0, 0, 0.155))
    return base, ob, lo


def tolomeo_mega_wall(name):
    """Artemide Tolomeo Mega Parete (aluminium, diffuseur parchemin Ø 32),
    géométrie Artemide. Local : platine au mur en y = 0, bras vers +y, z vers le haut ;
    origine = centre de la platine (à fixer à la hauteur voulue)."""
    pied, shade = name + '_pied', name + '_abat_jour'
    o = import_3ds('Tolomeo_Mega_Parete.3ds', {
        'brep_3': (pied, 'inox'), 'shell_1': (pied, 'inox'), 'shell_2': (pied, 'inox'),
        'shell_3': (pied, 'inox'), 'brep_1': (pied, 'inox'), 'brep_2': (shade, 'tolomeo_diffuseur'),
    }, decimate=0.6)
    R = Matrix.Rotation(math.pi / 2, 4, 'Z')  # le fichier sort du mur vers +x
    for ob in o.values():
        ob.matrix_world = R
        apply_transform(ob)
    lo = light(name + '_lum', 20.0, size=0.06)
    lo.matrix_world = Matrix.Translation((0, 0.622, 0.69))
    return o[pied], o[shade], lo


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



# ------------------------------------------------------------------ séjour : Ghost + EKENÄSET
SHOWEFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'showefy')


def ghost_sofa(name='canape'):
    """Canapé Gervasoni Ghost 13 (fichier OBJ Showefy fourni par le propriétaire,
    non versionné), housse lin mélangé beige. Local : dos contre le mur (y = 0),
    façade vers +y, centré en x."""
    import numpy as np
    from lib import material as getmat, mesh_obj, smooth_by_angle
    V, F = [], []
    for line in open(os.path.join(SHOWEFY, 'GHOST13.obj')):
        if line.startswith('v '):
            V.append([float(t) for t in line.split()[1:4]])
        elif line.startswith('f '):
            idx = [int(t.split('/')[0]) - 1 for t in line.split()[1:]]
            for k in range(1, len(idx) - 1):
                F.append((idx[0], idx[k], idx[k + 1]))
    V = np.array(V) * 0.001
    ymax = V[:, 1].max()
    # fichier : dos vers +y -> on retourne (façade vers +y local) et on plaque le dos au mur
    V = np.stack([-V[:, 0], ymax - V[:, 1], V[:, 2]], 1)
    ob = mesh_obj(name, V.tolist(), F)
    ob.data.materials.append(getmat('lin_ghost'))
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0002)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    m = ob.modifiers.new('decimer', 'DECIMATE')
    m.ratio = 0.4
    bpy.ops.object.modifier_apply(modifier=m.name)
    smooth_by_angle(ob, 60)
    ob.select_set(False)
    return ob


def ekenaset(name='fauteuil'):
    """Fauteuil IKEA EKENÄSET, Kilanda beige clair : structure hêtre massif,
    accoudoirs plats, coussins d'assise et de dossier rembourrés (simulés).
    L 64 x P 78 x H 76 ; assise H 45, accoudoirs H 63, dégagement sous assise 22.
    Local : centré en x, façade vers +y, z vers le haut."""
    import cloth
    W, Dp = 0.64, 0.78
    p = []
    bv = 0.007
    xa = W / 2 - 0.03                                   # axe des montants
    for sx in (-1, 1):
        x = sx * xa
        # pied avant, légèrement fuselé (section 38 -> 30 mm)
        p.append(cylinder('pied_av', 0.017, 0.0, 0.612, 6, 'hetre', cx=x, cy=0.30, r_top=0.019, bevel=0.003))
        # montant arrière incliné (pied + support de dossier)
        p.append(tube('montant_ar', [(x, -0.27, 0.0), (x, -0.31, 0.40), (x, -0.375, 0.74)], 0.017, 10, 'hetre'))
        # accoudoir plat, débord avant arrondi
        p.append(box('accoudoir', x - 0.026, -0.36, 0.612, x + 0.026, 0.355, 0.637, 'hetre', bevel=0.01, seg=3, grain='y'))
        # longeron d'assise
        p.append(box('longeron', x - 0.013, -0.29, 0.22, x + 0.013, 0.30, 0.30, 'hetre', bevel=bv, grain='y'))
    p.append(box('traverse_av', -xa, 0.285, 0.22, xa, 0.31, 0.30, 'hetre', bevel=bv))
    p.append(box('traverse_ar', -xa, -0.30, 0.22, xa, -0.275, 0.30, 'hetre', bevel=bv))
    p.append(box('traverse_haut', -xa, -0.39, 0.70, xa, -0.365, 0.735, 'hetre', bevel=bv))
    # sangles sous l'assise (visibles de près)
    for k in range(4):
        y = -0.22 + k * 0.15
        p.append(box('sangle', -xa + 0.01, y - 0.025, 0.285, xa - 0.01, y + 0.025, 0.29, 'caoutchouc'))
    frame = join(p, name)
    seat = cloth.pillow(name + '_assise', 0.56, 0.54, thick=0.13, cell=0.018, pressure=4.5, frames=30, mat='kilanda', bending=6.0)
    seat.matrix_world = Matrix.Translation((0, 0.02, 0.375))
    apply_transform(seat)
    back = cloth.pillow(name + '_dossier', 0.56, 0.46, thick=0.12, cell=0.018, pressure=4.0, frames=30, mat='kilanda', bending=6.0)
    back.matrix_world = Matrix.Translation((0, -0.29, 0.54)) @ Matrix.Rotation(math.radians(-76), 4, 'X')
    apply_transform(back)
    return frame, seat, back


# ------------------------------------------------------------------ cuisine
def cuisine_v2():
    """Reconstruit les caissons et façades (mêmes emplacements que room_cuisine.build)."""
    import room_cuisine as RC
    from room_chambre import place_all
    remove('tiroirs_a', 'fileur', 'four', 'etroit', 'evier_meuble', 'joue', 'haut_ferme', 'haut_vitre',
           'haut_vitre_vitrage')
    fA, fB = RC.RUN_A, RC.RUN_B
    sw, sk = fA.length - 0.005, fB.length
    items = [(fA, 'tiroirs_a', RC.drawers_unit(0.60, 'tiroirs_a', 3), sw - 1.20),
             (fB, 'four', RC.oven_unit(), sk - 0.60), (fB, 'etroit', RC.narrow_unit(), sk - 0.80),
             (fB, 'evier_meuble', RC.drawers_unit(0.60, 'evier_meuble', 2), sk - 1.40)]
    for fr, name, parts, s0 in items:
        if name == 'evier_meuble':
            # caisson sous évier ouvert en haut (la cuve y descend) : joues, fond, dos
            car = [o for o in parts if o.name.startswith('evier_meuble_caisson')][0]
            parts.remove(car)
            bpy.data.objects.remove(car)
            parts += [box('evier_joue_g', 0.0, 0.0, 0.08, 0.018, RC.D - 0.002, RC.TOP, 'caisson_cuisine'),
                      box('evier_joue_d', 0.582, 0.0, 0.08, 0.60, RC.D - 0.002, RC.TOP, 'caisson_cuisine'),
                      box('evier_fond', 0.018, 0.0, 0.08, 0.582, RC.D - 0.002, 0.098, 'caisson_cuisine'),
                      box('evier_dos', 0.018, 0.0, 0.098, 0.582, 0.008, RC.TOP, 'caisson_cuisine'),
                      box('evier_traverse', 0.018, RC.D - 0.08, RC.TOP - 0.018, 0.582, RC.D - 0.002, RC.TOP, 'caisson_cuisine')]
        place_all(parts, frame_matrix(fr, s0, 0.0))
        tag(join(parts, name), room='cuisine', collide=True, lit='probe', label='Cuisine (VOXTORP)')
    fil = box('fileur', 0.0, 0.0, 0.08, sw - 1.20, RC.D + 0.019, RC.TOP, 'voxtorp')
    place_all([fil], frame_matrix(fA, 0.0, 0.0))
    tag(fil, room='cuisine', collide=True, lit='probe')
    joue = box('joue', 0.0, 0.0, 0.0, 0.019, RC.D + 0.019, RC.TOP, 'voxtorp')
    place_all([joue], frame_matrix(fB, sk - 1.40 - 0.019, 0.0))
    tag(joue, room='cuisine', collide=True, lit='probe')
    closed = RC.upper(0.80, 'haut_ferme')
    place_all(closed, frame_matrix(fA, sw - 0.80, 0.0))
    tag(join(closed, 'haut_ferme'), room='cuisine', collide=False, lit='probe')
    Mg = frame_matrix(fA, sw - 1.40, 0.0)
    glz = RC.upper(0.60, 'haut_vitre', glazed=True)
    place_all(glz, Mg)
    tag(join(glz, 'haut_vitre'), room='cuisine', collide=False, lit='probe')
    gv = RC.glazing(0.60, 'haut_vitre')
    place_all([gv], Mg)
    tag(gv, room='cuisine', lit='glass', collide=False, bake_hide=True)


# ------------------------------------------------------------------ application
def remove(*names):
    for o in list(bpy.data.objects):
        if any(o.name == n or o.name.startswith(n + '.') for n in names):
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
    for key, (dx, dy) in (('chevet_1', (0.13, 0.2)), ('chevet_2', (0.2, 0.335))):
        c = C[key]
        M = frame_matrix(c['frame'], c['s0'], c['t0']) @ Matrix.Translation((dx, dy, 0.67))
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
        # TV côté fenêtre / terrasse, lampe Nessino côté cuisine
    s_tv = s0 + 0.10 + 0.50
    tvp, screen = television(45)
    place(tvp + [screen], frame_matrix(fr, s_tv, 0.21, 0.56))
    tvj = join(tvp, 'television')
    tag(tvj, room='sejour', collide=False, lit='probe')
    tag(screen, room='sejour', lit='probe', collide=False)
    base, dome, lo = nessino('lampe_tv')
    place([base, dome, lo], frame_matrix(fr, s0 + Wf - 0.22, 0.23, 0.56))
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
    place([pied, shade, lo], frame_matrix(fr, s_sofa + 2.0 + 0.05, 0.0, 0.95))
    # tableaux au-dessus du canapé : 1 m vers la fenêtre (demande du propriétaire)
    remove('affiche_sej_0', 'affiche_sej_1')
    for i, (ds, art) in enumerate(((-0.28, 'affiche_cercles'), (0.28, 'affiche_formes'))):
        pf = poster_frame(f'affiche_sej_{i}', 0.40, 0.50, art)
        pf.matrix_world = frame_matrix(fr, s_sofa + 1.0 + ds + 1.0, 0.0, 1.45)
        apply_transform(pf)
        tag(pf, room='sejour', collide=False, lit='probe')
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
    # --- canapé Ghost 13 (lin mélangé beige) à la place du canapé-lit, centré sur son mur
    remove('canape', 'coussin_canape_0', 'coussin_canape_1', 'plaid')
    fr = RS.MUR_CANAPE
    gs = ghost_sofa('canape')
    place([gs], frame_matrix(fr, (fr.length) / 2, 0.02))
    tag(gs, room='sejour', collide=True, lit='probe', label='Canapé Ghost 13 (Gervasoni), lin beige')
    # --- fauteuil EKENÄSET dans l'angle de la fenêtre, tourné vers le salon
    remove('fauteuil', 'fauteuil_assise', 'fauteuil_dossier')
    fa, fs, fb = ekenaset('fauteuil')
    cx, cz = 7.22, 10.33
    ang = math.atan2(-(4.6 - cx), -(9.3 - cz))  # façade (+y local) vers le coin salon
    Mf = Matrix.Translation(P(cx, cz)) @ Matrix.Rotation(ang, 4, 'Z')
    place([fa, fs, fb], Mf)
    tag(fa, room='sejour', collide=True, lit='probe', label='Fauteuil EKENÄSET Kilanda beige clair')
    for o in (fs, fb):
        tag(o, room='sejour', collide=False, lit='probe')
    # --- séjour : olivier retiré (demande du propriétaire)
    remove('olivier_pot', 'olivier_feuillage', 'terreau_olivier', 'pot_olivier')
    # --- cuisine : façades VOXTORP sans poignée, portes vitrées HEJSTA
    cuisine_v2()
    # --- toutes les lampes à 2700 K
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.get('lamp_group'):
            o.data.color = K2700
    bpy.ops.wm.save_mainfile()
    import export
    export.export()


if __name__ == '__main__':
    main()
