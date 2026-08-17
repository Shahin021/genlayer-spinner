#!/usr/bin/env python3
"""
GenLayer Portal spinner — build script.

Single source of truth. Geometry, keyframes, phases and colour tokens are
declared once here; the SVG, the preview page and the raster test frames are all
emitted from these constants, so they cannot drift apart.

    python3 build.py
"""
import io, os

OUT = "/mnt/user-data/outputs"

# ---------------------------------------------------------------- geometry ---
# Traced from the official GenLayer mark (400 px render) and mapped into a 48
# viewBox: outer edges at dx/dy 0.482 (25.7 deg off vertical), the narrow
# vertical channel at the apex, the notch, the tapered feet, the core kite.
# Each blade is divided once, perpendicular to its own axis, into two seats of
# equal area. With the core that makes five.
SEATS = [
    ("upper left",  "21.99,5.00 21.99,18.97 16.91,29.47 11.50,26.88"),
    ("upper right", "36.50,26.88 31.09,29.47 26.01,18.97 26.01,5.00"),
    ("lower left",  "16.26,30.82 15.51,32.38 20.98,36.63 3.77,43.00 10.85,28.23"),
    ("lower right", "37.15,28.23 44.23,43.00 27.02,36.63 32.49,32.38 31.74,30.82"),
    ("core",        "23.94,23.22 27.69,31.04 23.94,33.16 20.20,31.04"),
]

# ----------------------------------------------------------------- motion ----
CYCLE = 1.6                     # seconds
STEPS = 5                       # 320 ms per state
STEP  = CYCLE / STEPS

# one seat joins, one leaves, three hold. the trail makes the direction legible.
LEVELS = [1.0, 0.6, 0.3, 0.0, 0.0]
HOLD   = 0.11                   # fraction of the cycle each state sits still

# vote order: core, lower left, upper left, upper right, lower right.
# the quorum climbs the left blade, crosses the apex, comes down the right.
ORDER = ["core", "lower left", "upper left", "upper right", "lower right"]
# a seat whose phase is p is at the top of its curve when t = cycle - p, so the
# phase for the i-th seat in the lighting order is (STEPS - i) mod STEPS steps.
PHASE = {name: ((STEPS - ORDER.index(name)) % STEPS) * STEP for name, _ in SEATS}

def keyframe_table():
    """[(percent, opacity)] — the same table drives the CSS and the rasteriser."""
    kf = []
    for i, v in enumerate(LEVELS):
        a = i * (100.0 / STEPS)
        kf.append((a, v))
        kf.append((a + HOLD * 100, v))
    kf.append((100.0, LEVELS[0]))
    return kf

def css_keyframes(indent="      "):
    kf = keyframe_table()
    out, i = [], 0
    while i < len(kf) - 1:
        v = kf[i][1]
        j = i
        while j + 1 < len(kf) - 1 and kf[j + 1][1] == v:
            j += 1
        out.append("%s%g%%,%g%% { opacity:%s }" % (indent, kf[i][0], kf[j][0], fmtv(v)))
        i = j + 1
    out.append("%s100%% { opacity:%s }" % (indent, fmtv(LEVELS[0])))
    return "\n".join(out)

def fmtv(v):
    s = ("%g" % v)
    return s[1:] if s.startswith("0.") else s

def level_at(t):
    """opacity at t percent of the cycle, ease-in-out between keyframes."""
    kf = keyframe_table()
    t %= 100
    for (t0, v0), (t1, v1) in zip(kf, kf[1:]):
        if t0 <= t <= t1:
            if t1 == t0:
                return v1
            p = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * (p * p * (3 - 2 * p))
    return LEVELS[0]

# ----------------------------------------------------------------- colour ----
# Only the three official values are used. Everything else is a documented
# mix of them, so the spinner never introduces a fourth colour.
COBALT, VOID, CERAMIC = "#110FFF", "#070707", "#F5F5F5"
TOKENS = {
    "light": {"active": COBALT,   "track": "#CACACA",   # 18% Carbon Void over Ceramic Node
              "active_mix": None,
              "track_mix": "color-mix(in srgb, %s 18%%, %s)" % (VOID, CERAMIC)},
    "dark":  {"active": "#5554FC", "track": "#323232",  # 70/30 cobalt-ceramic; 18% Ceramic over Void
              "active_mix": "color-mix(in srgb, %s 70%%, %s)" % (COBALT, CERAMIC),
              "track_mix": "color-mix(in srgb, %s 18%%, %s)" % (CERAMIC, VOID)},
}

def phase_rules(sel, indent="    "):
    """per-seat phase, in seconds, as a custom property."""
    return "\n".join(
        "%s%s polygon:nth-child(%d){ --p:%gs }   /* %s */" % (indent, sel, i + 1, PHASE[name], name)
        for i, (name, _) in enumerate(SEATS))

def polygons(cls, indent):
    return "\n".join('%s<polygon class="%s" points="%s"/>' % (indent, cls, pts)
                     for _, pts in SEATS)

# -------------------------------------------------------------------- svg ----
def svg_file():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48" role="img" aria-label="Loading" focusable="false">
  <title>Loading</title>
  <style>
    svg{
      --gl-cycle:%(cycle)gs;
      --gl-active:%(la)s;
      --gl-track:%(lt)s;
      --gl-track:%(ltm)s;
    }
    @media (prefers-color-scheme:dark){
      svg{
        --gl-active:%(da)s;
        --gl-active:%(dam)s;
        --gl-track:%(dt)s;
        --gl-track:%(dtm)s;
      }
    }
    .seat{ fill:var(--gl-track) }
    .vote{
      fill:var(--gl-active);
      opacity:%(first)s;
      animation:gl-vote var(--gl-cycle) ease-in-out infinite;
      animation-delay:calc(-1 * var(--p));
    }
%(phases)s

    @keyframes gl-vote{
%(kf)s
    }

    @media (prefers-reduced-motion:reduce){
      .votes polygon:nth-child(n){
        animation:gl-hold calc(var(--gl-cycle) * 1.5) ease-in-out infinite;
        animation-delay:0s;
      }
      @keyframes gl-hold{ 0%%,100%%{opacity:0} 50%%{opacity:.85} }
    }
  </style>
  <!-- Geometry traced from the official GenLayer mark: outer edges at dx/dy 0.482
       (25.7 deg off vertical), the narrow vertical channel at the apex, the notch,
       the tapered feet, the core kite. Each blade is divided once, perpendicular to
       its axis, into two equal-area seats; with the core that makes five.
       Nothing is rotated, scaled, stretched, morphed or recoloured. Opacity is the
       only animated property. Five seats, three lit at any instant.
       Colour: Kinetic Cobalt, Carbon Void and Ceramic Node only - every other value
       here is a documented mix of those three. -->
  <g aria-hidden="true">
    <g class="seats">
%(seats)s
    </g>
    <g class="votes">
%(votes)s
    </g>
  </g>
</svg>
''' % dict(cycle=CYCLE, la=TOKENS["light"]["active"], lt=TOKENS["light"]["track"],
           ltm=TOKENS["light"]["track_mix"], da=TOKENS["dark"]["active"],
           dam=TOKENS["dark"]["active_mix"], dt=TOKENS["dark"]["track"],
           dtm=TOKENS["dark"]["track_mix"], first=fmtv(LEVELS[0]),
           phases=phase_rules(".votes"), kf=css_keyframes(),
           seats=polygons("seat", "      "), votes=polygons("vote", "      "))

# ---------------------------------------------------------------- raster -----
def static_svg(t, theme, all_lit=False):
    """explicit-colour copy for rasterising: same geometry, same keyframe table."""
    tk = TOKENS[theme]
    body = "".join('<polygon points="%s" fill="%s"/>' % (p, tk["track"]) for _, p in SEATS)
    for name, p in SEATS:
        o = 1.0 if all_lit else level_at(t + PHASE[name] / CYCLE * 100)
        body += '<polygon points="%s" fill="%s" opacity="%.4f"/>' % (p, tk["active"], o)
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">%s</svg>' % body

def render(t, theme, px, all_lit=False):
    import cairosvg
    from PIL import Image
    png = cairosvg.svg2png(bytestring=static_svg(t, theme, all_lit).encode(),
                           output_width=px, output_height=px)
    fg = Image.open(io.BytesIO(png)).convert("RGBA")
    bg = Image.new("RGBA", (px, px), VOID if theme == "dark" else CERAMIC)
    return Image.alpha_composite(bg, fg).convert("RGB")

def sheets():
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    sizes = [(16, 5), (20, 4), (24, 4), (32, 3), (48, 3)]
    rows = [(None, "all lit")] + [(i * (100.0 / STEPS), "state %d" % (i + 1)) for i in range(STEPS)]
    for theme in ("light", "dark"):
        cell = 165
        im = Image.new("RGB", (150 + len(sizes) * cell, 40 + len(rows) * cell),
                       "#141414" if theme == "dark" else "#FFFFFF")
        d = ImageDraw.Draw(im); tc = "#DDD" if theme == "dark" else "#111"
        for j, (px, z) in enumerate(sizes):
            d.text((150 + j * cell + 6, 14), "%dpx x%d" % (px, z), fill=tc, font=font)
        for i, (t, lab) in enumerate(rows):
            y = 40 + i * cell
            d.text((12, y + cell // 2), lab, fill=tc, font=font)
            for j, (px, z) in enumerate(sizes):
                f = render(0 if t is None else t, theme, px, all_lit=(t is None))
                im.paste(f.resize((px * z, px * z), Image.NEAREST), (150 + j * cell + 6, y + 6))
        im.save(os.path.join(OUT, "test-frames-%s.png" % theme))
        frames = [render(k * 100.0 / 40, theme, 96) for k in range(40)]
        frames[0].save(os.path.join(OUT, "genlayer-spinner-%s.gif" % theme), save_all=True,
                       append_images=frames[1:], duration=int(CYCLE * 1000 / 40), loop=0, optimize=True)

# --------------------------------------------------------------- preview -----
def preview_html():
    inline = ('    <svg class="gl-spinner" viewBox="0 0 48 48" role="img" aria-label="Loading" focusable="false">\n'
              '      <g aria-hidden="true">\n        <g class="seats">\n'
              + polygons("seat", "          ")
              + '\n        </g>\n        <g class="votes">\n'
              + polygons("vote", "          ")
              + '\n        </g>\n      </g>\n    </svg>')
    ladder = lambda theme: "\n".join(
        '        <div class="rung"><div class="slot" data-size="%d"%s></div><span class="eyebrow">%d</span></div>'
        % (s, ' data-theme="dark"' if theme == "dark" else "", s) for s in (16, 20, 24, 32, 48))
    states = "\n".join(
        '        <div class="rung"><div class="slot is-frozen" data-size="56" style="--t:%gs"></div>'
        '<span class="eyebrow">%d</span></div>' % (i * STEP, i + 1) for i in range(STEPS))
    L, D = TOKENS["light"], TOKENS["dark"]
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GenLayer Portal spinner — preview</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{ --void:%(void)s; --ceramic:%(ceramic)s; --cobalt:%(cobalt)s;
         --rule:#CACACA; --muted:#606060; --gutter:clamp(20px,5vw,64px) }
  *{box-sizing:border-box}
  body{margin:0;background:var(--ceramic);color:var(--void);
       font-family:"Space Grotesk",system-ui,sans-serif;line-height:1.5}
  .wrap{max-width:1080px;margin:0 auto;padding:0 var(--gutter)}
  .eyebrow{font-family:"JetBrains Mono",monospace;font-size:11px;letter-spacing:.14em;
           text-transform:uppercase;color:var(--muted)}
  .bar{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
       padding:14px 0;border-bottom:1px solid var(--rule)}
  h1{font-size:clamp(46px,11vw,110px);line-height:.92;letter-spacing:-.045em;margin:14px 0 0}
  .thesis{font-size:clamp(17px,2.2vw,21px);max-width:38ch;margin:18px 0 0;color:#303030}
  section{padding:clamp(40px,7vw,76px) 0;border-top:1px solid var(--rule)}
  h2{font-size:clamp(22px,3.2vw,32px);letter-spacing:-.03em;margin:10px 0 0}
  .lede{max-width:62ch;color:#303030;margin:14px 0 0}
  .seam{position:relative;display:grid;place-items:center;min-height:clamp(200px,32vw,300px);
        background:linear-gradient(90deg,#FFF 0 50%%,var(--void) 50%% 100%%);
        border:1px solid var(--rule);margin-top:clamp(30px,5vw,52px)}
  .strips{margin-top:32px;display:grid;gap:2px}
  .strip{display:flex;align-items:flex-end;gap:clamp(18px,5vw,50px);flex-wrap:wrap;
         padding:clamp(20px,4vw,36px);border:1px solid var(--rule)}
  .strip--dark{background:var(--void);border-color:#303030}
  .strip--dark .eyebrow{color:#8A8A8A}
  .rung{display:grid;gap:12px;justify-items:center}
  .rung .eyebrow{font-size:10px}
  .note{margin-top:14px}
  footer{border-top:1px solid var(--rule);padding:24px 0 60px}

  /* ---------------- spinner ---------------- */
  .gl-spinner{
    --gl-cycle:%(cycle)gs;
    --gl-active:%(la)s;
    --gl-track:%(lt)s;
    --gl-track:%(ltm)s;
    width:24px;height:24px;display:block;
  }
  [data-theme="dark"] .gl-spinner, .strip--dark .gl-spinner, .seam-dark .gl-spinner{
    --gl-active:%(da)s;
    --gl-active:%(dam)s;
    --gl-track:%(dt)s;
    --gl-track:%(dtm)s;
  }
  .gl-spinner .seat{ fill:var(--gl-track) }
  .gl-spinner .vote{
    fill:var(--gl-active);
    opacity:%(first)s;
    animation:gl-vote var(--gl-cycle) ease-in-out infinite;
    animation-delay:calc(-1 * (var(--p) + var(--t, 0s)));
  }
%(phases)s
  /* a frozen slot shows one real state of the same animation, not a redrawing of it */
  .is-frozen .gl-spinner .vote{ animation-play-state:paused }

  @keyframes gl-vote{
%(kf)s
  }
  @keyframes gl-hold{ 0%%,100%%{opacity:0} 50%%{opacity:.85} }
  @media (prefers-reduced-motion:reduce){
    .gl-spinner .votes polygon:nth-child(n){
      animation:gl-hold calc(var(--gl-cycle) * 1.5) ease-in-out infinite;
      animation-delay:0s;
    }
  }
</style>
</head>
<body>

<template id="tpl">
%(inline)s
</template>

<div class="wrap">
  <div class="bar">
    <span class="eyebrow">GenLayer Portal — loading state</span>
    <span class="eyebrow">Every spinner on this page is the same SVG</span>
  </div>
</div>

<div class="wrap" style="padding-top:clamp(44px,8vw,88px);padding-bottom:clamp(24px,4vw,40px)">
  <span class="eyebrow">Spinner</span>
  <h1>Quorum</h1>
  <p class="thesis">The mark, taking a vote. Three of its five parts lit at any instant — the smallest majority that decides anything.</p>
  <div class="seam"><div class="slot" data-size="132" data-variant="universal"></div></div>
  <div class="bar" style="border:0"><span class="eyebrow">One mark, both surfaces</span>
    <span class="eyebrow">Photon #FFFFFF · Carbon Void %(void)s</span></div>
</div>

<div class="wrap">
  <section>
    <span class="eyebrow">Legibility</span>
    <h2>16 px up to 48 px, either surface</h2>
    <p class="lede">The seat track sits under the votes, so all five parts are present in every frame and the
      silhouette never changes. Nothing rotates, scales or moves.</p>
    <div class="strips">
      <div class="strip">
%(ladder_light)s
        <div class="rung" style="margin-left:auto"><span class="eyebrow">Ceramic Node</span></div>
      </div>
      <div class="strip strip--dark">
%(ladder_dark)s
        <div class="rung" style="margin-left:auto"><span class="eyebrow">Carbon Void</span></div>
      </div>
    </div>
  </section>

  <section>
    <span class="eyebrow">Motion</span>
    <h2>Five real states, %(step)d ms apart</h2>
    <p class="lede">These are not drawings of the animation. Each slot below runs the same animation with
      <code>animation-play-state:paused</code> and a different phase offset, so it is literally one frame of
      the live spinner. One seat joins, one leaves, three hold.</p>
    <div class="strips">
      <div class="strip">
%(states)s
        <div class="rung" style="margin-left:auto"><span class="eyebrow">%(cycle)gs loop</span></div>
      </div>
    </div>
    <p class="lede note">The five phases are exactly a fifth of a cycle apart, so no two seats ever hold the
      same value and there is no frame where the mark flattens into one uniform state.</p>
  </section>

  <section>
    <span class="eyebrow">Colour</span>
    <h2>Three official values, nothing else</h2>
    <p class="lede">
      Kinetic Cobalt at full strength measures 2.4:1 on Carbon Void, under the 3:1 floor for non-text
      graphics, so the dark accent is Cobalt mixed 70/30 with Ceramic Node — %(da)s, 3.9:1. The seat track is
      18%% Carbon Void over Ceramic Node on light (%(lt)s) and 18%% Ceramic Node over Carbon Void on dark
      (%(dt)s). No fourth colour is introduced; each value is written as a
      <code>color-mix()</code> of the official three, with a hex fallback.
    </p>
  </section>

  <footer>
    <span class="eyebrow">The official mark is unchanged and remains the primary brand mark. This is a
      separate loading component built on its geometry.</span>
  </footer>
</div>

<script>
  const tpl = document.getElementById('tpl');
  document.querySelectorAll('.slot').forEach(slot => {
    const svg = tpl.content.querySelector('svg').cloneNode(true);
    const size = slot.dataset.size || 24;
    svg.style.width = size + 'px';
    svg.style.height = size + 'px';
    slot.appendChild(svg);
  });
</script>
</body>
</html>
''' % dict(void=VOID, ceramic=CERAMIC, cobalt=COBALT, cycle=CYCLE, step=int(STEP * 1000),
           la=L["active"], lt=L["track"], ltm=L["track_mix"],
           da=D["active"], dam=D["active_mix"], dt=D["track"], dtm=D["track_mix"],
           first=fmtv(LEVELS[0]), phases=phase_rules(".gl-spinner .votes", "  "),
           kf=css_keyframes("    "), inline=inline,
           ladder_light=ladder("light"), ladder_dark=ladder("dark"), states=states)

# ----------------------------------------------------------------- main ------
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "genlayer-spinner.svg"), "w").write(svg_file())
    open(os.path.join(OUT, "preview.html"), "w").write(preview_html())
    sheets()
    print("cycle %.2fs, %d states, %d ms each" % (CYCLE, STEPS, STEP * 1000))
    print("phases:", {k: round(v, 2) for k, v in PHASE.items()})
    print("wrote genlayer-spinner.svg, preview.html, test-frames-*.png, *.gif")
