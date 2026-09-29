"""
Implantation du mobilier (repères muraux, emprises au sol), partagée par
Blender (modélisation) et par le contrôle 2D (docs/implantation.png).
Coordonnées plan en mètres (x droite, z bas). Un repère mural a une
origine o, un axe u le long du mur et un axe n = (u.z, -u.x) vers la pièce
(repère direct une fois converti dans Blender).
"""
import json
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PLAN = json.load(open(os.path.join(ROOT, 'web', 'public', 'data', 'plan.json')))
PXM = PLAN['px_per_m']


def px(x, y):
    return (x / PXM, y / PXM)


class Frame:
    def __init__(self, o, toward, name=''):
        self.o = o
        dx, dz = toward[0] - o[0], toward[1] - o[1]
        L = math.hypot(dx, dz)
        self.u = (dx / L, dz / L)
        self.n = (self.u[1], -self.u[0])
        self.length = L
        self.name = name
        # angle de rotation Blender (autour de Z) de l'axe local x
        self.rot = math.atan2(-self.u[1], self.u[0])

    def pt(self, s, t=0.0):
        return (self.o[0] + self.u[0] * s + self.n[0] * t, self.o[1] + self.u[1] * s + self.n[1] * t)

    def rect(self, s0, s1, t0, t1):
        return [self.pt(s0, t0), self.pt(s1, t0), self.pt(s1, t1), self.pt(s0, t1)]


# ----------------------------------------------------------------- chambre
# Cloison salle de bain / chambre (tête de lit) : de l'angle NE vers la porte
CH_CLOISON = Frame(px(379.5, 176.5), px(208, 397), 'cloison_lit')
# Mur NE (placard) : de l'extrémité est vers l'angle de la cloison
CH_MUR_NE = Frame(px(552.5, 316.5), px(379.5, 176.5), 'mur_placard')

BED_S0 = 1.58          # début du lit le long de la cloison (m) : dégage le débattement du PAX
BED_W, BED_L = 1.60, 2.02
CHAMBRE = dict(
    pax=dict(frame=CH_MUR_NE, s0=CH_MUR_NE.length - 0.012 - 2.50, s1=CH_MUR_NE.length - 0.012, t0=0.008, t1=0.608),
    chevet_1=dict(frame=CH_CLOISON, s0=BED_S0 - 0.44, s1=BED_S0 - 0.04, t0=0.015, t1=0.415),
    lit=dict(frame=CH_CLOISON, s0=BED_S0, s1=BED_S0 + BED_W, t0=0.012, t1=0.012 + BED_L),
    chevet_2=dict(frame=CH_CLOISON, s0=BED_S0 + BED_W + 0.04, s1=BED_S0 + BED_W + 0.44, t0=0.015, t1=0.415),
    tapis=dict(frame=CH_CLOISON, s0=BED_S0 + BED_W / 2 - 1.20, s1=BED_S0 + BED_W / 2 + 1.00, t0=0.80, t1=2.40),
)


def footprints(room):
    out = {}
    for k, v in room.items():
        f = v['frame']
        out[k] = f.rect(v['s0'], v['s1'], v['t0'], v['t1'])
    return out


if __name__ == '__main__':
    from PIL import Image, ImageDraw
    from shapely.geometry import Polygon, Point
    S = 3
    im = Image.open(os.path.join(ROOT, 'references', 'plan-sans-mobilier.jpg')).convert('RGB')
    W, H = im.size
    im = im.resize((W * S, H * S), Image.LANCZOS)
    d = ImageDraw.Draw(im, 'RGBA')
    fp = footprints(CHAMBRE)
    room = Polygon([r for r in PLAN['rooms'] if r['id'] == 'chambre'][0]['poly'])
    for k, poly in fp.items():
        pts = [(x * PXM * S, z * PXM * S) for x, z in poly]
        inside = all(room.buffer(0.02).contains(Point(p)) for p in poly)
        d.polygon(pts, outline=(0, 0, 0, 255), fill=(80, 160, 80, 90) if inside else (220, 40, 40, 110))
        cx = sum(p[0] for p in pts) / 4
        cy = sum(p[1] for p in pts) / 4
        d.text((cx - 20, cy - 5), k, fill=(0, 0, 0, 255))
        print(k, 'OK' if inside else 'DEBORDE')
    # débattement des portes du PAX (vantail de 50 cm côté cloison, paumelles à gauche)
    f = CH_MUR_NE
    pax = CHAMBRE['pax']
    for k in range(5):
        s_h = pax['s0'] + 0.5 * k
        c = f.pt(s_h, pax['t1'])
        arc = [f.pt(s_h + 0.5 * math.cos(a), pax['t1'] + 0.5 * math.sin(a)) for a in [i * math.pi / 40 for i in range(21)]]
        d.line([(x * PXM * S, z * PXM * S) for x, z in arc], fill=(0, 0, 255, 200), width=2)
    # débattement de la porte de la chambre
    hx, hz = px(202, 470)
    arc = [(hx + 0.82 * math.sin(a), hz - 0.82 * math.cos(a)) for a in [i * math.pi / 40 for i in range(21)]]
    d.line([(x * PXM * S, z * PXM * S) for x, z in arc], fill=(255, 0, 255, 220), width=2)
    im.crop((150 * S, 120 * S, 600 * S, 520 * S)).save(os.path.join(ROOT, 'docs', 'implantation-chambre.png'))
