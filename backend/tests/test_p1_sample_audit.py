import unittest

from backend.tools.audit_p1_sample_precision_recall import compare_core_rule_ids, flatten_p1_rule_ids, flatten_p2_rule_ids


class P1SampleAuditTests(unittest.TestCase):
    def test_flatten_p1_rule_ids_collects_nested_ids(self):
        payload = {
            "violations": {
                "P1": [
                    {
                        "object": "sample.ctl",
                        "violations": [
                            {"rule_id": "RULE-01"},
                            {"rule_id": "RULE-02"},
                            {"rule_id": "RULE-01"},
                        ],
                    }
                ]
            }
        }

        self.assertEqual(flatten_p1_rule_ids(payload), ["RULE-01", "RULE-02"])

    def test_flatten_p2_rule_ids_collects_top_level_ids(self):
        payload = {
            "violations": {
                "P2": [
                    {"rule_id": "P2-01"},
                    {"rule_id": "P2-02"},
                    {"rule_id": "P2-01"},
                ]
            }
        }

        self.assertEqual(flatten_p2_rule_ids(payload), ["P2-01", "P2-02"])

    def test_compare_core_rule_ids_reports_matches_missing_and_unexpected(self):
        result = compare_core_rule_ids(
            expected_rule_ids=["RULE-01", "RULE-02", "RULE-03"],
            detected_rule_ids=["RULE-02", "RULE-03", "RULE-99"],
        )

        self.assertEqual(result["matched_core_rule_ids"], ["RULE-02", "RULE-03"])
        self.assertEqual(result["missing_core_rule_ids"], ["RULE-01"])
        self.assertEqual(result["unexpected_detected_rule_ids"], ["RULE-99"])
        self.assertEqual(result["core_recall_pct"], round((2 / 3) * 100.0, 2))


if __name__ == "__main__":
    unittest.main()
