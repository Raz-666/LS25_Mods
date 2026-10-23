#!/usr/bin/env python3
"""Explains the trick behind FS25_UFO2500 in one picture (side view, to scale).

    python tools/ufo/console_preview.py   ->  docs/renders/ufo2500_concept.png

Dimensions are read from the built mod (ufo2500.xml / ufo2500.i3d), so the
drawing always matches what the game loads.
"""

import math
import os
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD = os.path.join(REPO, "FS25_UFO2500")

W, H = 1020, 800
GROUND_Y = 690
ORIGIN_X = 560
PX_PER_M = 40.0

INK = (238, 246, 242)
DIM = (158, 198, 180)
ACCENT = (120, 235, 165)
GHOST = (160, 130, 220)
OUTLINE = (96, 122, 144)


def _font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_SMALL = _font(14)
F_TEXT = _font(16)
F_TITLE = _font(22)
F_BOLD = _font(17)


def load():
    i3d = ET.parse(os.path.join(MOD, "ufo2500.i3d")).getroot()

    def walk(node, parent=(0.0, 0.0, 0.0)):
        tr = [float(v) for v in node.get("translation", "0 0 0").split()]
        here = (parent[0] + tr[0], parent[1] + tr[1], parent[2] + tr[2])
        yield node.get("name"), here
        for child in node:
            yield from walk(child, here)

    nodes = {}
    for root in i3d.find("Scene"):
        for name, pos in walk(root):
            if name:
                nodes[name] = pos

    veh = ET.parse(os.path.join(MOD, "ufo2500.xml")).getroot()
    wheels = []
    cfg = veh.find("wheels/wheelConfigurations/wheelConfiguration[@saveId='HARVESTER']")
    for w in cfg.findall("wheels/wheel"):
        phys = w.find("physics")
        wheels.append((phys.get("repr"), float(phys.get("width"))))
    return nodes, wheels


def main():
    nodes, wheels = load()
    craft_y = nodes["visual"][1]
    seat_y = nodes["driverSeatNode"][1]

    img = Image.new("RGB", (W, H), (15, 22, 27))
    d = ImageDraw.Draw(img)

    def X(x):
        return ORIGIN_X + x * PX_PER_M

    def Y(y):
        return GROUND_Y - y * PX_PER_M

    # --- ground and field ---------------------------------------------------
    d.rectangle([0, GROUND_Y, W, H], fill=(31, 37, 26))
    for i in range(0, W, 7):
        d.line([(i, GROUND_Y - 4), (i + 3, GROUND_Y)], fill=(112, 94, 40))
    d.text((26, GROUND_Y + 18), "Boden / Feld", fill=(168, 176, 126), font=F_TEXT)

    # --- invisible wheels (side view: circles lying on the ground) ----------
    for name, _width in wheels:
        x, _y, _z = nodes[name]
        r = 0.55 * PX_PER_M
        box = [X(x) - r * 0.7, Y(0.55) - r, X(x) + r * 0.7, Y(0.55) + r]
        brush = name.startswith("wheelBrush")
        d.ellipse(box, fill=(28, 44, 34) if brush else (26, 26, 34),
                  outline=ACCENT if brush else GHOST)

    # --- the vehicle "body" the game sees ----------------------------------
    d.rectangle([X(-2.35), Y(7.9), X(2.35), GROUND_Y], outline=OUTLINE)
    d.text((X(2.35) + 12, Y(4.2)), "dieser ganze Raum\nist das Fahrzeug\n"
                                   "(der Ursprung steht am Boden)",
           fill=DIM, font=F_SMALL, spacing=5)

    # --- the saucer, to scale ----------------------------------------------
    hull_top, hull_bottom = craft_y + 1.20, craft_y - 0.36
    d.ellipse([X(-2.35), Y(hull_top), X(2.35), Y(hull_bottom)],
              fill=(178, 196, 198), outline=(226, 238, 238))
    # rim glow strip
    d.arc([X(-2.35), Y(hull_top), X(2.35), Y(hull_bottom)], 200, 340,
          fill=(120, 235, 165), width=3)
    # the glass dome (upper half of an ellipse standing on the hull)
    base = craft_y + 1.17
    dome_r = 1.58
    d.pieslice([X(-dome_r), Y(base + dome_r), X(dome_r), Y(base - dome_r)],
               180, 360, fill=(142, 204, 214), outline=(216, 240, 244))
    # seat
    d.line([X(0) - 8, Y(seat_y), X(0) + 8, Y(seat_y)], fill=(250, 220, 120), width=3)
    d.line([X(0) + 8, Y(seat_y), X(1.85), Y(seat_y)], fill=(250, 220, 120))
    d.text((X(1.95), Y(seat_y) - 8), "Sitz", fill=(250, 220, 120), font=F_SMALL)

    # --- beam --------------------------------------------------------------
    d.polygon([(X(-0.10), Y(craft_y + 0.2)), (X(0.10), Y(craft_y + 0.2)),
               (X(1.75), GROUND_Y - 5), (X(-1.75), GROUND_Y - 5)],
              outline=(96, 212, 192))

    # --- brush contact patch ----------------------------------------------
    brush = [w for w in wheels if w[0].startswith("wheelBrush")]
    half = (max(nodes[n][0] for n, _w in brush) + 0.25) * PX_PER_M
    d.rectangle([X(0) - half, GROUND_Y - 7, X(0) + half, GROUND_Y], fill=ACCENT)
    d.text((X(0), GROUND_Y + 4), "7,5 m Pinsel", anchor="ma", fill=ACCENT, font=F_SMALL)

    # --- dimension arrows --------------------------------------------------
    def dimension(x, y_from, y_to, label, colour=DIM, offset=-8, anchor="rm"):
        d.line([(x, Y(y_from)), (x, Y(y_to))], fill=colour)
        for yy in (Y(y_from), Y(y_to)):
            d.line([(x - 6, yy), (x + 6, yy)], fill=colour)
        d.text((x + offset, (Y(y_from) + Y(y_to)) / 2), label, anchor=anchor,
               fill=colour, font=F_TEXT)

    dimension(X(-3.1), 0.0, craft_y + 0.30, "8,83 m", colour=(96, 212, 192))
    dimension(X(-4.9), 0.0, seat_y, "10,00 m", colour=(250, 220, 120))

    # --- legend / text -----------------------------------------------------
    d.text((26, 26), "FS25_UFO2500 – Konsole ohne Lua", fill=INK, font=F_TITLE)
    d.multiline_text((26, 60),
                     "Das UFO ist ein ganz normales Fahrzeug. Seine vier unsichtbaren\n"
                     "Räder stehen am Boden, das Cockpit schwebt 10 m darüber.",
                     fill=DIM, font=F_TEXT, spacing=6)

    y = 122
    for colour, text in (
        (GHOST, "4 Pflege-Räder tragen das Fahrzeug – sie beschädigen nichts"),
        (ACCENT, "15 Pinsel-Räder à 0,5 m drücken das Getreide platt (7,5 m breit)"),
        ((96, 212, 192), "Strahl: feste Geometrie, endet immer am Boden"),
        (OUTLINE, "Aufstandspunkt bleibt am Boden – Physik wie beim Auto"),
        ((250, 220, 120), "10,00 m = Blickhöhe (Sitz),  8,83 m = Schwebehöhe des Rumpfes"),
    ):
        d.ellipse([28, y + 2, 42, y + 16], outline=colour,
                  fill=colour if colour == ACCENT else None)
        d.text((52, y), text, fill=DIM, font=F_SMALL)
        y += 26

    d.text((26, H - 26), "maßstabsgetreue Skizze – erzeugt von tools/ufo/console_preview.py",
           fill=(108, 138, 124), font=F_SMALL)

    out = os.path.join(REPO, "docs", "renders", "ufo2500_concept.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
