"""
Phase 5 Auto-fix 코드 수정 제안 및 WinMerge / Diff 1-Click API 단위 테스트.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from app.ui.api import JSApi


class TestCodeDiffAPI:
    """JSApi.get_code_diff 및 open_in_winmerge 검증."""

    @pytest.fixture
    def api(self) -> JSApi:
        return JSApi()

    def test_get_code_diff_changes_detected(self, api: JSApi):
        orig_text = "void main() {\n    int a = 10;\n}\n"
        mod_text = "void main() {\n    int a = 20; // fixed\n}\n"

        res = api.get_code_diff(orig_text, mod_text)
        assert res["success"] is True
        assert res["has_changes"] is True
        assert "-    int a = 10;" in res["diff_text"]
        assert "+    int a = 20; // fixed" in res["diff_text"]

    def test_get_code_diff_no_changes(self, api: JSApi):
        text = "void main() {\n    return;\n}\n"
        res = api.get_code_diff(text, text)
        assert res["success"] is True
        assert res["has_changes"] is False
        assert res["diff_text"] == ""

    def test_open_in_winmerge_creates_temp_file(self, api: JSApi):
        with tempfile.NamedTemporaryFile(suffix=".ctl", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write("void test() { int x = 0; }")
            tf_path = Path(tf.name)

        try:
            mod_text = "void test() { int x = 100; // autofix }"
            res = api.open_in_winmerge(str(tf_path), mod_text)
            assert res["success"] is True
            assert res["mode"] in ("winmerge", "builtin")
            assert "modified_path" in res
            mod_file = Path(res["modified_path"])
            assert mod_file.exists()
            assert mod_file.read_text(encoding="utf-8") == mod_text
        finally:
            if tf_path.exists():
                tf_path.unlink()
