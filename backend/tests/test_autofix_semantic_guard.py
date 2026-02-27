import unittest

from backend.core.autofix_semantic_guard import evaluate_semantic_delta


class AutoFixSemanticGuardTests(unittest.TestCase):
    def test_blocks_string_literal_change(self):
        before = 'main() { dpSet("A.B.C", 1); }\n'
        after = 'main() { dpSet("A.B.D", 1); }\n'
        result = evaluate_semantic_delta(before, after)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("blocked"))
        self.assertIn("strings_changed", result.get("violations", []))

    def test_blocks_number_literal_change(self):
        before = 'main() { int x = 1; }\n'
        after = 'main() { int x = 2; }\n'
        result = evaluate_semantic_delta(before, after)
        self.assertTrue(result.get("blocked"))
        self.assertIn("numbers_changed", result.get("violations", []))

    def test_blocks_operator_change(self):
        before = 'main() { if (a == b) { return; } }\n'
        after = 'main() { if (a != b) { return; } }\n'
        result = evaluate_semantic_delta(before, after)
        self.assertTrue(result.get("blocked"))
        self.assertIn("operators_changed", result.get("violations", []))

    def test_blocks_keyword_change(self):
        before = 'main() { if (ok) { return; } }\n'
        after = 'main() { while (ok) { return; } }\n'
        result = evaluate_semantic_delta(before, after)
        self.assertTrue(result.get("blocked"))
        self.assertIn("keywords_changed", result.get("violations", []))

    def test_allows_whitespace_and_comment_only_changes(self):
        before = 'main() {\n  dpSet("A.B.C", 1);\n}\n'
        after = 'main()\t{ // note\n  dpSet("A.B.C", 1);\n}\n'
        result = evaluate_semantic_delta(before, after)
        self.assertTrue(result.get("ok"))
        self.assertFalse(result.get("blocked"))


if __name__ == "__main__":
    unittest.main()
