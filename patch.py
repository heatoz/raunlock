#!/usr/bin/env python3
# Usage: ./patch <project> [--dry-run]
# Example: ./patch duckstation
#
# Reads patches/<project>/*.toml from the patches/ folder.
# The first comment of each toml defines its target file:
#   # src/core/achievements.cpp
#
# Each [section] in the toml has a match and rewrite key.
# Matching is done by exact string search after normalizing whitespace:
#   - Leading/trailing whitespace per line is preserved in the match
#   - The match string is searched verbatim in the source file
#   - If not found, indentation is auto-detected and retried
#
# To compile:
#   pyinstaller --onefile --add-data "patches:patches" patch.py

import argparse
import difflib
import re
import sys
from pathlib import Path


def get_patches_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / "patches"


def get_target(toml_content: str) -> str | None:
    for line in toml_content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def parse_sections(toml_content: str) -> list[tuple[str, str, str]]:
    """
    Parses a toml string into a list of (section_name, match, rewrite) tuples.
    Handles triple-quoted strings (both ''' and \"\"\").
    """
    sections = []
    # Strip the header comment line(s)
    lines = toml_content.splitlines(keepends=True)

    # Join back and use regex to extract sections
    text = "".join(lines)

    # Find all [section] headers
    header_pattern = re.compile(r"^\[([^\]]+)\]", re.MULTILINE)
    headers = list(header_pattern.finditer(text))

    for i, header in enumerate(headers):
        section_name = header.group(1)
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        section_body = text[start:end]

        match_val = _extract_triple_quoted(section_body, "match")
        rewrite_val = _extract_triple_quoted(section_body, "rewrite")

        if match_val is None or rewrite_val is None:
            continue

        sections.append((section_name, match_val, rewrite_val))

    return sections


def _extract_triple_quoted(text: str, key: str) -> str | None:
    """
    Extracts the value of a triple-quoted key from a toml section body.
    Supports both ''' and \"\"\".
    """
    for quote in ("'''", '"""'):
        pattern = re.compile(
            rf"^{re.escape(key)}\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}",
            re.DOTALL | re.MULTILINE,
        )
        m = pattern.search(text)
        if m:
            # Strip exactly one leading newline (toml convention: value starts after '''\n)
            val = m.group(1)
            if val.startswith("\n"):
                val = val[1:]
            # Strip exactly one trailing newline
            if val.endswith("\n"):
                val = val[:-1]
            return val
    return None


def _dedent_amount(text: str) -> int:
    """Returns the number of leading spaces on the first non-empty line."""
    for line in text.splitlines():
        if line.strip():
            return len(line) - len(line.lstrip(" "))
    return 0


def _reindent(text: str, current_indent: int, target_indent: int) -> str:
    """Shifts all lines in text by (target_indent - current_indent) spaces."""
    delta = target_indent - current_indent
    if delta == 0:
        return text
    result = []
    for line in text.splitlines(keepends=True):
        if line.strip() == "":
            result.append(line)
        elif delta > 0:
            result.append(" " * delta + line)
        else:
            strip = min(-delta, len(line) - len(line.lstrip(" ")))
            result.append(line[strip:])
    return "".join(result)


def apply_sections(
    source: str,
    sections: list[tuple[str, str, str]],
    filename: str,
) -> tuple[str, list[str], list[str]]:
    """
    Applies all sections to source. Returns (new_source, applied, failed).
    """
    applied = []
    failed = []
    result = source

    for name, match_str, rewrite_str in sections:
        # Try verbatim match first
        if match_str in result:
            result = result.replace(match_str, rewrite_str, 1)
            applied.append(name)
            continue

        # Try with normalized line endings
        match_normalized = match_str.replace("\r\n", "\n")
        result_normalized = result.replace("\r\n", "\n")
        if match_normalized in result_normalized:
            result = result_normalized.replace(match_normalized, rewrite_str, 1)
            applied.append(name)
            continue

        # Try reindenting: detect indentation of match and find it in source
        # with any consistent indentation offset
        match_indent = _dedent_amount(match_str)
        # Build a dedented version of the match to search for structure
        dedented_match = _reindent(match_str, match_indent, 0)

        # Try every indentation level from 0 to 16 in steps of 2
        found = False
        for target_indent in range(0, 17, 2):
            candidate = _reindent(dedented_match, 0, target_indent)
            if candidate in result:
                # Reindent the rewrite by the same delta
                rewrite_indent = _dedent_amount(rewrite_str)
                reindented_rewrite = _reindent(
                    rewrite_str, rewrite_indent, target_indent
                )
                result = result.replace(candidate, reindented_rewrite, 1)
                applied.append(f"{name} (reindented to {target_indent})")
                found = True
                break

        if not found:
            failed.append(name)

    return result, applied, failed


def show_diff(original: str, patched: str, filename: str) -> None:
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    sys.stdout.writelines(diff)


def apply_file(
    toml_content: str,
    target: Path,
    dry_run: bool,
) -> tuple[bool, list[str], list[str]]:
    sections = parse_sections(toml_content)
    if not sections:
        return False, [], ["no sections parsed"]

    original = target.read_text(encoding="utf-8")
    patched, applied, failed = apply_sections(original, sections, target.name)

    if dry_run:
        show_diff(original, patched, str(target))
    else:
        if patched != original:
            target.write_text(patched, encoding="utf-8")

    return True, applied, failed


def main():
    patches_dir = get_patches_dir()

    available = (
        sorted(p.name for p in patches_dir.iterdir() if p.is_dir())
        if patches_dir.is_dir()
        else []
    )

    parser = argparse.ArgumentParser(prog="patch")
    parser.add_argument(
        "project",
        help=f"Project to patch. Available: {', '.join(available)}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show diff without modifying files",
    )
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
            print(f"{toml_file.name}: target not found: {target_rel}")
            fail += 1
            continue

        label = "dry-run" if args.dry_run else "patching"
        print(f"> {toml_file.name} -> {target_rel} ({label})")

        success, applied, failed_sections = apply_file(toml_content, target, args.dry_run)

        if not success:
            print(f"  error: {failed_sections[0]}")
            fail += 1
            continue

        for s in applied:
            print(f"  [ok] {s}")
        for s in failed_sections:
            print(f"  [MISS] {s}  <-- match not found, skipped")

        if failed_sections:
            fail += 1
        else:
            ok += 1

    print(f"\n{ok} ok  {fail} failed")


if __name__ == "__main__":
    main()
