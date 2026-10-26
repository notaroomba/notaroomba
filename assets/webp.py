"""Pre-render the animated header and footer into looping WebPs.

Frames are free to play back, so these use every black hole particle and smooth motion.
Needs node with playwright (npm i playwright) and ffmpeg built with libwebp.
    cd assets && python3 webp.py [frames-per-second] [loop-seconds]
"""
import os
import subprocess
import sys
import tempfile

import gen

FPS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
gen.LOOP = int(sys.argv[2]) if len(sys.argv) > 2 else 10
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
        procs.append(subprocess.Popen(["node", os.path.join(here, "render.js"), path, os.path.join(tmp, name), str(frames), str(FPS), "1"]))
    for p in procs:
        if p.wait():
            sys.exit("frame render failed")
    for name in jobs:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, name, "%05d.png"),
                        "-c:v", "libwebp_anim", "-q:v", "60", "-compression_level", "4", "-loop", "0",
                        os.path.join(here, name + ".webp")], check=True)
        print(name + ".webp", os.path.getsize(os.path.join(here, name + ".webp")))
