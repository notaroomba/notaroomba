"""Pre-render the animated header and footer into looping animated AVIFs.

Frames are free to play back, so these use every black hole particle and smooth motion.
AV1 keeps them near-lossless at a fraction of a WebP's size, with transparent corners.
Needs node with playwright (npm i playwright) and ffmpeg 6.1+ built with libaom.
    cd assets && python3 anim.py [frames-per-second] [loop-seconds] [scale] [crf]
"""
import os
import subprocess
import sys
import tempfile

import gen

FPS = int(sys.argv[1]) if len(sys.argv) > 1 else 24
gen.LOOP = int(sys.argv[2]) if len(sys.argv) > 2 else 10
SCALE = sys.argv[3] if len(sys.argv) > 3 else "1.5"  # pixels per SVG unit, above 1 for sharper text on retina screens
CRF = sys.argv[4] if len(sys.argv) > 4 else "24"  # 0 is lossless; 24 keeps the header under 5 MB and looks the same
gen.DETAIL = True

here = os.path.dirname(os.path.abspath(__file__))
jobs = {
    "header-blackhole": gen.header(gen.DESKTOP, "blackhole", terminal=False),
    "header-blackhole-mobile": gen.header(gen.MOBILE, "blackhole", terminal=False),
    "footer-stars": gen.footer(gen.DESKTOP, "stars"),
    "footer-stars-mobile": gen.footer(gen.MOBILE, "stars"),
}
frames = FPS * gen.LOOP
with tempfile.TemporaryDirectory() as tmp:
    procs = []
    for name, svg in jobs.items():
        path = os.path.join(tmp, name + ".svg")
        open(path, "w").write(svg)
        procs.append(subprocess.Popen(["node", os.path.join(here, "render.js"), path, os.path.join(tmp, name), str(frames), str(FPS), SCALE]))
    for p in procs:
        if p.wait():
            sys.exit("frame render failed")
    for name in jobs:
        # color and alpha go in as two streams, which ffmpeg muxes into one AVIF with transparency
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, name, "%05d.png"),
                        "-filter_complex", "[0:v]format=rgba,split[c][a];[c]format=yuv444p[cc];[a]alphaextract,format=gray[aa]",
                        "-map", "[cc]", "-map", "[aa]", "-c:v", "libaom-av1", "-crf", CRF, "-cpu-used", "8", "-row-mt", "1",
                        os.path.join(here, name + ".avif")], check=True)
        print(name + ".avif", os.path.getsize(os.path.join(here, name + ".avif")))
