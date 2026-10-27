"""Generate the animated ASCII SVGs for the GitHub profile README.

    python3 gen.py <out_dir>

Colors come from notaroomba.dev (tailwind argentinian_blue scale + the hero's
"everything" offset colors). GitHub strips JS, so everything animates with CSS:
either keyframes cycling pre-rendered frames, or transforms on static layers.
Each header/footer/about comes in a desktop (900 wide) and mobile (480 wide)
version; the README swaps them with <picture media="(max-width: 600px)">.
"""
import math
import os
import random
import re
import sys

import base64
import io

import pyfiglet
from fontTools import subset
from fontTools.ttLib import TTFont

from icons import ICONS

BLUE = {
    100: "#00233d", 200: "#00457a", 300: "#0068b8", 400: "#008bf5",
    500: "#35a7ff", 600: "#5cb8ff", 700: "#85caff", 800: "#addcff", 900: "#d6edff",
}
# real star colors, hottest to coolest (O/B blue-white .. M red), weighted toward white
STAR = ["#9bb0ff", "#cad7ff", "#f8f7ff", "#ffffff", "#fff4ea", "#ffe4b5", "#ffd2a1", "#ffb48a"]
STAR_DIM = ["#3a4466", "#55596e", "#5e5a52", "#66503f", "#5c3b2e"]
# accretion disk: dull red at the edge to white-hot near the horizon
HOT = ["#2b0d02", "#5c1d04", "#8f3405", "#c4540a", "#e87b14", "#f6a62a", "#fcc75e", "#fee2a0", "#fff5df", "#ffffff"]
# gas giant bands
PLANET = ["#5a3a22", "#8a5a34", "#b98552", "#dcb486"]
# offset layers from the site's "everything", back to front
RETRO = [(-2, "#01204E"), (-1, "#028393"), (2, "#F65625"), (1, "#FAAA68"), (0, "#F6DCAC")]
# the same colors stacked for the name, back to front
# name colors, back to front, and which way the back layers step (+1 right, -1 left).
# "athena" follows the Athena logo: red in front, layers stepping left, white in place of beige.
PALETTES = {
    "classic": (["#01204E", "#028393", "#F65625", "#FAAA68", "#F6DCAC"], 1),
    "athena": (["#01204E", "#028393", "#ffffff", "#FAAA68", "#F65625"], -1),
}
SMOKE = "#f2f4f3"
BG = "#000000"
EDGE = "#2d2a26"  # neutral card border
FPS = 1  # every animation updates this many times a second, all on the same beats, so the image repaints rarely
LOOP = 0  # for pre-rendered frames: every animation then repeats a whole number of times in LOOP seconds, so frames loop seamlessly
DETAIL = False  # for pre-rendered frames: they cost nothing to play, so the black hole gets every particle
MONO = "ui-monospace, SFMono-Regular, 'JetBrains Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# Blender Pro Bold for all readable text; the ASCII scenes stay monospace so columns line up.
# The font is subset to printable ASCII and embedded, since an SVG shown as an <img> can't fetch fonts.
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BlenderProBold.ttf")


def _load_font():
    font = TTFont(FONT_PATH)
    opts = subset.Options()
    opts.layout_features = ["kern"]
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=range(0x20, 0x7F))
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return font, base64.b64encode(buf.getvalue()).decode()


_FONT, _FONT_B64 = _load_font()
_CMAP, _HMTX, _UPM = _FONT.getBestCmap(), _FONT["hmtx"], _FONT["head"].unitsPerEm
FONT_FACE = (f"@font-face{{font-family:'Blender Pro';font-weight:700;"
             f"src:url(data:font/ttf;base64,{_FONT_B64}) format('truetype')}}"
             ".bp,.bp text{font-family:'Blender Pro','Rajdhani','Arial Narrow',sans-serif;font-weight:700}")


def measure(text, size):
    """Advance width of text in Blender Pro Bold at size px."""
    return sum(_HMTX[_CMAP[ord(c)]][0] for c in text if ord(c) in _CMAP) * size / _UPM


CHAR_W = 7.5
LINE_H = 13.5
FRAMES = 32
DT = 0.11
T = FRAMES * DT

DESKTOP = dict(w=900, banner_cell=(8, 13), sub_font=19, sub_lines=1, scene_rows=14, about_font=18)
MOBILE = dict(w=480, banner_cell=(4.6, 8), sub_font=17, sub_lines=2, scene_rows=11, about_font=18)

SOCIALS = [
    ("github", "github", "notaroomba", "https://github.com/notaroomba"),
    ("instagram", "instagram", "@notaroomba", "https://instagram.com/notaroomba"),
    ("linkedin", "linkedin", "in/notaroomba", "https://linkedin.com/in/notaroomba"),
    ("youtube", "youtube", "@notaroomba", "https://youtube.com/@notaroomba"),
    ("site", "website", "notaroomba.dev", "https://notaroomba.dev"),
]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def color_classes():
    colors = dict.fromkeys([*BLUE.values(), *STAR, *STAR_DIM, *HOT, *PLANET])
    return "".join(f".b{c[1:]}{{fill:{c}}}" for c in colors)


def frame_css(prefix):
    pct = 100 / FRAMES
    return (
        f"@keyframes {prefix}k{{0%{{opacity:1}}{pct:.3f}%{{opacity:0}}100%{{opacity:0}}}}"
        f".{prefix}{{opacity:0;animation:{prefix}k {T:.2f}s step-end infinite}}"
        + "".join(f".{prefix}{i}{{animation-delay:{i * DT - T:.2f}s}}" for i in range(FRAMES))
    )


def grid_to_svg(grid, y0, width):
    """One <text> per (row, color), other cells blanked, stretched to the full width."""
    out = []
    for y, row in enumerate(grid):
        for c in sorted({c for ch, c in row if c and ch != " "}):
            s = "".join(ch if cc == c else " " for ch, cc in row)
            out.append(f'<text y="{y0 + (y + 1) * LINE_H:g}" class="b{c[1:]}" textLength="{width}">{esc(s)}</text>')
    return "".join(out)


def frames_group(frames, y0, width, prefix):
    return "".join(
        f'<g class="{prefix} {prefix}{i}">{grid_to_svg(g, y0, width)}</g>' for i, g in enumerate(frames)
    )


# ---------------------------------------------------------------- waves
WAVE_LAYERS = [
    # (base row, [(amp, spatial cycles per 120 cols, temporal cycles per loop, phase)], body chars, surface color, body colors)
    (3.0, [(1.6, 3, 1, 0.0), (0.6, 7, -1, 1.3)], "  .", BLUE[200], [BLUE[100]]),
    (5.6, [(1.9, 4, -1, 2.1), (0.5, 9, 2, 0.4)], ". .", BLUE[300], [BLUE[200], BLUE[100]]),
    (8.4, [(2.4, 4, 1, 4.0), (0.7, 7, -2, 0.9), (0.3, 13, 3, 2.2)], "=-:..",
     BLUE[700], [BLUE[500], BLUE[400], BLUE[300], BLUE[200], BLUE[200], BLUE[100]]),
]


def wave_frames(cols, rows, shift=0.0):
    """shift moves the waves up (negative) or down so shorter strips still show all layers."""
    def surface(layer, x, f):
        h = layer[0] + shift
        for amp, k, n, ph in layer[1]:
            h += amp * math.sin(2 * math.pi * (k * x / 120 - n * f / FRAMES) + ph)
        return h

    frames = []
    for f in range(FRAMES):
        grid = [[(" ", None)] * cols for _ in range(rows)]
        for li, layer in enumerate(WAVE_LAYERS):
            _, _, fill, top_c, body_cs = layer
            front = li == len(WAVE_LAYERS) - 1
            hs = [surface(layer, x, f) for x in range(-1, cols + 1)]
            for x in range(cols):
                h = hs[x + 1]
                top = math.floor(h)
                frac = h - top
                # sub-row precision: high in the cell -> '~', middle -> '-', low -> '_'
                ch = "~" if frac < 0.34 else "-" if frac < 0.67 else "_"
                crest = front and hs[x + 1] <= hs[x] and hs[x + 1] <= hs[x + 2]
                if 0 <= top < rows:
                    grid[top][x] = (ch, BLUE[900] if crest else top_c)
                if crest and 0 <= top - 1 < rows and (x + f // 4) % 3 == 0:
                    grid[top - 1][x] = ("*" if (f // 4) % 2 else ".", BLUE[900])  # foam spray
                for y in range(max(top + 1, 0), rows):
                    d = y - top - 1
                    # drift the texture sideways every other frame so the water body moves
                    hx = (x - f // 2 * (1 if li % 2 == 0 else -1)) % cols
                    gap = (hx * 3 + y * 5) % 8 < min(2 * max(d - 1, 0), 7) if front else (hx + y) % 2 == 1
                    c = body_cs[min(d, len(body_cs) - 1)]
                    grid[y][x] = (" " if gap else fill[min(d, len(fill) - 1)], c)
        frames.append(grid)
    return frames


def scene_waves(width, rows, y0, prefix="w", shift=0.0):
    cols = round(width / CHAR_W)
    return frame_css(prefix), frames_group(wave_frames(cols, rows, shift), y0, width, prefix)


# ---------------------------------------------------------------- stars
def scene_stars(width, height, prefix="s", seed=3, density=1.0):
    """Three parallax layers drifting left, twinkling bright stars, and a shooting star."""
    rnd = random.Random(seed)
    rows = int(height / LINE_H) + 1
    # a layer drifts one tile per period. Normally the tile is the full width; for a short
    # seamless loop it is a third of it, so the layers keep their slow, distinct speeds
    tile_w = width / round(width / 300) if LOOP else width
    cols = round(tile_w / CHAR_W)
    css, out = [], []
    for li, (chars, palette, prob, dur) in enumerate([
        (".", STAR_DIM, 0.05, 90), ("..+", STAR[1:7], 0.022, 55), ("+*", STAR, 0.008, 32),
    ]):
        if LOOP:
            dur = LOOP / (li + 1)
        grid = [[(rnd.choice(chars), rnd.choice(palette)) if rnd.random() < prob * density else (" ", None)
                 for _ in range(cols)] for _ in range(rows)]
        tile = grid_to_svg(grid, 0, tile_w)
        css.append(f"@keyframes {prefix}d{li}{{from{{transform:translateX(0)}}to{{transform:translateX(-{tile_w:g}px)}}}}"
                   f".{prefix}l{li}{{animation:{prefix}d{li} {dur:g}s linear infinite}}")
        copies = "".join(f'<g transform="translate({j * tile_w:g} 0)">{tile}</g>' for j in range(round(width / tile_w) + 1))
        out.append(f'<g class="{prefix}l{li}">{copies}</g>')
    css.append(f"@keyframes {prefix}tw{{0%,100%{{opacity:.15}}50%{{opacity:1}}}}")
    for _ in range(int(14 * density * width / 900) + 4):
        x, y = rnd.uniform(10, width - 10), rnd.uniform(10, height - 4)
        dur, delay = rnd.uniform(2.2, 4.5), rnd.uniform(-4.5, 0)
        out.append(f'<text x="{x:.0f}" y="{y:.0f}" class="b{rnd.choice(STAR)[1:]}" style="animation:{prefix}tw {dur:.1f}s {delay:.1f}s ease-in-out infinite">{rnd.choice("*+")}</text>')
    css.append(
        f"@keyframes {prefix}sh{{0%{{transform:translate({width * 0.85:.0f}px,-10px);opacity:0}}"
        f"2%{{opacity:1}}10%{{transform:translate({width * 0.35:.0f}px,{height * 0.55:.0f}px);opacity:0}}"
        f"100%{{transform:translate({width * 0.35:.0f}px,{height * 0.55:.0f}px);opacity:0}}}}"
        f".{prefix}sh{{animation:{prefix}sh 7s 1.5s ease-out infinite;opacity:0}}"
    )
    out.append(f'<g class="{prefix}sh"><text class="bffffff" transform="rotate(-38)">*<tspan class="bfff4ea">=</tspan><tspan class="bffe4b5">-</tspan><tspan class="b{STAR_DIM[2][1:]}">-</tspan><tspan class="b{STAR_DIM[1][1:]}">.</tspan></text></g>')
    return "".join(css), "".join(out)


def _planet_geom(w, H, rows):
    r = w * 1.1
    return w / 2, H - rows * LINE_H * 0.55 + r, r


def planet_defs(w, H, rows):
    cx, cy, r = _planet_geom(w, H, rows)
    return (f'<clipPath id="pl"><circle cx="{cx:g}" cy="{cy:g}" r="{r:g}"/></clipPath>'
            f'<radialGradient id="atm" gradientUnits="userSpaceOnUse" cx="{cx:g}" cy="{cy:g}" r="{r + 40:g}">'
            f'<stop offset="{r / (r + 40):.4f}" stop-color="#ffb877" stop-opacity=".4"/>'
            f'<stop offset="1" stop-color="#ffb877" stop-opacity="0"/></radialGradient>')


def planet_horizon(w, H, rows):
    """The curved limb of an ASCII planet; its cloud bands drift sideways under a clip."""
    cx, cy, r = _planet_geom(w, H, rows)
    cols = round(w / CHAR_W)
    top_row = int((cy - r) / LINE_H) - 1
    rnd = random.Random(11)
    lines = []
    for y in range(top_row, int(H / LINE_H) + 2):
        band = math.sin(y * 1.3) * 0.5 + 0.5
        s = "".join(
            ("=" if band > 0.7 else ":" if band > 0.35 else ".") if rnd.random() < 0.55 + 0.3 * band else " "
            for _ in range(cols)
        )
        c = PLANET[min(3, int(band * 4))]
        lines.append(f'<text y="{(y + 1) * LINE_H:g}" class="b{c[1:]}" textLength="{w}">{s}</text>')
    tile = "".join(lines)
    css = (f"@keyframes pd{{from{{transform:translateX(0)}}to{{transform:translateX(-{w}px)}}}}"
           f".pd{{animation:pd 40s linear infinite}}")
    svg = (f'<circle cx="{cx:g}" cy="{cy:g}" r="{r + 40:g}" fill="url(#atm)"/>'
           f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{BG}"/>'
           f'<g clip-path="url(#pl)"><g class="pd"><g>{tile}</g><g transform="translate({w} 0)">{tile}</g></g></g>'
           f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="#ffd2a1" stroke-width="1.2" stroke-dasharray="2 5"/>')
    return css, svg


# ---------------------------------------------------------------- black hole
RAMP = " .,:-=+*#%@"
RAMP_C = [None, *HOT]


def blackhole_frames(cols, rows, rs):
    """ASCII Gargantua: tilted accretion disk with spiral arms, Doppler-brightened on the
    approaching side, a lensed ring hugging the shadow, and an empty shadow."""
    cx, cy = (cols - 1) / 2, (rows - 1) / 2
    tilt = 0.17
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        grid = [[(" ", None)] * cols for _ in range(rows)]
        for y in range(rows):
            for x in range(cols):
                px, py = (x - cx) * CHAR_W, (y - cy) * LINE_H
                r_screen = math.hypot(px, py)
                u, v = px, py / tilt
                rd = math.hypot(u, v)
                th = math.atan2(v, u)
                inten = 0.0
                in_disk = 1.6 * rs < rd < 8 * rs
                if in_disk:
                    arms = 0.6 + 0.4 * math.sin(3 * th + rd * 0.05 - 2 * math.pi * t)
                    fall = (1.6 * rs / rd) ** 0.9
                    edge = min(1, (rd - 1.6 * rs) / (0.3 * rs))
                    doppler = 1 + 0.45 * math.cos(th + math.pi)  # left side approaches us
                    # far half of the disk sits behind the shadow
                    if not (py < 0 and r_screen < rs * 1.05):
                        inten = fall * arms * edge * doppler
                # lensed image of the far disk: a bright ring hugging the shadow
                phi = math.atan2(py, px)
                ring = math.exp(-(((r_screen - 1.45 * rs) / (0.3 * rs)) ** 2))
                ring *= (0.75 + 0.25 * math.sin(3 * phi - 2 * math.pi * t)) * (1 + 0.3 * math.cos(phi + math.pi))
                inten = max(inten, ring * 1.1)
                if r_screen < rs and not (py > 0 and in_disk):
                    inten = 0.0  # event horizon shadow
                i = min(len(RAMP) - 1, int(min(inten, 1) ** 0.6 * (len(RAMP) - 1) + 0.2))
                if i > 0:
                    grid[y][x] = (RAMP[i], RAMP_C[i])
        frames.append(grid)
    return frames


def scene_blackhole(width, rows, y0):
    """A smooth ASCII black hole. Every glyph is a particle gliding along its own orbit
    with CSS offset-path (kept upright), on Keplerian timing so the inner disk whips round
    and the outer disk drifts. Behind it: a warm glow and a lensed halo circling the
    shadow; in front: the near half of the disk, re-drawn over the shadow via a clip."""
    small = width < 600
    rs = 30 if small else 40
    cx, cy = width / 2, y0 + rows * LINE_H / 2
    tilt = 0.2
    rnd = random.Random(5)
    css = [
        ".pt{transform-box:view-box;offset-rotate:0deg;offset-anchor:0 0;text-anchor:middle;dominant-baseline:central}",
        "@keyframes orb{from{offset-distance:0%}to{offset-distance:100%}}",
        # brightest on the approaching (left) side of each orbit: Doppler beaming
    ]

    def ellipse(rx, ry):
        # start at the right edge, run counter-clockwise on screen (near side moves right to left)
        return (f"M{cx + rx:.1f} {cy:.1f}A{rx:.1f} {ry:.1f} 0 1 1 {cx - rx:.1f} {cy:.1f}"
                f"A{rx:.1f} {ry:.1f} 0 1 1 {cx + rx:.1f} {cy:.1f}Z")

    # kept deliberately light: one animation per particle and no duplicated layers,
    # since every particle is a separately composited moving element
    def particle(path, period, ch, color, size, opacity):
        d = -rnd.uniform(0, period)
        return (f'<text class="pt b{color[1:]}" style="font-size:{size:.1f}px;opacity:{opacity:.2f};offset-path:path(\'{path}\');'
                f'animation:orb {period:.2f}s {d:.2f}s linear infinite">{ch}</text>')

    disk = []
    n_disk = (550 if small else 1100) if DETAIL else (120 if small else 240)
    r_in, r_out = 1.6 * rs, (5.6 if small else 8.5) * rs
    for _ in range(n_disk):
        # more particles near the hot inner edge
        r = r_in + (r_out - r_in) * rnd.random() ** 1.3
        heat = 1 - (r - r_in) / (r_out - r_in)
        idx = max(0, min(len(HOT) - 1, int(heat * (len(HOT) - 1) + rnd.uniform(-1.2, 1.2))))
        ramp = "@#%*+=-:." if heat > 0.5 else "*+=-:.."
        ch = ramp[min(len(ramp) - 1, int((1 - heat) * len(ramp) + rnd.uniform(-1, 1)) % len(ramp))]
        period = 5.5 * (r / r_in) ** 1.5
        disk.append(particle(ellipse(r, r * tilt + rnd.uniform(-2.5, 2.5)), period, ch, HOT[idx], 10 + 3 * heat, 0.55 + 0.45 * rnd.random()))

    halo = []
    for _ in range((90 if small else 170) if DETAIL else (28 if small else 50)):
        r = rs * rnd.uniform(1.22, 1.5)
        idx = rnd.randint(5, len(HOT) - 1)
        halo.append(particle(ellipse(r, r * rnd.uniform(0.92, 1.0)), rnd.uniform(7, 10), rnd.choice("*+.:o"), HOT[idx], 10, 0.7 + 0.3 * rnd.random()))

    glow = (f'<radialGradient id="bhg" gradientUnits="userSpaceOnUse" cx="{cx:g}" cy="{cy:g}" r="{r_out:g}" '
            f'gradientTransform="translate(0 {cy * (1 - 0.35):g}) scale(1 0.35)">'
            f'<stop offset="0" stop-color="#e87b14" stop-opacity=".45"/><stop offset=".35" stop-color="#8f3405" stop-opacity=".18"/>'
            f'<stop offset="1" stop-color="#2b0d02" stop-opacity="0"/></radialGradient>')
    # occlusion without drawing the disk twice: the shadow sits under the disk, so the near
    # side (lower half) passes in front of it, and a black cap over the upper half hides the
    # far side as it goes behind
    cap = f"M{cx - rs:g} {cy:g}A{rs:g} {rs:g} 0 0 1 {cx + rs:g} {cy:g}Z"
    svg = (f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{r_out:g}" ry="{r_out * 0.35:g}" fill="url(#bhg)" opacity=".7"/>'
           f'<circle cx="{cx:g}" cy="{cy:g}" r="{rs:g}" fill="{BG}"/>'
           f'<g>{"".join(disk)}</g>'
           f'<path d="{cap}" fill="{BG}"/>'
           f'<g>{"".join(halo)}</g>'
           f'<circle cx="{cx:g}" cy="{cy:g}" r="{rs + 1.5:g}" fill="none" stroke="#fff5df" stroke-opacity=".55" stroke-width="1"/>')
    return "".join(css), svg, glow


# ---------------------------------------------------------------- banner
def banner_art():
    return [r for r in pyfiglet.figlet_format("NotARoomba", font="ansi_shadow", width=300).split("\n") if r.strip()]


def banner(x0, y0, cw, ch, unit, palette="classic"):
    """NotARoomba in ANSI Shadow, drawn as rects in the site's offset retro colors.
    Each layer is shifted further right so the colored edges show, like the site hero."""
    art = banner_art()
    rects = []
    for y, row in enumerate(art):
        for m in re.finditer(r"█+", row):
            rects.append(f'<rect x="{x0 + m.start() * cw:g}" y="{y0 + y * ch:g}" width="{(m.end() - m.start()) * cw + 0.4:g}" height="{ch + 0.4:g}"/>')
    layers = []
    # staggered one way: each color sits one step further right, cream in front
    stack, direction = PALETTES[palette]
    for i, c in enumerate(stack):
        inner = f'<g id="ban">{"".join(rects)}</g>' if i == 0 else '<use href="#ban"/>'
        layers.append(f'<g transform="translate({direction * (len(stack) - 1 - i) * unit:g} 0)" fill="{c}">{inner}</g>')
    css = []
    return "".join(css), "".join(layers), len(art) * ch


def subtitle(cfg, y, palette="classic"):
    """'... a bit of everything' with the same offset effect on 'everything'."""
    fs, w = cfg["sub_font"], cfg["w"]
    lines = (["a full-stack developer / hardware magician who does a bit of "] if cfg["sub_lines"] == 1
             else ["a full-stack developer / hardware magician", "who does a bit of "])
    out = []
    for i, p1 in enumerate(lines):
        yy = y + i * fs * 1.3
        last = i == len(lines) - 1
        total = measure(p1, fs) + (measure("everything", fs) if last else 0)
        sx = (w - total) / 2
        out.append(f'<text x="{sx:.1f}" y="{yy:g}" fill="{SMOKE}" style="font-size:{fs}px">{p1.rstrip()}</text>')
        if last:
            ex = sx + measure(p1, fs)
            if palette == "classic":
                out += [f'<text x="{ex + dx * 1.5:.1f}" y="{yy:g}" fill="{c}" style="font-size:{fs}px">everything</text>' for dx, c in RETRO]
            else:
                stack, direction = PALETTES[palette]
                out += [f'<text x="{ex + (len(stack) - 1) * 1.5 * (direction < 0) + direction * (len(stack) - 1 - i) * 1.5:.1f}" y="{yy:g}" fill="{c}" style="font-size:{fs}px">everything</text>'
                        for i, c in enumerate(stack)]
    return f'<g class="bp">{"".join(out)}</g>', (len(lines) - 1) * fs * 1.3


# ---------------------------------------------------------------- cards
ANIM = re.compile(r"animation:([\w-]+) ([\d.]+)s(?: (-?[\d.]+)s)? ([\w-]+(?:\([^)]*\))?) infinite")


def quantize(svg, fps=None):
    """Snap every animation to a grid of 1/fps: whole-beat durations and delays, and steps()
    so values only change on the beat. Every element then changes at the same instants.
    With LOOP set instead, stretch each duration to LOOP / (whole number) and keep it smooth."""
    fps = FPS if fps is None else fps

    def loop(m):
        dur = float(m.group(2))
        dur = LOOP / max(1, round(LOOP / dur))
        return m.group(0).replace(f" {m.group(2)}s", f" {dur:g}s", 1)

    if LOOP:
        return ANIM.sub(loop, svg)

    def fix(m):
        name, dur, delay = m.group(1), float(m.group(2)), float(m.group(3) or 0)
        n = max(1, round(dur * fps))
        out = f"animation:{name} {n / fps:g}s"
        d = round(delay * fps) / fps
        return out + (f" {d:g}s" if d else "") + f" steps({n}) infinite"
    return ANIM.sub(fix, svg) if fps else svg


def card(w, h, inner, css="", label="", defs="", border=EDGE, font=False):
    return quantize(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
<style>{FONT_FACE if font else ""}text{{font-family:{MONO};font-size:12.5px;white-space:pre}}{color_classes()}{css}
@keyframes blink{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}.cur{{animation:blink 1.1s step-end infinite}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}</style>
<defs><clipPath id="card"><rect width="{w}" height="{h}" rx="18"/></clipPath>{defs}</defs>
<g clip-path="url(#card)"><rect width="{w}" height="{h}" fill="{BG}"/>{inner}</g>
<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="18" fill="none" stroke="{border}" stroke-width="1.5"/>
</svg>''')


def header(cfg, scene, terminal=True, palette="classic"):
    w = cfg["w"]
    cw, ch = cfg["banner_cell"]
    bx = (w - max(len(r) for r in banner_art()) * cw) / 2 - PALETTES[palette][1] * 2 * cw * 0.4
    by = 62 if w > 600 else 52
    bcss, bsvg, bh = banner(bx, by, cw, ch, unit=cw * 0.4, palette=palette)
    sub_y = by + bh + (40 if w > 600 else 32)
    sub, extra = subtitle(cfg, sub_y, palette)
    scene_y = sub_y + extra + 18
    rows = cfg["scene_rows"]
    H = round(scene_y + rows * LINE_H + 6)
    pfs = 16
    if terminal:
        prompt = (f'<g class="bp"><text x="{bx:.1f}" y="{by - 18}" fill="{SMOKE}" style="font-size:{pfs}px">~/notaroomba '
                  f'<tspan fill="{BLUE[500]}">$</tspan> whoami</text>'
                  f'<rect class="cur" x="{bx + measure("~/notaroomba $ whoami ", pfs):.1f}" y="{by - 18 - pfs * 0.72:.1f}" '
                  f'width="{pfs * 0.5:g}" height="{pfs * 0.82:.1f}" fill="{SMOKE}"/></g>')
    else:  # the site hero's greeting instead of a shell prompt
        prompt = f'<g class="bp"><text x="{bx:.1f}" y="{by - 18}" fill="{SMOKE}" style="font-size:{pfs + 2}px">hey there, im</text></g>'
    back, front, scss, defs = "", "", "", ""
    if scene == "waves":
        scss, front = scene_waves(w, rows, scene_y)
    elif scene == "stars":
        scss, back = scene_stars(w, H)
        pcss, front = planet_horizon(w, H, rows)
        scss += pcss
        defs = planet_defs(w, H, rows)
    elif scene == "blackhole":
        scss, back = scene_stars(w, H, density=0.7)
        hcss, front, defs = scene_blackhole(w, rows, scene_y)
        scss += hcss
    return card(w, H, back + prompt + bsvg + sub + front, bcss + scss,
                "hey there, im NotARoomba: a full-stack developer / hardware magician who does a bit of everything", defs, font=True,
                )


def footer(cfg, scene):
    w = cfg["w"]
    rows = 10 if w > 600 else 8
    H = round(rows * LINE_H + 6)
    if scene == "waves":
        css, inner = scene_waves(w, rows, 0, "v", shift=-1.5 if w > 600 else -2.5)
    else:
        css, inner = scene_stars(w, H, "s", seed=21)
    return card(w, H, inner, css, "ascii " + scene)


ABOUT = [
    [("aero/astro and EE @ ", None), ("mit '30", "#ff1423"), (", previously gap year @ ", None), ("hack club", "#ec3750"),
     (".", None)],
    [("im into full-stack development, embedded programming, and ", None), ("hardware design", BLUE[500]), (".", None)],
    [("i am an avid ", None), ("musician/composer", "#f1c40f"), (" and play piano, cello and drums.", None)],
    [("currently learning ", None), ("altium", BLUE[500]), (" + ", None), ("solidworks", BLUE[500]), (".", None)],
]


def wrap_runs(runs, width, fs):
    """Word-wrap colored runs to `width` px, keeping colored phrases whole."""
    lines, cur, n = [], [], 0
    for text, c in runs:
        for p in ([text] if c else [p for p in re.split(r"(?<= )", text) if p]):
            if n + measure(p.rstrip(), fs) > width and cur:
                lines.append(cur)
                cur, n = [], 0
                p = p.lstrip()
            cur.append((p, c))
            n += measure(p, fs)
    lines.append(cur)
    return lines


def about(cfg, terminal=True):
    w, fs = cfg["w"], cfg["about_font"]
    line_h, x0, y0 = fs * 1.4, 28, 46
    body = [[("$ ", BLUE[500]), ("cat about.txt", SMOKE)], []] if terminal else ["heading", []]
    for para in ABOUT:
        body += wrap_runs(para, w - 2 * x0, fs)
    body += [[], [("and here are my other socials:", None)]]
    body += [[], "cursor"] if terminal else []
    H = round(y0 + (len(body) - 1) * line_h + 26)
    out = []
    for i, runs in enumerate(body):
        y = y0 + i * line_h
        if runs == "heading":
            out.append(f'<text x="{x0}" y="{y + 4:g}" style="font-size:{fs * 1.7:g}px" fill="{SMOKE}">about me</text>')
        elif runs == "cursor":
            out.append(f'<text x="{x0}" y="{y:g}" style="font-size:{fs}px" fill="{BLUE[500]}">$</text>'
                       f'<rect class="cur" x="{x0 + measure("$ ", fs):.1f}" y="{y - fs * 0.72:.1f}" width="{fs * 0.5:g}" height="{fs * 0.82:.1f}" fill="{SMOKE}"/>')
        elif isinstance(runs, tuple):
            x = x0
            for key, handle in runs[1]:
                # a plain terminal-style prompt marker instead of brand icons
                # Blender Pro draws '>' as an arrow, so the marker uses the monospace face
                tx = x
                if terminal:
                    out.append(f'<text x="{x}" y="{y:g}" style="font-size:{fs}px;font-family:{MONO}" fill="{BLUE[500]}">&gt;</text>')
                    tx = x + fs * 0.6 + measure(" ", fs) + 2
                out.append(f'<text x="{tx:g}" y="{y:g}" style="font-size:{fs}px"><tspan fill="{SMOKE}">{key}</tspan>'
                           f'<tspan fill="#8b949e"> {esc(handle)}</tspan></text>')
                x = tx + measure(f"{key} {handle}", fs) + 34
        elif runs:
            spans = "".join(
                f'<tspan fill="{c or SMOKE}">{esc(t)}</tspan>'
                for t, c in runs
            )
            out.append(f'<text x="{x0}" y="{y:g}" style="font-size:{fs}px">{spans}</text>')
    return card(w, H, f'<g class="bp">{"".join(out)}</g>', font=True, label="about me: aero/astro and EE @ mit '30, previously gap year @ hack club")


def social_chip(key, handle, terminal=True, mobile=False):
    """One clickable social, a small card that sits under the about card. GitHub can't make
    parts of an image clickable, so each social is its own image wrapped in a link."""
    fs = 22 if mobile else 19
    w, h = (160, 56) if mobile else (229, 48)
    y = h / 2 + fs * 0.35
    parts = []
    text = "website" if key == "site" else key
    isz = fs * 1.05  # brand icon, white like the text
    gap = fs * 0.5
    tw = isz + gap + measure(text, fs)
    x = (w - tw) / 2
    parts.append(f'<g transform="translate({x:.1f} {h / 2 - isz / 2:.1f}) scale({isz / 24:.3f})">'
                 f'{globe_icon(SMOKE) if key == "site" else f"<path fill=\'{SMOKE}\' d=\'{ICONS[key]}\'/>"}</g>')
    x += isz + gap
    handle_span = ""  # names only, so one image reads at desktop and phone widths
    parts.append(f'<text x="{x:.1f}" y="{y:.1f}" style="font-size:{fs}px"><tspan fill="{SMOKE}">{text}</tspan>{handle_span}</text>')
    return card(w, h, f'<g class="bp">{"".join(parts)}</g>', font=True, label=f"{key}: {handle}")


def link_chip(key, handle, pos, n=4, gap=0.06):
    """A chip for the README row: n images at 100/n % each, set with no whitespace between them.
    Each image carries transparent margins so the chips share equal gaps (gap x image width)
    and the outer two sit flush with the cards' edges."""
    chip = re.sub(r' width="[^"]*" height="[^"]*"', "", social_chip(key, handle, terminal=False), count=1)
    cw, h = 229, 48
    W = cw / (1 - gap * (n - 1) / n)
    g = gap * W
    left = pos * (cw + g) - pos * W
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.2f} {h}" width="{W:.2f}" height="{h}" role="img" aria-label="{key}">'
            f'<svg x="{left:.2f}" width="{cw}" height="{h}"{chip[4:]}')


def globe_icon(color=BLUE[500]):
    s = f'stroke="{color}" stroke-width="1.7" fill="none"'
    return (f'<circle cx="12" cy="12" r="10.2" {s}/><ellipse cx="12" cy="12" rx="4.4" ry="10.2" {s}/>'
            f'<path d="M2 12h20M3.5 6.8h17M3.5 17.2h17" {s}/>')


def badge(key, label):
    """A small pill: white icon and label on black with the neutral card border.
    Drawn locally so it needs no shields.io round trip."""
    text = label.upper()
    tw = len(text) * 6.4
    h = 20
    w = 26 + tw + 9
    icon = (globe_icon(SMOKE) if key == "site" else f'<path fill="{SMOKE}" d="{ICONS[key]}"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h}" width="{w:g}" height="{h}" role="img" aria-label="{esc(label)}">
<rect x="0.5" y="0.5" width="{w - 1:g}" height="{h - 1}" rx="4" fill="{BG}" stroke="{EDGE}"/>
<g transform="translate(7 4) scale(0.5)">{icon}</g>
<text x="26" y="13.6" fill="{SMOKE}" font-family="Verdana, DejaVu Sans, sans-serif" font-size="8.5" font-weight="700" textLength="{tw:g}">{esc(text)}</text>
</svg>'''


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)

    def write(name, svg):
        with open(os.path.join(out, name), "w") as fh:
            fh.write(svg)

    for scene in ("waves", "stars", "blackhole"):
        write(f"header-{scene}.svg", header(DESKTOP, scene))
        write(f"header-{scene}-mobile.svg", header(MOBILE, scene))
    for scene in ("waves", "stars"):
        write(f"footer-{scene}.svg", footer(DESKTOP, scene))
        write(f"footer-{scene}-mobile.svg", footer(MOBILE, scene))
    write("about.svg", about(DESKTOP))
    write("about-mobile.svg", about(MOBILE))
    # "plain" variation: same design without the terminal prompt, cursor and markers
    for scene in ("waves", "stars", "blackhole"):
        write(f"header-{scene}-plain.svg", header(DESKTOP, scene, terminal=False))
        write(f"header-{scene}-plain-mobile.svg", header(MOBILE, scene, terminal=False))
        # "athena" color variation of both styles
        for style, term in (("", True), ("-plain", False)):
            write(f"header-{scene}{style}-athena.svg", header(DESKTOP, scene, term, "athena"))
            write(f"header-{scene}{style}-athena-mobile.svg", header(MOBILE, scene, term, "athena"))
    for key, _, handle, _ in SOCIALS:
        if key in ("instagram", "linkedin", "youtube", "site"):
            for style, term in (("", True), ("-plain", False)):
                write(f"social-{key}{style}.svg", social_chip(key, handle, term))
                write(f"social-{key}{style}-mobile.svg", social_chip(key, handle, term, mobile=True))
    for i, key in enumerate(("instagram", "linkedin", "youtube", "site")):
        write(f"link-{key}.svg", link_chip(key, key, i) + "</svg>")
    write("about-plain.svg", about(DESKTOP, terminal=False))
    write("about-plain-mobile.svg", about(MOBILE, terminal=False))
    for key, _, handle, _ in SOCIALS:
        write(f"badge-{key}.svg", badge(key, handle if key == "site" else key))
