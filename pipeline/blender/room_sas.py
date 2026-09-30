"""
Dégagement / buanderie : lave-linge au droit des raccordements réels
(robinet + évacuation vus sur la vidéo, à ~0,7 m de l'angle sud-ouest du mur
extérieur), meuble blanc à portes jusqu'à 2,40 m qui l'encadre, trappe de
visite de la salle de bain laissée accessible, passages dégagés.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import layout as L  # noqa: E402

from lib import H, P, apply_transform, box, cylinder, join, lathe, set_collection, tag  # noqa: E402
from room_chambre import ceiling_light, frame_matrix, place_all  # noqa: E402

px = L.px
# mur extérieur du dégagement : origine côté salle de bain (NE), s vers le SO
MUR = L.Frame(px(116.5, 337.5), px(45.5, 429.5), 'mur_buanderie')
# retour de la salle de bain (trappe de visite)
RETOUR = L.Frame(px(135, 352), px(116.5, 337.5), 'retour_sdb')
MACHINE_S = MUR.length - 0.72  # axe du lave-linge (depuis l'angle NE)


def washer():
    """Lave-linge frontal blanc 60 x 57 x 85 (hublot chromé, vitre fumée)."""
    w, d, h = 0.597, 0.57, 0.845
    p = [box('ll_caisse', 0.0, 0.0, 0.0, w, d, h, 'plastique_blanc', bevel=0.01)]
    p.append(box('ll_bandeau', 0.01, d, h - 0.13, w - 0.01, d + 0.008, h - 0.01, 'plastique_blanc', bevel=0.004))
    p.append(box('ll_tiroir', 0.02, d + 0.008, h - 0.115, 0.22, d + 0.012, h - 0.03, 'plastique_blanc', bevel=0.004))
    p.append(box('ll_ecran', 0.36, d + 0.008, h - 0.095, 0.47, d + 0.01, h - 0.045, 'verre_noir'))
    k = cylinder('ll_programme', 0.026, 0, 0.02, 32, 'plastique_gris', bevel=0.003)
    k.matrix_world = Matrix.Translation((0.29, d + 0.008, h - 0.07)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    apply_transform(k)
    p.append(k)
    ring = lathe('ll_hublot', [(0.15, 0.0), (0.2, 0.0), (0.2, 0.02), (0.185, 0.045), (0.15, 0.05)], 64, 'chrome')
    glass = lathe('ll_vitre', [(0.0, 0.035), (0.15, 0.035), (0.15, 0.04), (0.0, 0.02)], 48, 'verre_noir')
    for o in (ring, glass):
        o.matrix_world = Matrix.Translation((w / 2, d, 0.40)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
        apply_transform(o)
    p += [ring, glass]
    p.append(box('ll_trappe', 0.44, d, 0.03, 0.56, d + 0.004, 0.11, 'plastique_blanc', bevel=0.003))
    return join(p, 'lave_linge')


def cabinet():
    """Meuble à portes blanches encadrant le lave-linge, hauteur 2,40 m."""
    W, D, Ht = 0.72, 0.60, 2.40
    t = 0.018
    p = [box('joue_g', 0.0, 0.0, 0.0, t, D, Ht, 'blanc_meuble', bevel=0.002, grain='z'),
         box('joue_d', W - t, 0.0, 0.0, W, D, Ht, 'blanc_meuble', bevel=0.002, grain='z'),
         box('tablette_ll', t, 0.0, 0.88, W - t, D - 0.02, 0.88 + t, 'blanc_meuble'),
         box('caisson_haut', t, 0.0, 0.88 + t, W - t, D - 0.02, Ht, 'blanc_caisson'),
         box('dessus', 0.0, 0.0, Ht - t, W, D, Ht, 'blanc_meuble', bevel=0.002)]
    for k in range(2):
        a, b = t + k * (W - 2 * t) / 2, t + (k + 1) * (W - 2 * t) / 2
        p.append(box(f'porte{k}', a + 0.0015, D - 0.02, 0.90, b - 0.0015, D, Ht - t - 0.002, 'blanc_meuble', bevel=0.0015, grain='z'))
        # prise de main : découpe (ombre) figurée par un petit creux
        hx = b - 0.035 if k == 0 else a + 0.035
        p.append(box(f'prise{k}', hx - 0.006, D, 1.28, hx + 0.006, D + 0.02, 1.44, 'inox', bevel=0.003))
    return join(p, 'meuble_buanderie')


def build():
    set_collection('buanderie')
    out = []
    s0 = MACHINE_S - 0.36
    cab = cabinet()
    place_all([cab], frame_matrix(MUR, s0, 0.005))
    tag(cab, atlas='sas', room='sas', collide=True, lit='lightmap', label='Rangement buanderie (h. 2,40 m)')
    ww = washer()
    place_all([ww], frame_matrix(MUR, s0 + 0.0615, 0.02))
    tag(ww, atlas='sas', room='sas', collide=True, lit='lightmap', label='Lave-linge')
    # trappe de visite existante sur le retour de la salle de bain
    tr = box('trappe', 0.03, 0.0, 0.10, 0.33, 0.006, 0.72, 'plastique_blanc', bevel=0.002)
    place_all([tr], frame_matrix(RETOUR, 0.0, 0.0))
    tag(tr, atlas='sas', room='sas', collide=False, lit='lightmap')
    out += [cab, ww, tr]
    out += ceiling_light('plafonnier_degagement', px(125, 420), 'sas')
    return out
