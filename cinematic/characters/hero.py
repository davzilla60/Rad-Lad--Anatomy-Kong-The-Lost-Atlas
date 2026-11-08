"""The radiographer, after assets/concept/character_sheet.png.

Female (default): auburn curly ponytail with a blue scrunchie, freckles,
navy scrubs with a radiation-trefoil patch on the right sleeve, lanyard and
ID badge, belt, watch, brown boots and a big brown backpack with a bedroll.
Male ('m'): same kit, short brown hair and a beard.
"""
import math
import random
import numpy as np
from mathutils import Vector, Matrix
import akcore as ak
import humanoid as hu
import pixel

V = hu.V
ss = ak.smoothstep

BASE = dict(
    pelvis_z=0.90, waist_z=1.02, chest_z=1.19, neck_z=1.36, head_z=1.415,
    head_c=(0, -0.010, 1.528), head_r=(0.090, 0.104, 0.120),
    shoulder_x=0.165, shoulder_z=1.32, arm_drop=56, upper_arm=0.265, forearm=0.235, hand_scale=0.93,
    hip_x=0.085, hip_z=0.86, knee_z=0.47, ankle_z=0.08, foot_len=0.25,
    neck_r=0.040,
    arm_r=(0.046, 0.040, 0.032, 0.031, 0.025),
    leg_r=(0.086, 0.076, 0.056, 0.054, 0.05),
    shoe_w=0.05, shoe_h=0.06,
    sleeve_s=1.9,
    torso=[(0.80, 0.12, 0.09, 0.0, 2.4), (0.87, 0.162, 0.112, 0.0, 2.6), (0.95, 0.152, 0.10, 0.0, 2.6),
           (1.03, 0.132, 0.09, 0.005, 2.6), (1.12, 0.146, 0.096, 0.0, 2.8), (1.21, 0.158, 0.10, 0.005, 3.0),
           (1.29, 0.155, 0.092, 0.015, 3.0), (1.37, 0.062, 0.052, 0.02, 2.2)],
    bust=(0.024, 1.19, 0.062),
    face=dict(
        skull_back=0.07, crown=0.0, jaw=0.70, jaw_square=0.0, face_flat=0.06, chin_fwd=0.05,
        chin_flat=0.6, temple=0.02, chin_len=0.88,
        eye_x=0.034, eye_z=-0.004, eye_r=0.0158, eye_sink=0.45,
        nose_bridge_z=-0.008, nose_tip_z=-0.038, nose_len=0.017, nose_w=(0.008, 0.0125), nose_under=0.14,
        brow=0.004, socket=0.005, mouth_z=-0.064, lips=0.005, chin=0.004, cheek=0.005,
        lid_up=24, lid_low=-30, lash=11, iris_rings=8, pupil_rings=4,
        brow_z=0.026, brow_in=0.011, brow_out=0.053, brow_th=0.0058, brow_arch=0.005,
        mouth_w=0.022, ear_z=-0.016, ear_size=0.95,
    ),
)

MALE = dict(
    shoulder_x=0.185, shoulder_z=1.34, neck_z=1.38, head_z=1.43, neck_r=0.046,
    head_c=(0, -0.010, 1.545), head_r=(0.092, 0.106, 0.122),
    arm_r=(0.052, 0.046, 0.036, 0.035, 0.028), hand_scale=1.0,
    torso=[(0.80, 0.125, 0.09, 0.0, 2.4), (0.87, 0.16, 0.11, 0.0, 2.6), (0.95, 0.155, 0.104, 0.0, 2.6),
           (1.03, 0.150, 0.10, 0.005, 2.6), (1.12, 0.165, 0.106, 0.0, 2.8), (1.22, 0.182, 0.112, 0.005, 3.0),
           (1.30, 0.178, 0.10, 0.015, 3.0), (1.385, 0.068, 0.058, 0.02, 2.2)],
    bust=None,
)
MALE_FACE = dict(jaw=0.80, jaw_square=0.08, chin_flat=0.45, chin_len=0.92, eye_r=0.0145, lid_up=18, lid_low=-26,
                 lash=8, nose_len=0.022, nose_w=(0.009, 0.014), brow=0.007, brow_th=0.0075, brow_z=0.023,
                 eye_x=0.035, mouth_w=0.024)

EXPRESSIONS = {
    'neutral': {},
    'determined': {'brows': {'angry': 0.45}, 'lids': {'squint': 0.2}, 'mouth': {'smirk.R': 0.6}},
    'shouting': {'brows': {'angry': 0.9}, 'lids': {'wide': 0.4}, 'mouth': {'open': 1.0}},
    'shocked': {'brows': {'worried': 0.9, 'up': 0.4}, 'lids': {'wide': 0.8}, 'mouth': {'oh': 1.0}},
    'wry': {'brows': {'up.L': 0.7, 'worried': 0.3}, 'lids': {'narrow.R': 0.3}, 'mouth': {'smirk.L': 0.8}},
}


def params(variant):
    P = {k: (dict(v) if isinstance(v, dict) else v) for k, v in BASE.items()}
    if variant == 'm':
        P.update(MALE)
        P['face'].update(MALE_FACE)
    return P


def materials(v):
    t = ak.toon
    p = 'HeroM_' if v == 'm' else 'Hero_'
    M = {
        'chest': t('Hero_SkinChest', '#dc9663'),
        'sleeve': t('Hero_ScrubSleeve', '#2f5f95'),
        'skin': t('Hero_Skin', '#dc9663'),
        'face': t('Hero_Face', '#dc9663', attr='Col'),
        'scrubs': t('Hero_Scrubs', '#2f5f95'),
        'scrubs_dk': t('Hero_ScrubsDark', '#244a76'),
        'belt': t('Hero_Belt', '#2a2a33', rim=0.15),
        'buckle': t('Hero_Buckle', '#a9a8b4', rim=0.3),
        'boot': t('Hero_Boot', '#6b4426', hl='#a8784e', hl_rough=0.25, hl_cut=0.6),
        'pack': t('Hero_Pack', '#7c5735'),
        'pack_dk': t('Hero_PackDark', '#5c3f27'),
        'roll': t('Hero_Bedroll', '#94704a'),
        'roll_grey': t('Hero_RollGrey', '#b8b7c3'),
        'strap': t('Hero_Strap', '#5a3d26'),
        'lanyard': t('Hero_Lanyard', '#22324f'),
        'watch': t('Hero_Watch', '#222a3a', rim=0.2),
        'hair': t(p + 'Hair', '#9b4720' if v != 'm' else '#5e3a22',
                  hl='#d4743a' if v != 'm' else '#8c5c36', hl_rough=0.35, hl_cut=0.5),
        'hair_lt': t(p + 'HairLight', '#c86a2f' if v != 'm' else '#80522f',
                     hl='#f2a066' if v != 'm' else '#b07a4c', hl_rough=0.35, hl_cut=0.5),
        'scrunchie': t('Hero_Scrunchie', '#2d5fa6'),
        'earring': t('Hero_Earring', '#d9dbe6', rim=0.4),
        'brow': ak.flat(p + 'Brow', '#6a3018' if v != 'm' else '#3e2616'),
        'beard': t('HeroM_Beard', '#5a3820'),
        'sclera': t('Hero_Sclera', '#f4f0ea'),
        'iris': t('Hero_Iris', '#6a3a1c'),
        'pupil': ak.flat('Hero_Pupil', '#120a08'),
        'glint': ak.flat('Hero_Glint', '#ffffff'),
        'lid': t('Hero_Lid', '#dc9663'),
        'lash': ak.flat('Hero_Lash', '#24140f'),
        'lash_low': t('Hero_LashLow', '#a8603c'),
        'mouth': ak.flat('Hero_Mouth', '#5a2228'),
        'teeth': t('Hero_Teeth', '#f4efe6'),
        'patch': t('Hero_Patch', '#ffffff', image=trefoil_image()),
        'badge': t('Hero_Badge', '#ffffff', image=badge_image()),
    }
    pixel.noline(M['glint'], M['pupil'], M['mouth'], M['teeth'], M['brow'], M['lash'], M['iris'],
                 M['patch'], M['badge'], M['earring'])
    return M


# ------------------------------------------------------------------ textures
def trefoil_image(n=128):
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    y = -y
    r = np.hypot(x, y)
    a = np.degrees(np.arctan2(y, x)) % 360
    img = np.zeros((n, n, 4), np.float32)
    yellow, black = ak.srgb_arr('#f2c230'), ak.srgb_arr('#16121a')
    img[:] = yellow
    blade = np.zeros_like(r, bool)
    for c in (90, 210, 330):
        d = np.abs((a - c + 180) % 360 - 180)
        blade |= (d < 30) & (r > 0.28) & (r < 0.78)
    blade |= r < 0.17
    img[blade] = black
    img[(r > 0.9) & (r <= 1.0)] = black
    img[r > 1.0] = black
    img[..., 3] = 1
    return ak.image_from_array('Trefoil', img)


def badge_image(w=96, h=128):
    img = np.zeros((h, w, 4), np.float32)
    img[:] = ak.srgb_arr('#f4f2ee')
    img[6:26, :] = ak.srgb_arr('#2f5f95')
    img[36:84, 10:46] = ak.srgb_arr('#c9b07a')          # photo
    img[44:62, 20:36] = ak.srgb_arr('#8a5a3a')
    for i, yy in enumerate((40, 52, 64, 76)):
        img[yy:yy + 5, 54:90 - i * 6] = ak.srgb_arr('#4a4652')
    img[96:108, 10:86] = ak.srgb_arr('#f2c230')
    img[..., 3] = 1
    return ak.image_from_array('Badge', img)


def textured_quad(center, right, up, w, h):
    c = Vector(center)
    r, u = Vector(right).normalized() * (w / 2), Vector(up).normalized() * (h / 2)
    verts = [c - r - u, c + r - u, c + r + u, c - r + u]
    return dict(verts=verts, faces=[(0, 1, 2, 3)], uv=[(0, 0), (1, 0), (1, 1), (0, 1)])


def head_colours(P, head, v):
    F = P['face']
    cols = []
    rnd = random.Random(3)
    freckles = [(rnd.uniform(0.012, 0.052) * rnd.choice((-1, 1)), rnd.uniform(-0.03, -0.012)) for _ in range(26)]
    for p, d in zip(head['local'], head['dir']):
        c = [1.0, 1.0, 1.0]
        front = ss(0.2, -0.5, d.y)
        if v == 'm':
            jaw = ss(-0.1, -0.4, d.z) * ss(0.6, 0.15, d.y)
            st = jaw * 0.5
            c = [1 - st * 0.25, 1 - st * 0.28, 1 - st * 0.2]
        else:
            blush = sum(hu.gauss((abs(p.x) - 0.045) ** 2 + (p.z - (F['eye_z'] - 0.03)) ** 2, 0.016) for _ in (0,))
            c = [1.0, 1 - 0.12 * blush * front, 1 - 0.1 * blush * front]
            for fx, fz in freckles:
                f = hu.gauss((p.x - fx) ** 2 + (p.z - fz) ** 2, 0.0022) * front
                if f > 0.6:
                    c = [1 - 0.12 * f, 1 - 0.2 * f, 1 - 0.24 * f]
        cols.append((*c, 1.0))
    return cols


# ------------------------------------------------------------------ kit
def kit(coll, arm, P, J, M, v):
    mb = ak.MeshBuilder('Hero_Kit' if v != 'm' else 'HeroM_Kit')
    # textured quads go in their own object: an ink hull would cover them
    db = ak.MeshBuilder('Hero_Decals' if v != 'm' else 'HeroM_Decals')
    db.uvs = {}
    tw = hu.torso_weights(P, J)

    def ring_at(z, grow, n=40):
        _, wx, wy, yo, e = hu.torso_size_at(P, z)
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = hu.super_pt(a, wx + grow, wy + grow, yo, e)
            pts.append(V(x, y, z))
        return pts, (wx, wy, yo, e)

    # belt + buckle
    bz = P['hip_z'] + 0.075
    pts, (wx, wy, yo, e) = ring_at(bz, 0.006)
    mb.add(ak.loop_tube(pts, (0.004, 0.018), ring=8), M['belt'], tw)
    _, fy = hu.super_pt(0, wx, wy, yo, e)
    mb.add(ak.fix_normals(ak.rounded_box(V(0, fy - 0.012, bz), (0.05, 0.008, 0.034), r=0.4, segs=1)),
           M['buckle'], tw(V(0, 0, bz)))
    # short sleeves: a flared cuff around the upper arm
    for s in ('L', 'R'):
        S, E = J[f'shoulder.{s}'], J[f'elbow.{s}']
        inner = S + (J[f'clav.{s}'] - S) * 0.4
        ar = P['arm_r']
        cuff = S + (E - S) * 0.62
        sl = ak.tube([inner, S, cuff], [ar[0] + 0.012, ar[0] + 0.014, ar[1] + 0.016], ring=18, per=5,
                     caps=(True, False))
        mb.add(sl, M['sleeve'], [hu.blend({f'clavicle.{s}': 1}, {f'upper_arm.{s}': 1}, ss(0.3, 1.1, x))
                                 for x in sl['s']])
        if s == 'R':
            # trefoil patch on the outside of the right sleeve
            c = S + (E - S) * 0.28
            out = V(-1, 0, 0.35).normalized()
            fwd = (E - S).normalized()
            centre = c + out * (ar[0] + 0.024)
            right = out.cross(fwd).normalized()
            q = textured_quad(centre, right, -fwd, 0.05, 0.05)
            base = db.add(q, M['patch'], {f'upper_arm.{s}': 1.0})
            for i, uv in enumerate(q['uv']):
                db.uvs[base + i] = uv
    # watch on the left wrist
    W, E = J['wrist.L'], J['elbow.L']
    d = (W - E).normalized()
    c = W - d * 0.025
    u = V(0, 0, 1)
    u = (u - d * u.dot(d)).normalized()
    sd = d.cross(u)
    wr = P['arm_r'][4] + 0.004
    mb.add(ak.loop_tube([c + (sd * math.cos(a) + u * math.sin(a)) * wr for a in
                         [2 * math.pi * k / 20 for k in range(20)]], (0.003, 0.009), ring=6),
           M['watch'], {'forearm.L': 1.0})
    # lanyard + badge
    cz = P['chest_z']
    _, (wx, wy, yo, e) = ring_at(cz - 0.02, 0)
    _, fy = hu.super_pt(0, wx, wy, yo, e)
    bust = P.get('bust')
    by = fy - (bust[0] * 0.9 if bust else 0) - 0.012
    badge_c = V(0.0, by, cz - 0.05)
    for sx in (1, -1):
        nk = V(sx * 0.05, J['neck'].y - 0.02, P['neck_z'] - 0.02)
        mid = V(sx * 0.035, by + 0.004, cz + 0.06)
        lan = ak.tube([nk + V(0, 0.035, 0.01), nk, mid, badge_c + V(sx * 0.008, 0, 0.04)], (0.006, 0.0015),
                      ring=6, per=4, up=V(0, -1, 0.3))
        mb.add(lan, M['lanyard'], tw)
    q = textured_quad(badge_c + V(0, -0.0065, 0), V(1, 0, 0), V(0, 0.08, 1), 0.052, 0.07)
    base = db.add(q, M['badge'], tw(badge_c))
    for i, uv in enumerate(q['uv']):
        db.uvs[base + i] = uv
    mb.add(ak.fix_normals(ak.rounded_box(badge_c + V(0, 0.002, 0), (0.056, 0.004, 0.074), r=0.6, segs=1)),
           M['lanyard'], tw(badge_c))

    # backpack
    _, (wx, wy, yo, e) = ring_at(cz, 0)
    _, back_y = hu.super_pt(math.pi, wx, wy, yo, e)
    pc = V(0, back_y + 0.095, cz - 0.07)
    pw = 0.30 if v != 'm' else 0.32
    mb.add(ak.fix_normals(ak.rounded_box(pc, (pw, 0.17, 0.40), r=0.75, segs=2)), M['pack'], {'chest': 1.0})
    mb.add(ak.fix_normals(ak.rounded_box(pc + V(0, 0.085, -0.06), (pw * 0.7, 0.05, 0.2), r=0.7, segs=1)),
           M['pack_dk'], {'chest': 1.0})
    mb.add(ak.fix_normals(ak.rounded_box(pc + V(pw / 2 + 0.03, 0.01, -0.09), (0.06, 0.11, 0.13), r=0.7, segs=1)),
           M['pack_dk'], {'chest': 1.0})
    # flap
    mb.add(ak.fix_normals(ak.rounded_box(pc + V(0, 0.004, 0.15), (pw * 1.02, 0.175, 0.12), r=0.7, segs=1)),
           M['pack_dk'], {'chest': 1.0})
    # bedroll on top, grey roll beneath on the right
    top = pc + V(0, 0.01, 0.25)
    roll = ak.tube([top + V(-0.21, 0, 0), top + V(0.21, 0, 0)], 0.072, ring=20, per=3)
    mb.add(roll, M['roll'], {'chest': 1.0})
    for sx in (1, -1):
        mb.add(ak.loop_tube([top + V(sx * 0.12, math.cos(a) * 0.075, math.sin(a) * 0.075)
                             for a in [2 * math.pi * k / 20 for k in range(20)]], (0.006, 0.004), ring=6),
               M['strap'], {'chest': 1.0})
        # spiral hint on the roll ends
        sp = [top + V(sx * 0.212, math.cos(a) * r, math.sin(a) * r)
              for a, r in [(t * 0.6, 0.012 + t * 0.0022) for t in range(28)]]
        mb.add(ak.tube(sp, 0.0025, ring=5, per=2), M['pack_dk'], {'chest': 1.0})
    g = pc + V(-pw / 2 - 0.02, 0.02, -0.17)
    mb.add(ak.tube([g + V(0, -0.07, 0), g + V(0, 0.07, 0)], 0.05, ring=16, per=2), M['roll_grey'], {'chest': 1.0})
    # shoulder straps
    for sx, s in ((1, 'L'), (-1, 'R')):
        S = J[f'shoulder.{s}']
        _, (wx2, wy2, yo2, e2) = ring_at(cz + 0.07, 0.012)
        a_front = math.radians(32) * sx
        fx, fy2 = hu.super_pt(a_front if sx > 0 else 2 * math.pi + a_front, wx2, wy2, yo2, e2)
        path = [pc + V(sx * 0.08, -0.07, 0.17), V(sx * 0.085, back_y + 0.012, P['shoulder_z'] + 0.015),
                V(sx * 0.10, -0.02, P['shoulder_z'] + 0.028), V(fx, fy2 - 0.01, cz + 0.07),
                V(sx * 0.13, fy2 + 0.03, cz - 0.08), pc + V(sx * 0.13, -0.08, -0.17)]
        st = ak.tube(path, (0.022, 0.005), ring=8, per=6, up=None)
        mb.add(st, M['strap'], {'chest': 0.7, f'clavicle.{s}': 0.3})
        # buckle tab on the front of the strap
        mb.add(ak.fix_normals(ak.rounded_box(V(fx * 0.98, fy2 - 0.016, cz + 0.04), (0.03, 0.008, 0.026),
                                             r=0.4, segs=1)), M['pack_dk'], {'chest': 1.0})
    ob = mb.build(coll, arm)
    dob = db.build(coll, arm)
    uvl = dob.data.uv_layers.new(name='UVMap')
    for poly in dob.data.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = db.uvs[dob.data.loops[li].vertex_index]
    ak.add_outline(ob, 0.004)
    return ob


# ------------------------------------------------------------------ hair
def hair_f(coll, arm, head, bvh, M, name):
    C = head['C']
    rnd = random.Random(11)
    mb = ak.MeshBuilder(name)
    mb.add(hu.scalp_cap(head, hu.hairline_mask(44, 82, 125), 0.0045), M['hair'], {'head': 1.0})

    def add(path, radii, light, flat=0.5, ring=8):
        mb.add(hu.clump2(bvh, C, path, radii, ring=ring, per=5, flat=flat),
               M['hair_lt' if light else 'hair'], {'head': 1.0})
    tie_b = 128
    # pulled back toward the tie
    for i, a0 in enumerate([-48, -36, -24, -12, 0, 12, 24, 36, 48]):
        # start under the skin so the hairline is a smooth edge, not teeth
        path = [(a0, 40 + abs(a0) * 0.08, -0.007), (a0 * 0.95, 50, 0.006), (a0 * 0.9, 64, 0.014),
                (a0 * 0.7, 88, 0.016), (a0 * 0.35, 112, 0.014), (a0 * 0.08, tie_b, 0.012)]
        add(path, [0.014, 0.016, 0.017, 0.02, 0.016, 0.01], light=i % 2 == 0)
    for s in (1, -1):
        for j, (a0, b0) in enumerate(((58, 32), (68, 22), (77, 10))):
            path = [(s * a0, b0 - 4, -0.006), (s * a0, b0 + 8, 0.005), (s * (a0 - 4), b0 + 40, 0.01),
                    (s * (a0 - 18), b0 + 80, 0.012), (s * 20, tie_b - 4, 0.01)]
            add(path, [0.012, 0.014, 0.015, 0.016, 0.009], light=j % 2 == 1)
    for i, a0 in enumerate([-45, -25, 0, 25, 45]):
        path = [(a0, 196, 0.004), (a0 * 0.8, 170, 0.01), (a0 * 0.4, 148, 0.013), (a0 * 0.1, tie_b + 4, 0.012)]
        add(path, [0.008, 0.016, 0.018, 0.01], light=i % 2 == 1)
    # side-swept bangs from a part on her left
    for k, (a0, a1, l) in enumerate(((22, -30, 0.016), (14, -42, 0.014), (30, -16, 0.018), (6, -50, 0.012))):
        path = [(a0, 74, 0.016), (a0 * 0.6 + a1 * 0.4, 62, 0.02), (a1 * 0.8, 50, l), (a1, 40, 0.012)]
        add(path, [0.012, 0.015, 0.011, 0.004], light=k % 2 == 0, flat=0.45)
    # face-framing curls
    for s in (1, -1):
        for k in range(2):
            a = s * (70 + k * 6)
            path = [(a, 30 - k * 4, 0.006), (a + s * 4, 10, 0.012), (a + s * 6, -12, 0.016), (a + s * 2, -30, 0.012)]
            add(path, [0.008, 0.009, 0.008, 0.003], light=k == 0, flat=0.6)
    # tie point + ponytail
    loc, nrm = hu.scalp_hit2(bvh, C, 0, tie_b)
    tie = loc + nrm * 0.012
    axis = (nrm + V(0, 0.9, 0.05)).normalized()
    side = V(1, 0, 0)
    up2 = axis.cross(side).normalized()
    sc_pts = [tie + (side * math.cos(a) + up2 * math.sin(a)) * 0.026 for a in
              [2 * math.pi * k / 24 for k in range(24)]]
    mb.add(ak.loop_tube(sc_pts, 0.011, ring=10), M['scrunchie'], {'head': 1.0})
    for k in range(16):
        ang = 2 * math.pi * k / 16
        sp = rnd.uniform(0.6, 1.0)
        off = (side * math.cos(ang) + up2 * math.sin(ang)) * 0.02 * sp
        lat = side * math.cos(ang) * rnd.uniform(0.02, 0.06)
        p0 = tie + off
        p1 = tie + axis * 0.06 + off * 2.2 + V(0, 0.0, 0.01)
        p2 = tie + V(0, 0.11, -0.05) + lat + off
        p3 = tie + V(0, 0.12, -0.15) + lat * 1.4
        curl = rnd.uniform(0, 2 * math.pi)
        p4 = p3 + V(math.cos(curl) * 0.03, 0.02 + math.sin(curl) * 0.02, -0.06)
        p5 = p4 + V(-math.cos(curl) * 0.025, -0.02, -0.03)
        t = ak.tube([p0, p1, p2, p3, p4, p5], [(0.016, 0.012), (0.028, 0.02), (0.03, 0.022), (0.024, 0.018),
                                                  (0.014, 0.011), (0.004, 0.003)], ring=8, per=5)
        mb.add(t, M['hair_lt' if k % 3 else 'hair'], {'head': 1.0})
    ob = mb.build(coll, arm)
    ak.add_outline(ob, 0.003)
    return ob


def hair_m(coll, arm, head, bvh, M, name):
    C = head['C']
    rnd = random.Random(5)
    mb = ak.MeshBuilder(name)
    mb.add(hu.scalp_cap(head, hu.hairline_mask(42, 80, 118), 0.005), M['hair'], {'head': 1.0})

    def add(path, radii, light, flat=0.55):
        mb.add(hu.clump2(bvh, C, path, radii, ring=8, per=5, flat=flat), M['hair_lt' if light else 'hair'],
               {'head': 1.0})
    # tousled top swept up and to his left
    for i, a0 in enumerate([-40, -28, -16, -4, 8, 20, 32, 44]):
        j = rnd.uniform(-5, 5)
        path = [(a0, 48, 0.004), (a0 + 6 + j, 64, 0.035), (a0 + 12, 84, 0.03), (a0 + 10, 112, 0.018), (a0 + 6, 140, 0.006)]
        add(path, [0.01, 0.024, 0.022, 0.016, 0.005], light=i % 2 == 0)
    for s in (1, -1):
        for a0, b0 in ((60, 30), (72, 18), (80, 5)):
            add([(s * a0, b0, 0.003), (s * (a0 - 4), b0 + 40, 0.01), (s * (a0 - 14), b0 + 85, 0.01),
                 (s * (a0 - 24), 150, 0.004)], [0.009, 0.013, 0.012, 0.004], light=False)
    for a0 in (-40, -14, 14, 40):
        add([(a0, 118, 0.016), (a0, 150, 0.01), (a0 * 0.9, 180, 0.003)], [0.02, 0.015, 0.004], light=a0 > 0)
    ob = mb.build(coll, arm)
    ak.add_outline(ob, 0.003)
    return ob


def beard(coll, arm, P, head, M, name):
    F = P['face']

    def mask(d, p):
        if p.y > 0.035 or d.z > -0.05:
            return False
        lipgap = abs(p.x) < 0.02 and abs(p.z - F['mouth_z']) < 0.006
        if lipgap:
            return False
        # leave the cheeks clear above the jaw line
        if d.z > -0.32 and d.y < -0.55 and abs(p.x) < 0.055:
            return abs(p.x) < 0.028 and p.z < F['mouth_z'] + 0.02   # moustache
        return True
    part = hu.scalp_cap(head, mask, 0.004)
    mb = ak.MeshBuilder(name)
    mb.add(part, M['beard'], {'head': 1.0})
    ob = mb.build(coll, arm)
    ak.add_outline(ob, 0.0025)
    return ob


# ------------------------------------------------------------------ build
def build(coll, variant='f'):
    P = params(variant)
    M = materials(variant)
    pre = 'HeroM_' if variant == 'm' else 'Hero_'
    head = hu.sculpt_head(P)
    bvh, eyes = hu.face_anchors(P, head)
    J = hu.joints(P)
    arm = hu.build_armature(pre + 'Rig', J, eyes, coll)

    mb = ak.MeshBuilder(pre + 'Body')
    torso = hu.body(mb, P, J, {'torso': M['scrubs'], 'skin': M['skin'], 'sleeve': M['scrubs'],
                               'leg': M['scrubs'], 'shoe': M['boot']})
    tb = ak.bvh_from(torso)
    tw = hu.torso_weights(P, J)
    # scrub V-neck: skin patch plus a darker trim along both edges
    nz = P['neck_z']
    lo, hi, top_w = nz - 0.088, nz + 0.012, 0.056
    mb.add(hu.front_patch(tb, lo, hi, lambda z: top_w * ss(lo - 0.002, hi, z)), M['chest'], tw)
    for sx in (1, -1):
        mb.add(hu.front_strip(tb, [(0, lo - 0.004), (sx * top_w, hi)], 0.011), M['scrubs_dk'], tw)
    body = mb.build(coll, arm)
    sub = body.modifiers.new('Smooth', 'SUBSURF')
    sub.levels, sub.render_levels = 0, 1
    ak.add_outline(body, 0.0045)

    hb = ak.MeshBuilder(pre + 'Head')
    hb.add(head, M['face'], {'head': 1.0}, colors=head_colours(P, head, variant))
    hu.ears(hb, P, bvh, M | {'skin': M['face']})
    if variant != 'm':
        for sx in (1, -1):
            o = V(head['C'].x + sx * 0.5, head['C'].y + 0.006, head['C'].z + P['face']['ear_z'] - 0.026)
            hit = bvh.ray_cast(o, V(-sx, 0, 0))
            if hit[0] is not None:
                e0 = hit[0] + V(sx * 0.006, 0.006, -0.004)
                hb.add(ak.uv_sphere(e0, 0.0032, segs=8, rings=6), M['earring'], {'head': 1.0})
                hb.add(ak.uv_sphere(e0 + V(0, 0, -0.011), (0.003, 0.003, 0.006), segs=8, rings=6),
                       M['earring'], {'head': 1.0})
    headob = hb.build(coll, arm)
    hu.soften_face_normals(headob, head)
    ak.add_outline(headob, 0.0032)

    eb = ak.MeshBuilder(pre + 'Eyes')
    hu.eyeballs(eb, P, eyes, M)
    eyeob = eb.build(coll, arm)
    lids = hu.lids(coll, arm, P, eyes, M, pre + 'Lids')
    ak.add_outline(lids, 0.0012)
    brows = hu.brows(coll, arm, P, bvh, M, pre + 'Brows')
    mouth = hu.mouth(coll, arm, P, bvh, M, pre + 'Mouth')
    hairob = (hair_m if variant == 'm' else hair_f)(coll, arm, head, bvh, M, pre + 'Hair')
    extra = [beard(coll, arm, P, head, M, pre + 'Beard')] if variant == 'm' else []
    kit(coll, arm, P, J, M, variant)
    ak.no_cast(headob, eyeob, lids, brows, mouth, hairob, *extra)
    return dict(arm=arm, face={'lids': lids, 'brows': brows, 'mouth': mouth}, expressions=EXPRESSIONS,
                head=headob, P=P)
