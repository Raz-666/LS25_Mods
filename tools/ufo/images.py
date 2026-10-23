# SPDX-License-Identifier: GPL-3.0-or-later
"""Shop icon, store picture, brand image and the doc renders for the UFO 2000."""

import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import render  # noqa: E402


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
    render.render(size=900, eye=(7.2, 3.4, 9.6), target=(0, 1.1, 0), fov=36, ss=2).save(
        os.path.join(docs, "ufo_hero.png"))
    render.render(size=800, eye=(0, 2.0, 10.0), target=(0, 1.2, 0), fov=36, ss=2).save(
        os.path.join(docs, "ufo_front.png"))
    render.render(size=800, eye=(6.5, -4.2, 7.5), target=(0, 0.5, 0), fov=38, ss=2, beam=True).save(
        os.path.join(docs, "ufo_below.png"))
    print("images written")


if __name__ == "__main__":
    build_all()
