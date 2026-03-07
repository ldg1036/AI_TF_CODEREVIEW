import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.autofix_apply_engine import apply_with_engine


class AutoFixApplyEngineTests(unittest.TestCase):
    def test_structure_apply_success(self):
        base = "main()\n{\n  dpSet(\"A.B.C\", 1);\n}\n"
        hunks = [
            {
                "start_line": 3,
                "end_line": 3,
                "context_before": "{",
                "context_after": "  dpSet(\"A.B.C\", 1);",
                "replacement_text": "  dpSet(\"A.B.C\", 2);",
            }
        ]
        result = apply_with_engine(base, hunks, anchor_line=3, generator_type="rule", options={"max_line_drift": 20})
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("engine_mode"), "structure_apply")
        self.assertIn("dpSet(\"A.B.C\", 2);", result.get("patched_text", ""))

    def test_structure_failure_falls_back_to_text_patch(self):
        base = "main()\n  dpSet(\"A.B.C\", 1);\n"
        hunks = [
            {
                "start_line": 2,
                "end_line": 2,
                "context_before": "main()",
                "context_after": "  dpSet(\"A.B.C\", 1);",
                "replacement_text": "  dpSet(\"A.B.C\", 3);",
            }
        ]
        result = apply_with_engine(base, hunks, anchor_line=2, generator_type="llm")
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("engine_mode"), "text_fallback")
        self.assertIn("dpSet(\"A.B.C\", 3);", result.get("patched_text", ""))

    def test_both_structure_and_text_fail(self):
        base = "main()\n{\n}\n"
        hunks = [
            {
                "start_line": 99,
                "end_line": 99,
                "context_before": "",
                "context_after": "",
                "replacement_text": "bad();",
            }
        ]
        result = apply_with_engine(base, hunks, anchor_line=1, generator_type="rule")
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("engine_mode"), "failed")

    def test_ambiguous_anchor_fails_soft(self):
        base = "main() {\n  x = 1;\n}\nmain() {\n  x = 1;\n}\n"
        hunks = [
            {
                "start_line": 2,
                "end_line": 2,
                "context_before": "main() {",
                "context_after": "  x = 1;",
                "replacement_text": "  x = 2;",
            }
        ]
        result = apply_with_engine(base, hunks, anchor_line=2, generator_type="rule")
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("engine_mode"), "failed")
        self.assertIn("ambiguous", str(result.get("fallback_reason", "")))

    def test_multi_hunks_same_block_success(self):
        base = "main()\n{\n  int a = 1;\n  int b = 2;\n  return;\n}\n"
        hunks = [
            {
                "start_line": 3,
                "end_line": 3,
                "context_before": "{",
                "context_after": "  int a = 1;",
                "replacement_text": "  int a = 10;",
            },
            {
                "start_line": 4,
                "end_line": 4,
                "context_before": "  int a = 1;",
                "context_after": "  int b = 2;",
                "replacement_text": "  int b = 20;",
            },
        ]
        result = apply_with_engine(base, hunks, anchor_line=3, generator_type="rule", options={"max_hunks_per_apply": 3})
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("engine_mode"), "structure_apply")
        patched = result.get("patched_text", "")
        self.assertIn("int a = 10;", patched)
        self.assertIn("int b = 20;", patched)

    def test_multi_hunks_cross_block_fails(self):
        base = "main()\n{\n  int a = 1;\n}\nfunc()\n{\n  int b = 2;\n}\n"
        hunks = [
            {
                "start_line": 3,
                "end_line": 3,
                "context_before": "{",
                "context_after": "  int a = 1;",
                "replacement_text": "  int a = 10;",
            },
            {
                "start_line": 7,
                "end_line": 7,
                "context_before": "{",
                "context_after": "  int b = 2;",
                "replacement_text": "  int b = 20;",
            },
        ]
        result = apply_with_engine(base, hunks, anchor_line=3, generator_type="rule")
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("engine_mode"), "failed")
        self.assertIn(result.get("fallback_reason", ""), ("hunks_span_multiple_blocks", "ambiguous_candidates", "anchor_context_not_unique"))

    def test_multi_hunks_overlapping_fails(self):
        base = "main()\n{\n  int a = 1;\n  int b = 2;\n}\n"
        hunks = [
            {
                "start_line": 3,
                "end_line": 4,
                "context_before": "{",
                "context_after": "  int a = 1;",
                "replacement_text": "  int a = 10;\n  int b = 20;",
            },
            {
                "start_line": 4,
                "end_line": 4,
                "context_before": "  int a = 1;",
                "context_after": "  int b = 2;",
                "replacement_text": "  int b = 200;",
            },
        ]
        result = apply_with_engine(base, hunks, anchor_line=3, generator_type="rule")
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("fallback_reason"), "overlapping_hunks")

    def test_multi_hunks_too_many_fails(self):
        base = "main()\n{\n  a=1;\n  b=2;\n  c=3;\n  d=4;\n}\n"
        hunks = [
            {"start_line": 3, "end_line": 3, "context_before": "{", "context_after": "  a=1;", "replacement_text": "  a=10;"},
            {"start_line": 4, "end_line": 4, "context_before": "  a=1;", "context_after": "  b=2;", "replacement_text": "  b=20;"},
            {"start_line": 5, "end_line": 5, "context_before": "  b=2;", "context_after": "  c=3;", "replacement_text": "  c=30;"},
            {"start_line": 6, "end_line": 6, "context_before": "  c=3;", "context_after": "  d=4;", "replacement_text": "  d=40;"},
        ]
        result = apply_with_engine(base, hunks, anchor_line=3, generator_type="rule", options={"max_hunks_per_apply": 3})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("fallback_reason"), "too_many_hunks")


if __name__ == "__main__":
    unittest.main()
