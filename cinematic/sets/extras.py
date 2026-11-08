"""The rest of the cinematic's set pieces, beside the vault:

  pages()       loose Atlas pages (double-sided quads) with trail glows
  portal()      Dr Dissection's purple portal: a dark core and spinning rings
  lieutenants() five anonymous hooded silhouettes in haze, on their own stage
  night_sky()   the night sky of Anatomia: a pixel-painted backdrop the pages fly over

The lieutenants follow the README: one generic cloaked build for all five,
small changes in height and stance only, a neutral rim light the same for
each, and haze in front so the outlines stay vague.
"""
import math
import random
import bpy
import numpy as np
from mathutils import Vector, Matrix
import akcore as ak
import lightfx as fx
import pixel
import vault

V = lambda *a: Vector(a)

LIEUT_STAGE = V(60.0, 0.0, 0.0)      # where the lieutenants stand, far from the tomb
SKY_STAGE = V(-200.0, 0.0, 0.0)      # the night-sky diorama
SKY_W, SKY_H, SKY_D = 64.0, 36.0, 60.0   # backdrop size and distance from the sky camera


# ------------------------------------------------------------------ pages
def pages(coll, M, n=36, seed=11):
    """n loose pages. Each is a 0.2 x 0.26 m quad, parchment both sides, with a
    small glow sprite (its 'trail head') parented to it."""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        mb = vault.UVBuilder(f'Page{i:02d}')
        q = vault.quad(V(0, 0, 0), V(1, 0, 0), V(0, 0, 1), 0.2, 0.26)
        mb.addq(q, M['page'])
        back = vault.quad(V(0, 0.002, 0), V(-1, 0, 0), V(0, 0, 1), 0.2, 0.26)
        mb.addq(back, M['page'])
        ob = mb.build(coll)
        ob.visible_shadow = False
        ob.hide_render = True
        ob['spin'] = (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))
        out.append(ob)
    glows = []
    for i in range(n):
        g = fx.sprite(f'PageGlow{i:02d}', coll, V(0, 0, 0), 0.22, M['glow_gold'])
        g['px_sprite'] = True
        g.hide_render = True
        glows.append(g)
    return dict(obs=out, glows=glows)


# ------------------------------------------------------------------ portal
def portal(coll):
    """Vertical oval portal centred on its empty; local -Y faces out of it.
    Rings spin about local Y; scale the root from 0 to 1 to open it."""
    root = bpy.data.objects.new('Portal', None)
    coll.objects.link(root)
    core_m = ak.flat('PortalCore', '#160626', 1.0)
    rim_m = ak.flat('PortalRim', '#3a0f5a', 1.0)
    cols = ['#d6a6ff', '#9a52ee', '#ff9ae8', '#7040d8', '#efd8ff']
    mb = ak.MeshBuilder('Portal_Core')
    n = 48
    rx, rz = 0.75, 1.15
    ring = [V(math.cos(a) * rx, 0.0, math.sin(a) * rz) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    verts = [V(0, 0, 0)] + ring
    faces = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
    mb.add(dict(verts=verts, faces=faces), core_m)
    mb.add(ak.loop_tube(ring, 0.05, ring=6), rim_m)
    core = mb.build(coll, smooth=False)
    core.parent = root
    rings = []
    for i, c in enumerate(cols):
        k = 1.0 + i * 0.07
        pts = [V(math.cos(a) * rx * k, -0.02 - i * 0.01, math.sin(a) * rz * k)
               for a in np.linspace(0, 2 * math.pi * 0.72, 30)]
        m = ak.flat(f'PortalRing{i}', c, 2.2)
        pixel.noline(m)
        rb = ak.MeshBuilder(f'Portal_Ring{i}')
        rb.add(ak.tube(pts, 0.035 - i * 0.004, ring=6, per=1), m)
        r = rb.build(coll, smooth=False)
        r.parent = root
        r['speed'] = (1.6 + i * 0.45) * (1 if i % 2 else -1)
        rings.append(fx.tag(r))
    glow = fx.sprite('PortalGlow', coll, V(0, 0, 0), 2.2, fx.sprite_mat('GlowViolet', '#a060ff'))
    glow['px_sprite'] = True
    light = bpy.data.lights.new('PortalLight', 'POINT')
    light.energy = 0.0
    light.color = ak.lin('#b070ff')[:3]
    lo = bpy.data.objects.new('PortalLight', light)
    coll.objects.link(lo)
    lo.parent = root
    lo.location = V(0, -0.6, 0)
    root.scale = (0.001, 0.001, 0.001)
    return dict(root=root, core=core, rings=rings, glow=glow, light=lo)


# ------------------------------------------------------------------ lieutenants
def _cloak(mb, base, h, lean, hood_tilt, mat):
    """A generic hooded cloak: a flared cone body, sloped shoulders, a hood."""
    rings = []
    for t, r in ((0.0, 0.52), (0.25, 0.44), (0.55, 0.32), (0.78, 0.26), (0.86, 0.3)):
        z = h * t
        cx = base.x + lean * t
        rings.append([V(cx + math.cos(a) * r, base.y + math.sin(a) * r * 0.75, base.z + z)
                      for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)])
    mb.add(ak.loft(rings, closed=True, cap_end=True), mat)
    hc = V(base.x + lean * 0.95, base.y, base.z + h * 0.93)
    mb.add(ak.uv_sphere(hc, (0.2, 0.2, 0.25), segs=16, rings=10), mat)
    tip = hc + V(lean * 0.2, 0.06, 0.26 + hood_tilt)
    mb.add(ak.tube([hc + V(0, 0.04, 0.12), tip], [0.17, 0.02], ring=10, per=3), mat)


def lieutenants(coll):
    O = LIEUT_STAGE
    black = ak.flat('Lieutenant', '#040306', 1.0)
    ground = ak.flat('LieutGround', '#0a0812', 1.0)
    stage = ak.MeshBuilder('Lieut_Ground')
    stage.add(vault.box(O + V(0, 4, -0.05), (30, 30, 0.1)), ground)
    stage.build(coll, smooth=False)
    # one build for all five: only height, lean and stance differ slightly
    specs = [(-3.2, 2.05, 0.05, 0.02), (-1.6, 2.15, -0.04, 0.0), (0.0, 2.1, 0.0, 0.04),
             (1.6, 2.2, 0.04, -0.02), (3.2, 2.0, -0.05, 0.03)]
    rim_m = fx.sprite_mat('LieutRim', '#8a84a8', levels=((0.0, 0.05), (0.4, 0.14), (0.7, 0.28)))
    haze_m = fx.sprite_mat('LieutHaze', '#4a4458', levels=((0.0, 0.06), (0.5, 0.12), (0.8, 0.18)))
    figs, rims = [], []
    for i, (x, h, lean, tilt) in enumerate(specs):
        mb = ak.MeshBuilder(f'Lieutenant{i}')
        _cloak(mb, O + V(x, 2.5 + (i % 2) * 0.6, 0), h, lean, tilt, black)
        f = mb.build(coll, smooth=True)
        f.hide_render = True
        figs.append(f)
        r = fx.sprite(f'LieutRim{i}', coll, O + V(x, 3.6 + (i % 2) * 0.6, h * 0.6), 1.5, rim_m)
        r['px_sprite'] = True
        r.hide_render = True
        rims.append(r)
    haze = []
    for k in range(6):
        hz = fx.sprite(f'LieutHaze{k}', coll, O + V(-4 + k * 1.6, 1.2, 0.6 + (k % 3) * 0.4), 2.2, haze_m)
        hz['px_sprite'] = True
        haze.append(hz)
    return dict(figs=figs, rims=rims, haze=haze, cam=(O + V(0, -5.2, 1.4), O + V(0, 2.8, 1.25)))


# ------------------------------------------------------------------ the night sky of Anatomia
def _sky_image(w=320, h=180, seed=5):
    """Painted at pixel scale, row 0 = top. Returns the array and the landmark
    pixels the pages fly to."""
    rnd = np.random.default_rng(seed)
    a = np.zeros((h, w, 4), np.float32)
    a[..., 3] = 1
    yy, xx = np.mgrid[0:h, 0:w]
    bands = ['#0a1030', '#10163c', '#161c48', '#1e2254', '#2a2660', '#3a2a6a', '#4e2e70', '#683472', '#844070']
    for i, c in enumerate(bands):
        a[(yy >= i * h * 0.075)] = ak.srgb_arr(c)
    for _ in range(260):
        x, y = rnd.integers(0, w), rnd.integers(0, int(h * 0.62))
        a[y, x] = ak.srgb_arr('#dfe6ff' if rnd.random() < 0.85 else '#ffe6b0')
    # moon
    m = (xx - 252) ** 2 + (yy - 30) ** 2
    a[m < 13 ** 2] = ak.srgb_arr('#c8c8dc')
    a[m < 12 ** 2] = ak.srgb_arr('#f2f0f8')
    a[((xx - 248) ** 2 + (yy - 27) ** 2) < 9] = ak.srgb_arr('#c8c8dc')
    a[((xx - 257) ** 2 + (yy - 35) ** 2) < 5] = ak.srgb_arr('#c8c8dc')

    def ridge(x0, x1, base, amp, f1, f2, col, ph=0.0):
        xs = np.arange(x0, x1)
        top = base - amp * (0.6 * np.abs(np.sin(xs * f1 + ph)) + 0.4 * np.abs(np.sin(xs * f2 + ph * 2)))
        for x, t in zip(xs, top):
            a[int(t):, x] = ak.srgb_arr(col)
    # distant mountain range with snow caps (left)
    ridge(0, 130, 128, 46, 0.045, 0.11, '#46467c', 0.4)
    for x in range(0, 130):
        tops = np.nonzero(np.abs(a[:, x, :3] - ak.srgb_arr('#46467c')[:3]).sum(-1) < 1e-3)[0]
        if len(tops) and tops[0] < 100:
            a[tops[0]:tops[0] + 3, x] = ak.srgb_arr('#d8dcf0')
    # rolling hills under everything
    ridge(0, w, 150, 10, 0.03, 0.07, '#2c2650', 1.3)
    # dense forest (centre-left)
    for k in range(34):
        tx = 118 + k * 3 + int(rnd.integers(0, 3))
        th = int(rnd.integers(10, 20))
        for d in range(th):
            half = d // 3 + 1
            a[140 - th + d, max(0, tx - half):tx + half + 1] = ak.srgb_arr('#1c4a38' if k % 2 else '#245a44')
    # glowing caves in a cliff (centre-right)
    cliff = (xx > 196) & (xx < 246) & (yy > 112 - (xx - 196) * 0.15) & (yy < 160)
    a[cliff] = ak.srgb_arr('#43385a')
    for cx, cy in ((208, 132), (226, 124), (236, 142)):
        hole = ((xx - cx) / 5.0) ** 2 + ((yy - cy) / 4.0) ** 2 < 1
        a[hole] = ak.srgb_arr('#0a0610')
        glow = ((xx - cx) / 3.5) ** 2 + ((yy - cy - 1) / 2.6) ** 2 < 1
        a[glow] = ak.srgb_arr('#56f0c0')
    # ominous castle on a crag (right)
    crag = (xx > 256) & (yy > 108 + np.abs(xx - 285) * 0.55) & (yy < 160)
    a[crag] = ak.srgb_arr('#2a1a3a')
    for tx, tw, th in ((262, 6, 30), (272, 8, 42), (284, 7, 34), (295, 6, 26)):
        a[110 - th:112, tx:tx + tw] = ak.srgb_arr('#1e1028')
        for d in range(8):
            a[110 - th - 8 + d, tx + tw // 2 - d // 2:tx + tw // 2 + d // 2 + 1] = ak.srgb_arr('#1e1028')
        a[110 - th + 8:110 - th + 10, tx + tw // 2] = ak.srgb_arr('#ff3a3a')
    # the Temple of Anatomia in the foreground, the oculus lit from inside
    dome = ((xx - 160) / 30.0) ** 2 + ((yy - 172) / 18.0) ** 2 < 1
    a[dome | ((xx > 128) & (xx < 192) & (yy > 168))] = ak.srgb_arr('#2e2440')
    a[(np.abs(xx - 160) < 3) & (yy > 152) & (yy < 156)] = ak.srgb_arr('#ffd98a')
    for k in range(6):
        a[172:178, 134 + k * 10:136 + k * 10] = ak.srgb_arr('#c89a50')
    a[..., 3] = 1
    marks = [(70, 96), (150, 128), (224, 126), (282, 80), (24, 112), (300, 140), (110, 104), (196, 118)]
    return a, marks, (160, 152)


def night_sky(coll, M):
    O = SKY_STAGE
    img, marks, temple = _sky_image()
    h, w = img.shape[:2]
    mat = vault.flat_image('NightSky', ak.image_from_array('NightSkyArt', img), 1.25)
    mb = vault.UVBuilder('NightSkyBackdrop')
    plane_c = O + V(0, SKY_D, 0)
    mb.addq(vault.quad(plane_c, V(1, 0, 0), V(0, 0, 1), SKY_W, SKY_H), mat)
    ob = mb.build(coll)
    ob.visible_shadow = False

    def px_to_world(px, py):
        return plane_c + V((px / w - 0.5) * SKY_W, -0.5, (0.5 - py / h) * SKY_H)
    return dict(ob=ob, marks=[px_to_world(*m) for m in marks], temple=px_to_world(*temple),
                cam=(O + V(0, 0, 0), plane_c))
