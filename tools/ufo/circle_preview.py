#!/usr/bin/env python3
"""Renders a preview sheet of the crop circle patterns.

The pattern maths lives in FS25_UFO2000/scripts/UFO2000.lua, so this script
evaluates the real Lua (through lupa) instead of duplicating the formulas -
what you see in docs/renders/circles.png is exactly what the UFO mows.

    python tools/ufo/circle_preview.py
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LUA = os.path.join(REPO, "FS25_UFO2000", "scripts", "UFO2000.lua")

STUB = r"""
Class = function() local c = {}; c.__index = c; return c end
Specialization = {}
SpecializationUtil = {
    registerFunction = function() end,
    registerOverwrittenFunction = function() end,
    registerEventListener = function() end,
}
Event = { new = function(mt) return setmetatable({}, mt or {}) end }
InitStaticEventClass = function() end
NetworkUtil = { readNodeObject = function() end, writeNodeObject = function() end }
-- lupa uses Lua 5.5 which folded atan2 into math.atan(y, x); FS25 has atan2
if math.atan2 == nil then math.atan2 = function(y, x) return math.atan(y, x) end end
"""


def main():
    from lupa import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUB)
    lua.execute(open(LUA, encoding="utf-8").read())

    count = lua.eval("UFO2000.getPatternCount()")
    is_point = lua.eval("UFO2000.isPointInPattern")
    names = [lua.eval("UFO2000.PATTERNS[%d].name" % i) for i in range(1, count + 1)]
    print("patterns:", ", ".join(names))

    cols, rows = 3, (count + 2) // 3
    tile, gap = 260, 16
    img = Image.new("RGB", (cols * tile + (cols + 1) * gap, rows * tile + (rows + 1) * gap + 30),
                    (24, 42, 34))
    draw = ImageDraw.Draw(img)

    # a wheat-ish field texture as background for the tiles
    rng = np.random.default_rng(3)
    for index in range(count):
        cx = gap + (index % cols) * (tile + gap)
        cy = gap + 30 + (index // cols) * (tile + gap)
        field = np.zeros((tile, tile, 3), dtype=np.float32)
        yy, xx = np.mgrid[0:tile, 0:tile]
        n = rng.normal(size=(tile, tile)) * 0.05
        field[..., 0] = 0.78 + n
        field[..., 1] = 0.66 + n
        field[..., 2] = 0.28 + n * 0.6
        # mown cells: darker stubble
        u = (xx - tile / 2) / (tile / 2 - 4)
        v = (yy - tile / 2) / (tile / 2 - 4)
        flat_u, flat_v = u.ravel(), v.ravel()
        mown = np.array([bool(is_point(index + 1, float(a), float(b)))
                         for a, b in zip(flat_u, flat_v)], dtype=bool).reshape(tile, tile)
        rr = np.sqrt(u ** 2 + v ** 2)
        mown &= rr <= 1.0
        field[mown] = field[mown] * 0.35 + np.array([0.28, 0.26, 0.16]) * 0.65
        tile_img = Image.fromarray((np.clip(field, 0, 1) * 255).astype(np.uint8), "RGB")
        img.paste(tile_img, (cx, cy))
        draw.rectangle([cx, cy, cx + tile - 1, cy + tile - 1], outline=(120, 200, 160))
        draw.text((cx + tile / 2, cy + tile + 2), names[index].replace("ufo_circle_", ""),
                  anchor="ma", fill=(200, 235, 215))

    out = os.path.join(REPO, "docs", "renders", "circles.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
