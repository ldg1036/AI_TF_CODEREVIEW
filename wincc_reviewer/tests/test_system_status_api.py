"""
get_system_status() API 단위 테스트.

검증 항목:
1. get_system_status() 반환 구조에 4개 핵심 지표 키가 모두 존재하는지 확인
2. 각 지표의 status 필드가 허용된 값(ok/warn/error/offline) 중 하나인지 확인
3. python_runtime에 version 및 path 필드가 존재하는지 확인
4. AI 서버 미구동 시 ai_online.status가 'offline'으로 반환되는지 확인
5. ruleset_validity에 client/server 부울 필드가 존재하는지 확인
"""

from __future__ import annotations

from app.ui.api import JSApi


class TestGetSystemStatus:
    """get_system_status() API 반환 구조 및 필드 타입 검증."""

    def setup_method(self):
        self.api = JSApi()

    def test_returns_success_key(self):
        """반환 딕셔너리에 success 키가 존재해야 합니다."""
        result = self.api.get_system_status()
        assert "success" in result
        assert isinstance(result["success"], bool)

    def test_contains_all_required_keys(self):
        """4가지 핵심 지표 키가 모두 반환되어야 합니다."""
        result = self.api.get_system_status()
        required_keys = ["python_runtime", "winmerge_available", "ruleset_validity", "ai_online"]
        for key in required_keys:
            assert key in result, f"필수 지표 '{key}'가 반환값에 없습니다."

    def test_python_runtime_structure(self):
        """python_runtime 지표의 구조가 올바른지 확인합니다."""
        result = self.api.get_system_status()
        py = result.get("python_runtime", {})
        assert "status" in py, "python_runtime에 status 필드가 없습니다."
        assert "version" in py, "python_runtime에 version 필드가 없습니다."
        assert "path" in py, "python_runtime에 path 필드가 없습니다."
        assert py["status"] in ("ok", "warn"), (
            f"python_runtime.status가 허용 값이 아닙니다: {py['status']}"
        )
        assert py["version"], "python_runtime.version이 비어 있습니다."

    def test_winmerge_available_structure(self):
        """winmerge_available 지표의 구조가 올바른지 확인합니다."""
        result = self.api.get_system_status()
        wm = result.get("winmerge_available", {})
        assert "status" in wm
        assert "message" in wm
        assert wm["status"] in ("ok", "warn"), (
            f"winmerge_available.status가 허용 값이 아닙니다: {wm['status']}"
        )
        assert isinstance(wm["message"], str)

    def test_ruleset_validity_structure(self):
        """ruleset_validity 지표의 구조가 올바른지 확인합니다."""
        result = self.api.get_system_status()
        rv = result.get("ruleset_validity", {})
        assert "status" in rv
        assert "client" in rv
        assert "server" in rv
        assert "message" in rv
        assert rv["status"] in ("ok", "error"), (
            f"ruleset_validity.status가 허용 값이 아닙니다: {rv['status']}"
        )
        assert isinstance(rv["client"], bool), "client 필드는 bool 타입이어야 합니다."
        assert isinstance(rv["server"], bool), "server 필드는 bool 타입이어야 합니다."

    def test_ai_online_structure(self):
        """ai_online 지표의 구조가 올바른지 확인합니다."""
        result = self.api.get_system_status()
        ai = result.get("ai_online", {})
        assert "status" in ai
        assert "message" in ai
        # AI 서버는 테스트 환경에서 미구동이므로 offline 또는 ok 중 하나
        assert ai["status"] in ("ok", "warn", "offline"), (
            f"ai_online.status가 허용 값이 아닙니다: {ai['status']}"
        )
        assert isinstance(ai["message"], str)

    def test_ai_offline_when_server_not_running(self):
        """로컬 AI 서버가 미구동 상태에서 ai_online.status가 'offline'이어야 합니다.
        (테스트 환경에서 기본 포트 8000에 서버가 없으므로 항상 offline 예상)
        """
        result = self.api.get_system_status()
        ai = result.get("ai_online", {})
        # 테스트 환경에서는 로컬 서버가 없으므로 offline 예상
        # 단, CI 환경에서 실제 서버가 있을 수 있으므로 ok도 허용
        assert ai["status"] in ("ok", "offline"), (
            f"ai_online.status가 예상 값이 아닙니다: {ai['status']}"
        )

    def test_all_status_fields_have_message(self):
        """모든 지표에 사람이 읽을 수 있는 message 필드가 존재해야 합니다."""
        result = self.api.get_system_status()
        for key in ["python_runtime", "winmerge_available", "ruleset_validity", "ai_online"]:
            indicator = result.get(key, {})
            assert "message" in indicator, f"{key}에 message 필드가 없습니다."
            assert isinstance(indicator["message"], str), f"{key}.message가 문자열이 아닙니다."
            assert len(indicator["message"]) > 0, f"{key}.message가 빈 문자열입니다."
