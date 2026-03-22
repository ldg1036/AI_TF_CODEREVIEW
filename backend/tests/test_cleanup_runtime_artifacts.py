import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_cleanup_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "tools" / "cleanup_runtime_artifacts.py"
    spec = importlib.util.spec_from_file_location("cleanup_runtime_artifacts", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CleanupRuntimeArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_cleanup_module()
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _touch(self, relative_path: str, *, content: str = "x") -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_build_cleanup_plan_keeps_latest_integration_artifact_per_prefix(self):
        older = self._touch("tools/integration_results/ui_real_smoke_20260321_100000.json")
        newer = self._touch("tools/integration_results/ui_real_smoke_20260321_110000.json")
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))

        plan = self.module.build_cleanup_plan(str(self.root))
        candidate_paths = {item["path"] for item in plan["candidates"]}
        kept_paths = set(plan["keep"])

        self.assertIn(str(older), candidate_paths)
        self.assertIn(str(newer), kept_paths)
        self.assertNotIn(str(newer), candidate_paths)

    def test_apply_cleanup_plan_moves_candidate_into_bk(self):
        older = self._touch("CodeReview_Report/release_gate_20260321_100000.json", content=json.dumps({"ok": True}))
        newer = self._touch("CodeReview_Report/release_gate_20260321_110000.json", content=json.dumps({"ok": True}))
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))

        plan = self.module.build_cleanup_plan(str(self.root))
        result = self.module.apply_cleanup_plan(plan, root=str(self.root))

        self.assertFalse(older.exists())
        self.assertTrue(newer.exists())
        self.assertGreaterEqual(int(result["moved_count"]), 1)
        moved_destinations = [item["destination"] for item in result["results"] if item.get("status") == "moved"]
        self.assertTrue(any("bk" in destination for destination in moved_destinations))

    def test_apply_cleanup_plan_marks_permission_error_as_skipped_locked(self):
        older = self._touch("tools/integration_results/full_audit_20260321_100000.json")
        newer = self._touch("tools/integration_results/full_audit_20260321_110000.json")
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))
        plan = self.module.build_cleanup_plan(str(self.root))

        with mock.patch.object(self.module.shutil, "move", side_effect=PermissionError("locked")):
            result = self.module.apply_cleanup_plan(plan, root=str(self.root))

        self.assertTrue(older.exists())
        self.assertGreaterEqual(int(result["skipped_locked_count"]), 1)


if __name__ == "__main__":
    unittest.main()
