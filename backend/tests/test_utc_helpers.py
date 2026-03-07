import datetime
import importlib.util
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.ctrl_wrapper import CtrlppWrapper
from main import CodeInspectorApp
from tools import winccoa_context_mcp_server, winccoa_context_server


def _load_ctrlpp_smoke_module():
    module_path = os.path.join(PROJECT_ROOT, "tools", "ctrlpp", "run_ctrlpp_integration_smoke.py")
    spec = importlib.util.spec_from_file_location("ctrlpp_integration_smoke_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class UtcHelperTests(unittest.TestCase):
    @staticmethod
    def _assert_utc_z(value: str) -> None:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == datetime.timedelta(0)
        assert value.endswith("Z")

    def test_code_inspector_iso_now_returns_utc_z(self):
        self._assert_utc_z(CodeInspectorApp._iso_now())

    def test_context_servers_return_utc_z(self):
        self._assert_utc_z(winccoa_context_server._utc_now())
        self._assert_utc_z(winccoa_context_mcp_server._utc_now())

    def test_ctrlpp_helpers_return_utc_values(self):
        self.assertGreater(CtrlppWrapper._perf_now(), 0.0)
        ctrlpp_smoke = _load_ctrlpp_smoke_module()
        self._assert_utc_z(ctrlpp_smoke.utc_now())


if __name__ == "__main__":
    unittest.main()
