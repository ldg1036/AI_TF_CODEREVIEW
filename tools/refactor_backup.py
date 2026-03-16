import argparse
import ast
import datetime as _dt
import difflib
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "workspace" / "runtime" / "refactor_backups"
DEFAULT_TARGET_FILES = [
    "backend/main.py",
    "backend/server.py",
    "backend/tests/test_api_and_reports.py",
]


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_label() -> str:
    now = _dt.datetime.now()
    return now.strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _safe_label(label: str) -> str:
    raw = str(label or "snapshot").strip() or "snapshot"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in raw)
    return cleaned.strip("_") or "snapshot"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _rel_path(path_value: str, project_root: Path) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate.resolve().relative_to(project_root.resolve()).as_posix()
    return Path(path_value).as_posix()


def _git_head(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except Exception:
        return ""


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _surface_from_python(text: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "imports": [],
            "functions": [],
            "classes": {},
            "public_entrypoints": [],
            "parse_error": str(exc),
        }

    imports: List[str] = []
    functions: List[str] = []
    classes: Dict[str, List[str]] = {}
    public_entrypoints: List[str] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name if not alias.asname else f"{alias.name} as {alias.asname}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported = ", ".join(
                alias.name if not alias.asname else f"{alias.name} as {alias.asname}"
                for alias in node.names
            )
            imports.append(f"from {module} import {imported}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
            if not node.name.startswith("_"):
                public_entrypoints.append(node.name)
        elif isinstance(node, ast.ClassDef):
            methods: List[str] = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(child.name)
                    if not child.name.startswith("_"):
                        public_entrypoints.append(f"{node.name}.{child.name}")
            classes[node.name] = methods

    return {
        "imports": sorted(imports),
        "functions": sorted(functions),
        "classes": {name: sorted(methods) for name, methods in sorted(classes.items())},
        "public_entrypoints": sorted(public_entrypoints),
        "parse_error": "",
    }


def _method_diff(before: Dict[str, List[str]], after: Dict[str, List[str]]) -> Dict[str, Dict[str, List[str]]]:
    class_names = sorted(set(before) | set(after))
    added: Dict[str, List[str]] = {}
    removed: Dict[str, List[str]] = {}
    for class_name in class_names:
        before_methods = set(before.get(class_name, []))
        after_methods = set(after.get(class_name, []))
        if after_methods - before_methods:
            added[class_name] = sorted(after_methods - before_methods)
        if before_methods - after_methods:
            removed[class_name] = sorted(before_methods - after_methods)
    return {"added": added, "removed": removed}


def create_backup(
    label: str,
    files: Optional[Iterable[str]] = None,
    *,
    project_root: Path = PROJECT_ROOT,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
) -> Dict[str, Any]:
    target_files = list(files or DEFAULT_TARGET_FILES)
    relative_files = [_rel_path(item, project_root) for item in target_files]
    missing_files = [rel for rel in relative_files if not (project_root / rel).is_file()]
    if missing_files:
        return {
            "ok": False,
            "error_code": "FILE_NOT_FOUND",
            "message": "One or more target files do not exist.",
            "missing_files": missing_files,
        }

    timestamp = _timestamp_label()
    safe_label = _safe_label(label)
    backup_dir = backup_root / f"{timestamp}_{safe_label}"
    source_dir = backup_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=False)

    manifest_files: List[Dict[str, Any]] = []
    for relative_path in relative_files:
        source_path = project_root / relative_path
        snapshot_path = source_dir / relative_path
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, snapshot_path)
        manifest_files.append(
            {
                "relative_path": relative_path,
                "snapshot_path": snapshot_path.relative_to(backup_dir).as_posix(),
                "size": int(source_path.stat().st_size),
                "sha256": _sha256_file(source_path),
            }
        )

    manifest = {
        "label": safe_label,
        "timestamp": timestamp,
        "created_at": _utc_now_iso(),
        "project_root": str(project_root),
        "git_head": _git_head(project_root),
        "files": manifest_files,
    }
    manifest_path = backup_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "ok": True,
        "label": safe_label,
        "timestamp": timestamp,
        "backup_dir": str(backup_dir),
        "manifest_path": str(manifest_path),
        "files": manifest_files,
    }


def _resolve_manifest_path(target: str, project_root: Path) -> Path:
    path = Path(target)
    if not path.is_absolute():
        path = project_root / path
    if path.is_dir():
        path = path / "manifest.json"
    return path


def _compare_file_entry(entry: Dict[str, Any], manifest_dir: Path, project_root: Path) -> Dict[str, Any]:
    relative_path = str(entry.get("relative_path", "") or entry.get("path", "") or "")
    snapshot_rel = str(entry.get("snapshot_path", "") or Path("source") / relative_path)
    snapshot_path = manifest_dir / snapshot_rel
    current_path = project_root / relative_path

    result: Dict[str, Any] = {
        "relative_path": relative_path,
        "snapshot_path": str(snapshot_path),
        "current_path": str(current_path),
        "exists_in_snapshot": snapshot_path.is_file(),
        "exists_in_current": current_path.is_file(),
        "snapshot_sha256": entry.get("sha256", ""),
        "current_sha256": "",
        "changed": False,
        "imports_added": [],
        "imports_removed": [],
        "functions_added": [],
        "functions_removed": [],
        "methods_added": {},
        "methods_removed": {},
        "public_entrypoints_added": [],
        "missing_public_entrypoints": [],
        "unified_diff": [],
        "parse_errors": {},
    }

    if not snapshot_path.is_file():
        return result

    snapshot_text = _read_text(snapshot_path)
    current_text = _read_text(current_path) if current_path.is_file() else ""
    if current_path.is_file():
        result["current_sha256"] = _sha256_file(current_path)
    result["changed"] = snapshot_text != current_text

    snapshot_surface = _surface_from_python(snapshot_text)
    current_surface = _surface_from_python(current_text)
    if snapshot_surface.get("parse_error"):
        result["parse_errors"]["snapshot"] = snapshot_surface["parse_error"]
    if current_surface.get("parse_error"):
        result["parse_errors"]["current"] = current_surface["parse_error"]

    snapshot_imports = set(snapshot_surface.get("imports", []))
    current_imports = set(current_surface.get("imports", []))
    snapshot_functions = set(snapshot_surface.get("functions", []))
    current_functions = set(current_surface.get("functions", []))
    snapshot_public = set(snapshot_surface.get("public_entrypoints", []))
    current_public = set(current_surface.get("public_entrypoints", []))
    method_delta = _method_diff(
        snapshot_surface.get("classes", {}),
        current_surface.get("classes", {}),
    )

    result["imports_added"] = sorted(current_imports - snapshot_imports)
    result["imports_removed"] = sorted(snapshot_imports - current_imports)
    result["functions_added"] = sorted(current_functions - snapshot_functions)
    result["functions_removed"] = sorted(snapshot_functions - current_functions)
    result["methods_added"] = method_delta["added"]
    result["methods_removed"] = method_delta["removed"]
    result["public_entrypoints_added"] = sorted(current_public - snapshot_public)
    result["missing_public_entrypoints"] = sorted(snapshot_public - current_public)
    result["unified_diff"] = list(
        difflib.unified_diff(
            snapshot_text.splitlines(),
            current_text.splitlines(),
            fromfile=f"snapshot/{relative_path}",
            tofile=f"current/{relative_path}",
            lineterm="",
        )
    )
    return result


def _markdown_report(payload: Dict[str, Any]) -> str:
    lines = [
        f"# Refactor Backup Review",
        "",
        f"- label: `{payload.get('label', '')}`",
        f"- backup_dir: `{payload.get('backup_dir', '')}`",
        f"- manifest_path: `{payload.get('manifest_path', '')}`",
        f"- compared_at: `{payload.get('compared_at', '')}`",
        f"- ok: `{payload.get('ok', False)}`",
    ]
    if payload.get("error_code"):
        lines.append(f"- error_code: `{payload.get('error_code', '')}`")
    lines.append("")

    for file_result in payload.get("files", []):
        lines.append(f"## {file_result.get('relative_path', '')}")
        lines.append("")
        lines.append(f"- changed: `{file_result.get('changed', False)}`")
        lines.append(f"- exists_in_current: `{file_result.get('exists_in_current', False)}`")
        lines.append(f"- imports_added: `{', '.join(file_result.get('imports_added', []))}`")
        lines.append(f"- imports_removed: `{', '.join(file_result.get('imports_removed', []))}`")
        lines.append(f"- functions_added: `{', '.join(file_result.get('functions_added', []))}`")
        lines.append(f"- functions_removed: `{', '.join(file_result.get('functions_removed', []))}`")
        lines.append(f"- missing_public_entrypoints: `{', '.join(file_result.get('missing_public_entrypoints', []))}`")
        lines.append("")
        diff_lines = file_result.get("unified_diff", [])
        if diff_lines:
            lines.append("```diff")
            lines.extend(diff_lines)
            lines.append("```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def review_backup(
    target: str,
    *,
    project_root: Path = PROJECT_ROOT,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    manifest_path = _resolve_manifest_path(target, project_root)
    if not manifest_path.is_file():
        return {
            "ok": False,
            "error_code": "MANIFEST_NOT_FOUND",
            "message": f"Manifest not found: {manifest_path}",
            "manifest_path": str(manifest_path),
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    manifest_dir = manifest_path.parent
    compare_stamp = _timestamp_label()
    review_dir = output_dir or (manifest_dir / "review")
    review_dir.mkdir(parents=True, exist_ok=True)

    file_results = [_compare_file_entry(entry, manifest_dir, project_root) for entry in manifest.get("files", [])]
    missing_snapshot = [item["relative_path"] for item in file_results if not item.get("exists_in_snapshot", False)]
    missing_current = [item["relative_path"] for item in file_results if not item.get("exists_in_current", False)]

    payload: Dict[str, Any] = {
        "ok": not missing_snapshot and not missing_current,
        "error_code": "",
        "label": manifest.get("label", ""),
        "timestamp": manifest.get("timestamp", ""),
        "compared_at": _utc_now_iso(),
        "backup_dir": str(manifest_dir),
        "manifest_path": str(manifest_path),
        "compare_json_path": str(review_dir / f"compare_{compare_stamp}.json"),
        "compare_markdown_path": str(review_dir / f"compare_{compare_stamp}.md"),
        "missing_snapshot_files": missing_snapshot,
        "missing_current_files": missing_current,
        "files": file_results,
    }
    if missing_snapshot:
        payload["error_code"] = "SNAPSHOT_FILE_MISSING"
    elif missing_current:
        payload["error_code"] = "CURRENT_FILE_MISSING"

    _write_json(Path(payload["compare_json_path"]), payload)
    Path(payload["compare_markdown_path"]).write_text(_markdown_report(payload), encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create and review refactor backup snapshots.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a source snapshot for selected files")
    create_parser.add_argument("--label", default="snapshot", help="Short label for the backup folder")
    create_parser.add_argument("files", nargs="*", help="Relative or absolute file paths to snapshot")

    review_parser = subparsers.add_parser("review", help="Compare current files against a backup snapshot")
    review_parser.add_argument("target", help="Backup directory or manifest.json path")

    args = parser.parse_args(argv)
    if args.command == "create":
        result = create_backup(args.label, args.files)
    else:
        result = review_backup(args.target)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
