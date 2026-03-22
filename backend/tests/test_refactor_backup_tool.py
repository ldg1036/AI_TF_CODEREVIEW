import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "refactor_backup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("refactor_backup_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RefactorBackupToolTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_module()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.project_root = Path(self.tempdir.name)
        (self.project_root / "backend").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "tests").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "main.py").write_text(
            "def public_api():\n    return 1\n\nclass Demo:\n    def run(self):\n        return 1\n",
            encoding="utf-8",
        )
        (self.project_root / "backend" / "server.py").write_text("def server_api():\n    return 2\n", encoding="utf-8")
        (self.project_root / "backend" / "tests" / "test_api_and_reports.py").write_text(
            "def smoke_test():\n    return True\n",
            encoding="utf-8",
        )
        (self.project_root / "frontend").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "renderer.js").write_text(
            "\n".join(
                [
                    "export function createRendererController() {",
                    "    const root = document.getElementById('root');",
                    "    root.addEventListener('click', () => {});",
                    "    return {",
                    "        render,",
                    "        reset,",
                    "    };",
                    "}",
                    "",
                    "function render() {",
                    "    document.querySelector('.toolbar');",
                    "}",
                    "",
                    "function reset() {",
                    "    window.addEventListener('resize', () => {});",
                    "}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.backup_root = self.project_root / "workspace" / "runtime" / "refactor_backups"

    def test_create_backup_writes_manifest_and_snapshots(self):
        result = self.module.create_backup(
            "phase1",
            ["backend/main.py", "backend/server.py"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(result["ok"])
        manifest_path = Path(result["manifest_path"])
        self.assertTrue(manifest_path.is_file())
        snapshot_main = Path(result["backup_dir"]) / "source" / "backend" / "main.py"
        snapshot_server = Path(result["backup_dir"]) / "source" / "backend" / "server.py"
        self.assertTrue(snapshot_main.is_file())
        self.assertTrue(snapshot_server.is_file())

    def test_review_backup_reports_diff_and_entrypoint_changes(self):
        created = self.module.create_backup(
            "phase1",
            ["backend/main.py"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])

        (self.project_root / "backend" / "main.py").write_text(
            "def new_api():\n    return 2\n\nclass Demo:\n    def helper(self):\n        return 2\n",
            encoding="utf-8",
        )

        reviewed = self.module.review_backup(created["manifest_path"], project_root=self.project_root)
        self.assertTrue(reviewed["ok"])
        self.assertTrue(Path(reviewed["compare_json_path"]).is_file())
        self.assertTrue(Path(reviewed["compare_markdown_path"]).is_file())
        file_result = reviewed["files"][0]
        self.assertTrue(file_result["changed"])
        self.assertIn("public_api", file_result["functions_removed"])
        self.assertIn("new_api", file_result["functions_added"])
        self.assertIn("Demo.run", file_result["missing_public_entrypoints"])
        self.assertIn("Demo", file_result["methods_added"])
        self.assertIn("helper", file_result["methods_added"]["Demo"])

    def test_review_backup_fail_soft_for_missing_manifest_and_current_file(self):
        missing_manifest = self.module.review_backup(
            str(self.project_root / "workspace" / "runtime" / "refactor_backups" / "missing"),
            project_root=self.project_root,
        )
        self.assertFalse(missing_manifest["ok"])
        self.assertEqual(missing_manifest["error_code"], "MANIFEST_NOT_FOUND")

        created = self.module.create_backup(
            "phase1",
            ["backend/server.py"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])
        (self.project_root / "backend" / "server.py").unlink()

        reviewed = self.module.review_backup(created["manifest_path"], project_root=self.project_root)
        self.assertFalse(reviewed["ok"])
        self.assertEqual(reviewed["error_code"], "CURRENT_FILE_MISSING")
        self.assertIn("backend/server.py", reviewed["missing_current_files"])

    def test_create_backup_captures_javascript_surface(self):
        created = self.module.create_backup(
            "frontend-phase",
            ["frontend/renderer.js"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])
        file_entry = created["files"][0]
        self.assertEqual(file_entry["language"], "javascript")
        surface = file_entry["surface"]
        self.assertIn("createRendererController", surface["exports"])
        self.assertIn("render", surface["functions"])
        self.assertIn("render", surface["controller_methods"])
        self.assertIn("#root", surface["dom_selectors"])
        self.assertIn(".toolbar", surface["dom_selectors"])
        self.assertIn("root:click", surface["event_bindings"])

    def test_review_backup_reports_missing_javascript_exports_and_bindings(self):
        created = self.module.create_backup(
            "frontend-phase",
            ["frontend/renderer.js"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])

        (self.project_root / "frontend" / "renderer.js").write_text(
            "\n".join(
                [
                    "export function createRendererController() {",
                    "    const root = document.getElementById('root');",
                    "    return {",
                    "        render,",
                    "    };",
                    "}",
                    "",
                    "function render() {",
                    "    document.querySelector('.workspace');",
                    "}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        reviewed = self.module.review_backup(created["manifest_path"], project_root=self.project_root)
        self.assertTrue(reviewed["ok"])
        file_result = reviewed["files"][0]
        self.assertIn("reset", file_result["missing_controller_methods"])
        self.assertIn(".toolbar", file_result["missing_dom_bindings"])
        self.assertIn("window:resize", file_result["missing_event_bindings"])

    def test_compare_alias_matches_review_behavior(self):
        created = self.module.create_backup(
            "phase1",
            ["backend/server.py"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])
        exit_code = self.module.main(["compare", created["backup_dir"]])
        self.assertEqual(exit_code, 0)

    def test_review_backup_aggregate_surface_survives_javascript_refactor_move(self):
        created = self.module.create_backup(
            "frontend-phase",
            ["frontend/renderer.js"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])

        (self.project_root / "frontend" / "renderer.js").write_text(
            "export function createRendererController() {\n    return { render };\n}\n\nfunction render() {}\n",
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "bootstrap.js").write_text(
            "const root = document.getElementById('root');\nroot.addEventListener('click', () => {});\nwindow.addEventListener('resize', () => {});\ndocument.querySelector('.toolbar');\n",
            encoding="utf-8",
        )

        reviewed = self.module.review_backup(created["manifest_path"], project_root=self.project_root)
        self.assertTrue(reviewed["ok"])
        self.assertEqual(reviewed["aggregate_missing_event_bindings"], [])
        self.assertEqual(reviewed["aggregate_missing_dom_bindings"], [])
        self.assertEqual(reviewed["missing_event_bindings"], [])
        self.assertEqual(reviewed["missing_dom_bindings"], [])

    def test_review_backup_normalizes_dom_binding_targets_for_aggregate_compare(self):
        (self.project_root / "frontend" / "renderer.js").write_text(
            "\n".join(
                [
                    "export function createRendererController() {",
                    "    const dom = { resultTableWrap: document.getElementById('root') };",
                    "    dom.resultTableWrap.addEventListener('scroll', () => {});",
                    "    return {",
                    "        render,",
                    "    };",
                    "}",
                    "",
                    "function render() {}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        created = self.module.create_backup(
            "frontend-phase",
            ["frontend/renderer.js"],
            project_root=self.project_root,
            backup_root=self.backup_root,
        )
        self.assertTrue(created["ok"])

        (self.project_root / "frontend" / "renderer.js").write_text(
            "\n".join(
                [
                    "export function createRendererController() {",
                    "    return {",
                    "        render,",
                    "    };",
                    "}",
                    "",
                    "function render() {}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "workspace-module.js").write_text(
            "\n".join(
                [
                    "const dom = { resultTableWrap: document.getElementById('root') };",
                    "dom.resultTableWrap.addEventListener('scroll', () => {});",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        reviewed = self.module.review_backup(created["manifest_path"], project_root=self.project_root)
        self.assertTrue(reviewed["ok"])
        self.assertEqual(reviewed["aggregate_missing_event_bindings"], [])
        self.assertEqual(reviewed["missing_event_bindings"], [])


if __name__ == "__main__":
    unittest.main()
