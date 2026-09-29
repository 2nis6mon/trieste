"""
Extraction de la géométrie de l'appartement depuis le dernier plan sans mobilier.

Source : references/plan-sans-mobilier.jpg (export Floorplanner, murs noirs).
Échelle : barre graphique 0-5 m du plan = 372 px  ->  74,4 px/m (1 px = 1,34 cm).
Contrôle : 8,79 m / 10,86 m (hors tout), 1,35 m (salle de bain), 3,00 m (mur
fenêtre séjour), 3,88 m (mur canapé) du plan coté concordent à +-2 cm.

Repère de sortie (identique au repère three.js) :
    x = px / 74,4   (vers la droite du plan)
    z = py / 74,4   (vers le bas du plan)
    y = hauteur (sol fini = 0, plafond = 2,70 m)

Les murs sont vectorisés automatiquement (contours des pixels noirs, simplifiés
à 1,2 px). Les ouvertures (portes, fenêtres) sont décrites à la main à partir
des sommets des murs qui les encadrent : elles sont les « trous » du dessin.
Les hauteurs d'allège / de linteau viennent des captures vidéo (voir
docs/DIMENSIONS.md).

Usage : python extract_plan.py  ->  web/public/data/plan.json + docs/plan-vectorise.png
"""
import json
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'references', 'plan-sans-mobilier.jpg')
PX_PER_M = 74.4
CEILING = 2.70

# Nord (plan cadastral, rose des vents) : le haut du plan regarde l'azimut 71°
# (ENE). Les fenêtres sur cour (à droite du plan) regardent donc le SSE (161°).
PLAN_UP_AZIMUTH_DEG = 70.9


def m(p):
    return [round(p[0] / PX_PER_M, 4), round(p[1] / PX_PER_M, 4)]


def load_masks():
    im = np.array(Image.open(SRC).convert('RGB')).astype(int)
    s = im.sum(axis=2)
    black = (s < 200).astype(np.uint8)
    black[880:] = 0  # légende / échelle
    walls = cv2.morphologyEx(black, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    grey = ((abs(r - 170) < 22) & (abs(g - 170) < 22) & (abs(b - 170) < 22)).astype(np.uint8)
    return im, walls, grey


def contours_to_polys(mask, min_area=15, eps=1.2):
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = []
    for i, c in enumerate(cnts):
        if hier[0][i][3] != -1:
            continue
        if cv2.contourArea(c) < min_area:
            continue
        ap = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(float)
        # les contours OpenCV passent par le centre des pixels de bord :
        # on les dilate d'un demi-pixel pour retrouver le bord réel.
        poly = Polygon(ap).buffer(0.5, join_style=2)
        polys.append(poly)
    return polys


def snap_axis(poly, tol_deg=2.5):
    """Redresse les arêtes quasi horizontales / verticales (bruit de pixel)."""
    pts = list(poly.exterior.coords)[:-1]
    n = len(pts)
    pts = [list(p) for p in pts]
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ang = abs(math.degrees(math.atan2(dy, dx))) % 180
        if min(ang, 180 - ang) < tol_deg and abs(dx) > 3:
            y = (a[1] + b[1]) / 2
            a[1] = b[1] = y
        elif abs(ang - 90) < tol_deg and abs(dy) > 3:
            x = (a[0] + b[0]) / 2
            a[0] = b[0] = x
    return Polygon(pts).buffer(0)


# --------------------------------------------------------------------------
# Ouvertures, en pixels du plan. quad = [A1, A2, B2, B1] : A = face côté
# « pièce A », B = face côté « pièce B » ; A1-B1 et A2-B2 sont les tableaux.
# --------------------------------------------------------------------------
OPENINGS = [
    dict(id='fen_sejour', type='window', label='Fenêtre du séjour (3 vantaux + imposte)',
         quad=[(578, 653), (578, 775), (599, 775), (599, 653)], room='sejour',
         sill=0.83, head=2.50, leaves=3, transom=0.37, frame_depth_from_A=0.17),
    dict(id='porte_terrasse', type='door_glazed', label='Porte-fenêtre de la terrasse',
         quad=[(500, 587), (556, 587), (556, 565), (500, 565)], room='sejour',
         sill=0.0, head=2.50, leaves=1, transom=0.0, hinge='A2', opens='B',
         frame_depth_from_A=0.14),
    dict(id='fen_cuisine', type='window', label='Fenêtre de la cuisine (1 vantail)',
         quad=[(477, 514), (476, 558), (497, 558), (498, 514)], room='cuisine',
         sill=0.85, head=2.50, leaves=1, transom=0.0, frame_depth_from_A=0.14),
    dict(id='fen_chambre_1', type='window', label='Chambre, fenêtre nord (2 vantaux + imposte)',
         quad=[(546, 334), (514, 392), (532, 401), (561, 343)], room='chambre',
         sill=0.84, head=2.50, leaves=2, transom=0.37, frame_depth_from_A=0.13),
    dict(id='fen_chambre_2', type='window', label='Chambre, fenêtre sud (2 vantaux + imposte)',
         quad=[(503, 424), (484, 487), (504, 492), (523, 429)], room='chambre',
         sill=0.84, head=2.50, leaves=2, transom=0.37, frame_depth_from_A=0.13),
    dict(id='porte_entree', type='door_entry', label="Porte d'entrée blindée",
         quad=[(91, 753), (165, 753), (165, 775), (91, 775)], room='sejour',
         sill=0.0, head=2.10, hinge='A1', opens='A'),
    dict(id='passage_sas', type='passage', label='Passage séjour / dégagement (sans porte)',
         quad=[(97, 457.5), (162, 481), (164, 472.5), (99, 449)], room='sejour',
         sill=0.0, head=2.10),
    dict(id='porte_sdb', type='door', label='Porte de la salle de bain',
         quad=[(137, 356), (195, 396), (199, 389), (144, 346)], room='sas',
         sill=0.0, head=2.10, hinge='A2', opens='B'),
    dict(id='porte_chambre', type='door', label='Porte de la chambre',
         quad=[(197, 405), (197, 473), (207.5, 473), (207.5, 405)], room='sas',
         sill=0.0, head=2.10, hinge='A2', opens='B'),
]

# Graines de remplissage des pièces (pixels) et noms affichés.
ROOMS = [
    dict(id='chambre', name='Chambre', seed=(400, 330)),
    dict(id='sdb', name='Salle de bain', seed=(250, 240)),
    dict(id='sas', name='Dégagement / buanderie', seed=(110, 405)),
    dict(id='sejour', name='Séjour / salle à manger', seed=(330, 720)),
]


def main():
    im, walls_mask, grey = load_masks()
    H, W = walls_mask.shape

    wall_polys = [snap_axis(p) for p in contours_to_polys(walls_mask)]
    walls_union = unary_union(wall_polys)

    open_polys = {o['id']: Polygon(o['quad']).buffer(0) for o in OPENINGS}

    # Espace libre = intérieur de l'enveloppe - murs - ouvertures.
    solid = unary_union([walls_union] + list(open_polys.values()))
    outer = Polygon(max(
        (Polygon(p.exterior) for p in (solid.geoms if isinstance(solid, MultiPolygon) else [solid])),
        key=lambda q: q.area).exterior)
    # l'enveloppe englobe aussi la terrasse : on ne garde que les trous du solide
    holes = []
    for g in (solid.geoms if isinstance(solid, MultiPolygon) else [solid]):
        for ring in g.interiors:
            holes.append(Polygon(ring))
    free = unary_union(holes)
    # Les murs ne sont pas tous connectés (bloc cuisine, trumeau…) : on
    # rebouche avec la différence enveloppe-murs, en retirant la terrasse.
    # Terrasse : zone grise refermée (l'arc de la porte-fenêtre coupe le gris)
    cl = cv2.morphologyEx(grey, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, lab_t, st, _ = cv2.connectedComponentsWithStats(cl)
    ti = 1 + int(np.argmax(st[1:, 4]))
    terrace_mask = (lab_t == ti).astype(np.uint8)
    terrace_polys = contours_to_polys(terrace_mask, min_area=500, eps=1.0)
    terrace = max(terrace_polys, key=lambda p: p.area)
    terrace = terrace.buffer(3, join_style=2).difference(
        unary_union([walls_union] + list(open_polys.values()))).buffer(0)
    if isinstance(terrace, MultiPolygon):
        terrace = max(terrace.geoms, key=lambda p: p.area)
    terrace = terrace.intersection(box(0, 0, W, 565)).buffer(0)
    # garde-corps : bord libre (droit) de la zone grise, échantillonné ligne à ligne
    rail_px = []
    for yy in range(386, 566, 4):
        xs = np.where(terrace_mask[min(yy, 562)])[0]
        if len(xs):
            rail_px.append((float(xs.max()) - 1.0, float(yy)))
    # lissage (moyenne glissante) pour une courbe continue
    rp = np.array(rail_px)
    k = 5
    sm = rp.copy()
    for i in range(len(rp)):
        a, b = max(0, i - k // 2), min(len(rp), i + k // 2 + 1)
        sm[i, 0] = rp[a:b, 0].mean()
    rail_px = [tuple(p) for p in sm]

    # Pièces par remplissage raster (plus robuste que la topologie vectorielle)
    lab = np.ones((H, W), np.uint8)
    solid_img = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(solid_img)
    for g in (walls_union.geoms if isinstance(walls_union, MultiPolygon) else [walls_union]):
        d.polygon([tuple(c) for c in g.exterior.coords], fill=255)
    for p in open_polys.values():
        d.polygon([tuple(c) for c in p.exterior.coords], fill=255)
    for p in terrace_polys:
        d.polygon([tuple(c) for c in p.exterior.coords], fill=255)
    solid_arr = (np.array(solid_img) > 0).astype(np.uint8)
    free_arr = (1 - solid_arr).astype(np.uint8)
    free_arr[880:] = 0

    rooms_out = []
    room_polys = {}
    for r in ROOMS:
        ff = free_arr.copy()
        mask = np.zeros((H + 2, W + 2), np.uint8)
        cv2.floodFill(ff, mask, r['seed'], 2)
        reg = (ff == 2).astype(np.uint8)
        polys = contours_to_polys(reg, min_area=100, eps=1.0)
        poly = max(polys, key=lambda p: p.area)
        # ne pas dépasser dans les murs après la dilatation d'un demi-pixel
        poly = snap_axis(poly.difference(walls_union).buffer(0))
        if isinstance(poly, MultiPolygon):
            poly = max(poly.geoms, key=lambda p: p.area)
        room_polys[r['id']] = poly

    # Cuisine = partie du séjour au nord de la ligne du passage (y < 596 px)
    # et entre le refend (x >= 176 px) et la face est du bloc (x < 473 px).
    sej = room_polys['sejour']
    kitchen_zone = box(176, 400, 473, 596)
    kitchen = sej.intersection(kitchen_zone)
    if isinstance(kitchen, MultiPolygon):
        kitchen = max(kitchen.geoms, key=lambda p: p.area)
    room_polys['cuisine'] = kitchen
    names = {r['id']: r['name'] for r in ROOMS}
    names['cuisine'] = 'Cuisine'
    names['sejour'] = 'Séjour / salle à manger'

    for rid in ['chambre', 'sdb', 'sas', 'cuisine', 'sejour']:
        p = room_polys[rid]
        rooms_out.append(dict(
            id=rid, name=names[rid],
            poly=[m(c) for c in list(p.exterior.coords)[:-1]],
            area_m2=round(p.area / PX_PER_M ** 2, 2),
        ))

    # Sol continu = pièces + seuils de portes (ouvertures au sol, hors fenêtres)
    floor_parts = [room_polys['chambre'], room_polys['sdb'], room_polys['sas'], room_polys['sejour']]
    for o in OPENINGS:
        if o['sill'] == 0.0 and o['type'] != 'door_glazed' and o['type'] != 'door_entry':
            floor_parts.append(open_polys[o['id']].buffer(0.6, join_style=2))
    floor = unary_union(floor_parts).buffer(0)
    floor = floor.difference(walls_union.buffer(-0.01)).buffer(0)

    walls_out = []
    for i, p in enumerate(wall_polys):
        walls_out.append(dict(id=f'mur_{i}', poly=[m(c) for c in list(p.exterior.coords)[:-1]]))

    openings_out = []
    for o in OPENINGS:
        q = [np.array(c, float) for c in o['quad']]
        a1, a2, b2, b1 = q
        width = np.linalg.norm(a2 - a1) / PX_PER_M
        thick = np.linalg.norm((b1 + b2) / 2 - (a1 + a2) / 2) / PX_PER_M
        oo = {k: v for k, v in o.items() if k != 'quad'}
        oo.update(quad=[m(c) for c in o['quad']], width=round(width, 3), thickness=round(thick, 3))
        openings_out.append(oo)

    def ring(p):
        return [m(c) for c in list(p.exterior.coords)[:-1]]

    def poly_with_holes(p):
        return dict(outer=ring(p), holes=[[m(c) for c in list(h.coords)[:-1]] for h in p.interiors])

    floors = floor.geoms if isinstance(floor, MultiPolygon) else [floor]

    east_edge = rail_px

    out = dict(
        source='references/plan-sans-mobilier.jpg (Floorplanner, dernier plan sans mobilier)',
        px_per_m=PX_PER_M,
        repere='x = px/74.4 vers la droite du plan ; z = py/74.4 vers le bas du plan ; y = hauteur',
        ceiling_height=CEILING,
        plan_up_azimuth_deg=PLAN_UP_AZIMUTH_DEG,
        walls=walls_out,
        openings=openings_out,
        rooms=rooms_out,
        floor=[poly_with_holes(p) for p in floors],
        terrace=dict(poly=ring(terrace), railing=[m(c) for c in east_edge]),
    )
    os.makedirs(os.path.join(ROOT, 'web', 'public', 'data'), exist_ok=True)
    with open(os.path.join(ROOT, 'web', 'public', 'data', 'plan.json'), 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    # Visualisation de contrôle
    S = 3
    vis = Image.open(SRC).convert('RGB').resize((W * S, H * S), Image.NEAREST)
    dv = ImageDraw.Draw(vis, 'RGBA')
    colors = dict(chambre=(80, 140, 255, 70), sdb=(60, 200, 200, 70), sas=(200, 120, 255, 70),
                  cuisine=(255, 150, 40, 70), sejour=(90, 220, 90, 60))
    for rid, p in room_polys.items():
        dv.polygon([(x * S, y * S) for x, y in p.exterior.coords], fill=colors[rid], outline=(0, 0, 0, 255))
    for p in wall_polys:
        dv.line([(x * S, y * S) for x, y in p.exterior.coords], fill=(255, 0, 0, 255), width=2)
    for o in OPENINGS:
        dv.polygon([(x * S, y * S) for x, y in o['quad']], outline=(0, 0, 255, 255), fill=(0, 0, 255, 60))
    dv.line([(x * S, y * S) for x, y in east_edge], fill=(255, 0, 255, 255), width=3)
    vis.crop((0, 100, W * S, 880 * S)).save(os.path.join(ROOT, 'docs', 'plan-vectorise.png'))

    print('murs', len(walls_out), 'ouvertures', len(openings_out))
    for r in rooms_out:
        print(r['id'], r['area_m2'], 'm2', len(r['poly']), 'sommets')
    print('sol', [round(p.area / PX_PER_M ** 2, 2) for p in floors], 'terrasse', round(terrace.area / PX_PER_M ** 2, 2))


if __name__ == '__main__':
    main()
