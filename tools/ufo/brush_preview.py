#!/usr/bin/env python3
"""Top view diagram of the four brush widths of FS25_UFO2500.

Everything is read from the built mod (ufo2500.xml + ufo2500.i3d), so the
picture cannot drift away from the actual configuration.

    python tools/ufo/brush_preview.py   ->  docs/renders/brushes.png
"""

import math
import os
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD = os.path.join(REPO, "FS25_UFO2500")

SCALE = 30.0            # pixels per metre
W, H = 1040, 660
LABEL_W = 300
ROW_H = 150


def load():
    veh = ET.parse(os.path.join(MOD, "ufo2500.xml")).getroot()
    i3d = ET.parse(os.path.join(MOD, "ufo2500.i3d")).getroot()
    nodes = {n.get("name"): n for n in i3d.find("Scene").iter() if n.get("name")}
    cfgs = []
    for cfg in veh.findall("wheels/wheelConfigurations/wheelConfiguration"):
        modules = []
        for w in cfg.findall("wheels/wheel"):
            phys = w.find("physics")
            name = phys.get("repr")
            if not name.startswith("wheelBrush"):
                continue
            tr = nodes[name].get("translation").split()
            modules.append((float(tr[0]), float(tr[2]), float(phys.get("width")),
                            (w.get("isCareWheel") or "false") == "true"))
        cfgs.append((cfg.get("saveId"), modules))
    ring = nodes["groundRing"]
    ring_r = float(ring.get("scale").split()[0])
    return cfgs, ring_r


def main():
    cfgs, ring_r = load()
    img = Image.new("RGB", (W, H), (18, 30, 25))
    d = ImageDraw.Draw(img)

    for i, (save_id, modules) in enumerate(cfgs):
        top = 30 + i * ROW_H
        cx = LABEL_W + (W - LABEL_W) // 2
        cy = top + ROW_H // 2 - 6
        swath = sum(m[2] for m in modules)

        # reference: the ground ring under the saucer (standard width)
        rr = ring_r * SCALE
        if save_id == "STANDARD":
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(52, 100, 78))
            d.text((cx, cy - rr - 12), "Bodenring unter dem UFO = 3,5 m",
                   anchor="ms", fill=(85, 150, 120))

        # the brush modules, to scale
        for x, z, width, care in modules:
            px = cx + x * SCALE
            half = width * SCALE / 2
            colour = (120, 235, 165) if not care else (200, 120, 120)
            d.rectangle([px - half, cy - 20, px + half, cy + 20], fill=colour)
        d.line([cx - swath * SCALE / 2 - 26, cy + 40, cx + swath * SCALE / 2 + 26, cy + 40],
               fill=(90, 160, 130))
        d.text((cx, cy + 48), "%.1f m" % swath, anchor="ma", fill=(160, 220, 190))

        d.text((24, cy - 16), save_id, fill=(230, 245, 235))
        d.text((24, cy + 2), "%.1f m Pinsel" % swath, fill=(140, 190, 165))
        d.text((24, cy + 20), "%.0f m2 / 100 m Fahrt" % (swath * 100), fill=(110, 160, 140))

    d.text((W // 2, H - 22),
           "FS25_UFO2500 - der Pinsel ist eine Reihe unsichtbarer 0,5-m-Raeder, "
           "die das Grundspiel plattdrueckt",
           anchor="ms", fill=(120, 170, 145))

    out = os.path.join(REPO, "docs", "renders", "brushes.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
