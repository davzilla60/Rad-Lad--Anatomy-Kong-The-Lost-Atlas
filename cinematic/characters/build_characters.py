"""Build the cinematic characters and render review sheets.

  blender --background --python characters/build_characters.py -- [options]

Options (after --):
  --only doc|hero|hero_m   build just one character
  --turn                   render turnaround sheets to characters/renders/
  --faces                  render expression close-ups
  --nosave                 do not write characters.blend
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, 'lib'), HERE]

import bpy                      # noqa: E402
import numpy as np              # noqa: E402
from mathutils import Vector    # noqa: E402
import akcore as ak             # noqa: E402
import humanoid as hu           # noqa: E402
import pixel                    # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(HERE, 'renders')
os.makedirs(OUT, exist_ok=True)


def opt(name):
    return name in argv


def val(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def lights():
    ak.world('#2a2236', 0.55)
    ak.sun('Key', (48, 0, -16), energy=3.0, color='#fff4ea')
    ak.sun('Rim', (-62, 0, 150), energy=1.3, color='#c9b8ff')


PX = 3   # screen pixels per art pixel; --smooth renders without the pixel pass


def render_to(path):
    sc = bpy.context.scene
    if opt('--smooth'):
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    else:
        pixel.render_pixel(path, sc.render.resolution_x // PX, sc.render.resolution_y // PX, scale=PX)


def load_px(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a


def save_px(path, a):
    h, w = a.shape[:2]
    img = bpy.data.images.new('sheet', w, h, alpha=True)
    img.pixels.foreach_set(a.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def stitch(paths, out):
    tiles = [load_px(p) for p in paths]
    save_px(out, np.concatenate(tiles, axis=1))
    for p in paths:
        os.remove(p)


def turnaround(name, ch, height):
    sc = ak.setup_render(560, 1000, samples=24)
    cam = ak.camera('TurnCam', (0, -9.0, height * 0.52), (0, 0, height * 0.52), ortho=height * 1.08)
    sc.camera = cam
    arm = ch['arm']
    tiles = []
    for i, ang in enumerate((0, 35, 90, 180)):
        arm.rotation_euler = (0, 0, math.radians(ang))
        p = os.path.join(OUT, f'_{name}_{i}.png')
        render_to(p)
        tiles.append(p)
    arm.rotation_euler = (0, 0, 0)
    stitch(tiles, os.path.join(OUT, f'{name}_turnaround.png'))
    bpy.data.objects.remove(cam)


def faces(name, ch):
    sc = ak.setup_render(480, 520, samples=24)
    C = Vector(ch['P']['head_c'])
    cam = ak.camera('FaceCam', (C.x + 0.28, C.y - 1.0, C.z + 0.04), (C.x, C.y, C.z - 0.005), lens=85)
    cam.data.lens = 120
    sc.camera = cam
    tiles = []
    for nm, preset in ch['expressions'].items():
        hu.set_expression(ch['face'], preset)
        p = os.path.join(OUT, f'_{name}_face_{nm}.png')
        render_to(p)
        tiles.append(p)
    hu.set_expression(ch['face'], {})
    stitch(tiles, os.path.join(OUT, f'{name}_expressions.png'))
    bpy.data.objects.remove(cam)


TEST_POSE = {
    # bone: (x, y, z) degrees, local axes. A mid-stride walk with a gesture,
    # chosen to stress shoulders, elbows, hips, knees and fingers.
    # Axes (from the rig): thigh/upper_arm +X swings forward; knee bend is -X;
    # elbow bend is +X; arm down is -Z on .L, +Z on .R; finger curl is -X.
    'upper_arm.L': (15, 0, -40), 'forearm.L': (25, 0, 0),
    'upper_arm.R': (50, 0, 35), 'forearm.R': (65, 0, 0),
    'thigh.L': (25, 0, 0), 'shin.L': (-15, 0, 0),
    'thigh.R': (-15, 0, 0), 'shin.R': (-40, 0, 0), 'foot.R': (-15, 0, 0),
    'spine': (4, 8, 0), 'chest': (0, 6, 0), 'neck': (0, -10, 0), 'head': (-6, -12, 4),
    **{f'{f}.0{i}.L': (-30, 0, 0) for f in ('index', 'middle', 'ring', 'pinky') for i in (1, 2, 3)},
    **{f'{f}.0{i}.R': (-35, 0, 0) for f in ('middle', 'ring', 'pinky') for i in (1, 2, 3)},
}


def pose(arm, values):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = [math.radians(a) for a in values.get(pb.name, (0, 0, 0))]


def posed(name, ch, height):
    sc = ak.setup_render(1120, 1000, samples=24)
    cam = ak.camera('PoseCam', (-4.5, -7.8, height * 0.52), (0, 0, height * 0.52), ortho=height * 1.15)
    sc.camera = cam
    pose(ch['arm'], TEST_POSE)
    hu.set_expression(ch['face'], list(ch['expressions'].values())[2])
    render_to(os.path.join(OUT, f'{name}_pose_test.png'))
    pose(ch['arm'], {})
    hu.set_expression(ch['face'], {})
    bpy.data.objects.remove(cam)


def main():
    ak.reset()
    lights()
    only = val('--only')
    built = {}
    if only in (None, 'doc'):
        import doc
        built['doc'] = (doc.build(ak.collection('Dr Dissection')), 1.84)
    if only in (None, 'hero', 'hero_m'):
        try:
            import hero
        except ImportError:
            hero = None
        if hero:
            for variant in (('f', 'm') if only is None else ('m',) if only == 'hero_m' else ('f',)):
                nm = 'hero' if variant == 'f' else 'hero_m'
                built[nm] = (hero.build(ak.collection('Radiographer' + ('' if variant == 'f' else ' (male)')),
                                        variant), 1.66)
    # spread the characters out for the saved file
    xs = {'doc': -0.6, 'hero': 0.6, 'hero_m': 1.6}
    if not opt('--nosave'):
        for nm, (ch, h) in built.items():
            ch['arm'].location.x = xs.get(nm, 0)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'characters.blend'), compress=True)
    for nm, (ch, h) in built.items():
        # hide the others while rendering this one
        for other, (oc, _) in built.items():
            hide = other != nm
            for ob in oc['arm'].children_recursive + [oc['arm']]:
                ob.hide_render = hide
        ch['arm'].location.x = 0
        if opt('--turn'):
            turnaround(nm, ch, h)
        if opt('--faces'):
            faces(nm, ch)
        if opt('--pose'):
            posed(nm, ch, h)


main()
