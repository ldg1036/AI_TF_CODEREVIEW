"""
verify_coverage_claim.py

원천 매핑 데이터(client.yaml, server.yaml) 실시간 동적 파싱 기반 커버리지 및 내장 체커 수 자동 실측 검증 파이프라인
"""

from pathlib import Path
import sys
import os
import yaml

base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir / "wincc_reviewer"))

def verify_coverage_claim():
    from app.core.rules.checker_registry import CheckerRegistry

    checkers = CheckerRegistry.list_registered()
    checker_count = len(checkers)

    client_yaml_path = base_dir / "config" / "legacy_mapping" / "client.yaml"
    server_yaml_path = base_dir / "config" / "legacy_mapping" / "server.yaml"

    with open(client_yaml_path, "r", encoding="utf-8") as f:
        client_data = yaml.safe_load(f)
    with open(server_yaml_path, "r", encoding="utf-8") as f:
        server_data = yaml.safe_load(f)

    client_entries = client_data.get("entries", [])
    server_entries = server_data.get("entries", [])

    client_total = len(client_entries)
    client_auto = sum(1 for e in client_entries if e.get("automation_mode") != "manual")

    server_total = len(server_entries)
    server_auto = sum(1 for e in server_entries if e.get("automation_mode") != "manual")

    client_coverage = round((client_auto / client_total) * 100.0, 1) if client_total > 0 else 0.0
    server_coverage = round((server_auto / server_total) * 100.0, 1) if server_total > 0 else 0.0
    overall_coverage = round((client_coverage + server_coverage) / 2.0, 1)

    print(f"등록 체커 수: {checker_count}개")
    print(f"Client 원천 매핑: {client_auto}/{client_total} 항목 자동화 ({client_coverage}%)")
    print(f"Server 원천 매핑: {server_auto}/{server_total} 항목 자동화 ({server_coverage}%)")
    print(f"원천 매핑 실측 평균 자동화 커버리지: {overall_coverage}%")

    if checker_count >= 30 and overall_coverage >= 99.9:
        print("성공: 원천 YAML 파싱 동적 연산 결과 자동화 커버리지 100% 실측 달성 검증 통과")
        return True
    else:
        print(f"오류: 체커 수 미달 또는 커버리지 미달 ({checker_count}개, {overall_coverage}%)")
        return False

if __name__ == "__main__":
    if not verify_coverage_claim():
        sys.exit(1)
    sys.exit(0)
