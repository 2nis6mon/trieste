"""
Génération procédurale des textures (aucune banque d'images n'est accessible
depuis l'environnement de production : tout est synthétisé ici, licence du
projet). Toutes les textures sont raccordables (bruit spectral périodique).

Sortie : web/public/textures/<nom>.webp (+ _n normale, _r rugosité)
         pipeline/textures/manifest.json (taille physique de chaque motif)

Usage : python gen_textures.py [nom ...]
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'web', 'public', 'textures')
os.makedirs(OUT, exist_ok=True)
MANIFEST = {}


# ----------------------------------------------------------------- outils
def rng(seed):
    return np.random.default_rng(seed)


def spectral_noise(h, w, beta=2.0, seed=0, fmin=0.0, aniso=(1, 1)):
    """Bruit périodique de spectre 1/f^beta, normalisé [-1, 1].
    aniso=(ax, ay) étire le bruit (ax>1 : allongé selon x)."""
    r = rng(seed)
    white = r.standard_normal((h, w))
    F = np.fft.fft2(white)
    # aniso=(ax, ay) : ax > 1 lisse le bruit le long de x (fibres allongées selon x)
    fy = np.fft.fftfreq(h)[:, None] * aniso[1]
    fx = np.fft.fftfreq(w)[None, :] * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta / 2.0)
    amp[f < fmin] = 0
    amp[0, 0] = 0
    n = np.real(np.fft.ifft2(F * amp))
    n -= n.mean()
    n /= (2.5 * n.std() + 1e-9)
    return np.clip(n, -1.5, 1.5)


def blur_wrap(a, sigma):
    """Flou gaussien périodique (FFT)."""
    h, w = a.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (math.pi ** 2) * (sigma ** 2) * (fx * fx + fy * fy))
    if a.ndim == 2:
        return np.real(np.fft.ifft2(np.fft.fft2(a) * g))
    return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., c]) * g)) for c in range(a.shape[2])], -1)


def normal_from_height(hgt, strength):
    """Carte normale (convention OpenGL, Y+) depuis une hauteur périodique."""
    dx = (np.roll(hgt, -1, axis=1) - np.roll(hgt, 1, axis=1)) * 0.5
    dy = (np.roll(hgt, -1, axis=0) - np.roll(hgt, 1, axis=0)) * 0.5
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(hgt)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return ((n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)


def srgb_u8(rgb):
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)


def save(name, arr, q=90, lossless=False, mode=None):
    if arr.dtype != np.uint8:
        arr = srgb_u8(arr)
    im = Image.fromarray(arr, mode) if mode else Image.fromarray(arr)
    path = os.path.join(OUT, name + '.webp')
    im.save(path, 'WEBP', quality=q, lossless=lossless, method=6)
    return path


def register(name, size_m, maps, **extra):
    MANIFEST[name] = dict(size_m=size_m, maps=maps, **extra)


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------- parquet
def floor_wood():
    """Sol brun aspect bois : lames 16 x 128 cm (motif 2,56 m)."""
    N = 2048
    size = 2.56
    ppm = N / size
    lw = int(0.16 * ppm)  # 128 px
    rows = N // lw
    r = rng(11)
    alb = np.zeros((N, N, 3))
    hgt = np.zeros((N, N))
    rough = np.zeros((N, N))
    # réservoir de fil du bois : bruit très allongé selon x
    grain_fields = [spectral_noise(512, 2048, beta=1.6, seed=100 + i, aniso=(16.667, 1)) for i in range(4)]
    pores = [spectral_noise(512, 2048, beta=0.6, seed=200 + i, aniso=(8.333, 1)) for i in range(4)]
    base = np.array([0.545, 0.345, 0.225])  # brun chaud moyen (sRGB)
    yy = np.arange(lw)[:, None]
    for row in range(rows):
        y0 = row * lw
        # découpe de la rangée : 1 ou 2 joints, décalage aléatoire (raccord périodique)
        off = int(r.integers(0, N // 64)) * 64
        n_cuts = int(r.integers(1, 3))
        cuts = sorted(set([off] + [(off + int(r.integers(8, 24)) * 64) % N for _ in range(n_cuts - 1)]))
        segs = []
        for i, c in enumerate(cuts):
            e = cuts[(i + 1) % len(cuts)]
            L = (e - c) % N or N
            segs.append((c, L))
        for (x0, L) in segs:
            gi = int(r.integers(0, 4))
            gy = int(r.integers(0, 512 - lw))
            gx = int(r.integers(0, 2048))
            g = np.roll(grain_fields[gi], -gx, axis=1)[gy:gy + lw]
            p = np.roll(pores[gi], -gx, axis=1)[gy:gy + lw]
            xs = (np.arange(L) + x0) % N
            gg = g[:, np.arange(L) % 2048]
            pp = p[:, np.arange(L) % 2048]
            tone = 1.0 + float(np.clip(r.normal(0, 0.045), -0.08, 0.08))
            warm = r.normal(0, 0.02)
            col = base * tone + np.array([warm, warm * 0.3, -warm * 0.5])
            # veines (bandes longues) + « flammes » + pores sombres fins
            streak = 0.5 + 0.35 * gg
            flame = 0.5 + 0.5 * np.sin((yy / lw * 3.0 + gg * 1.4 + x0 * 0.001) * math.pi)
            dark = np.clip(pp * 1.6 - 1.1, 0, 1)
            shade = 1.0 + (streak - 0.5) * 0.30 + (flame - 0.5) * 0.10 - dark * 0.22
            c = col[None, None, :] * shade[..., None]
            alb[y0:y0 + lw][:, xs] = c
            hgt[y0:y0 + lw][:, xs] = gg * 0.15 - dark * 0.6
            rough[y0:y0 + lw][:, xs] = 0.42 + 0.06 * (streak - 0.5) + dark * 0.1
            # micro-chanfrein en bout de lame
            for k in range(3):
                edge = [(x0 + k) % N, (x0 + L - 1 - k) % N]
                hgt[y0:y0 + lw, edge] -= (3 - k) * 0.9
                alb[y0:y0 + lw, edge] *= 0.86 + 0.04 * k
        # micro-chanfrein longitudinal
        for k in range(3):
            for yy2 in (y0 + k, y0 + lw - 1 - k):
                hgt[yy2 % N, :] -= (3 - k) * 0.9
                alb[yy2 % N, :] *= 0.86 + 0.04 * k
    # légère variation grande échelle (usure, lumière)
    big = spectral_noise(N, N, beta=3.0, seed=7)
    alb *= (1.0 + big * 0.04)[..., None]
    save('parquet', alb, q=88)
    save('parquet_n', normal_from_height(blur_wrap(hgt, 0.7), 1.2), q=92)
    save('parquet_r', srgb_u8(np.repeat(rough[..., None], 3, -1)), q=85)
    register('parquet', size, ['parquet', 'parquet_n', 'parquet_r'])


# ------------------------------------------------------------- peinture
def plaster():
    N = 1024
    n1 = spectral_noise(N, N, beta=1.2, seed=21)
    n2 = spectral_noise(N, N, beta=2.6, seed=22)
    hgt = n1 * 0.6 + n2 * 0.4
    save('enduit_n', normal_from_height(blur_wrap(hgt, 1.2), 1.3), q=90)
    a = 0.5 + 0.5 * spectral_noise(N, N, beta=2.8, seed=23)
    alb = np.ones((N, N, 3)) * np.array([0.925, 0.918, 0.898])[None, None]
    alb *= (0.985 + 0.03 * a)[..., None]
    save('enduit', alb, q=90)
    register('enduit', 1.0, ['enduit', 'enduit_n'])


# ------------------------------------------------------------- bouleau
def birch():
    """Placage bouleau (MANDAL) : clair, fil fin, légères ondes."""
    N = 1024
    g = spectral_noise(N, N, beta=1.8, seed=31, aniso=(20, 1))
    w = spectral_noise(N, N, beta=2.5, seed=32, aniso=(3.333, 1))
    f = spectral_noise(N, N, beta=0.9, seed=33, aniso=(10, 1))
    base = np.array([0.86, 0.72, 0.53])
    shade = 1 + g * 0.07 + w * 0.05 - np.clip(f * 2.5 - 1.7, 0, 1) * 0.08
    alb = base[None, None] * shade[..., None]
    save('bouleau', alb, q=90)
    save('bouleau_n', normal_from_height(blur_wrap(g * 0.3 + f * 0.2, 0.8), 0.8), q=90)
    register('bouleau', 0.6, ['bouleau', 'bouleau_n'])


def oak():
    N = 1024
    g = spectral_noise(N, N, beta=1.5, seed=41, aniso=(25, 1))
    ray = spectral_noise(N, N, beta=0.4, seed=42, aniso=(4, 1))
    base = np.array([0.78, 0.62, 0.43])
    shade = 1 + g * 0.12 - np.clip(ray * 3 - 2.2, 0, 1) * 0.1
    alb = base[None, None] * shade[..., None]
    save('chene', alb, q=90)
    save('chene_n', normal_from_height(blur_wrap(g * 0.4 - np.clip(ray * 3 - 2.2, 0, 1), 0.8), 1.0), q=90)
    register('chene', 0.8, ['chene', 'chene_n'])


def bamboo():
    """Bambou (NORDKISA) : lamelles verticales ~2 cm, nœuds, ton caramel clair."""
    N = 1024
    size = 0.4
    ppm = N / size
    r = rng(51)
    alb = np.zeros((N, N, 3))
    hgt = np.zeros((N, N))
    strip = int(0.02 * ppm)  # 51 px
    nstrips = N // strip + 1
    g = spectral_noise(N, N, beta=1.6, seed=52, aniso=(25, 1))
    x = 0
    base = np.array([0.80, 0.63, 0.40])
    while x < N:
        w = strip + int(r.integers(-6, 7))
        tone = 1 + r.normal(0, 0.06)
        # le fil est horizontal (selon x) ; les lamelles sont des bandes en y
        y0 = x
        y1 = min(N, x + w)
        col = base * tone
        alb[y0:y1] = col
        hgt[y0:y1] = 0
        hgt[y0:y0 + 2] -= 1.0
        # nœuds : fines bandes sombres perpendiculaires au fil
        nodes = r.integers(0, N, size=int(r.integers(1, 3)))
        for nx in nodes:
            for k in range(-4, 5):
                cx = (nx + k) % N
                alb[y0:y1, cx] *= 0.82 + 0.02 * abs(k)
                hgt[y0:y1, cx] += 0.3 * (1 - abs(k) / 5)
        x += w
    alb *= (1 + g * 0.08)[..., None]
    save('bambou', alb, q=90)
    save('bambou_n', normal_from_height(blur_wrap(hgt + g * 0.2, 0.8), 1.0), q=90)
    register('bambou', size, ['bambou', 'bambou_n'])


# ------------------------------------------------------------- tissus
def weave(N, period_px, seed, slub=0.3):
    """Hauteur d'un tissage toile (fils ~ period_px)."""
    y, x = np.mgrid[0:N, 0:N].astype(float)
    k = 2 * math.pi / period_px
    warp = np.sin(x * k) * np.sign(np.sin(y * k * 0.5))
    weft = np.sin(y * k) * -np.sign(np.sin(x * k * 0.5))
    h = np.maximum(np.abs(np.cos(x * k * 0.5)) * (0.5 + 0.5 * np.sign(np.sin(y * k * 0.5))),
                   np.abs(np.cos(y * k * 0.5)) * (0.5 - 0.5 * np.sign(np.sin(y * k * 0.5))))
    sl = spectral_noise(N, N, beta=1.0, seed=seed, aniso=(20, 1)) * slub
    sl2 = spectral_noise(N, N, beta=1.0, seed=seed + 1, aniso=(1, 20)) * slub
    return h + sl + sl2


def linen():
    N = 1024
    h = weave(N, 8, 61, slub=0.5)
    save('lin_n', normal_from_height(blur_wrap(h, 0.8), 1.4), q=90)
    a = spectral_noise(N, N, beta=1.0, seed=62, aniso=(20, 1))
    alb = np.ones((N, N, 3)) * np.array([0.93, 0.92, 0.89])[None, None] * (1 + a * 0.03)[..., None]
    save('lin', alb, q=90)
    register('lin', 0.12, ['lin', 'lin_n'])


def floral_print():
    """NÅLBJÖRNBÄR (d'après la photo produit IKEA) : semis dense de motifs
    botaniques vert sauge aquarellés (fougères, marguerites, pompons d'ail,
    tiges feuillues, fleurs à cinq pétales) sur toile de lin blanche."""
    N = 2048
    size = 0.50  # raccord 50 cm
    S = 2
    W = N * S
    ppm = W / size
    mask = Image.new('L', (W, W), 0)
    d = ImageDraw.Draw(mask)
    r = rng(171)

    def wrap(fn):
        for ox in (-W, 0, W):
            for oy in (-W, 0, W):
                fn(ox, oy)

    def poly(pts, v):
        wrap(lambda ox, oy: d.polygon([(x + ox, y + oy) for x, y in pts], fill=v))

    def line(pts, wdt, v):
        wrap(lambda ox, oy: d.line([(x + ox, y + oy) for x, y in pts], fill=v, width=max(1, int(wdt)), joint='curve'))

    def disc(cx, cy, rad, v):
        wrap(lambda ox, oy: d.ellipse([cx - rad + ox, cy - rad + oy, cx + rad + ox, cy + rad + oy], fill=v))

    def leaf_pts(cx, cy, ang, L, wid, tip=0.8):
        pts = [(t * L, math.sin(math.pi * t) ** tip * wid) for t in np.linspace(0, 1, 18)]
        pts += [(t * L, -math.sin(math.pi * t) ** tip * wid) for t in np.linspace(1, 0, 18)]
        ca, sa = math.cos(ang), math.sin(ang)
        return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]

    def stem(cx, cy, ang, L, curv):
        pts, a = [], ang
        x, y = cx, cy
        for i in range(20):
            pts.append((x, y))
            a += curv / 20
            x += math.cos(a) * L / 20
            y += math.sin(a) * L / 20
        return pts

    def fern(cx, cy, ang, L, v):
        pts = stem(cx, cy, ang, L, r.normal(0, 0.4))
        line(pts, ppm * 0.0012, v)
        for i in range(2, 19, 2):
            x, y = pts[i]
            a0 = math.atan2(pts[i + 1][1] - y, pts[i + 1][0] - x)
            ln = L * 0.2 * (1 - i / 21) ** 0.7
            for sg in (1, -1):
                poly(leaf_pts(x, y, a0 + sg * 0.95, ln, ln * 0.14), v)

    def daisy(cx, cy, rad, v):
        n = r.integers(14, 20)
        for k in range(n):
            a = k * 2 * math.pi / n + r.normal(0, 0.05)
            poly(leaf_pts(cx + math.cos(a) * rad * 0.28, cy + math.sin(a) * rad * 0.28, a, rad * 0.75, rad * 0.11), v)
        disc(cx, cy, rad * 0.26, min(255, v + 40))
        line(stem(cx, cy, math.pi / 2 + r.normal(0, 0.3), rad * 3.2, r.normal(0, 0.5)), ppm * 0.0011, v)

    def pompon(cx, cy, rad, v):
        for k in range(46):
            a, rr = r.uniform(0, 2 * math.pi), rad * math.sqrt(r.uniform(0, 1))
            disc(cx + math.cos(a) * rr, cy + math.sin(a) * rr, rad * 0.13, v)
        line(stem(cx, cy, math.pi / 2 + r.normal(0, 0.25), rad * 4.0, r.normal(0, 0.4)), ppm * 0.0011, v)

    def leafy(cx, cy, ang, L, v):
        pts = stem(cx, cy, ang, L, r.normal(0, 0.6))
        line(pts, ppm * 0.0012, v)
        for i in range(3, 19, 3):
            x, y = pts[i]
            a0 = math.atan2(pts[i + 1][1] - y, pts[i + 1][0] - x)
            ln = L * r.uniform(0.14, 0.2)
            sg = 1 if (i // 3) % 2 else -1
            poly(leaf_pts(x, y, a0 + sg * 0.8, ln, ln * 0.42, tip=0.6), v)
        x, y = pts[-1]
        poly(leaf_pts(x, y, math.atan2(y - pts[-2][1], x - pts[-2][0]), L * 0.18, L * 0.07), v)

    def blossom(cx, cy, rad, v):
        for k in range(5):
            a = k * 2 * math.pi / 5 + r.uniform(0, 1)
            poly(leaf_pts(cx, cy, a, rad, rad * 0.5, tip=0.45), v)
        disc(cx, cy, rad * 0.18, max(0, v - 60))
        line(stem(cx, cy, math.pi / 2 + r.normal(0, 0.3), rad * 3.0, r.normal(0, 0.5)), ppm * 0.0011, v)
        for sg in (1, -1):
            poly(leaf_pts(cx + sg * rad * 0.2, cy + rad * 1.8, math.pi / 2 - sg * 0.9, rad * 0.9, rad * 0.35), v)

    # semis : placement par rejet sur une grille périodique
    placed = []
    kinds = ['fern', 'daisy', 'pompon', 'leafy', 'blossom', 'leafy', 'fern']
    tries = 0
    while len(placed) < 95 and tries < 5000:
        tries += 1
        x, y = r.uniform(0, W), r.uniform(0, W)
        ok = True
        for (px_, py_) in placed:
            dx = min(abs(x - px_), W - abs(x - px_))
            dy = min(abs(y - py_), W - abs(y - py_))
            if dx * dx + dy * dy < (ppm * 0.045) ** 2:
                ok = False
                break
        if not ok:
            continue
        placed.append((x, y))
        k = kinds[len(placed) % len(kinds)]
        v = int(r.uniform(170, 245))
        up = -math.pi / 2 + r.normal(0, 0.35)
        if k == 'fern':
            fern(x, y, up, ppm * r.uniform(0.07, 0.10), v)
        elif k == 'daisy':
            daisy(x, y, ppm * r.uniform(0.011, 0.015), v)
        elif k == 'pompon':
            pompon(x, y, ppm * r.uniform(0.009, 0.012), v)
        elif k == 'leafy':
            leafy(x, y, up, ppm * r.uniform(0.06, 0.09), v)
        else:
            blossom(x, y, ppm * r.uniform(0.010, 0.014), v)
    m = np.asarray(mask.resize((N, N), Image.LANCZOS)).astype(float) / 255
    # aquarelle : l'encre varie à l'intérieur des motifs, bords un peu fondus
    ink = 0.72 + 0.28 * spectral_noise(N, N, beta=1.6, seed=172)
    a = np.clip(blur_wrap(m, 0.6) * ink, 0, 1)
    base = np.array([0.955, 0.953, 0.94])
    sage = np.array([0.50, 0.66, 0.55])
    arr = base[None, None] * (1 - a[..., None]) + sage[None, None] * a[..., None]
    # toile de lin : légère irrégularité de fil (flammes) sous l'impression
    slub = spectral_noise(N, N, beta=1.0, seed=173, aniso=(24, 1))
    arr *= (1 + slub * 0.025)[..., None]
    save('nalbjornbar', arr, q=92)
    register('nalbjornbar', size, ['nalbjornbar'])


def sofa_fabric():
    N = 1024
    h = weave(N, 14, 81, slub=0.9)
    bumps = spectral_noise(N, N, beta=0.8, seed=82)
    hh = h + bumps * 0.6
    save('tissu_canape_n', normal_from_height(blur_wrap(hh, 0.9), 1.8), q=90)
    base = np.array([0.66, 0.62, 0.57])
    alb = base[None, None] * (1 + blur_wrap(hh, 1.0)[..., None] * 0.05 + bumps[..., None] * 0.04)
    save('tissu_canape', alb, q=90)
    register('tissu_canape', 0.1, ['tissu_canape', 'tissu_canape_n'])


def knit(name, base, N=1024, size=0.3, seed=91, chunky=True):
    """Tapis tricoté / tressé (motif de mailles en V)."""
    y, x = np.mgrid[0:N, 0:N].astype(float)
    cols = 24 if chunky else 40
    rows = 32 if chunky else 56
    cw, rh = N / cols, N / rows
    u = (x % cw) / cw
    v = (y % rh) / rh
    col = np.floor(x / cw)
    # maille : deux jambes en V
    leg = np.where(u < 0.5, u * 2, (1 - u) * 2)
    vv = (v + leg * 0.5) % 1.0
    h = np.sin(vv * math.pi) * np.sin(np.clip(np.where(u < 0.5, u, 1 - u) * 2, 0, 1) * math.pi) ** 0.5
    fib = spectral_noise(N, N, beta=0.9, seed=seed, aniso=(1, 3.333))
    h = h + fib * 0.25
    save(name + '_n', normal_from_height(blur_wrap(h, 0.9), 3.0), q=90)
    tone = spectral_noise(N, N, beta=2.5, seed=seed + 1)
    alb = np.array(base)[None, None] * (0.86 + 0.18 * blur_wrap(h, 1.0)[..., None] + tone[..., None] * 0.03)
    save(name, alb, q=90)
    register(name, size, [name, name + '_n'])


def terry():
    N = 512
    loops = spectral_noise(N, N, beta=0.3, seed=101)
    save('eponge_n', normal_from_height(blur_wrap(loops, 1.0), 2.5), q=90)
    alb = np.ones((N, N, 3)) * np.array([0.90, 0.86, 0.79])[None, None] * (1 + loops[..., None] * 0.06)
    save('eponge', alb, q=90)
    register('eponge', 0.08, ['eponge', 'eponge_n'])


def cane():
    """Cannage viennois (chaises type Cesca) : 4 directions de brins, trous octogonaux."""
    N = 512
    size = 0.036
    S = 4
    W = N * S
    img = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pitch = W / 2
    wv = int(W * 0.075)
    col = (206, 160, 98, 255)
    col2 = (186, 138, 80, 255)
    for i in range(-1, 4):
        c = i * pitch + pitch / 2
        d.rectangle([c - wv / 2, 0, c + wv / 2, W], fill=col)
        d.rectangle([0, c - wv / 2, W, c + wv / 2], fill=col2)
    for i in range(-4, 6):
        o = i * pitch
        d.line([(o, 0), (o + W, W)], fill=col, width=int(wv * 0.9))
        d.line([(o + W, 0), (o, W)], fill=col2, width=int(wv * 0.9))
    img = img.resize((N, N), Image.LANCZOS)
    a = np.asarray(img).astype(float) / 255
    n = spectral_noise(N, N, beta=1.0, seed=111, aniso=(5, 1))
    rgb = a[..., :3] * (1 + n[..., None] * 0.08)
    out = np.concatenate([srgb_u8(rgb), srgb_u8(a[..., 3:4])], -1)
    save('cannage', out, q=92, lossless=True, mode='RGBA')
    hgt = a[..., 3] + n * 0.1
    save('cannage_n', normal_from_height(blur_wrap(hgt, 1.0), 2.0), q=90)
    register('cannage', size, ['cannage', 'cannage_n'], alpha=True)


# ------------------------------------------------------------- céramique
def bath_tile():
    """Carreaux 60 x 120 grège (salle de bain), joints fins."""
    N = 2048
    size = 1.2  # 1 carreau de large, 2 carreaux de haut sur 2,4 m -> motif 1,2 x 1,2
    ppm = N / size
    alb = np.ones((N, N, 3))
    base = np.array([0.43, 0.40, 0.37])
    stone = spectral_noise(N, N, beta=2.2, seed=121)
    fine = spectral_noise(N, N, beta=0.8, seed=122)
    shade = 1 + stone * 0.06 + fine * 0.02
    alb = base[None, None] * shade[..., None]
    hgt = np.zeros((N, N))
    g = max(2, int(0.002 * ppm))
    # joints : carreau 60 cm de large (2 par motif en x), 120 cm de haut (1 par motif en y)
    for xg in (0, N // 2):
        alb[:, xg:xg + g] = np.array([0.36, 0.34, 0.32])
        hgt[:, xg:xg + g] = -1
    alb[0:g, :] = np.array([0.36, 0.34, 0.32])
    hgt[0:g, :] = -1
    save('carrelage', alb, q=90)
    save('carrelage_n', normal_from_height(blur_wrap(hgt + fine * 0.05, 1.0), 2.0), q=90)
    register('carrelage', size, ['carrelage', 'carrelage_n'])


def terrace_tile():
    N = 1024
    size = 1.2
    base = np.array([0.62, 0.60, 0.57])
    n = spectral_noise(N, N, beta=1.4, seed=131)
    alb = base[None, None] * (1 + n[..., None] * 0.07)
    hgt = np.zeros((N, N))
    step = N // 3
    for k in range(3):
        alb[:, k * step:k * step + 3] *= 0.8
        alb[k * step:k * step + 3, :] *= 0.8
        hgt[:, k * step:k * step + 3] = -1
        hgt[k * step:k * step + 3, :] = -1
    save('terrasse', alb, q=88)
    save('terrasse_n', normal_from_height(blur_wrap(hgt + n * 0.1, 1.0), 2.0), q=88)
    register('terrasse', size, ['terrasse', 'terrasse_n'])


def terracotta_laminate():
    N = 512
    n = spectral_noise(N, N, beta=0.4, seed=141)
    n2 = spectral_noise(N, N, beta=2.5, seed=142)
    base = np.array([0.72, 0.38, 0.27])
    alb = base[None, None] * (1 + n[..., None] * 0.025 + n2[..., None] * 0.02)
    save('terracotta', alb, q=90)
    register('terracotta', 0.5, ['terracotta'])


def brushed_metal():
    N = 512
    s = spectral_noise(N, N, beta=0.6, seed=151, aniso=(50, 1))
    rough = 0.28 + s * 0.05
    save('brosse_r', srgb_u8(np.repeat(rough[..., None], 3, -1)), q=90)
    save('brosse_n', normal_from_height(s, 0.4), q=90)
    register('brosse', 0.2, ['brosse_r', 'brosse_n'])


# ------------------------------------------------------------- façades de la cour
def facade(name, wall_rgb, floors=7, bays=6, seed=0, shutters=True, floor_h=3.3, bay_w=2.6):
    """Façade d'immeuble triestin sur cour : enduit, fenêtres à encadrement,
    volets persiennés. 1 px = 1 cm. Largeur = bays*bay_w, hauteur = floors*floor_h."""
    r = rng(seed)
    Wm, Hm = bays * bay_w, floors * floor_h
    W, H = int(Wm * 100), int(Hm * 100)
    base = np.array(wall_rgb)
    n = spectral_noise(512, 512, beta=2.4, seed=seed + 1)
    ny = np.array(Image.fromarray(((n + 1) * 127).astype(np.uint8)).resize((W, H), Image.BILINEAR)).astype(float) / 127 - 1
    dirt = np.linspace(0.92, 1.03, H)[:, None]  # coulures en bas, plus propre en haut
    alb = base[None, None] * (1 + ny[..., None] * 0.06) * dirt[..., None]
    img = Image.fromarray(srgb_u8(alb))
    d = ImageDraw.Draw(img)
    frame = (236, 232, 222)
    glass_day = (58, 66, 74)
    for f in range(floors):
        # bandeau d'étage
        yb = H - int(f * floor_h * 100)
        d.rectangle([0, yb - 12, W, yb - 4], fill=tuple(int(c * 255 * 1.06) for c in base))
        for b in range(bays):
            cx = int((b + 0.5) * bay_w * 100)
            ww, wh = 110, 160
            sill = yb - int(floor_h * 100) + 95
            x0, x1 = cx - ww // 2, cx + ww // 2
            y1 = yb - 95 + 0
            y0 = y1 - wh
            d.rectangle([x0 - 12, y0 - 14, x1 + 12, y1 + 10], fill=frame)  # encadrement pierre
            d.rectangle([x0, y0, x1, y1], fill=glass_day)
            # menuiserie
            d.rectangle([x0, y0, x1, y1], outline=(245, 243, 238), width=6)
            d.line([(cx, y0), (cx, y1)], fill=(245, 243, 238), width=6)
            d.line([(x0, y0 + 40), (x1, y0 + 40)], fill=(245, 243, 238), width=5)
            # reflets de ciel aléatoires
            if r.random() < 0.6:
                d.polygon([(x0 + 8, y1 - 10), (x0 + 8, y0 + 50), (x0 + 40, y0 + 50)], fill=(92, 104, 118))
            if shutters and r.random() < 0.75:
                sc = (70, 88, 74) if r.random() < 0.6 else (122, 108, 90)
                openw = r.random() < 0.7
                for side in (-1, 1):
                    sx0 = x0 - 58 if side < 0 else x1 + 2
                    if not openw:
                        sx0 = x0 if side < 0 else cx
                    sw = 56 if openw else ww // 2
                    d.rectangle([sx0, y0, sx0 + sw, y1], fill=sc)
                    for ly in range(y0 + 6, y1, 9):
                        d.line([(sx0 + 4, ly), (sx0 + sw - 4, ly)], fill=tuple(int(c * 0.75) for c in sc), width=3)
    # corniche en haut
    d.rectangle([0, 0, W, 30], fill=tuple(int(min(255, c * 255 * 1.1)) for c in base))
    img = img.resize((W // 2, H // 2), Image.LANCZOS)
    img.save(os.path.join(OUT, name + '.webp'), 'WEBP', quality=86, method=6)
    register(name, [Wm, Hm], [name], kind='facade')


def facade_emissive(name, floors, bays, seed, floor_h=3.3, bay_w=2.6, lit_ratio=0.35):
    """Fenêtres éclairées la nuit (masque émissif, même gabarit que facade)."""
    r = rng(seed + 999)
    Wm, Hm = bays * bay_w, floors * floor_h
    W, H = int(Wm * 100), int(Hm * 100)
    img = Image.new('RGB', (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for f in range(floors):
        yb = H - int(f * floor_h * 100)
        for b in range(bays):
            if r.random() > lit_ratio:
                continue
            cx = int((b + 0.5) * bay_w * 100)
            ww, wh = 110, 160
            x0, x1 = cx - ww // 2, cx + ww // 2
            y1 = yb - 95
            y0 = y1 - wh
            warm = (255, int(r.uniform(170, 205)), int(r.uniform(95, 140)))
            k = r.uniform(0.35, 1.0)
            c = tuple(int(v * k) for v in warm)
            d.rectangle([x0 + 6, y0 + 6, x1 - 6, y1 - 6], fill=c)
            d.line([(cx, y0), (cx, y1)], fill=(0, 0, 0), width=6)
            d.line([(x0, y0 + 40), (x1, y0 + 40)], fill=(0, 0, 0), width=5)
    img = img.filter(ImageFilter.GaussianBlur(2)).resize((W // 4, H // 4), Image.LANCZOS)
    img.save(os.path.join(OUT, name + '.webp'), 'WEBP', quality=86, method=6)
    register(name, [Wm, Hm], [name], kind='facade_emissive')


# ------------------------------------------------------------- tableaux
def artworks():
    """Affiches abstraites (terracotta, sauge, sable), d'après l'esprit des rendus."""
    specs = {
        'affiche_arche': 'arch', 'affiche_feuille': 'leaf', 'affiche_cercles': 'circles',
        'affiche_formes': 'shapes', 'affiche_bouquet': 'bouquet', 'affiche_soleil': 'sun'}
    pal = dict(bg=(236, 226, 208), terra=(186, 104, 72), sage=(128, 142, 112), sand=(214, 186, 150),
               ochre=(206, 150, 86), dark=(90, 84, 70), rose=(214, 160, 140))
    for name, kind in specs.items():
        W, H = 600, 800
        im = Image.new('RGB', (W, H), pal['bg'])
        d = ImageDraw.Draw(im)
        if kind == 'arch':
            d.rectangle([150, 330, 450, 700], fill=pal['terra'])
            d.pieslice([150, 180, 450, 480], 180, 360, fill=pal['terra'])
            d.ellipse([380, 120, 470, 210], fill=pal['ochre'])
        elif kind == 'leaf':
            d.line([(300, 720), (300, 120)], fill=pal['sage'], width=10)
            for i, y in enumerate(range(170, 680, 70)):
                for s in (-1, 1):
                    L = 150 - i * 6
                    pts = [(300, y)]
                    for t in np.linspace(0, 1, 12):
                        pts.append((300 + s * L * t, y - 60 * t + math.sin(t * math.pi) * -34))
                    for t in np.linspace(1, 0, 12):
                        pts.append((300 + s * L * t, y - 60 * t + math.sin(t * math.pi) * 34))
                    d.polygon(pts, fill=pal['sage'])
        elif kind == 'circles':
            d.ellipse([130, 110, 470, 450], fill=pal['sage'])
            d.ellipse([200, 380, 480, 660], fill=pal['terra'])
            d.ellipse([100, 520, 260, 680], fill=pal['sand'])
        elif kind == 'shapes':
            d.ellipse([140, 140, 360, 360], fill=pal['rose'])
            d.polygon([(220, 700), (460, 700), (460, 330)], fill=pal['sage'])
            d.rectangle([120, 420, 300, 700], fill=pal['terra'])
        elif kind == 'bouquet':
            d.polygon([(230, 520), (370, 520), (400, 720), (200, 720)], fill=pal['terra'])
            for a in np.linspace(-0.9, 0.9, 7):
                ex, ey = 300 + math.sin(a) * 230, 520 - math.cos(a) * 330
                d.line([(300, 520), (ex, ey)], fill=pal['dark'], width=5)
                d.ellipse([ex - 38, ey - 38, ex + 38, ey + 38], fill=pal['sage'] if a < 0 else pal['ochre'])
        elif kind == 'sun':
            d.rectangle([0, 470, W, H], fill=pal['sand'])
            d.pieslice([140, 250, 460, 690], 180, 360, fill=pal['terra'])
            d.line([(0, 470), (W, 470)], fill=pal['dark'], width=4)
        # grain papier
        a = np.asarray(im).astype(float) / 255
        n = spectral_noise(512, 512, beta=0.5, seed=hash(name) % 1000)
        n = np.array(Image.fromarray(((n + 1) * 127).astype(np.uint8)).resize((W, H))).astype(float) / 127 - 1
        a *= (1 + n * 0.025)[..., None]
        Image.fromarray(srgb_u8(a)).save(os.path.join(OUT, name + '.webp'), 'WEBP', quality=90)
        register(name, [0.3, 0.4], [name], kind='art')


# ------------------------------------------------------------- feuillages
def leaves():
    """Atlas de feuilles (alpha) : olivier, eucalyptus, pothos, basilic, fougère."""
    W = 1024
    img = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = rng(161)

    def leaf_shape(box, color, kind):
        x0, y0, x1, y1 = box
        cx = (x0 + x1) / 2
        L = y1 - y0
        wd = x1 - x0
        pts = []
        for t in np.linspace(0, 1, 40):
            if kind == 'olive':
                w_ = math.sin(math.pi * t) ** 0.7 * wd * 0.22
            elif kind == 'euca':
                w_ = math.sin(math.pi * t) ** 0.6 * wd * 0.48
            elif kind == 'pothos':
                w_ = (math.sin(math.pi * min(1, t * 1.15)) ** 0.5) * wd * 0.46 * (1 - 0.3 * t)
            else:
                w_ = math.sin(math.pi * t) ** 0.8 * wd * 0.42
            pts.append((cx + w_, y1 - t * L))
        for t in np.linspace(1, 0, 40):
            if kind == 'olive':
                w_ = math.sin(math.pi * t) ** 0.7 * wd * 0.22
            elif kind == 'euca':
                w_ = math.sin(math.pi * t) ** 0.6 * wd * 0.48
            elif kind == 'pothos':
                w_ = (math.sin(math.pi * min(1, t * 1.15)) ** 0.5) * wd * 0.46 * (1 - 0.3 * t)
            else:
                w_ = math.sin(math.pi * t) ** 0.8 * wd * 0.42
            pts.append((cx - w_, y1 - t * L))
        d.polygon(pts, fill=color)
        vc = tuple(min(255, int(c * 1.25)) for c in color[:3]) + (255,)
        d.line([(cx, y1), (cx, y0 + L * 0.05)], fill=vc, width=max(2, int(wd * 0.03)))

    cells = {'olive': ((0, 0, 256, 512), (112, 128, 96, 255)),
             'euca': ((256, 0, 512, 512), (126, 150, 140, 255)),
             'pothos': ((512, 0, 768, 512), (70, 118, 52, 255)),
             'basil': ((768, 0, 1024, 512), (74, 130, 54, 255)),
             'ficus': ((0, 512, 256, 1024), (52, 86, 44, 255)),
             'herb': ((256, 512, 512, 1024), (96, 140, 70, 255))}
    uv = {}
    for k, (box, col) in cells.items():
        x0, y0, x1, y1 = box
        pad = 12
        leaf_shape((x0 + pad, y0 + pad, x1 - pad, y1 - pad), col, k if k in ('olive', 'euca', 'pothos') else 'basil')
        uv[k] = [x0 / W, 1 - y1 / W, x1 / W, 1 - y0 / W]
    a = np.asarray(img).astype(float) / 255
    n = spectral_noise(W, W, beta=1.5, seed=162)
    a[..., :3] *= (1 + n[..., None] * 0.1)
    # débord de couleur sous l'alpha (évite les franges sombres au mipmapping)
    rgb = a[..., :3].copy()
    al = a[..., 3]
    acc = rgb * al[..., None]
    wsum = al.copy()
    for s in (2, 4, 8, 16):
        acc_b = np.stack([np.asarray(Image.fromarray(srgb_u8(acc[..., c])).filter(ImageFilter.GaussianBlur(s))).astype(float) / 255 for c in range(3)], -1)
        w_b = np.asarray(Image.fromarray(srgb_u8(wsum)).filter(ImageFilter.GaussianBlur(s))).astype(float) / 255
        fill = acc_b / np.maximum(w_b[..., None], 1e-4)
        rgb = np.where(al[..., None] > 0.01, rgb, np.where(w_b[..., None] > 1e-3, fill, rgb))
    out = np.concatenate([srgb_u8(rgb), srgb_u8(al[..., None])], -1)
    save('feuilles', out, q=92, lossless=True, mode='RGBA')
    register('feuilles', 1.0, ['feuilles'], alpha=True, cells=uv)


def soil():
    N = 256
    n = spectral_noise(N, N, beta=0.3, seed=171)
    alb = np.array([0.24, 0.17, 0.12])[None, None] * (1 + n[..., None] * 0.25)
    save('terreau', alb, q=85)
    register('terreau', 0.2, ['terreau'])


def ceramic_pot():
    N = 512
    n = spectral_noise(N, N, beta=0.2, seed=181)
    n2 = spectral_noise(N, N, beta=2.0, seed=182)
    alb = np.array([0.80, 0.77, 0.71])[None, None] * (1 + n[..., None] * 0.04 + n2[..., None] * 0.03)
    save('gres', alb, q=88)
    save('gres_n', normal_from_height(n * 0.5, 0.8), q=88)
    register('gres', 0.3, ['gres', 'gres_n'])


ALL = dict(parquet=floor_wood, enduit=plaster, bouleau=birch, chene=oak, bambou=bamboo,
           lin=linen, nalbjornbar=floral_print, canape=sofa_fabric,
           tapis_chambre=lambda: knit('tapis_chambre', [0.84, 0.79, 0.70], size=0.35, seed=91, chunky=True),
           tapis_sejour=lambda: knit('tapis_sejour', [0.76, 0.66, 0.52], size=0.25, seed=95, chunky=False),
           plaid=lambda: knit('plaid', [0.80, 0.76, 0.69], size=0.12, seed=97, chunky=False),
           eponge=terry, cannage=cane, carrelage=bath_tile, terrasse=terrace_tile,
           terracotta=terracotta_laminate, brosse=brushed_metal, affiches=artworks,
           feuilles=leaves, terreau=soil, gres=ceramic_pot,
           facades=lambda: [facade('facade_est', [0.70, 0.42, 0.33], floors=7, bays=7, seed=301),
                            facade('facade_nord', [0.86, 0.84, 0.80], floors=7, bays=6, seed=302),
                            facade('facade_sud', [0.84, 0.72, 0.52], floors=7, bays=7, seed=303),
                            facade('facade_ouest', [0.88, 0.83, 0.72], floors=7, bays=6, seed=304),
                            facade_emissive('facade_est_nuit', 7, 7, 301),
                            facade_emissive('facade_nord_nuit', 7, 6, 302),
                            facade_emissive('facade_sud_nuit', 7, 7, 303),
                            facade_emissive('facade_ouest_nuit', 7, 6, 304)])


def main():
    names = sys.argv[1:] or list(ALL)
    mpath = os.path.join(os.path.dirname(__file__), 'manifest.json')
    if os.path.exists(mpath):
        MANIFEST.update(json.load(open(mpath)))
    for n in names:
        print('->', n, flush=True)
        ALL[n]()
    with open(mpath, 'w') as f:
        json.dump(MANIFEST, f, indent=1)
    tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print('total', round(tot / 1e6, 2), 'Mo')


if __name__ == '__main__':
    main()
