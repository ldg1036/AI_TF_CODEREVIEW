"""
WinCC OA 코드 리뷰 자동화 도구 — UI Settings API 단위 테스트.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml
from app.ui.api import JSApi


class TestSettingsAPI:
    """JSApi의 설정 관리 메서드 테스트 스위트."""

    def test_get_and_update_settings(self):
        """설정 조회 및 업데이트 검증."""
        api = JSApi()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config = Path(tmpdir) / "settings.yaml"
            sample_settings = {
                "ai": {
                    "enabled": True,
                    "provider": "local",
                    "local_server": {
                        "host": "127.0.0.1",
                        "port": 8000,
                        "api_key": "test_key",
                    },
                }
            }

            with open(tmp_config, "w", encoding="utf_8_sig") as f:
                yaml.dump(sample_settings, f, allow_unicode=True)

            with patch.object(api, "_resolve_settings_path", return_value=tmp_config):
                # 조회 검증
                res_get = api.get_settings()
                assert res_get["success"] is True
                assert res_get["settings"]["ai"]["provider"] == "local"

                # 수정 및 업데이트 검증
                modified_settings = res_get["settings"]
                modified_settings["ai"]["local_server"]["port"] = 9999

                res_update = api.update_settings(modified_settings)
                assert res_update["success"] is True
                assert res_update["settings"]["ai"]["local_server"]["port"] == 9999

                # 다시 읽어서 디스크 반영 검증
                res_reget = api.get_settings()
                assert res_reget["settings"]["ai"]["local_server"]["port"] == 9999

    def test_list_ai_models(self):
        """AI 모델 목록 조회 검증."""
        api = JSApi()

        res_mock = api.list_ai_models({"provider": "mock"})
        assert res_mock["success"] is True
        assert "mock_gemini_3_6_pro" in res_mock["models"]

        res_gemini = api.list_ai_models({"provider": "gemini"})
        assert res_gemini["success"] is True
        assert len(res_gemini["models"]) >= 1

        res_local_fallback = api.list_ai_models({"provider": "local", "host": "127.0.0.1", "port": 1})
        assert "models" in res_local_fallback
        assert "sane_local_llm" in res_local_fallback["models"]

    def test_custom_settings_path(self):
        """커스텀 설정 저장 경로 변경 검증."""
        api = JSApi()

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_yaml = Path(tmpdir) / "custom_dir" / "my_settings.yaml"
            data_to_save = {
                "ai": {
                    "enabled": False,
                    "provider": "mock",
                }
            }

            res_save = api.update_settings(data_to_save, custom_path=str(custom_yaml))
            assert res_save["success"] is True
            assert custom_yaml.exists()

            res_load = api.get_settings(custom_path=str(custom_yaml))
            assert res_load["success"] is True
            assert res_load["settings"]["ai"]["provider"] == "mock"


