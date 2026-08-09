"""
UI JSApi 브리지 유닛 테스트 (TRD §5.9 & Phase 8 기준).

검증 항목:
1. JSApi.run_review 파이프라인 연동 성공 및 report/html_content 반환
2. 존재하지 않는 경로 실행 시 error 핸들링 검증
"""

from __future__ import annotations

from pathlib import Path

from app.ui.api import JSApi


class TestJSApi:
    """JSApi 유닛 테스트."""

    def test_js_api_run_review_success(self, tmp_path: Path):
        """JSApi.run_review 파이프라인 연동 테스트."""
        ctl_file = tmp_path / "script.ctl"
        ctl_file.write_text("main() { dpConnect('cb', 'dpe'); }", encoding="utf-8")

        out_dir = tmp_path / "out"

        api = JSApi()
        res = api.run_review(str(ctl_file), {"output_dir": str(out_dir), "no_ai": True})

        assert res["success"] is True
        assert "report" in res
        assert "html_content" in res
        assert "<html" in res["html_content"]
        assert res["report"]["metrics"]["file_count"] == 1

    def test_js_api_run_review_invalid_path(self):
        """존재하지 않는 경로 지정 시 실패 반환 검증."""
        api = JSApi()
        res = api.run_review("non_existent_path_99999")

        assert res["success"] is False
        assert "error" in res
        assert "존재하지 않는 경로" in res["error"]

    def test_js_api_export_report_no_run(self):
        """리뷰 구동 없이 export 호출 시 에러 처리 검증."""
        api = JSApi()
        res = api.export_report("json")
        assert res["success"] is False
        assert "내보낼 수 있는 리뷰 결과가 없습니다" in res["error"]

    def test_js_api_select_input_path_esc_cancel(self):
        """pywebview 윈도우에서 ESC나 취소 버튼으로 다이얼로그를 닫았을 때 fallback 없이 None 반환 검증."""
        class DummyWindow:
            def create_file_dialog(self, *args, **kwargs):
                return None  # ESC / 취소 시 None 반환

        api = JSApi()
        api.set_window(DummyWindow())
        res = api.select_input_path("folder")

        assert res["selected_path"] is None


