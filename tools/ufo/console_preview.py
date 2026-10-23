#!/usr/bin/env python3
"""Explains the trick behind FS25_UFO2500 in one picture (side view, to scale).

    python tools/ufo/console_preview.py   ->  docs/renders/ufo2500_concept.png

Dimensions are read from the built mod (ufo2500.xml / ufo2500.i3d), so the
drawing always matches what the game loads.  The craft is drawn twice: hovering
(solid) and after the landing animation (ghost).
"""

import os
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD = os.path.join(REPO, "FS25_UFO2500")

W, H = 1080, 800
GROUND_Y = 690
ORIGIN_X = 620
PX_PER_M = 23.0

INK = (238, 246, 242)
DIM = (158, 198, 180)
ACCENT = (120, 235, 165)
GHOST = (150, 128, 210)
OUTLINE = (96, 122, 144)
SEAT = (250, 220, 120)
BEAM = (96, 212, 192)


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
        wheels.append((phys.get("repr"), float(phys.get("width")),
                       float(phys.get("radius"))))
    anim = veh.find("animations/animation[@name='landing']/part[@node='visual']")
    landed_y = float(anim.get("endTrans").split()[1])
    return nodes, wheels, landed_y


def main():
    nodes, wheels, landed_y = load()
    craft_y = nodes["visual"][1]
    seat_y = nodes["driverSeatNode"][1]
    total = seat_y + 0.0

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
    for name, width, radius in wheels:
        x, _y, _z = nodes[name]
        r = radius * PX_PER_M
        brush = name.startswith("wheelBrush")
        wide = name in ("wheelFront", "wheelRear")
        box = [X(x) - r * 0.7, Y(radius) - r, X(x) + r * 0.7, Y(radius) + r]
        if brush:
            d.ellipse(box, fill=(28, 44, 34), outline=ACCENT)
        elif wide:
            d.ellipse(box, fill=(30, 30, 42), outline=GHOST, width=2)
        else:
            d.ellipse(box, outline=(70, 60, 96))

    # --- the vehicle "body" the game sees ----------------------------------
    d.rectangle([X(-2.35), Y(craft_y + 1.2), X(2.35), GROUND_Y], outline=OUTLINE)
    d.text((X(2.75), Y(craft_y * 0.45)), "dieser ganze Raum\nist das Fahrzeug\n"
                                         "(der Ursprung steht am Boden)",
           fill=DIM, font=F_SMALL, spacing=5)

    def saucer(cy, colour, outline, ghost=False):
        hull_top, hull_bottom = cy + 1.20, cy - 0.36
        d.ellipse([X(-2.35), Y(hull_top), X(2.35), Y(hull_bottom)],
                  fill=None if ghost else colour, outline=outline)
        if not ghost:
            d.arc([X(-2.35), Y(hull_top), X(2.35), Y(hull_bottom)], 200, 340,
                  fill=ACCENT, width=3)
        base = cy + 1.17
        dome_r = 1.58
        d.pieslice([X(-dome_r), Y(base + dome_r), X(dome_r), Y(base - dome_r)],
                   180, 360, fill=None if ghost else (142, 204, 214), outline=outline)
        # cockpit interior: seat and the two blinking beacons
        d.line([X(0) - 7, Y(cy + 1.72), X(0) + 7, Y(cy + 1.72)],
               fill=SEAT, width=3)
        for sx in (-0.44, 0.44):
            d.ellipse([X(sx) - 3, Y(cy + 1.62) - 3, X(sx) + 3, Y(cy + 1.62) + 3],
                      outline=ACCENT if not ghost else (60, 90, 74))

    # hover state
    saucer(craft_y, (178, 196, 198), (226, 238, 238))
    # landing state (ghost)
    saucer(landed_y, None, (120, 104, 168), ghost=True)
    # legs, hovering: splayed out; landed: vertical
    for dx in (-1.55, 1.55):
        d.line([X(dx * 0.65), Y(craft_y - 0.2), X(dx), Y(craft_y - 1.05)],
               fill=(196, 196, 206), width=3)
        d.line([X(dx * 0.85), Y(landed_y - 0.2), X(dx * 0.85), Y(landed_y - 0.75)],
               fill=(120, 104, 168), width=2)

    # seat marker of the hovering craft
    d.line([X(0) + 8, Y(seat_y), X(1.85), Y(seat_y)], fill=SEAT)

    # --- beam --------------------------------------------------------------
    d.polygon([(X(-0.10), Y(craft_y + 0.2)), (X(0.10), Y(craft_y + 0.2)),
               (X(1.75), GROUND_Y - 5), (X(-1.75), GROUND_Y - 5)],
              outline=BEAM)
    d.polygon([(X(-0.06), Y(landed_y - 0.2)), (X(0.06), Y(landed_y - 0.2)),
               (X(0.9), GROUND_Y - 5), (X(-0.9), GROUND_Y - 5)],
              outline=(96, 140, 132))

    # --- brush contact patch ----------------------------------------------
    brush = [w for w in wheels if w[0].startswith("wheelBrush")]
    half = (max(nodes[n][0] for n, _w, _r in brush) + 0.25) * PX_PER_M
    d.rectangle([X(0) - half, GROUND_Y - 7, X(0) + half, GROUND_Y], fill=ACCENT)
    d.text((X(0), GROUND_Y + 4), "7,5 m Pinsel", anchor="ma", fill=ACCENT, font=F_SMALL)

    # --- dimension arrows --------------------------------------------------
    def dimension(x, y_from, y_to, label, colour=DIM, offset=-8, anchor="rm", dy=0):
        d.line([(x, Y(y_from)), (x, Y(y_to))], fill=colour)
        for yy in (Y(y_from), Y(y_to)):
            d.line([(x - 6, yy), (x + 6, yy)], fill=colour)
        d.text((x + offset, (Y(y_from) + Y(y_to)) / 2 + dy), label, anchor=anchor,
               fill=colour, font=F_TEXT)

    dimension(X(-3.1), 0.0, craft_y + 0.30,
              ("%.2f m" % (craft_y + 0.30)).replace(".", ","), colour=BEAM, dy=18)
    dimension(X(-4.9), 0.0, seat_y, ("%.2f m" % seat_y).replace(".", ","),
              colour=SEAT)
    d.line([(X(3.6), Y(0.0)), (X(3.6), Y(landed_y))], fill=GHOST)
    for yy in (Y(0.0), Y(landed_y)):
        d.line([(X(3.6) - 6, yy), (X(3.6) + 6, yy)], fill=GHOST)
    d.text((X(3.9), Y(1.9)), ("%.2f m" % landed_y).replace(".", ","), fill=GHOST, font=F_SMALL)

    d.multiline_text((26, 400),
                     "Taste X landet das UFO:\n"
                     "in 4,5 s fährt das Cockpit auf\n"
                     "Straßenniveau, die Beine klappen\n"
                     "aus, der Strahl wird zum Landefleck.\n"
                     "Nochmal X = wieder abheben.\n\n"
                     "Im Cockpit: Sitz, Konsole, zwei\n"
                     "blinkende Leuchten (Grundspiel-\n"
                     "BeaconLight, Taste Rundumlicht).\n\n"
                     "Die Federung lässt das UFO leicht\n"
                     "wippen – Schweben ohne Lua.",
                     fill=DIM, font=F_TEXT, spacing=6)

    # --- legend / text -----------------------------------------------------
    d.text((26, 24), "FS25_UFO2500 – Konsole ohne Lua", fill=INK, font=F_TITLE)
    d.multiline_text((26, 58),
                     "Ein ganz normales Fahrzeug: zwei breite unsichtbare Räder stehen\n"
                     "am Boden, das Cockpit schwebt 20 m darüber. Die Landung fährt\n"
                     "es auf Straßenniveau herunter.",
                     fill=DIM, font=F_TEXT, spacing=6)

    y = 150
    legends = (
        (GHOST, "2 breite Räder (0,7 m) tragen das UFO, 2 Stützräder halten es gerade"),
        (ACCENT, "15 Pinsel-Räder à 0,5 m drücken das Getreide platt (7,5 m breit)"),
        (BEAM, "Strahl: feste Geometrie, endet immer am Boden"),
        (SEAT, "%.2f m = Sitzhöhe beim Schweben" % seat_y),
        ((120, 104, 168), "Landung: Cockpit fährt auf %.2f m herunter, Beine stützen" % landed_y),
        (OUTLINE, "Aufstandspunkt bleibt am Boden – Physik wie beim Auto"),
    )
    for colour, text in legends:
        d.ellipse([28, y + 2, 42, y + 16], outline=colour,
                  fill=colour if colour == ACCENT else None)
        d.text((52, y), text, fill=DIM, font=F_SMALL)
        y += 25

    d.text((26, H - 26), "maßstabsgetreue Skizze – erzeugt von tools/ufo/console_preview.py",
           fill=(108, 138, 124), font=F_SMALL)

    out = os.path.join(REPO, "docs", "renders", "ufo2500_concept.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out, "(seat %.2f m, total %.2f m)" % (seat_y, total))


if __name__ == "__main__":
    sys.exit(main())
