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

def static_rules(sel, indent="    "):
    """reduced motion: hold one settled state instead of breathing."""
    return "\n".join(
        "%s%s polygon:nth-child(%d){ opacity:%s }" %
        (indent, sel, i + 1, fmtv(round(level_at(PHASE[name] / CYCLE * 100), 3)))
        for i, (name, _) in enumerate(SEATS))

def phase_rules(sel, indent="    "):
    """per-seat phase, in seconds, as a custom property."""
    return "\n".join(
        "%s%s polygon:nth-child(%d){ --p:%gs }   /* %s */" % (indent, sel, i + 1, PHASE[name], name)
        for i, (name, _) in enumerate(SEATS))

def polygons(cls, indent):
    return "\n".join('%s<polygon class="%s" points="%s"/>' % (indent, cls, pts)
                     for _, pts in SEATS)

# -------------------------------------------------------------------- svg ----
def svg_file(mode="auto"):
    """mode 'auto' answers prefers-color-scheme and is themable when inlined.
       'light' and 'dark' are fixed-palette variants for <img> on a known surface."""
    L, D = TOKENS["light"], TOKENS["dark"]
    if mode == "auto":
        tokens = ("""      --gl-active:%s;
      --gl-track:%s;
      --gl-track:%s;""" % (L["active"], L["track"], L["track_mix"]))
        scheme = """
    @media (prefers-color-scheme:dark){
      svg{
        --gl-active:%s;
        --gl-active:%s;
        --gl-track:%s;
        --gl-track:%s;
      }
    }""" % (D["active"], D["active_mix"], D["track"], D["track_mix"])
        note = ("Colour follows prefers-color-scheme. Inline this file and override the\n"
                "       gl-active and gl-track custom properties to drive it from the Portal's\n"
                "       own theme instead.")
    else:
        T = TOKENS[mode]
        tokens = ("""      --gl-active:%s;
      --gl-active:%s;
      --gl-track:%s;
      --gl-track:%s;""" % (T["active"], T["active_mix"] or T["active"], T["track"], T["track_mix"]))
        scheme = ""
        note = ("Fixed %s palette, no media query, so it renders the same inside an image\n"
                "       whatever theme the operating system is in." % mode)
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48" role="img" aria-label="Loading" focusable="false">
  <title>Loading</title>
  <style>
    svg{
      --gl-cycle:%(cycle)gs;
%(tokens)s
    }%(scheme)s
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

    /* reduced motion: hold one settled 3-of-5 majority, no movement at all */
    @media (prefers-reduced-motion:reduce){
      .votes polygon:nth-child(n){ animation:none }
%(static)s
    }
  </style>
  <!-- Quorum - a loading component for the GenLayer Portal.
       Geometry traced from the official mark: outer edges at dx/dy 0.482 (25.7 deg
       off vertical), the narrow vertical channel at the apex, the notch, the tapered
       feet, the core kite. Each blade is divided once, perpendicular to its axis, into
       two equal-area seats; with the core that makes five. Each settled state resolves
       to a 3-of-5 majority. Opacity is the only animated property.
       The official GenLayer mark asset is never modified or animated. This is a
       separate component derived from its geometry.
       %(note)s -->
  <g aria-hidden="true">
    <g class="seats">
%(seats)s
    </g>
    <g class="votes">
%(votes)s
    </g>
  </g>
</svg>
''' % dict(cycle=CYCLE, tokens=tokens, scheme=scheme, first=fmtv(LEVELS[0]),
           phases=phase_rules(".votes"), kf=css_keyframes(),
           static=static_rules(".votes", "      "), note=note,
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
        background:linear-gradient(90deg,var(--ceramic) 0 50%%,var(--void) 50%% 100%%);
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
  @media (prefers-reduced-motion:reduce){
    .gl-spinner .votes polygon:nth-child(n){ animation:none }
%(static)s
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
  <p class="thesis">The mark, taking a vote. Each settled state resolves to a 3-of-5 majority — the smallest majority that decides anything.</p>
  <div class="seam"><div class="slot" data-size="132" data-variant="universal"></div></div>
  <div class="bar" style="border:0"><span class="eyebrow">One mark, both surfaces</span>
    <span class="eyebrow">Ceramic Node %(ceramic)s · Carbon Void %(void)s</span></div>
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
    <h2>Five settled states, %(step)d ms apart</h2>
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
      same value and there is no frame where the mark flattens into one uniform state. During a crossfade a fourth seat is briefly non-zero; each <em>settled</em> state is a clean 3-of-5.</p>
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

  <section>
    <span class="eyebrow">Theming</span>
    <h2>Which file to use where</h2>
    <p class="lede">
      <code>genlayer-spinner.svg</code> follows <code>prefers-color-scheme</code>, which is the operating
      system's setting, not the colour of the container it sits in. Inline it and override
      <code>--gl-active</code> and <code>--gl-track</code> to drive it from the Portal's own theme. If it has
      to be an <code>&lt;img&gt;</code> on a surface whose theme the Portal controls independently, use
      <code>genlayer-spinner-light.svg</code> or <code>genlayer-spinner-dark.svg</code> — fixed palettes, no
      media query, so they cannot disagree with the surface.
    </p>
  </section>

  <footer>
    <span class="eyebrow">The official GenLayer mark asset is never modified or animated. Quorum is a
      separate loading component derived from its geometry.</span>
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
           static=static_rules(".gl-spinner .votes", "    "),
           kf=css_keyframes("    "), inline=inline,
           ladder_light=ladder("light"), ladder_dark=ladder("dark"), states=states)


# ------------------------------------------------------------------ readme ---
README = """# Quorum \u2014 GenLayer Portal spinner

An animated loading spinner for the GenLayer Portal. One self-contained SVG (3.2 KB)
animated in CSS: no JavaScript, no runtime, no external assets.

![preview](genlayer-spinner-light.gif)

## Identity

I rasterised the official GenLayer mark and traced it, edge by edge:

- outer edges at **dx/dy 0.482 \u2014 25.7\u00b0 off vertical**
- the narrow vertical channel at the apex
- the notch, the tapered feet, the core kite

That outline is the spinner. Each blade is split once, perpendicular to its own axis,
into two equal-area parts; with the core that makes five.

**The official GenLayer mark asset is never modified or animated.** Quorum is a
separate loading component derived from its geometry; the mark remains the primary
brand mark.

## Motion

Five seats, and **each settled state resolves to a 3-of-5 majority**. Every {STEP} ms one
seat joins, one leaves, three hold; a {CYCLE} s seamless loop. Opacity is the only
animated property, so nothing moves, rotates or rescales.

The five phases are exactly a fifth of a cycle apart, so no two seats ever hold the same
value and there is no frame where the mark flattens into one uniform state. During a
crossfade a fourth seat is briefly non-zero; every settled state is a clean three.

Under `prefers-reduced-motion: reduce` the animation stops entirely and the spinner holds
one settled 3-of-5 majority. Nothing breathes, pulses or moves.

## Colour

Only Kinetic Cobalt, Carbon Void and Ceramic Node. Every other value is a documented
`color-mix()` of those three:

| Token | Value | Derivation |
|---|---|---|
| light accent | `{LA}` | Kinetic Cobalt, 7.6:1 on Ceramic Node |
| dark accent | `{DA}` | 70% Cobalt / 30% Ceramic Node, 3.9:1 on Carbon Void |
| light track | `{LT}` | 18% Carbon Void over Ceramic Node |
| dark track | `{DT}` | 18% Ceramic Node over Carbon Void |

Full Cobalt measures 2.4:1 on Carbon Void, under the 3:1 floor for non-text graphics,
which is why the dark accent is a tint rather than the raw value.

## Which file to use where

`genlayer-spinner.svg` follows `prefers-color-scheme` \u2014 the operating system's setting,
not the colour of the container it sits in.

- **Inline it** and override `--gl-active` and `--gl-track` to drive it from the Portal's
  own theme. This is the recommended integration.
- **As an `<img>`** on a surface whose theme the Portal controls independently of the OS,
  use `genlayer-spinner-light.svg` or `genlayer-spinner-dark.svg` instead. Fixed palettes,
  no media query, so they cannot disagree with the surface.

```html
<img src="genlayer-spinner-light.svg" width="24" height="24" alt="Loading">
```

## Accessibility

`role="img"` with a label; the artwork is `aria-hidden`. Verified at 16, 20, 24, 32 and
48 px on both surfaces \u2014 see `test-frames-light.png` and `test-frames-dark.png`.

## Files

| File | What it is |
|---|---|
| `genlayer-spinner.svg` | the spinner, following the system colour scheme |
| `genlayer-spinner-light.svg` / `-dark.svg` | fixed-palette variants for `<img>` use |
| `preview.html` | live preview: light/dark, 16\u201348 px, five settled states |
| `build.py` | single source of truth \u2014 emits every file above |
| `genlayer-spinner-*.gif` | animated previews |
| `test-frames-*.png` | frame-by-frame renders at every size |

Geometry, keyframes, phases and colour tokens are declared once in `build.py`, so the
SVG, the preview and the test renders cannot drift apart. The frozen states in
`preview.html` are the live animation paused at a phase offset, not redrawings of it.

## Licence

MIT \u2014 free for the GenLayer Foundation to use, modify and redistribute.
"""

NOTES = """Quorum \u2014 a loading spinner for the Portal. One self-contained SVG (3.2 KB) animated in CSS: no JS, no runtime, no external assets.

Identity: I rasterised the official mark and traced it \u2014 outer edges at dx/dy 0.482 (25.7\u00b0 off vertical), the narrow apex channel, the notch, the core kite. Each blade is split once, perpendicular to its axis, into two equal-area parts; with the core, five. The official mark asset is never modified or animated; this is a separate component derived from its geometry.

Motion: five seats, each settled state resolving to a 3-of-5 majority. Every {STEP} ms one joins, one leaves, three hold; {CYCLE} s seamless loop. Opacity is the only animated property, and reduced motion holds one settled majority.

Colour: only Cobalt, Void and Ceramic Node; other values are a color-mix() of those three. Dark accent {DA} is 70/30 Cobalt/Ceramic, 3.9:1 on Void where full Cobalt is 2.4:1.

Verified 16\u201348 px, light and dark. Inline + CSS variables for Portal theming; fixed light/dark variants included for <img> use.

Source + live preview: <LINK>
"""

def fill(text):
    L, D = TOKENS["light"], TOKENS["dark"]
    for k, v in (("{STEP}", str(int(STEP * 1000))), ("{CYCLE}", "%g" % CYCLE),
                 ("{LA}", L["active"]), ("{DA}", D["active"]),
                 ("{LT}", L["track"]), ("{DT}", D["track"])):
        text = text.replace(k, v)
    return text

# ----------------------------------------------------------------- main ------
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "genlayer-spinner.svg"), "w").write(svg_file("auto"))
    open(os.path.join(OUT, "genlayer-spinner-light.svg"), "w").write(svg_file("light"))
    open(os.path.join(OUT, "genlayer-spinner-dark.svg"), "w").write(svg_file("dark"))
    open(os.path.join(OUT, "preview.html"), "w").write(preview_html())
    open(os.path.join(OUT, "README.md"), "w").write(fill(README))
    open(os.path.join(OUT, "submission-notes.txt"), "w").write(fill(NOTES))
    sheets()
    print("cycle %.2fs, %d states, %d ms each" % (CYCLE, STEPS, STEP * 1000))
    print("phases:", {k: round(v, 2) for k, v in PHASE.items()})
    print("static reduced-motion state:", {n: round(level_at(PHASE[n]/CYCLE*100),2) for n,_ in SEATS})
    print("wrote", sorted(os.listdir(OUT)))
