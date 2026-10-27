#!/usr/bin/env python3
"""Check localization references and external translation paths in FS25 ZIPs.

Run from the repository root:
    python tools/test_localization_paths.py
"""

from pathlib import Path
from zipfile import BadZipFile, ZipFile
import argparse
import re
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
EXPECTED_PREFIX = "translations/translation"
BASE_GAME_KEYS = {
    "brand_lizard",
    "configuration_valueDefault",
    "info_transmission_automatic",
    "info_transmission_manual",
    "unit_kilogramShort",
    "unit_kmh",
    "unit_liter",
    "unit_literShort",
    "unit_meterShort",
}


def check_archive(path):
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            mod_desc = ET.fromstring(archive.read("modDesc.xml"))
            language_files = sorted(
                name for name in names
                if name.startswith("translations/translation_") and name.endswith(".xml")
            )
            if language_files:
                l10n = mod_desc.find("l10n")
                if l10n is None or l10n.get("filenamePrefix") != EXPECTED_PREFIX:
                    return (f"{path.name}: external translations exist, but modDesc.xml "
                            f"does not declare filenamePrefix=\"{EXPECTED_PREFIX}\"")
                for lang in ("de", "en"):
                    expected_file = f"{EXPECTED_PREFIX}_{lang}.xml"
                    if expected_file not in names:
                        return f"{path.name}: missing {expected_file}"

            keys = {
                text.get("name")
                for text in mod_desc.findall("./l10n/text")
                if text.get("name")
            }
            for name in language_files:
                root = ET.fromstring(archive.read(name))
                if root.tag != "l10n":
                    return f"{path.name}: {name} does not have an <l10n> root"
                keys.update(text.get("name") for text in root.iter("text")
                            if text.get("name"))

            used = set()
            for name in names:
                if not name.endswith(".xml") or name.startswith("translations/"):
                    continue
                try:
                    text = archive.read(name).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                used.update(re.findall(r"\$l10n_([A-Za-z0-9_]+)", text))

            missing = sorted(used - keys - BASE_GAME_KEYS)
            if missing:
                return f"{path.name}: missing localization keys: {', '.join(missing)}"

            suffix = (f"; {len(language_files)} external language files registered"
                      if language_files else "; inline translations found")
            print(f"OK  {path.name}: local XML keys resolve{suffix}")
            return None
    except (BadZipFile, KeyError, ET.ParseError) as error:
        return f"{path.name}: could not inspect localization files: {error}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=REPO / "dist",
                        help="directory containing FS25 mod ZIP packages")
    args = parser.parse_args()
    archives = sorted(args.dist.glob("FS25_*.zip"))
    if not archives:
        print(f"No FS25 mod ZIP packages found in {args.dist}", file=sys.stderr)
        return 2

    errors = [error for archive in archives if (error := check_archive(archive))]
    for error in errors:
        print("FAIL " + error, file=sys.stderr)
    if errors:
        return 1
    print(f"Localization check passed for all {len(archives)} mod packages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
