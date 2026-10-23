# SPDX-License-Identifier: GPL-3.0-or-later
"""Shop icon, store picture, brand image and the doc renders for the UFO 2000."""

import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import render  # noqa: E402
import model  # noqa: E402


def _dds(src_png, dst_dds, fmt="bc1", python=sys.executable):
    subprocess.run([python, os.path.join(REPO, "tools", "png2dds.py"), src_png, dst_dds,
                    "--format", fmt], check=True, stdout=subprocess.DEVNULL)


def _with_shadow(img, cx=0.5, cy=0.92, rx=0.33, ry=0.055, strength=0.35):
    """Add a soft ground shadow to an RGBA image."""
    w, h = img.size
    import numpy as np
    arr = np.array(img).astype(np.float32) / 255.0
    yy, xx = np.mgrid[0:h, 0:w]
    d = (((xx - w * cx) / (w * rx)) ** 2 + ((yy - h * cy) / (h * ry)) ** 2) ** 0.5
    mask = (np.clip(1.0 - d, 0.0, 1.0) ** 1.7) * strength
    rgb = arr[..., :3] * (1 - mask[..., None])
    out = np.dstack([rgb, arr[..., 3]])
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def _find(node, name):
    if node.name == name:
        return node
    for child in node.children:
        found = _find(child, name)
        if found is not None:
            return found
    return None


def doc_scene(beam=False, legs=0.0, altitude=6.0):
    """Scene for the documentation renders: legs partly folded, beam on."""
    root = model.build_scene()
    for i in range(3):
        leg = _find(root, "leg%d" % i)
        if leg is not None:
            rest = float(leg.attrs["rotation"].split()[2])
            leg.attrs["rotation"] = "0 %s %s" % (leg.attrs["rotation"].split()[1],
                                                rest + 74 * legs)
    if beam:
        radius = max(1.8, altitude * math.tan(math.radians(34.0)))
        tube = _find(root, "beamNode")
        ring = _find(root, "groundRing")
        if tube is not None:
            tube.attrs["visibility"] = "true"
            tube.attrs["scale"] = "%.4f %.4f %.4f" % (radius, altitude - 0.22, radius)
        if ring is not None:
            ring.attrs["visibility"] = "true"
            ring.attrs["translation"] = "0 %.3f 0" % (0.08 - altitude)
            ring.attrs["scale"] = "%.4f 1 %.4f" % (radius, radius)
    return root


def build_all(python=sys.executable):
    mod = os.path.join(REPO, "FS25_UFO2000")
    build = os.path.join(REPO, "build")
    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(build, exist_ok=True)
    os.makedirs(docs, exist_ok=True)

    # 1) shop icon (512x512, with mips) - the shape the mod list shows
    icon = render.render(size=512, eye=(6.0, 3.4, 8.8), target=(0, 1.05, 0), fov=36, ss=2)
    icon = render.add_shadow(icon, strength=0.30)
    p = os.path.join(build, "icon_ufo2000.png")
    icon.save(p)
    _dds(p, os.path.join(mod, "icon_ufo2000.dds"), "bc1", python)

    # 2) store picture (RGBA png, like the base game store images)
    store = render.render(size=512, eye=(6.6, 3.9, 9.4), target=(0, 1.0, 0), fov=34, ss=2,
                          return_alpha=True)
    store = _with_shadow(store, cy=0.90, rx=0.34, ry=0.05, strength=0.30)
    store.save(os.path.join(mod, "store_ufo.png"))

    # 3) brand image
    brand = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    little = render.render(size=256, eye=(0, 1.2, 8.5), target=(0, 1.05, 0), fov=34, ss=2,
                           background=(1, 1, 1), return_alpha=True)
    brand.alpha_composite(little, (128, 0))
    d = ImageDraw.Draw(brand)
    d.text((256, 214), "UFO 2000", anchor="mm", fill=(38, 58, 54, 255))
    p = os.path.join(build, "brand_ufo2000.png")
    brand.save(p)
    _dds(p, os.path.join(mod, "brand_ufo2000.dds"), "bc1", python)

    # 4) documentation renders
    render.render(size=900, eye=(7.4, 3.6, 9.8), target=(0, 1.25, 0), fov=36, ss=2).save(
        os.path.join(docs, "ufo_hero.png"))
    render.render(size=800, eye=(0, 2.2, 10.0), target=(0, 1.35, 0), fov=36, ss=2).save(
        os.path.join(docs, "ufo_front.png"))
    render.render(size=800, eye=(6.5, -4.2, 7.5), target=(0, 0.5, 0), fov=38, ss=2,
                  beam=True, root=doc_scene(beam=True, legs=1.0, altitude=5.5)).save(
        os.path.join(docs, "ufo_below.png"))

    # beam + marker ring, exactly as the Lua script places it
    render.render(size=900, eye=(13.0, 5.0, 15.0), target=(0, 2.6, 0), fov=40, ss=2,
                  beam=True, root=doc_scene(beam=True, legs=1.0, altitude=8.0)).save(
        os.path.join(docs, "ufo_beam.png"))

    # landing legs down / up
    down = render.render(size=420, eye=(0, 2.4, 8.2), target=(0, 1.0, 0), fov=36, ss=2,
                         root=doc_scene(legs=0.0))
    up = render.render(size=420, eye=(0, 2.4, 8.2), target=(0, 1.0, 0), fov=36, ss=2,
                       root=doc_scene(legs=1.0))
    combo = Image.new("RGB", (840, 420))
    combo.paste(down, (0, 0))
    combo.paste(up, (420, 0))
    combo.save(os.path.join(docs, "ufo_legs.png"))
    print("images written")


if __name__ == "__main__":
    build_all()
