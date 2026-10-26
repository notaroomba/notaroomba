// node render.js <svg> <outdir> <frames> <fps> <scale> [first]: screenshots each frame of an SVG with its CSS animations paused at that time
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [svg, out, n, fps, scale, s0] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const src = fs.readFileSync(svg, 'utf8');
  const m = src.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  const W = Math.ceil(+m[1]), H = Math.ceil(+m[2]);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: +scale });
  await p.goto('file://' + path.resolve(svg));
  await p.waitForTimeout(500);
  await p.evaluate(() => document.getAnimations().forEach(a => a.pause()));
  for (let i = +(s0 || 0); i < +n; i++) {
    await p.evaluate(t => document.getAnimations().forEach(a => { a.currentTime = t; }), i * 1000 / +fps);
    await p.screenshot({ path: path.join(out, String(i).padStart(5, '0') + '.png'), omitBackground: true });
  }
  await b.close();
})();
