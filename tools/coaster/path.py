#!/usr/bin/env python3
"""Parametric route and rotation-minimising frames for Höhensturm.

The same equally-spaced closed point list is exported as the train-system
spline and used for the visible track.  The script specialization samples the
engine spline and builds the same kind of parallel-transport frame at runtime;
that is what lets the car bank and invert through the vertical loops.
"""

import math

STEP = 0.55


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def mul(a, s):
    return tuple(x * s for x in a)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def unit(a, fallback=(0.0, 1.0, 0.0)):
    n = length(a)
    if n < 1e-10:
        return fallback
    return mul(a, 1.0 / n)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def bezier_point(p0, p1, p2, p3, t):
    u = 1.0 - t
    return tuple(
        u * u * u * p0[i] + 3.0 * u * u * t * p1[i]
        + 3.0 * u * t * t * p2[i] + t * t * t * p3[i]
        for i in range(3)
    )


def append_samples(raw, points, tag):
    for p in points:
        p = tuple(float(v) for v in p)
        if raw and length(sub(p, raw[-1][0])) < 1e-7:
            continue
        raw.append((p, tag))


def line(raw, a, b, tag, step=STEP):
    n = max(2, int(math.ceil(length(sub(b, a)) / step)))
    append_samples(raw, [lerp(a, b, i / n) for i in range(n + 1)], tag)


def curve(raw, p0, p1, p2, p3, tag, step=STEP):
    # Control polygon length slightly overestimates the final Bezier length.
    estimate = sum(length(sub(a, b)) for a, b in zip((p0, p1, p2), (p1, p2, p3)))
    n = max(24, int(math.ceil(estimate / step)))
    append_samples(raw, [bezier_point(p0, p1, p2, p3, i / n)
                         for i in range(n + 1)], tag)


def loop(raw, x, bottom_y, z0, radius, advance, tag, step=STEP):
    """Heartline-style vertical loop, advanced along the track to avoid overlap."""
    estimate = 2.0 * math.pi * math.sqrt(radius * radius + (advance / (2.0 * math.pi)) ** 2)
    n = max(128, int(math.ceil(estimate / step)))
    pts = []
    for i in range(n + 1):
        theta = 2.0 * math.pi * i / n
        y = bottom_y + radius * (1.0 - math.cos(theta))
        z = z0 + radius * math.sin(theta) + advance * i / n
        pts.append((x, y, z))
    append_samples(raw, pts, tag)


def helix(raw, cx, cz, radius, start_y, rise, start_angle, turns, reverse, tag, step=STEP):
    """A rising 3-D helix; reverse chooses which way the entry tangent points."""
    estimate = math.hypot(2.0 * math.pi * radius * turns, rise)
    n = max(256, int(math.ceil(estimate / step)))
    pts = []
    direction = -1.0 if reverse else 1.0
    for i in range(n + 1):
        u = i / n
        theta = start_angle + direction * 2.0 * math.pi * turns * u
        x = cx + radius * math.cos(theta)
        z = cz + radius * math.sin(theta)
        y = start_y + rise * u
        pts.append((x, y, z))
    append_samples(raw, pts, tag)


def _resample_closed(raw, step=STEP):
    if len(raw) < 4:
        raise ValueError("route needs at least four points")
    points = [item[0] for item in raw]
    tags = [item[1] for item in raw]
    if length(sub(points[0], points[-1])) < 1e-5:
        points.pop()
        tags.pop()
    segments = []
    cumulative = [0.0]
    total = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        d = length(sub(points[j], points[i]))
        if d < 1e-7:
            continue
        # The label of an edge is the route section that supplied its end.
        edge_tag = tags[j] if j != 0 else tags[0]
        segments.append((total, total + d, points[i], points[j], edge_tag))
        total += d
        cumulative.append(total)
    count = max(64, int(math.ceil(total / step)))
    spacing = total / count
    output, output_tags = [], []
    seg_i = 0
    for k in range(count):
        d = k * spacing
        while seg_i + 1 < len(segments) and d >= segments[seg_i][1]:
            seg_i += 1
        start_d, end_d, a, b, tag = segments[seg_i]
        f = (d - start_d) / max(end_d - start_d, 1e-9)
        output.append(lerp(a, b, f))
        output_tags.append(tag)
    return output, output_tags, total


def build_route(step=STEP):
    """Return (points, labels, distance, landmarks) in local placeable coordinates."""
    raw = []
    station = (0.0, 2.5, 0.0)
    line(raw, station, (0.0, 2.5, 25.0), "station")

    # A 55.5 m lift hill, then a long, steep first drop.
    curve(raw, (0.0, 2.5, 25.0), (0.0, 2.5, 54.0),
          (0.0, 58.0, 76.0), (0.0, 58.0, 105.0), "lift")
    curve(raw, (0.0, 58.0, 105.0), (0.0, 58.0, 122.0),
          (0.0, 10.5, 141.0), (0.0, 7.0, 155.0), "firstDrop")

    # First 360-degree vertical inversion.  The 11 m heartline advance keeps
    # its entrance and exit separate while preserving matching tangents.
    curve(raw, (0.0, 7.0, 155.0), (0.0, 7.0, 165.0),
          (20.0, 7.0, 170.0), (20.0, 7.0, 180.0), "loop1Lead")
    loop(raw, 20.0, 7.0, 180.0, 15.5, 11.0, "loop1", step)
    line(raw, (20.0, 7.0, 191.0), (20.0, 7.0, 214.0), "loop1Exit")

    # A rising 1.5-turn helix/corkscrew, 26 m of vertical gain.
    helix(raw, cx=38.0, cz=230.0, radius=18.0, start_y=7.0, rise=26.0,
          start_angle=math.pi, turns=1.5, reverse=True, tag="spiral", step=step)

    # Sweep out of the spiral, descend, and enter the second vertical loop.
    curve(raw, (56.0, 33.0, 230.0), (56.0, 33.0, 211.0),
          (60.0, 7.0, 250.0), (60.0, 7.0, 270.0), "loop2Lead")
    loop(raw, 60.0, 7.0, 270.0, 12.5, 9.0, "loop2", step)

    # Return rail and station approach complete one closed, manually driven lap.
    curve(raw, (60.0, 7.0, 279.0), (60.0, 7.0, 299.0),
          (80.0, 5.0, 286.0), (80.0, 5.0, 250.0), "returnTurn")
    line(raw, (80.0, 5.0, 250.0), (80.0, 4.0, 35.0), "return")
    curve(raw, (80.0, 4.0, 35.0), (80.0, 4.0, -5.0),
          (0.0, 2.5, -55.0), (0.0, 2.5, -30.0), "stationTurn")
    line(raw, (0.0, 2.5, -30.0), station, "station")

    points, labels, total = _resample_closed(raw, step=step)
    landmarks = {
        "station": station,
        "liftTop": (0.0, 58.0, 105.0),
        "loop1Bottom": (20.0, 7.0, 180.0),
        "loop1Top": (20.0, 38.0, 185.5),
        "spiralTop": (56.0, 33.0, 230.0),
        "loop2Bottom": (60.0, 7.0, 270.0),
        "loop2Top": (60.0, 32.0, 274.5),
    }
    return points, labels, total, landmarks


def _rotate_axis(v, axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    return add(add(mul(v, c), mul(cross(axis, v), s)),
               mul(axis, dot(axis, v) * (1.0 - c)))


def _project_up(up, tangent):
    return unit(sub(up, mul(tangent, dot(up, tangent))), fallback=(1.0, 0.0, 0.0))


def parallel_transport_frames(points):
    """Build a closed, seam-corrected, rotation-minimising track frame."""
    n = len(points)
    tangents = []
    for i in range(n):
        tangents.append(unit(sub(points[(i + 1) % n], points[(i - 1) % n]),
                             fallback=(0.0, 0.0, 1.0)))

    seed = (0.0, 1.0, 0.0)
    if abs(dot(seed, tangents[0])) > 0.94:
        seed = (1.0, 0.0, 0.0)
    ups = [_project_up(seed, tangents[0])]

    for i in range(1, n):
        prev_t, cur_t = tangents[i - 1], tangents[i]
        axis_v = cross(prev_t, cur_t)
        axis_len = length(axis_v)
        cosine = max(-1.0, min(1.0, dot(prev_t, cur_t)))
        if axis_len < 1e-10:
            candidate = ups[-1]
        else:
            candidate = _rotate_axis(ups[-1], mul(axis_v, 1.0 / axis_len),
                                     math.atan2(axis_len, cosine))
        ups.append(_project_up(candidate, cur_t))

    # Carry the final frame across the closing segment and distribute any
    # accumulated holonomy over the lap, so station orientation has no snap.
    axis_v = cross(tangents[-1], tangents[0])
    axis_len = length(axis_v)
    cosine = max(-1.0, min(1.0, dot(tangents[-1], tangents[0])))
    if axis_len < 1e-10:
        end_up = ups[-1]
    else:
        end_up = _rotate_axis(ups[-1], mul(axis_v, 1.0 / axis_len),
                              math.atan2(axis_len, cosine))
    end_up = _project_up(end_up, tangents[0])
    seam_angle = math.atan2(dot(tangents[0], cross(end_up, ups[0])),
                            max(-1.0, min(1.0, dot(end_up, ups[0]))))

    frames = []
    for i, (p, tangent, up) in enumerate(zip(points, tangents, ups)):
        corrected = _project_up(_rotate_axis(up, tangent, seam_angle * i / n), tangent)
        right = unit(cross(corrected, tangent), fallback=(1.0, 0.0, 0.0))
        # Recompute up to guarantee an orthonormal, right-handed basis.
        corrected = unit(cross(tangent, right), fallback=(0.0, 1.0, 0.0))
        frames.append({"point": p, "tangent": tangent, "up": corrected,
                       "right": right, "t": i / n})
    return frames


def nearest_index(points, target):
    return min(range(len(points)), key=lambda i: dot(sub(points[i], target), sub(points[i], target)))


def validate_route(points, frames, landmarks):
    ys = [p[1] for p in points]
    low, high = min(ys), max(ys)
    if high - low < 50.0:
        raise AssertionError("elevation difference %.2f m is below 50 m" % (high - low))
    if length(sub(points[0], points[-1])) > 1.5:
        raise AssertionError("closed route seam is too long")
    for name in ("loop1Top", "loop2Top"):
        i = nearest_index(points, landmarks[name])
        if frames[i]["up"][1] > -0.35:
            raise AssertionError("%s frame is not inverted (up=%r)" % (name, frames[i]["up"]))
    return {"minimumY": low, "maximumY": high, "elevationDifference": high - low,
            "length": sum(length(sub(points[(i + 1) % len(points)], points[i]))
                           for i in range(len(points)))}
