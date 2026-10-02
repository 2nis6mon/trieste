"""Lecteur minimal de fichiers Autodesk .3ds (maillages, matériaux, couleurs
diffuses) : le module bpy installé par pip n'embarque pas l'importeur 3DS.
Retourne une liste d'objets {name, verts (N,3), faces (M,3), mat_faces {mat: [i]}}
et un dictionnaire {mat: (r, g, b)}."""
import struct

import numpy as np


def _cstr(b, i):
    j = b.index(b'\0', i)
    return b[i:j].decode('latin-1'), j + 1


def lire(path):
    b = open(path, 'rb').read()
    objets, mats = [], {}

    def color(i, end):
        while i < end:
            cid, ln = struct.unpack_from('<HI', b, i)
            if cid in (0x0011, 0x0012):
                return tuple(c / 255 for c in b[i + 6:i + 9])
            if cid in (0x0010, 0x0013):
                return struct.unpack_from('<3f', b, i + 6)
            i += ln
        return None

    def walk(i, end, ctx):
        while i < end - 5:
            cid, ln = struct.unpack_from('<HI', b, i)
            if ln < 6:
                break
            body, stop = i + 6, i + ln
            if cid in (0x4D4D, 0x3D3D):
                walk(body, stop, ctx)
            elif cid == 0xAFFF:
                m = {}
                walk(body, stop, m)
                if 'name' in m:
                    mats[m['name']] = m.get('diffuse', (0.8, 0.8, 0.8))
            elif cid == 0xA000:
                ctx['name'], _ = _cstr(b, body)
            elif cid == 0xA020:
                ctx['diffuse'] = color(body, stop)
            elif cid == 0x4000:
                name, j = _cstr(b, body)
                o = {'name': name}
                walk(j, stop, o)
                if 'verts' in o and 'faces' in o:
                    objets.append(o)
            elif cid == 0x4100:
                walk(body, stop, ctx)
            elif cid == 0x4110:
                n = struct.unpack_from('<H', b, body)[0]
                ctx['verts'] = np.frombuffer(b, '<f4', n * 3, body + 2).reshape(n, 3).copy()
            elif cid == 0x4120:
                n = struct.unpack_from('<H', b, body)[0]
                f = np.frombuffer(b, '<u2', n * 4, body + 2).reshape(n, 4)[:, :3].astype(np.int64)
                ctx['faces'] = f
                ctx['mat_faces'] = {}
                walk(body + 2 + n * 8, stop, ctx)
            elif cid == 0x4130:
                mname, j = _cstr(b, body)
                n = struct.unpack_from('<H', b, j)[0]
                ctx.setdefault('mat_faces', {}).setdefault(mname, []).extend(
                    np.frombuffer(b, '<u2', n, j + 2).tolist())
            i = stop

    walk(0, len(b), {})
    return objets, mats


if __name__ == '__main__':
    import sys
    objs, mats = lire(sys.argv[1])
    allv = np.concatenate([o['verts'] for o in objs])
    print(len(objs), 'objets', sum(len(o['faces']) for o in objs), 'faces')
    print('bornes', allv.min(0).round(2), allv.max(0).round(2))
    for k, v in mats.items():
        print('mat', k, [round(c, 2) for c in v])
    for o in objs[:40]:
        print(o['name'], len(o['verts']), len(o['faces']), list(o['mat_faces'].keys()))
