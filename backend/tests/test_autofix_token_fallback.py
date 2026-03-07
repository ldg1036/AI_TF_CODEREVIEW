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

    def test_locate_anchor_line_by_tokens_tie_break_nearest_when_enabled(self):
        lines = [
            'main() { dpSet("A.B.C", 1); }',
            "noop();",
            'main() { dpSet("A.B.C", 1); }',
        ]
        strict = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=False,
        )
        self.assertFalse(strict.get("ok"))
        self.assertEqual(strict.get("reason"), "ambiguous_candidates")

        relaxed = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=True,
        )
        self.assertTrue(relaxed.get("ok"))
        self.assertEqual(relaxed.get("line"), 1)
        self.assertEqual(relaxed.get("reason"), "tie_break_nearest")

    def test_locate_anchor_line_by_tokens_tie_break_gap_relaxed_when_enabled(self):
        lines = [
            'main() { dpSet("A.B.C", 1); }',
            "noop();",
            "noop();",
            "noop();",
            "noop();",
            "noop();",
            "noop();",
            'main() { dpSet("A.B.C", 2); }',
        ]
        strict = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=False,
        )
        self.assertFalse(strict.get("ok"))
        self.assertEqual(strict.get("reason"), "ambiguous_candidates")

        relaxed = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=True,
        )
        self.assertTrue(relaxed.get("ok"))
        self.assertEqual(relaxed.get("line"), 1)
        self.assertEqual(relaxed.get("reason"), "tie_break_gap_relaxed")

    def test_locate_anchor_line_by_tokens_hint_bias_selects_near_hint(self):
        lines = [
            'main() { dpSet("A.B.C", 1); }',
            "noop();",
            "noop();",
            'main() { dpSet("A.B.C", 1); }',
        ]
        no_bias = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=False,
            hint_bias=0.0,
        )
        self.assertFalse(no_bias.get("ok"))
        self.assertEqual(no_bias.get("reason"), "ambiguous_candidates")

        with_bias = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=False,
            hint_bias=0.03,
        )
        self.assertTrue(with_bias.get("ok"))
        self.assertEqual(with_bias.get("line"), 1)
        self.assertEqual(with_bias.get("reason"), "hint_bias_selected")

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

    def test_locate_anchor_line_by_tokens_force_pick_nearest_on_ambiguous(self):
        lines = [
            'main() { dpSet("A.B.C", 1); }',
            "noop();",
            "noop();",
            'main() { dpSet("A.B.C", 2); }',
        ]
        forced = locate_anchor_line_by_tokens(
            lines,
            before_expected="",
            after_expected='main(){dpSet("A.B.C",1);}',
            hint_line=1,
            min_confidence=0.8,
            min_gap=0.15,
            max_line_drift=20,
            prefer_nearest_on_tie=False,
            hint_bias=0.0,
            force_pick_nearest_on_ambiguous=True,
        )
        self.assertTrue(forced.get("ok"))
        self.assertEqual(forced.get("line"), 1)
        self.assertEqual(forced.get("reason"), "forced_nearest_benchmark")


if __name__ == "__main__":
    unittest.main()
