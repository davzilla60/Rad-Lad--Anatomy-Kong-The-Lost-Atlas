"""Pixel-art light effects: banded translucent beams, glow sprites and dust.

Real volumetrics are noisy at one render sample and smooth where pixel art
wants hard bands, so light is drawn the way a pixel artist would: additive
shapes whose brightness steps through two or three flat bands. All of them
are tagged px_skip_id so they never produce outlines.
"""
import math
import bpy
from mathutils import Vector
import akcore as ak


def _blended(m):
    for attr, val in (('surface_render_method', 'BLENDED'), ('blend_method', 'BLEND')):
        if hasattr(m, attr):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    m.use_backface_culling = False


def _additive(nt, col_socket_or_value, strength_socket):
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    emi = N.new('ShaderNodeEmission')
    if isinstance(col_socket_or_value, tuple):
        emi.inputs['Color'].default_value = col_socket_or_value
    else:
        L.new(col_socket_or_value, emi.inputs['Color'])
    L.new(strength_socket, emi.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent')
    add = N.new('ShaderNodeAddShader')
    L.new(emi.outputs[0], add.inputs[0])
    L.new(tr.outputs[0], add.inputs[1])
    L.new(add.outputs[0], out.inputs['Surface'])


def _bands(nt, fac_socket, levels):
    """Constant ramp: levels = [(position, value)] ascending."""
    r = nt.nodes.new('ShaderNodeValToRGB')
    cr = r.color_ramp
    cr.interpolation = 'CONSTANT'
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0, 0, 0, 1)
    first = True
    for pos, v in levels:
        e = cr.elements[1] if first else cr.elements.new(pos)
        e.position = pos
        e.color = (v, v, v, 1)
        first = False
    nt.links.new(fac_socket, r.inputs['Fac'])
    return r.outputs['Color']


def beam_mat(name, color, levels=((0.18, 0.10), (0.45, 0.2), (0.75, 0.32)), axis='Z', invert=False,
             edge=True):
    """Shaft brightness from the object's generated coordinate along axis,
    times a soft edge falloff, then stepped into bands."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    ak._use_nodes(m)
    _blended(m)
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs[0])
    g = sep.outputs[axis]
    if invert:
        inv = N.new('ShaderNodeMath')
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        L.new(g, inv.inputs[1])
        g = inv.outputs[0]
    fac = g
    if edge:
        lw = N.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.5
        e = N.new('ShaderNodeMath')
        e.operation = 'SUBTRACT'
        e.inputs[0].default_value = 1.0
        L.new(lw.outputs['Facing'], e.inputs[1])
        mul = N.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        L.new(g, mul.inputs[0])
        L.new(e.outputs[0], mul.inputs[1])
        fac = mul.outputs[0]
    st = _bands(nt, fac, levels)
    _additive(nt, ak.lin(color), st)
    return m


def sprite_mat(name, color, levels=((0.0, 0.08), (0.35, 0.22), (0.65, 0.5), (0.85, 1.0))):
    """Round glow on a UV-mapped quad: concentric flat bands."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    ak._use_nodes(m)
    _blended(m)
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    sub = N.new('ShaderNodeVectorMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    L.new(tc.outputs['UV'], sub.inputs[0])
    ln = N.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    L.new(sub.outputs[0], ln.inputs[0])
    inv = N.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    sc = N.new('ShaderNodeMath')
    sc.operation = 'MULTIPLY'
    sc.inputs[1].default_value = 2.0
    L.new(ln.outputs['Value'], sc.inputs[0])
    L.new(sc.outputs[0], inv.inputs[1])
    st = _bands(nt, inv.outputs[0], levels[1:] if levels[0][0] == 0 else levels)
    _additive(nt, ak.lin(color), st)
    return m


def tag(ob):
    ob['px_skip_id'] = True
    ob.visible_shadow = False
    return ob


def frustum(name, coll, top_c, top_r, bot_c, bot_r, mat, seg=32):
    """Open cone from top circle to bottom circle (a light shaft)."""
    top_c, bot_c = Vector(top_c), Vector(bot_c)
    part = ak.tube([top_c, bot_c], [top_r, bot_r], ring=seg, per=1, caps=(False, False))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in part['verts']], [], part['faces'])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return tag(ob)


def wedge(name, coll, corners_near, corners_far, mat):
    """Light spilling through an opening: a 4-sided open box between a near
    quad (at the opening) and a far quad (where it fades out)."""
    v = [Vector(c) for c in corners_near] + [Vector(c) for c in corners_far]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(x) for x in v], [], faces)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return tag(ob)


def sprite(name, coll, loc, radius, mat, camera=None):
    """Camera-facing glow quad (Track To the camera)."""
    r = radius
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-r, -r, 0), (r, -r, 0), (r, r, 0), (-r, r, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, l in enumerate(me.loops):
        uv.data[i].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][l.vertex_index]
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    if camera is not None:
        face_camera(ob, camera)
    return tag(ob)


def face_camera(ob, camera):
    c = ob.constraints.get('FaceCam') or ob.constraints.new('TRACK_TO')
    c.name = 'FaceCam'
    c.target = camera
    c.track_axis = 'TRACK_Z'
    c.up_axis = 'UP_Y'


def dust(name, coll, centre, size, count, mat, seed=1, r=0.012):
    """Motes as tiny octahedra in one mesh; animation can move the object or
    shape them later."""
    import random
    rnd = random.Random(seed)
    verts, faces = [], []
    c = Vector(centre)
    for i in range(count):
        p = c + Vector((rnd.uniform(-1, 1) * size[0], rnd.uniform(-1, 1) * size[1], rnd.uniform(-1, 1) * size[2]))
        b = len(verts)
        for d in ((r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r)):
            verts.append(tuple(p + Vector(d)))
        for f in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)):
            faces.append(tuple(b + k for k in f))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return tag(ob)
