"""Stylised humanoid toolkit for the cinematic characters.

One parameter dict (P) describes a character's proportions. From it:
  joints(P)            skeleton points (left side mirrored to right)
  sculpt_head(P)       head mesh: an ellipsoid shaped by jaw/chin/nose/brow terms
  face_anchors(...)    eye centres etc. found by ray casting the sculpted head
  build_armature(...)  deform bones + eye bones + (disabled) leg IK
  body(...)            torso loft, neck, arm/leg tubes, hands, shoes into a MeshBuilder
  eyes/lids/brows/mouth/ears   face rig parts with shape keys
  hair helpers         clumps that follow the scalp, scalp caps from the head mesh

Coordinates: metres, Z up, the character faces -Y, its left is +X (.L).
"""
import math
import bpy
from mathutils import Vector, Matrix
import akcore as ak

ss = ak.smoothstep


def V(*a):
    return Vector(a)


def mir(v):
    return Vector((-v.x, v.y, v.z))


def gauss(d2, s):
    return math.exp(-d2 / (s * s))


# ===================================================================== skeleton
def joints(P):
    J = {}
    J['pelvis'] = V(0, 0.0, P['pelvis_z'])
    J['waist'] = V(0, 0.01, P['waist_z'])
    J['chest'] = V(0, 0.012, P['chest_z'])
    J['neck'] = V(0, 0.022, P['neck_z'])
    J['head'] = V(0, 0.018, P['head_z'])
    J['head_top'] = V(0, 0.018, P['head_c'][2] + P['head_r'][2])

    a = math.radians(P['arm_drop'])
    S = V(P['shoulder_x'], 0.015, P['shoulder_z'])
    d = V(math.cos(a), 0, -math.sin(a))
    E = S + d * P['upper_arm'] + V(0, 0.03, 0)
    W = E + d * P['forearm'] + V(0, -0.035, 0)
    hd = (W - E).normalized()
    n = V(-math.sin(a), 0, -math.cos(a))
    n = (n - hd * n.dot(hd)).normalized()         # palm normal, toward the body
    w = hd.cross(n).normalized()
    if w.y > 0:
        w = -w                                     # across the palm, toward the thumb (front)
    J['clav.L'] = V(0.035, 0.02, P['shoulder_z'] - 0.02)
    J['shoulder.L'], J['elbow.L'], J['wrist.L'] = S, E, W
    J['_hd'], J['_n'], J['_w'] = hd, n, w
    hs = P.get('hand_scale', 1.0)
    hl = 0.085 * hs
    J['knuckle.L'] = W + hd * hl
    fl = 0.088 * hs
    for nm, off, lf, spread in (('index', 0.026, 0.95, 0.07), ('middle', 0.008, 1.0, 0.0),
                                ('ring', -0.010, 0.94, -0.07), ('pinky', -0.026, 0.76, -0.15)):
        L = fl * lf
        k0 = W + hd * hl * (0.97 if nm != 'pinky' else 0.9) + w * off * hs
        fd = (hd + w * spread).normalized()
        k1 = k0 + fd * L * 0.45 + n * 0.004
        k2 = k1 + fd * L * 0.31 + n * 0.007
        k3 = k2 + fd * L * 0.24 + n * 0.007
        for i, k in enumerate((k0, k1, k2, k3)):
            J[f'{nm}{i}.L'] = k
    t0 = W + hd * 0.018 * hs + w * 0.02 * hs + n * 0.008 * hs
    d1 = (hd * 0.55 + w * 0.6 + n * 0.45).normalized()
    d2 = (hd * 0.75 + w * 0.35 + n * 0.35).normalized()
    t1 = t0 + d1 * 0.036 * hs
    t2 = t1 + d2 * 0.028 * hs
    t3 = t2 + d2 * 0.023 * hs
    for i, k in enumerate((t0, t1, t2, t3)):
        J[f'thumb{i}.L'] = k

    hx = P['hip_x']
    J['hip.L'] = V(hx, 0.0, P['hip_z'])
    J['knee.L'] = V(hx * 0.96, -0.015, P['knee_z'])
    A = V(hx * 0.93, 0.02, P['ankle_z'])
    J['ankle.L'] = A
    fl = P['foot_len']
    J['heel.L'] = V(hx * 0.93, A.y + 0.04, 0.035)
    J['ball.L'] = V(hx * 0.95, A.y - fl * 0.62, 0.026)
    J['toe.L'] = V(hx * 0.95, A.y - fl * 0.92, 0.028)

    for k in list(J):
        if k.endswith('.L'):
            J[k[:-2] + '.R'] = mir(J[k])
    J['_hd.R'], J['_n.R'], J['_w.R'] = mir(hd), mir(n), mir(w)
    return J


FINGERS = ('index', 'middle', 'ring', 'pinky', 'thumb')


def bone_specs(J, eyes):
    fwd = V(0, -1, 0)
    up = V(0, 0, 1)
    B = [
        ('root', V(0, 0, 0), V(0, -0.3, 0), None, up, False, False),
        ('hips', J['pelvis'], J['waist'], 'root', fwd, True, False),
        ('spine', J['waist'], J['chest'], 'hips', fwd, True, True),
        ('chest', J['chest'], J['neck'], 'spine', fwd, True, True),
        ('neck', J['neck'], J['head'], 'chest', fwd, True, True),
        ('head', J['head'], J['head_top'], 'neck', fwd, True, True),
    ]
    for s in ('L', 'R'):
        back = -J['_n' if s == 'L' else '_n.R']
        B += [
            (f'clavicle.{s}', J[f'clav.{s}'], J[f'shoulder.{s}'], 'chest', fwd, True, False),
            (f'upper_arm.{s}', J[f'shoulder.{s}'], J[f'elbow.{s}'], f'clavicle.{s}', fwd, True, True),
            (f'forearm.{s}', J[f'elbow.{s}'], J[f'wrist.{s}'], f'upper_arm.{s}', fwd, True, True),
            (f'hand.{s}', J[f'wrist.{s}'], J[f'knuckle.{s}'], f'forearm.{s}', back, True, True),
        ]
        for f in FINGERS:
            for i in range(3):
                B.append((f'{f}.0{i + 1}.{s}', J[f'{f}{i}.{s}'], J[f'{f}{i + 1}.{s}'],
                          f'hand.{s}' if i == 0 else f'{f}.0{i}.{s}', back, True, i > 0))
        B += [
            (f'thigh.{s}', J[f'hip.{s}'], J[f'knee.{s}'], 'hips', fwd, True, False),
            (f'shin.{s}', J[f'knee.{s}'], J[f'ankle.{s}'], f'thigh.{s}', fwd, True, True),
            (f'foot.{s}', J[f'ankle.{s}'], J[f'ball.{s}'], f'shin.{s}', up, True, True),
            (f'toe.{s}', J[f'ball.{s}'], J[f'toe.{s}'], f'foot.{s}', up, True, True),
            (f'foot_ik.{s}', J[f'ankle.{s}'], J[f'ball.{s}'], 'root', up, False, False),
        ]
        c = eyes[s]
        B.append((f'eye.{s}', c, c + V(0, -0.03, 0), 'head', up, True, False))
    return B


def build_armature(name, J, eyes, coll):
    ad = bpy.data.armatures.new(name)
    ad.display_type = 'OCTAHEDRAL'
    ob = bpy.data.objects.new(name, ad)
    coll.objects.link(ob)
    ob.show_in_front = True
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    specs = bone_specs(J, eyes)
    for nm, h, t, par, roll, deform, conn in specs:
        eb = ad.edit_bones.new(nm)
        eb.head, eb.tail = h, t
        eb.align_roll(roll)
        eb.use_deform = deform
    for nm, h, t, par, roll, deform, conn in specs:
        if par:
            eb = ad.edit_bones[nm]
            eb.parent = ad.edit_bones[par]
            eb.use_connect = conn
    bpy.ops.object.mode_set(mode='OBJECT')
    # leg IK, off by default: animation turns influence up when feet must plant
    for s in ('L', 'R'):
        ik = ob.pose.bones[f'shin.{s}'].constraints.new('IK')
        ik.target, ik.subtarget, ik.chain_count = ob, f'foot_ik.{s}', 2
        ik.influence = 0.0
        cr = ob.pose.bones[f'foot.{s}'].constraints.new('COPY_ROTATION')
        cr.target, cr.subtarget = ob, f'foot_ik.{s}'
        cr.influence = 0.0
    ob.select_set(False)
    return ob


# ===================================================================== weights
def chain_w(s, bones, band=0.2):
    """s runs 0..len(bones); bone i spans [i, i+1]; blend across joints."""
    nb = len(bones)
    j = int(round(s))
    if 0 < j < nb and abs(s - j) < band:
        t = ss(j - band, j + band, s)
        return {bones[j - 1]: 1 - t, bones[j]: t}
    return {bones[min(int(s), nb - 1)]: 1.0}


def blend(a, b, t):
    out = {}
    for k, v in a.items():
        out[k] = out.get(k, 0) + v * (1 - t)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v * t
    return out


# ===================================================================== body
def spline1d(samples, per=4):
    """Catmull-Rom through tuples; returns interpolated tuples."""
    P = [tuple(s) for s in samples]
    ext = [tuple(2 * a - b for a, b in zip(P[0], P[1]))] + P + \
          [tuple(2 * a - b for a, b in zip(P[-1], P[-2]))]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for k in range(per):
            t = k / per
            out.append(tuple(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                                    + (-a + 3 * b - 3 * c + d) * t ** 3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(P[-1])
    return out


def super_pt(a, wx, wy, yo, e):
    sa, ca = math.sin(a), math.cos(a)
    x = wx * math.copysign(abs(sa) ** (2 / e), sa)
    y = yo - wy * math.copysign(abs(ca) ** (2 / e), ca)
    return x, y


def torso_rings(P, ring=48, per=8, grow=0.0):
    """Rings for the torso loft. P['torso'] = [(z, wx, wy, yoff, exponent)]."""
    rows = spline1d(P['torso'], per)
    rings, meta = [], []
    bust = P.get('bust')
    for z, wx, wy, yo, e in rows:
        r = []
        for k in range(ring):
            a = 2 * math.pi * k / ring
            x, y = super_pt(a, wx + grow, wy + grow, yo, e)
            if bust and math.cos(a) > 0:
                amt, bz, bx = bust
                y -= amt * math.cos(a) ** 2 * gauss((abs(x) - bx) ** 2, 0.055) * gauss((z - bz) ** 2, 0.06)
            r.append(V(x, y, z))
        rings.append(r)
        meta.append(z)
    return rings, meta


def torso_size_at(P, z):
    rows = spline1d(P['torso'], 6)
    best = min(rows, key=lambda r: abs(r[0] - z))
    return best


def torso_weights(P, J):
    wz, cz, nz = P['waist_z'], P['chest_z'], P['neck_z']
    sx, sz = P['shoulder_x'], P['shoulder_z']

    def f(v, i=None):
        z = v.z
        t1 = ss(wz - 0.06, wz + 0.05, z)
        t2 = ss(cz - 0.07, cz + 0.04, z)
        t3 = ss(nz - 0.025, nz + 0.03, z)
        w = {'hips': 1 - t1, 'spine': t1 * (1 - t2), 'chest': t2 * (1 - t3), 'neck': t3}
        s = 'L' if v.x > 0 else 'R'
        tc = ss(0.5 * sx, 0.95 * sx, abs(v.x)) * ss(cz, sz - 0.01, z) * 0.75
        if tc > 0:
            w[f'clavicle.{s}'] = w['chest'] * tc
            w['chest'] *= 1 - tc
        return w
    return f


def body(mb, P, J, M):
    """Torso, neck, arms, hands, legs and shoes into MeshBuilder mb.
    M: materials dict with keys torso, skin, sleeve, leg, shoe, hand(optional).
    P['torso_mat'](z, angle) may return a material key per torso face."""
    # --- torso
    rings, zs = torso_rings(P)
    part = ak.loft(rings, cap_start=True, cap_end=True)
    ring = len(rings[0])
    fm = []
    tm = P.get('torso_mat')
    for fi, f in enumerate(part['faces']):
        if tm and fi < (len(rings) - 1) * ring:
            row, k = divmod(fi, ring)
            z = (zs[row] + zs[row + 1]) / 2
            a = 2 * math.pi * (k + 0.5) / ring
            fm.append(M[tm(z, a)])
        else:
            fm.append(None)
    mb.add(part, M['torso'], torso_weights(P, J), face_mats=fm)
    torso_part = part

    # --- neck
    nr = P['neck_r']
    neck = ak.tube([J['neck'] + V(0, 0, -0.07), J['neck'], J['head'] + V(0, -0.005, 0.03)],
                   [nr * 1.15, nr, nr * 0.95], ring=16, per=5)
    mb.add(neck, M['skin'], [blend({'chest': 1}, {'neck': 1}, ss(0.3, 0.9, s)) if s < 1 else
                             blend({'neck': 1}, {'head': 1}, ss(1.4, 1.9, s)) for s in neck['s']])

    # --- arms, hands
    for s in ('L', 'R'):
        S, E, W = J[f'shoulder.{s}'], J[f'elbow.{s}'], J[f'wrist.{s}']
        inner = S + (J[f'clav.{s}'] - S) * 0.45 + V(0, 0, -0.01)
        ar = P['arm_r']  # (shoulder, upper, elbow, forearm, wrist)
        pts = [inner, S, (S + E) / 2, E, (E + W) / 2, W]
        rad = [ar[0] * 0.9, ar[0], ar[1], ar[2], ar[3], ar[4]]
        arm = ak.tube(pts, rad, ring=16, per=5, caps=(True, True))
        sv = P.get('sleeve_s', 99)          # tube parameter where sleeves end
        fm = []
        for f in arm['faces']:
            sf = sum(arm['s'][i] for i in f) / len(f)
            fm.append(M['sleeve'] if sf < sv else M['skin'])
        bones = [f'clavicle.{s}', f'upper_arm.{s}', f'upper_arm.{s}', f'forearm.{s}', f'forearm.{s}']

        def aw(sv_, bones=bones):
            # map 5 tube segments to bones with a soft shoulder and elbow
            if sv_ < 1.0:
                return blend({bones[0]: 1}, {bones[1]: 1}, ss(0.4, 1.15, sv_))
            if sv_ < 3.0:
                return blend({bones[1]: 1}, {bones[3]: 1}, ss(2.75, 3.25, sv_))
            return blend({bones[3]: 1}, {f'hand.{s}': 1}, ss(4.85, 5.0, sv_))
        mb.add(arm, M['skin'], [aw(x) for x in arm['s']], face_mats=fm)
        hand(mb, P, J, s, M.get('hand', M['skin']))

    # --- legs
    for s in ('L', 'R'):
        H, K, A = J[f'hip.{s}'], J[f'knee.{s}'], J[f'ankle.{s}']
        lr = P['leg_r']  # (hip, thigh, knee, calf, ankle)
        top = H + V(-0.02 if s == 'L' else 0.02, 0, 0.07)
        pts = [top, H, (H + K) / 2, K, K + (A - K) * 0.35, A + V(0, 0, 0.02)]
        rad = [lr[0], lr[0], lr[1], lr[2], lr[3], lr[4]]
        leg = ak.tube(pts, rad, ring=18, per=5, caps=(True, True))

        def lw(x, s=s):
            if x < 1.0:
                return blend({'hips': 1}, {f'thigh.{s}': 1}, ss(0.2, 1.0, x))
            if x < 4.0:
                return blend({f'thigh.{s}': 1}, {f'shin.{s}': 1}, ss(2.75, 3.25, x))
            return {f'shin.{s}': 1}
        mb.add(leg, M['leg'], [lw(x) for x in leg['s']])
        shoe(mb, P, J, s, M['shoe'])
    return torso_part


def _face_front(part):
    """Flip a projected patch so it faces -Y (toward the viewer)."""
    v, f = part['verts'], part['faces']
    for q in f:
        n = (v[q[1]] - v[q[0]]).cross(v[q[2]] - v[q[0]])
        if n.length > 1e-12:
            if n.y > 0:
                part['faces'] = [tuple(reversed(x)) for x in f]
            break
    return part


def front_patch(bvh, zlo, zhi, hw, rows=10, cols=8, offset=0.0018, cx=0.0):
    """Patch projected onto a surface from the front: rows from zlo to zhi,
    each spanning x = cx +- hw(z). Straight, clean edges (necklines)."""
    verts, faces = [], []
    for i in range(rows + 1):
        z = zlo + (zhi - zlo) * i / rows
        w = hw(z)
        for j in range(cols + 1):
            x = cx - w + 2 * w * j / cols
            hit = ak.project_front(bvh, x, z)
            p = hit[0] + hit[1] * offset if hit else V(x, -0.3, z)
            verts.append(p)
    W = cols + 1
    for i in range(rows):
        for j in range(cols):
            faces.append((i * W + j, i * W + j + 1, (i + 1) * W + j + 1, (i + 1) * W + j))
    return _face_front(dict(verts=verts, faces=faces))


def front_quad(bvh, a, b, c, d, n=5, offset=0.004):
    """Bilinear patch through 2-D corners a,b (top edge) and d,c (bottom
    edge), projected from the front. Corners may coincide (triangles)."""
    A, B, Cc, D = (V(p[0], 0, p[1]) for p in (a, b, c, d))
    verts, faces = [], []
    for i in range(n + 1):
        t = i / n
        l, r = A.lerp(D, t), B.lerp(Cc, t)
        for j in range(n + 1):
            q = l.lerp(r, j / n)
            hit = ak.project_front(bvh, q.x, q.z)
            verts.append(hit[0] + hit[1] * offset if hit else V(q.x, -0.3, q.z))
    W = n + 1
    for i in range(n):
        for j in range(n):
            faces.append((i * W + j, i * W + j + 1, (i + 1) * W + j + 1, (i + 1) * W + j))
    return _face_front(dict(verts=verts, faces=faces))


def front_strip(bvh, pts2d, width, offset=0.0024, per=4):
    """Band of constant width along a 2-D (x, z) polyline, projected from
    the front (trims, seams)."""
    P = [V(x, 0, z) for x, z in pts2d]
    dense = []
    for a, b in zip(P, P[1:]):
        for k in range(per):
            dense.append(a.lerp(b, k / per))
    dense.append(P[-1])
    verts, faces = [], []
    for i, p in enumerate(dense):
        a = dense[max(i - 1, 0)]
        b = dense[min(i + 1, len(dense) - 1)]
        t = (b - a).normalized()
        n = V(-t.z, 0, t.x) * (width / 2)
        for q in (p - n, p + n):
            hit = ak.project_front(bvh, q.x, q.z)
            verts.append(hit[0] + hit[1] * offset if hit else V(q.x, -0.3, q.z))
    for i in range(len(dense) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    return _face_front(dict(verts=verts, faces=faces))


def hand(mb, P, J, s, mat):
    hs = P.get('hand_scale', 1.0)
    W, K = J[f'wrist.{s}'], J[f'knuckle.{s}']
    hd = J['_hd' if s == 'L' else '_hd.R']
    n = J['_n' if s == 'L' else '_n.R']
    palm = ak.tube([W - hd * 0.012, W + (K - W) * 0.5, K - hd * 0.004],
                   [(0.026 * hs, 0.012 * hs), (0.036 * hs, 0.014 * hs), (0.034 * hs, 0.012 * hs)],
                   ring=14, per=4, up=n)
    mb.add(palm, mat, [blend({f'forearm.{s}': 1}, {f'hand.{s}': 1}, ss(0.0, 0.5, x)) for x in palm['s']])
    for f in FINGERS:
        pts = [J[f'{f}{i}.{s}'] for i in range(4)]
        r = (0.0105 if f == 'thumb' else 0.0088) * hs
        fin = ak.tube(pts, [r, r * 0.95, r * 0.88, r * 0.8], ring=8, per=3)
        bones = [f'{f}.01.{s}', f'{f}.02.{s}', f'{f}.03.{s}']
        mb.add(fin, mat, [blend({f'hand.{s}': 1}, chain_w(x, bones), ss(0.0, 0.3, x)) for x in fin['s']])


def shoe(mb, P, J, s, mat):
    A, B, T, Hl = J[f'ankle.{s}'], J[f'ball.{s}'], J[f'toe.{s}'], J[f'heel.{s}']
    sw = P.get('shoe_w', 0.048)
    sh = P.get('shoe_h', 0.05)
    mid = V(A.x, A.y - 0.03, 0.045)
    pts = [Hl + V(0, 0.0, 0.01), mid, B + V(0, 0, 0.01), T + V(0, 0, 0.005)]
    rad = [(sw * 0.85, sh * 0.85), (sw, sh), (sw * 1.05, sh * 0.62), (sw * 0.8, sh * 0.48)]

    def flat_sole(off, sv, a):
        return off  # adjusted after: clamp to the floor below

    sh_ = ak.tube(pts, rad, ring=16, per=5, up=V(0, 0, 1))
    sh_['verts'] = [V(v.x, v.y, max(v.z, 0.0)) for v in sh_['verts']]
    # ankle cuff
    cuff = ak.tube([A + V(0, 0.005, -0.03), A + V(0, 0.005, 0.03)],
                   [P['leg_r'][4] * 1.15, P['leg_r'][4] * 1.12], ring=16, per=2)
    mb.add(sh_, mat, [blend({f'foot.{s}': 1}, {f'toe.{s}': 1}, ss(1.8, 2.3, x)) for x in sh_['s']])
    mb.add(cuff, mat, {f'foot.{s}': 0.6, f'shin.{s}': 0.4})


# ===================================================================== head
def sculpt_head(P, segs=112, rings=72):
    """Returns part dict with verts (world), faces, plus 'local' points and
    'dir' (unit sphere direction) per vertex for masks/colour."""
    C = V(*P['head_c'])
    rx, ry, rz = P['head_r']
    H = P['face']
    sp = ak.uv_sphere((0, 0, 0), 1.0, segs=segs, rings=rings)
    loc = []
    for d in sp['verts']:
        p = V(d.x * rx, d.y * ry, d.z * rz)
        zf = d.z
        front = ss(0.15, -0.6, d.y)
        if p.y > 0:
            p.y *= 1 + H['skull_back'] * ss(-0.3, 0.5, zf)
            p.y *= 1 - 0.32 * ss(-0.2, -0.95, zf)
        p.z += H.get('crown', 0.0) * rz * ss(0.6, 1.0, zf)
        jt = H['jaw'] + (1 - H['jaw']) * ss(-0.98, 0.0, zf)
        jt += H.get('jaw_square', 0.0) * ss(-0.5, -0.8, zf) * ss(-1.0, -0.8, zf)
        p.x *= jt
        temple = H.get('temple', 0.0) * gauss((zf - 0.3) ** 2, 0.25) * ss(0.2, -0.4, d.y)
        p.x *= 1 - temple
        if p.y < 0:
            p.y *= 1 - H['face_flat'] * ss(-0.2, -0.9, d.y) * ss(-0.9, -0.3, zf)
        cb = ss(-0.55, -1.0, zf) * front
        p.y -= H['chin_fwd'] * cb * rz
        if zf < -0.82:
            p.z = -rz * 0.82 - (-zf - 0.82) * rz * H.get('chin_flat', 0.5)
        if p.z < 0:
            p.z *= H.get('chin_len', 1.0)
        loc.append(p)

    base = [p.copy() for p in loc]
    # facial features (head-local metres)
    ex, ez = H['eye_x'], H['eye_z']
    nb, nt = H['nose_bridge_z'], H['nose_tip_z']
    for i, p in enumerate(loc):
        d = sp['verts'][i]
        front = ss(0.0, -0.55, d.y)
        if front <= 0:
            continue
        x, z = p.x, p.z
        u = (nb - z) / (nb - nt)
        if 0 <= u <= 1:
            prof = 0.22 + 0.78 * u ** 1.6
        elif u > 1:
            prof = math.exp(-((u - 1) / H.get('nose_under', 0.16)) ** 2)
        else:
            prof = 0.22 * math.exp(-(u / 0.2) ** 2)
        nw = H['nose_w'][0] + (H['nose_w'][1] - H['nose_w'][0]) * min(1, max(0, u))
        dy = H['nose_len'] * prof * gauss(x * x, nw)
        # nostril wings
        for sx in (-1, 1):
            dy += H['nose_len'] * 0.32 * gauss((x - sx * H['nose_w'][1] * 0.95) ** 2 + (z - nt - 0.004) ** 2, 0.008)
        # brow ridge
        dy += H['brow'] * gauss((z - (ez + 0.024)) ** 2, 0.014) * ss(0.075, 0.03, abs(x))
        # sockets
        for sx in (-1, 1):
            dy -= H['socket'] * gauss((x - sx * ex) ** 2 + (z - ez) ** 2, 0.017)
        # lips, chin
        mz = H['mouth_z']
        dy += H['lips'] * gauss(x * x, 0.022) * gauss((z - mz) ** 2, 0.014)
        dy += H['chin'] * gauss(x * x, 0.026) * gauss((z - (mz - 0.04)) ** 2, 0.016)
        p.y -= dy * front
        # cheekbones
        ck = H['cheek'] * gauss((abs(x) - rx * 0.62) ** 2 + (z - (ez - 0.03)) ** 2, 0.03)
        p.x += math.copysign(ck, x)
        p.y -= ck * 0.6

    verts = [C + p for p in loc]
    return dict(verts=verts, faces=sp['faces'], local=loc, dir=sp['verts'], C=C, base=base)


def soften_face_normals(ob, head, k=0.75):
    """Toon trick: bend the head's shading normals toward the featureless
    head shape so the cel bands fall in clean shapes instead of blotches.
    Assumes the head part is the first part in the object."""
    me = ob.data
    rx, ry, rz = 1, 1, 1
    nb = len(head['base'])
    # normals of the featureless shape, from a temporary mesh
    tmp = bpy.data.meshes.new('_tmp')
    tmp.from_pydata([tuple(p) for p in head['base']], [], head['faces'])
    tmp.update()
    bn = [v.normal.copy() for v in tmp.vertices]
    bpy.data.meshes.remove(tmp)
    out = []
    for i, v in enumerate(me.vertices):
        n = v.normal.copy()
        if i < nb:
            n = n.lerp(bn[i], k).normalized()
        out.append(n)
    me.normals_split_custom_set_from_vertices(out)


def face_anchors(P, head):
    """Ray-cast eye centres from the sculpted head."""
    bvh = ak.bvh_from(head)
    C = head['C']
    H = P['face']
    r = H['eye_r']
    eyes = {}
    for s, sx in (('L', 1), ('R', -1)):
        hit = ak.project_front(bvh, C.x + sx * H['eye_x'], C.z + H['eye_z'])
        eyes[s] = hit[0] + V(0, r * H.get('eye_sink', 0.55), 0)
    return bvh, eyes


def head_normal(head, i):
    """Approximate outward normal from the ellipsoid gradient."""
    rx, ry, rz = 1, 1, 1
    p = head['local'][i]
    return V(p.x / 0.008, p.y / 0.011, p.z / 0.016).normalized()


# ===================================================================== face parts
def eyeballs(mb, P, eyes, M):
    H = P['face']
    r = H['eye_r']
    for s in ('L', 'R'):
        c = eyes[s]
        look = V(0, -1, 0)
        sp = ak.uv_sphere(c, r, segs=24, rings=18, axis=look)
        fm = []
        pr, ir = H.get('pupil_rings', 2), H.get('iris_rings', 5)
        for rg in sp['ring']:
            fm.append(M['pupil'] if rg < pr else M['iris'] if rg < ir else None)
        mb.add(sp, M['sclera'], {f'eye.{s}': 1.0}, face_mats=fm)
        # catch-light, fixed to the head so it stays put when the eye turns
        g = ak.uv_sphere(c + V(-0.3 * r if s == 'L' else -0.3 * r, -r * 1.0, 0.38 * r), r * 0.2, segs=8, rings=6)
        mb.add(g, M['glint'], {'head': 1.0})


def lid_shell(c, R, e0, e1, a0=-1.85, a1=1.85, na=18, ne=8, edge_band=None):
    """Spherical lid patch between elevations e0..e1 (radians), horizontal
    angle a0..a1 around the front. Returns part + face rows."""
    verts, faces, rows = [], [], []
    es = []
    if edge_band:  # first band thin (lash line)
        es = [e0, e0 + edge_band] + [e0 + edge_band + (e1 - e0 - edge_band) * k / (ne - 1) for k in range(1, ne)]
    else:
        es = [e0 + (e1 - e0) * k / ne for k in range(ne + 1)]
    for e in es:
        for j in range(na + 1):
            a = a0 + (a1 - a0) * j / na
            verts.append(c + R * V(math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    w = na + 1
    for i in range(len(es) - 1):
        for j in range(na):
            faces.append((i * w + j, i * w + j + 1, (i + 1) * w + j + 1, (i + 1) * w + j))
            rows.append(i)
    return dict(verts=verts, faces=faces), rows


def lids(coll, arm, P, eyes, M, name):
    """Upper + lower lids as one object with shape keys: blink, wide, squint,
    blink.L/.R (wink)."""
    H = P['face']
    r = H['eye_r']
    R = r * 1.14
    up0 = math.radians(H['lid_up'])      # rest upper edge elevation
    lo0 = math.radians(H['lid_low'])     # rest lower edge elevation (negative)
    mb = ak.MeshBuilder(name)
    meta = []
    for s in ('L', 'R'):
        c = eyes[s]
        up, rows = lid_shell(c, R, up0, math.radians(105), edge_band=math.radians(H.get('lash', 7)))
        fm = [M['lash'] if rw == 0 else None for rw in rows]
        b = mb.add(up, M['lid'], {'head': 1.0}, face_mats=fm)
        meta.append((s, 'up', b, len(up['verts']), c))
        lo, rows = lid_shell(c, R * 0.995, math.radians(-100), lo0)
        fm = [M['lash_low'] if rw == len(set(rows)) - 1 else None for rw in rows]
        b = mb.add(lo, M['lid'], {'head': 1.0}, face_mats=fm)
        meta.append((s, 'lo', b, len(lo['verts']), c))
    # upper shell faces: verify outward
    ob = mb.build(coll, arm)
    me = ob.data
    ob.shape_key_add(name='Basis')

    def key(nm, up_e=None, lo_e=None, sides=('L', 'R')):
        k = ob.shape_key_add(name=nm, from_mix=False)
        k.value = 0.0
        for s, which, b, cnt, c in meta:
            if s not in sides:
                continue
            if which == 'up' and up_e is not None:
                part, _ = lid_shell(c, R, up_e, math.radians(105), edge_band=math.radians(H.get('lash', 7)))
                for i, v in enumerate(part['verts']):
                    k.data[b + i].co = v
            if which == 'lo' and lo_e is not None:
                part, _ = lid_shell(c, R * 0.995, math.radians(-100), lo_e)
                for i, v in enumerate(part['verts']):
                    k.data[b + i].co = v
    shut = lo0 + math.radians(4)
    key('blink', up_e=shut)
    key('blink.L', up_e=shut, sides=('L',))
    key('blink.R', up_e=shut, sides=('R',))
    key('wide', up_e=up0 + math.radians(16), lo_e=lo0 - math.radians(6))
    key('squint', up_e=up0 - math.radians(10), lo_e=lo0 + math.radians(12))
    key('narrow.L', up_e=up0 - math.radians(12), sides=('L',))
    key('narrow.R', up_e=up0 - math.radians(12), sides=('R',))
    return ob


def decal(coll, arm, name, bvh, grid, keys, mat_fn, M, offset=0.0015, rows=2, cols=12):
    """Surface decal projected onto the head from the front, with shape keys.
    grid(i, j) -> (x, z) in world; keys: name -> grid-like function."""
    def build_pts(fn):
        pts = []
        for i in range(rows + 1):
            for j in range(cols + 1):
                x, z = fn(i / rows, j / cols)
                hit = ak.project_front(bvh, x, z)
                if hit is None:
                    pts.append(V(x, 0, z))
                else:
                    pts.append(hit[0] + hit[1] * offset)
        return pts
    base = build_pts(grid)
    faces, fm = [], []
    w = cols + 1
    for i in range(rows):
        for j in range(cols):
            faces.append((i * w + j, (i + 1) * w + j, (i + 1) * w + j + 1, i * w + j + 1))
            fm.append(mat_fn(i, j))
    part = dict(verts=base, faces=faces)
    # make normals face the viewer (-Y)
    a, b, c = (base[faces[0][k]] for k in range(3))
    if (b - a).cross(c - a).y > 0:
        part['faces'] = [tuple(reversed(f)) for f in faces]
    mb = ak.MeshBuilder(name)
    mb.add(part, M[mat_fn(0, 0)], {'head': 1.0}, face_mats=[M[k] for k in fm])
    ob = mb.build(coll, arm)
    ob.shape_key_add(name='Basis')
    for nm, fn in keys.items():
        k = ob.shape_key_add(name=nm, from_mix=False)
        k.value = 0.0
        for i, v in enumerate(build_pts(fn)):
            k.data[i].co = v
    return ob


def brows(coll, arm, P, bvh, M, name):
    """Brow strips. Shape keys: up, up.L, up.R, angry, worried."""
    H = P['face']
    C = V(*P['head_c'])
    bz = C.z + H['eye_z'] + H['brow_z']
    bi, bo = H['brow_in'], H['brow_out']
    th = H['brow_th']
    arch = H.get('brow_arch', 0.004)

    def make(dz_in=(0, 0), dz_out=(0, 0), dz_mid=(0, 0)):
        def fn(u, v):
            # v: 0..1 along both brows (0..0.5 = R side outer->inner, 0.5..1 = L inner->outer)
            side = 1 if v >= 0.5 else -1
            t = (v - 0.5) * 2 if side > 0 else (0.5 - v) * 2      # 0 inner .. 1 outer
            t = min(1, max(0, (t - 0.04) / 0.96))
            si = 0 if side > 0 else 1
            x = C.x + side * (bi + (bo - bi) * t)
            z = bz + arch * math.sin(math.pi * min(1, t * 1.15)) - 0.003 * t
            z += dz_in[si] * (1 - t) + dz_out[si] * t + dz_mid[si] * math.sin(math.pi * t)
            h = th * (1.0 - 0.45 * t)
            return x, z + (u - 0.5) * h
        return fn
    grid = make()
    keys = {
        'up': make((0.008, 0.008), (0.006, 0.006), (0.002, 0.002)),
        'up.L': make((0.008, 0), (0.006, 0), (0.002, 0)),
        'up.R': make((0, 0.008), (0, 0.006), (0, 0.002)),
        'angry': make((-0.008, -0.008), (0.003, 0.003)),
        'worried': make((0.008, 0.008), (-0.003, -0.003)),
    }
    # gap between brows: faces in the middle use the 'skip' material -> removed below
    cols = 24
    ob = decal(coll, arm, name, bvh, grid, keys, lambda i, j: 'brow', M, offset=0.0022, rows=2, cols=cols)
    # delete the bridge faces between the two brows
    import bmesh
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if abs(f.calc_center_median().x - C.x) < bi * 0.9]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(me)
    bm.free()
    return ob


def mouth(coll, arm, P, bvh, M, name):
    """Mouth patch. Rows 0..1 are teeth, collapsed onto the upper lip unless
    the mouth opens. Keys: smile, smirk.L, smirk.R, frown, open, grin, oh."""
    H = P['face']
    C = V(*P['head_c'])
    mz = C.z + H['mouth_z'] + H.get('mouth_dz', 0.0)
    mw = H['mouth_w']
    rows, cols = 6, 16
    tr = 2  # teeth rows

    def make(w=1.0, curve=0.0, lcorner=0.0, rcorner=0.0, open_=0.0, teeth=0.35, squareness=0.0, drop=0.0):
        def fn(u, v):
            s = v * 2 - 1                         # -1 (R) .. 1 (L)
            x = C.x + s * mw * w
            corner = (lcorner if s > 0 else rcorner) * abs(s) ** 2
            line = mz + curve * (s * s - 0.35) + corner
            shape = (1 - abs(s) ** 2) if squareness == 0 else (1 - abs(s) ** (2 + 6 * squareness))
            top = line + open_ * 0.25 * shape
            bot = line - open_ * 0.75 * shape - drop * shape
            th = 0.0012
            if open_ <= 0:
                top, bot = line + th, line - th
            # rows: 0..tr teeth (top), tr..rows interior/lip
            rr = u * rows
            if rr <= tr:
                tt = rr / tr * teeth
            else:
                tt = teeth + (1 - teeth) * (rr - tr) / (rows - tr)
            if open_ <= 0:
                tt = 0 if rr <= tr else (rr - tr) / (rows - tr)
            return x, top + (bot - top) * tt
        return fn
    grid = make()
    keys = {
        'smile': make(w=1.08, curve=0.004, lcorner=0.004, rcorner=0.004),
        'smirk.L': make(lcorner=0.007, curve=0.001),
        'smirk.R': make(rcorner=0.007, curve=0.001),
        'frown': make(w=0.95, curve=-0.004, lcorner=-0.003, rcorner=-0.003),
        'open': make(w=0.92, open_=0.016, teeth=0.25),
        'grin': make(w=1.15, open_=0.012, teeth=0.45, squareness=0.6, lcorner=0.002, rcorner=0.002),
        'laugh': make(w=1.12, curve=0.004, open_=0.02, teeth=0.3, lcorner=0.005, rcorner=0.005),
        'oh': make(w=0.6, open_=0.014, teeth=0.0),
    }

    def mat(i, j):
        return 'teeth' if i < tr else 'mouth'
    return decal(coll, arm, name, bvh, grid, keys, mat, M, offset=0.0016, rows=rows, cols=cols)


def ears(mb, P, bvh, M):
    H = P['face']
    C = V(*P['head_c'])
    for sx in (1, -1):
        o = V(C.x + sx * 0.5, C.y + H.get('ear_y', 0.004), C.z + H['ear_z'])
        hit = bvh.ray_cast(o, V(-sx, 0, 0))
        loc = hit[0] if hit[0] is not None else o
        c = loc + V(sx * 0.004, 0.006, 0)
        e = H.get('ear_size', 1.0)
        rot = Matrix.Rotation(math.radians(-14 * sx), 3, 'Z') @ Matrix.Rotation(math.radians(-8), 3, 'X')
        sp = ak.uv_sphere((0, 0, 0), (0.007 * e, 0.019 * e, 0.029 * e), segs=16, rings=12)
        # cup the ear: pull the outer face in at the middle
        vs = []
        for v in sp['verts']:
            q = v.copy()
            if q.x * sx > 0:
                q.x -= sx * 0.004 * e * gauss(q.y ** 2 + (q.z / 1.5) ** 2, 0.012 * e)
            vs.append(c + rot @ q)
        mb.add(dict(verts=vs, faces=sp['faces']), M['skin'], {'head': 1.0})


# ===================================================================== hair
def scalp_hit2(bvh, C, alpha, beta):
    """Sagittal parameterisation for swept hair. beta: angle over the head
    from the front (0 = straight ahead, 90 = top, 180 = straight back);
    alpha: sideways (+ = character's left). Degrees. Returns (loc, normal)."""
    a, b = math.radians(alpha), math.radians(beta)
    d = V(math.sin(a), -math.cos(a) * math.cos(b), math.cos(a) * math.sin(b))
    hit = bvh.ray_cast(C + d * 0.6, -d)
    if hit[0] is None:
        return C + d * 0.1, d
    return hit[0], (hit[0] - C).normalized().lerp(hit[1], 0.5).normalized()


def clump2(bvh, C, path, radii, ring=8, per=5, flat=0.55, tip=None):
    """Like clump() but with (alpha, beta, lift) path points. tip: optional
    world-space offset added to the final point (lets ends lift off)."""
    pts, ups = [], []
    for k, (al, be, lift) in enumerate(path):
        loc, nrm = scalp_hit2(bvh, C, al, be)
        p = loc + nrm * lift
        if tip is not None and k == len(path) - 1:
            p = p + tip
        pts.append(p)
        ups.append(tuple(nrm))
    return ak.tube(pts, [(r, r * flat) for r in radii], ring=ring, per=per, up=ups)


def scalp_hit(bvh, C, theta, phi):
    """theta: around Z, 0 = front (-Y), +90 = character's left (+X).
    phi: from the top (0) down. Degrees. Returns (loc, normal)."""
    t, p = math.radians(theta), math.radians(phi)
    d = V(math.sin(p) * math.sin(t), -math.sin(p) * math.cos(t), math.cos(p))
    hit = bvh.ray_cast(C + d * 0.6, -d)
    if hit[0] is None:
        return C + d * 0.1, d
    return hit[0], (hit[0] - C).normalized().lerp(hit[1], 0.5).normalized()


def clump(bvh, C, path, radii, ring=8, per=5, flat=0.55, jitter=None):
    """path: [(theta, phi, lift)] on the scalp. radii: per path point
    (width). The clump is flattened against the scalp."""
    pts, ups = [], []
    for th, ph, lift in path:
        loc, nrm = scalp_hit(bvh, C, th, ph)
        p = loc + nrm * lift
        if jitter:
            p = p + jitter
        pts.append(p)
        ups.append(tuple(nrm))
    rad = [(r, r * flat) for r in radii]
    return ak.tube(pts, rad, ring=ring, per=per, up=ups)


def scalp_cap(head, mask, off):
    """Copy of head faces whose verts all pass mask(dir, local) pushed out."""
    keep = [all(mask(head['dir'][i], head['local'][i]) for i in f) for f in head['faces']]
    used = {}
    verts, faces = [], []
    C = head['C']
    for f, k in zip(head['faces'], keep):
        if not k:
            continue
        nf = []
        for i in f:
            if i not in used:
                used[i] = len(verts)
                v = head['verts'][i]
                n = (v - C).normalized()
                verts.append(v + n * off)
            nf.append(used[i])
        faces.append(tuple(nf))
    return dict(verts=verts, faces=faces)


def hairline_mask(front, side, back):
    """mask for scalp caps: phi (from the top) below a hairline that runs
    front -> side -> back, all in degrees."""
    def m(d, p):
        th = math.degrees(math.atan2(d.x, -d.y))
        ph = math.degrees(math.acos(max(-1, min(1, d.z))))
        a = abs(th)
        if a < 90:
            lim = front + (side - front) * ss(0, 90, a)
        else:
            lim = side + (back - side) * ss(90, 180, a)
        return ph < lim
    return m


# ===================================================================== poses
# Local-axis Euler degrees per bone (see README for the axis conventions).
POSES = {
    'relaxed': {
        'upper_arm.L': (6, 0, -46), 'upper_arm.R': (6, 0, 46),
        'forearm.L': (18, 0, 0), 'forearm.R': (18, 0, 0),
        **{f'{f}.0{i}.{s}': (-14, 0, 0) for f in ('index', 'middle', 'ring', 'pinky') for i in (1, 2, 3)
           for s in 'LR'},
    },
}


def pose(arm, values):
    """Set a pose dict on an armature; bones not named go back to rest."""
    if isinstance(values, str):
        values = POSES[values]
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = [math.radians(a) for a in values.get(pb.name, (0, 0, 0))]


# ===================================================================== expressions
def set_expression(parts, preset):
    """parts: dict role -> object (lids, brows, mouth). preset: {role: {key: v}}.
    Keys not named are reset to 0."""
    for role, ob in parts.items():
        if ob is None or ob.data.shape_keys is None:
            continue
        vals = preset.get(role, {})
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = vals.get(kb.name, 0.0)


def key_expression(parts, preset, frame):
    set_expression(parts, preset)
    for ob in parts.values():
        if ob is None or ob.data.shape_keys is None:
            continue
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.keyframe_insert('value', frame=frame)
