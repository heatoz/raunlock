# unblock-hardcore

A command-line tool for applying source code patches on emulators: removes the restrictions of RetroAchievements Hardcore mode.<br>
<br>
Save state. Load state. Rewind. Cheats. Enjoy! :)

## Usage

Be on the root folder of the emulator source code. Run:

```
./patch <project> [--dry-run]
```

```
./patch duckstation
./patch duckstation --dry-run
```
Now compile!<br>

`--dry-run` prints a unified diff to stdout without modifying any files. Useful for verifying patches before applying them.

## How patches work

Patches live under `patches/<project>/` as `.toml` files. Each file targets a single source file, declared in the first comment at the top:

```toml
# src/core/achievements.cpp
```

Each `[section]` in the file defines one replacement using a `match` and a `rewrite` key, both as triple-quoted strings:

```toml
[disable_achievement_lockout]
match = '''
  if (achievements_locked)
    return false;
'''

rewrite = '''
  if (achievements_locked)
    return true;
'''
```

The tool searches for the `match` text verbatim in the target file. If the exact string is not found, it strips indentation and retries at every indentation level from 0 to 16 spaces. The `rewrite` is applied with the same indentation offset.

If a section's match cannot be found, it is reported as `[MISS]` and skipped. The remaining sections in the file still run.

## Output

```
duckstation -- 3 patch(es) in /home/user/duckstation

> achievements.toml -> src/core/achievements.cpp (patching)
  [ok] disable_achievement_lockout
  [ok] skip_hardcore_check (reindented to 4)
  [MISS] remove_leaderboard_submit  <-- match not found, skipped

1 ok  1 failed
```

## Compiling

Requires Python 3.10+ and PyInstaller.

```
pip install pyinstaller
pyinstaller --onefile --add-data "patches:patches" patch.py
```

The resulting binary is written to `dist/patch`. The `patches/` directory is bundled into the executable, so the binary is self-contained and can be distributed without the source tree.

## Adding patches for a new project

1. Create a folder under `patches/<project>/`.
2. Add one or more `.toml` files following the format above.
3. Run `./patch <project> --dry-run` to verify before applying.

## Contributing

If you want to contribute patches for a project, open a pull request with the new or updated `.toml` files under `patches/`. No changes to the tool itself are needed in most cases.

If a patch no longer applies because the upstream source changed, or if a restriction you expected to be removed is still active, open an issue describing the project, the patch file, and what behavior you are seeing.
