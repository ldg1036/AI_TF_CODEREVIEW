"""Ctrlpp cases for system verification."""

try:
    from ._system_verification_base import *  # noqa: F403
except ImportError:
    from _system_verification_base import *  # noqa: F403


class SystemVerificationCtrlppMixin:
    def test_ctrlpp_disabled_by_default(self):
        wrapper = CtrlppWrapper()
        self.assertFalse(wrapper.default_enabled)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            result = wrapper.run_check(target)
            self.assertEqual(result, [])

    def test_ctrlpp_enabled_ctl_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ctl_path = os.path.join(temp_dir, "sample.ctl")
            pnl_path = os.path.join(temp_dir, "sample.pnl")
            with open(ctl_path, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            with open(pnl_path, "w", encoding="utf-8") as f:
                f.write(
                    '6 13\n"btn"\n""\n1 10 10 E E E 1 E 1 E N "_Transparent" E N "_Transparent" E E\n'
                    '"Clicked" 1\n"main()\\n{\\n  int b = 1;\\n}" 0\n'
                )
    
            app = CodeInspectorApp()
            app.data_dir = temp_dir
    
            calls = []
    
            def fake_run_check(file_path, code_content=None, enabled=None, binary_path=None):
                calls.append(os.path.basename(file_path))
                return []
    
            app.ctrl_tool.run_check = fake_run_check
            app.run_directory_analysis(mode="Static", enable_ctrlppcheck=True)
    
            self.assertIn("sample.ctl", calls)
            self.assertFalse(any(name.endswith("_pnl.txt") for name in calls))

    def test_ctrlpp_missing_binary_fail_soft(self):
        wrapper = CtrlppWrapper()
        wrapper.config_binary_path = ""
        wrapper.auto_install_on_missing = False
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            result = wrapper.run_check(
                target,
                enabled=True,
                binary_path=os.path.join(temp_dir, "does_not_exist", "ctrlppcheck.exe"),
            )
            self.assertGreaterEqual(len(result), 1)
            self.assertEqual(result[0].get("source"), "CtrlppCheck")
            self.assertIn("not found", result[0].get("message", ""))

    def test_ctrlpp_auto_install_attempt_on_missing_binary(self):
        wrapper = CtrlppWrapper()
        wrapper.config_binary_path = ""
        wrapper.auto_install_on_missing = True
        calls = {"count": 0}
    
        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"
    
        wrapper.ensure_installed = fake_ensure
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            result = wrapper.run_check(
                target,
                enabled=True,
                binary_path=os.path.join(temp_dir, "does_not_exist", "ctrlppcheck.exe"),
            )
        self.assertEqual(calls["count"], 1)
        self.assertGreaterEqual(len(result), 1)
        self.assertIn("install failed", result[0].get("message", "").lower())

    def test_ctrlpp_auto_install_skipped_when_disabled(self):
        wrapper = CtrlppWrapper()
        wrapper.config_binary_path = ""
        wrapper.auto_install_on_missing = True
        calls = {"count": 0}
    
        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"
    
        wrapper.ensure_installed = fake_ensure
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            result = wrapper.run_check(target, enabled=False)
        self.assertEqual(result, [])
        self.assertEqual(calls["count"], 0)

    def test_ctrlpp_auto_install_persists_binary_path_to_state_file_without_mutating_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = os.path.join(temp_dir, "tools")
            config_path = os.path.join(temp_dir, "config.json")
            config_payload = {
                "ctrlppcheck": {
                    "enabled_default": False,
                    "binary_path": "",
                    "timeout_sec": 30,
                    "enable_levels": "style,information",
                    "version": "v1.0.2",
                    "auto_install_on_missing": True,
                    "install_dir": install_dir,
                    "github_repo": "siemens/CtrlppCheck",
                    "asset_pattern": "WinCCOA_QualityChecks_*.zip",
                }
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_payload, f, ensure_ascii=False, indent=2)
    
            zip_fixture = os.path.join(temp_dir, "asset.zip")
            with zipfile.ZipFile(zip_fixture, "w") as zf:
                zf.writestr("WinCCOA_QualityChecks/bin/ctrlppcheck.exe", "fake-binary")
    
            wrapper = CtrlppWrapper(config_path=config_path)
            wrapper._fetch_release_payload = lambda: {
                "assets": [
                    {
                        "name": "WinCCOA_QualityChecks_v1.0.2.zip",
                        "browser_download_url": "mock://asset",
                        "digest": "",
                    }
                ]
            }
            wrapper._download_asset = lambda _url, dst: shutil.copy2(zip_fixture, dst)
    
            binary, error = wrapper.ensure_installed()
            self.assertEqual(error, "")
            self.assertTrue(binary.lower().endswith("ctrlppcheck.exe"))
            self.assertTrue(os.path.exists(binary))
    
            with open(config_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["ctrlppcheck"]["binary_path"], "")
    
            self.assertTrue(os.path.exists(wrapper.install_state_path))
            with open(wrapper.install_state_path, "r", encoding="utf-8") as f:
                state_saved = json.load(f)
            self.assertEqual(os.path.normpath(state_saved["binary_path"]), os.path.normpath(binary))
            self.assertEqual(os.path.normpath(wrapper.state_binary_path), os.path.normpath(binary))

    def test_ctrlpp_auto_install_fail_soft_on_download_error(self):
        wrapper = CtrlppWrapper()
        wrapper.config_binary_path = ""
        wrapper.auto_install_on_missing = True
    
        def failing_ensure():
            raise RuntimeError("CtrlppCheck download failed: mocked offline")
    
        wrapper.ensure_installed = failing_ensure
        wrapper._find_binary = lambda *a, **kw: ""
        wrapper.state_binary_path = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            result = wrapper.run_check(target, enabled=True)
    
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual(result[0].get("source"), "CtrlppCheck")
        self.assertIn("download failed", result[0].get("message", "").lower())

    def test_ctrlpp_prepare_for_analysis_skip_without_ctl(self):
        wrapper = CtrlppWrapper()
        wrapper.auto_install_on_missing = True
        calls = {"count": 0}
    
        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"
    
        wrapper.ensure_installed = fake_ensure
        result = wrapper.prepare_for_analysis(True, ["sample_pnl.txt"])
        self.assertFalse(bool(result.get("attempted", False)))
        self.assertFalse(bool(result.get("ready", False)))
        self.assertEqual(calls["count"], 0)

    def test_ctrlpp_prepare_for_analysis_attempts_install_once(self):
        wrapper = CtrlppWrapper()
        wrapper.config_binary_path = ""
        wrapper.state_binary_path = ""
        wrapper.tool_path = ""
        wrapper.auto_install_on_missing = True
        calls = {"count": 0}
    
        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"
    
        wrapper.ensure_installed = fake_ensure
        result = wrapper.prepare_for_analysis(True, ["sample.ctl"])
        self.assertTrue(bool(result.get("attempted", False)))
        self.assertFalse(bool(result.get("ready", False)))
        self.assertIn("install failed", str(result.get("message", "")).lower())
        self.assertEqual(calls["count"], 1)

    def test_ctrlpp_prepare_for_analysis_blocks_immediate_reinstall_retry(self):
        wrapper = CtrlppWrapper()
        wrapper.config_binary_path = ""
        wrapper.state_binary_path = ""
        wrapper.tool_path = ""
        wrapper.auto_install_on_missing = True
        calls = {"count": 0}
    
        def fake_ensure():
            calls["count"] += 1
            return "", "CtrlppCheck install failed: mocked"
    
        wrapper.ensure_installed = fake_ensure
        preflight = wrapper.prepare_for_analysis(True, ["sample.ctl"])
        self.assertTrue(bool(preflight.get("attempted", False)))
        self.assertFalse(bool(preflight.get("ready", False)))
    
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sample.ctl")
            with open(target, "w", encoding="utf-8") as f:
                f.write("main() { int a = 0; }")
            result = wrapper.run_check(target, enabled=True)
        self.assertEqual(calls["count"], 1)
        self.assertGreaterEqual(len(result), 1)
        self.assertIn("install failed", result[0].get("message", "").lower())

    def test_ctrlpp_checksum_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = os.path.join(temp_dir, "tools")
            config_path = os.path.join(temp_dir, "config.json")
            config_payload = {
                "ctrlppcheck": {
                    "enabled_default": False,
                    "binary_path": "",
                    "timeout_sec": 30,
                    "enable_levels": "style,information",
                    "version": "v1.0.2",
                    "auto_install_on_missing": True,
                    "install_dir": install_dir,
                    "github_repo": "siemens/CtrlppCheck",
                    "asset_pattern": "WinCCOA_QualityChecks_*.zip",
                }
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_payload, f, ensure_ascii=False, indent=2)
    
            zip_fixture = os.path.join(temp_dir, "asset.zip")
            with zipfile.ZipFile(zip_fixture, "w") as zf:
                zf.writestr("WinCCOA_QualityChecks/bin/ctrlppcheck.exe", "fake-binary")
    
            wrapper = CtrlppWrapper(config_path=config_path)
            wrapper._fetch_release_payload = lambda: {
                "assets": [
                    {
                        "name": "WinCCOA_QualityChecks_v1.0.2.zip",
                        "browser_download_url": "mock://asset",
                        "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    }
                ]
            }
            wrapper._download_asset = lambda _url, dst: shutil.copy2(zip_fixture, dst)
    
            binary, error = wrapper.ensure_installed()
            self.assertEqual(binary, "")
            self.assertIn("checksum mismatch", error.lower())

    def test_ctrlpp_xml_parse_to_p2_schema(self):
        wrapper = CtrlppWrapper()
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <results version="2">
      <errors>
    <error id="unusedVariable" severity="warning" msg="unused variable" verbose="unused variable verbose">
      <location file="sample.ctl" line="12"/>
    </error>
      </errors>
    </results>"""
        parsed = wrapper._parse_xml_report(sample_xml, default_file="sample.ctl")
        self.assertEqual(len(parsed), 1)
        finding = parsed[0]
        for key in ("type", "rule_id", "line", "message", "file", "source"):
            self.assertIn(key, finding)
        self.assertEqual(finding["rule_id"], "unusedVariable")
        self.assertEqual(finding["line"], 12)
        self.assertEqual(finding["source"], "CtrlppCheck")

    def test_ctrlpp_build_command_includes_project_name_option(self):
        wrapper = CtrlppWrapper()
        wrapper.winccoa_project_name = "TEST_PROJECT"
        cmd = wrapper._build_command("ctrlppcheck.exe", "sample.ctl")
        self.assertIn("--winccoa-projectName=TEST_PROJECT", cmd)

    def test_ctrlpp_no_xml_output_returns_warning(self):
        wrapper = CtrlppWrapper()
        wrapper.auto_install_on_missing = False
    
        original_find_binary = wrapper._find_binary
        original_run = subprocess.run
        wrapper._find_binary = lambda binary_path=None: "ctrlppcheck.exe"
    
        def fake_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(
                args=["ctrlppcheck.exe", "sample.ctl"],
                returncode=0,
                stdout="Mandatory option missing: --winccoa-projectName",
                stderr="",
            )
    
        subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                target = os.path.join(temp_dir, "sample.ctl")
                with open(target, "w", encoding="utf-8") as f:
                    f.write("main() { int a = 0; }")
                result = wrapper.run_check(target, enabled=True)
        finally:
            wrapper._find_binary = original_find_binary
            subprocess.run = original_run
    
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual(result[0].get("source"), "CtrlppCheck")
        self.assertIn("no XML output", result[0].get("message", ""))
