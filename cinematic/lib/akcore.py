"""Shared helpers for the Anatomy Kong cinematic.

Toon materials, ink outlines (inverted hull), mesh building (tubes, lofts,
a multi-part MeshBuilder with vertex-group weights), procedural textures and
scene/render setup. Everything is plain bpy so scripts run with
`blender --background --python ...`.
"""
import bpy
import math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

INK = '#1b1024'
# Shadow tints lean purple, like the concept sheet.
SHADOW_MUL = (0.50, 0.44, 0.66)
MID_MUL = (0.80, 0.76, 0.88)


# ---------------------------------------------------------------- colour
def lin(c):
    """'#rrggbb' (sRGB) -> linear RGBA tuple. Tuples pass through."""
    if not isinstance(c, str):
        return tuple(c) + ((1.0,) if len(c) == 3 else ())
    c = c.lstrip('#')
    rgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    rgb = [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in rgb]
    return (*rgb, 1.0)


def _use_nodes(m):
    try:
        m.use_nodes = True
    except Exception:
        pass


# ---------------------------------------------------------------- materials
def toon(name, base, image=None, attr=None, steps=(0.16, 0.42), shadow=SHADOW_MUL,
         mid=MID_MUL, rim=0.0, cull=False, hl=None, hl_rough=0.32, hl_cut=0.55):
    """Three-band cel material: lit colour stepped by a constant ramp.

    base   colour (hex) used when no image/attribute is given
    image  bpy image to use as the base colour (UV mapped)
    attr   colour attribute name multiplied into the base (e.g. stubble)
    rim    strength of a pale fresnel rim (0 = off)
    """
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    _use_nodes(m)
    m.use_backface_culling = cull
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    dif = N.new('ShaderNodeBsdfDiffuse')
    dif.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = N.new('ShaderNodeShaderToRGB')
    ramp = N.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*shadow, 1)
    cr.elements[1].position = steps[0]
    cr.elements[1].color = (*mid, 1)
    cr.elements.new(steps[1]).color = (1, 1, 1, 1)
    L.new(dif.outputs[0], s2r.inputs[0])
    L.new(s2r.outputs['Color'], ramp.inputs['Fac'])

    # base colour source
    if image is not None:
        tex = N.new('ShaderNodeTexImage')
        tex.image = image
        tex.interpolation = 'Closest' if image.size[0] <= 64 else 'Linear'
        base_out = tex.outputs['Color']
    else:
        rgb = N.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = lin(base)
        base_out = rgb.outputs[0]
    if attr:
        at = N.new('ShaderNodeAttribute')
        at.attribute_name = attr
        mixa = N.new('ShaderNodeMix')
        mixa.data_type = 'RGBA'
        mixa.blend_type = 'MULTIPLY'
        mixa.inputs[0].default_value = 1.0
        L.new(base_out, mixa.inputs[6])
        L.new(at.outputs['Color'], mixa.inputs[7])
        base_out = mixa.outputs[2]

    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1.0
    L.new(base_out, mix.inputs[6])
    L.new(ramp.outputs['Color'], mix.inputs[7])
    col = mix.outputs[2]

    if rim > 0:
        fr = N.new('ShaderNodeLayerWeight')
        fr.inputs['Blend'].default_value = 0.25
        rr = N.new('ShaderNodeValToRGB')
        rr.color_ramp.interpolation = 'CONSTANT'
        rr.color_ramp.elements[0].color = (0, 0, 0, 1)
        rr.color_ramp.elements[1].position = 0.72
        rr.color_ramp.elements[1].color = (rim, rim, rim * 1.1, 1)
        L.new(fr.outputs['Facing'], rr.inputs['Fac'])
        add = N.new('ShaderNodeMix')
        add.data_type = 'RGBA'
        add.blend_type = 'ADD'
        add.inputs[0].default_value = 1.0
        L.new(col, add.inputs[6])
        L.new(rr.outputs['Color'], add.inputs[7])
        col = add.outputs[2]

    if hl:
        # hard specular band: glossy -> threshold -> flat highlight colour
        for idn in ('ShaderNodeBsdfGlossy', 'ShaderNodeBsdfAnisotropic'):
            try:
                gl = N.new(idn)
                break
            except RuntimeError:
                continue
        gl.inputs['Color'].default_value = (1, 1, 1, 1)
        gl.inputs['Roughness'].default_value = hl_rough
        g2r = N.new('ShaderNodeShaderToRGB')
        L.new(gl.outputs[0], g2r.inputs[0])
        hr = N.new('ShaderNodeValToRGB')
        hr.color_ramp.interpolation = 'CONSTANT'
        hr.color_ramp.elements[0].color = (0, 0, 0, 1)
        hr.color_ramp.elements[1].position = hl_cut
        hr.color_ramp.elements[1].color = (1, 1, 1, 1)
        L.new(g2r.outputs['Color'], hr.inputs['Fac'])
        mx = N.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        L.new(hr.outputs['Color'], mx.inputs[0])
        L.new(col, mx.inputs[6])
        mx.inputs[7].default_value = lin(hl)
        col = mx.outputs[2]

    emi = N.new('ShaderNodeEmission')
    L.new(col, emi.inputs['Color'])
    L.new(emi.outputs[0], out.inputs['Surface'])
    return m


def flat(name, color, strength=1.0, cull=False):
    """Unlit colour (ink, glints, glowing things)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    _use_nodes(m)
    m.use_backface_culling = cull
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emi = nt.nodes.new('ShaderNodeEmission')
    emi.inputs['Color'].default_value = lin(color)
    emi.inputs['Strength'].default_value = strength
    nt.links.new(emi.outputs[0], out.inputs['Surface'])
    return m


def ink():
    m = flat('Ink', INK, cull=True)
    # the hull should not shade the body it surrounds
    for attr in ('use_backface_culling_shadow', 'use_shadow', 'visible_shadow'):
        if hasattr(m, attr):
            try:
                setattr(m, attr, attr == 'use_backface_culling_shadow')
            except Exception:
                pass
    return m


def add_outline(ob, thickness):
    """Inverted-hull ink line: a flipped, back-face-culled shell."""
    me = ob.data
    m = ink()
    if m.name not in me.materials:
        me.materials.append(m)
    idx = list(me.materials).index(m)
    mod = ob.modifiers.new('Ink', 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_even_offset = False
    mod.material_offset = idx
    mod.material_offset_rim = idx
    return mod


# ---------------------------------------------------------------- textures
def image_from_array(name, arr):
    """arr: HxWx4 float array, row 0 = top. Packed so it saves in the .blend."""
    h, w = arr.shape[:2]
    img = bpy.data.images.get(name)
    if img and tuple(img.size) == (w, h):
        # reuse: materials built earlier still point at this image
        img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).astype(np.float32).ravel())
        img.pack()
        return img
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).astype(np.float32).ravel())
    img.pack()
    return img


def srgb_arr(hexstr):
    return np.array(lin(hexstr), dtype=np.float32)


# ---------------------------------------------------------------- mesh building
def smoothstep(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def catmull(points, per):
    """Sample a Catmull-Rom spline through points. Returns [(pos, s)] where s
    runs 0..len(points)-1 (integer s = an input point)."""
    P = [Vector(p) for p in points]
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            pos = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                         + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((pos, i + t))
    out.append((P[-1].copy(), float(len(P) - 1)))
    return out


def _interp(vals, s):
    i = min(int(s), len(vals) - 2)
    t = s - i
    a, b = vals[i], vals[i + 1]
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


def tube(points, radii, ring=16, per=6, up=None, caps=(True, True), cap_rings=4,
         squash=None, open_angle=0.0):
    """Tube through points with elliptical cross-sections.

    radii: per point, float or (rx, ry); rx is across `side`, ry along `up`.
    up:    reference up vector (Vector or per-point list) that fixes the
           ellipse orientation; parallel transport when None.
    Returns dict(verts, faces, s) with s = spline parameter per vertex.
    """
    samples = catmull(points, per)
    pos = [p for p, _ in samples]
    ss = [s for _, s in samples]
    n = len(pos)
    tans = []
    for i in range(n):
        a = pos[max(i - 1, 0)]
        b = pos[min(i + 1, n - 1)]
        tans.append((b - a).normalized())
    # frames
    frames = []
    if up is None:
        t0 = tans[0]
        ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((0, 1, 0))
        nrm = (ref - t0 * ref.dot(t0)).normalized()
        for i in range(n):
            t = tans[i]
            nrm = (nrm - t * nrm.dot(t)).normalized()
            frames.append((t.cross(nrm).normalized(), nrm))
    else:
        for i in range(n):
            t = tans[i]
            u = Vector(_interp(up, ss[i])) if isinstance(up, list) else Vector(up)
            u = (u - t * u.dot(t))
            if u.length < 1e-6:
                u = Vector((0, 0, 1)) - t * t.z
            u.normalize()
            frames.append((t.cross(u).normalized(), u))

    def rad(s):
        r = _interp(radii, s) if isinstance(radii, list) else radii
        return (r, r) if not isinstance(r, tuple) else r

    verts, vs = [], []
    a0 = open_angle
    for i in range(n):
        side, u = frames[i]
        rx, ry = rad(ss[i])
        for k in range(ring):
            a = a0 + (2 * math.pi - 2 * a0) * k / (ring if a0 == 0 else ring - 1)
            off = side * (math.sin(a) * rx) + u * (math.cos(a) * ry)
            if squash:
                off = squash(off, ss[i], a)
            verts.append(pos[i] + off)
            vs.append(ss[i])
    closed = a0 == 0
    faces = []
    for i in range(n - 1):
        for k in range(ring if closed else ring - 1):
            k2 = (k + 1) % ring
            faces.append((i * ring + k, i * ring + k2, (i + 1) * ring + k2, (i + 1) * ring + k))

    def cap(end):
        i = 0 if end == 0 else n - 1
        t = tans[i] * (-1 if end == 0 else 1)
        side, u = frames[i]
        rx, ry = rad(ss[i])
        base = i * ring
        prev = list(range(base, base + ring))
        for c in range(1, cap_rings):
            ang = (c / cap_rings) * math.pi / 2
            sc, ex = math.cos(ang), math.sin(ang)
            cur = []
            for k in range(ring):
                v = verts[base + k]
                off = v - pos[i]
                verts.append(pos[i] + off * sc + t * (ex * min(rx, ry)))
                vs.append(ss[i])
                cur.append(len(verts) - 1)
            for k in range(ring):
                k2 = (k + 1) % ring
                if end == 0:
                    faces.append((cur[k], cur[k2], prev[k2], prev[k]))
                else:
                    faces.append((prev[k], prev[k2], cur[k2], cur[k]))
            prev = cur
        verts.append(pos[i] + t * min(rx, ry))
        vs.append(ss[i])
        pole = len(verts) - 1
        for k in range(ring):
            k2 = (k + 1) % ring
            faces.append((prev[k2], prev[k], pole) if end == 0 else (prev[k], prev[k2], pole))

    if closed:
        if caps[0]:
            cap(0)
        if caps[1]:
            cap(1)
    return dict(verts=verts, faces=faces, s=vs)


def loft(rings, closed=True, cap_start=False, cap_end=False):
    """Skin a list of equal-length point rings."""
    m = len(rings[0])
    verts = [Vector(p) for r in rings for p in r]
    faces = []
    for i in range(len(rings) - 1):
        for k in range(m if closed else m - 1):
            k2 = (k + 1) % m
            faces.append((i * m + k, i * m + k2, (i + 1) * m + k2, (i + 1) * m + k))
    for flag, i, rev in ((cap_start, 0, True), (cap_end, len(rings) - 1, False)):
        if flag:
            c = sum((Vector(p) for p in rings[i]), Vector()) / m
            verts.append(c)
            ci = len(verts) - 1
            for k in range(m):
                k2 = (k + 1) % m
                a, b = i * m + k, i * m + k2
                faces.append((b, a, ci) if rev else (a, b, ci))
    return dict(verts=verts, faces=faces)


def uv_sphere(center, radii, segs=32, rings=16, axis=None):
    """Sphere with poles on `axis` (default Z). Returns dict(verts, faces,
    ring=ring index per face counted from the +axis pole)."""
    c = Vector(center)
    rx, ry, rz = radii if isinstance(radii, tuple) else (radii,) * 3
    rot = Matrix.Identity(3)
    if axis is not None:
        rot = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix()
    verts = [c + rot @ Vector((0, 0, rz))]
    for i in range(1, rings):
        th = math.pi * i / rings
        for j in range(segs):
            ph = 2 * math.pi * j / segs
            verts.append(c + rot @ Vector((rx * math.sin(th) * math.cos(ph),
                                           ry * math.sin(th) * math.sin(ph), rz * math.cos(th))))
    verts.append(c + rot @ Vector((0, 0, -rz)))
    faces, fring = [], []
    for j in range(segs):
        faces.append((0, 1 + j, 1 + (j + 1) % segs))
        fring.append(0)
    for i in range(rings - 2):
        for j in range(segs):
            a = 1 + i * segs + j
            b = 1 + i * segs + (j + 1) % segs
            faces.append((a, a + segs, b + segs, b))
            fring.append(i + 1)
    last = len(verts) - 1
    base = 1 + (rings - 2) * segs
    for j in range(segs):
        faces.append((base + j, last, base + (j + 1) % segs))
        fring.append(rings - 1)
    return dict(verts=verts, faces=faces, ring=fring)


def rounded_box(center, size, r=0.2, segs=3, rot=None):
    """Superellipsoid-ish box: a cube mapped toward a rounded shape."""
    c = Vector(center)
    sx, sy, sz = [s / 2 for s in size]
    n = 6 + segs * 2
    verts, idx = [], {}
    faces = []
    # build a subdivided cube surface, then round it
    def key(i, j, k):
        return (i, j, k)
    grid = range(n + 1)
    for i in grid:
        for j in grid:
            for k in grid:
                if i in (0, n) or j in (0, n) or k in (0, n):
                    idx[(i, j, k)] = len(verts)
                    p = Vector((i / n * 2 - 1, j / n * 2 - 1, k / n * 2 - 1))
                    # round: blend cube point toward sphere near edges
                    q = Vector((p.x * math.sqrt(max(0, 1 - p.y ** 2 / 2 - p.z ** 2 / 2 + p.y ** 2 * p.z ** 2 / 3)),
                                p.y * math.sqrt(max(0, 1 - p.z ** 2 / 2 - p.x ** 2 / 2 + p.z ** 2 * p.x ** 2 / 3)),
                                p.z * math.sqrt(max(0, 1 - p.x ** 2 / 2 - p.y ** 2 / 2 + p.x ** 2 * p.y ** 2 / 3))))
                    p = p.lerp(q, r)
                    v = Vector((p.x * sx, p.y * sy, p.z * sz))
                    if rot is not None:
                        v = rot @ v
                    verts.append(c + v)
    for a in range(n):
        for b in range(n):
            for fixed, val, rev in ((0, 0, True), (0, n, False), (1, 0, False), (1, n, True), (2, 0, True), (2, n, False)):
                if fixed == 0:
                    q = [(val, a, b), (val, a + 1, b), (val, a + 1, b + 1), (val, a, b + 1)]
                elif fixed == 1:
                    q = [(a, val, b), (a + 1, val, b), (a + 1, val, b + 1), (a, val, b + 1)]
                else:
                    q = [(a, b, val), (a + 1, b, val), (a + 1, b + 1, val), (a, b + 1, val)]
                f = [idx[x] for x in q]
                faces.append(tuple(reversed(f)) if rev else tuple(f))
    return dict(verts=verts, faces=faces)


class MeshBuilder:
    """Accumulates parts (verts, faces, material, per-vertex bone weights)
    and emits one object with materials and vertex groups."""

    def __init__(self, name):
        self.name = name
        self.verts, self.faces, self.fmat = [], [], []
        self.mats = []
        self.weights = []  # per vertex: dict bone -> w
        self.uvs = None
        self.colors = None

    def mat_index(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def add(self, part, mat, weights=None, face_mats=None, colors=None):
        """weights: dict (rigid), list of dicts per vertex, or callable(v, i)."""
        base = len(self.verts)
        vs = part['verts']
        self.verts.extend(Vector(v) for v in vs)
        mi = self.mat_index(mat)
        for fi, f in enumerate(part['faces']):
            self.faces.append(tuple(base + i for i in f))
            self.fmat.append(self.mat_index(face_mats[fi]) if face_mats and face_mats[fi] is not None else mi)
        for i, v in enumerate(vs):
            if weights is None:
                self.weights.append({})
            elif isinstance(weights, dict):
                self.weights.append(weights)
            elif callable(weights):
                self.weights.append(weights(Vector(v), i))
            else:
                self.weights.append(weights[i])
        if colors is not None or self.colors is not None:
            if self.colors is None:
                self.colors = [(1, 1, 1, 1)] * base
            self.colors.extend(colors if colors is not None else [(1, 1, 1, 1)] * len(vs))
        return base

    def build(self, coll, armature=None, smooth=True):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata([tuple(v) for v in self.verts], [], self.faces)
        me.update()
        for m in self.mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.fmat)
        if smooth:
            me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
        if self.colors is not None:
            ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
            ca.data.foreach_set('color', [c for col in self.colors for c in col])
        ob = bpy.data.objects.new(self.name, me)
        coll.objects.link(ob)
        groups = {}
        for i, w in enumerate(self.weights):
            for b, val in w.items():
                if val <= 1e-4:
                    continue
                if b not in groups:
                    groups[b] = ob.vertex_groups.new(name=b)
                groups[b].add([i], val, 'REPLACE')
        if armature is not None:
            ob.parent = armature
            mod = ob.modifiers.new('Armature', 'ARMATURE')
            mod.object = armature
        return ob


def fix_normals(part):
    """Make a closed part's faces point outward (in place)."""
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(v)) for v in part['verts']]
    bm.verts.ensure_lookup_table()
    fs = []
    for f in part['faces']:
        try:
            fs.append(bm.faces.new([vs[i] for i in f]))
        except ValueError:
            fs.append(None)
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in fs if f])
    part['faces'] = [tuple(v.index for v in f.verts) if f else orig
                     for f, orig in zip(fs, part['faces'])]
    bm.free()
    return part


def loop_tube(points, r, ring=6):
    """Closed tube along a closed loop of points (glasses rims, belts)."""
    P = [Vector(p) for p in points]
    n = len(P)
    verts, faces = [], []
    for i in range(n):
        t = (P[(i + 1) % n] - P[i - 1]).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = (ref - t * ref.dot(t)).normalized()
        s = t.cross(u)
        rx, ry = r if isinstance(r, tuple) else (r, r)
        for k in range(ring):
            a = 2 * math.pi * k / ring
            verts.append(P[i] + s * (math.sin(a) * rx) + u * (math.cos(a) * ry))
    for i in range(n):
        for k in range(ring):
            i2, k2 = (i + 1) % n, (k + 1) % ring
            faces.append((i * ring + k, i * ring + k2, i2 * ring + k2, i2 * ring + k))
    return dict(verts=verts, faces=faces)


def merge_parts(*parts):
    verts, faces = [], []
    for p in parts:
        b = len(verts)
        verts.extend(p['verts'])
        faces.extend(tuple(i + b for i in f) for f in p['faces'])
    return dict(verts=verts, faces=faces)


def no_cast(*obs):
    """Stop small face parts casting blotchy self-shadow on the face."""
    for ob in obs:
        ob.visible_shadow = False


def bvh_from(part):
    return BVHTree.FromPolygons([tuple(v) for v in part['verts']], part['faces'])


def project_front(bvh, x, z, y0=-2.0):
    """Ray from the front (-Y) toward +Y. Returns (location, normal) or None."""
    hit = bvh.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)))
    if hit[0] is None:
        # missed the edge of the surface: snap to the nearest point instead
        near = bvh.find_nearest(Vector((x, -0.05, z)))
        if near[0] is None:
            return None
        return near[0], near[1]
    return hit[0], hit[1]


# ---------------------------------------------------------------- scene / render
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def setup_render(w=1920, h=1080, samples=32, film_transparent=False):
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = film_transparent
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    try:
        sc.eevee.taa_render_samples = samples
    except AttributeError:
        pass
    sc.render.image_settings.file_format = 'PNG'
    return sc


def world(color='#1a1424', strength=1.0):
    sc = bpy.context.scene
    wd = sc.world or bpy.data.worlds.new('World')
    sc.world = wd
    _use_nodes(wd)
    bg = wd.node_tree.nodes.get('Background')
    if bg is None:
        wd.node_tree.nodes.clear()
        out = wd.node_tree.nodes.new('ShaderNodeOutputWorld')
        bg = wd.node_tree.nodes.new('ShaderNodeBackground')
        wd.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs['Color'].default_value = lin(color)
    bg.inputs['Strength'].default_value = strength
    return wd


def sun(name, rot_deg, energy=3.0, color='#ffffff', angle=2.0):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = energy
    ld.color = lin(color)[:3]
    ld.angle = math.radians(angle)
    ob = bpy.data.objects.new(name, ld)
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera(name, loc, target, lens=50, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
