"""Ancient stonework: worn ashlar walls, broken floor slabs, rubble, column
drums, cobwebs and hanging roots.

Blocks are chamfered boxes: the bevelled edges catch a light band, which at
pixel scale reads as hand-placed highlights. Everything is built into a
MeshBuilder so a whole wall is one object.
"""
import math
from mathutils import Vector, Matrix
import akcore as ak

V = lambda *a: Vector(a)


# ------------------------------------------------------------------ chamfered box
def _template():
    """Topology of a chamfered box: 3 verts per corner (one per face it
    touches), 6 face quads, 12 edge quads, 8 corner triangles."""
    corners = [(sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    cidx = {c: i for i, c in enumerate(corners)}

    def vi(c, k):
        return cidx[c] * 3 + k
    faces = []
    for k in range(3):
        j, l = [a for a in range(3) if a != k]
        for s in (-1, 1):
            q = []
            for sj, sl in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                c = [0, 0, 0]
                c[k], c[j], c[l] = s, sj, sl
                q.append(vi(tuple(c), k))
            faces.append(tuple(q))
    for k in range(3):
        j, l = [a for a in range(3) if a != k]
        for sj in (-1, 1):
            for sl in (-1, 1):
                lo = [0, 0, 0]
                hi = [0, 0, 0]
                lo[k], lo[j], lo[l] = -1, sj, sl
                hi[k], hi[j], hi[l] = 1, sj, sl
                faces.append((vi(tuple(lo), j), vi(tuple(lo), l), vi(tuple(hi), l), vi(tuple(hi), j)))
    for c in corners:
        faces.append((vi(c, 0), vi(c, 1), vi(c, 2)))
    unit = _verts((0, 0, 0), (1, 1, 1), 0.2, None, corners)
    part = ak.fix_normals(dict(verts=unit, faces=faces))
    return corners, part['faces']


def _verts(c, s, ch, rot, corners):
    c = Vector(c)
    h = [s[0] / 2, s[1] / 2, s[2] / 2]
    out = []
    for cs in corners:
        for k in range(3):
            p = [cs[a] * h[a] for a in range(3)]
            for a in range(3):
                if a != k:
                    p[a] -= cs[a] * ch
            v = Vector(p)
            out.append(c + (rot @ v if rot is not None else v))
    return out


_CORNERS, _FACES = None, None


def chamfer_box(c, s, ch=0.03, rot=None):
    global _CORNERS, _FACES
    if _FACES is None:
        _CORNERS, _FACES = _template()
    ch = min(ch, min(s) * 0.45)
    return dict(verts=_verts(c, s, ch, rot, _CORNERS), faces=_FACES)


def wall_frame(U, N):
    return Matrix((Vector(U).normalized(), Vector(N).normalized(), V(0, 0, 1))).transposed()


# ------------------------------------------------------------------ walls
def ashlar_wall(mb, O, U, N, length, height, mats, mortar, rnd, hole=None, rows=(0.34, 0.42, 0.5, 0.58),
                lengths=(0.55, 1.35), depth=0.22, gap=0.045, proud=0.04, missing=0.03, chipped=0.08,
                cracked=0.07, stain=None):
    """Irregular coursed stone. Each course has its own height; blocks vary in
    length, sit a little proud or sunk, lean a degree or two, and some are
    chipped (smaller), cracked (split in two) or missing (dark hole).
    hole(u, v) -> True where the wall must stay open."""
    U, N = Vector(U).normalized(), Vector(N).normalized()
    Z = V(0, 0, 1)
    base_rot = wall_frame(U, N)
    v = 0.0
    while v < height - 0.05:
        bh = min(rnd.choice(rows), height - v)
        u = -rnd.uniform(0, lengths[0])
        while u < length:
            bl = rnd.uniform(*lengths)
            u0, u1 = max(u, 0), min(u + bl, length)
            u += bl
            if u1 - u0 < 0.12:
                continue
            uc, vc = (u0 + u1) / 2, v + bh / 2
            if hole and (hole(uc, vc) or hole(u0 + 0.06, vc) or hole(u1 - 0.06, vc)
                         or hole(uc, v + 0.05) or hole(uc, v + bh - 0.05)):
                continue
            r = rnd.random()
            if r < missing:
                continue
            pieces = [(u0, u1)]
            if r < missing + cracked and u1 - u0 > 0.5:
                cut = rnd.uniform(u0 + 0.2, u1 - 0.2)
                pieces = [(u0, cut - 0.015), (cut + 0.015, u1)]
            for a, b in pieces:
                w, hh, dd = b - a - gap, bh - gap, depth
                sink = rnd.uniform(-0.015, 0.03)
                if missing + cracked <= r < missing + cracked + chipped:
                    w *= rnd.uniform(0.7, 0.9)
                    hh *= rnd.uniform(0.75, 0.92)
                    sink -= 0.03
                tilt = Matrix.Rotation(math.radians(rnd.uniform(-1.6, 1.6)), 3, N) @ \
                    Matrix.Rotation(math.radians(rnd.uniform(-1.2, 1.2)), 3, U)
                c = O + U * ((a + b) / 2) + Z * vc + N * (proud - dd / 2 + sink)
                mat = mats[rnd.randrange(len(mats))]
                if stain and rnd.random() < 0.12:
                    mat = stain
                mb.add(chamfer_box(c, (w, dd, hh), ch=rnd.uniform(0.02, 0.05), rot=tilt @ base_rot), mat)
        v += bh
    # dark bed behind the stones, leaving holes open
    cell = 0.25
    verts, faces = [], []
    for i in range(int(length / cell + 0.999)):
        for k in range(int(height / cell + 0.999)):
            a0, b0 = i * cell, k * cell
            a1, b1 = min(a0 + cell, length), min(b0 + cell, height)
            if hole and hole((a0 + a1) / 2, (b0 + b1) / 2):
                continue
            n = len(verts)
            verts += [O + U * a0 + Z * b0, O + U * a1 + Z * b0, O + U * a1 + Z * b1, O + U * a0 + Z * b1]
            faces.append((n, n + 1, n + 2, n + 3))
    if faces:
        a, b, c = verts[0], verts[1], verts[2]
        if (b - a).cross(c - a).dot(N) < 0:
            faces = [tuple(reversed(f)) for f in faces]
        mb.add(dict(verts=verts, faces=faces), mortar)


def slab_floor(mb, x0, x1, y0, y1, mats, grout, rnd, size=(0.8, 1.6), z=0.0, broken=0.1, missing=0.04,
               keep_clear=None, rubble_mat=None):
    """Big irregular floor slabs, slightly tilted; some cracked, a few gone
    (with rubble in the hole)."""
    y = y0
    while y < y1 - 0.05:
        sh = min(rnd.uniform(*size), y1 - y)
        x = x0 - rnd.uniform(0, size[0])
        while x < x1:
            sw = rnd.uniform(*size)
            a, b = max(x, x0), min(x + sw, x1)
            x += sw
            if b - a < 0.15:
                continue
            cx, cy = (a + b) / 2, y + sh / 2
            r = rnd.random()
            clear = keep_clear and keep_clear(cx, cy)
            if r < missing and not clear:
                if rubble_mat is not None:
                    rubble(mb, V(cx, cy, z - 0.02), min(b - a, sh) * 0.35, 6, rubble_mat, rnd, scale=0.7)
                continue
            pieces = [(a, b, y, y + sh)]
            if r < missing + broken and b - a > 0.6:
                cut = rnd.uniform(a + 0.25, b - 0.25)
                pieces = [(a, cut - 0.02, y, y + sh), (cut + 0.02, b, y, y + sh)]
            for pa, pb, qa, qb in pieces:
                hgt = 0.08
                tilt = Matrix.Rotation(math.radians(rnd.uniform(-1.4, 1.4)), 3, 'X') @ \
                    Matrix.Rotation(math.radians(rnd.uniform(-1.4, 1.4)), 3, 'Y')
                c = V((pa + pb) / 2, (qa + qb) / 2, z - hgt / 2 + rnd.uniform(-0.012, 0.012))
                mb.add(chamfer_box(c, (pb - pa - 0.05, qb - qa - 0.05, hgt), ch=0.025, rot=tilt),
                       mats[rnd.randrange(len(mats))])
        y += sh
    mb.add(dict(verts=[V(x0, y0, z - 0.06), V(x1, y0, z - 0.06), V(x1, y1, z - 0.06), V(x0, y1, z - 0.06)],
                faces=[(0, 1, 2, 3)]), grout)


def rubble(mb, centre, radius, count, mat, rnd, scale=1.0):
    c = Vector(centre)
    for _ in range(count):
        a = rnd.uniform(0, math.tau)
        d = radius * math.sqrt(rnd.random())
        s = rnd.uniform(0.05, 0.2) * scale
        rot = Matrix.Rotation(rnd.uniform(0, math.tau), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-0.6, 0.6), 3, 'X')
        dims = (s * rnd.uniform(0.7, 1.4), s * rnd.uniform(0.7, 1.3), s * rnd.uniform(0.5, 0.9))
        mb.add(chamfer_box(c + V(math.cos(a) * d, math.sin(a) * d, dims[2] * 0.4), dims, ch=s * 0.2, rot=rot), mat)


def column(mb, base, height, r, stone, cap, rnd, drums=6, broken_at=None):
    """Stacked drums with slight misalignment, square base and capital.
    broken_at: number of drums left standing (the top one tilted)."""
    base = Vector(base)
    mb.add(chamfer_box(base + V(0, 0, 0.17), (r * 2.8, r * 2.8, 0.34), ch=0.05), cap)
    shaft = height - 0.68
    dh = shaft / drums
    n = drums if broken_at is None else broken_at
    for i in range(n):
        z0 = 0.34 + i * dh
        off = V(rnd.uniform(-0.012, 0.012), rnd.uniform(-0.012, 0.012), 0)
        top = z0 + dh - 0.025
        if broken_at is not None and i == n - 1:
            # jagged break: shorter, tilted drum
            top = z0 + dh * rnd.uniform(0.35, 0.6)
            off += V(0.03, -0.02, 0)
        t = ak.tube([base + off + V(0, 0, z0), base + off + V(0, 0, top)], r * rnd.uniform(0.97, 1.0), ring=24,
                    per=1)
        mb.add(t, stone)
    if broken_at is None:
        mb.add(chamfer_box(base + V(0, 0, height - 0.17), (r * 2.9, r * 2.9, 0.34), ch=0.05), cap)
        mb.add(chamfer_box(base + V(0, 0, height - 0.4), (r * 2.4, r * 2.4, 0.12), ch=0.03), cap)


def fallen_drum(mb, centre, r, length, yaw, mat):
    c = Vector(centre)
    d = Matrix.Rotation(yaw, 3, 'Z') @ V(1, 0, 0)
    mb.add(ak.tube([c - d * length / 2 + V(0, 0, r), c + d * length / 2 + V(0, 0, r)], r, ring=24, per=1), mat)


def cobweb(mb, apex, a, b, size, mat, rnd, spokes=6, rings=4, thick=0.0045):
    """Corner web: spokes fanning from the apex between directions a and b,
    joined by sagging rings."""
    apex, a, b = Vector(apex), Vector(a).normalized(), Vector(b).normalized()
    sag = V(0, 0, -1)
    ends = []
    for i in range(spokes):
        t = i / (spokes - 1)
        d = a.slerp(b, t) if hasattr(a, 'slerp') else (a.lerp(b, t)).normalized()
        L = size * rnd.uniform(0.75, 1.0)
        ends.append((d, L))
        mb.add(ak.tube([apex, apex + d * L], thick, ring=4, per=1, caps=(False, False)), mat)
    for k in range(1, rings + 1):
        f = k / (rings + 1)
        pts = []
        for i, (d, L) in enumerate(ends):
            pts.append(apex + d * L * f)
        dense = []
        for p, q in zip(pts, pts[1:]):
            for s in range(4):
                u = s / 4
                dense.append(p.lerp(q, u) + sag * (math.sin(math.pi * u) * size * 0.06 * f))
        dense.append(pts[-1])
        mb.add(ak.tube(dense, thick * 0.8, ring=4, per=1, caps=(False, False)), mat)


def root(mb, top, length, mat, rnd, r0=0.035):
    """A root hanging from a ceiling crack: wavy, tapering, maybe forked."""
    top = Vector(top)
    pts, p = [top], top.copy()
    ph = rnd.uniform(0, math.tau)
    n = 6
    for i in range(1, n + 1):
        p = p + V(math.sin(ph + i * 1.3) * 0.06, math.cos(ph + i * 0.9) * 0.05, -length / n)
        pts.append(p.copy())
    rad = [r0 * (1 - i / (n + 1)) + 0.003 for i in range(n + 1)]
    mb.add(ak.tube(pts, rad, ring=6, per=3), mat)
    if length > 0.8:
        k = rnd.randrange(2, 4)
        q = pts[k]
        branch = [q, q + V(0.12, 0.05, -0.25), q + V(0.18, 0.12, -0.5)]
        mb.add(ak.tube(branch, [rad[k] * 0.6, rad[k] * 0.35, 0.003], ring=5, per=3), mat)
