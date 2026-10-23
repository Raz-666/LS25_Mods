# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal software renderer: draws the procedural UFO scene to a PNG.

No Blender, no OpenGL - just a numpy z-buffer rasteriser.  It is used for the
mod icon, the shop picture and the images in docs/.
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model  # noqa: E402

# base colours + glossiness per material (albedo in linear-ish sRGB 0..1)
MAT_LOOK = {
    "collision": None,
    "hullPaint": ((0.86, 0.94, 0.89), 0.45, 0.0, 1.0),
    "hullMetal": ((0.30, 0.34, 0.36), 0.75, 0.0, 1.0),
    "cockpit": ((0.16, 0.21, 0.20), 0.25, 0.0, 1.0),
    "glass": ((0.55, 0.86, 0.93), 0.9, 0.0, 0.42),
    "lensGreen": ((0.25, 1.0, 0.5), 0.4, 0.9, 1.0),
    "lensRed": ((1.0, 0.22, 0.20), 0.4, 0.9, 1.0),
    "lensWhite": ((1.0, 0.96, 0.82), 0.5, 0.7, 1.0),
    "alienSkin": ((0.55, 0.88, 0.50), 0.35, 0.0, 1.0),
    "eyeBlack": ((0.03, 0.04, 0.05), 0.9, 0.0, 1.0),
    "beam": ((0.45, 0.92, 1.0), 0.1, 0.8, 0.30),
}

LIGHT_KEY = np.array([-0.45, 0.78, 0.44])
LIGHT_KEY /= np.linalg.norm(LIGHT_KEY)
LIGHT_FILL = np.array([0.6, -0.35, -0.5])
LIGHT_FILL /= np.linalg.norm(LIGHT_FILL)


def _rot_matrix(rx, ry, rz):
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ mx @ my


def collect(node, parent=np.eye(4), visible=True, out=None):
    if out is None:
        out = []
    if not visible:
        return out
    t = np.eye(4)
    tr = node.attrs.get("translation")
    ro = node.attrs.get("rotation")
    if tr:
        t[:3, 3] = [float(v) for v in tr.split()]
    if ro:
        t[:3, :3] = _rot_matrix(*[float(v) for v in ro.split()])
    sc = node.attrs.get("scale")
    if sc:
        t[:3, :3] = t[:3, :3] @ np.diag([float(v) for v in sc.split()])
    world = parent @ t
    vis = node.attrs.get("visibility", "true") != "false"
    if node.mesh is not None and vis:
        for mat in node.mesh.order:
            if mat == "collision":
                continue
            verts, normals, _uv, tris = node.mesh.parts[mat]
            v = np.array(verts, dtype=np.float64)
            n = np.array(normals, dtype=np.float64)
            v = v @ world[:3, :3].T + world[:3, 3]
            n = n @ world[:3, :3].T
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
            idx = np.array(tris, dtype=np.int64).reshape(-1, 3)
            out.append((mat, v[idx[:, 0]], v[idx[:, 1]], v[idx[:, 2]],
                        n[idx[:, 0]], n[idx[:, 1]], n[idx[:, 2]]))
    for child in node.children:
        collect(child, world, vis, out)
    return out


def look_at(eye, target, up=(0, 1, 0)):
    eye = np.array(eye, dtype=np.float64)
    target = np.array(target, dtype=np.float64)
    f = target - eye
    f /= np.linalg.norm(f)
    up = np.array(up, dtype=np.float64)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def render(eye=(6.8, 3.2, 9.2), target=(0, 1.05, 0), size=1024, fov=38.0, ss=2,
           background="sky", beam=False, return_alpha=False, root=None):
    if root is None:
        root = model.build_scene()
    tris = collect(root)

    W = H = size * ss
    color = np.zeros((H, W, 3), dtype=np.float32)
    alpha = np.zeros((H, W), dtype=np.float32)
    depth = np.full((H, W), -1e9, dtype=np.float32)

    if background == "sky":
        yy = np.linspace(0, 1, H)[:, None]
        top = np.array([0.76, 0.90, 0.95])
        bottom = np.array([0.97, 0.97, 0.93])
        color[:] = (top * (1 - yy)[..., None] + bottom * yy[..., None])
    else:
        color[:] = np.array(background, dtype=np.float32)

    view = look_at(eye, target)
    f = 1.0 / math.tan(math.radians(fov) / 2.0)
    proj = np.array([[f, 0, 0, 0], [0, f, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    vp = proj @ view

    def project(pts):
        h = np.hstack([pts, np.ones((len(pts), 1))])
        c = h @ vp.T
        z = c[:, 2]
        w = np.where(np.abs(z) < 1e-6, 1e-6, -z)
        x = c[:, 0] / w
        y = c[:, 1] / w
        px = (x * 0.5 + 0.5) * W
        py = (1 - (y * 0.5 + 0.5)) * H
        return np.stack([px, py, z], axis=1)

    order = sorted(range(len(tris)), key=lambda i: MAT_LOOK.get(tris[i][0], (None,))[0] is not None)
    # opaque first, transparent last
    opaque = [t for t in tris if MAT_LOOK.get(t[0], (0, 0, 0, 1))[3] >= 0.99]
    transparent = [t for t in tris if MAT_LOOK.get(t[0], (0, 0, 0, 1))[3] < 0.99]

    def draw(batch, sort_transparent):
        items = []
        for mat, A, B, C, NA, NB, NC in batch:
            n = len(A)
            if n == 0:
                continue
            pts = np.stack([A, B, C], axis=1).reshape(-1, 3)
            P = project(pts).reshape(n, 3, 3)
            keep = np.all(P[:, :, 2] < -0.05, axis=1)
            if not keep.any():
                continue
            P = P[keep]
            NA2, NB2, NC2 = NA[keep], NB[keep], NC[keep]
            area = (P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - \
                   (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])
            valid = np.abs(area) > 1e-9
            for i in np.nonzero(valid)[0]:
                items.append((P[i, :, 2].mean(), mat, P[i], NA2[i], NB2[i], NC2[i]))
        if sort_transparent:
            items.sort(key=lambda it: it[0])
        for _z, mat, p, na, nb, nc in items:
            _raster(mat, p, na, nb, nc, color, alpha, depth)

    draw(opaque, False)
    if not beam:
        transparent = [t for t in transparent if t[0] != "beam"]
    draw(transparent, True)

    img = (np.clip(color, 0, 1) * 255).astype(np.uint8)
    out = Image.fromarray(img, "RGB")
    if ss > 1:
        out = out.resize((size, size), Image.LANCZOS)
    if return_alpha:
        a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        a_img = Image.fromarray(a, "L")
        if ss > 1:
            a_img = a_img.resize((size, size), Image.LANCZOS)
        out = out.convert("RGBA")
        out.putalpha(a_img)
    return out


def _sd_ground_shadow(img, eye, target, fov, size):
    pass


def _raster(mat, p, na, nb, nc, color, alpha, depth):
    look = MAT_LOOK.get(mat)
    if look is None:
        return
    base = np.array(look[0], dtype=np.float32)
    gloss = look[1]
    emissive = look[2]
    opacity = look[3]

    H, W = color.shape[:2]
    xmin = max(int(math.floor(p[:, 0].min())), 0)
    xmax = min(int(math.ceil(p[:, 0].max())), W - 1)
    ymin = max(int(math.floor(p[:, 1].min())), 0)
    ymax = min(int(math.ceil(p[:, 1].max())), H - 1)
    if xmax < xmin or ymax < ymin:
        return
    xs = np.arange(xmin, xmax + 1) + 0.5
    ys = np.arange(ymin, ymax + 1) + 0.5
    gx, gy = np.meshgrid(xs, ys)
    x0, y0 = p[0, 0], p[0, 1]
    x1, y1 = p[1, 0], p[1, 1]
    x2, y2 = p[2, 0], p[2, 1]
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 1e-9:
        return
    w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / denom
    w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / denom
    w2 = 1.0 - w0 - w1
    mask = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not mask.any():
        return
    z = w0 * p[0, 2] + w1 * p[1, 2] + w2 * p[2, 2]
    zbuf = depth[ymin:ymax + 1, xmin:xmax + 1]
    # camera looks down -Z, larger z = closer
    closer = mask & (z > zbuf)
    if not closer.any():
        return

    n = (na[None, :] * w0[..., None] + nb[None, :] * w1[..., None] + nc[None, :] * w2[..., None])
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    lam = np.clip(n @ LIGHT_KEY, 0, 1)
    fill = np.clip(n @ LIGHT_FILL, 0, 1)
    view_dir = np.array([0.0, 0.0, -1.0])
    half = LIGHT_KEY + view_dir
    half /= np.linalg.norm(half)
    spec = np.clip(n @ half, 0, 1) ** (8 + 90 * gloss)
    fres = np.clip(1.0 - np.abs(n @ view_dir), 0, 1) ** 3

    shade = (0.30 + 0.78 * lam + 0.20 * fill)[..., None] * base[None, None, :]
    shade = shade + (spec * gloss * 0.85)[..., None]
    shade = shade + fres[..., None] * 0.16 * base[None, None, :]
    if emissive > 0:
        shade = shade + base[None, None, :] * emissive * 0.45
    shade = np.clip(shade, 0, 1)

    sub_color = color[ymin:ymax + 1, xmin:xmax + 1]
    sub_alpha = alpha[ymin:ymax + 1, xmin:xmax + 1]
    sel = closer
    if opacity >= 0.99:
        sub_color[sel] = shade[sel]
        sub_alpha[sel] = 1.0
        zbuf[sel] = z[sel]
    else:
        a = opacity
        sub_color[sel] = sub_color[sel] * (1 - a) + shade[sel] * a
        sub_alpha[sel] = 1.0
        zbuf[sel] = np.maximum(zbuf[sel], z[sel])


def add_shadow(img, center=(0, 0, 0), radius=2.6, strength=0.28):
    """Cheap contact shadow: soft ellipse under the craft in screen space."""
    w, h = img.size
    arr = np.array(img).astype(np.float32) / 255.0
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * 0.5, h * 0.80
    d = np.sqrt(((xx - cx) / (w * 0.30)) ** 2 + ((yy - cy) / (h * 0.055)) ** 2)
    mask = np.clip(1.0 - d, 0, 1) ** 1.6 * strength
    arr = arr * (1 - mask[..., None])
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB")


def icon(size=512, beam=False):
    img = render(size=size, eye=(6.2, 3.1, 9.0), target=(0, 1.12, 0), fov=36, ss=2, beam=beam)
    img = add_shadow(img)
    return img


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    os.makedirs(os.path.join(repo, "docs", "renders"), exist_ok=True)
    icon(700).save(os.path.join(repo, "build", "preview_icon.png"))
    render(size=900, eye=(8.2, 5.0, 9.6), target=(0, 1.1, 0), fov=36, ss=2).save(
        os.path.join(repo, "docs", "renders", "ufo_hero.png"))
    print("rendered")
