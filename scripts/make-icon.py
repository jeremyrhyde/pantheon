"""Draw a placeholder module app icon: a dark rounded tile with a glowing
dot-constellation glyph, in the spirit of Hestia's and Pluto's icons.

    uv run python scripts/make-icon.py <glyph> <out_dir> <file:size>...

Glyphs: sun (Apollo), hermes (winged H), flame (Hestia), bident (Pluto), wing.

e.g. `... sun modules/apollo/frontend/public icon-512.png:512`. Replace the
output with real art at the same paths any time — nothing else changes.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

BASE = 1024
GLYPHS = {
    "sun": (255, 200, 90),      # Apollo — gold
    "hermes": (170, 205, 255),  # Hermes — silver-blue winged H
    "flame": (255, 140, 60),    # Hestia — ember orange hearth flame
    "bident": (205, 215, 230),  # Pluto — silver bident
    "wing": (170, 205, 255),    # a lone wing (kept for reuse)
}

Stroke = list[tuple[float, float]]


def bezier(p0, p1, p2, n=9) -> Stroke:
    """n points along a quadratic Bézier from p0 to p2, pulled toward p1."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1])
            for t in (i / (n - 1) for i in range(n))]


def line(p0, p1, n) -> Stroke:
    return [(p0[0] + (p1[0] - p0[0]) * i / (n - 1), p0[1] + (p1[1] - p0[1]) * i / (n - 1))
            for i in range(n)]


def sun() -> list[list[tuple[float, float]]]:
    c = BASE / 2
    ring = [(c + 170 * math.cos(a), c + 170 * math.sin(a))
            for a in (i * 2 * math.pi / 24 for i in range(25))]
    inner = [(c + 80 * math.cos(a), c + 80 * math.sin(a))
             for a in (i * 2 * math.pi / 12 for i in range(13))]
    rays = [[(c + r * math.cos(a), c + r * math.sin(a)) for r in (230, 280, 330, 375)]
            for a in (i * 2 * math.pi / 12 for i in range(12))]
    return [ring, inner, *rays]


def hermes() -> list[Stroke]:
    # The winged H from Hermes's own icon, redrawn as a constellation: two
    # uprights and a crossbar, with three swept feathers off each upright.
    left, right, top, bottom, bar = 420, 604, 300, 740, 520
    strokes = [line((left, top), (left, bottom), 9),
               line((right, top), (right, bottom), 9),
               line((left, bar), (right, bar), 5)]
    for k, (y, reach, lift) in enumerate(((340, 250, 150), (400, 220, 105), (460, 185, 65))):
        strokes.append(bezier((left, y), (left - reach * 0.55, y + 10), (left - reach, y - lift), 7))
        strokes.append(bezier((right, y), (right + reach * 0.55, y + 10), (right + reach, y - lift), 7))
    return strokes


def flame() -> list[Stroke]:
    # A hearth flame: a full teardrop, an inner tongue, and two crossed logs
    # beneath it.
    c = BASE / 2
    tip, base = (c + 10, 180), (c, 760)
    outer_l = bezier(base, (230, 620), tip, 15)
    outer_r = bezier(base, (794, 620), tip, 15)
    inner_l = bezier((c, 740), (390, 600), (c - 5, 400), 9)
    inner_r = bezier((c, 740), (634, 600), (c - 5, 400), 9)
    log_a = line((330, 790), (694, 870), 9)
    log_b = line((330, 870), (694, 790), 9)
    return [outer_l, outer_r, inner_l, inner_r, log_a, log_b]


def bident() -> list[Stroke]:
    # Pluto's two-pronged staff: a shaft, a crossguard, and two prongs that
    # flare slightly outward.
    c = BASE / 2
    shaft = line((c, 370), (c, 870), 11)
    guard = bezier((360, 390), (c, 415), (664, 390), 11)
    prong_l = bezier((360, 390), (330, 280), (370, 150), 7)
    prong_r = bezier((664, 390), (694, 280), (654, 150), 7)
    butt = bezier((460, 870), (c, 895), (564, 870), 5)
    return [shaft, guard, prong_l, prong_r, butt]


def wing() -> list[Stroke]:
    # A swept wing: a leading-edge arc from the root up to the tip, and flight
    # feathers fanning from the root to a scalloped trailing edge below it.
    root = (270, 720)
    tip = (790, 250)
    leading = bezier(root, (250, 420), tip, 13)
    ends = [(tip[0] + 10, tip[1] + 90), (800, 400), (775, 520), (725, 620), (655, 700), (565, 760)]
    feathers = []
    for k, end in enumerate(ends):
        mid = ((root[0] + end[0]) / 2, (root[1] + end[1]) / 2)
        feathers.append(bezier(root, (mid[0] - 60 + 12 * k, mid[1] - 90 + 8 * k), end, 9))
    return [leading, *feathers]


def draw(glyph: str) -> Image.Image:
    color = GLYPHS[glyph]
    strokes = {"sun": sun, "hermes": hermes, "flame": flame, "bident": bident, "wing": wing}[glyph]()
    rng = random.Random(glyph)

    tile = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, BASE - 1, BASE - 1), radius=200, fill=(8, 10, 16, 255))

    glow = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    art = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    g, a = ImageDraw.Draw(glow), ImageDraw.Draw(art)
    for _ in range(260):                                   # background dust
        x, y, r = rng.uniform(80, 944), rng.uniform(80, 944), rng.uniform(1, 2.6)
        a.ellipse((x - r, y - r, x + r, y + r), fill=(*color, rng.randint(40, 120)))
    for stroke in strokes:
        a.line(stroke, fill=(*color, 110), width=3)
        g.line(stroke, fill=(*color, 160), width=18)
        for x, y in stroke:
            r = rng.uniform(5, 9)
            a.ellipse((x - r, y - r, x + r, y + r), fill=(*color, 255))
            g.ellipse((x - 3 * r, y - 3 * r, x + 3 * r, y + 3 * r), fill=(*color, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(22))

    out = Image.alpha_composite(tile, glow)
    out = Image.alpha_composite(out, art)
    mask = Image.new("L", (BASE, BASE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, BASE - 1, BASE - 1), radius=200, fill=255)
    out.putalpha(mask)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] not in GLYPHS:
        print(__doc__, file=sys.stderr)
        return 2
    image = draw(argv[0])
    out_dir = Path(argv[1])
    specs = []
    for spec in argv[2:]:
        name, _, size = spec.partition(":")
        if not name or not size.isdigit() or int(size) < 1:
            print(f"bad size spec {spec!r} (want file:size)", file=sys.stderr)
            print(__doc__, file=sys.stderr)
            return 2
        specs.append((name, int(size)))
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, size in specs:
        image.resize((size, size), Image.LANCZOS).save(out_dir / name)
        print(f"wrote {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
