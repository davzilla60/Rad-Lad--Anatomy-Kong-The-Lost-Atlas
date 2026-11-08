"""Pixel-art rendering for the cinematic.

render_pixel() makes one frame in three steps:
  1. colour pass: Eevee at the low "pixel" resolution with anti-aliasing off,
     so every pixel is one flat cel colour;
  2. ID pass: the same frame with every material switched to an emission that
     encodes (object index, material index, view depth) into an EXR;
  3. numpy post: 1px outlines on the near side of every edge. Silhouettes and
     depth jumps get dark ink; boundaries between parts of one surface get a
     darker shade of the local colour ("sel-out", as pixel artists do). Then
     a nearest-neighbour upscale.

The inverted-hull ink modifiers are switched off while rendering pixels: the
post pass draws every line at exactly one pixel.
"""
import os
import bpy
import numpy as np
import akcore as ak

DEPTH_SCALE = 100.0       # metres per unit of the ID pass blue channel
DZ = 0.035                # depth jump (m) that counts as an occlusion edge
DZ_SOFT = 0.009           # smaller jump inside one part: drawn as a soft line
SOFT_FAR = 22.0           # beyond this depth (m) small steps draw no lines (avoids mush)
CAST_SHADOWS = False      # pure cel bands; one-sample shadow maps streak at pixel scale
SOFT = np.array([0.56, 0.50, 0.66], np.float32)


def _hex(c):
    c = c.lstrip('#')
    return np.array([int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


INK = _hex(ak.INK)


def noline(*mats):
    """Materials whose pixels never receive a sel-out line (glints, pupils,
    mouths: small dark or bright details that a line would swallow)."""
    for m in mats:
        m['px_noline'] = True


def _out_node(nt):
    outs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
    for n in outs:
        if n.is_active_output:
            return n
    return outs[0] if outs else None


def _prepare(mats):
    """Give each material an ID emission branch. Returns {mat: id}."""
    ids = {}
    for i, m in enumerate(sorted(mats, key=lambda m: m.name)):
        mid = i + 1
        ids[m] = mid
        nt = m.node_tree
        if nt is None:
            continue
        out = _out_node(nt)
        if out is None:
            continue
        if 'PX_ID' not in nt.nodes:
            if out.inputs['Surface'].is_linked:
                m['px_orig'] = out.inputs['Surface'].links[0].from_node.name
            N, L = nt.nodes, nt.links
            oi = N.new('ShaderNodeObjectInfo')
            oi.name = 'PX_OI'
            cam = N.new('ShaderNodeCameraData')
            cam.name = 'PX_CAM'
            dv = N.new('ShaderNodeMath')
            dv.operation = 'DIVIDE'
            dv.inputs[1].default_value = 255.0
            dv.name = 'PX_DIV'
            dz = N.new('ShaderNodeMath')
            dz.operation = 'DIVIDE'
            dz.inputs[1].default_value = DEPTH_SCALE
            dz.name = 'PX_DZ'
            cc = N.new('ShaderNodeCombineColor')
            cc.name = 'PX_CC'
            emi = N.new('ShaderNodeEmission')
            emi.name = 'PX_ID'
            md = N.new('ShaderNodeMath')
            md.operation = 'MODULO'
            md.inputs[1].default_value = 256.0
            L.new(oi.outputs['Object Index'], md.inputs[0])
            L.new(md.outputs[0], dv.inputs[0])
            L.new(cam.outputs['View Z Depth'], dz.inputs[0])
            L.new(dv.outputs[0], cc.inputs[0])
            L.new(dz.outputs[0], cc.inputs[2])
            L.new(cc.outputs[0], emi.inputs['Color'])
            # depth split over two channels: Eevee's buffers are half floats,
            # which alone give ~5 mm steps at 10 m and draw false lines
            m10 = N.new('ShaderNodeMath')
            m10.operation = 'MULTIPLY'
            m10.inputs[1].default_value = 10.0
            L.new(cam.outputs['View Z Depth'], m10.inputs[0])
            fl = N.new('ShaderNodeMath')
            fl.operation = 'FLOOR'
            L.new(m10.outputs[0], fl.inputs[0])
            coarse = N.new('ShaderNodeMath')
            coarse.operation = 'DIVIDE'
            coarse.inputs[1].default_value = 64.0
            L.new(fl.outputs[0], coarse.inputs[0])
            fr = N.new('ShaderNodeMath')
            fr.operation = 'FRACT'
            L.new(m10.outputs[0], fr.inputs[0])
            cd = N.new('ShaderNodeCombineColor')
            L.new(coarse.outputs[0], cd.inputs[0])
            L.new(fr.outputs[0], cd.inputs[1])
            ed = N.new('ShaderNodeEmission')
            ed.name = 'PX_DEPTH'
            L.new(cd.outputs[0], ed.inputs['Color'])
        nt.nodes['PX_CC'].inputs[1].default_value = mid / 255.0
    return ids


def _id_mode(mats, on):
    """on: False (normal shading), True / 'id' (ID pass) or 'depth'."""
    for m in mats:
        nt = m.node_tree
        if nt is None or 'PX_ID' not in nt.nodes:
            continue
        out = _out_node(nt)
        if on == 'depth':
            src = nt.nodes.get('PX_DEPTH')
        else:
            src = nt.nodes['PX_ID'] if on else nt.nodes.get(m.get('px_orig', ''))
        if src is None:
            continue
        nt.links.new(src.outputs[0], out.inputs['Surface'])


def _scene_mats():
    mats = set()
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH' and not ob.hide_render:
            for s in ob.material_slots:
                if s.material:
                    mats.add(s.material)
    return mats


def _load(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1]   # row 0 = top
    bpy.data.images.remove(img)
    return a


def _save(path, a):
    h, w = a.shape[:2]
    img = bpy.data.images.new('px_out', w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def _shift(a, dy, dx, fill):
    out = np.full_like(a, fill)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def despeckle(rgb, key, passes=2):
    """Pixel-art cleanup: a pixel whose colour no 4-neighbour of the same part
    shares takes the most common colour among those neighbours."""
    h, w = key.shape
    code = (np.round(rgb * 255).astype(np.int64) * np.array([65536, 256, 1])).sum(-1)
    for _ in range(passes):
        ncodes, same = [], []
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nc = _shift(code, dy, dx, -1)
            nk = _shift(key, dy, dx, -2)
            ncodes.append(np.where(nk == key, nc, -1))
        nst = np.stack(ncodes)
        lonely = (key >= 0) & ~(nst == code).any(0) & ((nst >= 0).sum(0) >= 3)
        if not lonely.any():
            break
        ys, xs = np.nonzero(lonely)
        for y, x in zip(ys, xs):
            vals = [v for v in nst[:, y, x] if v >= 0]
            best = max(set(vals), key=vals.count)
            code[y, x] = best
    out = np.stack([(code >> 16) & 255, (code >> 8) & 255, code & 255], -1) / 255.0
    return out.astype(np.float32)


def outline(col, idp, noline_ids=()):
    """col: HxWx4 sRGB colour pass; idp: HxWx4 ID pass. Returns RGBA."""
    a = col[..., 3] > 0.5
    oid = np.round(idp[..., 0] * 255).astype(np.int64)
    mid = np.round(idp[..., 1] * 255).astype(np.int64)
    key = np.where(a, oid * 1000 + mid, -1)
    col = col.copy()
    col[..., :3] = despeckle(col[..., :3], key)
    z = np.where(a, idp[..., 2] * DEPTH_SCALE, 1e9)
    hard = np.zeros(a.shape, bool)
    soft = np.zeros(a.shape, bool)
    edge_bg = np.zeros(a.shape, bool)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nk = _shift(key, dy, dx, -1)
        nz = _shift(z, dy, dx, 1e9)
        oz = _shift(z, -dy, -dx, 1e9)          # the opposite neighbour
        bg = nk == -1
        edge_bg |= a & bg
        # depth jump measured against the surface's own slope, so a flat wall
        # seen edge-on (big but steady depth steps) draws no lines
        slope = np.where(oz < 1e8, z - oz, 0.0)
        jump = (nz - z) - np.maximum(slope, 0.0)
        near = z < SOFT_FAR
        hard |= a & (bg | ((nz - z > DZ) & (jump > DZ * 0.6)))
        soft |= a & ~bg & (nk != key) & (nz >= z - 0.002)
        # small depth steps within one part (nose over cheek, mortar, chin)
        soft |= a & ~bg & near & (jump > DZ_SOFT) & ~((nz - z > DZ) & (jump > DZ * 0.6))
    if len(noline_ids):
        protect = np.isin(mid, list(noline_ids))
        soft &= ~protect
        hard &= ~protect | edge_bg
    rgb = col[..., :3].copy()
    rgb[soft] = rgb[soft] * SOFT
    rgb[hard] = INK
    return np.dstack([rgb, a.astype(np.float32)])


def render_pixel(path, w, h, scale=3, bg='#1d1428', tmp_dir=None):
    sc = bpy.context.scene
    r = sc.render
    tmp_dir = tmp_dir or os.path.dirname(path)
    saved = (r.resolution_x, r.resolution_y, r.film_transparent, r.filter_size, r.dither_intensity,
             sc.eevee.taa_render_samples)
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = True
    r.filter_size = 0.0
    r.dither_intensity = 0.0
    sc.eevee.taa_render_samples = 1
    # hard shadows: one sample of a soft shadow is noise
    lights = [(l, l.angle, getattr(l, 'shadow_filter_radius', None), l.use_shadow)
              for l in bpy.data.lights if l.type == 'SUN']
    for l, _, _, _ in lights:
        l.angle = 0.0
        l.use_shadow = CAST_SHADOWS
    # point/spot lights too: a soft light sampled once hatches the cel bands
    soft = [(l, l.shadow_soft_size, l.use_shadow) for l in bpy.data.lights if l.type in ('POINT', 'SPOT', 'AREA')]
    for l, _, _ in soft:
        l.shadow_soft_size = 0.0
        l.use_shadow = CAST_SHADOWS
        if hasattr(l, 'shadow_filter_radius'):
            l.shadow_filter_radius = 0.0
    inks = [m for ob in sc.objects for m in ob.modifiers if m.name == 'Ink']
    for m in inks:
        m.show_render = False
    for i, ob in enumerate(sorted((o for o in sc.objects if o.type == 'MESH'), key=lambda o: o.name)):
        ob.pass_index = i + 1
    mats = _scene_mats()
    ids = _prepare(mats)

    cp = os.path.join(tmp_dir, '_px_col.png')
    ip = os.path.join(tmp_dir, '_px_id.exr')
    s = r.image_settings
    s.file_format, s.color_mode, s.color_depth = 'PNG', 'RGBA', '8'
    r.filepath = cp
    bpy.ops.render.render(write_still=True)
    _id_mode(mats, True)
    # light shapes (beams, glows, dust) colour the frame but take no part in lines
    skip = [o for o in sc.objects if o.get('px_skip_id') and not o.hide_render]
    for o in skip:
        o.hide_render = True
    s.file_format, s.color_depth = 'OPEN_EXR', '32'
    r.filepath = ip
    bpy.ops.render.render(write_still=True)
    dp = os.path.join(tmp_dir, '_px_depth.exr')
    _id_mode(mats, 'depth')
    r.filepath = dp
    bpy.ops.render.render(write_still=True)
    for o in skip:
        o.hide_render = False
    _id_mode(mats, False)
    s.file_format, s.color_depth = 'PNG', '8'

    col, idp, dep = _load(cp), _load(ip), _load(dp)
    for p in (cp, ip, dp):
        os.remove(p)
    # exact depth from the coarse + fine channels replaces the ID pass's blue
    idp[..., 2] = (np.round(dep[..., 0] * 64.0) + dep[..., 1]) / 10.0 / DEPTH_SCALE
    nl = [mid for m, mid in ids.items() if m.get('px_noline')]
    out = outline(col, idp, nl)
    if bg:
        b = _hex(bg)
        al = out[..., 3:4]
        out = np.dstack([out[..., :3] * al + b * (1 - al), np.ones(al.shape, np.float32)])
    out = np.repeat(np.repeat(out, scale, 0), scale, 1)
    _save(path, out)

    for m in inks:
        m.show_render = True
    for l, ang, fr, us in lights:
        l.angle = ang
        l.use_shadow = us
        if fr is not None:
            l.shadow_filter_radius = fr
    for l, sz, us in soft:
        l.shadow_soft_size = sz
        l.use_shadow = us
    (r.resolution_x, r.resolution_y, r.film_transparent, r.filter_size, r.dither_intensity,
     sc.eevee.taa_render_samples) = saved
    return out
