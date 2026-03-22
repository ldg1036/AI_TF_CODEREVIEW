import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


TIMESTAMP_RE = re.compile(
    r"^(?P<prefix>.+?)_(?:\d{14,}|\d{8}(?:_\d{6,})?)(?:_[0-9a-f]+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CleanupCandidate:
    path: str
    reason: str
    bucket: str


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def _artifact_prefix(name: str) -> str:
    stem = Path(name).stem
    match = TIMESTAMP_RE.match(stem)
    if match:
        return str(match.group("prefix") or stem)
    return stem


def _list_existing(paths: Iterable[Path]) -> List[Path]:
    return [path for path in paths if path.exists()]


def _mtime_desc(paths: Sequence[Path]) -> List[Path]:
    return sorted(paths, key=lambda item: (item.stat().st_mtime, item.name.lower()), reverse=True)


def _group_by_prefix(paths: Sequence[Path]) -> Dict[str, List[Path]]:
    grouped: Dict[str, List[Path]] = {}
    for path in paths:
        grouped.setdefault(_artifact_prefix(path.name), []).append(path)
    return grouped


def _select_stale_by_prefix(paths: Sequence[Path], *, keep_per_prefix: int = 1) -> Tuple[List[CleanupCandidate], List[str]]:
    candidates: List[CleanupCandidate] = []
    kept: List[str] = []
    for bucket, bucket_paths in _group_by_prefix(paths).items():
        ordered = _mtime_desc(bucket_paths)
        for keep_path in ordered[:keep_per_prefix]:
            kept.append(str(keep_path))
        for stale_path in ordered[keep_per_prefix:]:
            candidates.append(CleanupCandidate(path=str(stale_path), reason=f"stale_{bucket}", bucket=bucket))
    return candidates, kept


def _select_stale_by_recency(
    paths: Sequence[Path],
    *,
    keep_count: int,
    bucket: str,
    reason: str,
) -> Tuple[List[CleanupCandidate], List[str]]:
    ordered = _mtime_desc(paths)
    kept = [str(path) for path in ordered[:keep_count]]
    candidates = [
        CleanupCandidate(path=str(path), reason=reason, bucket=bucket)
        for path in ordered[keep_count:]
    ]
    return candidates, kept


def build_cleanup_plan(root: str) -> Dict[str, object]:
    repo_root = Path(root).resolve()
    keep: List[str] = []
    candidates: List[CleanupCandidate] = []

    integration_dir = repo_root / "tools" / "integration_results"
    if integration_dir.is_dir():
        items = _list_existing(integration_dir.iterdir())
        stale, kept = _select_stale_by_prefix(items, keep_per_prefix=1)
        candidates.extend(stale)
        keep.extend(kept)

    runtime_dir = repo_root / "workspace" / "runtime"
    if runtime_dir.is_dir():
        full_audits = _list_existing(runtime_dir.glob("full_audit_*"))
        stale, kept = _select_stale_by_recency(
            full_audits,
            keep_count=3,
            bucket="workspace_runtime_full_audit",
            reason="stale_runtime_audit",
        )
        candidates.extend(stale)
        keep.extend(kept)

        audit_backups_dir = runtime_dir / "audit_backups"
        if audit_backups_dir.is_dir():
            backup_dirs = _list_existing(audit_backups_dir.iterdir())
            stale, kept = _select_stale_by_recency(
                backup_dirs,
                keep_count=3,
                bucket="workspace_runtime_audit_backup",
                reason="stale_runtime_audit_backup",
            )
            candidates.extend(stale)
            keep.extend(kept)

    report_dir = repo_root / "CodeReview_Report"
    if report_dir.is_dir():
        report_files = _list_existing(path for path in report_dir.iterdir() if path.is_file())
        stale, kept = _select_stale_by_prefix(report_files, keep_per_prefix=1)
        candidates.extend(stale)
        keep.extend(kept)

        analysis_dirs = [
            path
            for path in report_dir.iterdir()
            if path.is_dir() and (path / "analysis_summary.json").exists()
        ]
        stale, kept = _select_stale_by_recency(
            analysis_dirs,
            keep_count=4,
            bucket="code_review_report_analysis",
            reason="stale_analysis_report",
        )
        candidates.extend(stale)
        keep.extend(kept)

    candidates = sorted(candidates, key=lambda item: item.path.lower())
    return {
        "root": str(repo_root),
        "candidate_count": len(candidates),
        "keep_count": len(keep),
        "candidates": [candidate.__dict__ for candidate in candidates],
        "keep": sorted(keep),
    }


def _safe_move_path(source: Path, destination_root: Path, *, repo_root: Path) -> Dict[str, object]:
    relative = source.resolve().relative_to(repo_root.resolve())
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    unique_destination = destination
    if unique_destination.exists():
        suffix = datetime.now().strftime("%H%M%S%f")
        unique_destination = unique_destination.with_name(f"{unique_destination.stem}_{suffix}{unique_destination.suffix}")
    try:
        shutil.move(str(source), str(unique_destination))
        return {
            "path": str(source),
            "status": "moved",
            "destination": str(unique_destination),
        }
    except PermissionError:
        return {
            "path": str(source),
            "status": "skipped_locked",
            "destination": str(unique_destination),
        }
    except OSError as exc:
        return {
            "path": str(source),
            "status": "skipped_locked" if "being used" in str(exc).lower() else "skipped_error",
            "destination": str(unique_destination),
            "error": str(exc),
        }


def apply_cleanup_plan(plan: Dict[str, object], *, root: str) -> Dict[str, object]:
    repo_root = Path(root).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bk_root = repo_root / "bk" / "runtime_cleanup" / timestamp
    results: List[Dict[str, object]] = []
    for item in plan.get("candidates", []) or []:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path", "") or ""))
        if not path.exists():
            results.append({
                "path": str(path),
                "status": "missing",
            })
            continue
        results.append(_safe_move_path(path, bk_root, repo_root=repo_root))
    return {
        "root": str(repo_root),
        "bk_root": str(bk_root),
        "results": results,
        "moved_count": sum(1 for item in results if item.get("status") == "moved"),
        "skipped_locked_count": sum(1 for item in results if item.get("status") == "skipped_locked"),
        "missing_count": sum(1 for item in results if item.get("status") == "missing"),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or apply cleanup for runtime artifacts.")
    parser.add_argument("--apply", action="store_true", help="Move cleanup candidates into bk/runtime_cleanup.")
    parser.add_argument("--root", default=str(_repo_root_from_script()), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_cleanup_plan(args.root)
    payload: Dict[str, object] = {
        "mode": "apply" if args.apply else "dry_run",
        "plan": plan,
    }
    if args.apply:
        payload["apply"] = apply_cleanup_plan(plan, root=args.root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
