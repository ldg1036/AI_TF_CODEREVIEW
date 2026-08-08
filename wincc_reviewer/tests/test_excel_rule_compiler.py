"""
ExcelRuleCompiler 유닛 테스트 (09_구현착수_패키지_계약.md §5 & §8 기준).

검증 항목:
1. Client 15개, Server 20개 Excel + legacy_mapping 정상 컴파일
2. 미매핑 source_key 발생 시 ExcelCompileError 발생
3. SHA256 불일치 시 ExcelCompileError 발생
4. manual 항목이 MANUAL_REVIEW 상태로 올바르게 분류되는지 검증
5. 자동 룰(auto_full) 항목의 RuleDefinition 컴파일 검증
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from app.core.models import CheckerType, SeverityLevel
from app.core.rules.excel_rule_compiler import ExcelCompileError, ExcelRuleCompiler


class TestExcelRuleCompiler:
    """ExcelRuleCompiler 기능 및 오류 처리 테스트."""

    @pytest.fixture
    def client_excel_path(self, config_dir: Path) -> Path:
        return config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"

    @pytest.fixture
    def server_excel_path(self, config_dir: Path) -> Path:
        return config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"

    @pytest.fixture
    def client_yaml_path(self, config_dir: Path) -> Path:
        return config_dir / "legacy_mapping" / "client.yaml"

    @pytest.fixture
    def server_yaml_path(self, config_dir: Path) -> Path:
        return config_dir / "legacy_mapping" / "server.yaml"

    def test_compile_client_excel(self, client_excel_path: Path, client_yaml_path: Path):
        """Client Excel + client.yaml 정상 컴파일 테스트."""
        res = ExcelRuleCompiler.compile_rules(client_excel_path, client_yaml_path)

        assert res.total_count == 15
        assert len(res.rules) == 15
        assert res.manual_review_count == 0
        assert res.automated_count == 15
        assert res.unmapped_count == 0
        assert res.profile_version == "1.0.0"
        assert res.file_sha256 != ""

        # 첫번째 룰 검증
        rule0 = res.rules[0]
        assert rule0.checker_type == CheckerType.BUILTIN
        assert rule0.rule_id == "CTL_PRF_002"

    def test_compile_server_excel(self, server_excel_path: Path, server_yaml_path: Path):
        """Server Excel + server.yaml 정상 컴파일 테스트."""
        res = ExcelRuleCompiler.compile_rules(server_excel_path, server_yaml_path)

        assert res.total_count == 20
        assert len(res.rules) == 20
        assert res.manual_review_count == 0
        assert res.automated_count == 20
        assert res.unmapped_count == 0

    def test_compile_sha256_mismatch(self, client_excel_path: Path, tmp_path: Path):
        """SHA256 불일치 시 ExcelCompileError 발생 검증."""
        fake_yaml = tmp_path / "fake_client.yaml"
        data = {
            "profile_version": "1.0.0",
            "source_excel_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            "entries": []
        }
        with open(fake_yaml, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        with pytest.raises(ExcelCompileError) as exc_info:
            ExcelRuleCompiler.compile_rules(client_excel_path, fake_yaml, verify_sha256=True)
        assert "SHA256 해시 불일치" in str(exc_info.value)

    def test_compile_unmapped_source_key(self, client_excel_path: Path, client_yaml_path: Path, tmp_path: Path):
        """매핑 프로파일에 등록되지 않은 source_key 존재 시 ExcelCompileError 발생 검증."""
        with open(client_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 1개 항목 삭제
        data["entries"].pop()

        broken_yaml = tmp_path / "broken_client.yaml"
        with open(broken_yaml, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        with pytest.raises(ExcelCompileError) as exc_info:
            ExcelRuleCompiler.compile_rules(client_excel_path, broken_yaml, verify_sha256=False)
        assert "매핑 프로파일에 등록되지 않은 항목" in str(exc_info.value)

    def test_compile_duplicate_source_key_in_profile(self, client_excel_path: Path, client_yaml_path: Path, tmp_path: Path):
        """매핑 프로파일 내 중복 source_key 존재 시 ExcelCompileError 발생 검증."""
        with open(client_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 항목 복제
        data["entries"].append(data["entries"][0])

        dup_yaml = tmp_path / "dup_client.yaml"
        with open(dup_yaml, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        with pytest.raises(ExcelCompileError) as exc_info:
            ExcelRuleCompiler.compile_rules(client_excel_path, dup_yaml, verify_sha256=False)
        assert "중복된 source_key" in str(exc_info.value)

    def test_compile_with_automated_rule(self, client_excel_path: Path, client_yaml_path: Path, tmp_path: Path):
        """자동화 룰(auto_full, builtin) 항목 컴파일 검증."""
        with open(client_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for entry in data["entries"]:
            entry["automation_mode"] = "manual"
            entry["rule_ids"] = []
            entry.pop("checker_type", None)
            entry.pop("checker_key", None)

        # 첫 번째 항목을 자동화 룰로 변경
        data["entries"][0]["automation_mode"] = "auto_full"
        data["entries"][0]["rule_ids"] = ["CTL-RES-001"]
        data["entries"][0]["checker_type"] = "builtin"
        data["entries"][0]["checker_key"] = "ctl.dp_connect_pair"
        data["entries"][0]["severity"] = "Critical"
        data["entries"][0]["message"] = "dpConnect 해제 누락 발생"

        auto_yaml = tmp_path / "auto_client.yaml"
        with open(auto_yaml, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        res = ExcelRuleCompiler.compile_rules(client_excel_path, auto_yaml, verify_sha256=False)

        assert res.total_count == 15
        assert res.automated_count == 1
        assert res.manual_review_count == 14

        auto_rule = res.rules[0]
        assert auto_rule.rule_id == "CTL-RES-001"
        assert auto_rule.checker_type == CheckerType.BUILTIN
        assert auto_rule.severity == SeverityLevel.CRITICAL
        assert auto_rule.checker_key == "ctl.dp_connect_pair"
        assert auto_rule.message == "dpConnect 해제 누락 발생"
