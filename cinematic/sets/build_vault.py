"""Build the vault set (with the characters for scale) and render test shots.

  blender --background --python sets/build_vault.py -- [--shots a,b,c] [--nosave] [--smooth]

Shots: corridor (scene 1 opening), door (the bolts), spill (door open, light
pouring out), vault (wide chamber), pedestal (Doc at the Atlas).
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, 'lib'), os.path.join(ROOT, 'characters'), HERE]

import bpy                      # noqa: E402
from mathutils import Vector    # noqa: E402
import akcore as ak             # noqa: E402
import humanoid as hu           # noqa: E402
import pixel                    # noqa: E402
import vault                    # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(HERE, 'renders')
os.makedirs(OUT, exist_ok=True)
W, H, PX = 640, 360, 3

SHOTS = {
    # name: (camera location, look-at target, lens mm)
    'corridor': ((0.6, 1.0, 1.75), (0.0, 32.0, 2.6), 30),
    'door': ((2.2, 22.0, 1.4), (0.0, 32.0, 2.4), 40),
    'spill': ((-1.2, 14.0, 1.6), (0.3, 32.0, 2.2), 32),
    'vault': ((5.6, 34.0, 3.4), (-0.6, 41.5, 1.2), 22),
    'mural': ((0.0, 35.2, 2.2), (0.0, 46.0, 4.0), 24),
    'frieze': ((-3.5, 36.0, 3.3), (6.5, 41.5, 4.6), 26),
    'pedestal': ((-3.6, 35.4, 1.7), (0.0, 39.5, 1.45), 34),
}


def opt(n):
    return n in argv


def val(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d


def place(ch, loc, yaw_deg):
    ch['arm'].location = loc
    ch['arm'].rotation_euler = (0, 0, math.radians(yaw_deg))


def main():
    ak.reset()
    sc = ak.setup_render(W * PX, H * PX, samples=16)
    coll = ak.collection('Vault Set')
    S = vault.build(coll)
    import doc
    import hero
    d = doc.build(ak.collection('Dr Dissection'))
    hr = hero.build(ak.collection('Radiographer'), 'f')
    hu.pose(d['arm'], 'relaxed')
    hu.pose(hr['arm'], 'relaxed')
    want = (val('--shots') or ','.join(SHOTS)).split(',')
    if not opt('--nosave'):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'vault.blend'), compress=True)
    for name in want:
        loc, tgt, lens = SHOTS[name]
        cam = ak.camera('Cam_' + name, loc, tgt, lens=lens)
        cam.data.clip_end = 120
        sc.camera = cam
        vault.aim_sprites(cam)
        S['spill'].hide_render = name != 'spill'
        bolts_in = name == 'spill'
        door = S['door']
        door['root'].location = vault.DOOR['c'] + (Vector((vault.DOOR['open_x'], 0, 0)) if name == 'spill' else Vector())
        # put the characters where each shot needs them
        hide_hero = True
        if name in ('corridor', 'door'):
            place(d, (0.4, 22.0 if name == 'corridor' else 27.6, 0), 180 + 0)
        elif name == 'spill':
            place(d, (0.2, 27.5, 0), 180)
        elif name == 'vault':
            place(d, (-0.9, 38.4, 0), -130)
            place(hr, (2.4, 36.0, 0), 150)
            hide_hero = False
        else:
            place(d, (-1.15, 38.55, 0), -125)
        for ob in hr['arm'].children_recursive + [hr['arm']]:
            ob.hide_render = hide_hero
        hu.set_expression(d['face'], d['expressions']['calculating'] if name == 'pedestal' else {})
        path = os.path.join(OUT, f'vault_{name}.png')
        if opt('--smooth'):
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
        else:
            pixel.render_pixel(path, W, H, scale=PX, bg='#000000')
        bpy.data.objects.remove(cam)


main()
