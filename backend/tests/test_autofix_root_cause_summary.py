import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.perf.autofix_root_cause_summary import build_root_cause_summary, load_summary, to_markdown


class AutofixRootCauseSummaryTests(unittest.TestCase):
    def test_build_root_cause_summary_aggregates_counts(self):
        rows = [
            {
                "path": "a.json",
                "run_count": 2,
                "apply_attempts": 2,
                "apply_success_count": 1,
                "anchor_mismatch_failure_count": 1,
                "instruction_apply_rate": 0.5,
                "instruction_validation_fail_rate": 0.1,
                "error_code_counts": {"ANCHOR_MISMATCH": 1},
                "validation_error_fragment_counts": {"drift_exceeded": 1},
                "instruction_fail_stage_distribution": {"apply": 1},
            },
            {
                "path": "b.json",
                "run_count": 2,
                "apply_attempts": 2,
                "apply_success_count": 2,
                "anchor_mismatch_failure_count": 0,
                "instruction_apply_rate": 1.0,
                "instruction_validation_fail_rate": 0.0,
                "error_code_counts": {"NONE": 2},
                "validation_error_fragment_counts": {"drift_exceeded": 0},
                "instruction_fail_stage_distribution": {"none": 2},
            },
        ]
        payload = build_root_cause_summary(rows)
        self.assertEqual(payload["input_file_count"], 2)
        self.assertEqual(payload["total_apply_attempts"], 4)
        self.assertEqual(payload["total_apply_success_count"], 3)
        self.assertEqual(payload["error_code_counts"]["ANCHOR_MISMATCH"], 1)
        self.assertEqual(payload["release_note_snippet"]["anchor_mismatch_failure_count"], 1)

    def test_load_summary_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.json"
            path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "run_count": 1,
                            "apply_attempts": 1,
                            "apply_success_count": 0,
                            "anchor_mismatch_failure_count": 1,
                            "instruction_apply_rate": 0.0,
                            "instruction_validation_fail_rate": 1.0,
                            "error_code_counts": {"ANCHOR_MISMATCH": 1},
                            "validation_error_fragment_counts": {"drift_exceeded": 1},
                            "instruction_fail_stage_distribution": {"validate": 1},
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            row = load_summary(path)
            payload = build_root_cause_summary([row])
            md = to_markdown(payload)
            self.assertIn("Autofix Root Cause Summary", md)
            self.assertIn("ANCHOR_MISMATCH", md)


if __name__ == "__main__":
    unittest.main()
