import unittest

from backend.core.autofix_tokenizer import locate_anchor_line_by_tokens, tokenize_ctl


class AutoFixTokenFallbackTests(unittest.TestCase):
    def test_tokenize_ctl_includes_offsets(self):
        tokens = tokenize_ctl('main() { dpSet("A.B.C", 1); }')
        self.assertGreater(len(tokens), 0)
        self.assertIn("start", tokens[0])
        self.assertIn("end", tokens[0])
        self.assertIn("line", tokens[0])
        self.assertIn("column", tokens[0])

    def test_locate_anchor_line_by_tokens_unique(self):
        lines = [
            'main() { dpSet("A.B.C", 1); }',
            'main() { return; }',
        ]
        result = locate_anchor_line_by_tokens(
            lines,
            before_expected='',
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            max_line_drift=20,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("line"), 1)

    def test_locate_anchor_line_by_tokens_ambiguous(self):
        lines = [
            'main() { dpSet("A.B.C", 1); }',
            'main() { dpSet("A.B.C", 1); }',
        ]
        result = locate_anchor_line_by_tokens(
            lines,
            before_expected='',
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            max_line_drift=20,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "ambiguous_candidates")

    def test_locate_anchor_line_by_tokens_whitespace_normalized(self):
        lines = [
            "main()  {   dpSet(\"A.B.C\",   1); }",
        ]
        result = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("line"), 1)


if __name__ == "__main__":
    unittest.main()
