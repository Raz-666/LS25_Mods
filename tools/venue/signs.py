# SPDX-License-Identifier: GPL-3.0-or-later
"""Neon sign / lettering painter for the venue mods.

Draws words the way a neon tube looks: a bright core, a coloured halo, a dark
backing panel and little tube "bridges" between letters.  Everything is plain
Pillow, so the signs are just textures on a flat quad in the i3d.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _text_mask(text, size, font_path, tracking=0.0, slant=0.0):
    """Render text into an L mask, with optional letter spacing and slant."""
    font = _font(font_path, int(size))
    pad = int(size * 0.6)
    probe = Image.new("L", (10, 10))
    width = int(ImageDraw.Draw(probe).textlength(text, font=font) + tracking * size * len(text))
    height = int(size * 1.6)
    img = Image.new("L", (max(width, 1) + pad * 2, height + pad * 2), 0)
    d = ImageDraw.Draw(img)
    x = pad
    for ch in text:
        d.text((x, pad), ch, font=font, fill=255)
        x += d.textlength(ch, font=font) + tracking * size
    if slant:
        # shear to get the 70s/80s script feel
        w, h = img.size
        img = img.transform((w + int(h * slant), h), Image.AFFINE,
                            (1, -slant, 0, 0, 1, 0), resample=Image.BICUBIC)
    return img


def neon_word(text, colour=(0.35, 0.85, 1.0), size=512, font_path=FONT_BOLD,
              tracking=0.0, background=(0.06, 0.05, 0.05), slant=0.0,
              tube_gain=1.0, glow=1.0):
    """A neon tube word on a dark backing, as an RGB image."""
    mask = _text_mask(text, size, font_path, tracking, slant)
    # trim to content, add a margin for the halo
    box = mask.getbbox()
    if box is None:
        return Image.new("RGB", (512, 128), background)
    margin = int(size * 0.35)
    mask = mask.crop((max(box[0] - margin, 0), max(box[1] - margin, 0),
                      min(box[2] + margin, mask.width), min(box[3] + margin, mask.height)))
    # scale so the longest side is `size` * 2 for crisp downscaling
    scale = (size * 2.0) / max(mask.size)
    mask = mask.resize((max(1, int(mask.width * scale)), max(1, int(mask.height * scale))),
                       Image.LANCZOS)
    m = np.asarray(mask, dtype=np.float32) / 255.0

    # the tube: the *outline* of the letters glows, the inside stays dark -
    # that is what a bent neon tube looks like
    mask_img = Image.fromarray((m * 255).astype(np.uint8))
    thickness = max(3, int(mask_img.width * 0.007))
    inner = mask_img.filter(ImageFilter.MinFilter(thickness * 2 + 1))
    tube = np.clip((np.asarray(mask_img, dtype=np.float32) -
                    np.asarray(inner, dtype=np.float32)) / 255.0, 0, 1)
    tube_img = Image.fromarray((tube * 255).astype(np.uint8))
    halo = np.asarray(tube_img.filter(
        ImageFilter.GaussianBlur(mask_img.width * 0.012)), dtype=np.float32) / 255.0
    far = np.asarray(tube_img.filter(
        ImageFilter.GaussianBlur(mask_img.width * 0.05)), dtype=np.float32) / 255.0

    h, w = m.shape
    bg = np.broadcast_to(np.array(background, dtype=np.float32), (h, w, 3)).copy()
    col = np.broadcast_to(np.array(colour, dtype=np.float32), (h, w, 3))
    white = np.ones((h, w, 3), dtype=np.float32)
    # the dark backing panel, slightly lighter than the wall
    panel = np.clip(bg + m[..., None] * 0.035, 0, 1)

    rgb = panel
    rgb += far[..., None] * col * 0.55 * glow
    rgb += halo[..., None] * col * 1.25 * glow
    rgb += tube[..., None] * (col * 0.45 + white * 0.8) * tube_gain
    rgb = np.clip(rgb, 0, 1)
    img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB")
    # vignette so the panel edges disappear
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx / w) - 0.5) ** 2 + ((yy / h) - 0.5) ** 2) * 2.0
    a = np.clip(1.15 - 0.55 * r, 0, 1)[..., None]
    arr = np.asarray(img, dtype=np.float32) * a
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def sign_pair(size, out_dir):
    """The two signs of the club: DISTILLERY (script, warm/blue) and LEIPZIG."""
    os.makedirs(out_dir, exist_ok=True)
    d = neon_word("DISTILLERY", colour=(1.0, 0.62, 0.22), size=size,
                  font_path=FONT_BOLD, tracking=-0.02, slant=0.10,
                  background=(0.045, 0.035, 0.03))
    # blue rim light on the lower half, like the reference photo
    arr = np.asarray(d, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    yy = (np.arange(h, dtype=np.float32) / h)[:, None, None]
    blue = np.array([0.25, 0.65, 1.0], dtype=np.float32)
    arr = arr * (1.0 - 0.35 * yy) + blue[None, None, :] * 0.28 * yy * (arr.max(axis=2, keepdims=True))
    d = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB")
    d.save(os.path.join(out_dir, "signDistillery.png"))

    l = neon_word("LEIPZIG", colour=(0.35, 0.72, 1.0), size=size,
                  font_path=FONT_BOLD, tracking=0.06, slant=0.04,
                  background=(0.045, 0.035, 0.03))
    l.save(os.path.join(out_dir, "signLeipzig.png"))

    b = neon_word("BAR 01", colour=(1.0, 0.45, 0.15), size=size // 2,
                  font_path=FONT_BOLD, tracking=0.08,
                  background=(0.05, 0.04, 0.035))
    b.save(os.path.join(out_dir, "signBar.png"))
    return [os.path.join(out_dir, n) for n in
            ("signDistillery.png", "signLeipzig.png", "signBar.png")]


if __name__ == "__main__":
    import sys
    for p in sign_pair(512, sys.argv[1] if len(sys.argv) > 1 else "/tmp/signs"):
        print(p)


def playlist_panel(titles, size=(768, 512), out_path=None, header="DISTILLERY  -  DJ BOOTH"):
    """The set list board next to the mixer.

    One texture holds every row, so the i3d only needs a handful of quads with
    different UV rectangles - the script then just moves the marker bar to the
    row that is playing.
    """
    w, h = size
    img = Image.new("RGB", (w, h), (34, 26, 19))
    d = ImageDraw.Draw(img)
    # amber glass frame + a few vertical light strips, like a backlit sign
    d.rectangle([0, 0, w - 1, h - 1], outline=(110, 62, 22), width=4)
    for x in range(24, w - 8, 34):
        d.line([(x, 6), (x, h - 6)], fill=(44, 32, 22), width=2)

    font_head = _font(FONT_BOLD, int(h * 0.075))
    font_row = _font(FONT_SANS, int(h * 0.062))
    font_num = _font(FONT_BOLD, int(h * 0.055))
    d.text((26, int(h * 0.035)), header, font=font_head, fill=(255, 176, 64))
    d.line([(26, int(h * 0.13)), (w - 26, int(h * 0.13))], fill=(255, 150, 50), width=3)

    n = max(1, len(titles))
    top = int(h * 0.16)
    bottom = h - int(h * 0.06)
    row_h = (bottom - top) / float(n)
    for i, title in enumerate(titles):
        y = top + i * row_h
        if i % 2 == 0:
            d.rectangle([16, y + 1, w - 16, y + row_h - 1], fill=(52, 39, 27))
        d.text((34, y + row_h * 0.22), "%02d" % (i + 1), font=font_num,
               fill=(150, 110, 60))
        d.text((96, y + row_h * 0.16), title, font=font_row, fill=(244, 232, 210))
        d.line([(30, y + row_h - 2), (w - 30, y + row_h - 2)], fill=(96, 70, 44), width=1)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    # warm glow from the left so it reads as a lit panel
    arr = np.asarray(img, dtype=np.float32) / 255.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    glow = np.clip(1.25 - 0.7 * (xx / w), 0.55, 1.2)[..., None]
    arr = np.clip(arr * glow * 1.35, 0, 1)
    out = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        out.save(out_path)
    return out
