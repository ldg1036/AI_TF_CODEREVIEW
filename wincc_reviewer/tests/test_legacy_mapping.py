"""
Legacy Mapping Profile 검증 테스트.

09_구현착수_패키지_계약.md §5 준수 여부 검증:
- config/legacy_mapping/client.yaml (15개 항목)
- config/legacy_mapping/server.yaml (20개 항목)
- Excel SHA256 해시 일치 검증
- 모든 항목이 등록되어 있는지, 중복 source_key가 없는지 검증
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from app.core.rules.excel_rule_loader import calculate_file_sha256


class TestLegacyMappingProfile:
    """legacy_mapping_profile YAML 검증 테스트."""

    @pytest.fixture
    def client_yaml_path(self, config_dir: Path) -> Path:
        path = config_dir / "legacy_mapping" / "client.yaml"
        assert path.exists(), f"client.yaml 누락: {path}"
        return path

    @pytest.fixture
    def server_yaml_path(self, config_dir: Path) -> Path:
        path = config_dir / "legacy_mapping" / "server.yaml"
        assert path.exists(), f"server.yaml 누락: {path}"
        return path

    def test_client_legacy_mapping_profile(self, client_yaml_path: Path, config_dir: Path):
        """Client 레거시 매핑 프로파일 검증."""
        with open(client_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["profile_version"] == "1.0.0"
        assert len(data["entries"]) == 15, f"Client 매핑 항목 수는 15개여야 합니다 (실제: {len(data['entries'])})"

        # Excel 파일 SHA256 일치 검증
        excel_path = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
        actual_sha256 = calculate_file_sha256(excel_path)
        assert data["source_excel_sha256"] == actual_sha256

        # source_key 중복 검증 및 필수 필드 검증
        source_keys = [e["source_key"] for e in data["entries"]]
        assert len(source_keys) == len(set(source_keys)), "중복된 source_key가 존재합니다."
        for entry in data["entries"]:
            assert "source_key" in entry and entry["source_key"] != ""
            assert "automation_mode" in entry and entry["automation_mode"] in ["auto_full", "auto_violation_only", "manual"]

    def test_server_legacy_mapping_profile(self, server_yaml_path: Path, config_dir: Path):
        """Server 레거시 매핑 프로파일 검증."""
        with open(server_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["profile_version"] == "1.0.0"
        assert len(data["entries"]) == 20, f"Server 매핑 항목 수는 20개여야 합니다 (실제: {len(data['entries'])})"

        # Excel 파일 SHA256 일치 검증
        excel_path = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
        actual_sha256 = calculate_file_sha256(excel_path)
        assert data["source_excel_sha256"] == actual_sha256

        # source_key 중복 검증 및 필수 필드 검증
        source_keys = [e["source_key"] for e in data["entries"]]
        assert len(source_keys) == len(set(source_keys)), "중복된 source_key가 존재합니다."
        for entry in data["entries"]:
            assert "source_key" in entry and entry["source_key"] != ""
            assert "automation_mode" in entry and entry["automation_mode"] in ["auto_full", "auto_violation_only", "manual"]
