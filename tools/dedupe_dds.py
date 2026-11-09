#!/usr/bin/env python3
"""Deduplicate byte-identical DDS textures in a generated mod folder.

Only exact byte-for-byte DDS duplicates that are referenced by the mod's XML/
I3D files are considered. The source paths are rewritten before the redundant
copy is removed; Lua files are checked for explicit dynamic references and are
never silently broken.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import defaultdict
from pathlib import Path

TEXT_EXTENSIONS = {".xml", ".i3d", ".lua", ".txt"}
STATIC_EXTENSIONS = {".xml", ".i3d"}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_text_files(root: Path) -> dict[Path, str]:
    out = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            try:
                out[path] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return out


def dedupe_dds(root: str | os.PathLike[str]) -> list[tuple[str, str]]:
    """Rewrite references and remove safe exact DDS duplicates under *root*.

    Returns a list of (removed relative path, canonical relative path) pairs.
    """
    mod_root = Path(root).resolve()
    if not mod_root.is_dir():
        raise FileNotFoundError(f"mod folder does not exist: {mod_root}")

    groups: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(mod_root.rglob("*.dds")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        groups[digest].append(path)

    text_files = _read_text_files(mod_root)
    rewritten: list[tuple[str, str]] = []
    for paths in groups.values():
        if len(paths) < 2:
            continue

        # Prefer the path already used most often by static XML/I3D references;
        # lexical order provides a stable tie-breaker for reproducible builds.
        def score(path: Path) -> tuple[int, str]:
            rel = _relative(path, mod_root)
            refs = sum(text.count(rel) + text.count(rel.replace("/", "\\"))
                       for file, text in text_files.items()
                       if file.suffix.lower() in STATIC_EXTENSIONS)
            return (-refs, rel)

        canonical = min(paths, key=score)
        canonical_rel = _relative(canonical, mod_root)
        for duplicate in paths:
            if duplicate == canonical:
                continue
            duplicate_rel = _relative(duplicate, mod_root)
            # Keep assets whose exact path is constructed or referenced by Lua;
            # this helper only rewrites explicit XML/I3D paths.
            stem = duplicate.stem.lower()
            dynamic_ref = any(stem in text.lower() for file, text in text_files.items()
                              if file.suffix.lower() == ".lua")
            static_ref = any(duplicate_rel in text or duplicate_rel.replace("/", "\\") in text
                             for file, text in text_files.items()
                             if file.suffix.lower() in STATIC_EXTENSIONS)
            if dynamic_ref or not static_ref:
                continue

            updated: dict[Path, str] = {}
            for file, text in text_files.items():
                new_text = text.replace(duplicate_rel, canonical_rel)
                new_text = new_text.replace(duplicate_rel.replace("/", "\\"),
                                            canonical_rel.replace("/", "\\"))
                if new_text != text:
                    updated[file] = new_text

            # Do not remove a copy if any remaining text file still mentions its
            # path; such a reference may be dynamic or outside XML/I3D.
            if any(duplicate_rel in text or duplicate_rel.replace("/", "\\") in text
                   for text in updated.values()):
                continue

            for file, text in updated.items():
                file.write_text(text, encoding="utf-8", newline="\n")
                text_files[file] = text
            duplicate.unlink()
            rewritten.append((duplicate_rel, canonical_rel))

    return rewritten


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod_folder", help="generated, unpacked mod directory")
    args = parser.parse_args(argv)
    removed = dedupe_dds(args.mod_folder)
    if removed:
        print(f"DDS dedupe: removed {len(removed)} exact duplicate(s)")
        for old, new in removed:
            print(f"  {old} -> {new}")
    else:
        print("DDS dedupe: no safe exact duplicates found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
