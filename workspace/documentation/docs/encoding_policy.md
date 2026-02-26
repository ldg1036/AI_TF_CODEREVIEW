# Encoding Policy (UTF-8 Fixed)

Last Updated: 2026-02-25 (UTF-8 fixed policy + legacy doc recovery workflow)

This project uses a strict text encoding rule to prevent broken Korean text, tool failures, and patch/apply errors.

## Policy

- All text source files must be saved as `UTF-8` (without BOM unless a specific tool requires BOM).
- Default line ending for project files is `LF`.
- PowerShell scripts (`.ps1`) may use `CRLF`.
- Do not save project files in `CP949`, `EUC-KR`, or mixed encodings.

## Why This Is Required

Recent issues showed that mixed-encoding files can cause:

- broken Korean text in `README.md` / docs
- patch tooling failures (UTF-8 decode errors)
- unstable diffs and review noise
- inconsistent behavior between editors/terminals

Note:
- Some legacy docs were found with irreversible `?` replacement loss (not recoverable by encoding conversion alone).
- For these cases, rewrite from current implementation/context is preferred over blind recoding.

## Scope (UTF-8 Required)

Apply UTF-8 to:

- `backend/**/*.py`
- `frontend/**/*.{js,html,css}`
- `Config/**/*.json`
- `docs/**/*.md`
- `tools/**/*.py`
- `tools/**/*.js`
- top-level `README.md`, `todo.md`

## Project Defaults

The repo now includes `.editorconfig` with:

- `charset = utf-8`
- `end_of_line = lf` (most files)
- `insert_final_newline = true`
- `trim_trailing_whitespace = true`

## Editor Setup (Recommended)

### VS Code

- Set default encoding to `utf8`
- Enable auto-detect encoding (optional)
- When a file looks broken, use `Reopen with Encoding` before saving
- Save as `UTF-8` explicitly after confirming content

### Other Editors / IDEs

- Set project encoding to `UTF-8`
- Disable legacy code-page fallback for source files when possible
- Confirm markdown/json/python/js files are not being saved in ANSI/CP949

## Operating Rules (Team)

- Do not bulk-convert files unless you first create a backup.
- If a file cannot be decoded as UTF-8, inspect and repair only the broken region.
- After repairing encoding, verify diffs to ensure content changed only where intended.
- Prefer editing Korean example strings directly in UTF-8 once the file is normalized.

## Verification Commands

### Quick UTF-8 decode check (single file)

```powershell
@'
from pathlib import Path
Path(r"C:\path\to\file.md").read_text(encoding="utf-8")
print("utf8-ok")
'@ | python -
```

### Project scan example (selected extensions)

```powershell
@'
from pathlib import Path
root = Path(r"C:\Users\Administrator\Desktop\Coder_Wincc-main")
exts = {".py", ".js", ".json", ".md", ".html", ".css"}
bad = []
for p in root.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in exts:
        continue
    try:
        p.read_text(encoding="utf-8")
    except Exception as e:
        bad.append((str(p), type(e).__name__))
print(f"bad_count={len(bad)}")
for item in bad[:50]:
    print(item[0], item[1])
'@ | python -
```

## Recovery Procedure (If Encoding Breaks Again)

1. Create a backup copy of the file before saving.
2. Inspect the raw bytes / suspect region.
3. Repair only the broken bytes (avoid whole-file blind recoding).
4. Save as UTF-8.
5. Re-run UTF-8 decode check.
6. Review diff for unintended changes.

