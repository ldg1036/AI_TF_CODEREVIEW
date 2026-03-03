import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.autofix_instruction import (
    instruction_to_hunks,
    normalize_instruction,
    validate_instruction,
)


class AutoFixInstructionTests(unittest.TestCase):
    def test_replace_instruction_to_hunk(self):
        raw = {
            "target": {"file": "sample.ctl", "object": "sample.ctl", "event": "Global"},
            "operation": "replace",
            "locator": {
                "kind": "anchor_context",
                "start_line": 10,
                "context_before": "prev();",
                "context_after": "next();",
            },
            "payload": {"code": "doWork();"},
            "safety": {"requires_hash_match": True},
        }
        instr = normalize_instruction(raw)
        ok, errors = validate_instruction(instr)
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        hunks = instruction_to_hunks(instr)
        self.assertEqual(len(hunks), 1)
        self.assertEqual(hunks[0]["start_line"], 10)
        self.assertEqual(hunks[0]["replacement_text"], "doWork();")

    def test_insert_instruction_to_hunk(self):
        raw = {
            "target": {"file": "sample.ctl", "object": "sample.ctl", "event": "Global"},
            "operation": "insert",
            "locator": {
                "kind": "anchor_context",
                "start_line": 3,
                "context_before": "{",
                "context_after": "int x = 0;",
            },
            "payload": {"code": "// note"},
            "safety": {"requires_hash_match": True},
        }
        instr = normalize_instruction(raw)
        ok, _ = validate_instruction(instr)
        self.assertTrue(ok)
        hunks = instruction_to_hunks(instr)
        self.assertEqual(hunks[0]["start_line"], 3)
        self.assertEqual(hunks[0]["end_line"], 3)

    def test_invalid_operation_delete_fails_validation(self):
        instr = normalize_instruction(
            {
                "target": {"file": "sample.ctl"},
                "operation": "delete",
                "locator": {"kind": "anchor_context", "start_line": 1},
                "payload": {"code": "x"},
            }
        )
        ok, errors = validate_instruction(instr)
        self.assertFalse(ok)
        self.assertTrue(any("operation" in e for e in errors))

    def test_missing_payload_code_fails_validation(self):
        instr = normalize_instruction(
            {
                "target": {"file": "sample.ctl"},
                "operation": "replace",
                "locator": {"kind": "anchor_context", "start_line": 1},
                "payload": {"code": "   "},
            }
        )
        ok, errors = validate_instruction(instr)
        self.assertFalse(ok)
        self.assertTrue(any("payload.code" in e for e in errors))

    def test_target_file_can_be_checked_by_caller(self):
        instr = normalize_instruction(
            {
                "target": {"file": "other.ctl"},
                "operation": "insert",
                "locator": {"kind": "anchor_context", "start_line": 1},
                "payload": {"code": "x"},
            }
        )
        ok, errors = validate_instruction(instr)
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertNotEqual(instr.get("target", {}).get("file"), "sample.ctl")


if __name__ == "__main__":
    unittest.main()
