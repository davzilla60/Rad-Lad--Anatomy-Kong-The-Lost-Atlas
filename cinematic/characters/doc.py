"""Dr Dissection, after assets/concept/character_sheet.png.

Swept-back grey hair with silver streaks, black rectangular glasses, square
stubbled jaw, white lab coat over a charcoal open-collar shirt, two pens in
the breast pocket, dark trousers and shoes.
"""
import math
import random
from mathutils import Vector, Matrix
import akcore as ak
import humanoid as hu
import pixel

V = hu.V
ss = ak.smoothstep

P = dict(
    pelvis_z=0.98, waist_z=1.12, chest_z=1.32, neck_z=1.515, head_z=1.578,
    head_c=(0, -0.014, 1.684), head_r=(0.095, 0.111, 0.126),
    shoulder_x=0.19, shoulder_z=1.47, arm_drop=54, upper_arm=0.30, forearm=0.27, hand_scale=1.06,
    hip_x=0.092, hip_z=0.94, knee_z=0.51, ankle_z=0.085, foot_len=0.27,
    neck_r=0.046,
    arm_r=(0.052, 0.046, 0.038, 0.037, 0.03),
    leg_r=(0.088, 0.077, 0.058, 0.056, 0.052),
    shoe_w=0.05, shoe_h=0.052,
    torso=[(0.86, 0.12, 0.09, 0.0, 2.4), (0.95, 0.165, 0.11, 0.0, 2.6), (1.05, 0.155, 0.104, 0.0, 2.6),
           (1.16, 0.150, 0.100, 0.005, 2.6), (1.27, 0.170, 0.110, 0.0, 2.8), (1.38, 0.185, 0.112, 0.005, 3.0),
           (1.46, 0.172, 0.100, 0.015, 3.0), (1.53, 0.075, 0.062, 0.02, 2.2)],
    face=dict(
        skull_back=0.06, crown=0.0, jaw=0.70, jaw_square=0.06, face_flat=0.06, chin_fwd=0.06,
        chin_flat=0.45, temple=0.0, chin_len=0.9,
        eye_x=0.036, eye_z=0.0, eye_r=0.0135, eye_sink=0.5,
        nose_bridge_z=-0.004, nose_tip_z=-0.040, nose_len=0.03, nose_w=(0.0095, 0.0155), nose_under=0.15,
        brow=0.009, socket=0.007, mouth_z=-0.060, lips=0.004, chin=0.006, cheek=0.006,
        lid_up=6, lid_low=-22, lash=10, iris_rings=6, pupil_rings=3,
        brow_z=0.021, brow_in=0.011, brow_out=0.057, brow_th=0.0085, brow_arch=0.0035,
        mouth_w=0.024, ear_z=-0.014, ear_size=1.05,
    ),
)

EXPRESSIONS = {
    'neutral': {},
    'calculating': {'brows': {'angry': 0.55, 'up.L': 0.7}, 'lids': {'narrow.R': 0.7, 'squint': 0.15},
                    'mouth': {'smirk.L': 0.9}},
    'amused': {'brows': {'up': 0.35}, 'lids': {'squint': 0.35}, 'mouth': {'smile': 0.75, 'smirk.L': 0.5}},
    'frustrated': {'brows': {'angry': 1.0}, 'lids': {'wide': 0.35}, 'mouth': {'grin': 1.0}},
    'victorious': {'brows': {'up': 0.8}, 'lids': {'squint': 0.7}, 'mouth': {'laugh': 1.0}},
}


def materials():
    t = ak.toon
    M = {
        'skin': t('Doc_Skin', '#d99a6c'),
        'chest': t('Doc_SkinChest', '#d99a6c'),
        'face': t('Doc_Face', '#d99a6c', attr='Col'),
        'shirt': t('Doc_Shirt', '#36303c'),
        'collar': t('Doc_ShirtCollar', '#3d3644'),
        'trousers': t('Doc_Trousers', '#2f2a37'),
        'shoe': t('Doc_Shoes', '#3c2a25', hl='#8a6a5c', hl_rough=0.2, hl_cut=0.6),
        'coat': t('Doc_Coat', '#efebf4'),
        'lapel': t('Doc_CoatLapel', '#f4f1f8'),
        'pocket': t('Doc_CoatPocket', '#eae6f0'),
        'coat_in': t('Doc_CoatLining', '#d9d3e3'),
        'button': t('Doc_Button', '#b8b2c4'),
        'hair': t('Doc_Hair', '#6e6978', hl='#a9a5b6', hl_rough=0.35, hl_cut=0.5),
        'hair_lt': t('Doc_HairLight', '#c4c0cf', hl='#f1eff7', hl_rough=0.35, hl_cut=0.5),
        'hair_mid': t('Doc_HairMid', '#97929f', hl='#d2cedc', hl_rough=0.35, hl_cut=0.5),
        'brow': ak.flat('Doc_Brow', '#3e3944'),
        'glasses': t('Doc_Glasses', '#17121c', hl='#8f8aa0', hl_rough=0.15, hl_cut=0.5),
        'pen_b': t('Doc_PenBlue', '#3a6fd8'),
        'pen_o': t('Doc_PenOrange', '#e0782a'),
        'pen_cap': t('Doc_PenCap', '#d8d5de'),
        'sclera': t('Doc_Sclera', '#f2eee8'),
        'iris': t('Doc_Iris', '#3b2a22'),
        'pupil': ak.flat('Doc_Pupil', '#0d0a10'),
        'glint': ak.flat('Doc_Glint', '#ffffff'),
        'lid': t('Doc_Lid', '#d99a6c'),
        'lash': ak.flat('Doc_Lash', '#1e1520'),
        'lash_low': t('Doc_LashLow', '#a86a4c'),
        'mouth': ak.flat('Doc_Mouth', '#4a1f26'),
        'teeth': t('Doc_Teeth', '#f1ebe1'),
    }
    pixel.noline(M['glint'], M['pupil'], M['mouth'], M['teeth'], M['brow'], M['lash'], M['iris'])
    return M


def head_colours(head):
    """Stubble on jaw, chin and upper lip; faint warmth on the cheeks."""
    cols = []
    C = head['C']
    F = P['face']
    for p, d in zip(head['local'], head['dir']):
        c = [1.0, 1.0, 1.0]
        front = ss(0.3, -0.4, d.y)
        jaw = ss(-0.15, -0.45, d.z) * ss(0.55, 0.1, d.y)
        lipgap = hu.gauss(p.x ** 2, 0.02) * hu.gauss((p.z - F['mouth_z']) ** 2, 0.006)
        upper = hu.gauss(p.x ** 2, 0.022) * hu.gauss((p.z - (F['mouth_z'] + 0.014)) ** 2, 0.007) * front
        st = max(jaw * (1 - lipgap), upper * 0.8)
        st *= 1 - ss(-0.9, -1.0, d.z) * 0.3
        k = 0.8
        c = [1 - st * (1 - 0.80 * k), 1 - st * (1 - 0.76 * k), 1 - st * (1 - 0.86 * k)]
        cols.append((*c, 1.0))
    return cols


def coat(coll, arm, J, M):
    mb = ak.MeshBuilder('Doc_Coat')
    hip = P['hip_z']

    def gap(z):
        tbl = [(1.53, 64), (1.45, 50), (1.33, 30), (1.22, 11), (1.12, 3), (0.95, 5), (0.46, 17)]
        for (z0, g0), (z1, g1) in zip(tbl, tbl[1:]):
            if z1 <= z <= z0:
                return math.radians(g1 + (g0 - g1) * (z - z1) / (z0 - z1))
        return math.radians(tbl[0][1] if z > tbl[0][0] else tbl[-1][1])

    def size(z):
        if z >= hip:
            _, wx, wy, yo, e = hu.torso_size_at(P, min(z, 1.51))
            grow = 0.024 if z < 1.46 else 0.024 + (z - 1.46) * 0.2
            return wx + grow, wy + 0.026, yo, min(e, 2.7)
        k = hip - z
        return 0.189 + 0.11 * k, 0.136 + 0.07 * k, 0.0 + 0.03 * k, 2.6

    zs = [0.46 + i * 0.02 for i in range(54)]
    nring = 44
    rings = []
    for z in zs:
        wx, wy, yo, e = size(z)
        g = gap(z)
        r = []
        for k in range(nring):
            a = g + (2 * math.pi - 2 * g) * k / (nring - 1)
            x, y = hu.super_pt(a, wx, wy, yo, e)
            # hem swings out a touch at the back
            r.append(V(x, y, z))
        rings.append(r)
    body = ak.loft(rings, closed=False)
    tw = hu.torso_weights(P, J)

    def cw(v, i=None):
        if v.z >= hip:
            return tw(v)
        s = 'L' if v.x > 0 else 'R'
        t = ss(hip, P['knee_z'], v.z) * 0.55 * ss(0.0, 0.08, abs(v.x))
        return {'hips': 1 - t, f'thigh.{s}': t}
    mb.add(body, M['coat'], cw)

    # lapels: flaps lying on the coat beside the opening
    for side in (1, -1):
        lrows = []
        for z in [1.215 + i * 0.015 for i in range(20)]:
            if z > 1.50:
                break
            wx, wy, yo, e = size(z)
            g = gap(z)
            lw = math.radians(26) * ss(1.215, 1.43, z) * (1 - 0.35 * ss(1.44, 1.50, z))
            row = []
            for k in range(6):
                a = g + lw * k / 5
                if side < 0:
                    a = 2 * math.pi - a
                x, y = hu.super_pt(a, wx + 0.006, wy + 0.006, yo, e)
                row.append(V(x, y, z))
            if side < 0:
                row.reverse()
            lrows.append(row)
        mb.add(ak.loft(lrows, closed=False), M['lapel'], tw)

    # collar band round the back of the neck
    crows = []
    for z, wx, wy in ((1.48, 0.11, 0.09), (1.51, 0.094, 0.082), (1.545, 0.09, 0.08)):
        g = math.radians(58)
        row = []
        for k in range(26):
            a = g + (2 * math.pi - 2 * g) * k / 25
            x, y = hu.super_pt(a, wx, wy, 0.022, 2.2)
            row.append(V(x, y, z))
        crows.append(row)
    mb.add(ak.loft(crows, closed=False), M['coat'], {'chest': 0.5, 'neck': 0.5})

    # sleeves (open at the cuff)
    for s in ('L', 'R'):
        S, E, W = J[f'shoulder.{s}'], J[f'elbow.{s}'], J[f'wrist.{s}']
        hd = J['_hd' if s == 'L' else '_hd.R']
        inner = S + (J[f'clav.{s}'] - S) * 0.35
        pts = [inner, S, (S + E) / 2, E, (E + W) / 2, W - hd * 0.012]
        ar = P['arm_r']
        g = 0.02
        rad = [ar[0] + g, ar[0] + g + 0.004, ar[1] + g, ar[2] + g, ar[3] + g * 1.1, ar[4] + g * 1.35]
        sl = ak.tube(pts, rad, ring=18, per=5, caps=(True, False))

        def aw(x, s=s):
            if x < 1.0:
                return hu.blend({f'clavicle.{s}': 1}, {f'upper_arm.{s}': 1}, ss(0.3, 1.1, x))
            return hu.blend({f'upper_arm.{s}': 1}, {f'forearm.{s}': 1}, ss(2.75, 3.25, x))
        mb.add(sl, M['coat'], [aw(x) for x in sl['s']])

    # breast pocket (character's left) + pens, hip pockets, buttons
    z0 = 1.30
    wx, wy, yo, e = size(z0)
    a = math.radians(38)
    x, y = hu.super_pt(a, wx + 0.004, wy + 0.004, yo, e)
    pk = ak.rounded_box(V(x, y, z0), (0.07, 0.006, 0.075), r=0.5, segs=1,
                        rot=Matrix.Rotation(-a * 0.7, 3, 'Z'))
    mb.add(ak.fix_normals(pk), M['pocket'], {'chest': 1.0})
    for i, (dx, mat) in enumerate(((-0.014, 'pen_b'), (0.012, 'pen_o'))):
        px = x + dx
        base = V(px, y - 0.002, z0 + 0.01)
        pen = ak.tube([base, base + V(0, 0, 0.06)], 0.0055, ring=10, per=2)
        mb.add(pen, M[mat], {'chest': 1.0})
        clipm = ak.rounded_box(base + V(0, -0.0065, 0.035), (0.0035, 0.002, 0.035), r=0.4, segs=1)
        mb.add(ak.fix_normals(clipm), M['pen_cap'], {'chest': 1.0})
    for side in (1, -1):
        zp = 0.86
        wx2, wy2, yo2, e2 = size(zp)
        ap = math.radians(40) if side > 0 else 2 * math.pi - math.radians(40)
        x2, y2 = hu.super_pt(ap, wx2 + 0.004, wy2 + 0.004, yo2, e2)
        fl = ak.rounded_box(V(x2, y2, zp), (0.11, 0.006, 0.03), r=0.5, segs=1,
                            rot=Matrix.Rotation(-math.atan2(x2, -y2) * 0.8, 3, 'Z'))
        mb.add(ak.fix_normals(fl), M['pocket'], cw(V(x2, y2, zp)))
    for zb in (1.19, 1.06, 0.93):
        wx3, wy3, yo3, e3 = size(zb)
        g = gap(zb)
        x3, y3 = hu.super_pt(g + math.radians(5), wx3 + 0.004, wy3 + 0.004, yo3, e3)
        bt = ak.uv_sphere(V(x3, y3, zb), (0.007, 0.003, 0.007), segs=10, rings=6)
        mb.add(bt, M['button'], cw(V(x3, y3, zb)))

    ob = mb.build(coll, arm)
    th = ob.modifiers.new('Cloth', 'SOLIDIFY')
    th.thickness = 0.006
    th.offset = -1
    th.use_rim = True
    # move the solidify before the armature? no: order armature -> cloth -> ink
    ak.add_outline(ob, 0.0055)
    return ob


def glasses(mb, bvh, eyes, M):
    F = P['face']
    C = V(*P['head_c'])
    bridge = ak.project_front(bvh, C.x, C.z + F['eye_z'] + 0.004)[0]
    ly = min(eyes['L'].y - F['eye_r'] - 0.013, bridge.y - 0.006)
    w, h, cr = 0.046, 0.029, 0.008
    rims = {}
    for s, sx in (('L', 1), ('R', -1)):
        cx = eyes[s].x + sx * 0.003
        cz = eyes[s].z + 0.001
        pts = []
        for corner, (qx, qz) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
            ox, oz = qx * (w / 2 - cr), qz * (h / 2 - cr)
            a0 = math.pi / 2 * corner
            for k in range(6):
                a = a0 + math.pi / 2 * k / 5
                px = cx + ox + math.cos(a) * cr
                pz = cz + oz + math.sin(a) * cr
                # wrap the lens plane gently round the face
                py = ly + 0.01 * ((px - C.x) / 0.07) ** 2
                pts.append(V(px, py, pz))
        mb.add(ak.loop_tube(pts, (0.0024, 0.0028), ring=6), M['glasses'], {'head': 1.0})
        rims[s] = (cx, cz)
    # bridge
    lx = rims['L'][0] - w / 2
    rx = rims['R'][0] + w / 2
    bz = rims['L'][1] + 0.004
    mb.add(ak.tube([V(rx, ly + 0.0005, bz), V(C.x, ly - 0.001, bz + 0.003), V(lx, ly + 0.0005, bz)], 0.0021,
                   ring=6, per=4), M['glasses'], {'head': 1.0})
    # temples back to the ears
    for s, sx in (('L', 1), ('R', -1)):
        ox = rims[s][0] + sx * w / 2
        oz = rims[s][1] + h / 2 - 0.006
        pts = [V(ox, ly + 0.012 * (ox / 0.07) ** 2, oz)]
        for yy, dz in ((0.0, 0.002), (0.035, 0.0), (0.07, -0.01)):
            o = V(C.x + sx * 0.5, C.y + yy, C.z + F['eye_z'] + dz)
            hit = bvh.ray_cast(o, V(-sx, 0, 0))
            p = hit[0] if hit[0] is not None else o
            pts.append(p + V(sx * 0.0045, 0, 0))
        mb.add(ak.tube(pts, 0.0019, ring=6, per=4), M['glasses'], {'head': 1.0})


def hair(coll, arm, head, bvh, M):
    C = head['C']
    rnd = random.Random(7)
    mb = ak.MeshBuilder('Doc_Hair')
    cap = hu.scalp_cap(head, hu.hairline_mask(40, 78, 122), 0.005)
    mb.add(cap, M['hair'], {'head': 1.0})

    tones = ('hair', 'hair_mid', 'hair_lt')

    def add(path, radii, tone, flat=0.5):
        tb = hu.clump2(bvh, C, path, radii, ring=8, per=5, flat=flat)
        mb.add(tb, M[tones[tone] if isinstance(tone, int) else tone], {'head': 1.0})

    def wavy(a0, betas, lifts, amp):
        """path with a sideways wave so the clumps don't run in rails"""
        ph = rnd.uniform(0, math.pi * 2)
        return [(a0 * (1 + 0.12 * k / len(betas)) + amp * math.sin(ph + k * 1.7), b, l)
                for k, (b, l) in enumerate(zip(betas, lifts))]

    # swept-back top, voluminous at the front: 15 clumps, mixed tones
    for i, a0 in enumerate([-46 + i * 6.6 for i in range(15)]):
        betas = [49 + abs(a0) * 0.1, 62, 80, 104, 130, 154, 174]
        lifts = [0.003, 0.034 - abs(a0) * 0.0002, 0.034, 0.028, 0.02, 0.011, 0.005]
        add(wavy(a0, betas, lifts, rnd.uniform(3, 7)), [0.004, 0.017, 0.02, 0.019, 0.016, 0.011, 0.004],
            tone=rnd.choice((0, 1, 1, 2, 2, 2)))
    # upper layer: the silver streaks that catch the light
    for i, a0 in enumerate([-34, -21, -8, 5, 18, 31]):
        betas = [55, 68, 90, 116, 140, 160]
        lifts = [0.012, 0.05, 0.046, 0.036, 0.022, 0.01]
        add(wavy(a0, betas, lifts, rnd.uniform(4, 8)), [0.005, 0.016, 0.019, 0.016, 0.011, 0.004],
            tone=2 if i % 2 == 0 else 1)
    # sides, swept back above the ears
    for s in (1, -1):
        for j, (a0, b0) in enumerate(((54, 34), (64, 26), (73, 16), (80, 4))):
            path = [(s * a0, b0, 0.003), (s * (a0 + 2), b0 + 30, 0.012), (s * (a0 - 4), b0 + 75, 0.014),
                    (s * (a0 - 12), b0 + 120, 0.01), (s * (a0 - 20), 165, 0.004)]
            add(path, [0.008, 0.015, 0.016, 0.013, 0.004], tone=j % 3)
    # back
    for i, a0 in enumerate([-50, -37, -24, -11, 2, 15, 28, 41, 54]):
        path = wavy(a0, [112, 140, 168, 192], [0.018, 0.014, 0.009, 0.004], 4)
        add(path, [0.016, 0.018, 0.014, 0.005], tone=i % 3)
    # loose locks over the forehead (his right)
    add([(-12, 66, 0.04), (-16, 56, 0.034), (-20, 45, 0.02), (-22, 38, 0.01)], [0.009, 0.008, 0.006, 0.002],
        tone=2, flat=0.6)
    add([(-4, 64, 0.04), (-6, 55, 0.03), (-10, 48, 0.016)], [0.007, 0.006, 0.0015], tone=1, flat=0.6)
    ob = mb.build(coll, arm)
    ak.add_outline(ob, 0.0028)
    return ob


def build(coll):
    M = materials()
    head = hu.sculpt_head(P)
    bvh, eyes = hu.face_anchors(P, head)
    J = hu.joints(P)
    arm = hu.build_armature('Doc_Rig', J, eyes, coll)

    # body
    mb = ak.MeshBuilder('Doc_Body')
    torso = hu.body(mb, P, J, {'torso': M['shirt'], 'skin': M['skin'], 'sleeve': M['shirt'],
                               'leg': M['trousers'], 'shoe': M['shoe']})
    tb = ak.bvh_from(torso)
    tw = hu.torso_weights(P, J)
    # open neck: a clean V of skin projected onto the shirt
    nz = P['neck_z']
    mb.add(hu.front_patch(tb, nz - 0.075, nz + 0.012, lambda z: 0.052 * ss(nz - 0.078, nz + 0.012, z) ** 0.9),
           M['chest'], tw)
    # stand collar round the back of the neck, open at the front
    nr = P['neck_r']
    rows = []
    for z, g in ((nz - 0.025, 1.12), (nz + 0.02, 1.08), (nz + 0.045, 1.1)):
        row = []
        for k in range(24):
            a = math.radians(38) + (2 * math.pi - math.radians(76)) * k / 23
            row.append(V(math.sin(a) * (nr + 0.016) * g, J['neck'].y - math.cos(a) * (nr + 0.012) * g, z))
        rows.append(row)
    mb.add(ak.loft(rows, closed=False), M['collar'], {'neck': 0.6, 'chest': 0.4})
    # collar points lying open on the chest
    for sx in (1, -1):
        q = hu.front_quad(tb, (sx * 0.028, nz + 0.02), (sx * 0.078, nz + 0.01),
                          (sx * 0.072, nz - 0.07), (sx * 0.060, nz - 0.07), offset=0.006)
        mb.add(q, M['collar'], tw)
    body = mb.build(coll, arm)
    sub = body.modifiers.new('Smooth', 'SUBSURF')
    sub.levels, sub.render_levels = 0, 1
    ak.add_outline(body, 0.005)

    # head
    hb = ak.MeshBuilder('Doc_Head')
    hb.add(head, M['face'], {'head': 1.0}, colors=head_colours(head))
    hu.ears(hb, P, bvh, M | {'skin': M['face']})
    headob = hb.build(coll, arm)
    hu.soften_face_normals(headob, head)
    ak.add_outline(headob, 0.0035)

    eb = ak.MeshBuilder('Doc_Eyes')
    hu.eyeballs(eb, P, eyes, M)
    eyeob = eb.build(coll, arm)

    lids = hu.lids(coll, arm, P, eyes, M, 'Doc_Lids')
    ak.add_outline(lids, 0.0012)
    brows = hu.brows(coll, arm, P, bvh, M, 'Doc_Brows')
    mouth = hu.mouth(coll, arm, P, bvh, M, 'Doc_Mouth')

    gb = ak.MeshBuilder('Doc_Glasses')
    glasses(gb, bvh, eyes, M)
    gl = gb.build(coll, arm)

    hairob = hair(coll, arm, head, bvh, M)
    coat(coll, arm, J, M)
    ak.no_cast(headob, eyeob, lids, brows, mouth, gl, hairob)
    face = {'lids': lids, 'brows': brows, 'mouth': mouth}
    return dict(arm=arm, face=face, expressions=EXPRESSIONS, head=headob, P=P)
