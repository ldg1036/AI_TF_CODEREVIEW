import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tools import analyze_template_coverage as coverage_tool


class AnalyzeTemplateCoverageToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = self.tmp_dir.name

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_fail_soft_returns_skipped_payload_when_openpyxl_missing(self):
        with mock.patch.object(coverage_tool, "_resolve_load_workbook", side_effect=RuntimeError("openpyxl is required")):
            output_path, payload = coverage_tool.analyze_template_coverage(
                self.project_root,
                ensure_openpyxl=False,
                fail_soft=True,
            )

        self.assertTrue(os.path.isfile(output_path))
        self.assertEqual(payload.get("status"), "skipped_optional_missing")
        self.assertEqual(payload.get("missing_dependency"), "openpyxl")
        self.assertIn("openpyxl", str(payload.get("reason", "")))

    def test_without_fail_soft_raises_runtime_error(self):
        with mock.patch.object(coverage_tool, "_resolve_load_workbook", side_effect=RuntimeError("openpyxl is required")):
            with self.assertRaises(RuntimeError):
                coverage_tool.analyze_template_coverage(
                    self.project_root,
                    ensure_openpyxl=False,
                    fail_soft=False,
                )


if __name__ == "__main__":
    unittest.main()
