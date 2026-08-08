#!/usr/bin/env python3
"""
Build the Kanta launcher icon: a truck on a weighbridge, simplified until
it survives 48px.

What got cut from the illustration, and why: side ribs, exhaust stack,
mirror, headlamp, bumper, chassis detail, the readout pillar, and every
highlight/shadow tone. At launcher size each of those is under a pixel and
turns to mud. What is left is four shapes - body, cab, wheels, deck.

Layout note: everything sits inside a 230x150 box centred on the canvas.
Its half-diagonal is 137px on a 432px foreground, inside Android's 144px
adaptive-icon safe radius, so a circular launcher mask cannot clip it.

Outputs, all under assets/icon/:
  mipmap-<density>/ic_launcher.png            legacy square, 48dp
  mipmap-<density>/ic_launcher_round.png      legacy round, 48dp
  mipmap-<density>/ic_launcher_foreground.png adaptive layer, 108dp
"""

import io
import os

import cairosvg
from PIL import Image, ImageDraw

INK   = "#12171c"
PAINT = "#f2b705"
STEEL = "#9aa39c"

CANVAS = 432          # design canvas = 108dp at xxxhdpi

# density -> (legacy px @48dp, foreground px @108dp)
DENSITIES = {
    "mdpi":    (48, 108),
    "hdpi":    (72, 162),
    "xhdpi":   (96, 216),
    "xxhdpi":  (144, 324),
    "xxxhdpi": (192, 432),
}


def artwork():
    """The mark only, on a transparent ground."""
    r = lambda x, y, w, h, f: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{f}"/>'
    g = []
    g.append(r(101, 141, 130, 78, PAINT))        # tipper body
    g.append(r(237, 159, 74, 60, PAINT))         # cab
    g.append(r(245, 169, 58, 24, INK))           # windscreen
    g.append(r(101, 219, 218, 12, STEEL))        # chassis
    for cx in (131, 175, 291):                   # wheels
        g.append(f'<circle cx="{cx}" cy="{253}" r="22" fill="{STEEL}"/>')
        g.append(f'<circle cx="{cx}" cy="{253}" r="8" fill="{INK}"/>')
    g.append(r(101, 275, 230, 16, STEEL))        # weighbridge deck
    g.append(r(101, 275, 230, 5, PAINT))         # deck edge
    return "".join(g)


def svg(with_background, scale=1.0):
    """
    The two layers need different framing, which is easy to get wrong.

    The adaptive foreground (scale 1.0) must stay inside the 72dp safe zone
    of a 108dp canvas, because launcher masks crop the rest. The legacy
    square icon has no mask and should fill its canvas instead - drawn at
    safe-zone scale it just looks shrunken.
    """
    off = (CANVAS / 2) - (CANVAS / 2) * scale     # rescale about the centre
    bg = f'<rect width="{CANVAS}" height="{CANVAS}" fill="{INK}"/>' if with_background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS} {CANVAS}" '
            f'width="{CANVAS}" height="{CANVAS}">{bg}'
            f'<g transform="translate({off:.2f},{off:.2f}) scale({scale})">{artwork()}</g></svg>')


def render(svg_text, px):
    png = cairosvg.svg2png(bytestring=svg_text.encode(), output_width=px, output_height=px)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def round_mask(im):
    """Legacy round icon: same art, circular crop."""
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, im.size[0] - 1, im.size[1] - 1), fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def main():
    fg_svg = svg(with_background=False, scale=1.0)   # adaptive: safe zone
    sq_svg = svg(with_background=True,  scale=1.7)   # legacy: fills canvas

    for density, (legacy_px, fg_px) in DENSITIES.items():
        d = os.path.join("assets", "icon", f"mipmap-{density}")
        os.makedirs(d, exist_ok=True)

        square = render(sq_svg, legacy_px)
        square.save(os.path.join(d, "ic_launcher.png"))
        round_mask(square).save(os.path.join(d, "ic_launcher_round.png"))
        render(fg_svg, fg_px).save(os.path.join(d, "ic_launcher_foreground.png"))
        print(f"  mipmap-{density}: {legacy_px}px legacy, {fg_px}px foreground")

    os.makedirs("assets/icon", exist_ok=True)
    open("assets/icon/icon-source.svg", "w").write(sq_svg)
    open("assets/icon/icon-foreground.svg", "w").write(fg_svg)
    print("  icon-source.svg, icon-foreground.svg")


if __name__ == "__main__":
    main()
