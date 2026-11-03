"""Anatomy Kong 3D cutscene prototype: 'The Atlas' (vault scene).
Builds the scene, saves vault.blend beside this script, then optionally renders.
  With Blender:   blender --background --python vault.py -- [--still N[,N..]] [--clean] [--anim]
  With pip bpy:   python vault.py [--still N[,N..]] [--clean] [--anim]
No flags: just build and save vault.blend (open it in Blender to look around).
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix

OUT = os.path.dirname(os.path.abspath(__file__))
FPS, END = 24, 300
random.seed(7)
D2R = math.radians

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = END

# ---------------------------------------------------------------- materials
def mat(name, col, rough=.6, metal=0., emit=None, estr=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = estr
    return m

def glow(name, col, strength, alpha=1.):
    """emission that can be keyed (node 'E'), optionally see-through"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission"); e.name = "E"
    e.inputs[0].default_value = (*col, 1); e.inputs[1].default_value = strength
    if alpha < 1:
        t = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs[0].default_value = 1 - alpha
        nt.links.new(t.outputs[0], mx.inputs[1]); nt.links.new(e.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], o.inputs[0])
    else:
        nt.links.new(e.outputs[0], o.inputs[0])
    return m

def stone(name, col, scale, mortar, brick=(.5, .25)):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = scale
    br.inputs["Color1"].default_value = (*col, 1)
    br.inputs["Color2"].default_value = (*[c * .78 for c in col], 1)
    br.inputs["Mortar"].default_value = (*mortar, 1)
    br.inputs["Mortar Size"].default_value = .015
    br.inputs["Brick Width"].default_value = brick[0]; br.inputs["Row Height"].default_value = brick[1]
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 18
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = .35
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = .4
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(br.outputs["Color"], mix.inputs["A"]); nt.links.new(nz.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs[0], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = .85
    return m

# ink outline: inverted hull, black where the far side shows past the silhouette
INK = bpy.data.materials.new("ink"); INK.use_nodes = True
nt = INK.node_tree; nt.nodes.clear()
o = nt.nodes.new("ShaderNodeOutputMaterial"); g = nt.nodes.new("ShaderNodeNewGeometry")
e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (.01, .005, .02, 1)
t = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(g.outputs["Backfacing"], mx.inputs[0]); nt.links.new(e.outputs[0], mx.inputs[1])
nt.links.new(t.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs[0])

# ---------------------------------------------------------------- object helpers
def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); sc.collection.objects.link(o)
    o.parent = parent; o.location = loc; o.empty_display_size = .1
    return o

def part(kind, name, loc, scale, m, parent=None, rot=(0, 0, 0), ink=.012, smooth=True, bevel=0, **kw):
    if kind == "sphere": bpy.ops.mesh.primitive_uv_sphere_add(segments=kw.get("seg", 24), ring_count=kw.get("ring", 14), radius=1)
    elif kind == "cyl": bpy.ops.mesh.primitive_cylinder_add(vertices=kw.get("seg", 20), radius=1, depth=1)
    elif kind == "cone": bpy.ops.mesh.primitive_cone_add(vertices=kw.get("seg", 24), radius1=kw["r1"], radius2=kw["r2"], depth=1)
    elif kind == "cube": bpy.ops.mesh.primitive_cube_add(size=2)
    elif kind == "torus": bpy.ops.mesh.primitive_torus_add(major_radius=kw["R"], minor_radius=kw["r"], major_segments=kw.get("seg", 40), minor_segments=10)
    elif kind == "plane": bpy.ops.mesh.primitive_plane_add(size=2)
    ob = bpy.context.active_object; ob.name = name
    ob.scale = scale; ob.rotation_euler = [D2R(a) for a in rot]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    ob.data.materials.append(m)
    if smooth and kind not in ("cube", "plane"): bpy.ops.object.shade_smooth()
    if bevel:
        bv = ob.modifiers.new("bev", "BEVEL"); bv.width = bevel; bv.segments = 2
    ob.parent = parent; ob.location = loc
    if ink:   # inverted hull: a copy pushed out along its normals, faces turned inside out
        me = ob.data.copy(); me.materials.clear(); me.materials.append(INK)
        bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
        for v in bm.verts: v.co += v.normal * ink
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:]); bm.to_mesh(me); bm.free()
        h = bpy.data.objects.new(name + "_ink", me); sc.collection.objects.link(h)
        h.parent = parent; h.location = loc
        h.visible_shadow = False; h.visible_diffuse = False; h.visible_glossy = False
    return ob

def key(ob, path, f, val, idx=-1, interp=None):
    if path in ("location", "rotation_euler", "scale") and not isinstance(val, (int, float)):
        setattr(ob, path, val)
    elif path == "rotation_euler":
        ob.rotation_euler[idx] = val
    elif path == "location":
        ob.location[idx] = val
    else:
        setattr(ob, path, val)
    ob.keyframe_insert(path, index=idx, frame=f)

def keynode(m, node, sock, f, val):
    s = m.node_tree.nodes[node].inputs[sock]; s.default_value = val
    s.keyframe_insert("default_value", frame=f)

def keylight(l, f, energy):
    l.data.energy = energy; l.data.keyframe_insert("energy", frame=f)

# ---------------------------------------------------------------- Dr Dissection
COAT = mat("coat", (.80, .78, .90), .7)
SHIRT = mat("shirt", (.06, .045, .06), .8)
TROU = mat("trousers", (.07, .065, .09), .8)
SHOE = mat("shoes", (.03, .02, .02), .35)
SKIN = mat("skin", (.62, .38, .26), .55)
HAIR1 = mat("hair_lt", (.58, .57, .60), .5)
HAIR2 = mat("hair_dk", (.26, .25, .28), .5)
BLACK = mat("black", (.01, .01, .012), .3)
EYE = mat("eye", (.02, .015, .01), .2)
LENS = mat("lens", (.7, .75, .9), .05, emit=(.5, .55, .8), estr=.15)
RED = mat("pen_red", (.7, .12, .08), .4); BLUE = mat("pen_blue", (.1, .25, .75), .4)

doc = empty("DrDissection")
legs = {}
for side, x in (("L", .105), ("R", -.105)):
    p = empty("hip" + side, (x, 0, .95), doc)
    part("cyl", "leg" + side, (0, 0, -.45), (.078, .078, .9), TROU, p)
    part("cube", "shoe" + side, (0, -.06, -.91), (.075, .14, .045), SHOE, p, bevel=.02)
    legs[side] = p
part("cone", "coat", (0, 0, 1.05), (1, 1, 1), COAT, doc, r1=.31, r2=.235, seg=28)
part("sphere", "shoulders", (0, 0, 1.5), (.30, .2, .1), COAT, doc)
part("cube", "shirt", (0, -.24, 1.3), (.07, .018, .25), SHIRT, doc, rot=(-4, 0, 0))
for sx in (1, -1):
    part("cube", "lapel", (sx * .1, -.245, 1.38), (.035, .012, .17), COAT, doc, rot=(-4, 0, sx * -14))
    part("cube", "collar", (sx * .07, -.17, 1.58), (.06, .02, .035), SHIRT, doc, rot=(0, 0, sx * 30))
part("cyl", "penR", (.15, -.262, 1.36), (.012, .012, .1), RED, doc, ink=.006)
part("cyl", "penB", (.18, -.258, 1.36), (.012, .012, .1), BLUE, doc, ink=.006)
neck = empty("neck", (0, 0, 1.6), doc)
part("cyl", "neckm", (0, 0, .02), (.062, .062, .14), SKIN, neck)
H = (0, 0, -1.6)  # head parts were laid out in body space; shift into neck space
def hp(kind, name, loc, scale, m, **kw):
    return part(kind, name, (loc[0], loc[1], loc[2] + H[2]), scale, m, neck, **kw)
hp("sphere", "head", (0, 0, 1.79), (.145, .155, .185), SKIN)
hp("sphere", "jaw", (0, -.035, 1.69), (.12, .115, .075), SKIN)
hp("cone", "nose", (0, -.165, 1.77), (1, 1, .06), SKIN, rot=(90, 0, 0), r1=.025, r2=.006, seg=10, ink=.006)
for sx in (1, -1):
    hp("sphere", "ear", (sx * .148, .01, 1.78), (.025, .045, .055), SKIN, ink=.008)
    hp("sphere", "eye", (sx * .056, -.138, 1.8), (.017, .012, .017), EYE, ink=0)
    hp("cube", "brow", (sx * .058, -.148, 1.845), (.042, .01, .009), HAIR2, ink=0, rot=(0, sx * -16, 0))
    hp("torus", "rim", (sx * .058, -.158, 1.8), (1.2, 1, .85), BLACK, rot=(90, 0, 0), R=.038, r=.0065, ink=0, seg=24)
    hp("cyl", "lens", (sx * .058, -.156, 1.8), (.045, .036, .003), LENS, rot=(90, 0, 0), ink=0)
    hp("cube", "arm_g", (sx * .118, -.07, 1.805), (.004, .085, .004), BLACK, ink=0)
hp("cube", "bridge", (0, -.16, 1.805), (.018, .004, .004), BLACK, ink=0)
hp("cube", "smirk", (.012, -.143, 1.708), (.042, .006, .006), mat("mouth", (.25, .08, .07)), ink=0, rot=(0, -9, 0))
for (x, y, z, r, m) in [(0, .03, 1.93, .14, HAIR1), (-.08, .05, 1.91, .1, HAIR2), (.085, .05, 1.92, .1, HAIR1),
                        (0, .09, 1.85, .15, HAIR2), (-.13, .04, 1.84, .07, HAIR1), (.13, .04, 1.85, .07, HAIR2),
                        (-.02, -.07, 1.955, .085, HAIR1), (.05, -.10, 1.975, .06, HAIR2), (-.07, -.06, 1.94, .065, HAIR2),
                        (0, .12, 1.74, .12, HAIR1), (.1, .1, 1.97, .07, HAIR1)]:
    hp("sphere", "hair", (x, y, z), (r, r * 1.05, r * .85), m, seg=16, ring=10)

arms = {}
for side, x in (("L", .285), ("R", -.285)):
    sh = empty("shoulder" + side, (x, 0, 1.48), doc)
    part("cyl", "sleeve" + side, (0, 0, -.17), (.068, .068, .36), COAT, sh)
    el = empty("elbow" + side, (0, 0, -.34), sh)
    part("cyl", "fore" + side, (0, 0, -.14), (.06, .06, .3), COAT, el)
    part("sphere", "hand" + side, (0, 0, -.33), (.055, .045, .065), SKIN, el)
    hand = empty("grip" + side, (0, -.03, -.36), el)
    sh.rotation_euler.z = D2R(-6 if side == "L" else 6); sh.rotation_euler.y = D2R(-6 if side == "L" else 6)
    arms[side] = (sh, el, hand)

# ---------------------------------------------------------------- the vault
FLOOR = stone("floor", (.16, .17, .22), 1.6, (.04, .04, .05), (.5, .5))
WALL = stone("wall", (.18, .17, .24), 1.2, (.05, .045, .06))
COL = mat("column", (.28, .27, .33), .7)
GOLD = mat("gold", (.95, .66, .22), .28, metal=1)
PEDM = mat("pedestal", (.34, .32, .38), .6)
part("plane", "floor", (0, 0, 0), (40, 40, 1), FLOOR, ink=0)
part("plane", "wall", (0, 3.6, 4), (40, 6, 1), WALL, rot=(90, 0, 0), ink=0)
for x in (-7.5, -4.2, 4.2, 7.5):
    part("cyl", "column", (x, 2.8, 3), (.42, .42, 6), COL, ink=.02, seg=24)
    part("cube", "colbase", (x, 2.8, .18), (.55, .55, .18), COL, ink=.02, bevel=.03)
    part("cube", "colcap", (x, 2.8, 3.6), (.55, .55, .14), COL, ink=.02, bevel=.03)
    part("torus", "colring", (x, 2.8, 3.38), (1, 1, 1), GOLD, R=.44, r=.035, ink=0)
FLAME = glow("flame", (1, .45, .1), 25)
torches = []
for x in (-5.85, -2.4, 2.4, 5.85):
    part("cube", "sconce", (x, 3.5, 2.3), (.08, .1, .2), GOLD, bevel=.02, ink=.01)
    part("cone", "flame", (x, 3.38, 2.55), (1, 1, .22), FLAME, r1=.07, r2=0, seg=12, ink=0)
    bpy.ops.object.light_add(type="POINT", location=(x, 3.1, 2.65)); L = bpy.context.active_object
    L.data.energy = 60; L.data.color = (1, .55, .25); L.data.shadow_soft_size = .15; torches.append(L)
# wall emblem behind the pedestal: a dim golden glyph
EMB = glow("emblem", (1, .7, .25), .8)
part("torus", "emblem", (0, 3.55, 3.1), (1, 1, 1), EMB, rot=(90, 0, 0), R=1.25, r=.03, ink=0, seg=64)
part("torus", "emblem2", (0, 3.55, 3.1), (1, 1, 1), EMB, rot=(90, 0, 0), R=.95, r=.015, ink=0, seg=64)

# ---------------------------------------------------------------- blocking: walk, stop, reach
START_X, STOP_X, WALK_END = -5.6, -.85, 150
def ang(a): return D2R(a)
# walking: speed profile, stride phase drives limbs
vel = [1. if f < 118 else max(0., 1 - (f - 118) / 32) for f in range(WALK_END + 1)]
tot = sum(vel[1:]); dist = 0.; STRIDE = .62
for f in range(1, WALK_END + 1):
    dist += vel[f] / tot * (STOP_X - START_X)
    ph = 2 * math.pi * dist / (2 * STRIDE); a = vel[f]
    if f == 1 or f % 2 == 0 or f == WALK_END:
        key(doc, "location", f, (START_X + dist, 0, .025 * a * abs(math.sin(ph))))
        key(legs["L"], "rotation_euler", f, ang(26 * a * math.sin(ph)), 0)
        key(legs["R"], "rotation_euler", f, ang(-26 * a * math.sin(ph)), 0)
        key(arms["L"][0], "rotation_euler", f, ang(-14 * a * math.sin(ph)), 0)
        key(arms["R"][0], "rotation_euler", f, ang(14 * a * math.sin(ph)), 0)
        key(arms["L"][1], "rotation_euler", f, ang(-12 - 8 * a), 0)
        key(arms["R"][1], "rotation_euler", f, ang(-12 - 8 * a), 0)
        key(neck, "rotation_euler", f, ang(2 * a * math.sin(2 * ph)), 0)
key(doc, "rotation_euler", 1, ang(90), 2); key(doc, "rotation_euler", 150, ang(90), 2)
key(doc, "rotation_euler", 176, ang(62), 2)           # turns three-quarters to the pedestal
key(neck, "rotation_euler", 176, ang(4), 0); key(neck, "rotation_euler", 176, ang(10), 2)
sR, eR, gR = arms["R"]; sL, eL, gL = arms["L"]
key(sR, "rotation_euler", 182, 0, 0); key(eR, "rotation_euler", 182, ang(-14), 0)
key(sR, "rotation_euler", 206, ang(-78), 0); key(eR, "rotation_euler", 206, ang(-8), 0)   # the reach
key(neck, "rotation_euler", 206, ang(13), 0)
key(sR, "rotation_euler", 218, ang(-80), 0)
# draws the Atlas in and holds it up at the chest
key(sR, "rotation_euler", 246, ang(-14), 0); key(eR, "rotation_euler", 246, ang(-92), 0)
key(sR, "rotation_euler", 246, ang(14), 2)
key(neck, "rotation_euler", 246, ang(-6), 0); key(neck, "rotation_euler", 246, ang(-14), 2)
key(sL, "rotation_euler", 176, 0, 0); key(sL, "rotation_euler", 250, ang(-6), 0)
key(eL, "rotation_euler", 250, ang(-30), 0)
key(doc, "rotation_euler", 250, ang(62), 2); key(doc, "rotation_euler", 285, ang(32), 2)
key(doc, "location", 250, (STOP_X, 0, 0)); key(doc, "location", 300, (STOP_X, 0, .01))
key(sR, "rotation_euler", 300, ang(-18), 0); key(neck, "rotation_euler", 300, ang(-8), 0)

for o in bpy.data.objects:
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves if hasattr(o.animation_data.action, "fcurves") else []:
            for k in fc.keyframe_points: k.interpolation = "BEZIER"

def world(ob, f):
    sc.frame_set(f); return ob.matrix_world.translation.copy()

# ---------------------------------------------------------------- pedestal and the Atlas (placed where the hand reaches)
reach = world(gR, 206); print("REACH", tuple(round(v,2) for v in reach), "DOC", tuple(round(v,2) for v in world(doc,206)))
BOOKC = Vector((reach.x + .03, reach.y - .01, reach.z + .015))
top = BOOKC.z - .2; PX, PY = BOOKC.x + .02, BOOKC.y
part("cyl", "ped_base", (PX, PY, .09), (.36, .36, .18), PEDM, ink=.015, seg=28)
part("cyl", "ped_col", (PX, PY, top / 2), (.19, .19, top - .2), PEDM, ink=.015, seg=24)
part("cyl", "ped_top", (PX, PY, top - .05), (.29, .29, .1), PEDM, ink=.015, seg=28)
part("torus", "ped_ring", (PX, PY, top - .1), (1, 1, 1), GOLD, R=.29, r=.022, ink=0)
part("torus", "ped_ring2", (PX, PY, .18), (1, 1, 1), GOLD, R=.36, r=.022, ink=0)
GLYPH = glow("glyph", (1, .72, .3), 6)
for r, w in ((1.05, .02), (.8, .012), (1.25, .008)):
    part("torus", "glyph", (PX, PY, .004), (1, 1, .05), GLYPH, R=r, r=w, ink=0, seg=64)
for i in range(8):
    a = i / 8 * 2 * math.pi
    part("cube", "rune", (PX + .93 * math.cos(a), PY + .93 * math.sin(a), .004), (.05, .012, .002), GLYPH, ink=0, rot=(0, 0, math.degrees(a)))
BEAM = glow("beam", (1, .78, .4), 3, alpha=.93)
part("cyl", "beam", (PX, PY, top + 3), (.2, .2, 6), BEAM, ink=0, seg=32)

book = empty("Atlas")
COVER = mat("cover", (.16, .02, .025), .45)
PAGES = mat("pages", (.92, .86, .7), .9)
BGLOW = glow("bookglow", (1, .72, .3), 6)
part("cube", "cover", (0, 0, 0), (.13, .03, .17), COVER, book, bevel=.008, ink=.008)
part("cube", "pagesblk", (.008, 0, 0), (.122, .026, .162), PAGES, book, ink=0)
part("cyl", "emblem", (0, -.031, .02), (.055, .055, .004), BGLOW, book, rot=(90, 0, 0), ink=0)
part("cube", "spine_band", (-.13, 0, .1), (.004, .033, .012), GOLD, book, ink=0)
part("cube", "spine_band2", (-.13, 0, -.1), (.004, .033, .012), GOLD, book, ink=0)
bpy.ops.object.light_add(type="POINT", location=(0, -.3, .05)); BL = bpy.context.active_object
BL.parent = book; BL.data.color = (1, .7, .35); BL.data.shadow_soft_size = .1

# hover, flicker, snap to the hand, then held (baked per frame against the hand)
for f in range(1, END + 1):
    hov = BOOKC + Vector((0, 0, .03 * math.sin(f / 13)))
    rot = (D2R(8), D2R(4 * math.sin(f / 19)), D2R(28 + f * .9))
    if f <= 206:
        loc = hov
    else:
        h = world(gR, f) + Vector((0, 0, .02))
        t = min(1, (f - 206) / 14); t = t * t * (3 - 2 * t)
        loc = hov.lerp(h, t)
        held = (D2R(-10), D2R(0), D2R(20))
        rot = tuple(r0 + (r1 - r0) * t for r0, r1 in zip((D2R(8), 0, D2R(28 + 206 * .9) % (2 * math.pi)), held))
    if f % 2 == 0 or f in (1, 206, 207, END):
        key(book, "location", f, tuple(loc)); key(book, "rotation_euler", f, rot)
sc.frame_set(1)
# light cues
keylight(BL, 1, 12); keylight(BL, 196, 12)
for f, v in ((199, 60), (201, 10), (203, 80), (205, 15), (208, 60), (220, 140), (232, 25), (300, 18)): keylight(BL, f, v)
keynode(BGLOW, "E", 1, 1, 3); keynode(BGLOW, "E", 1, 205, 4); keynode(BGLOW, "E", 1, 220, 30); keynode(BGLOW, "E", 1, 240, 6)
keynode(BEAM, "E", 1, 1, 3); keynode(BEAM, "E", 1, 214, 3); keynode(BEAM, "E", 1, 236, 0)
keynode(GLYPH, "E", 1, 1, 6); keynode(GLYPH, "E", 1, 216, 8); keynode(GLYPH, "E", 1, 250, .6)

# ---------------------------------------------------------------- lights
def light(kind, loc, energy, col, rot=(0, 0, 0), size=1., spot=None):
    bpy.ops.object.light_add(type=kind, location=loc); L = bpy.context.active_object
    L.data.energy = energy; L.data.color = col; L.rotation_euler = [D2R(a) for a in rot]
    if kind == "AREA": L.data.size = size
    else: L.data.shadow_soft_size = size
    if spot: L.data.spot_size = D2R(spot); L.data.spot_blend = .6
    return L
SPOT = light("SPOT", (PX, PY, 6), 900, (1, .78, .45), size=.3, spot=24)
keylight(SPOT, 1, 900); keylight(SPOT, 214, 900); keylight(SPOT, 238, 120)
KEY = light("AREA", (-2.6, -2.8, 3.2), 260, (1, .9, .8), rot=(55, 0, -40), size=2)
FILL = light("AREA", (-3, -6, 4), 260, (.45, .55, 1), rot=(60, 0, -25), size=6)
RIM = light("SPOT", (STOP_X + 1.0, 1.9, 2.8), 60, (.7, .35, 1), size=.5, spot=30)
rt = RIM.constraints.new("TRACK_TO"); rt.target = doc; rt.track_axis = "TRACK_NEGATIVE_Z"; rt.up_axis = "UP_Y"
keylight(RIM, 1, 80); keylight(RIM, 222, 80); keylight(RIM, 262, 900)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (.008, .008, .02, 1)

# dust motes in the beam
DUST = glow("dust", (1, .85, .5), 6)
for i in range(46):
    a = random.random() * 6.28; r = random.random() * .5
    x0, y0, z0 = PX + r * math.cos(a), PY + r * math.sin(a), random.random() * 3.2
    d = part("sphere", "dust", (x0, y0, z0), (.008, .008, .008), DUST, ink=0, seg=6, ring=4)
    key(d, "location", 1, (x0, y0, z0)); key(d, "location", END, (x0 + random.uniform(-.2, .2), y0, z0 + .5 + random.random() * .5))

# ---------------------------------------------------------------- camera (three shots, hard cuts)
bpy.ops.object.camera_add(); cam = bpy.context.active_object; sc.camera = cam
cam.data.lens = 32
aim = empty("aim")
tc = cam.constraints.new("TRACK_TO"); tc.target = aim; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
def shot(f, c, t, lens=None):
    key(cam, "location", f, c); key(aim, "location", f, t)
    if lens: cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
# A: tracking him down the vault, the beam waiting ahead (1-140)
for f in range(1, 141, 10):
    dx = world(doc, f).x; u = f / 140
    shot(f, (dx - .4 + 1.2 * u, -6.6 + 1.2 * u, 2.0 - .2 * u), (dx + 1.1, 0, 1.3), 32)
shot(140, (world(doc, 140).x + .8, -5.4, 1.8), (world(doc, 140).x + 1.1, 0, 1.3), 32)
# B: front three-quarter, pedestal to the right; slow push as he reaches (141-221)
hd = Vector((STOP_X, 0, 1.55)); mid = (hd + BOOKC) / 2
shot(141, (mid.x - .6, mid.y - 3.1, 1.75), (mid.x, mid.y, 1.45), 38)
shot(221, (mid.x - .5, mid.y - 2.45, 1.6), (mid.x, mid.y, 1.5), 38)
# C: low angle, the villain with his prize (222-300)
shot(222, (STOP_X - .35, -1.95, .9), (STOP_X + .05, 0, 1.55), 30)
shot(300, (STOP_X - .3, -1.6, .85), (STOP_X + .05, 0, 1.62), 30)
for f, d in ((224, (.03, 0, .025)), (226, (-.025, 0, -.02)), (229, (.01, 0, .008))):   # the burst jolts the frame
    sc.frame_set(f); key(cam, "location", f, tuple(cam.location + Vector(d)))
# hard cuts: constant interpolation on the camera rig
for ob in (cam, aim, cam.data):
    ad = ob.animation_data
    if ad and ad.action:
        for lay in getattr(ad.action, "layers", []):
            for st in lay.strips:
                for cb in st.channelbags:
                    for fc in cb.fcurves:
                        for k in fc.keyframe_points:
                            if k.co.x in (140, 141, 221, 222): k.interpolation = "CONSTANT"
        for fc in getattr(ad.action, "fcurves", []):
            for k in fc.keyframe_points:
                if k.co.x in (140, 141, 221, 222): k.interpolation = "CONSTANT"

# ---------------------------------------------------------------- render setup
r = sc.render
r.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 24; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
sc.cycles.transparent_max_bounces = 10; sc.cycles.transmission_bounces = 2
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"; sc.view_settings.exposure = .6
r.resolution_x, r.resolution_y = 384, 216
r.film_transparent = False
r.image_settings.file_format = "PNG"

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
clean = "--clean" in args
if clean:
    r.resolution_x, r.resolution_y = 1152, 648; sc.cycles.samples = 64
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "vault.blend"))
if "--still" in args:
    for f in args[args.index("--still") + 1].split(","):
        sc.frame_set(int(f)); r.filepath = os.path.join(OUT, "stills", f"{'clean' if clean else 'px'}_{int(f):03d}.png")
        bpy.ops.render.render(write_still=True)
elif "--anim" in args:
    r.filepath = os.path.join(OUT, "frames", "f_"); bpy.ops.render.render(animation=True)
