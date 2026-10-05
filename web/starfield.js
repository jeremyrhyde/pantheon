/* Starfield background shared by the home and status screens.
 *
 * Three parallax layers drift slowly left, a few stars twinkle, and a faint
 * shooting star crosses now and then. Capped at ~30 fps; a single static
 * frame under prefers-reduced-motion. Colours come from the --color-star*
 * tokens. Usage: startStarfield(canvasElement, { dim: 0..1, speed: 0..1 }).
 */
function startStarfield(canvas, { dim = 1, speed = 1 } = {}) {
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext('2d');
  const css = getComputedStyle(document.documentElement);
  const palette = ['--color-star', '--color-star', '--color-star-cool', '--color-star-warm']
    .map((name) => css.getPropertyValue(name).trim() || 'white');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // density = stars per square pixel
  const LAYERS = [
    { density: 0.00012, size: [0.4, 0.9], speed: 0.6, alpha: 0.45 },
    { density: 0.00006, size: [0.7, 1.3], speed: 1.4, alpha: 0.7 },
    { density: 0.00002, size: [1.1, 1.9], speed: 2.6, alpha: 0.95 },
  ];
  const FRAME_MS = 33;
  let stars = [];
  let shooting = null;
  let width = 0;
  let height = 0;
  let last = 0;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = LAYERS.flatMap((layer) =>
      Array.from({ length: Math.round(width * height * layer.density) }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: layer.size[0] + Math.random() * (layer.size[1] - layer.size[0]),
        v: layer.speed * speed,
        a: layer.alpha * dim,
        twinkle: Math.random() < 0.08 ? Math.random() * Math.PI * 2 : null,
        color: palette[Math.floor(Math.random() * palette.length)],
      })));
    draw(0);
  }

  function draw(t) {
    ctx.clearRect(0, 0, width, height);
    for (const s of stars) {
      ctx.globalAlpha = s.twinkle === null ? s.a : s.a * (0.55 + 0.45 * Math.sin(t / 700 + s.twinkle));
      ctx.fillStyle = s.color;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    if (shooting) {
      const len = Math.hypot(shooting.vx, shooting.vy);
      const tx = shooting.x - (shooting.vx / len) * 90;
      const ty = shooting.y - (shooting.vy / len) * 90;
      const gradient = ctx.createLinearGradient(shooting.x, shooting.y, tx, ty);
      gradient.addColorStop(0, palette[0]);
      gradient.addColorStop(1, 'transparent');
      ctx.globalAlpha = Math.max(0, shooting.life) * 0.8 * dim;
      ctx.strokeStyle = gradient;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(shooting.x, shooting.y);
      ctx.lineTo(tx, ty);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function step(t) {
    requestAnimationFrame(step);
    if (t - last < FRAME_MS) return;
    const dt = (t - last) / 1000;
    last = t;
    if (dt > 1) return; // first frame, or the tab was hidden
    for (const s of stars) {
      s.x -= s.v * dt * 4;
      if (s.x < -2) { s.x = width + 2; s.y = Math.random() * height; }
    }
    if (!shooting && Math.random() < 0.0015 * speed) {
      shooting = { x: width * (0.2 + Math.random() * 0.8), y: Math.random() * height * 0.4,
                   vx: -width * 0.6, vy: height * 0.25, life: 1 };
    }
    if (shooting) {
      shooting.x += shooting.vx * dt;
      shooting.y += shooting.vy * dt;
      shooting.life -= dt * 1.2;
      if (shooting.life <= 0) shooting = null;
    }
    draw(t);
  }

  window.addEventListener('resize', resize);
  resize();
  if (!reduced) requestAnimationFrame(step);
}
