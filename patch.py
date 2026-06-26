#!/usr/bin/env python3
# Usage: ./patch <project> [--dry-run]
# Example: ./patch duckstation
#
# Reads patches/<project>/*.toml from the patches/ folder.
# The first comment of each toml defines its target file:
#   # src/core/achievements.cpp
#
# To compile:
#   pyinstaller --onefile --add-data "patches:patches" patch.py

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def get_patches_dir() -> Path:
    """
    Returns the patches/ directory, whether running as a script or a
    pyinstaller-compiled binary.

    Returns:
        Path to the patches/ directory.
    """
    import os
    if getattr(sys, "frozen", False):
        # running as pyinstaller binary: files are extracted to _MEIPASS
        base = Path(sys._MEIPASS)
    else:
        # running as plain script
        base = Path(__file__).parent
    return base / "patches"


def get_target(toml_content: str) -> str | None:
    """
    Reads the target file path from the first comment in a toml string.

    Args:
        toml_content: The toml content to read.

    Returns:
        The target file path, or None if no comment was found.
    """
    for line in toml_content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def apply(toml_content: str, target: Path, dry_run: bool) -> bool:
    """
    Applies a comby patch from a toml string to a target file.

    Args:
        toml_content: The toml patch content.
        target: The file to patch.
        dry_run: If True, shows diff without modifying the file.

    Returns:
        True if comby exited successfully, False otherwise.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml",
                                     delete=False, encoding="utf-8") as tmp:
        tmp.write(toml_content)
        tmp_path = tmp.name

    try:
        cmd = ["comby", "-config", tmp_path, "-f", str(target)]
        if not dry_run:
            cmd.append("-in-place")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout.strip():
            print(result.stdout.strip())

        return result.returncode == 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main():
    patches_dir = get_patches_dir()

    available = sorted(p.name for p in patches_dir.iterdir() if p.is_dir()) \
        if patches_dir.is_dir() else []

    parser = argparse.ArgumentParser(prog="patch")
    parser.add_argument("project", help=f"Project to patch. Available: {', '.join(available)}")
    parser.add_argument("--dry-run", action="store_true", help="Show diff without modifying files")
    args = parser.parse_args()

    project_dir = patches_dir / args.project
    if not project_dir.is_dir():
        print(f"Project '{args.project}' not found.")
        print(f"Available: {', '.join(available)}")
        sys.exit(1)

    toml_files = sorted(project_dir.glob("*.toml"))
    if not toml_files:
        print(f"No .toml files found in {project_dir}")
        sys.exit(0)

    repo = Path(".").resolve()
    ok = fail = 0

    print(f"{args.project} -- {len(toml_files)} patch(es) in {repo}\n")

    for toml_file in toml_files:
        toml_content = toml_file.read_text(encoding="utf-8")
        target_rel = get_target(toml_content)

        if not target_rel:
            print(f"{toml_file.name}: no path comment found, skipping.")
            continue

        target = repo / target_rel
        if not target.exists():
            print(f"{toml_file.name}: file not found: {target_rel}")
            fail += 1
            continue

        label = "dry-run" if args.dry_run else "patching"
        print(f"> {toml_file.name} -> {target_rel} ({label})")

        if apply(toml_content, target, args.dry_run):
            print("  done!")
            ok += 1
        else:
            print("  failed.")
            fail += 1

    print(f"\n{ok} ok  {fail} failed")


if __name__ == "__main__":
    main()
