"""Animate and render the opening cinematic, "The Theft of the Atlas".

  blender --background --python anim/cinematic.py -- [--stills 12,30.5,...] [--frames 0-1619] [--save]

Everything is driven from one timeline in code: apply(t) sets the camera,
the characters' poses and faces, the door, the light shapes, the Atlas, the
pages, the portal and the lieutenants for time t (seconds). Frames render at
FPS through lib/pixel.py at the art resolution (640x360, one pixel per art
pixel) into anim/frames/. --stills renders single moments to anim/stills/.

The game keeps its own subtitles, score and sound effects: LINES, CAPTIONS
and CUES below are written to anim/timing.json for it to schedule against
the video's currentTime.
"""
import os
import sys
import math
import json
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, 'lib'), os.path.join(ROOT, 'characters'), os.path.join(ROOT, 'sets')]

import bpy                                  # noqa: E402
from mathutils import Vector, Euler         # noqa: E402
import akcore as ak                         # noqa: E402
import humanoid as hu                       # noqa: E402
import pixel                                # noqa: E402
import vault                                # noqa: E402
import extras                               # noqa: E402
import lightfx as fx                        # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FPS = 12
W, H = 640, 360
LENGTH = 135.0
V = lambda *a: Vector(a)


def opt(n):
    return n in argv


def val(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d


# ===================================================================== script timing
# (t0, t1, who, text, expression) -- the game shows these as subtitles
LINES = [
    (24.0, 27.0, 'doc', 'At last... the Atlas of Anatomy.', 'calculating'),
    (30.6, 34.4, 'doc', 'Centuries of knowledge... and they kept it locked away in a basement.', 'amused'),
    (36.0, 38.0, 'doc', 'How terribly unimaginative.', 'calculating'),
    (41.4, 43.4, 'hero', 'Stop! Put that book back!', 'shouting'),
    (45.2, 47.6, 'doc', "Oh, I'm afraid you're a little late.", 'amused'),
    (47.9, 51.2, 'doc', "Although, I must admit... I'm impressed you made it this far.", 'calculating'),
    (51.5, 55.0, 'doc', 'Unfortunately, our little tour of the vault has reached its conclusion.', 'amused'),
    (60.0, 61.8, 'hero', 'What are you doing?!', 'shocked'),
    (62.2, 64.8, 'doc', 'Oh, merely reorganising the curriculum!', 'victorious'),
    (77.0, 80.8, 'doc', 'And there we have it. A rather comprehensive redistribution of anatomical knowledge.', 'amused'),
    (81.1, 83.4, 'doc', 'The pages are now scattered across Anatomia.', 'calculating'),
    (83.7, 86.4, 'doc', "Of course, I haven't left them entirely unattended.", 'amused'),
    (86.8, 89.8, 'doc', 'Each of my lieutenants has been entrusted with a collection of pages.', 'calculating'),
    (90.0, 95.0, 'doc', 'The bones, the muscles, the vessels, the brain... and all those wonderfully complicated organs.', 'amused'),
    (96.4, 98.4, 'doc', 'So, if you wish to reclaim the Atlas...', 'calculating'),
    (98.6, 100.4, 'doc', "You'll have to find my lieutenants...", 'calculating'),
    (100.7, 103.0, 'doc', '...and defeat every last one of them.', 'calculating'),
    (103.6, 105.5, 'hero', "You're not getting away with this!", 'shouting'),
    (107.0, 108.9, 'doc', 'My dear radiographer...', 'amused'),
    (109.1, 111.4, 'doc', 'You spend your days looking inside people.', 'calculating'),
    (111.6, 114.4, 'doc', "Let's see how well you actually know what's in there.", 'victorious'),
    (114.7, 118.9, 'doc', 'Oh, and do try not to break anything. The skeleton is rather difficult to put back together.', 'amused'),
    (128.6, 131.4, 'hero', 'Well... this is going to be a long shift.', 'wry'),
]
CAPTIONS = [(15.2, 18.0, 'Dr Dissection has arrived.')]
LIEUT_WORDS = [90.3, 91.1, 91.9, 92.7, 94.1]          # bones, muscles, vessels, brain, organs
BOLT_T = [9.7, 10.1, 10.5, 10.9, 11.3, 11.7]
CUES = ([(0.0, 'drone_on')] + [(t, 'clank') for t in BOLT_T] +
        [(12.0, 'grind'), (12.0, 'rumble'), (27.6, 'magic'), (29.3, 'pulse'), (55.2, 'magic'), (57.0, 'wind'),
         (65.0, 'burst'), (67.2, 'wind'), (75.4, 'dust')] + [(t, 'cp') for t in LIEUT_WORDS] +
        [(103.0, 'portal'), (105.6, 'laugh'), (119.2, 'implode'), (120.0, 'drone_off'), (124.6, 'flutter'),
         (126.6, 'page'), (133.4, 'flourish')] +
        [(38.0 + k * 0.17, 'step') for k in range(18)] + [(121.6 + k * 0.3, 'step') for k in range(10)])
# (t0, t1, kind) post fades: 'in' from black, 'out' to black, 'dip' through black, 'flash' white
FADES = [(0.0, 1.6, 'in'), (17.6, 18.6, 'dip'), (64.9, 65.5, 'flash'), (66.6, 67.4, 'dip'), (74.6, 75.6, 'dip'),
         (132.6, 134.4, 'out')]


# ===================================================================== small maths
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def seg(t, t0, t1):
    return ease((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t1)


def lerp(a, b, k):
    return a + (b - a) * k


def vlerp(a, b, k):
    return Vector(a).lerp(Vector(b), k)


def yaw_to(src, dst):
    d = Vector(dst) - Vector(src)
    return math.degrees(math.atan2(d.x, -d.y))


def ang_lerp(a, b, k):
    d = (b - a + 180) % 360 - 180
    return a + d * k


def track(t, keys):
    """keys: [(t, value)], eased between neighbours. value: float or Vector."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, a), (t1, b) in zip(keys, keys[1:]):
        if t <= t1:
            k = seg(t, t0, t1)
            return vlerp(a, b, k) if isinstance(a, (tuple, Vector)) else lerp(a, b, k)
    return keys[-1][1]


# ===================================================================== poses
# Rig axes (README): thigh/upper_arm +X forward; knee -X; elbow +X; arm down -Z on .L, +Z on .R;
# finger curl -X. 'neck'/'head' Y twists (look left/right). G is the arm that holds the Atlas.
REL = hu.POSES['relaxed']
G, O = 'R', 'L'
SGN = {'L': -1, 'R': 1}


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def mix(a, b, k):
    keys = set(a) | set(b)
    return {n: tuple(lerp(x, y, k) for x, y in zip(a.get(n, (0, 0, 0)), b.get(n, (0, 0, 0)))) for n in keys}


def arm(s, ux, uz, fx, curl=None):
    d = {f'upper_arm.{s}': (ux, 0, SGN[s] * uz), f'forearm.{s}': (fx, 0, 0)}
    if curl is not None:
        for f in ('index', 'middle', 'ring', 'pinky'):
            for i in (1, 2, 3):
                d[f'{f}.0{i}.{s}'] = (-curl, 0, 0)
    return d


def walk(phase, amp=1.0, run=False):
    s = math.sin(2 * math.pi * phase)
    c = math.cos(2 * math.pi * phase)
    th = (34 if run else 22) * amp
    d = {
        'thigh.L': (th * s, 0, 0), 'thigh.R': (-th * s, 0, 0),
        'shin.L': (-(10 + (45 if run else 28) * max(0.0, c)) * amp, 0, 0),
        'shin.R': (-(10 + (45 if run else 28) * max(0.0, -c)) * amp, 0, 0),
        'upper_arm.L': (6 - (32 if run else 18) * s * amp, 0, -40 if run else -46),
        'upper_arm.R': (6 + (32 if run else 18) * s * amp, 0, 40 if run else 46),
        'forearm.L': ((75 if run else 22), 0, 0), 'forearm.R': ((75 if run else 22), 0, 0),
        'spine': ((12 if run else 3) * amp, 0, 0),
    }
    return d


def bob(phase, amp=1.0, run=False):
    return abs(math.cos(2 * math.pi * phase)) * (0.05 if run else 0.025) * amp


# Dr Dissection's gestures (the Atlas, once taken, stays in hand G)
HOLD = arm(G, 32, 34, 78)
DOC_P = {
    'stand': REL,
    'glasses': merge(REL, arm(G, 74, 18, 138, curl=20), {'head': (6, 0, 0)}),
    'reach': merge(REL, arm(G, 74, 32, 12)),
    'hold': merge(REL, HOLD),
    'present': merge(REL, arm(G, 58, 30, 40), arm(O, 40, 46, 30)),
    'wave': merge(REL, HOLD, arm(O, 62, 74, 24, curl=0)),
    'flick': merge(REL, HOLD, arm(O, 160, 30, 12, curl=0), {'head': (-10, 0, 0)}),
    'brush': merge(REL, HOLD, arm(O, 26, 12, 105)),
    'brush2': merge(REL, HOLD, arm(O, 20, 22, 82)),
    'laugh': merge(REL, HOLD, arm(O, 30, 20, 95), {'head': (-16, 0, 0), 'neck': (-8, 0, 0), 'chest': (-5, 0, 0)}),
    'adjust': merge(REL, HOLD, arm(O, 74, 18, 138, curl=20)),
    'finger': merge(REL, HOLD, merge(arm(O, 88, 26, 70, curl=70), {f'index.0{i}.{O}': (0, 0, 0) for i in (1, 2, 3)})),
    'lean': merge(REL, HOLD, {'spine': (10, 0, 0), 'chest': (6, 0, 0), 'head': (-6, 0, 0)}),
}
HERO_P = {
    'stand': REL,
    'point': merge(REL, arm(G, 80, 30, 10, curl=60), {f'index.0{i}.{G}': (0, 0, 0) for i in (1, 2, 3)}),
    'shield': merge(REL, arm(O, 105, 18, 105, curl=30), arm(G, 30, 60, 40), {'spine': (-12, 0, 0), 'head': (8, 0, 0)}),
    'hold_page': merge(REL, arm('L', 38, 22, 72, curl=10), arm('R', 38, 22, 72, curl=10), {'head': (14, 0, 0)}),
    'fists': merge(REL, arm('L', 10, 40, 60, curl=80), arm('R', 10, 40, 60, curl=80)),
}


# ===================================================================== the scene
class Scene:
    pass


def build():
    ak.reset()
    ak.setup_render(W, H, samples=1)
    sc = bpy.context.scene
    S = Scene()
    S.v = vault.build(ak.collection('Vault Set'))
    M = S.v['M']
    import doc
    import hero
    S.doc = doc.build(ak.collection('Dr Dissection'))
    S.hero = hero.build(ak.collection('Radiographer'), 'f')
    ex = ak.collection('Cinematic Extras')
    S.pages = extras.pages(ex, M)
    S.portal = extras.portal(ex)
    S.lieut = extras.lieutenants(ex)
    S.sky = extras.night_sky(ex, M)
    # three trail glows behind each page, for the night-sky streaks
    S.trails = []
    for i in range(len(S.pages['obs'])):
        row = []
        for k in range(3):
            g = fx.sprite(f'PageTrail{i:02d}_{k}', ex, V(0, 0, 0), 0.5, M['glow_gold'])
            g['px_sprite'] = True
            g.hide_render = True
            row.append(g)
        S.trails.append(row)
    S.cam = ak.camera('CineCam', (0, 1, 1.7), (0, 32, 2), lens=30)
    S.cam.data.clip_end = 200
    sc.camera = S.cam
    vault.aim_sprites(S.cam)
    S.parts = {k: [S.__dict__[k]['arm']] + list(S.__dict__[k]['arm'].children_recursive) for k in ('doc', 'hero')}
    door = S.v['door']
    S.bolt_dir = []
    for b in door['bolts']:
        c = sum((v.co for v in b.data.vertices), Vector()) / len(b.data.vertices)
        S.bolt_dir.append(c.normalized())
    S.oculus_e = S.v['chamber']['oculus'].data.energy
    rnd = random.Random(7)
    n = len(S.pages['obs'])
    S.page_seed = [dict(a0=rnd.uniform(0, 2 * math.pi), r1=rnd.uniform(0.7, 1.5), h1=rnd.uniform(-0.3, 0.9),
                        w=rnd.uniform(1.6, 2.6), vx=rnd.uniform(-1.5, 1.5), vy=rnd.uniform(-1.5, 1.5),
                        up=rnd.uniform(5.0, 8.5), mark=i % len(S.sky['marks']), delay=i * 0.12,
                        dur=rnd.uniform(3.2, 4.6), arc=rnd.uniform(6, 14), jit=V(rnd.uniform(-2, 2), 0, rnd.uniform(-1.2, 1.2)))
                   for i in range(n)]
    return S


def show(obs, on):
    for o in obs:
        o.hide_render = not on


def place(ch, loc, yaw, scale=1.0):
    ch['arm'].location = Vector(loc)
    ch['arm'].rotation_euler = (0, 0, math.radians(yaw))
    ch['arm'].scale = (scale, scale, scale)


def pose(ch, values):
    hu.pose(ch['arm'], values)


def bone_tail(ch, name):
    a = ch['arm']
    return a.matrix_world @ a.pose.bones[name].tail


def bone_head(ch, name):
    a = ch['arm']
    return a.matrix_world @ a.pose.bones[name].head


def face(ch, who, t, expr):
    """Expression preset, plus lip flap while this character has a line, plus blinks."""
    preset = {k: dict(v) for k, v in ch['expressions'].get(expr, {}).items()}
    talking = any(t0 <= t <= t1 and w == who for t0, t1, w, _, _ in LINES)
    if talking:
        m = preset.setdefault('mouth', {})
        flap = 0.15 + 0.55 * abs(math.sin(t * 8.5)) * (0.6 + 0.4 * math.sin(t * 2.3))
        m['open'] = max(m.get('open', 0.0), flap)
    period = 3.7 if who == 'doc' else 4.3
    if (t % period) < 0.12:
        preset.setdefault('lids', {})['blink'] = 1.0
    hu.set_expression(ch['face'], preset)


def expr_at(who, t, default):
    for t0, t1, w, _, e in LINES:
        if w == who and t0 - 0.3 <= t <= t1 + 0.6:
            return e
    return default


def set_cam(S, loc, tgt, lens, shake=0.0, t=0.0):
    loc = Vector(loc)
    if shake:
        loc = loc + V(math.sin(t * 53.0), math.sin(t * 61.0 + 1), math.sin(t * 47.0 + 2)) * 0.03 * shake
    S.cam.location = loc
    ak.look_at(S.cam, tgt)
    S.cam.data.lens = lens


# ===================================================================== key positions
PED = vault.PED
DOC_PED = V(-0.85, 38.55, 0)             # where Doc stands at the altar (the radiographer's side of it)
HERO_SPOT = V(1.9, 36.6, 0)               # where the radiographer stops
DOC_NEAR = V(1.05, 37.45, 0)              # Doc steps up to the radiographer
PORTAL_C = V(-0.2, 38.6, 1.25)
STONE = vault.STONE
HERO_STONE = V(-1.05, 37.55, 0)


def apply(S, t):
    d, h = S.doc, S.hero
    v = S.v
    door = v['door']
    ch = v['chamber']
    # ------------------------------------------------ defaults
    show(S.parts['doc'], True)
    show(S.parts['hero'], 38.0 <= t < 135)
    show(S.lieut['figs'] + S.lieut['rims'], False)
    for row in S.trails:
        show(row, False)
    show(S.pages['obs'] + S.pages['glows'], False)
    # ------------------------------------------------ the door, bolts and spill
    for i, b in enumerate(door['bolts']):
        b.location = -S.bolt_dir[i] * 0.42 * seg(t, BOLT_T[i], BOLT_T[i] + 0.25)
    k_open = seg(t, 12.0, 14.6)
    dist = vault.DOOR['open_x'] * k_open
    door['root'].location = vault.DOOR['c'] + V(dist, 0, 0)
    door['root'].rotation_euler = (math.pi / 2, -dist / vault.DOOR['r'], 0)
    v['spill'].hide_render = k_open < 0.15
    # ------------------------------------------------ the beam, glyphs and Atlas glow
    lit = t < 29.3
    flick = 27.6 <= t < 29.3 and (int(t * FPS) * 7 % 5) < 2
    ch['beam'].hide_render = not lit
    ch['dust'].hide_render = not lit
    ch['glyph_ring'].hide_render = (not lit) or flick
    v['atlas_glow'].hide_render = not (lit or 55.2 <= t < 65.2)
    ch['oculus'].data.energy = S.oculus_e * (1.0 if lit else 0.25)
    # ------------------------------------------------ Dr Dissection
    yaw, loc, p, sc = 180.0, V(0.3, 20.0, 0), DOC_P['stand'], 1.0
    if t < 18.6:                              # 1: walking up the corridor into the light
        k = clamp((t - 14.0) / 4.2)
        loc = vlerp(V(0.3, 21.0, 0), V(0.15, 30.8, 0), k)
        ph = (t - 14.0) * 0.9
        p = walk(ph) if 14.0 <= t < 18.2 else DOC_P['stand']
        loc.z += bob(ph) if 14.0 <= t < 18.2 else 0
        yaw = 180.0
    elif t < 23.4:                            # 2: into the tomb, to the altar
        k = clamp((t - 18.6) / 4.6)
        a, b = V(-0.2, 33.6, 0), DOC_PED + V(0, -0.35, 0)
        loc = vlerp(a, b, k)
        ph = (t - 18.6) * 0.9
        p = walk(ph) if k < 1 else DOC_P['stand']
        loc.z += bob(ph) if k < 1 else 0
        yaw = yaw_to(a, b)
    else:
        loc = DOC_PED.copy()
        face_ped = yaw_to(DOC_PED, PED)
        face_hero = yaw_to(DOC_PED, HERO_SPOT)
        yaw = ang_lerp(yaw_to(DOC_PED + V(0, -0.35, 0), DOC_PED), face_ped, seg(t, 23.2, 23.9))
        if t < 26.6:
            p = mix(DOC_P['stand'], DOC_P['glasses'], seg(t, 23.6, 24.3) - seg(t, 25.6, 26.4))
        elif t < 29.4:
            p = mix(DOC_P['stand'], DOC_P['reach'], seg(t, 26.6, 27.6))
        elif t < 34.6:
            p = mix(DOC_P['reach'], DOC_P['hold'], seg(t, 29.2, 30.0))
        elif t < 36.0:                         # looks left and right
            look = math.sin((t - 34.6) / 1.4 * 2 * math.pi) * 38
            p = merge(DOC_P['hold'], {'neck': (0, look, 0)})
        elif t < 43.6:
            p = DOC_P['hold']
        elif t < 45.2:                         # turns to the radiographer
            yaw = ang_lerp(face_ped, face_hero, seg(t, 43.6, 44.8))
            p = DOC_P['hold']
        else:
            yaw = face_hero
            p = DOC_P['present'] if 51.5 <= t < 55.0 else DOC_P['hold']
        if 43.6 <= t:
            yaw = ang_lerp(face_ped, face_hero, seg(t, 43.6, 44.8))
        if 55.0 <= t < 65.0:                   # the book opens; pages rise and orbit
            p = mix(DOC_P['hold'], DOC_P['wave'], seg(t, 55.0, 55.8))
        elif 65.0 <= t < 75.6:
            p = mix(DOC_P['wave'], DOC_P['flick'], seg(t, 64.6, 65.1))
        elif 75.6 <= t < 77.0:                 # brushes off his coat
            p = DOC_P['brush'] if int((t - 75.6) * 5) % 2 == 0 else DOC_P['brush2']
        elif 81.1 <= t < 83.4:
            p = DOC_P['wave']
        if 95.2 <= t:                          # walks up to the radiographer
            k = clamp((t - 95.2) / 1.8)
            loc = vlerp(DOC_PED, DOC_NEAR, k)
            if k < 1:
                ph = (t - 95.2) * 0.9
                p = walk(ph)
                loc.z += bob(ph)
            elif t < 103.0:
                p = mix(DOC_P['hold'], DOC_P['lean'], seg(t, 100.4, 101.0))
        if 103.0 <= t:
            p = DOC_P['hold']
            if 105.5 <= t < 107.0:
                p = DOC_P['laugh']
            elif 109.1 <= t < 111.0:
                p = DOC_P['adjust']
            elif 114.7 <= t:
                p = mix(DOC_P['hold'], DOC_P['finger'], seg(t, 114.7, 115.4))
            # backs towards the portal, still facing the radiographer
            back = PORTAL_C.copy()
            back.z = 0
            back = back + (DOC_NEAR - back).normalized() * 0.45
            k = clamp((t - 111.8) / 3.0)
            loc = vlerp(DOC_NEAR, back, ease(k))
            if 0 < k < 1:
                p = merge(p, walk((t - 111.8) * -0.7, 0.6))
            sc = 1.0 - 0.95 * seg(t, 119.2, 119.9)
            loc = vlerp(loc, PORTAL_C - V(0, 0, 0.9), seg(t, 119.2, 119.9))
            yaw = face_hero + 360 * seg(t, 119.2, 119.9)
    place(d, loc, yaw, sc)
    pose(d, p)
    face(d, 'doc', t, expr_at('doc', t, 'calculating' if t > 23 else 'neutral'))
    show(S.parts['doc'], 13.9 <= t < 119.9)
    # ------------------------------------------------ the radiographer
    hp, hloc, hyaw = HERO_P['stand'], HERO_SPOT.copy(), yaw_to(HERO_SPOT, DOC_PED)
    if t < 41.0:                               # runs in
        a = V(0.2, 33.2, 0)
        k = clamp((t - 38.0) / 3.0)
        hloc = vlerp(a, HERO_SPOT, k)
        ph = (t - 38.0) * 1.5
        hp = walk(ph, run=True) if k < 1 else HERO_P['stand']
        hloc.z += bob(ph, run=True) if k < 1 else 0
        hyaw = yaw_to(a, HERO_SPOT)
    elif t < 43.6:
        hp = mix(HERO_P['stand'], HERO_P['point'], seg(t, 41.1, 41.6))
    elif 56.8 <= t < 65.6:                     # the wind pushes her back
        hp = mix(HERO_P['stand'], HERO_P['shield'], seg(t, 56.8, 57.6))
        hloc = HERO_SPOT + vlerp(V(0, 0, 0), V(0.35, -0.35, 0), seg(t, 57.0, 60.0))
    elif 65.6 <= t < 103.0:
        hloc = HERO_SPOT + V(0.35, -0.35, 0)
        hp = HERO_P['fists'] if 96.0 <= t else HERO_P['stand']
    elif 103.0 <= t < 121.6:
        hloc = HERO_SPOT + V(0.35, -0.35, 0)
        hp = HERO_P['point'] if 103.6 <= t < 105.6 else HERO_P['fists']
        hyaw = yaw_to(hloc, DOC_NEAR if t < 119 else PORTAL_C)
    elif t >= 121.6:                           # walks to the stone, takes the last page
        a = HERO_SPOT + V(0.35, -0.35, 0)
        k = clamp((t - 121.6) / 3.0)
        hloc = vlerp(a, HERO_STONE, k)
        ph = (t - 121.6) * 0.95
        hp = walk(ph) if k < 1 else HERO_P['stand']
        hloc.z += bob(ph) if k < 1 else 0
        hyaw = yaw_to(a, HERO_STONE) if k < 1 else ang_lerp(yaw_to(a, HERO_STONE), yaw_to(HERO_STONE, STONE), seg(t, 124.6, 125.4))
        if t >= 126.4:
            hp = mix(HERO_P['stand'], HERO_P['hold_page'], seg(t, 126.4, 127.6))
            hyaw = ang_lerp(yaw_to(HERO_STONE, STONE), yaw_to(HERO_STONE, V(0.2, 36.0, 0)), seg(t, 127.6, 128.6))
    place(h, hloc, hyaw)
    pose(h, hp)
    face(h, 'hero', t, expr_at('hero', t, 'shocked' if 56.8 <= t < 66 or 119 <= t < 121 else 'determined'))
    bpy.context.view_layer.update()
    # ------------------------------------------------ the Atlas
    book = v['atlas']
    if t < 29.3:
        book.location = PED + V(0, 0, 1.85 + 0.03 * math.sin(t * 2.0))
        book.rotation_euler = (math.radians(8), 0, math.radians(20 + t * 6))
        if t >= 27.8:                          # it drifts to his outstretched hand
            book.location = vlerp(book.location, bone_tail(d, f'hand.{G}') + V(0, 0, 0.08), seg(t, 27.8, 29.3))
        book.scale = (1, 1, 1)
        book.hide_render = False
    else:
        hand = bone_tail(d, f'hand.{G}')
        wrist = bone_head(d, f'hand.{G}')
        book.location = hand + (hand - wrist).normalized() * 0.06
        if 55.2 <= t < 65.2:                   # held up open-flat and glowing
            book.location = book.location + V(0, 0, 0.12 * seg(t, 55.2, 56.0))
            book.rotation_euler = (math.radians(90 * seg(t, 55.2, 56.0)), 0, math.radians(yaw))
        else:
            book.rotation_euler = (math.radians(20), 0, math.radians(yaw + 90))
        book.scale = (sc, sc, sc)
        book.hide_render = t >= 119.9
    v['atlas_glow'].location = book.location
    v['atlas_glow'].scale = (1.6, 1.6, 1.6) if 55.2 <= t < 65.2 else (1, 1, 1)
    # ------------------------------------------------ pages: orbit, burst, the last page
    centre = DOC_PED + V(0, 0, 1.2)
    obs, glows = S.pages['obs'], S.pages['glows']
    if 56.6 <= t < 67.0:
        for i, (ob, g) in enumerate(zip(obs, glows)):
            q = S.page_seed[i]
            born = 56.6 + i * 0.05
            if t < born:
                continue
            u = t - born
            r = lerp(0.15, q['r1'], ease(u / 1.4))
            a = q['a0'] + u * q['w']
            pos = centre + V(math.cos(a) * r, math.sin(a) * r, lerp(0.1, q['h1'], ease(u / 1.4)))
            if t >= 65.0:                      # the burst: up and out through the oculus
                ub = t - 65.0
                pos = pos + V(q['vx'] * ub * 0.6, q['vy'] * ub * 0.6, q['up'] * 0.45 * ub + 2.0 * ub * ub)
            sp = ob['spin']
            ob.location = pos
            ob.rotation_euler = (sp[0] * t * 3, sp[1] * t * 3, a + math.pi / 2)
            ob.scale = (1, 1, 1)
            g.location = pos
            g.scale = (0.5, 0.5, 0.5)
            show([ob, g], True)
    elif 67.0 <= t < 75.0:                     # streaks across the sky of Anatomia
        for i, (ob, g) in enumerate(zip(obs, glows)):
            q = S.page_seed[i]
            u = (t - 67.0 - q['delay'] * 0.5) / q['dur']
            if not (0.0 < u < 1.0):
                continue
            a = S.sky['temple']
            b = S.sky['marks'][q['mark']] + q['jit']

            def at(x):
                return vlerp(vlerp(a, (a + b) / 2 + V(0, 0, q['arc']), x), vlerp((a + b) / 2 + V(0, 0, q['arc']), b, x), x)
            pos = at(u)
            fade = 1.0 - seg(u, 0.75, 1.0)
            ob.location = pos
            ob.rotation_euler = (t * 4 + i, t * 3, i)
            ob.scale = (2.2 * fade + 0.01,) * 3
            g.location = pos
            g.scale = (1.8 * fade + 0.01,) * 3
            show([ob, g], fade > 0.05)
            for k, tr in enumerate(S.trails[i]):
                tr.location = at(max(0.0, u - 0.025 * (k + 1)))
                s2 = 1.5 * fade * (1 - 0.25 * k)
                tr.scale = (s2 + 0.01,) * 3
                tr.hide_render = fade < 0.05
    elif t >= 124.0:                           # the one page left behind, under the stone
        ob, g = obs[0], glows[0]
        ob.scale = (1, 1, 1)
        stuck = STONE + V(0.32, -0.12, 0.03)
        if t < 126.4:
            wig = math.sin(t * 22) * 0.35 * seg(t, 124.4, 124.8)
            ob.location = stuck
            ob.rotation_euler = (math.radians(-80), wig, 0.4)
            g.hide_render = True
            ob.hide_render = False
        else:
            hl, hr = bone_tail(h, 'hand.L'), bone_tail(h, 'hand.R')
            fwd = V(math.sin(math.radians(hyaw)), -math.cos(math.radians(hyaw)), 0)
            held = (hl + hr) / 2 + fwd * 0.08 + V(0, 0, -0.02)
            k = seg(t, 126.4, 128.0)
            pos = vlerp(stuck, held, k) + V(math.sin(t * 5) * 0.12 * (1 - k), 0, math.sin(k * math.pi) * 0.6)
            ob.location = pos
            ob.rotation_euler = (math.radians(lerp(-80, -50, k)), math.sin(t * 4) * 0.4 * (1 - k), math.radians(hyaw))
            g.location = pos
            g.scale = (0.5, 0.5, 0.5)
            show([ob, g], True)
    # ------------------------------------------------ the portal
    pr = S.portal
    k_portal = seg(t, 103.0, 104.4) * (1 - seg(t, 119.9, 120.6))
    pr['root'].location = PORTAL_C
    pr['root'].rotation_euler = (0, 0, math.radians(yaw_to(PORTAL_C, HERO_SPOT)))
    s = max(0.001, k_portal)
    pr['root'].scale = (s, s, s)
    for r in pr['rings']:
        r.rotation_euler = (0, t * r['speed'], 0)
    pr['glow'].location = PORTAL_C
    pr['glow'].scale = (s, s, s)
    pr['glow'].hide_render = k_portal < 0.02
    pr['light'].data.energy = 400 * k_portal
    for o in [pr['core']] + pr['rings']:
        o.hide_render = k_portal < 0.02
    # ------------------------------------------------ the lieutenants
    for i, (f, r) in enumerate(zip(S.lieut['figs'], S.lieut['rims'])):
        f.hide_render = r.hide_render = not (86.6 <= t < 95.4 and t >= LIEUT_WORDS[i])
    # ------------------------------------------------ camera
    camera(S, t, d, h)


def head_of(ch, up=0.0):
    return bone_head(ch, 'head') + V(0, 0, 0.08 + up)


def camera(S, t, d, h):
    door_c = vault.DOOR['c']
    if t < 9.4:                                # 1: down the corridor
        k = clamp(t / 9.4)
        set_cam(S, vlerp(V(0.6, 1.0, 1.75), V(0.4, 21.5, 1.6), ease(k)), vlerp(V(0, 32, 2.6), door_c, k), 30)
    elif t < 12.0:                             # the bolts
        set_cam(S, V(2.0, 23.0, 1.45), door_c + V(0, 0, 0.1), 38, shake=0.4 if t > 9.6 else 0, t=t)
    elif t < 14.2:                             # the door grinds open
        set_cam(S, vlerp(V(1.6, 21.0, 1.5), V(1.2, 19.5, 1.55), seg(t, 12, 14.2)), door_c, 34, shake=1.2, t=t)
    elif t < 18.6:                             # Doc in silhouette, into the light
        set_cam(S, V(-1.2, 14.0, 1.6), V(0.3, 32.0, 2.2), 32)
    elif t < 23.6:                             # 2: following him in
        dl = d['arm'].location
        set_cam(S, dl + V(1.6, -3.4, 1.9), dl + V(-0.2, 3.0, 1.2), 30)
    elif t < 27.2:                             # "At last..."
        set_cam(S, vlerp(V(0.9, 38.0, 1.85), V(0.7, 38.2, 1.85), seg(t, 23.6, 27.2)), head_of(d, -0.1), 46)
    elif t < 34.6:                             # the reach, the take, "Centuries..."
        set_cam(S, V(1.4, 37.4, 1.95), V(-0.4, 38.9, 1.45), 32, shake=1.0 if 29.3 <= t < 30.3 else 0, t=t)
    elif t < 38.0:                             # looks around: "How terribly unimaginative."
        set_cam(S, V(0.7, 38.2, 1.8), head_of(d, -0.15), 42)
    elif t < 41.2:                             # 3: the radiographer runs in
        set_cam(S, V(5.6, 34.0, 3.4), V(-0.4, 39.8, 1.2), 22)
    elif t < 43.6:                             # "Stop!"
        hd = h['arm'].location
        set_cam(S, hd + V(-1.3, 1.3, 1.6), head_of(h, -0.1), 42)
    elif t < 45.2:                             # he turns
        set_cam(S, V(2.9, 35.7, 1.8), V(-0.8, 39.4, 1.55), 34)
    elif t < 55.0:                             # over her shoulder
        set_cam(S, V(3.5, 35.8, 1.95), head_of(d, -0.25), 38 if t < 51.4 else 44)
    elif t < 57.0:                             # 4: the book opens
        set_cam(S, vlerp(V(1.4, 37.9, 1.7), V(0.4, 38.6, 1.75), seg(t, 55, 57)), V(-1.0, 39.45, 1.55), 42)
    elif t < 60.0:                             # the vortex
        set_cam(S, V(3.8, 35.0, 2.5), V(-0.2, 38.8, 1.4), 24)
    elif t < 62.0:                             # "What are you doing?!"
        hd = h['arm'].location
        set_cam(S, hd + V(-1.4, 1.1, 1.5), head_of(h, -0.1), 40, shake=0.3, t=t)
    elif t < 65.0:                             # "Merely reorganising the curriculum!"
        set_cam(S, V(1.3, 37.3, 1.9), head_of(d, -0.15), 46)
    elif t < 67.0:                             # the burst, up through the oculus
        set_cam(S, V(-2.6, 36.4, 0.7), vlerp(V(-0.7, 38.8, 2.0), V(-0.2, 39.5, 7.5), seg(t, 65, 66.8)), 20,
                shake=1.4, t=t)
    elif t < 75.0:                             # the night sky of Anatomia
        c, tgt = S.sky['cam']
        set_cam(S, c + V(0, 0, 0), tgt + vlerp(V(-4, 0, -3), V(3, 0, 0), seg(t, 67, 75)),
                lerp(36, 40, seg(t, 67, 75)))
    elif t < 86.6:                             # 5: "And there we have it."
        set_cam(S, vlerp(V(0.75, 37.5, 1.8), V(0.6, 37.8, 1.8), seg(t, 75, 86.6)), head_of(d, -0.25), 36)
    elif t < 95.4:                             # the lieutenants
        c, tgt = S.lieut['cam']
        set_cam(S, vlerp(c, c + V(0, 1.6, -0.1), seg(t, 86.6, 95.4)), tgt, 30)
    elif t < 100.6:                            # he walks up to her
        set_cam(S, V(-1.6, 34.1, 1.7), V(1.5, 37.1, 1.45), 32)
    elif t < 103.0:                            # "...and defeat every last one of them."
        set_cam(S, vlerp(V(2.7, 35.9, 1.85), V(2.5, 36.1, 1.85), seg(t, 100.6, 103)), head_of(d, -0.15), 48)
    elif t < 111.6:                            # 6: the portal; the laugh
        set_cam(S, V(-2.4, 34.2, 1.9), V(0.7, 37.7, 1.4), 28)
    elif t < 114.6:                            # "Let's see how well you know..."
        set_cam(S, V(1.9, 36.9, 1.8), head_of(d, -0.15), 46)
    elif t < 121.6:                            # backs into the portal; it implodes
        set_cam(S, V(-2.0, 34.6, 1.8), V(0.4, 38.2, 1.3), 30, shake=0.8 if 119.2 <= t < 120.8 else 0, t=t)
    elif t < 124.6:                            # 7: alone; to the stone
        set_cam(S, V(2.6, 35.0, 2.2), V(-0.8, 38.4, 1.0), 28)
    elif t < 126.4:                            # the page under the stone
        set_cam(S, V(-2.8, 37.2, 0.65), STONE + V(0.2, 0, 0.1), 40)
    elif t < 129.0:                            # it floats into her hands
        set_cam(S, V(-0.2, 36.2, 1.75), head_of(h, -0.3), 36)
    else:                                      # "a long shift"; the camera pulls back
        set_cam(S, vlerp(V(-0.2, 36.2, 1.75), V(4.2, 33.8, 4.6), seg(t, 129.5, 134.4)),
                vlerp(head_of(h, -0.3), V(-0.6, 39.0, 1.0), seg(t, 129.5, 134.4)),
                lerp(36, 22, seg(t, 129.5, 134.4)))


# ===================================================================== fades + render
def fade_factor(t):
    """(multiplier, white) for the post fade at time t."""
    mul, white = 1.0, 0.0
    for t0, t1, kind in FADES:
        if not (t0 <= t <= t1):
            continue
        k = (t - t0) / (t1 - t0)
        if kind == 'in':
            mul = min(mul, k)
        elif kind == 'out':
            mul = min(mul, 1 - k)
        elif kind == 'dip':
            mul = min(mul, abs(1 - 2 * k))
        elif kind == 'flash':
            white = max(white, 1 - abs(1 - 2 * k))
    # step the fade like a palette fade, not a smooth blend
    return round(mul * 6) / 6, round(white * 6) / 6


def render_at(S, t, path):
    apply(S, t)
    out = pixel.render_pixel(path, W, H, scale=1, bg='#000000')
    mul, white = fade_factor(t)
    if mul < 1 or white > 0:
        out = out.copy()
        out[..., :3] = out[..., :3] * mul + white * (1 - out[..., :3] * mul) * 0.85
        pixel._save(path, out)


def write_timing():
    data = dict(fps=FPS, length=LENGTH,
                lines=[dict(t0=a, t1=b, who=w, text=x) for a, b, w, x, _ in LINES],
                captions=[dict(t0=a, t1=b, text=x) for a, b, x in CAPTIONS],
                cues=sorted([dict(t=a, sfx=s) for a, s in CUES], key=lambda c: c['t']))
    with open(os.path.join(HERE, 'timing.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)


def main():
    write_timing()
    S = build()
    if opt('--save'):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'cinematic.blend'), compress=True)
    if val('--stills'):
        out = os.path.join(HERE, 'stills')
        os.makedirs(out, exist_ok=True)
        for s in val('--stills').split(','):
            t = float(s)
            render_at(S, t, os.path.join(out, f't{t:06.1f}.png'))
            print(f'STILL {t}', flush=True)
    if val('--frames'):
        a, b = (int(x) for x in val('--frames').split('-'))
        out = os.path.join(HERE, 'frames')
        os.makedirs(out, exist_ok=True)
        for f in range(a, b + 1):
            p = os.path.join(out, f'f{f:04d}.png')
            if os.path.exists(p) and not opt('--redo'):
                continue
            render_at(S, f / FPS, p)
            print(f'FRAME {f}', flush=True)


main()
