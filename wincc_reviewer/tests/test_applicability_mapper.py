"""
체크리스트 적용성 매퍼 (ApplicabilityMapper) 단위 테스트.

설계 기준 (06_구현기준_추적성_검증기준.md §5 & 09_구현착수 §5):
- Client 15/15, Server 20/20 매핑 프로파일이 정상 검증되고 커버리지 100%를 만족하는지 검증합니다.
"""

from pathlib import Path
import pytest

from app.core.rules.applicability_mapper import ApplicabilityMapper, ApplicabilityReport


class TestApplicabilityMapper:
    """ApplicabilityMapper 검증 테스트."""

    @pytest.fixture
    def config_dir(self) -> Path:
        """클로드prd/config 디렉터리 경로를 반환합니다."""
        current_file = Path(__file__).resolve()
        candidate = current_file.parent.parent.parent / "config"
        if candidate.exists():
            return candidate
        return Path("./config")

    def test_map_client_profile_coverage(self, config_dir: Path):
        """Client 레거시 매핑 프로파일(15개 항목) 검증 테스트."""
        client_yaml = config_dir / "legacy_mapping" / "client.yaml"
        if not client_yaml.exists():
            pytest.skip("client.yaml 파일이 없습니다.")

        report = ApplicabilityMapper.map_profile(client_yaml)
        assert report.total_items == 15, f"Client 매핑 항목 수는 15개여야 합니다: {report.total_items}"
        assert report.coverage_ratio == 1.0, "Client 매핑 커버리지는 100%여야 합니다."
        assert ApplicabilityMapper.verify_coverage(report, expected_total=15) is True

    def test_map_server_profile_coverage(self, config_dir: Path):
        """Server 레거시 매핑 프로파일(20개 항목) 검증 테스트."""
        server_yaml = config_dir / "legacy_mapping" / "server.yaml"
        if not server_yaml.exists():
            pytest.skip("server.yaml 파일이 없습니다.")

        report = ApplicabilityMapper.map_profile(server_yaml)
        assert report.total_items == 20, f"Server 매핑 항목 수는 20개여야 합니다: {report.total_items}"
        assert report.coverage_ratio == 1.0, "Server 매핑 커버리지는 100%여야 합니다."
        assert ApplicabilityMapper.verify_coverage(report, expected_total=20) is True

    def test_missing_profile_raises(self):
        """존재하지 않는 프로파일 경로 요청 시 FileNotFoundError 발생 테스트."""
        with pytest.raises(FileNotFoundError):
            ApplicabilityMapper.map_profile(Path("./non_existent_profile.yaml"))

    def test_to_checklist_applicability(self, config_dir: Path):
        """ApplicabilityReport를 ChecklistApplicability 데이터 모델로 변환하는지 검증."""
        client_yaml = config_dir / "legacy_mapping" / "client.yaml"
        if not client_yaml.exists():
            pytest.skip("client.yaml 파일이 없습니다.")

        report = ApplicabilityMapper.map_profile(client_yaml)
        ca_list = ApplicabilityMapper.to_checklist_applicability(report)

        assert len(ca_list) == 15
        assert ca_list[0].checklist_item != ""
        assert hasattr(ca_list[0], "automation_mode")
        assert ca_list[0].status in ("resolved", "manual_review", "mapping_incomplete")

