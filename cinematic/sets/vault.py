"""The Grand Vault: an ancient tomb that holds the Atlas.

Layout (metres, Z up). The corridor runs along +Y from y=0 to the end wall at
y=32. The round door sits in a slot between the corridor face (y=32) and the
tomb face (y=32.9) and rolls sideways (+X) into the wall. The tomb runs from
y=32.9 to y=46, x = +-7, with the altar under a ceiling oculus.

The idea: the Atlas began as the first illustration of the inside of the
body. Its original is painted on the tomb's back wall, and glowing gold
threads run from it along a frieze to painted panels of everything it led to:
anatomy through history on the left wall, imaging today (X-ray, CT, MRI,
ultrasound) on the right. The stone is old, worn, cracked and cobwebbed.
"""
import math
import random
import numpy as np
import bpy
from mathutils import Vector, Matrix
import akcore as ak
import lightfx as fx
import pixel
import stonework as sw
import ancient_art as art

V = lambda *a: Vector(a)

CORR = dict(x=3.5, len=32.0, h=6.5)
DOOR = dict(c=V(0, 32.45, 2.25), r=2.1, t=0.45, open_x=4.6)
ROOM = dict(y0=32.9, y1=46.0, x=7.0, h=8.0)
PED = V(0, 39.5, 0)
STONE = V(-1.7, 38.2, 0)
FRIEZE = dict(z0=4.35, z1=5.75, thread_z=5.95)


# ------------------------------------------------------------------ pixel icons
ICONS = {
    'skull': ["..XXXXXX..", ".XXXXXXXX.", "XXXXXXXXXX", "XX..XX..XX", "XX..XX..XX", "XXXXXXXXXX",
              ".XXXX.XXX.", "..XXXXXX..", "..X.XX.X..", "..XXXXXX.."],
    'heart': [".XX....XX.", "XXXX..XXXX", "XXXXXXXXXX", "XXXXXXXXXX", "XXXXXXXXXX", ".XXXXXXXX.",
              "..XXXXXX..", "...XXXX...", "....XX....", ".........."],
    'bone': [".XX.......", "XXXX......", ".XXXX.....", "..XXXX....", "...XXXX...", "....XXXX..",
             ".....XXXX.", "......XXXX", ".......XX.", ".........."],
    'brain': ["..XXXXXX..", ".XX.XX.XX.", "XXXXXXXXXX", "X.XX.XX.XX", "XXXXXXXXXX", "XX.XXXX.XX",
              ".XXXXXXXX.", "...XX.....", "...XX.....", ".........."],
    'rib': ["....XX....", ".XXXXXXXX.", "X...XX...X", ".XXXXXXXX.", "X...XX...X", ".XXXXXXXX.",
            "X...XX...X", ".XXXXXXXX.", "....XX....", ".........."],
    **art.ICONS,
}
# the floor ring alternates anatomy and imaging
RING = ['figure', 'xray', 'skull', 'ct', 'heart', 'mri', 'brain', 'us', 'bone', 'xray', 'rib', 'ct']


def icon_image(name, kind, fg='#ffd27a', bg='#1a1d25', pad=3):
    rows = ICONS[kind]
    n = len(rows) + pad * 2
    a = np.zeros((n, n, 4), np.float32)
    if bg:
        a[:] = ak.srgb_arr(bg)
        a[..., 3] = 1
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == 'X':
                a[y + pad, x + pad] = ak.srgb_arr(fg)
                a[y + pad, x + pad, 3] = 1
    return ak.image_from_array(name, a)


def page_image():
    w, h = 32, 40
    a = np.zeros((h, w, 4), np.float32)
    a[:] = ak.srgb_arr('#e6d6b0')
    ink = ak.srgb_arr('#7a5a3a')
    for y in range(6, 36, 3):
        a[y, 4:28 if y % 9 else 18] = ink
    a[8:18, 18:28] = ak.srgb_arr('#b8805a')
    a[..., 3] = 1
    return ak.image_from_array('AtlasPage', a)


# ------------------------------------------------------------------ materials
def flat_image(name, img, strength=1.0, alpha=False):
    """Unlit image. alpha=True: transparent where the image is."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    ak._use_nodes(m)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Closest'
    emi = nt.nodes.new('ShaderNodeEmission')
    emi.inputs['Strength'].default_value = strength
    nt.links.new(tex.outputs['Color'], emi.inputs['Color'])
    if alpha:
        fx._blended(m)
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Alpha'], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(emi.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(emi.outputs[0], out.inputs['Surface'])
    return m


def materials(rnd):
    t = ak.toon
    M = {
        # corridor: old blue-grey stone
        'cs0': t('Corr_Stone0', '#2e3443'), 'cs1': t('Corr_Stone1', '#373d4c'), 'cs2': t('Corr_Stone2', '#292f3c'),
        'cs3': t('Corr_Stone3', '#323a44'), 'cstain': t('Corr_StoneStain', '#22262e'),
        'cmortar': t('Corr_Mortar', '#0f1115'), 'niche': t('Corr_Niche', '#171a21'),
        'cf0': t('Corr_Flag0', '#3a3e49'), 'cf1': t('Corr_Flag1', '#32363f'), 'cf2': t('Corr_Flag2', '#2c3038'),
        'cgrout': t('Corr_Grout', '#0d0e11'), 'crubble': t('Corr_Rubble', '#3c414c'),
        'wood': t('Corr_Beam', '#3e2e1a'), 'wood_rot': t('Corr_BeamRot', '#33261a'), 'ceil': t('Corr_Ceiling', '#0c0d10'),
        'frame0': t('Frame_Stone0', '#4a4a54'), 'frame1': t('Frame_Stone1', '#5a5a65'),
        'rail': t('Door_Rail', '#4e5260', hl='#aab0bc', hl_rough=0.2),
        # door
        'gold': t('Gold', '#d0993a', hl='#fff2b8', hl_rough=0.22, hl_cut=0.5),
        'gold_dk': t('GoldDark', '#9c6a1e', hl='#e8c070', hl_rough=0.25, hl_cut=0.55),
        'gold_lt': t('GoldLight', '#e2b85a', hl='#fff8d8', hl_rough=0.2, hl_cut=0.5),
        # torches
        'iron': t('Iron', '#2a2622', hl='#7a6a5a', hl_rough=0.3),
        'flame': ak.flat('Flame', '#ff8a2a', 2.0), 'flame_core': ak.flat('FlameCore', '#ffe58a', 2.5),
        # tomb stone: weathered sandstone
        'ts0': t('Tomb_Stone0', '#7a6650'), 'ts1': t('Tomb_Stone1', '#6c5944'), 'ts2': t('Tomb_Stone2', '#857058'),
        'ts3': t('Tomb_Stone3', '#736050'), 'tstain': t('Tomb_StoneStain', '#564434'),
        'tmortar': t('Tomb_Mortar', '#1c140d'),
        'tf0': t('Tomb_Slab0', '#6a5844'), 'tf1': t('Tomb_Slab1', '#5e4e3c'), 'tf2': t('Tomb_Slab2', '#76624c'),
        'tgrout': t('Tomb_Grout', '#140e09'), 'trubble': t('Tomb_Rubble', '#6e5c48'),
        'tceil': t('Tomb_Ceiling', '#3a2e22'), 'tceil2': t('Tomb_Ceiling2', '#332819'),
        'column': t('Tomb_Column', '#86725a'), 'column_cap': t('Tomb_ColumnCap', '#6e5c47'),
        'plaster': t('Tomb_Plaster', '#a99270'), 'tniche': t('Tomb_Niche', '#4a3828'),
        'root': t('Root', '#3a2a1a'), 'web': ak.flat('Cobweb', '#b8b2c0', 1.0),
        'thread': ak.flat('GoldThread', '#ffcf6a', 1.5),
        'scroll': t('Scroll', '#d8c898'), 'scroll_end': t('ScrollEnd', '#a88a5a'),
        'tablet': t('ClayTablet', '#9a6a44'), 'tablet_dk': t('ClayTabletDark', '#7a5034'),
        'jar0': t('Canopic0', '#c8b48a', hl='#f4ead0', hl_rough=0.3), 'jar1': t('Canopic1', '#a88e64'),
        'jarlid0': t('CanopicLid0', '#5a7a8a'), 'jarlid1': t('CanopicLid1', '#8a5a3a'),
        'skull': t('Skull', '#e2d6b8'),
        'altar0': t('Altar0', '#9a8a74'), 'altar1': t('Altar1', '#857662'), 'altar2': t('Altar2', '#a89884'),
        'stone': t('LooseStone', '#8a7c68'),
        'glyphring': ak.flat('GlyphRing', '#ffc86a', 1.6),
        'sky': ak.flat('OculusSky', '#fff1c4', 2.0),
        # the Atlas
        'leather': t('Atlas_Leather', '#4a2a1c', hl='#8a5a40', hl_rough=0.3, hl_cut=0.6),
        'cover': t('Atlas_Cover', '#ffffff', image=art.cover(rnd).image('AtlasCover')),
        'pages': t('Atlas_Pages', '#ddd0aa'),
        'page': t('Atlas_Page', '#ffffff', image=page_image()),
        'corner': t('Atlas_Corner', '#b88a3a', hl='#f0d890', hl_rough=0.2),
        # light shapes
        'beam': fx.beam_mat('Beam', '#ffd98a', invert=True, levels=((0.2, 0.05), (0.5, 0.1), (0.8, 0.17))),
        'spill': fx.beam_mat('DoorSpill', '#ffd08a', axis='Y', invert=False, edge=False,
                             levels=((0.1, 0.08), (0.4, 0.16), (0.75, 0.28))),
        'glow_warm': fx.sprite_mat('GlowWarm', '#ffb050'),
        'glow_gold': fx.sprite_mat('GlowGold', '#ffd98a'),
        'dust': ak.flat('Dust', '#fff0c0', 1.5),
    }
    # the first illustration and the eight frieze panels (paint on plaster)
    M['first'] = t('FirstIllustration', '#ffffff', image=art.first_illustration(rnd).image('FirstIllustration'))
    for side, fns in (('L', art.LEFT), ('R', art.RIGHT)):
        for i, fn in enumerate(fns):
            M[f'panel_{side}{i}'] = t(f'Frieze_{side}{i}', '#ffffff', image=fn(rnd).image(f'Frieze_{side}{i}'))
    for k in ICONS:
        M['glyph_' + k] = flat_image('Glyph_' + k, icon_image('Icon_' + k, k, fg='#7ad8ff', bg=None), 1.3, alpha=True)
        M['glyph_' + k + '_gold'] = flat_image('GlyphGold_' + k, icon_image('IconGold_' + k, k, bg=None), 1.5,
                                               alpha=True)
        M['engrave_' + k] = flat_image('Engrave_' + k, icon_image('IconEngrave_' + k, k, fg='#4a2c08', bg=None), 1.0,
                                       alpha=True)
    pixel.noline(M['dust'], M['flame'], M['flame_core'], M['web'], M['thread'])
    return M


# ------------------------------------------------------------------ geometry helpers
def box(c, s, rot=None):
    c = Vector(c)
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    vs = [Vector((x, y, z)) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    if rot is not None:
        vs = [rot @ v for v in vs]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return dict(verts=[c + v for v in vs], faces=faces)


def lathe(profile, seg=64, centre=V(0, 0, 0)):
    """Revolve (r, h) profile points round the Y axis."""
    rings = []
    for r, h in profile:
        rings.append([centre + V(math.cos(2 * math.pi * k / seg) * r, h, math.sin(2 * math.pi * k / seg) * r)
                      for k in range(seg)])
    return ak.fix_normals(ak.loft(rings))


def plane_grid(mb, x0, x1, y0, y1, z, mat, hole=None, cell=0.5, down=True):
    verts, faces = [], []
    nx, ny = int((x1 - x0) / cell + 0.999), int((y1 - y0) / cell + 0.999)
    for i in range(nx):
        for k in range(ny):
            a0, a1 = x0 + i * cell, min(x0 + (i + 1) * cell, x1)
            b0, b1 = y0 + k * cell, min(y0 + (k + 1) * cell, y1)
            if hole and hole((a0 + a1) / 2, (b0 + b1) / 2):
                continue
            b = len(verts)
            verts += [V(a0, b0, z), V(a1, b0, z), V(a1, b1, z), V(a0, b1, z)]
            faces.append((b, b + 3, b + 2, b + 1) if down else (b, b + 1, b + 2, b + 3))
    mb.add(dict(verts=verts, faces=faces), mat)


def niche(mb, O, U, N, uc, mat, sill, lo=0.7, top=2.3, w=0.6, depth=0.45):
    """Arched recess: sides + back, opening on the wall plane. Returns the
    centre of its floor (for setting things in it)."""
    Z = V(0, 0, 1)
    outline = [(uc - w, lo), (uc - w, top)]
    for k in range(1, 12):
        a = math.pi - math.pi * k / 12
        outline.append((uc + math.cos(a) * w, top + math.sin(a) * w))
    outline += [(uc + w, top), (uc + w, lo)]
    front = [O + U * u + Z * v for u, v in outline]
    back = [p - N * depth for p in front]
    part = ak.loft([front, back], closed=True)
    f0 = part['faces'][0]
    va, vb, vc = (part['verts'][i] for i in f0[:3])
    cb = sum(back, Vector()) / len(back)
    if (vb - va).cross(vc - va).dot((cb + N * depth / 2) - va) < 0:
        part['faces'] = [tuple(reversed(f)) for f in part['faces']]
    mb.add(part, mat)
    fan = dict(verts=back + [cb], faces=[(i, (i + 1) % len(back), len(back)) for i in range(len(back))])
    va, vb, vc = (fan['verts'][i] for i in fan['faces'][0])
    if (vb - va).cross(vc - va).dot(N) < 0:
        fan['faces'] = [tuple(reversed(f)) for f in fan['faces']]
    mb.add(fan, mat)
    mb.add(sw.chamfer_box(O + U * uc + Z * (lo - 0.06) + N * 0.05, (w * 2 + 0.24, 0.2, 0.12), 0.03,
                          sw.wall_frame(U, N)), sill)
    return O + U * uc + Z * lo - N * (depth / 2)


def quad(c, U, Vv, w, h):
    c, U, Vv = Vector(c), Vector(U).normalized() * w / 2, Vector(Vv).normalized() * h / 2
    return dict(verts=[c - U - Vv, c + U - Vv, c + U + Vv, c - U + Vv], faces=[(0, 1, 2, 3)],
                uv=[(0, 0), (1, 0), (1, 1), (0, 1)])


class UVBuilder(ak.MeshBuilder):
    """MeshBuilder that keeps per-vertex UVs for textured quads."""

    def __init__(self, name):
        super().__init__(name)
        self.uv = {}

    def addq(self, q, mat, weights=None):
        b = self.add(q, mat, weights)
        for i, uv in enumerate(q['uv']):
            self.uv[b + i] = uv
        return b

    def build(self, coll, armature=None, smooth=False):
        ob = super().build(coll, armature, smooth)
        if self.uv:
            uvl = ob.data.uv_layers.new(name='UVMap')
            for li, lp in enumerate(ob.data.loops):
                uvl.data[li].uv = self.uv.get(lp.vertex_index, (0.5, 0.5))
        return ob


def torch(coll, M, pos, N, name, energy=140):
    """Wall sconce: bracket, cup, two-layer flame, a point light and a glow."""
    mb = ak.MeshBuilder(name)
    N = Vector(N).normalized()
    p = Vector(pos)
    mb.add(box(p - N * 0.05 + V(0, 0, -0.25), (0.12, 0.12, 0.35)), M['iron'])
    arm = ak.tube([p - N * 0.08 + V(0, 0, -0.3), p + N * 0.2 + V(0, 0, -0.18), p + N * 0.28 + V(0, 0, -0.08)],
                  0.025, ring=8, per=3)
    mb.add(arm, M['iron'])
    cup_c = p + N * 0.3
    mb.add(ak.tube([cup_c + V(0, 0, -0.12), cup_c + V(0, 0, 0.02)], [0.04, 0.11], ring=12, per=1,
                   caps=(True, False)), M['iron'])
    ob = mb.build(coll)
    fl = ak.MeshBuilder(name + '_Flame')
    for r, h, mat in ((0.085, 0.28, 'flame'), (0.05, 0.17, 'flame_core')):
        o = cup_c + V(0, 0, 0.06)
        sp = ak.uv_sphere(o, r, segs=10, rings=8)
        vs = []
        for v in sp['verts']:
            d = v - o
            if d.z > 0:
                d = V(d.x * (1 - d.z / (r * 1.6)), d.y * (1 - d.z / (r * 1.6)), d.z * h / r)
            vs.append(o + d)
        fl.add(dict(verts=vs, faces=sp['faces']), M[mat])
    flame = fl.build(coll)
    flame.visible_shadow = False
    ld = bpy.data.lights.new(name + '_Light', 'POINT')
    ld.energy = energy
    ld.color = ak.lin('#ffb066')[:3]
    ld.shadow_soft_size = 0.1
    lo = bpy.data.objects.new(name + '_Light', ld)
    lo.location = cup_c + V(0, 0, 0.25) + N * 0.1
    coll.objects.link(lo)
    g = fx.sprite(name + '_Glow', coll, cup_c + V(0, 0, 0.14), 0.45, M['glow_warm'])
    g['px_sprite'] = True
    return dict(body=ob, flame=flame, light=lo, glow=g)


# ------------------------------------------------------------------ corridor
def corridor(coll, M, rnd):
    X, L, H = CORR['x'], CORR['len'], CORR['h']
    mb = ak.MeshBuilder('Corridor')
    webs = ak.MeshBuilder('Corridor_Webs')
    glyph_b = UVBuilder('Corridor_Glyphs')
    stones = (M['cs0'], M['cs1'], M['cs2'], M['cs3'])
    sw.slab_floor(mb, -X, X, -2, L, (M['cf0'], M['cf1'], M['cf2']), M['cgrout'], rnd, size=(0.7, 1.3),
                  rubble_mat=M['crubble'], keep_clear=lambda x, y: abs(x) < 1.2)
    niches_y = [3.5, 8.5, 13.5, 18.5, 23.5]
    kinds = ['figure', 'skull', 'xray', 'heart', 'ct', 'brain', 'mri', 'bone', 'us', 'rib']

    def side_hole(u, v):
        for ny in niches_y:
            if abs(u - ny) < 0.64 and (0.66 < v < 2.3 or (v >= 2.3 and (u - ny) ** 2 + (v - 2.3) ** 2 < 0.64 ** 2)):
                return True
        return False
    torches = []
    for sx, s in ((1, 'R'), (-1, 'L')):
        O, U, N = V(sx * X, -2, 0), V(0, 1, 0), V(-sx, 0, 0)
        sw.ashlar_wall(mb, O, U, N, L + 2, H, stones, M['cmortar'], rnd, hole=lambda u, v: side_hole(u - 2, v),
                       stain=M['cstain'])
        for i, ny in enumerate(niches_y):
            niche(mb, O, U, N, ny + 2, M['niche'], M['frame0'], depth=0.3)
            kind = kinds[(i * 2 + (0 if sx > 0 else 1)) % len(kinds)]
            gc = O + U * (ny + 2) + V(0, 0, 3.75) + N * 0.07
            glyph_b.addq(quad(gc, -U if sx > 0 else U, V(0, 0, 1), 0.8, 0.8), M['glyph_' + kind])
        for ty in (6.0, 11.0, 16.0, 21.0, 26.0):
            torches.append(torch(coll, M, V(sx * (X - 0.05), ty, 2.7), N, f'Torch_{s}{int(ty)}'))
        # rubble along the wall foot, webs in the top corners
        for ry in rnd.sample([1.5, 5.0, 10.0, 15.5, 20.5, 25.0, 29.5], 4):
            sw.rubble(mb, V(sx * (X - 0.35), ry, 0.0), 0.35, 7, M['crubble'], rnd)
        for wy in rnd.sample([2.0, 7.5, 12.0, 17.0, 22.5, 28.0], 3):
            sw.cobweb(webs, V(sx * (X - 0.03), wy, H - 0.4), V(0, 1, -0.6), V(-sx, 0.3, -0.2), 0.9, M['web'], rnd)
    # ceiling and old beams (one has given way at one end)
    plane_grid(mb, -X, X, -2, L, H, M['ceil'], cell=1.0)
    for i, by in enumerate(np.arange(0.5, L, 2.5)):
        mat = M['wood_rot'] if i % 3 == 1 else M['wood']
        if i == 6:
            rot = Matrix.Rotation(math.radians(-24), 3, 'Y')
            mb.add(sw.chamfer_box(V(-0.7, by, H - 1.3), (2 * X - 0.2, 0.3, 0.34), 0.04, rot), M['wood_rot'])
            sw.rubble(mb, V(-2.6, by, 0), 0.5, 9, M['crubble'], rnd)
            continue
        mb.add(sw.chamfer_box(V(0, by, H - 0.2), (2 * X - 0.04, 0.3, 0.36), 0.04), mat)
    for sx in (1, -1):
        mb.add(sw.chamfer_box(V(sx * (X - 0.12), L / 2 - 1, H - 0.45), (0.24, L + 2, 0.18), 0.03), M['wood'])

    # end wall with the round opening, the voussoir ring and pillars
    c = DOOR['c']
    sw.ashlar_wall(mb, V(-X, L, 0), V(1, 0, 0), V(0, -1, 0), 2 * X, H, stones, M['cmortar'], rnd,
                   hole=lambda u, v: (u - X) ** 2 + (v - c.z) ** 2 < 2.25 ** 2, missing=0.0, stain=M['cstain'])
    nb = 14
    for k in range(nb):
        a0 = 2 * math.pi * k / nb + 0.012
        a1 = 2 * math.pi * (k + 1) / nb - 0.012
        rin, rout = 2.2, 2.85 + (0.12 if k % 2 else 0) + rnd.uniform(-0.04, 0.04)
        pts = []
        for y in (L - 0.32 + rnd.uniform(-0.02, 0.02), L + 0.02):
            for r, a in ((rin, a0), (rout, a0), (rout, a1), (rin, a1)):
                pts.append(V(math.cos(a) * r, y, c.z + math.sin(a) * r))
        part = dict(verts=pts, faces=[(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3),
                                      (3, 7, 4, 0)])
        if min(p.z for p in pts) > -0.4:
            mb.add(ak.fix_normals(part), M['frame1' if k % 2 else 'frame0'])
    mb.add(sw.chamfer_box(V(0, L - 0.2, c.z + 3.0), (0.7, 0.5, 0.6), 0.05), M['frame1'])
    for sx in (1, -1):
        for k in range(6):
            z0 = k * 0.85
            mb.add(sw.chamfer_box(V(sx * 3.1 + rnd.uniform(-0.02, 0.02), L - 0.2, z0 + 0.42),
                                  (0.6, 0.45, 0.82), 0.04), M['frame0'])
        mb.add(sw.chamfer_box(V(sx * 3.1, L - 0.22, 5.2), (0.8, 0.55, 0.22), 0.04), M['frame1'])
    mb.add(box((1.2, c.y, 0.02), (6.6, 0.16, 0.04)), M['rail'])
    sw.cobweb(webs, V(2.8, L - 0.35, 4.6), V(-0.6, 0, 1), V(-1, -0.3, -0.4), 0.8, M['web'], rnd)
    ob = mb.build(coll, smooth=False)
    wb = webs.build(coll)
    wb.visible_shadow = False
    gl = fx.tag(glyph_b.build(coll))
    return dict(ob=ob, glyphs=gl, torches=torches, webs=wb)


# ------------------------------------------------------------------ the door
def vault_door(coll, M):
    c, R, T = DOOR['c'], DOOR['r'], DOOR['t']
    root = bpy.data.objects.new('VaultDoor', None)
    root.empty_display_type = 'CIRCLE'
    root.empty_display_size = R
    root.rotation_euler = (math.pi / 2, 0, 0)
    root.location = c
    coll.objects.link(root)
    mb = ak.MeshBuilder('VaultDoor_Body')
    h = T / 2
    prof = [(0.0, -h + 0.04), (1.22, -h + 0.04), (1.26, -h), (1.74, -h), (1.78, -h - 0.03), (R - 0.06, -h - 0.03),
            (R, -h + 0.03), (R, h), (0.0, h)]
    body = lathe(prof, seg=72)
    fm = []
    for f in body['faces']:
        rr = sum(Vector((body['verts'][i].x, 0, body['verts'][i].z)).length for i in f) / len(f)
        fm.append(M['gold_dk'] if 1.24 < rr < 1.76 else None)
    mb.add(body, M['gold'], face_mats=fm)
    for rr in (1.24, 1.76, R - 0.03):
        mb.add(ak.loop_tube([V(math.cos(a) * rr, -h - 0.035, math.sin(a) * rr)
                             for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)], 0.028, ring=6), M['gold_lt'])
    for k in range(24):
        a = 2 * math.pi * k / 24
        mb.add(ak.uv_sphere(V(math.cos(a) * 1.95, -h - 0.04, math.sin(a) * 1.95), 0.045, segs=8, rings=6), M['gold_lt'])
    mb.add(lathe([(0.0, -h - 0.32), (0.26, -h - 0.32), (0.32, -h - 0.26), (0.32, -h), (0.0, -h)], seg=32), M['gold_dk'])
    wheel = [V(math.cos(a) * 0.85, -h - 0.3, math.sin(a) * 0.85) for a in np.linspace(0, 2 * math.pi, 48, endpoint=False)]
    mb.add(ak.loop_tube(wheel, 0.055, ring=8), M['gold_lt'])
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        mb.add(ak.tube([V(math.cos(a) * 0.28, -h - 0.3, math.sin(a) * 0.28),
                        V(math.cos(a) * 0.85, -h - 0.3, math.sin(a) * 0.85)], 0.04, ring=8, per=1), M['gold_lt'])
        mb.add(ak.uv_sphere(V(math.cos(a) * 0.85, -h - 0.38, math.sin(a) * 0.85), 0.07, segs=10, rings=8), M['gold'])
    body_ob = mb.build(coll, smooth=True)
    # pictographs engraved round the band: the same ring of anatomy and imaging
    eng = UVBuilder('VaultDoor_Engraving')
    for k in range(12):
        a = 2 * math.pi * k / 12 + math.pi / 2
        rad = V(math.cos(a), 0, math.sin(a))
        tan = V(math.sin(a), 0, -math.cos(a))
        eng.addq(quad(rad * 1.5 + V(0, -h - 0.004, 0), tan, rad, 0.34, 0.34), M['engrave_' + RING[k]])
    eng_ob = fx.tag(eng.build(coll))
    bolts = []
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        d = V(math.cos(a), 0, math.sin(a))
        bb = ak.MeshBuilder(f'VaultDoor_Bolt{i}')
        bb.add(ak.tube([d * 1.75, d * (R + 0.42)], 0.11, ring=12, per=1), M['gold_lt'])
        bolts.append(bb.build(coll, smooth=True))
    fix = Matrix.Rotation(-math.pi / 2, 4, 'X')
    for ob in [body_ob, eng_ob] + bolts:
        ob.data.transform(fix)
        ob.parent = root
        ob.data.update()
    return dict(root=root, body=body_ob, bolts=bolts, engraving=eng_ob)


# ------------------------------------------------------------------ the tomb
def tomb(coll, M, rnd):
    y0, y1, X, H = ROOM['y0'], ROOM['y1'], ROOM['x'], ROOM['h']
    mb = ak.MeshBuilder('Tomb')
    webs = ak.MeshBuilder('Tomb_Webs')
    paint = UVBuilder('Tomb_Paintings')
    gold = ak.MeshBuilder('Tomb_Threads')
    stones = (M['ts0'], M['ts1'], M['ts2'], M['ts3'])
    c = DOOR['c']
    p = PED
    sw.slab_floor(mb, -X, X, y0, y1, (M['tf0'], M['tf1'], M['tf2']), M['tgrout'], rnd, size=(0.9, 1.7),
                  rubble_mat=M['trubble'], keep_clear=lambda x, y: (x - p.x) ** 2 + (y - p.y) ** 2 < 3.2 ** 2
                  or abs(x) < 1.5 and y < y0 + 4)
    fz0, fz1 = FRIEZE['z0'], FRIEZE['z1']
    alcove_u = [3.0, 5.0, 8.2, 10.2]           # along each side wall from the entrance

    def side_hole(u, v):
        for a in alcove_u:
            if abs(u - a) < 0.58 and (0.86 < v < 2.3 or (v >= 2.3 and (u - a) ** 2 + (v - 2.3) ** 2 < 0.58 ** 2)):
                return True
        return False
    walls = {
        'front': (V(X, y0, 0), V(-1, 0, 0), V(0, 1, 0), 2 * X, lambda u, v: (u - X) ** 2 + (v - c.z) ** 2 < 2.25 ** 2),
        'back': (V(-X, y1, 0), V(1, 0, 0), V(0, -1, 0), 2 * X, None),
        'left': (V(-X, y0, 0), V(0, 1, 0), V(1, 0, 0), y1 - y0, side_hole),
        'right': (V(X, y1, 0), V(0, -1, 0), V(-1, 0, 0), y1 - y0, lambda u, v: side_hole((y1 - y0) - u, v)),
    }
    for nm, (O, U, N, length, hole) in walls.items():
        sw.ashlar_wall(mb, O, U, N, length, H, stones, M['tmortar'], rnd, hole=hole, stain=M['tstain'],
                       missing=0.0 if nm == 'front' else 0.035)

    # door surround on the tomb side
    for k in range(16):
        a0, a1 = 2 * math.pi * k / 16 + 0.012, 2 * math.pi * (k + 1) / 16 - 0.012
        pts = []
        for y in (y0 + 0.24, y0 - 0.01):
            for r, a in ((2.2, a0), (2.65 + rnd.uniform(-0.05, 0.05), a0), (2.65, a1), (2.2, a1)):
                pts.append(V(math.cos(a) * r, y, c.z + math.sin(a) * r))
        part = dict(verts=pts, faces=[(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
        if min(q.z for q in pts) > -0.3:
            mb.add(ak.fix_normals(part), M['column_cap' if k % 2 else 'column'])
    lin = ak.tube([V(0, DOOR['c'].y - 0.47, c.z), V(0, y0 + 0.01, c.z)], 2.2, ring=48, per=1, caps=(False, False))
    lin['faces'] = [tuple(reversed(f)) for f in lin['faces']]
    lin['verts'] = [V(v.x, v.y, max(v.z, 0.0)) for v in lin['verts']]
    mb.add(lin, M['frame0'])

    # ceiling of big cracked slabs, the oculus a rough opening, roots through the cracks
    slabs_y = np.linspace(y0, y1, 7)
    for i in range(len(slabs_y) - 1):
        for xa, xb in ((-X, -X / 3), (-X / 3, X / 3), (X / 3, X)):
            cx, cy = (xa + xb) / 2, (slabs_y[i] + slabs_y[i + 1]) / 2
            if (cx - p.x) ** 2 + (cy - p.y) ** 2 < 1.6 ** 2:
                continue
            sag = rnd.uniform(-0.05, 0.02)
            mb.add(sw.chamfer_box(V(cx, cy, H + 0.15 + sag), (xb - xa - 0.06, slabs_y[1] - slabs_y[0] - 0.06, 0.3),
                                  0.04, Matrix.Rotation(math.radians(rnd.uniform(-1.2, 1.2)), 3, 'X')),
                   M['tceil' if rnd.random() < 0.6 else 'tceil2'])
    ring_pts = []
    for k in range(20):
        a = 2 * math.pi * k / 20
        rr = 1.05 + rnd.uniform(-0.08, 0.1)
        mb.add(sw.chamfer_box(V(p.x + math.cos(a) * (rr + 0.35), p.y + math.sin(a) * (rr + 0.35), H + 0.05),
                              (0.7, 0.42, 0.36), 0.05, Matrix.Rotation(a, 3, 'Z')), M['tceil2'])
    mb.add(dict(verts=[V(p.x + math.cos(a) * 1.1, p.y + math.sin(a) * 1.1, H + 0.4)
                       for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)],
                faces=[tuple(range(23, -1, -1))]), M['sky'])
    plane_grid(mb, -X, X, y0, y1, H + 0.31, M['tmortar'], cell=1.0,
               hole=lambda x, y: (x - p.x) ** 2 + (y - p.y) ** 2 < 1.15 ** 2)
    for _ in range(14):
        rx = rnd.uniform(-X + 0.5, X - 0.5)
        ry = rnd.choice(list(slabs_y[1:-1])) + rnd.uniform(-0.05, 0.05)
        if (rx - p.x) ** 2 + (ry - p.y) ** 2 < 2.0 ** 2:
            continue
        sw.root(webs, V(rx, ry, H), rnd.uniform(0.4, 1.6), M['root'], rnd)

    # columns: worn drums; the back-right one has broken, its drums on the floor
    cols = [(sx * (X - 0.55), y) for sx in (1, -1) for y in (y0 + 1.4, p.y, y1 - 1.0)]
    for x, y in cols:
        broken = x > 0 and y == y1 - 1.0
        sw.column(mb, V(x, y, 0), H, 0.4, M['column'], M['column_cap'], rnd, drums=7, broken_at=3 if broken else None)
        if not broken:
            sw.cobweb(webs, V(x - math.copysign(0.55, x), y + 0.5, H - 0.4), V(0, 1, -0.4),
                      V(-math.copysign(1, x), 0, -0.6), 0.7, M['web'], rnd)
    bx, by = X - 0.55, y1 - 1.0
    sw.fallen_drum(mb, V(bx - 1.6, by - 0.6, 0), 0.38, 0.9, 0.5, M['column'])
    sw.fallen_drum(mb, V(bx - 2.5, by + 0.1, 0), 0.38, 0.85, -0.9, M['column'])
    sw.rubble(mb, V(bx - 1.0, by - 0.2, 0), 1.0, 22, M['trubble'], rnd)

    # alcoves with scrolls, clay tablets, canopic jars and the odd skull
    for nm in ('left', 'right'):
        O, U, N, length, _ = walls[nm]
        for i, a in enumerate(alcove_u):
            u = a if nm == 'left' else length - a
            fl = niche(mb, O, U, N, u, M['tniche'], M['ts2'], lo=0.92, top=2.3, w=0.55, depth=0.5)
            kind = (i + (1 if nm == 'right' else 0)) % 4
            Uu = Vector(U).normalized()
            if kind == 0:
                for k in range(3):
                    cc = fl + Uu * (k - 1) * 0.28 + V(0, 0, 0.12)
                    mb.add(ak.tube([cc - Vector(N) * 0.18, cc + Vector(N) * 0.18], 0.07, ring=10, per=1), M['scroll'])
                mb.add(ak.tube([fl + V(0, 0, 0.3) - Vector(N) * 0.15, fl + V(0, 0, 0.3) + Vector(N) * 0.15], 0.065,
                               ring=10, per=1), M['scroll'])
            elif kind == 1:
                for k in range(3):
                    rot = sw.wall_frame(U, N) @ Matrix.Rotation(math.radians(rnd.uniform(-14, 14)), 3, 'Y')
                    mb.add(sw.chamfer_box(fl + Uu * (k - 1) * 0.3 + V(0, 0, 0.22), (0.24, 0.06, 0.32), 0.02, rot),
                           M['tablet' if k % 2 else 'tablet_dk'])
            elif kind == 2:
                for k in range(4):
                    cc = fl + Uu * (k - 1.5) * 0.24
                    mb.add(ak.tube([cc, cc + V(0, 0, 0.32)], [0.075, 0.09], ring=12, per=1),
                           M['jar0' if k % 2 else 'jar1'])
                    mb.add(ak.uv_sphere(cc + V(0, 0, 0.38), (0.07, 0.07, 0.08), segs=10, rings=8),
                           M['jarlid0' if k % 2 else 'jarlid1'])
            else:
                mb.add(ak.uv_sphere(fl + V(0, 0, 0.16), (0.11, 0.13, 0.12), segs=12, rings=10), M['skull'])
                mb.add(sw.chamfer_box(fl + V(0, 0, 0.05) - Vector(N) * 0.06, (0.14, 0.1, 0.08), 0.02), M['skull'])
                sw.rubble(mb, fl + Uu * 0.25, 0.12, 3, M['trubble'], rnd, scale=0.5)

    # the first illustration: a plaster panel behind the altar, the figure painted on it
    bw, bh = 3.6, 4.8
    mb.add(sw.chamfer_box(V(0, y1 - 0.06, 3.3), (bw + 0.3, 0.1, bh + 0.3), 0.04), M['plaster'])
    paint.addq(quad(V(0, y1 - 0.115, 3.3), V(1, 0, 0), V(0, 0, 1), bw, bh), M['first'])
    # frieze: plaster bands on the side walls with four painted panels each
    pw = 1.25
    panel_tops = []
    for nm, side in (('left', 'L'), ('right', 'R')):
        O, U, N, length, _ = walls[nm]
        U, N = Vector(U).normalized(), Vector(N).normalized()
        mb.add(sw.chamfer_box(O + U * (length / 2) + V(0, 0, (fz0 + fz1) / 2) + N * 0.06,
                              (length - 0.6, 0.08, fz1 - fz0 + 0.2), 0.03, sw.wall_frame(U, N)), M['plaster'])
        # left runs entrance -> back, right runs back -> entrance: order so history
        # and imaging both read outward from the first illustration
        us = [length - 1.6 - k * 2.9 for k in range(4)] if nm == 'left' else [1.6 + k * 2.9 for k in range(4)]
        for i, u in enumerate(us):
            ctr = O + U * u + V(0, 0, (fz0 + fz1) / 2) + N * 0.105
            paint.addq(quad(ctr, U, V(0, 0, 1), pw, pw), M[f'panel_{side}{i}'])
            panel_tops.append(O + U * u + V(0, 0, fz1 + 0.02) + N * 0.11)

    # gold threads: out of the figure's heart, round the frieze, down to each panel
    def on_panel(px_, py_):
        """canvas pixel of the first illustration -> world point just in front"""
        return V((px_ / 96 - 0.5) * bw, y1 - 0.125, 3.3 + bh * (0.5 - py_ / 128))
    heart = on_panel(51, 54)
    tz = FRIEZE['thread_z']
    yw = y1 - 0.13
    for sx in (-1, 1):
        # heart -> shoulder -> along the arm -> out of the hand -> panel edge -> up to the frieze
        shoulder = on_panel(48 + sx * 16, 38)
        elbow = on_panel(48 + sx * 27, 46)
        hand = on_panel(48 + sx * 38, 57)
        edge = V(sx * (bw / 2 + 0.25), yw, hand.z)
        corner = V(sx * (bw / 2 + 0.25), yw, tz)
        wall = V(sx * (X - 0.12), yw, tz)
        far = V(sx * (X - 0.12), y0 + 1.0, tz)
        gold.add(ak.tube([heart, shoulder, elbow, hand], 0.016, ring=6, per=1, caps=(False, False)), M['thread'])
        gold.add(ak.tube([hand, edge, corner, wall, far], 0.022, ring=6, per=1, caps=(False, False)), M['thread'])
        gold.add(ak.uv_sphere(hand, 0.06, segs=8, rings=6), M['thread'])
    for top in panel_tops:
        gold.add(ak.tube([V(top.x, top.y, tz), top + V(0, 0, 0.02)], 0.02, ring=6, per=1, caps=(False, False)),
                 M['thread'])
        gold.add(ak.uv_sphere(V(top.x, top.y, tz), 0.05, segs=8, rings=6), M['thread'])
    for k in range(8):
        a = k / 8 * math.tau
        gold.add(ak.tube([heart, heart + V(math.cos(a) * 0.18, -0.0, math.sin(a) * 0.18)], 0.01, ring=4, per=1,
                         caps=(False, False)), M['thread'])

    # the altar: worn stacked blocks, a chipped corner, a carved gold figure
    mb.add(sw.chamfer_box(V(p.x, p.y, 0.13), (1.7, 1.7, 0.26), 0.05), M['altar1'])
    mb.add(sw.chamfer_box(V(p.x, p.y, 0.33), (1.35, 1.35, 0.16), 0.04), M['altar0'])
    mb.add(sw.chamfer_box(V(p.x, p.y, 0.88), (0.82, 0.82, 0.96), 0.05), M['altar2'])
    for z in (0.52, 1.24):
        mb.add(sw.chamfer_box(V(p.x, p.y, z), (0.9, 0.9, 0.07), 0.02), M['altar1'])
    mb.add(sw.chamfer_box(V(p.x, p.y, 1.42), (1.1, 1.1, 0.16), 0.05,
                          Matrix.Rotation(math.radians(1.2), 3, 'X')), M['altar0'])
    sw.rubble(mb, V(p.x + 0.7, p.y - 0.75, 0.0), 0.15, 4, M['altar0'], rnd, scale=0.6)
    paint.addq(quad(V(p.x, p.y - 0.416, 0.88), V(1, 0, 0), V(0, 0, 1), 0.5, 0.5), M['glyph_figure_gold'])
    # loose stone
    mb.add(sw.chamfer_box(STONE + V(0, 0, 0.09), (0.5, 0.36, 0.2), 0.07, Matrix.Rotation(0.4, 3, 'Z')), M['stone'])
    # floor glyph ring: anatomy and imaging, alternating
    ring = [V(p.x + math.cos(a) * 2.4, p.y + math.sin(a) * 2.4, 0.03) for a in np.linspace(0, 2 * math.pi, 96, endpoint=False)]
    glyph = UVBuilder('GlyphRing')
    glyph.add(ak.loop_tube(ring, (0.05, 0.01), ring=4), M['glyphring'])
    for k in range(12):
        a = 2 * math.pi * k / 12
        gc = V(p.x + math.cos(a) * 2.4, p.y + math.sin(a) * 2.4, 0.05)
        glyph.addq(quad(gc, V(-math.sin(a), math.cos(a), 0), V(math.cos(a), math.sin(a), 0), 0.5, 0.5),
                   M['glyph_' + RING[k] + '_gold'])
    gob = fx.tag(glyph.build(coll))
    # webs in the room's top corners
    for cx, cy, a, b in ((-X, y1, V(1, 0, -0.4), V(0, -1, -0.4)), (X, y1, V(-1, 0, -0.4), V(0, -1, -0.4)),
                         (-X, y0, V(1, 0, -0.4), V(0, 1, -0.4)), (X, y0, V(-1, 0, -0.4), V(0, 1, -0.4))):
        sw.cobweb(webs, V(cx * 0.995, cy + (0.05 if cy == y0 else -0.05), H - 0.05), a, b, 1.3, M['web'], rnd,
                  spokes=7, rings=5)

    ob = mb.build(coll, smooth=False)
    pt = paint.build(coll)
    pt.visible_shadow = False
    th = gold.build(coll)
    th.visible_shadow = False
    wb = webs.build(coll)
    wb.visible_shadow = False
    torches = [torch(coll, M, V(sx * (X - 0.05), y, 3.0), V(-sx, 0, 0), f'VTorch_{sx}_{int(y)}', energy=190)
               for sx in (1, -1) for y in (y0 + 4.1, y1 - 3.6)]
    # low warm fills so the alcoves and their contents read
    for sx in (1, -1):
        for yy in (y0 + 4.1, y1 - 3.6):
            lf = bpy.data.lights.new(f'AlcoveFill_{sx}_{int(yy)}', 'POINT')
            lf.energy = 60
            lf.color = ak.lin('#ffb880')[:3]
            lo = bpy.data.objects.new(lf.name, lf)
            lo.location = V(sx * (X - 1.4), yy, 1.6)
            coll.objects.link(lo)
    sp = bpy.data.lights.new('Oculus', 'SPOT')
    sp.energy = 2600
    sp.color = ak.lin('#ffe2a8')[:3]
    sp.spot_size = math.radians(34)
    sp.spot_blend = 0.3
    so = bpy.data.objects.new('Oculus', sp)
    so.location = V(p.x, p.y, H - 0.1)
    coll.objects.link(so)
    # a soft fill on the back wall so the first illustration reads
    fl = bpy.data.lights.new('MuralFill', 'AREA')
    fl.energy = 160
    fl.size = 4.0
    fl.color = ak.lin('#ffd8a0')[:3]
    fo = bpy.data.objects.new('MuralFill', fl)
    fo.location = V(0, y1 - 3.0, 6.5)
    fo.rotation_euler = (math.radians(-45), 0, 0)
    coll.objects.link(fo)
    beam = fx.frustum('Beam', coll, V(p.x, p.y, H), 0.95, V(p.x, p.y, 0.0), 1.3, M['beam'])
    dust = fx.dust('BeamDust', coll, V(p.x, p.y, 4.0), (0.9, 0.9, 3.6), 110, M['dust'], seed=4, r=0.014)
    return dict(ob=ob, paintings=pt, threads=th, webs=wb, glyph_ring=gob, torches=torches, oculus=so, beam=beam,
                dust=dust)


# ------------------------------------------------------------------ the Atlas
def atlas(coll, M, loc=None):
    """Closed book about 0.24 x 0.32 x 0.07 m: worn leather boards, brass
    corners and clasp. Origin at its centre; the front cover faces -Y when the
    book stands upright (spine on the left)."""
    w, h, d = 0.24, 0.32, 0.07
    mb = UVBuilder('Atlas')
    bt = 0.012
    for y, front in ((-d / 2 + bt / 2, True), (d / 2 - bt / 2, False)):
        mb.add(box((0.006, y, 0), (w, bt, h)), M['leather'])
        if front:
            mb.addq(quad(V(0.012, y - bt / 2 - 0.001, 0), V(1, 0, 0), V(0, 0, 1), w - 0.03, h - 0.03), M['cover'])
    mb.add(box((0.01, 0, 0), (w - 0.02, d - 2 * bt, h - 0.016)), M['pages'])
    mb.add(ak.tube([V(-w / 2 + 0.006, 0, -h / 2), V(-w / 2 + 0.006, 0, h / 2)], (0.012, d / 2), ring=12, per=1),
           M['leather'])
    for sz in (1, -1):
        for y in (-d / 2 + bt / 2, d / 2 - bt / 2):
            mb.add(box((w / 2 - 0.012, y, sz * (h / 2 - 0.018)), (0.034, bt + 0.004, 0.034)), M['corner'])
    mb.add(box((w / 2 + 0.004, 0, 0), (0.012, d + 0.006, 0.05)), M['corner'])      # clasp
    ob = mb.build(coll)
    if loc is not None:
        ob.location = loc
    return ob


def build(coll, seed=3):
    rnd = random.Random(seed)
    M = materials(rnd)
    ak.world('#0a0b10', 0.32)
    corr = corridor(coll, M, rnd)
    door = vault_door(coll, M)
    ch = tomb(coll, M, rnd)
    book = atlas(coll, M, V(PED.x, PED.y, 1.85))
    book.rotation_euler = (math.radians(8), 0, math.radians(20))
    bglow = fx.sprite('AtlasGlow', coll, book.location, 0.55, M['glow_gold'])
    bglow['px_sprite'] = True
    spill = fx.wedge('DoorSpill', coll,
                     [V(-1.9, 32.0, 0.05), V(1.9, 32.0, 0.05), V(1.9, 32.0, 4.1), V(-1.9, 32.0, 4.1)],
                     [V(-3.3, 19.0, 0.02), V(3.3, 19.0, 0.02), V(3.3, 19.0, 0.35), V(-3.3, 19.0, 0.35)], M['spill'])
    spill.hide_render = True
    og = fx.sprite('OculusGlow', coll, V(PED.x, PED.y, ROOM['h'] - 0.2), 1.6, M['glow_gold'])
    og['px_sprite'] = True
    return dict(M=M, corridor=corr, door=door, chamber=ch, atlas=book, atlas_glow=bglow, spill=spill)


def aim_sprites(camera):
    for ob in bpy.context.scene.objects:
        if ob.get('px_sprite'):
            fx.face_camera(ob, camera)
