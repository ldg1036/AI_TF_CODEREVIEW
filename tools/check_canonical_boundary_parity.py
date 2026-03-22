#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run txt/pnl UI smoke checks and verify canonical boundary parity.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--node", default="node", help="Node executable")
    parser.add_argument("--timeout-ms", type=int, default=120000, help="Per-smoke timeout")
    parser.add_argument("--txt-target", default="POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt", help="Canonical txt target")
    parser.add_argument("--pnl-target", default="POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl", help="Alias pnl target")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"failed to parse JSON artifact: {path}")


def metric_snapshot(report: Dict[str, Any]) -> Dict[str, Any]:
    after = ((report or {}).get("run") or {}).get("afterRun") or {}
    return {
        "ok": bool((report or {}).get("ok")),
        "target": ((report or {}).get("config") or {}).get("target_file_preference", ""),
        "total_issues": int(after.get("total_issues") or 0),
        "review_target_count": int(after.get("review_target_count") or 0),
        "result_row_count": int(after.get("result_row_count") or 0),
        "unknown_rule_row_count": int(after.get("unknown_rule_row_count") or 0),
        "selected_file_count": int((((after.get("renderer_diagnostics") or {}).get("selected_file_count")) or 0)),
    }


def run_smoke(node: str, timeout_ms: int, target: str, artifact_path: Path) -> Dict[str, Any]:
    command = [
        node,
        "tools/playwright_ui_real_smoke.js",
        "--timeout-ms",
        str(int(timeout_ms)),
        "--target-file",
        str(target),
        "--output",
        str(artifact_path),
    ]
    completed = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    payload = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "artifact_path": str(artifact_path),
        "artifact_exists": artifact_path.exists(),
        "report": {},
        "metrics": {},
    }
    if artifact_path.exists():
        report = read_json(artifact_path)
        payload["report"] = report
        payload["metrics"] = metric_snapshot(report)
    return payload


def main() -> int:
    args = parse_args()
    output_path = Path(args.output) if args.output else PROJECT_ROOT / "tools" / "integration_results" / "canonical_boundary_parity.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = output_path.stem.replace(".json", "")
    txt_artifact = output_path.parent / f"{stamp}_txt_smoke.json"
    pnl_artifact = output_path.parent / f"{stamp}_pnl_smoke.json"

    txt = run_smoke(args.node, args.timeout_ms, args.txt_target, txt_artifact)
    pnl = run_smoke(args.node, args.timeout_ms, args.pnl_target, pnl_artifact)

    txt_metrics = txt.get("metrics") or {}
    pnl_metrics = pnl.get("metrics") or {}
    parity = {
        "txt_ok": bool(txt_metrics.get("ok")) and txt.get("returncode") == 0,
        "pnl_ok": bool(pnl_metrics.get("ok")) and pnl.get("returncode") == 0,
        "total_equal": int(txt_metrics.get("total_issues") or 0) == int(pnl_metrics.get("total_issues") or 0),
        "review_target_equal": int(txt_metrics.get("review_target_count") or 0) == int(pnl_metrics.get("review_target_count") or 0),
        "result_row_equal": int(txt_metrics.get("result_row_count") or 0) == int(pnl_metrics.get("result_row_count") or 0),
        "unknown_zero": int(txt_metrics.get("unknown_rule_row_count") or 0) == 0 and int(pnl_metrics.get("unknown_rule_row_count") or 0) == 0,
        "single_selection": int(txt_metrics.get("selected_file_count") or 0) == 1 and int(pnl_metrics.get("selected_file_count") or 0) == 1,
    }
    ok = all(parity.values())
    payload = {
        "tool": "canonical_boundary_parity",
        "status": "passed" if ok else "failed",
        "ok": ok,
        "txt": txt,
        "pnl": pnl,
        "parity": parity,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
