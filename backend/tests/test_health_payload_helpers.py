import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.health_payload_helpers import (  # noqa: E402
    build_analysis_diff_payload,
    build_analysis_diff_unavailable_payload,
    build_analysis_run_collection,
    build_rules_health_payload,
    build_verification_latest_unavailable_payload,
    compute_operational_delta,
    summarize_ui_benchmark_payload,
    summarize_ui_real_smoke_payload,
)


class HealthPayloadHelpersTests(unittest.TestCase):
    def test_build_rules_health_payload_counts_detectors_and_dependencies(self):
        payload = build_rules_health_payload(
            [
                {"enabled": True, "detector": {"kind": "regex"}},
                {"enabled": False, "detector": {"kind": "composite"}},
                {"enabled": True, "detector": {"kind": "line_repeat"}},
            ],
            [{"type": "Client"}, {"type": "Server"}, {"type": "Client"}],
            {
                "openpyxl": {"available": True},
                "ctrlppcheck": {"available": False},
                "playwright": {"available": False},
            },
            generated_at_ms=123456,
        )

        self.assertEqual(payload["generated_at_ms"], 123456)
        self.assertEqual(payload["status"], "degraded")
        self.assertIn("CtrlppCheck missing", payload["message"])
        self.assertEqual(payload["rules"]["p1_total"], 3)
        self.assertEqual(payload["rules"]["p1_enabled"], 2)
        self.assertEqual(payload["rules"]["detector_counts"]["regex"], 1)
        self.assertEqual(payload["rules"]["detector_counts"]["composite"], 1)
        self.assertEqual(payload["rules"]["detector_counts"]["line_repeat"], 1)
        self.assertEqual(payload["rules"]["file_type_counts"]["Client"], 2)
        self.assertEqual(payload["rules"]["file_type_counts"]["Server"], 1)

    def test_summarize_operational_payloads_and_delta(self):
        benchmark_summary = summarize_ui_benchmark_payload(
            {
                "summary": {
                    "analyzeUiMs": {"avg": 210},
                    "resultTableScrollMs": {"avg": 15},
                    "codeJumpMs": {"avg": 40},
                },
                "threshold_failures": [],
                "finished_at": "2026-01-01T02:02:02Z",
            }
        )
        smoke_summary = summarize_ui_real_smoke_payload(
            {
                "ok": True,
                "backend": {"selected_target_file": "GoldenTime.ctl"},
                "run": {"elapsed_ms": 777, "afterRun": {"rows": 6, "totalIssues": "6"}},
                "finished_at": "2026-01-01T02:02:02Z",
            }
        )
        delta = compute_operational_delta(
            "ui_benchmark",
            {"analyze_ui_avg_ms": 210, "code_jump_avg_ms": 40},
            {"analyze_ui_avg_ms": 240, "code_jump_avg_ms": 50},
        )

        self.assertEqual(benchmark_summary["status"], "passed")
        self.assertEqual(benchmark_summary["analyze_ui_avg_ms"], 210.0)
        self.assertEqual(smoke_summary["selected_file"], "GoldenTime.ctl")
        self.assertEqual(smoke_summary["rows"], 6)
        self.assertEqual(delta["analyze_ui_avg_ms"], -30.0)
        self.assertEqual(delta["code_jump_avg_ms"], -10.0)

    def test_build_analysis_run_collection_includes_invalid_run_summary(self):
        payload = build_analysis_run_collection(
            [{"timestamp": "20260101_020202"}],
            ["analysis summary not found: D:/runs/20260101_010101/analysis_summary.json"],
        )

        self.assertEqual(len(payload["runs"]), 1)
        self.assertEqual(payload["invalid_run_count"], 1)
        self.assertTrue(payload["warnings"])
        self.assertIn("skipped 1 invalid run", payload["message"])

    def test_build_analysis_diff_unavailable_payload_preserves_shape(self):
        payload = build_analysis_diff_unavailable_payload(
            latest={"timestamp": "20260101_020202", "summary": {"total": 1}, "report_paths": {}},
            secondary_message="skipped 1 invalid run(s): analysis summary not found",
            warnings=["analysis summary not found"],
            invalid_run_count=1,
        )

        self.assertFalse(payload["available"])
        self.assertIn("비교 가능한 최근 2회", payload["message"])
        self.assertIn("skipped 1 invalid run", payload["message"])
        self.assertEqual(payload["latest"]["timestamp"], "20260101_020202")
        self.assertEqual(payload["delta"]["summary"], {})
        self.assertEqual(payload["file_diffs"], [])
        self.assertEqual(payload["invalid_run_count"], 1)

    def test_build_analysis_diff_payload_computes_summary_and_file_statuses(self):
        payload = build_analysis_diff_payload(
            {
                "timestamp": "20260101_020202",
                "request_id": "new-run",
                "summary": {"total": 5, "p1_total": 3, "warning": 3, "info": 1},
                "report_paths": {"html": "combined_analysis_report.html"},
                "file_summaries": [
                    {"file": "sample.ctl", "p1_total": 3, "p2_total": 1, "p3_total": 0, "critical": 1, "warning": 3, "info": 0, "total": 4},
                    {"file": "other.ctl", "p1_total": 0, "p2_total": 0, "p3_total": 1, "critical": 0, "warning": 0, "info": 1, "total": 1},
                ],
            },
            {
                "timestamp": "20260101_010101",
                "request_id": "old-run",
                "summary": {"total": 3, "p1_total": 2, "warning": 2, "info": 0},
                "report_paths": {"html": "combined_analysis_report.html"},
                "file_summaries": [
                    {"file": "sample.ctl", "p1_total": 2, "p2_total": 1, "p3_total": 0, "critical": 1, "warning": 2, "info": 0, "total": 3}
                ],
            },
            warnings=["analysis summary not found"],
            invalid_run_count=1,
        )

        self.assertTrue(payload["available"])
        self.assertEqual(payload["latest"]["request_id"], "new-run")
        self.assertEqual(payload["previous"]["request_id"], "old-run")
        self.assertEqual(payload["delta"]["summary"]["total"], 2)
        self.assertEqual(payload["delta"]["summary"]["p1_total"], 1)
        changed_sample = next(item for item in payload["file_diffs"] if item["file"] == "sample.ctl")
        added_other = next(item for item in payload["file_diffs"] if item["file"] == "other.ctl")
        self.assertEqual(changed_sample["status"], "changed")
        self.assertEqual(changed_sample["delta_counts"]["p1_total"], 1)
        self.assertEqual(added_other["status"], "added")
        self.assertEqual(payload["invalid_run_count"], 1)

    def test_build_verification_latest_unavailable_payload_is_fail_soft(self):
        payload = build_verification_latest_unavailable_payload("verification summary not found")

        self.assertFalse(payload["available"])
        self.assertEqual(payload["summary"], {})
        self.assertEqual(payload["source_file"], "")
        self.assertIn("verification summary not found", payload["message"])


if __name__ == "__main__":
    unittest.main()
