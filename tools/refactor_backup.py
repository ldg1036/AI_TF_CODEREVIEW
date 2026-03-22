import argparse
import ast
import datetime as _dt
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "workspace" / "runtime" / "refactor_backups"
DEFAULT_TARGET_FILES = [
    "backend/main.py",
    "backend/server.py",
    "backend/tests/test_api_and_reports.py",
]
JS_EXTENSIONS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}
PY_EXTENSIONS = {".py"}


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


def _detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PY_EXTENSIONS:
        return "python"
    if suffix in JS_EXTENSIONS:
        return "javascript"
    return "text"


def _sorted_unique(items: Iterable[str]) -> List[str]:
    return sorted({str(item).strip() for item in items if str(item).strip()})


def _surface_from_python(text: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "language": "python",
            "imports": [],
            "functions": [],
            "classes": {},
            "public_entrypoints": [],
            "exports": [],
            "controller_methods": [],
            "dom_selectors": [],
            "event_bindings": [],
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
        "language": "python",
        "imports": sorted(imports),
        "functions": sorted(functions),
        "classes": {name: sorted(methods) for name, methods in sorted(classes.items())},
        "public_entrypoints": sorted(public_entrypoints),
        "exports": [],
        "controller_methods": [],
        "dom_selectors": [],
        "event_bindings": [],
        "parse_error": "",
    }


def _js_imports(text: str) -> List[str]:
    imports = []
    for match in re.finditer(r"(?m)^\s*import\s+.+?$", text):
        imports.append(match.group(0).strip())
    return _sorted_unique(imports)


def _js_exports(text: str) -> List[str]:
    exports: Set[str] = set()
    for match in re.finditer(r"(?m)^\s*export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", text):
        exports.add(match.group(1))
    for match in re.finditer(r"(?m)^\s*export\s+(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)\b", text):
        exports.add(match.group(1))
    for match in re.finditer(r"(?m)^\s*export\s*\{([^}]+)\}", text):
        for part in match.group(1).split(","):
            token = part.strip()
            if not token:
                continue
            if " as " in token:
                exports.add(token.split(" as ", 1)[1].strip())
            else:
                exports.add(token)
    if re.search(r"(?m)^\s*export\s+default\b", text):
        exports.add("default")
    return sorted(exports)


def _js_functions(text: str) -> List[str]:
    functions: Set[str] = set()
    patterns = [
        r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
        r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(",
        r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            functions.add(match.group(1))
    return sorted(functions)


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    in_single = False
    in_double = False
    in_template = False
    in_line_comment = False
    in_block_comment = False
    escaped = False
    index = open_index
    while index < len(text):
        ch = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                index += 1
        elif in_single:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_single = False
        elif in_double:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
        elif in_template:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "`":
                in_template = False
        else:
            if ch == "/" and nxt == "/":
                in_line_comment = True
                index += 1
            elif ch == "/" and nxt == "*":
                in_block_comment = True
                index += 1
            elif ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch == "`":
                in_template = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return index
        index += 1
    return -1


def _extract_controller_return_object(body: str) -> str:
    depth = 0
    in_single = False
    in_double = False
    in_template = False
    in_line_comment = False
    in_block_comment = False
    escaped = False
    index = 0
    while index < len(body):
        ch = body[index]
        nxt = body[index + 1] if index + 1 < len(body) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                index += 1
        elif in_single:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_single = False
        elif in_double:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
        elif in_template:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "`":
                in_template = False
        else:
            if ch == "/" and nxt == "/":
                in_line_comment = True
                index += 1
            elif ch == "/" and nxt == "*":
                in_block_comment = True
                index += 1
            elif ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch == "`":
                in_template = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif depth == 0 and body.startswith("return", index):
                rest = body[index + 6 :]
                whitespace = len(rest) - len(rest.lstrip())
                brace_index = index + 6 + whitespace
                if brace_index < len(body) and body[brace_index] == "{":
                    end_index = _find_matching_brace(body, brace_index)
                    if end_index > brace_index:
                        return body[brace_index + 1 : end_index]
        index += 1
    return ""


def _controller_methods_from_return_objects(text: str) -> List[str]:
    methods: Set[str] = set()
    controller_pattern = re.compile(r"(?:export\s+)?function\s+(create[A-Za-z_$][\w$]*Controller)\s*\([^)]*\)\s*\{")
    for match in controller_pattern.finditer(text):
        open_index = match.end() - 1
        close_index = _find_matching_brace(text, open_index)
        if close_index <= open_index:
            continue
        body = text[open_index + 1 : close_index]
        return_body = _extract_controller_return_object(body)
        if not return_body:
            continue
        for line in return_body.splitlines():
            stripped = line.strip().rstrip(",")
            if not stripped or stripped.startswith("//"):
                continue
            property_match = re.match(r"([A-Za-z_$][\w$]*)\s*(?::|\(|$)", stripped)
            if property_match:
                methods.add(property_match.group(1))
    return sorted(methods)


def _dom_selectors(text: str) -> List[str]:
    selectors: Set[str] = set()
    for match in re.finditer(r"getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
        selectors.add(f"#{match.group(1)}")
    for match in re.finditer(r"(?:querySelector|querySelectorAll|closest)\(\s*([\"'])(.+?)\1\s*\)", text):
        selectors.add(match.group(2).strip())
    for match in re.finditer(r"classList\.(?:add|remove|toggle)\(\s*['\"]([^'\"]+)['\"]", text):
        selectors.add(f".{match.group(1)}")
    return sorted(selectors)


def _normalize_binding_target(target: str) -> str:
    raw = str(target or "").strip()
    if not raw:
        return raw
    if raw.startswith("dom."):
        return raw.split(".")[-1]
    return raw


def _event_bindings(text: str) -> List[str]:
    bindings: Set[str] = set()
    pattern = re.compile(r"([A-Za-z_$][\w$.]*)\.addEventListener\(\s*['\"]([^'\"]+)['\"]")
    for match in pattern.finditer(text):
        bindings.add(f"{_normalize_binding_target(match.group(1))}:{match.group(2)}")
    return sorted(bindings)


def _surface_from_javascript(text: str) -> Dict[str, Any]:
    return {
        "language": "javascript",
        "imports": _js_imports(text),
        "functions": _js_functions(text),
        "classes": {},
        "public_entrypoints": [],
        "exports": _js_exports(text),
        "controller_methods": _controller_methods_from_return_objects(text),
        "dom_selectors": _dom_selectors(text),
        "event_bindings": _event_bindings(text),
        "parse_error": "",
    }


def _surface_from_text(path: Path, text: str) -> Dict[str, Any]:
    language = _detect_language(path)
    if language == "python":
        return _surface_from_python(text)
    if language == "javascript":
        return _surface_from_javascript(text)
    return {
        "language": language,
        "imports": [],
        "functions": [],
        "classes": {},
        "public_entrypoints": [],
        "exports": [],
        "controller_methods": [],
        "dom_selectors": [],
        "event_bindings": [],
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
        source_text = _read_text(source_path)
        source_surface = _surface_from_text(source_path, source_text)
        manifest_files.append(
            {
                "relative_path": relative_path,
                "snapshot_path": snapshot_path.relative_to(backup_dir).as_posix(),
                "size": int(source_path.stat().st_size),
                "sha256": _sha256_file(source_path),
                "language": source_surface.get("language", _detect_language(source_path)),
                "surface": source_surface,
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


def _surface_from_entry_or_snapshot(entry: Dict[str, Any], snapshot_path: Path) -> Dict[str, Any]:
    snapshot_text = _read_text(snapshot_path)
    return _surface_from_text(snapshot_path, snapshot_text)


def _compare_file_entry(entry: Dict[str, Any], manifest_dir: Path, project_root: Path) -> Dict[str, Any]:
    relative_path = str(entry.get("relative_path", "") or entry.get("path", "") or "")
    snapshot_rel = str(entry.get("snapshot_path", "") or Path("source") / relative_path)
    snapshot_path = manifest_dir / snapshot_rel
    current_path = project_root / relative_path

    result: Dict[str, Any] = {
        "relative_path": relative_path,
        "snapshot_path": str(snapshot_path),
        "current_path": str(current_path),
        "language": str(entry.get("language", "") or _detect_language(current_path)),
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
        "exports_added": [],
        "missing_exports": [],
        "controller_methods_added": [],
        "missing_controller_methods": [],
        "dom_bindings_added": [],
        "missing_dom_bindings": [],
        "event_bindings_added": [],
        "missing_event_bindings": [],
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

    snapshot_surface = _surface_from_entry_or_snapshot(entry, snapshot_path)
    current_surface = _surface_from_text(current_path, current_text)
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
    snapshot_exports = set(snapshot_surface.get("exports", []))
    current_exports = set(current_surface.get("exports", []))
    snapshot_controller_methods = set(snapshot_surface.get("controller_methods", []))
    current_controller_methods = set(current_surface.get("controller_methods", []))
    snapshot_dom_selectors = set(snapshot_surface.get("dom_selectors", []))
    current_dom_selectors = set(current_surface.get("dom_selectors", []))
    snapshot_event_bindings = set(snapshot_surface.get("event_bindings", []))
    current_event_bindings = set(current_surface.get("event_bindings", []))
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
    result["exports_added"] = sorted(current_exports - snapshot_exports)
    result["missing_exports"] = sorted(snapshot_exports - current_exports)
    result["controller_methods_added"] = sorted(current_controller_methods - snapshot_controller_methods)
    result["missing_controller_methods"] = sorted(snapshot_controller_methods - current_controller_methods)
    result["dom_bindings_added"] = sorted(current_dom_selectors - snapshot_dom_selectors)
    result["missing_dom_bindings"] = sorted(snapshot_dom_selectors - current_dom_selectors)
    result["event_bindings_added"] = sorted(current_event_bindings - snapshot_event_bindings)
    result["missing_event_bindings"] = sorted(snapshot_event_bindings - current_event_bindings)
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


def _flatten_missing(file_results: Sequence[Dict[str, Any]], key: str) -> Dict[str, List[str]]:
    flattened: Dict[str, List[str]] = {}
    for item in file_results:
        values = [str(value) for value in item.get(key, []) if str(value).strip()]
        if values:
            flattened[str(item.get("relative_path", ""))] = values
    return flattened


def _merge_surface(target: Dict[str, Set[str]], surface: Dict[str, Any]) -> None:
    for key in ("imports", "functions", "public_entrypoints", "exports", "controller_methods", "dom_selectors", "event_bindings"):
        values = surface.get(key, []) or []
        target.setdefault(key, set()).update(str(value).strip() for value in values if str(value).strip())


def _collect_scope_files(manifest_entries: Sequence[Dict[str, Any]], project_root: Path) -> List[Path]:
    scope_dirs: Set[Path] = set()
    for entry in manifest_entries:
        relative_path = Path(str(entry.get("relative_path", "") or ""))
        suffix = relative_path.suffix.lower()
        if suffix not in JS_EXTENSIONS:
            continue
        scope_dirs.add((project_root / relative_path).parent)
    discovered: Set[Path] = set()
    for directory in scope_dirs:
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in JS_EXTENSIONS:
                discovered.add(path.resolve())
    return sorted(discovered)


def _markdown_report(payload: Dict[str, Any]) -> str:
    lines = [
        "# Refactor Backup Review",
        "",
        f"- label: `{payload.get('label', '')}`",
        f"- backup_dir: `{payload.get('backup_dir', '')}`",
        f"- manifest_path: `{payload.get('manifest_path', '')}`",
        f"- compared_at: `{payload.get('compared_at', '')}`",
        f"- ok: `{payload.get('ok', False)}`",
    ]
    if payload.get("error_code"):
        lines.append(f"- error_code: `{payload.get('error_code', '')}`")
    if payload.get("changed_files"):
        lines.append(f"- changed_files: `{', '.join(payload.get('changed_files', []))}`")
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
        lines.append(f"- missing_exports: `{', '.join(file_result.get('missing_exports', []))}`")
        lines.append(f"- missing_controller_methods: `{', '.join(file_result.get('missing_controller_methods', []))}`")
        lines.append(f"- missing_dom_bindings: `{', '.join(file_result.get('missing_dom_bindings', []))}`")
        lines.append(f"- missing_event_bindings: `{', '.join(file_result.get('missing_event_bindings', []))}`")
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
    changed_files = [item["relative_path"] for item in file_results if item.get("changed", False)]
    per_file_missing_exports = _flatten_missing(file_results, "missing_exports")
    per_file_missing_controller_methods = _flatten_missing(file_results, "missing_controller_methods")
    per_file_missing_dom_bindings = _flatten_missing(file_results, "missing_dom_bindings")
    per_file_missing_event_bindings = _flatten_missing(file_results, "missing_event_bindings")
    snapshot_aggregate: Dict[str, Set[str]] = {}
    current_aggregate: Dict[str, Set[str]] = {}
    manifest_entries = manifest.get("files", [])
    for entry in manifest_entries:
        relative_path = str(entry.get("relative_path", "") or "")
        snapshot_path = manifest_dir / str(entry.get("snapshot_path", "") or Path("source") / relative_path)
        snapshot_surface = _surface_from_entry_or_snapshot(entry, snapshot_path)
        _merge_surface(snapshot_aggregate, snapshot_surface)
    for path in _collect_scope_files(manifest_entries, project_root):
        _merge_surface(current_aggregate, _surface_from_text(path, _read_text(path)))
    aggregate_missing_exports = sorted(snapshot_aggregate.get("exports", set()) - current_aggregate.get("exports", set()))
    aggregate_missing_controller_methods = sorted(snapshot_aggregate.get("controller_methods", set()) - current_aggregate.get("controller_methods", set()))
    aggregate_missing_dom_bindings = sorted(snapshot_aggregate.get("dom_selectors", set()) - current_aggregate.get("dom_selectors", set()))
    aggregate_missing_event_bindings = sorted(snapshot_aggregate.get("event_bindings", set()) - current_aggregate.get("event_bindings", set()))
    aggregate_missing_public_entrypoints = sorted(snapshot_aggregate.get("public_entrypoints", set()) - current_aggregate.get("public_entrypoints", set()))

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
        "changed_files": changed_files,
        "missing_exports": aggregate_missing_exports,
        "missing_controller_methods": aggregate_missing_controller_methods,
        "missing_dom_bindings": aggregate_missing_dom_bindings,
        "missing_event_bindings": aggregate_missing_event_bindings,
        "per_file_missing_exports": per_file_missing_exports,
        "per_file_missing_controller_methods": per_file_missing_controller_methods,
        "per_file_missing_dom_bindings": per_file_missing_dom_bindings,
        "per_file_missing_event_bindings": per_file_missing_event_bindings,
        "aggregate_missing_exports": aggregate_missing_exports,
        "aggregate_missing_controller_methods": aggregate_missing_controller_methods,
        "aggregate_missing_dom_bindings": aggregate_missing_dom_bindings,
        "aggregate_missing_event_bindings": aggregate_missing_event_bindings,
        "aggregate_missing_public_entrypoints": aggregate_missing_public_entrypoints,
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

    compare_parser = subparsers.add_parser("compare", help="Alias for review")
    compare_parser.add_argument("target", help="Backup directory or manifest.json path")

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
