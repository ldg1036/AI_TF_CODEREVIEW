import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.live_ai_review_mixin import LiveAIReviewMixin
from core.llm_reviewer import LLMReviewer


class LLMReviewerTests(unittest.TestCase):
    def test_normalize_review_output_removes_before_after_arrow_markers(self):
        reviewer = LLMReviewer(ai_config={"provider": "ollama"})
        raw = (
            "요약: grouped call로 바꾸세요.\n\n"
            "코드:\n```cpp\n"
            "setValue(\"obj_auto_sel1\", \"enabled\", false);\n"
            "setValue(\"obj_auto_sel2\", \"enabled\", false);\n"
            "=> setMultiValue(\"A.B.C1\", v1,\n"
            "                 \"A.B.C2\", v2);\n"
            "```"
        )
        normalized = reviewer._normalize_review_output(raw)
        self.assertIn("setMultiValue(\"A.B.C1\", v1,", normalized)
        self.assertNotIn("=>", normalized)
        self.assertNotIn("setValue(\"obj_auto_sel1\"", normalized)

    def test_prompt_requires_exact_identifiers_and_forbids_placeholders(self):
        reviewer = LLMReviewer(ai_config={"provider": "ollama"})
        prompt = reviewer._build_prompt(
            code="setValue(\"A.B.C1\", v1);",
            violations=[],
            focus_snippet="8: setValue(\"A.B.C1\", v1);",
            issue_context={
                "primary": {
                    "source": "P1",
                    "rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
                    "line": 8,
                    "object": "sample.ctl",
                    "severity": "Warning",
                    "message": "다중 Set 업데이트 감지",
                },
                "linked_findings": [],
            },
            todo_prompt_context={
                "todo_comment": "다중 Set 업데이트 감지",
                "snippet": "8: setValue(\"A.B.C1\", v1);",
            },
        )
        self.assertIn("Reuse the exact identifiers", prompt)
        self.assertIn("Do not invent placeholder names", prompt)


class LiveAIReviewMixinTests(unittest.TestCase):
    def test_review_has_example_artifacts_detects_placeholder_and_arrow(self):
        review = (
            "요약: grouped call\n\n"
            "코드:\n```cpp\n"
            "setValue(\"obj_auto_sel1\", \"enabled\", false);\n"
            "=> setMultiValue(\"obj_auto_sel1\", \"enabled\", false);\n"
            "```"
        )
        self.assertTrue(LiveAIReviewMixin._review_has_example_artifacts(review))


if __name__ == "__main__":
    unittest.main()
