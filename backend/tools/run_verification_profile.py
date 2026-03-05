import argparse
import datetime
import json
import subprocess
from pathlib import Path
from typing import Dict, List


OPTIONAL_MISSING_PATTERNS = (
    "openpyxl is required",
    "ModuleNotFoundError: No module named 'openpyxl'",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _profiles() -> Dict[str, List[str]]:
    return {
        "core": [
            "python -m unittest backend.tests.test_api_and_reports -v",
            "python -m unittest backend.tests.test_todo_rule_mining -v",
            "python -m unittest backend.tests.test_winccoa_context_server -v",
            "python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py",
            "python backend/tools/check_config_rule_alignment.py --json",
        ],
        "report": [
            "python backend/tools/analyze_template_coverage.py",
        ],
    }


def classify_status(returncode: int, output: str) -> str:
    text = str(output or "")
    if returncode == 0:
        return "passed"
    if any(pattern in text for pattern in OPTIONAL_MISSING_PATTERNS):
        return "skipped_optional_missing"
    return "failed"


def run_profile(profile: str, include_report: bool = False) -> Dict:
    profiles = _profiles()
    commands = list(profiles.get(profile, []))
    if include_report:
        commands.extend(profiles["report"])

    rows: List[Dict] = []
    for cmd in commands:
        proc = subprocess.run(
            cmd,
            cwd=str(_project_root()),
            shell=True,
            text=True,
            capture_output=True,
        )
        combined_output = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
        rows.append(
            {
                "command": cmd,
                "returncode": int(proc.returncode),
                "status": classify_status(proc.returncode, combined_output),
                "output_tail": "\n".join(combined_output.splitlines()[-20:]),
            }
        )

    summary = {
        "passed": sum(1 for r in rows if r["status"] == "passed"),
        "failed": sum(1 for r in rows if r["status"] == "failed"),
        "skipped_optional_missing": sum(1 for r in rows if r["status"] == "skipped_optional_missing"),
        "total": len(rows),
    }

    return {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "profile": profile,
        "include_report": bool(include_report),
        "summary": summary,
        "checks": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run verification profile and emit JSON summary")
    parser.add_argument("--profile", choices=["core"], default="core")
    parser.add_argument("--include-report", action="store_true", help="Also run report-layer checks")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    args = parser.parse_args()

    payload = run_profile(args.profile, include_report=args.include_report)

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = _project_root() / "CodeReview_Report" / f"verification_summary_{_utc_stamp()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[+] verification summary written: {output_path}")
    print(json.dumps(payload.get("summary", {}), ensure_ascii=False))


if __name__ == "__main__":
    main()
