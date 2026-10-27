#!/usr/bin/env python3
"""Build the PC-only FS25 Höhensturm inversion coaster mod.

The native trainSystem supplies loading, renting, multiplayer position sync
and passenger boarding. The custom Lua specialization adds roll-aware inversion
frames, locks each manual dispatch into a full lap, and leaves native disconnect
cleanup intact so disconnected riders cannot remain as ghost occupants.
"""

from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
COASTER = TOOLS / "coaster"
UFO_TOOLS = TOOLS / "ufo"
BUILD_ROOT = ROOT / "build" / "rollercoaster"
MOD_DIR = BUILD_ROOT / "FS25_Hoehensturm"
DIST_ZIP = ROOT / "dist" / "FS25_Hoehensturm.zip"

sys.path.insert(0, str(COASTER))
sys.path.insert(0, str(UFO_TOOLS))

import model  # noqa: E402
import render  # noqa: E402
from path import (build_route, nearest_index, parallel_transport_frames,
                  validate_route)  # noqa: E402
from scene import (MATERIALS, build_car_scene, build_track_scene,
                  renderer_materials)  # noqa: E402
from coaster_sounds import generate as generate_coaster_sounds  # noqa: E402


def say(message: str) -> None:
    print("[rollercoaster] " + message, flush=True)


def replace_with_nurbs(inline_i3d: Path, points) -> int:
    text = inline_i3d.read_text(encoding="iso-8859-1")
    pattern = re.compile(
        r'<IndexedTriangleSet name="coasterSpline" shapeId="(\d+)"[^>]*>.*?</IndexedTriangleSet>',
        re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise RuntimeError("could not find the coasterSpline placeholder IndexedTriangleSet")
    shape_id = int(match.group(1))
    rows = ['      <NurbsCurve name="coasterSpline" shapeId="%d" type="linear" form="closed">' % shape_id]
    rows.extend('        <cv c="%.6f %.6f %.6f"/>' % tuple(p) for p in points)
    rows.append("      </NurbsCurve>")
    text = text[:match.start()] + "\n".join(rows) + text[match.end():]
    inline_i3d.write_text(text, encoding="iso-8859-1", newline="\n")
    return shape_id


def write_and_binarize(root, mappings, out_i3d: Path, inline_i3d: Path, points=None, asset_name="asset"):
    stats, i3d_mappings = model.write_i3d(root, str(inline_i3d), materials=MATERIALS, asset_name=asset_name)
    if points is not None:
        spline_id = replace_with_nurbs(inline_i3d, points)
        say("inserted closed linear spline shapeId=%d (%d control points)" % (spline_id, len(points)))
    else:
        spline_id = None
    out_i3d.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(TOOLS / "i3d" / "binarize_i3d.py"),
               str(inline_i3d), "--out", str(out_i3d), "--seed", "42"]
    proc = subprocess.run(command, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("I3D binarization failed:\n%s\n%s" % (proc.stdout, proc.stderr))
    say(proc.stdout.strip().replace("\n", " | "))
    return stats, i3d_mappings, spline_id


def make_store_image(points, labels, frames, track_root):
    render.MAT_LOOK.update(renderer_materials())
    # Compose a render-only copy with the four-seat vehicle at the station.
    hero = copy.deepcopy(track_root)
    car = build_car_scene()
    car.attrs["translation"] = "0 2.5 8.0"
    hero.add(car)

    png = MOD_DIR / "store_rollercoaster.png"
    docs_render = ROOT / "docs" / "renders" / "hohensturm_coaster_hero.png"
    docs_render.parent.mkdir(parents=True, exist_ok=True)
    # The viewpoint shows the full 1.1 km circuit, with the high loops and
    # station readable against the sky instead of cropping to the central loop.
    image = render.render(
        eye=(175.0, 118.0, 355.0), target=(29.0, 29.0, 128.0),
        size=1024, fov=48.0, ss=1, background="sky", root=hero,
    )
    image.save(png)
    image.save(docs_render)
    say("rendered store image %s (%s bytes)" % (png.name, png.stat().st_size))

    # Keep focused renders alongside the full-circuit view so the new hall and
    # inversion lighting are visible in the documentation, not just in the ZIP.
    station_detail = render.render(
        eye=(39.0, 27.0, 43.0), target=(0.0, 9.0, 9.0),
        size=1024, fov=52.0, ss=1, background="sky", root=hero,
    )
    station_detail.save(ROOT / "docs" / "renders" / "hohensturm_station_glass_detail.png")
    inversion_detail = render.render(
        eye=(124.0, 96.0, 305.0), target=(39.0, 23.0, 230.0),
        size=1024, fov=54.0, ss=1, background="sky", root=hero,
    )
    inversion_detail.save(ROOT / "docs" / "renders" / "hohensturm_coaster_detail.png")

    # The icon is a separate DDS required by modDesc; use the same authored PNG.
    image_tools = str(UFO_TOOLS)
    if image_tools not in sys.path:
        sys.path.insert(0, image_tools)
    import images  # noqa: E402
    icon_png = BUILD_ROOT / "icon_rollercoaster.png"
    icon = image.copy().resize((512, 512))
    icon.save(icon_png)
    images._dds(str(icon_png), str(MOD_DIR / "icon_rollercoaster.dds"), "bc1", sys.executable)


def write_mod_xml(track_mappings: str, car_mappings: str) -> None:
    shutil.copy2(COASTER / "modDesc.xml", MOD_DIR / "modDesc.xml")
    shutil.copy2(COASTER / "CoasterRoll.lua", MOD_DIR / "CoasterRoll.lua")

    placeable_template = (COASTER / "coasterSystem.template.xml").read_text(encoding="utf-8")
    if "__I3D_MAPPINGS__" not in placeable_template:
        raise RuntimeError("placeable XML template is missing the mapping placeholder")
    (MOD_DIR / "coasterSystem.xml").write_text(
        placeable_template.replace("__I3D_MAPPINGS__", track_mappings), encoding="utf-8")

    car_template = (COASTER / "coasterCar.template.xml").read_text(encoding="utf-8")
    if "__I3D_MAPPINGS__" not in car_template:
        raise RuntimeError("vehicle XML template is missing the mapping placeholder")
    (MOD_DIR / "coasterCar.xml").write_text(
        car_template.replace("__I3D_MAPPINGS__", car_mappings), encoding="utf-8")

    readme = """HÖHENSTURM — INVERSION COASTER (FS25)

PC ONLY. This mod requires CoasterRoll.lua; consoles are not supported.
For multiplayer, the server and every joining PC player must have the same mod.

INSTALL
1. Copy FS25_Hoehensturm.zip to the Farming Simulator 25 mods folder.
2. Enable it in the savegame mod list.
3. In the construction menu, place Höhensturm — Inversion Coaster.
   It is one large installation; allow approximately 180 x 370 m of clear ground.
4. At the station's train marker, rent the train and enter the front-left driver seat.
5. Tap accelerate to dispatch. Once the car moves, Lua locks it into an automatic
   full lap back to the station; braking, reversing, and all rider exits stay
   disabled en route. Wait for the full stop before leaving. Three passengers
   can ride in the same 2 x 2 car.

RIDE SPECIFICATIONS
- Track elevation: 2.5 m to about 58 m (over 55 m of vertical difference)
- Two full vertical loops plus a rising 1.5-turn spiral
- Manual dispatch; automatic full-lap return at up to 120 km/h
- Four total seats: one driver and three passengers
- A glass-vaulted station, cyan/violet LED tunnels at both loops and the rising spiral
- Original synthesized motor, fast whine, rail-air, dispatch-start and stop sounds
- Multiplayer co-riding uses the native FS25 passenger-seat system

MULTIPLAYER SAFETY
- Riders can exit individually after the train stops; no driver action is needed.
- A disconnected passenger is cleaned up through FS25's native seat/player cleanup.
- If the driver disconnects mid-lap, the coaster reasserts its station target and continues.
- If the host/server session itself ends, FS25 ends the whole multiplayer session.

The trainSystem spline handles movement and network updates. The Lua script
adds a closed rotation-minimising frame so the vehicle follows the track's roll
through both inversions and returns smoothly to upright at the station. It also
locks the locomotive and all rider exits for the duration of each dispatched lap.
"""
    (MOD_DIR / "README.txt").write_text(readme, encoding="utf-8")


def validate_mod(track_mappings: str, car_mappings: str, points, labels, frames, landmarks):
    metrics = validate_route(points, frames, landmarks)
    if metrics["elevationDifference"] < 50:
        raise AssertionError("track elevation difference is below requirement")
    if not any(label == "spiral" for label in labels):
        raise AssertionError("spiral segment was not generated")

    for filename in ("modDesc.xml", "coasterSystem.xml", "coasterCar.xml"):
        ET.parse(MOD_DIR / filename)
    mod = ET.parse(MOD_DIR / "modDesc.xml").getroot()
    placeable = ET.parse(MOD_DIR / "coasterSystem.xml").getroot()
    vehicle = ET.parse(MOD_DIR / "coasterCar.xml").getroot()
    assert mod.find("./multiplayer").get("supported") == "true"
    assert mod.find("./specializations/specialization[@name='coasterRoll']") is not None
    l10n = {text.get("name") for text in mod.findall("./l10n/text")}
    assert {"rollercoaster_name", "rollercoaster_function",
            "rollercoaster_car_name", "rollercoaster_type_desc",
            "hotspot_rentTrain"} <= l10n
    assert placeable.get("type") == "trainSystem"
    assert placeable.find("./trainSystem/spline").get("node") == "coasterSpline"
    assert len(placeable.findall("./trainSystem/train/vehicle")) == 1
    assert vehicle.find("./splineVehicle/dollies") is not None
    seats = vehicle.findall("./enterable/passengerSeats/passengerSeat")
    assert len(seats) == 3, "driver + three passenger places must total four"
    assert vehicle.find("./enterable/characterNode") is not None

    def mapping_ids(xml_root):
        return {e.get("id") for e in xml_root.findall("./i3dMappings/i3dMapping")}

    track_ids, car_ids = mapping_ids(placeable), mapping_ids(vehicle)
    required_track = {"coasterSpline", "rentMarker", "teleportNode", "placementStart", "placementEnd",
                      "clearStart", "clearWidth", "clearHeight"}
    required_car = {"frontNode", "backNode", "dollyFrontNode", "dollyBackNode", "exitPoint",
                    "enterNode", "driverSeatNode", "outdoorCamera", "indoorCamera"}
    if not required_track <= track_ids:
        raise AssertionError("missing track mappings: %s" % sorted(required_track - track_ids))
    if not required_car <= car_ids:
        raise AssertionError("missing car mappings: %s" % sorted(required_car - car_ids))
    for i in range(1, 4):
        prefix = "passengerSeat%02d" % i
        expected = {prefix, prefix + "PlayerSkin", prefix + "PlayerLeftHand", prefix + "PlayerRightHand",
                    prefix + "PlayerLeftFoot", prefix + "PlayerRightFoot", prefix + "ExitPoint", prefix + "Camera"}
        if not expected <= car_ids:
            raise AssertionError("missing %s mappings: %s" % (prefix, sorted(expected - car_ids)))

    track_i3d = ET.parse(MOD_DIR / "coaster.i3d").getroot()
    car_i3d = ET.parse(MOD_DIR / "coasterCar.i3d").getroot()
    track_scene_nodes = {node.get("name"): node for node in track_i3d.find("Scene").iter()
                         if node.get("name") is not None}
    for required in ("stationGlass", "stationLEDs", "inversionLightTunnels", "rideEffectLights"):
        if required not in track_scene_nodes:
            raise AssertionError("missing generated atmosphere node %s" % required)
    dynamic_lights = [node for node in track_i3d.find("Scene").iter()
                      if node.tag == "Light"]
    if len(dynamic_lights) < 9:
        raise AssertionError("expected station and inversion point lights, got %d" % len(dynamic_lights))
    glass_material = track_i3d.find("./Materials/Material[@name='glassBlue']")
    if glass_material is None or glass_material.get("alphaBlending") != "true":
        raise AssertionError("station glass material must be alpha blended")

    scene_nodes = {node.get("name"): node for node in car_i3d.find("Scene").iter()
                   if node.get("name") is not None}
    seat_layout = {
        "driverSeatNode": (0.48, 0.62),
        "passengerSeat01": (-0.48, 0.62),
        "passengerSeat02": (0.48, -0.57),
        "passengerSeat03": (-0.48, -0.57),
    }
    for name, (expected_x, expected_z) in seat_layout.items():
        coords = tuple(float(v) for v in scene_nodes[name].get("translation").split())
        if abs(coords[0] - expected_x) > 0.01 or abs(coords[2] - expected_z) > 0.01:
            raise AssertionError("%s is not in the intended 2x2 seat position: %r" % (name, coords))
    for i3d, expected_curve in ((track_i3d, True), (car_i3d, False)):
        shapes = i3d.find("Shapes")
        assert shapes is not None and shapes.get("externalShapesFile")
        assert (shapes.get("externalShapesFile") == "coaster.i3d.shapes") if expected_curve else (shapes.get("externalShapesFile") == "coasterCar.i3d.shapes")
    track_shapes = MOD_DIR / "coaster.i3d.shapes"
    car_shapes = MOD_DIR / "coasterCar.i3d.shapes"
    assert track_shapes.is_file() and track_shapes.stat().st_size > 1024
    assert car_shapes.is_file() and car_shapes.stat().st_size > 1024
    assert (MOD_DIR / "CoasterRoll.lua").is_file()
    assert (MOD_DIR / "store_rollercoaster.png").is_file()
    assert (MOD_DIR / "icon_rollercoaster.dds").is_file()
    for filename in ("coasterIdle.ogg", "coasterWhine.ogg", "coasterAirRush.ogg",
                     "coasterStart.ogg", "coasterStop.ogg"):
        audio_path = MOD_DIR / "sounds" / filename
        if not audio_path.is_file() or audio_path.stat().st_size < 1024:
            raise AssertionError("missing or incomplete coaster sound: %s" % filename)

    say("validated %.1f m elevation difference, %.1f m route, %d spline points, 4 seats" %
        (metrics["elevationDifference"], metrics["length"], len(points)))
    return metrics


def make_zip() -> None:
    DIST_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if DIST_ZIP.exists():
        DIST_ZIP.unlink()
    with zipfile.ZipFile(DIST_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for path in sorted(MOD_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(MOD_DIR).as_posix())
    say("wrote %s (%0.2f MiB)" % (DIST_ZIP.relative_to(ROOT), DIST_ZIP.stat().st_size / 1024 / 1024))


def main() -> None:
    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    MOD_DIR.mkdir(parents=True)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)

    points, labels, route_length, landmarks = build_route()
    frames = parallel_transport_frames(points)
    metrics = validate_route(points, frames, landmarks)
    say("route: %d uniform points, %.1f m, height %.1f–%.1f m (%.1f m delta)" %
        (len(points), route_length, metrics["minimumY"], metrics["maximumY"], metrics["elevationDifference"]))

    track_root, _ = build_track_scene(points, labels, frames)
    car_root = build_car_scene()
    track_inline = BUILD_ROOT / "coaster_inline.i3d"
    car_inline = BUILD_ROOT / "coasterCar_inline.i3d"
    track_i3d = MOD_DIR / "coaster.i3d"
    car_i3d = MOD_DIR / "coasterCar.i3d"

    _, track_mappings, spline_id = write_and_binarize(
        track_root, None, track_i3d, track_inline, points=points, asset_name="Hoehensturm Coaster")
    _, car_mappings, _ = write_and_binarize(
        car_root, None, car_i3d, car_inline, points=None, asset_name="Hoehensturm Coaster Car")
    write_mod_xml(track_mappings, car_mappings)
    generate_coaster_sounds(MOD_DIR / "sounds")
    make_store_image(points, labels, frames, track_root)
    validate_mod(track_mappings, car_mappings, points, labels, frames, landmarks)
    make_zip()


if __name__ == "__main__":
    main()
