#!/usr/bin/env python
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import CodeInspectorApp  # noqa: E402

DEFAULT_TEST_NAME = (
    "backend.tests.test_api_and_reports."
    "ApiIntegrationTests.test_autofix_apply_ctrlpp_regression_check_real_binary_optional"
)


def utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run executable CtrlppCheck integration smoke + optional unittest harness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--binary", default="", help="Explicit ctrlppcheck binary path (overrides auto-discovery)")
    parser.add_argument("--sample-file", default="", help="Use an existing .ctl file for direct smoke run")
    parser.add_argument("--skip-direct", action="store_true", help="Skip direct CtrlppWrapper.run_check smoke")
    parser.add_argument("--skip-unittest", action="store_true", help="Skip optional unittest harness execution")
    parser.add_argument("--test-name", default=DEFAULT_TEST_NAME, help="Unittest test target to run")
    parser.add_argument("--timeout-sec", type=int, default=180, help="Timeout for unittest subprocess")
    parser.add_argument(
        "--output-json",
        default="",
        help="Write structured JSON result (default: tools/integration_results/ctrlpp_integration_<ts>.json)",
    )
    parser.add_argument(
        "--allow-missing-binary",
        action="store_true",
        help="Exit 0 even when CtrlppCheck binary is not found (report will mark status accordingly)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print detailed subprocess stdout/stderr tails")
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_output_path() -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    return PROJECT_ROOT / "tools" / "integration_results" / f"ctrlpp_integration_{stamp}.json"


def finding_messages(findings: List[Dict[str, Any]]) -> List[str]:
    messages: List[str] = []
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        msg = str(item.get("message", "") or "").strip()
        if msg:
            messages.append(msg)
    return messages


def finding_types(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("type") or item.get("severity") or "unknown").strip().lower() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def classify_direct_smoke(findings: List[Dict[str, Any]], binary_found: bool) -> Dict[str, Any]:
    msgs = finding_messages(findings)
    joined = "\n".join(msgs).lower()
    error_markers = [
        "binary not found",
        "execution error",
        "timed out",
        "failed (exit=",
        "xml parse error",
        "returned no xml output",
    ]
    infra_error = any(marker in joined for marker in error_markers)
    ok = bool(binary_found) and not infra_error
    return {
        "ok": ok,
        "infra_error": infra_error,
        "finding_count": len(findings or []),
        "finding_type_counts": finding_types(findings or []),
        "messages_tail": msgs[-5:],
    }


def make_sample_ctl_content() -> str:
    return (
        "main()\n"
        "{\n"
        "  int x = 0;\n"
        "  x = x + 1;\n"
        "  DebugN(\"ctrlpp smoke\", x);\n"
        "}\n"
    )


def run_direct_smoke(app: CodeInspectorApp, binary_path: str, sample_file: str) -> Dict[str, Any]:
    started = time.perf_counter()
    findings: List[Dict[str, Any]] = []
    used_path = ""
    temp_dir_ctx = None
    try:
        if sample_file:
            used_path = sample_file
            findings = app.ctrl_tool.run_check(used_path, enabled=True, binary_path=binary_path or None)
        else:
            temp_dir_ctx = tempfile.TemporaryDirectory()
            used_path = os.path.join(temp_dir_ctx.name, "ctrlpp_integration_smoke_sample.ctl")
            with open(used_path, "w", encoding="utf-8") as f:
                f.write(make_sample_ctl_content())
            findings = app.ctrl_tool.run_check(used_path, enabled=True, binary_path=binary_path or None)
    finally:
        if temp_dir_ctx is not None:
            temp_dir_ctx.cleanup()
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    summary = classify_direct_smoke(findings, binary_found=bool(binary_path))
    summary.update(
        {
            "sample_file": used_path,
            "elapsed_ms": elapsed_ms,
            "raw_findings_preview": (findings or [])[:5],
        }
    )
    return summary


def run_unittest_harness(test_name: str, timeout_sec: int, binary_path: str, verbose: bool) -> Dict[str, Any]:
    env = os.environ.copy()
    env["RUN_CTRLPPCHECK_INTEGRATION"] = "1"
    if binary_path:
        env["CTRLPPCHECK_PATH"] = binary_path

    cmd = [sys.executable, "-m", "unittest", test_name]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=max(10, int(timeout_sec)),
            encoding="utf-8",
            errors="ignore",
            env=env,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = exc
        timed_out = True
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if timed_out:
        stdout_text = str(getattr(proc, "stdout", "") or "")
        stderr_text = str(getattr(proc, "stderr", "") or "")
        result = {
            "ok": False,
            "timed_out": True,
            "elapsed_ms": elapsed_ms,
            "returncode": None,
            "command": cmd,
            "stdout_tail": stdout_text[-2000:],
            "stderr_tail": stderr_text[-2000:],
            "status": "timeout",
        }
        if verbose:
            print("[unittest stdout tail]\n" + result["stdout_tail"])
            print("[unittest stderr tail]\n" + result["stderr_tail"])
        return result

    stdout_text = str(proc.stdout or "")
    stderr_text = str(proc.stderr or "")
    combined = (stdout_text + "\n" + stderr_text).lower()
    skipped = "skipped" in combined and ("ok (skipped=" in combined or "skipped=" in combined)
    ok = (proc.returncode == 0)
    status = "passed" if ok and not skipped else ("skipped" if ok and skipped else "failed")

    result = {
        "ok": ok,
        "timed_out": False,
        "elapsed_ms": elapsed_ms,
        "returncode": proc.returncode,
        "command": cmd,
        "stdout_tail": stdout_text[-2000:],
        "stderr_tail": stderr_text[-2000:],
        "status": status,
    }
    if verbose:
        print("[unittest stdout tail]\n" + result["stdout_tail"])
        print("[unittest stderr tail]\n" + result["stderr_tail"])
    return result


def main() -> int:
    args = parse_args()
    output_path = Path(args.output_json) if args.output_json else default_output_path()
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    report: Dict[str, Any] = {
        "tool": "ctrlpp_integration_smoke",
        "started_at": utc_now(),
        "project_root": str(PROJECT_ROOT),
        "config": {
            "binary": args.binary,
            "sample_file": args.sample_file,
            "skip_direct": bool(args.skip_direct),
            "skip_unittest": bool(args.skip_unittest),
            "test_name": args.test_name,
            "timeout_sec": int(args.timeout_sec),
            "allow_missing_binary": bool(args.allow_missing_binary),
        },
        "binary": {"requested": args.binary or None, "resolved": None, "exists": False},
        "direct_smoke": None,
        "unittest_harness": None,
        "status": "unknown",
    }

    try:
        app = CodeInspectorApp()
        app.ctrl_tool.auto_install_on_missing = False
        if args.binary:
            app.ctrl_tool.tool_path = args.binary

        resolved_binary = app.ctrl_tool._find_binary(binary_path=(args.binary or None))
        report["binary"] = {
            "requested": args.binary or None,
            "resolved": resolved_binary or None,
            "exists": bool(resolved_binary and os.path.exists(resolved_binary)),
        }

        if not resolved_binary:
            report["status"] = "binary_not_found"
            report["message"] = "CtrlppCheck binary not found. Configure CTRLPPCHECK_PATH or Config/config.json ctrlppcheck.binary_path."
            write_json(output_path, report)
            print(f"CtrlppCheck binary not found. Report written: {output_path}")
            return 0 if args.allow_missing_binary else 2

        print(f"CtrlppCheck binary: {resolved_binary}")

        if not args.skip_direct:
            print("Running direct CtrlppWrapper.run_check smoke...")
            direct = run_direct_smoke(app, resolved_binary, args.sample_file)
            report["direct_smoke"] = direct
            print(
                f"- direct_smoke: ok={direct.get('ok')} infra_error={direct.get('infra_error')} "
                f"finding_count={direct.get('finding_count')} elapsed_ms={direct.get('elapsed_ms')}"
            )

        if not args.skip_unittest:
            print(f"Running unittest harness: {args.test_name}")
            harness = run_unittest_harness(args.test_name, args.timeout_sec, resolved_binary, args.verbose)
            report["unittest_harness"] = harness
            print(
                f"- unittest_harness: status={harness.get('status')} returncode={harness.get('returncode')} "
                f"elapsed_ms={harness.get('elapsed_ms')}"
            )

        direct_ok = True if args.skip_direct else bool((report.get("direct_smoke") or {}).get("ok"))
        unittest_ok = True if args.skip_unittest else bool((report.get("unittest_harness") or {}).get("ok"))
        if direct_ok and unittest_ok:
            report["status"] = "passed"
            exit_code = 0
        else:
            report["status"] = "failed"
            exit_code = 1

        report["finished_at"] = utc_now()
        write_json(output_path, report)
        print(f"Report written: {output_path}")
        return exit_code
    except Exception as exc:  # pragma: no cover - script-level guard
        report["status"] = "error"
        report["error"] = str(exc)
        report["finished_at"] = utc_now()
        write_json(output_path, report)
        print(f"Script error: {exc}")
        print(f"Report written: {output_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
