"""Canvas 2D hero animations — one per organ, all vanilla JS.

Each function returns a JS string that initializes a Canvas 2D animation
on the element with id="hero-canvas". All animations:
- Use requestAnimationFrame
- Respect prefers-reduced-motion (static fallback)
- Are self-contained (no external deps)
- Use the organ's accent color via CSS custom property
"""

from __future__ import annotations


def generate_hero_canvas(organ_key: str) -> str:
    """Return JS code for an organ-specific Canvas 2D hero animation.

    Args:
        organ_key: Registry organ key (e.g., "ORGAN-I", "META-ORGANVM").

    Returns:
        JavaScript string to embed in a <script> tag.
    """
    generators = {
        "ORGAN-I": _organ_i_graph_nodes,
        "ORGAN-II": _organ_ii_particles,
        "ORGAN-III": _organ_iii_bars,
        "ORGAN-IV": _organ_iv_state_machine,
        "ORGAN-V": _organ_v_typewriter,
        "ORGAN-VI": _organ_vi_orbits,
        "ORGAN-VII": _organ_vii_broadcast,
        "META-ORGANVM": _organ_meta_network,
        "PERSONAL": _organ_meta_network,
    }
    generator = generators.get(organ_key, _default_animation)
    return generator()


def _reduced_motion_guard() -> str:
    """Return JS guard that skips animation if user prefers reduced motion."""
    return """\
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (prefersReduced) { return; }"""


def _canvas_setup() -> str:
    """Return JS for standard canvas setup."""
    return """\
const canvas = document.getElementById('hero-canvas');
if (!canvas) return;
const ctx = canvas.getContext('2d');
const dpr = window.devicePixelRatio || 1;
function resize() {
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = canvas.offsetHeight * dpr;
  ctx.scale(dpr, dpr);
}
resize();
window.addEventListener('resize', resize);
const W = () => canvas.offsetWidth;
const H = () => canvas.offsetHeight;
const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();"""


def _default_animation() -> str:
    """Gentle floating dots — used when no organ-specific animation exists."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const dots = Array.from({{length: 40}}, () => ({{
    x: Math.random() * W(), y: Math.random() * H(),
    vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 2 + 1
  }}));
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    dots.forEach(d => {{
      d.x += d.vx; d.y += d.vy;
      if (d.x < 0 || d.x > W()) d.vx *= -1;
      if (d.y < 0 || d.y > H()) d.vy *= -1;
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fillStyle = accent + '40';
      ctx.fill();
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_i_graph_nodes() -> str:
    """Pulsing graph nodes with glowing edges."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const nodes = Array.from({{length: 12}}, (_, i) => ({{
    x: W() * 0.15 + Math.random() * W() * 0.7,
    y: H() * 0.15 + Math.random() * H() * 0.7,
    r: 3 + Math.random() * 4, phase: Math.random() * Math.PI * 2
  }}));
  const edges = [];
  for (let i = 0; i < nodes.length; i++)
    for (let j = i + 1; j < nodes.length; j++) {{
      const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
      if (Math.sqrt(dx*dx + dy*dy) < W() * 0.3) edges.push([i, j]);
    }}
  let t = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    t += 0.01;
    edges.forEach(([a, b]) => {{
      ctx.beginPath();
      ctx.moveTo(nodes[a].x, nodes[a].y);
      ctx.lineTo(nodes[b].x, nodes[b].y);
      ctx.strokeStyle = accent + '18';
      ctx.lineWidth = 1;
      ctx.stroke();
    }});
    nodes.forEach(n => {{
      const pulse = 1 + Math.sin(t * 2 + n.phase) * 0.3;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r * pulse, 0, Math.PI * 2);
      ctx.fillStyle = accent + '50';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r * pulse * 2, 0, Math.PI * 2);
      ctx.fillStyle = accent + '10';
      ctx.fill();
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_ii_particles() -> str:
    """Flowing particle system with color gradients."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const particles = Array.from({{length: 60}}, () => ({{
    x: Math.random() * W(), y: Math.random() * H(),
    vx: (Math.random() - 0.5) * 0.8, vy: -0.2 - Math.random() * 0.5,
    life: Math.random(), decay: 0.001 + Math.random() * 0.002,
    r: 1 + Math.random() * 3
  }}));
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    particles.forEach(p => {{
      p.x += p.vx; p.y += p.vy; p.life -= p.decay;
      if (p.life <= 0 || p.y < 0) {{
        p.x = Math.random() * W(); p.y = H() + 10;
        p.life = 1; p.vx = (Math.random() - 0.5) * 0.8;
      }}
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = accent + Math.floor(p.life * 80).toString(16).padStart(2, '0');
      ctx.fill();
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_iii_bars() -> str:
    """Rising bar chart / dashboard gauges."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const bars = Array.from({{length: 8}}, (_, i) => ({{
    target: 0.3 + Math.random() * 0.6, current: 0, x: 0
  }}));
  let t = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    t += 0.005;
    const bw = W() / (bars.length * 2 + 1);
    bars.forEach((b, i) => {{
      b.x = bw + i * bw * 2;
      const wave = b.target + Math.sin(t + i * 0.5) * 0.05;
      b.current += (wave - b.current) * 0.02;
      const h = b.current * H() * 0.5;
      const y = H() * 0.8 - h;
      ctx.fillStyle = accent + '30';
      ctx.fillRect(b.x, y, bw, h);
      ctx.fillStyle = accent + '60';
      ctx.fillRect(b.x, y, bw, 3);
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_iv_state_machine() -> str:
    """Connected state machine nodes with flowing transitions."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const states = [
    {{label: 'INIT', x: 0.2, y: 0.3}},
    {{label: 'READY', x: 0.4, y: 0.5}},
    {{label: 'RUN', x: 0.6, y: 0.3}},
    {{label: 'DONE', x: 0.8, y: 0.5}}
  ];
  const transitions = [[0,1],[1,2],[2,3],[3,1]];
  let activeEdge = 0, progress = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    progress += 0.008;
    if (progress > 1) {{ progress = 0; activeEdge = (activeEdge + 1) % transitions.length; }}
    transitions.forEach(([a, b], idx) => {{
      const ax = states[a].x * W(), ay = states[a].y * H();
      const bx = states[b].x * W(), by = states[b].y * H();
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by);
      ctx.strokeStyle = idx === activeEdge ? accent + '50' : accent + '15';
      ctx.lineWidth = idx === activeEdge ? 2 : 1; ctx.stroke();
      if (idx === activeEdge) {{
        const px = ax + (bx - ax) * progress, py = ay + (by - ay) * progress;
        ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fillStyle = accent; ctx.fill();
      }}
    }});
    states.forEach(s => {{
      const sx = s.x * W(), sy = s.y * H();
      ctx.beginPath(); ctx.arc(sx, sy, 20, 0, Math.PI * 2);
      ctx.strokeStyle = accent + '40'; ctx.lineWidth = 1.5; ctx.stroke();
      ctx.fillStyle = accent + '08'; ctx.fill();
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_v_typewriter() -> str:
    """Typewriter text effect with glowing cursor."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const phrases = ['logos', 'discourse', 'essay', 'truth', 'public'];
  let phraseIdx = 0, charIdx = 0, deleting = false, pause = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    if (pause > 0) {{ pause--; requestAnimationFrame(draw); return; }}
    const word = phrases[phraseIdx];
    if (!deleting) {{
      charIdx++;
      if (charIdx > word.length) {{ pause = 120; deleting = true; }}
    }} else {{
      charIdx--;
      if (charIdx < 0) {{ charIdx = 0; deleting = false; phraseIdx = (phraseIdx + 1) % phrases.length; pause = 30; }}
    }}
    const text = word.substring(0, charIdx);
    ctx.font = '24px Georgia, serif';
    ctx.fillStyle = accent + '30';
    ctx.textAlign = 'center';
    ctx.fillText(text, W() / 2, H() / 2);
    if (Math.floor(Date.now() / 500) % 2 === 0) {{
      const tw = ctx.measureText(text).width;
      ctx.fillStyle = accent + '50';
      ctx.fillRect(W() / 2 + tw / 2 + 2, H() / 2 - 18, 2, 22);
    }}
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_vi_orbits() -> str:
    """Orbiting circle network."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const orbiters = Array.from({{length: 8}}, (_, i) => ({{
    angle: (i / 8) * Math.PI * 2, radius: 60 + Math.random() * 40,
    speed: 0.003 + Math.random() * 0.004, r: 3 + Math.random() * 3
  }}));
  let t = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    t += 1;
    const cx = W() / 2, cy = H() / 2;
    ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2);
    ctx.fillStyle = accent + '40'; ctx.fill();
    orbiters.forEach(o => {{
      o.angle += o.speed;
      const x = cx + Math.cos(o.angle) * o.radius;
      const y = cy + Math.sin(o.angle) * o.radius;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y);
      ctx.strokeStyle = accent + '12'; ctx.lineWidth = 1; ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, o.r, 0, Math.PI * 2);
      ctx.fillStyle = accent + '40'; ctx.fill();
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_vii_broadcast() -> str:
    """Signal wave / broadcast ripple."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const ripples = [];
  let t = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    t++;
    if (t % 60 === 0) ripples.push({{ r: 0, alpha: 0.5 }});
    const cx = W() / 2, cy = H() / 2;
    ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = accent + '60'; ctx.fill();
    for (let i = ripples.length - 1; i >= 0; i--) {{
      const rip = ripples[i];
      rip.r += 0.8; rip.alpha -= 0.003;
      if (rip.alpha <= 0) {{ ripples.splice(i, 1); continue; }}
      ctx.beginPath(); ctx.arc(cx, cy, rip.r, 0, Math.PI * 2);
      ctx.strokeStyle = accent + Math.floor(rip.alpha * 255).toString(16).padStart(2, '0');
      ctx.lineWidth = 1.5; ctx.stroke();
    }}
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""


def _organ_meta_network() -> str:
    """Eight interconnected organ nodes forming the system map."""
    return f"""\
(function() {{
  {_reduced_motion_guard()}
  {_canvas_setup()}
  const organs = [
    {{label: 'I', angle: 0}}, {{label: 'II', angle: Math.PI/4}},
    {{label: 'III', angle: Math.PI/2}}, {{label: 'IV', angle: 3*Math.PI/4}},
    {{label: 'V', angle: Math.PI}}, {{label: 'VI', angle: 5*Math.PI/4}},
    {{label: 'VII', angle: 3*Math.PI/2}}, {{label: 'M', angle: 7*Math.PI/4}}
  ];
  const edges = [[0,1],[1,2],[0,7],[3,0],[3,1],[3,2],[7,0],[7,1],[7,2],[7,3]];
  let t = 0;
  function draw() {{
    ctx.clearRect(0, 0, W(), H());
    t += 0.005;
    const cx = W() / 2, cy = H() / 2, rad = Math.min(W(), H()) * 0.25;
    organs.forEach((o, i) => {{
      o.x = cx + Math.cos(o.angle + t * 0.1) * rad;
      o.y = cy + Math.sin(o.angle + t * 0.1) * rad;
    }});
    edges.forEach(([a, b]) => {{
      ctx.beginPath(); ctx.moveTo(organs[a].x, organs[a].y);
      ctx.lineTo(organs[b].x, organs[b].y);
      ctx.strokeStyle = accent + '15'; ctx.lineWidth = 1; ctx.stroke();
    }});
    organs.forEach(o => {{
      ctx.beginPath(); ctx.arc(o.x, o.y, 8, 0, Math.PI * 2);
      ctx.fillStyle = accent + '25'; ctx.fill();
      ctx.strokeStyle = accent + '50'; ctx.lineWidth = 1; ctx.stroke();
    }});
    requestAnimationFrame(draw);
  }}
  draw();
}})();"""
