"""Cut the hero's in-game sprites and the dialogue portraits out of the concept sheet.

assets/concept/character_sheet.png  ->  assets/sprites/hero_<pose>.png  (transparent, game size)
                                         assets/sprites/port_<name>.png  (dialogue portraits)

The sheet's background is a flat dark navy, so each sprite is cut by flooding the
background in from the crop border. The climb pose's vine is removed (the game draws
its own vines). Sprites are scaled so the hero is HERO_H pixels tall at render scale.
"""
from collections import deque
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "assets" / "concept" / "character_sheet.png"
OUT = ROOT / "assets" / "sprites"
HERO_H = 54            # standing height in render pixels (render scale 2 -> 27 world px)
BG_TOL = 18            # colour distance still counted as background

# pose -> crop box on the sheet (x0, y0, x1, y1)
POSES = {
    "idle":  (795, 755, 905, 905),
    "run":   (945, 755, 1070, 905),
    "jump":  (1095, 745, 1225, 905),
    "climb": (1245, 745, 1345, 905),
    "roll":  (1355, 790, 1515, 905),
}
# portraits: crop box, output size
PORTS = {
    "doc_calc":   ((36, 750, 182, 905), 72),
    "doc_amused": ((218, 750, 364, 905), 72),
    "doc_frust":  ((399, 750, 545, 905), 72),
    "doc_victor": ((580, 750, 726, 905), 72),
    "hero":       ((860, 50, 1100, 300), 72),
    "hero_m":     ((1250, 320, 1505, 575), 72),
}


def cut(im, box, strip_green=False):
    c = im.crop(box).convert("RGBA")
    w, h = c.size
    px = c.load()
    bg = px[0, 0][:3]

    def is_bg(p):
        return sum(abs(p[i] - bg[i]) for i in range(3)) <= BG_TOL

    seen = [[False] * h for _ in range(w)]
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or seen[x][y]:
            continue
        seen[x][y] = True
        if not is_bg(px[x, y]):
            continue
        px[x, y] = (0, 0, 0, 0)
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    if strip_green:
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a and g > r + 25 and g > b + 15:
                    px[x, y] = (0, 0, 0, 0)
    return c.crop(c.getbbox())


def shrink(c, scale):
    w, h = c.size
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    s = c.resize((nw, nh), Image.LANCZOS)
    p = s.load()
    for y in range(nh):
        for x in range(nw):
            r, g, b, a = p[x, y]
            p[x, y] = (r, g, b, 255) if a > 120 else (0, 0, 0, 0)
    return s


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(SHEET).convert("RGB")
    cuts = {k: cut(im, b, strip_green=(k == "climb")) for k, b in POSES.items()}
    scale = HERO_H / cuts["idle"].size[1]
    for k, c in cuts.items():
        s = shrink(c, scale)
        s.save(OUT / f"hero_{k}.png")
        print(f"hero_{k}: {c.size} -> {s.size}")
    for k, (b, size) in PORTS.items():
        p = im.crop(b).resize((size, size), Image.LANCZOS)
        p.save(OUT / f"port_{k}.png")
        print(f"port_{k}: {size}x{size}")


if __name__ == "__main__":
    main()
