"""Painted art for the tomb, drawn pixel by pixel in numpy.

The story on the walls: the Atlas began as the first illustration of the
inside of the body, painted on the tomb's back wall. Gold threads run from it
to panels showing everything it led to:
  left wall  - anatomy through history: hand stencils, an Egyptian figure with
               canopic jars, a Greek figure with blood vessels, a Renaissance
               skeleton;
  right wall - imaging today: X-ray, CT, MRI and ultrasound.
"""
import math
import random
import numpy as np
import akcore as ak

PAL = {
    'plaster': '#cbb489', 'plaster_dk': '#b49c72', 'stone': '#6c5944',
    'ochre': '#b8662c', 'ochre_lt': '#d08a4a', 'red': '#9a2a1e', 'pink': '#c87a6e',
    'black': '#2a1c14', 'white': '#efe6d0', 'bone': '#e6d8b6', 'brown': '#7a4a2a',
    'film': '#1a1a22', 'grey': '#8a8a94', 'grey_lt': '#c8c8d0', 'gold': '#e0b050', 'blue': '#3a5a8a',
}


def C(name):
    c = ak.srgb_arr(PAL.get(name, name))
    c[3] = 1.0
    return c


class Canvas:
    def __init__(self, w, h, bg='plaster'):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.float32)
        if bg:
            self.a[:] = C(bg)
        yy, xx = np.mgrid[0:h, 0:w]
        self.xx, self.yy = xx, yy

    def mask_set(self, m, col):
        self.a[m] = C(col)

    def rect(self, x0, y0, x1, y1, col):
        self.a[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)] = C(col)

    def ellipse(self, cx, cy, rx, ry, col, ring=0):
        d = ((self.xx - cx) / max(rx, 0.1)) ** 2 + ((self.yy - cy) / max(ry, 0.1)) ** 2
        m = d <= 1.0 if not ring else (d <= 1.0) & (d >= (1 - ring / max(rx, ry)) ** 2)
        self.a[m] = C(col)
        return m

    def line(self, x0, y0, x1, y1, col, w=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for t in np.linspace(0, 1, n):
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            r = (w - 1) / 2
            self.a[max(0, int(round(y - r))):int(round(y + r)) + 1, max(0, int(round(x - r))):int(round(x + r)) + 1] = C(col)

    def poly(self, pts, col):
        x, y = self.xx + 0.5, self.yy + 0.5
        inside = np.zeros((self.h, self.w), bool)
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            cond = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1)
            inside ^= cond
        self.a[inside] = C(col)
        return inside

    def icon(self, rows, x, y, col, s=1):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch == 'X':
                    self.rect(x + i * s, y + j * s, x + (i + 1) * s, y + (j + 1) * s, col)

    def outline(self, m, col):
        """1px outline round a mask (pixels of m next to non-m)."""
        e = np.zeros_like(m)
        e[1:, :] |= m[1:, :] & ~m[:-1, :]
        e[:-1, :] |= m[:-1, :] & ~m[1:, :]
        e[:, 1:] |= m[:, 1:] & ~m[:, :-1]
        e[:, :-1] |= m[:, :-1] & ~m[:, 1:]
        self.a[e] = C(col)

    def weather(self, rnd, flakes=5, cracks=3, edge=True):
        """Flaking plaster (shows stone), hairline cracks, darkened edges."""
        for _ in range(flakes):
            # flaked-off plaster: an irregular patch of the paler under-layer,
            # with a darker rim where the edge has lifted
            cx, cy = rnd.uniform(0, self.w), rnd.uniform(0, self.h)
            r = rnd.uniform(1.5, max(2.0, self.w / 16))
            d = (self.xx - cx) ** 2 / r ** 2 + (self.yy - cy) ** 2 / (r * rnd.uniform(0.5, 1.2)) ** 2
            m = (d <= 1) & (np.random.default_rng(rnd.randrange(1 << 30)).random(d.shape) < 0.9)
            self.a[(d > 1) & (d <= 1.5)] = self.a[(d > 1) & (d <= 1.5)] * 0.85 + C('plaster_dk') * 0.15
            self.a[m] = C('plaster_dk')
        for _ in range(cracks):
            x, y = rnd.uniform(0, self.w), rnd.uniform(0, self.h)
            for _ in range(int(self.h * 0.6)):
                x += rnd.choice((-1, 0, 0, 1))
                y += 1
                if 0 <= x < self.w and 0 <= y < self.h:
                    self.a[int(y), int(x)] = C('black') * 0.6 + self.a[int(y), int(x)] * 0.4
                    self.a[int(y), int(x), 3] = 1
        if edge:
            k = 2
            for sl in ((slice(0, k), slice(None)), (slice(-k, None), slice(None)),
                       (slice(None), slice(0, k)), (slice(None), slice(-k, None))):
                self.a[sl][..., :3] *= 0.82

    def image(self, name):
        return ak.image_from_array(name, self.a)


# ------------------------------------------------------------------ pictographs
ICONS = {
    'xray': ["...X.X....", ".X.X.X.X..", ".X.X.X.X..", ".X.X.X.X..", ".XXXXXXX.X", ".XXXXXXXXX",
             ".XXXXXXXX.", "..XXXXXX..", "..XXXXX...", "...XXXX..."],
    'ct': ["..XXXXXX..", ".XX....XX.", "XX......XX", "X..XXXX..X", "X..XXXX..X", "X........X",
           "XX......XX", ".XX....XX.", "..XXXXXX..", "XXXXXXXXXX"],
    'mri': ["XXX....XXX", "XXX....XXX", "XXX....XXX", "XXX....XXX", "XXX....XXX", "XXXX..XXXX",
            ".XXXXXXXX.", "..XXXXXX..", "..........", ".........."],
    'us': ["....XX....", "...XXXX...", "..X.XX.X..", ".X..XX..X.", "X...XX...X", "X.X....X.X",
           "X..X..X..X", ".X......X.", "..XXXXXX..", ".........."],
    'figure': ["X...XX...X", ".X.XXXX.X.", "..X.XX.X..", "...XXXX...", "....XX....", "...XXXX...",
               "..X.XX.X..", "....XX....", "...X..X...", "..X....X.."],
}


# ------------------------------------------------------------------ the first illustration
def first_illustration(rnd):
    """The original anatomical figure (96 x 128): an ochre body with the
    skeleton and organs drawn inside it, hieroglyph columns either side."""
    cv = Canvas(96, 128)
    cx = 48
    # faint halo of dots
    for k in range(40):
        a = k / 40 * math.tau
        x, y = cx + math.cos(a) * 42, 64 + math.sin(a) * 52
        cv.rect(x, y, x + 2, y + 2, 'ochre_lt')
    # body silhouette
    body = np.zeros((cv.h, cv.w), bool)
    body |= cv.ellipse(cx, 20, 8.5, 10, 'ochre')
    body |= cv.poly([(44, 28), (52, 28), (53, 34), (43, 34)], 'ochre')
    body |= cv.poly([(29, 35), (67, 35), (64, 52), (59, 72), (61, 84), (35, 84), (37, 72), (32, 52)], 'ochre')
    for sx in (-1, 1):
        body |= cv.poly([(cx + sx * 18, 35), (cx + sx * 22, 38), (cx + sx * 36, 54), (cx + sx * 33, 57),
                         (cx + sx * 17, 44)], 'ochre')                          # upper arm + forearm, raised
        body |= cv.ellipse(cx + sx * 37, 57, 3.2, 3.6, 'ochre')                  # hand
        body |= cv.poly([(cx + sx * 2, 84), (cx + sx * 12, 84), (cx + sx * 12, 120), (cx + sx * 6, 120)], 'ochre')
        body |= cv.ellipse(cx + sx * 10, 121, 5, 2.5, 'ochre')
    # inside: brain, spine, ribs, lungs, heart, liver, stomach, pelvis, limb bones
    cv.ellipse(cx, 18, 6, 6.5, 'pink')
    for k in range(5):
        cv.line(cx - 4 + k * 2, 14, cx - 3 + k * 2, 22, 'red')
    for sx in (-1, 1):
        cv.ellipse(cx + sx * 8, 50, 5.5, 9, 'pink')
    cv.line(cx, 30, cx, 82, 'bone', 2)
    for k in range(6):
        y = 40 + k * 4
        for sx in (-1, 1):
            cv.line(cx, y, cx + sx * 13, y + 3, 'bone')
    cv.ellipse(cx + 3, 54, 3.5, 3.5, 'red')
    cv.ellipse(cx - 5, 66, 7, 3.5, 'brown')
    cv.ellipse(cx + 6, 66, 4.5, 3.5, 'pink')
    cv.line(cx - 10, 80, cx, 84, 'bone', 2)
    cv.line(cx + 10, 80, cx, 84, 'bone', 2)
    for sx in (-1, 1):
        cv.line(cx + sx * 7, 86, cx + sx * 8, 118, 'bone', 2)
        cv.line(cx + sx * 20, 39, cx + sx * 34, 54, 'bone')
    cv.outline(body, 'black')
    # hieroglyph columns
    glyphs = ['figure', 'xray', 'ct', 'mri', 'us']
    for i in range(5):
        cv.icon(ICONS[glyphs[i]], 2, 8 + i * 23, 'black', 1)
        cv.icon(ICONS[glyphs[(i + 2) % 5]], 84, 8 + i * 23, 'red', 1)
    cv.weather(rnd, flakes=5, cracks=3)
    return cv


# ------------------------------------------------------------------ frieze panels (48 x 48)
def panel_hands(rnd):
    cv = Canvas(48, 48)
    for x, y in ((6, 6), (24, 10)):
        cv.ellipse(x + 8, y + 9, 10, 11, 'red')
        cv.icon(ICONS['xray'], x + 3, y + 3, 'plaster', 1)  # negative hand stencil
    for i, x in enumerate((10, 22, 34)):
        cv.ellipse(x, 33, 1.8, 1.8, 'ochre')
        cv.line(x, 35, x, 41, 'ochre')
        cv.line(x - 3, 37, x + 3, 37, 'ochre')
        cv.line(x, 41, x - 2, 45, 'ochre')
        cv.line(x, 41, x + 2, 45, 'ochre')
    cv.weather(rnd, 4, 2)
    return cv


def panel_egypt(rnd):
    cv = Canvas(48, 48)
    m = cv.poly([(18, 6), (24, 6), (25, 12), (23, 14), (28, 16), (29, 30), (26, 31), (26, 44), (22, 44),
                 (21, 32), (19, 44), (15, 44), (16, 30), (13, 30), (15, 16), (19, 14)], 'ochre')
    cv.ellipse(21, 8, 4, 4, 'black')
    cv.outline(m, 'black')
    cv.ellipse(23, 21, 2, 2, 'red')
    for i, col in enumerate(('brown', 'ochre_lt', 'brown', 'ochre_lt')):
        x = 31 + i * 4
        cv.rect(x, 36, x + 3, 44, col)
        cv.ellipse(x + 1.5, 35, 1.8, 1.6, 'black')
    cv.line(2, 46, 46, 46, 'blue')
    cv.weather(rnd, 4, 2)
    return cv


def panel_greek(rnd):
    cv = Canvas(48, 48)
    m = cv.ellipse(24, 8, 4, 4.5, 'plaster_dk')
    m |= cv.poly([(16, 14), (32, 14), (30, 30), (31, 44), (17, 44), (18, 30)], 'plaster_dk')
    cv.outline(m, 'black')
    cv.ellipse(25, 20, 2.5, 2.5, 'red')
    rr = random.Random(5)
    for _ in range(9):
        x, y = 25, 20
        for _ in range(8):
            nx, ny = x + rr.choice((-2, -1, 1, 2)), y + rr.choice((-2, 1, 2, 3))
            cv.line(x, y, nx, ny, 'red')
            x, y = nx, ny
    cv.icon(ICONS['figure'], 36, 4, 'black', 1)
    cv.weather(rnd, 4, 2)
    return cv


def panel_skeleton(rnd):
    cv = Canvas(48, 48)
    cv.ellipse(24, 7, 4.5, 5, 'bone')
    cv.rect(22, 6, 23, 8, 'black')
    cv.rect(25, 6, 26, 8, 'black')
    cv.line(24, 12, 24, 30, 'bone', 2)
    for k in range(5):
        y = 15 + k * 3
        cv.line(24, y, 17, y + 2, 'bone')
        cv.line(24, y, 31, y + 2, 'bone')
    cv.line(18, 30, 30, 30, 'bone', 2)
    for sx in (-1, 1):
        cv.line(24 + sx * 3, 13, 24 + sx * 11, 26, 'bone')
        cv.line(24 + sx * 11, 26, 24 + sx * 12, 34, 'bone')
        cv.line(24 + sx * 4, 31, 24 + sx * 6, 44, 'bone', 2)
    cv.icon(ICONS['figure'], 2, 36, 'brown', 1)
    cv.weather(rnd, 4, 2)
    return cv


def panel_xray(rnd):
    cv = Canvas(48, 48)
    cv.rect(6, 4, 42, 44, 'film')
    for k, x in enumerate((15, 20, 25, 30)):
        top = 10 + abs(k - 1.5) * 2
        for seg in range(3):
            y0 = top + seg * 5
            cv.line(x, y0, x, y0 + 3, 'grey_lt')
    cv.line(35, 20, 33, 28, 'grey_lt')
    for x in (15, 20, 25, 30):
        cv.line(x, 26, 23, 36, 'grey')
    cv.line(20, 36, 21, 42, 'grey_lt', 2)
    cv.line(26, 36, 25, 42, 'grey_lt', 2)
    cv.weather(rnd, 3, 2)
    return cv


def panel_ct(rnd):
    """A CT scanner: the gantry ring with a patient sliding through on the table."""
    cv = Canvas(48, 48)
    ring = cv.ellipse(26, 22, 16, 17, 'grey')
    cv.ellipse(26, 22, 10, 10.5, 'plaster')
    cv.outline(ring, 'black')
    cv.ellipse(26, 22, 16, 17, 'black', ring=1)
    cv.rect(2, 27, 46, 29, 'grey_lt')                     # table
    cv.rect(6, 29, 9, 40, 'grey')                         # table leg
    cv.rect(38, 29, 41, 40, 'grey')
    body = cv.ellipse(23, 25, 13, 2.2, 'ochre')           # patient lying down
    body |= cv.ellipse(8, 24.5, 2.6, 2.6, 'ochre')        # head
    cv.outline(body, 'black')
    cv.rect(2, 40, 46, 42, 'brown')
    cv.weather(rnd, 3, 2)
    return cv


def panel_mri(rnd):
    """An MRI head, side view: skull outline, folded brain, cerebellum, cord."""
    cv = Canvas(48, 48)
    cv.rect(6, 4, 42, 44, 'film')
    head = cv.ellipse(23, 21, 12, 13.5, 'grey')
    head |= cv.poly([(33, 19), (38, 25), (33, 27)], 'grey')            # nose
    cv.ellipse(22, 18, 9, 8.5, 'grey_lt')
    for k in range(6):
        x = 15 + k * 2.6
        cv.line(x, 12 + (k % 2) * 2, x + 1, 22, 'grey')                 # folds
    cv.ellipse(15, 27, 3.5, 2.6, 'grey_lt')                            # cerebellum
    cv.line(20, 27, 21, 43, 'grey_lt', 2)                              # brainstem / cord
    cv.outline(head, 'white')
    cv.weather(rnd, 3, 2)
    return cv


def panel_us(rnd):
    cv = Canvas(48, 48)
    cv.rect(4, 4, 44, 44, 'film')
    cv.poly([(24, 6), (42, 38), (6, 38)], 'grey')
    g = np.random.default_rng(7).random((48, 48)) < 0.25
    fan = cv.poly([(24, 8), (40, 36), (8, 36)], 'grey')
    cv.a[fan & g] = C('grey_lt')
    cv.ellipse(25, 26, 6, 4, 'film')
    cv.weather(rnd, 3, 2)
    return cv


LEFT = [panel_hands, panel_egypt, panel_greek, panel_skeleton]       # anatomy through history
RIGHT = [panel_xray, panel_ct, panel_mri, panel_us]                  # imaging today


def cover(rnd):
    """The Atlas cover: worn dark leather, tooled border, the first
    illustration's figure in gilt."""
    cv = Canvas(48, 64, bg='#4a2a1c')
    wear = np.random.default_rng(3).random((64, 48)) < 0.07
    cv.a[wear] = C('#5e3826')
    for x in range(4, 44, 3):
        cv.rect(x, 3, x + 1, 4, 'gold')
        cv.rect(x, 60, x + 1, 61, 'gold')
    for y in range(4, 60, 3):
        cv.rect(3, y, 4, y + 1, 'gold')
        cv.rect(44, y, 45, y + 1, 'gold')
    cv.ellipse(24, 30, 14, 14, 'gold', ring=1)
    cv.icon(ICONS['figure'], 14, 20, 'gold', 2)
    cv.rect(14, 50, 34, 51, 'gold')
    return cv
