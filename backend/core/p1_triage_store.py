import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

TRIAGE_TOOL_NAME = "winccoa-code-review"
TRIAGE_FILE_NAME = "p1_triage_entries.json"
VALID_P1_TRIAGE_STATUS = {"open", "suppressed"}


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _epoch_ms() -> int:
    return int(time.time() * 1000)


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def get_p1_triage_paths(project_root: Optional[Path] = None) -> Dict[str, Path]:
    root = Path(project_root) if project_root is not None else _default_project_root()
    triage_dir = root / "workspace" / "runtime" / "triage"
    backup_dir = triage_dir / "backups"
    source_path = triage_dir / TRIAGE_FILE_NAME
    return {
        "project_root": root,
        "triage_dir": triage_dir,
        "backup_dir": backup_dir,
        "source_path": source_path,
    }


def _base_payload() -> Dict[str, Any]:
    return {
        "tool": TRIAGE_TOOL_NAME,
        "updated_at_ms": 0,
        "entries": [],
    }


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_match(match: Any) -> Dict[str, Any]:
    data = match if isinstance(match, dict) else {}
    return {
        "file": str(data.get("file", "") or ""),
        "line": _safe_int(data.get("line", 0), 0),
        "rule_id": str(data.get("rule_id", "") or ""),
        "message": str(data.get("message", "") or ""),
        "issue_id": str(data.get("issue_id", "") or ""),
    }


def normalize_p1_triage_entry(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise RuntimeError("Malformed P1 triage entry: object is required")
    triage_key = str(entry.get("triage_key", "") or "").strip()
    if not triage_key:
        raise RuntimeError("Malformed P1 triage entry: triage_key is required")
    status = str(entry.get("status", "open") or "open").strip().lower()
    if status not in VALID_P1_TRIAGE_STATUS:
        raise RuntimeError(f"Malformed P1 triage entry: invalid status '{status}'")
    return {
        "triage_key": triage_key,
        "status": status,
        "reason": str(entry.get("reason", "") or ""),
        "note": str(entry.get("note", "") or ""),
        "updated_at_ms": _safe_int(entry.get("updated_at_ms", _epoch_ms()), _epoch_ms()),
        "match": _normalize_match(entry.get("match", {})),
    }


def load_p1_triage_payload(project_root: Optional[Path] = None) -> Dict[str, Any]:
    paths = get_p1_triage_paths(project_root)
    source_path = paths["source_path"]
    if not source_path.exists():
        return _base_payload()
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Malformed P1 triage file: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read P1 triage file: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Malformed P1 triage file: root object is required")
    raw_entries = raw.get("entries", [])
    if not isinstance(raw_entries, list):
        raise RuntimeError("Malformed P1 triage file: entries must be a list")
    entries = [normalize_p1_triage_entry(item) for item in raw_entries]
    return {
        "tool": str(raw.get("tool", TRIAGE_TOOL_NAME) or TRIAGE_TOOL_NAME),
        "updated_at_ms": _safe_int(raw.get("updated_at_ms", 0), 0),
        "entries": entries,
    }


def _write_backup(paths: Dict[str, Path], *, reason: str) -> Optional[Path]:
    source_path = paths["source_path"]
    if not source_path.exists():
        return None
    backup_dir = paths["backup_dir"]
    backup_dir.mkdir(parents=True, exist_ok=True)
    safe_reason = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(reason or "update"))[:48] or "update"
    backup_path = backup_dir / f"p1_triage_entries_{_stamp()}_{safe_reason}.json"
    shutil.copy2(source_path, backup_path)
    return backup_path


def save_p1_triage_payload(payload: Dict[str, Any], *, project_root: Optional[Path] = None, backup_reason: str = "update") -> Dict[str, Any]:
    paths = get_p1_triage_paths(project_root)
    triage_dir = paths["triage_dir"]
    source_path = paths["source_path"]
    triage_dir.mkdir(parents=True, exist_ok=True)
    normalized_entries = [normalize_p1_triage_entry(item) for item in list(payload.get("entries", []) or [])]
    normalized_payload = {
        "tool": str(payload.get("tool", TRIAGE_TOOL_NAME) or TRIAGE_TOOL_NAME),
        "updated_at_ms": _epoch_ms(),
        "entries": normalized_entries,
    }
    _write_backup(paths, reason=backup_reason)
    fd, temp_path = tempfile.mkstemp(prefix="p1_triage_", suffix=".json", dir=str(triage_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized_payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, source_path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except OSError:
            pass
    return normalized_payload


def list_p1_triage_entries(project_root: Optional[Path] = None) -> Dict[str, Any]:
    payload = load_p1_triage_payload(project_root)
    paths = get_p1_triage_paths(project_root)
    return {
        "available": True,
        "count": len(payload["entries"]),
        "source_file": paths["source_path"].name,
        "source_path": str(paths["source_path"]),
        "updated_at_ms": payload["updated_at_ms"],
        "entries": payload["entries"],
    }


def upsert_p1_triage_entry(
    *,
    triage_key: str,
    status: str,
    reason: str,
    note: str,
    match: Dict[str, Any],
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    payload = load_p1_triage_payload(project_root)
    normalized_entry = normalize_p1_triage_entry(
        {
            "triage_key": triage_key,
            "status": status,
            "reason": reason,
            "note": note,
            "match": match,
            "updated_at_ms": _epoch_ms(),
        }
    )
    next_entries: List[Dict[str, Any]] = []
    replaced = False
    for entry in payload["entries"]:
        if str(entry.get("triage_key", "")) == normalized_entry["triage_key"]:
            next_entries.append(normalized_entry)
            replaced = True
        else:
            next_entries.append(entry)
    if not replaced:
        next_entries.append(normalized_entry)
    saved = save_p1_triage_payload(
        {
            "tool": payload.get("tool", TRIAGE_TOOL_NAME),
            "entries": next_entries,
        },
        project_root=project_root,
        backup_reason="upsert",
    )
    paths = get_p1_triage_paths(project_root)
    return {
        "ok": True,
        "entry": normalized_entry,
        "count": len(saved["entries"]),
        "source_file": paths["source_path"].name,
        "source_path": str(paths["source_path"]),
    }


def delete_p1_triage_entry(*, triage_key: str, project_root: Optional[Path] = None) -> Dict[str, Any]:
    payload = load_p1_triage_payload(project_root)
    normalized_key = str(triage_key or "").strip()
    if not normalized_key:
        raise ValueError("triage_key is required")
    next_entries = [entry for entry in payload["entries"] if str(entry.get("triage_key", "")) != normalized_key]
    deleted = len(next_entries) != len(payload["entries"])
    saved = save_p1_triage_payload(
        {
            "tool": payload.get("tool", TRIAGE_TOOL_NAME),
            "entries": next_entries,
        },
        project_root=project_root,
        backup_reason="delete",
    )
    paths = get_p1_triage_paths(project_root)
    return {
        "ok": True,
        "deleted": deleted,
        "triage_key": normalized_key,
        "count": len(saved["entries"]),
        "source_file": paths["source_path"].name,
        "source_path": str(paths["source_path"]),
    }
