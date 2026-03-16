#!/usr/bin/env python
import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SYNTAX_FILES = [
    "frontend/renderer.js",
    "frontend/renderer/app-shell.js",
    "frontend/renderer/app-state.js",
    "frontend/renderer/utils.js",
    "frontend/renderer/reviewed-linking.js",
    "frontend/renderer/code-viewer.js",
    "frontend/renderer/detail-panel.js",
    "frontend/renderer/dashboard-panels.js",
    "frontend/renderer/workspace-chrome-helpers.js",
    "frontend/renderer/workspace-view.js",
    "frontend/renderer/workspace-interaction-helpers.js",
    "frontend/renderer/autofix-ai.js",
    "frontend/renderer/rules-manage.js",
    "frontend/renderer/rules-manage-helpers.js",
]


def utc_now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stamp_compact() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def default_output_path() -> Path:
    return PROJECT_ROOT / "CodeReview_Report" / f"release_gate_{stamp_compact()}.json"


def default_markdown_path(json_output_path: Path) -> Path:
    return json_output_path.with_suffix(".md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the WinCC OA release gate and emit a consolidated JSON summary",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--profile", choices=["local", "ci"], default="local", help="Release gate execution profile")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    parser.add_argument("--python", default=sys.executable, help="Python executable")
    parser.add_argument("--node", default="node", help="Node executable")
    parser.add_argument("--benchmark-iterations", type=int, default=3, help="Playwright UI benchmark iterations")
    parser.add_argument("--benchmark-files", type=int, default=20, help="Mock file count for UI benchmark")
    parser.add_argument("--benchmark-violations-per-file", type=int, default=120, help="Mock P1 violations per file")
    parser.add_argument("--benchmark-code-lines", type=int, default=6000, help="Mock code lines per file")
    parser.add_argument("--ui-target-file", default="BenchmarkP1Fixture.ctl", help="Preferred real UI smoke target file")
    parser.add_argument("--with-live-ai", action="store_true", help="Run optional live AI integration check")
    parser.add_argument("--live-ai-with-context", action="store_true", help="Request MCP context during live AI check")
    parser.add_argument("--live-ai-target-file", default="BenchmarkP1Fixture.ctl", help="Preferred file for live AI check")
    parser.add_argument("--live-ai-min-successful-files", type=int, default=1, help="Minimum successful file count for live AI gate")
    parser.add_argument("--live-ai-min-p3-total", type=int, default=1, help="Minimum P3 review count for live AI gate")
    parser.add_argument("--live-ai-min-p1-total", type=int, default=1, help="Minimum P1 issue count for live AI gate")
    parser.add_argument("--live-ai-require-context", action="store_true", help="Fail live AI gate if context was requested but unavailable")
    parser.add_argument("--include-ctrlpp", action="store_true", help="Run Ctrlpp smoke even in profiles that skip it by default")
    parser.add_argument("--include-ui", action="store_true", help="Run UI benchmark/smoke even in profiles that skip them by default")
    parser.add_argument("--skip-ctrlpp", action="store_true", help="Skip Ctrlpp fail-soft smoke")
    parser.add_argument("--skip-ui", action="store_true", help="Skip UI benchmark and real UI smoke")
    parser.add_argument("--markdown-output", default="", help="Optional Markdown summary output path")
    parser.add_argument("--verbose", action="store_true", help="Print command output tails")
    return parser.parse_args()


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except json.JSONDecodeError:
            continue
    return None


def run_command(
    *,
    name: str,
    command: List[str],
    artifact_path: Optional[Path] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    started = datetime.datetime.now(datetime.timezone.utc)
    proc = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    combined = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    row: Dict[str, Any] = {
        "name": name,
        "command": command,
        "returncode": int(proc.returncode),
        "status": "passed" if proc.returncode == 0 else "failed",
        "started_at": started.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "finished_at": utc_now_iso(),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
        "artifact_path": str(artifact_path) if artifact_path else None,
        "_stdout_full": proc.stdout or "",
        "_stderr_full": proc.stderr or "",
    }
    if artifact_path:
        row["artifact_exists"] = artifact_path.exists()
        row["artifact_json"] = read_json(artifact_path)
    if verbose:
        print(f"[{name}] rc={proc.returncode}")
        if row["stdout_tail"]:
            print(row["stdout_tail"])
        if row["stderr_tail"]:
            print(row["stderr_tail"])
    if combined:
        row["output_tail"] = "\n".join(combined.splitlines()[-20:])
    return row


def run_live_ai_check(
    *,
    python_exe: str,
    target_file: str,
    with_context: bool,
    artifact_path: Path,
    verbose: bool = False,
) -> Dict[str, Any]:
    script = """
import json
import sys
import traceback
import urllib.request
from pathlib import Path

project_root = Path(sys.argv[1])
target_file = sys.argv[2]
with_context = sys.argv[3] == "1"
artifact_path = Path(sys.argv[4])
sys.path.insert(0, str(project_root / "backend"))

payload = {
    "tool": "live_ai_release_gate",
    "target_file": target_file,
    "with_context": with_context,
}

try:
    context_status = {"requested": with_context, "available": None}
    if with_context:
        try:
            with urllib.request.urlopen("http://127.0.0.1:3000/context?query=release-gate", timeout=3) as resp:
                context_status["available"] = int(getattr(resp, "status", 0) or 0) == 200
        except Exception:
            context_status["available"] = False
    payload["context"] = context_status

    from main import CodeInspectorApp

    app = CodeInspectorApp()
    result = app.run_directory_analysis(
        selected_files=[target_file],
        enable_live_ai=True,
        ai_with_context=with_context,
    )
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    violations = result.get("violations", {}) if isinstance(result, dict) else {}
    p3 = violations.get("P3", []) if isinstance(violations, dict) else []
    payload["status"] = "passed"
    payload["summary"] = {
        "successful_file_count": int(summary.get("successful_file_count", 0) or 0),
        "failed_file_count": int(summary.get("failed_file_count", 0) or 0),
        "p1_total": int(summary.get("p1_total", 0) or 0),
        "p2_total": int(summary.get("p2_total", 0) or 0),
        "p3_total": int(summary.get("p3_total", 0) or 0),
        "verification_level": summary.get("verification_level"),
        "output_dir": result.get("output_dir", "") if isinstance(result, dict) else "",
    }
    payload["p3_preview"] = p3[:3]
except Exception as exc:
    payload["status"] = "failed"
    payload["error"] = str(exc)
    payload["traceback_tail"] = traceback.format_exc()[-4000:]

artifact_path.parent.mkdir(parents=True, exist_ok=True)
artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
"""
    return run_command(
        name="live_ai",
        command=[
            python_exe,
            "-c",
            script,
            str(PROJECT_ROOT),
            target_file,
            "1" if with_context else "0",
            str(artifact_path),
        ],
        artifact_path=artifact_path,
        verbose=verbose,
    )


def resolve_execution_flags(args: argparse.Namespace) -> Dict[str, bool]:
    profile_defaults = {
        "local": {"run_ctrlpp": True, "run_ui": True},
        "ci": {"run_ctrlpp": False, "run_ui": False},
    }
    defaults = profile_defaults.get(args.profile, profile_defaults["local"])
    run_ctrlpp = bool(defaults["run_ctrlpp"])
    run_ui = bool(defaults["run_ui"])
    if args.include_ctrlpp:
        run_ctrlpp = True
    if args.include_ui:
        run_ui = True
    if args.skip_ctrlpp:
        run_ctrlpp = False
    if args.skip_ui:
        run_ui = False
    return {
        "run_ctrlpp": run_ctrlpp,
        "run_ui": run_ui,
    }


def evaluate_check(row: Dict[str, Any]) -> Dict[str, Any]:
    name = row["name"]
    artifact = row.get("artifact_json") or {}
    expectations = row.get("expectations") or {}
    verdict = {
        "ok": row.get("returncode") == 0,
        "status": row.get("status"),
        "details": [],
    }

    if name == "verification_profile":
        summary = artifact.get("summary") if isinstance(artifact, dict) else None
        if isinstance(summary, dict):
            passed = int(summary.get("passed", 0))
            total = int(summary.get("total", 0))
            failed = int(summary.get("failed", 0))
            verdict["details"].append(f"verification={passed}/{total}, failed={failed}")
            verdict["ok"] = verdict["ok"] and failed == 0 and passed == total and total >= 6
    elif name == "config_alignment":
        summary = artifact.get("summary") if isinstance(artifact, dict) else None
        if isinstance(summary, dict):
            mismatch_count = int(summary.get("mismatch_row_count", -1))
            broken_keys = int(summary.get("review_applicability_broken_key_count", -1))
            dup_semantics = int(summary.get("review_applicability_duplicate_semantic_count", -1))
            unknown_rules = int(summary.get("review_applicability_unknown_rule_id_count", -1))
            verdict["details"].append(
                f"mismatch={mismatch_count}, broken_keys={broken_keys}, duplicate_semantics={dup_semantics}, unknown_rule_ids={unknown_rules}"
            )
            verdict["ok"] = verdict["ok"] and mismatch_count == 0 and broken_keys == 0 and dup_semantics == 0 and unknown_rules == 0
    elif name == "template_coverage":
        coverage = artifact.get("coverage") if isinstance(artifact, dict) else None
        if isinstance(coverage, dict):
            client = coverage.get("Client") or {}
            server = coverage.get("Server") or {}
            c_match = int(client.get("matched_rule_count", -1))
            c_total = int(client.get("rule_count", -1))
            s_match = int(server.get("matched_rule_count", -1))
            s_total = int(server.get("rule_count", -1))
            verdict["details"].append(f"client={c_match}/{c_total}, server={s_match}/{s_total}")
            verdict["ok"] = verdict["ok"] and c_match == c_total and s_match == s_total and c_total > 0 and s_total > 0
    elif name == "ctrlpp_smoke":
        status = str(artifact.get("status", ""))
        verdict["details"].append(f"status={status}")
        verdict["ok"] = verdict["ok"] and status in {"passed", "binary_not_found"}
        if status == "binary_not_found":
            verdict["status"] = "skipped_optional_missing"
    elif name == "ui_benchmark":
        failures = artifact.get("threshold_failures") if isinstance(artifact, dict) else None
        summary = artifact.get("summary") if isinstance(artifact, dict) else None
        if isinstance(summary, dict):
            verdict["details"].append(
                "p95 analyze={a}, table={t}, jump={j}, code={c}".format(
                    a=(summary.get("analyzeUiMs") or {}).get("p95"),
                    t=(summary.get("resultTableScrollMs") or {}).get("p95"),
                    j=(summary.get("codeJumpMs") or {}).get("p95"),
                    c=(summary.get("codeViewerScrollMs") or {}).get("p95"),
                )
            )
        verdict["ok"] = verdict["ok"] and not failures
    elif name == "ui_real_smoke":
        ok = bool(artifact.get("ok"))
        run = artifact.get("run") or {}
        after = run.get("afterRun") or {}
        before = run.get("beforeClick") or {}
        intercepting = before.get("interceptingNode") or {}
        row_count = after.get("rows")
        if row_count is None:
            row_count = after.get("result_row_count")
        total_issues = after.get("totalIssues")
        if total_issues is None:
            total_issues = after.get("total_issues")
        workspace_visible = after.get("workspaceVisible")
        if workspace_visible is None:
            workspace_visible = after.get("workspace_visible")
        verdict["details"].append(
            f"rows={row_count}, total={total_issues}, intercept_id={intercepting.get('id')}"
        )
        verdict["ok"] = verdict["ok"] and ok and bool(workspace_visible) and int(row_count or 0) > 0
    elif name == "live_ai":
        status = str(artifact.get("status", ""))
        summary = artifact.get("summary") or {}
        context = artifact.get("context") or {}
        min_successful = int(expectations.get("min_successful_files", 1) or 1)
        min_p3_total = int(expectations.get("min_p3_total", 1) or 1)
        min_p1_total = int(expectations.get("min_p1_total", 0) or 0)
        require_context = bool(expectations.get("require_context", False))
        context_available = context.get("available")
        verdict["details"].append(
            "status={status}, p1_total={p1}, p3_total={p3}, successful_files={success}, context_available={ctx}".format(
                status=status,
                p1=summary.get("p1_total"),
                p3=summary.get("p3_total"),
                success=summary.get("successful_file_count"),
                ctx=context_available,
            )
        )
        verdict["ok"] = (
            verdict["ok"]
            and status == "passed"
            and int(summary.get("successful_file_count", 0) or 0) >= min_successful
            and int(summary.get("p3_total", 0) or 0) >= min_p3_total
            and int(summary.get("p1_total", 0) or 0) >= min_p1_total
            and (not require_context or context_available is True)
        )
    elif name == "frontend_unit":
        verdict["details"].append("vitest frontend unit suite")
    return verdict


def summarize_checks(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = []
    for row in rows:
        verdict = evaluate_check(row)
        item = {
            "name": row["name"],
            "status": verdict["status"],
            "ok": verdict["ok"],
            "details": verdict["details"],
            "artifact_path": row.get("artifact_path"),
        }
        results.append(item)
    failed = [item for item in results if not item["ok"]]
    skipped = [item for item in results if item["status"] == "skipped_optional_missing"]
    passed = [item for item in results if item["ok"] and item["status"] != "skipped_optional_missing"]
    return {
        "passed_count": len(passed),
        "failed_count": len(failed),
        "skipped_optional_missing_count": len(skipped),
        "total_count": len(results),
        "status": "passed" if not failed else "failed",
        "results": results,
    }


def build_markdown_summary(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Release Gate Summary",
        "",
        f"- Status: `{summary.get('status', 'unknown')}`",
        f"- Passed: `{summary.get('passed_count', 0)}`",
        f"- Failed: `{summary.get('failed_count', 0)}`",
        f"- Skipped optional missing: `{summary.get('skipped_optional_missing_count', 0)}`",
        f"- Generated at: `{payload.get('finished_at', '')}`",
        "",
        "## Checks",
        "",
    ]
    for item in summary.get("results", []):
        status_label = "PASS" if item.get("ok") else str(item.get("status", "unknown")).upper()
        details = "; ".join(item.get("details") or [])
        artifact_path = item.get("artifact_path") or ""
        line = f"- `{item.get('name')}`: `{status_label}`"
        if details:
            line += f" - {details}"
        if artifact_path:
            line += f" - artifact: `{artifact_path}`"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    flags = resolve_execution_flags(args)
    output_path = Path(args.output).resolve() if args.output else default_output_path()
    markdown_path = Path(args.markdown_output).resolve() if args.markdown_output else default_markdown_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    artifact_dir = output_path.parent
    verification_artifact = artifact_dir / f"verification_summary_release_gate_{stamp_compact()}.json"
    config_alignment_artifact = artifact_dir / f"config_alignment_release_gate_{stamp_compact()}.json"
    template_coverage_artifact = artifact_dir / f"template_coverage_release_gate_{stamp_compact()}.json"
    ctrlpp_artifact = PROJECT_ROOT / "tools" / "integration_results" / f"ctrlpp_release_gate_{stamp_compact()}.json"
    ui_benchmark_artifact = PROJECT_ROOT / "tools" / "benchmark_results" / f"ui_benchmark_release_gate_{stamp_compact()}.json"
    ui_smoke_artifact = PROJECT_ROOT / "tools" / "integration_results" / f"ui_real_smoke_release_gate_{stamp_compact()}.json"
    live_ai_artifact = PROJECT_ROOT / "tools" / "integration_results" / f"live_ai_release_gate_{stamp_compact()}.json"

    checks: List[Dict[str, Any]] = []

    checks.append(
        run_command(
            name="backend_unittest_discover",
            command=[
                args.python,
                "-m",
                "unittest",
                "backend.tests.test_api_and_reports",
                "backend.tests.test_todo_rule_mining",
                "backend.tests.test_winccoa_context_server",
                "-v",
            ],
            verbose=args.verbose,
        )
    )
    checks.append(
        run_command(
            name="verification_profile",
            command=[
                args.python,
                "backend/tools/run_verification_profile.py",
                "--profile",
                "core",
                "--include-report",
                "--output",
                str(verification_artifact),
            ],
            artifact_path=verification_artifact,
            verbose=args.verbose,
        )
    )
    checks.append(
        run_command(
            name="config_alignment",
            command=[args.python, "backend/tools/check_config_rule_alignment.py", "--json"],
            artifact_path=config_alignment_artifact,
            verbose=args.verbose,
        )
    )
    checks[-1]["artifact_path"] = str(config_alignment_artifact)
    if checks[-1].get("_stdout_full"):
        config_alignment_artifact.write_text(
            json.dumps(json.loads(checks[-1]["_stdout_full"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        checks[-1]["artifact_exists"] = True
        checks[-1]["artifact_json"] = read_json(config_alignment_artifact)

    checks.append(
        run_command(
            name="template_coverage",
            command=[args.python, "backend/tools/analyze_template_coverage.py"],
            verbose=args.verbose,
        )
    )
    template_row = checks[-1]
    generated_path = None
    for line in (template_row.get("stdout_tail") or "").splitlines():
        if "Coverage report saved:" in line:
            generated_path = line.split("Coverage report saved:", 1)[1].strip()
            break
    if generated_path:
        generated = Path(generated_path)
        template_row["artifact_path"] = str(generated)
        template_row["artifact_exists"] = generated.exists()
        template_row["artifact_json"] = read_json(generated)
        if generated.exists():
            template_coverage_artifact.write_text(generated.read_text(encoding="utf-8"), encoding="utf-8")

    checks.append(
        run_command(
            name="warning_gate",
            command=[
                args.python,
                "-W",
                "error::DeprecationWarning",
                "-m",
                "unittest",
                "backend.tests.test_api_and_reports",
                "backend.tests.test_winccoa_context_server",
            ],
            verbose=args.verbose,
        )
    )
    checks.append(
        run_command(
            name="frontend_syntax",
            command=[
                args.python,
                "-c",
                "\n".join([
                    "import subprocess",
                    "import sys",
                    "node = sys.argv[1]",
                    "files = sys.argv[2:]",
                    "failed = 0",
                    "for path in files:",
                    "    print(f'[frontend_syntax] {path}')",
                    "    rc = subprocess.run([node, '--check', path]).returncode",
                    "    failed = failed or rc",
                    "sys.exit(failed)",
                ]),
                args.node,
                *FRONTEND_SYNTAX_FILES,
            ],
            verbose=args.verbose,
        )
    )
    checks.append(
        run_command(
            name="frontend_unit",
            command=[args.node, str(PROJECT_ROOT / "node_modules" / "vitest" / "vitest.mjs"), "run"],
            verbose=args.verbose,
        )
    )

    if flags["run_ctrlpp"]:
        checks.append(
            run_command(
                name="ctrlpp_smoke",
                command=[
                    args.python,
                    "tools/run_ctrlpp_integration_smoke.py",
                    "--allow-missing-binary",
                    "--skip-unittest",
                    "--output-json",
                    str(ctrlpp_artifact),
                ],
                artifact_path=ctrlpp_artifact,
                verbose=args.verbose,
            )
        )

    if flags["run_ui"]:
        checks.append(
            run_command(
                name="ui_benchmark",
                command=[
                    args.node,
                    "tools/playwright_ui_benchmark.js",
                    "--iterations",
                    str(args.benchmark_iterations),
                    "--files",
                    str(args.benchmark_files),
                    "--violations-per-file",
                    str(args.benchmark_violations_per_file),
                    "--code-lines",
                    str(args.benchmark_code_lines),
                    "--output",
                    str(ui_benchmark_artifact),
                ],
                artifact_path=ui_benchmark_artifact,
                verbose=args.verbose,
            )
        )
        checks.append(
            run_command(
                name="ui_real_smoke",
                command=[
                    args.node,
                    "tools/playwright_ui_real_smoke.js",
                    "--target-file",
                    args.ui_target_file,
                    "--output",
                    str(ui_smoke_artifact),
                ],
                artifact_path=ui_smoke_artifact,
                verbose=args.verbose,
            )
        )

    if args.with_live_ai:
        live_ai_row = run_live_ai_check(
            python_exe=args.python,
            target_file=args.live_ai_target_file,
            with_context=bool(args.live_ai_with_context),
            artifact_path=live_ai_artifact,
            verbose=args.verbose,
        )
        live_ai_row["expectations"] = {
            "min_successful_files": int(args.live_ai_min_successful_files),
            "min_p3_total": int(args.live_ai_min_p3_total),
            "min_p1_total": int(args.live_ai_min_p1_total),
            "require_context": bool(args.live_ai_require_context or args.live_ai_with_context),
        }
        checks.append(live_ai_row)

    summary = summarize_checks(checks)
    payload = {
        "tool": "release_gate",
        "started_at": checks[0]["started_at"] if checks else utc_now_iso(),
        "finished_at": utc_now_iso(),
        "project_root": str(PROJECT_ROOT),
        "config": {
            "profile": args.profile,
            "python": args.python,
            "node": args.node,
            "benchmark_iterations": args.benchmark_iterations,
            "benchmark_files": args.benchmark_files,
            "benchmark_violations_per_file": args.benchmark_violations_per_file,
            "benchmark_code_lines": args.benchmark_code_lines,
            "ui_target_file": args.ui_target_file,
            "with_live_ai": bool(args.with_live_ai),
            "live_ai_with_context": bool(args.live_ai_with_context),
            "live_ai_target_file": args.live_ai_target_file,
            "live_ai_min_successful_files": int(args.live_ai_min_successful_files),
            "live_ai_min_p3_total": int(args.live_ai_min_p3_total),
            "live_ai_min_p1_total": int(args.live_ai_min_p1_total),
            "live_ai_require_context": bool(args.live_ai_require_context or args.live_ai_with_context),
            "run_ctrlpp": bool(flags["run_ctrlpp"]),
            "run_ui": bool(flags["run_ui"]),
        },
        "summary": summary,
        "checks": checks,
    }
    for row in payload["checks"]:
        row.pop("_stdout_full", None)
        row.pop("_stderr_full", None)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(build_markdown_summary(payload), encoding="utf-8")

    print("[Release Gate]")
    print(f"- status: {summary['status']}")
    print(f"- passed: {summary['passed_count']}")
    print(f"- skipped optional missing: {summary['skipped_optional_missing_count']}")
    print(f"- failed: {summary['failed_count']}")
    for item in summary["results"]:
        detail = f" ({'; '.join(item['details'])})" if item["details"] else ""
        print(f"- {item['name']}: {'PASS' if item['ok'] else item['status'].upper()}{detail}")
    print(f"- report: {output_path}")
    print(f"- markdown: {markdown_path}")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
