#!/usr/bin/env python3
# Usage: python patch.py <source_code> [--dry-run]
# Example:  python patch.py duckstation
#
# Reads patches/duckstation/*.toml
# The first comentary on each toml defines its file:
#   # src/core/achievements.cpp
# Will patch (from source core)/src/core/achievements.cpp

import argparse
import subprocess
import sys
from pathlib import Path

PATCHES_DIR = Path(__file__).parent / "patches"


def get_target(toml_path: Path) -> str | None:
    """
    Gets the target file from the toml.

    Args:
        toml_path:
            The toml to read.
    
    Returns:
        str:
            The file to be patched.
        None:
            No path could be found.
    """

    for line in toml_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def apply(toml_path: Path, target: Path, dry_run: bool) -> bool:
    """
    Applies a patch using comby.

    Args:
        toml_path:
            The toml to read.
        target:
            The file to be patched
        dry_run:
            Run without patching.
    
    Returns:
        bool:
            Operation failed or not.
    """

    cmd = ["comby", "-config", str(toml_path), "-f", str(target)]
    if not dry_run:
        cmd.append("-in-place")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout.strip():
        print(result.stdout.strip())

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Source code name (ex: duckstation)")
    parser.add_argument("--dry-run", action="store_true", help="Shows diff without patching")
    args = parser.parse_args()

    patches_dir = PATCHES_DIR / args.project
    if not patches_dir.is_dir():
        print(f"Folder couldn't be found: {patches_dir}")
        sys.exit(1)

    toml_files = sorted(patches_dir.glob("*.toml"))
    if not toml_files:
        print(f"No toml on: {patches_dir}")
        sys.exit(0)

    repo = Path(".").resolve()
    ok = fail = 0

    for toml in toml_files:
        target_rel = get_target(toml)
        if not target_rel:
            print(f"{toml.name}: no path commentary, skipping.")
            continue

        target = repo / target_rel
        if not target.exists():
            print(f"{toml.name}: file couldn't be found: {target_rel}")
            fail += 1
            continue

        label = "dry-run" if args.dry_run else "patching"
        print(f"> {toml.name} -> {target_rel} ({label})")

        if apply(toml, target, args.dry_run):
            print("done!")
            ok += 1
        else:
            print("failed :()")
            fail += 1

    print(f"\n{ok} ok  {fail} failed")


if __name__ == "__main__":
    main()
