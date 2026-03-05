import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tools.run_verification_profile import classify_status, run_profile


class VerificationProfileToolTests(unittest.TestCase):
    def test_classify_status_pass(self):
        self.assertEqual(classify_status(0, "ok"), "passed")

    def test_classify_status_optional_missing(self):
        output = "RuntimeError: openpyxl is required. Install with: pip install openpyxl"
        self.assertEqual(classify_status(1, output), "skipped_optional_missing")

    def test_classify_status_failed(self):
        self.assertEqual(classify_status(1, "unexpected error"), "failed")

    @patch("tools.run_verification_profile.subprocess.run")
    def test_run_profile_returns_summary_shape(self, mock_run):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        mock_run.return_value = Result()
        payload = run_profile("core", include_report=False)
        self.assertIn("summary", payload)
        self.assertIn("checks", payload)
        self.assertEqual(payload.get("profile"), "core")
        self.assertGreaterEqual(payload["summary"].get("total", 0), 1)
        self.assertEqual(payload["summary"].get("failed", 0), 0)


if __name__ == "__main__":
    unittest.main()
