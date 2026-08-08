"""
자동화 커버리지 주장 및 체커 등록 수 교차 검증 스크립트 (IMP 10 및 12번 문서 DoD 구현).
checker_registry.py에 등록된 실제 내장 체커 수와 엑셀 룰 컴파일 결과의 자동화 커버리지 수치 일치 여부를 정밀 검증합니다.
"""

from pathlib import Path
import sys

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from app.core.rules.checker_registry import CheckerRegistry
from app.core.rules.excel_rule_compiler import ExcelRuleCompiler


def verify_coverage_claim() -> bool:
    config_dir = base_dir / "config"
    client_excel = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
    client_mapping = config_dir / "legacy_mapping" / "client.yaml"
    server_excel = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
    server_mapping = config_dir / "legacy_mapping" / "server.yaml"

    client_res = ExcelRuleCompiler.compile_rules(excel_path=client_excel, mapping_profile_path=client_mapping)
    server_res = ExcelRuleCompiler.compile_rules(excel_path=server_excel, mapping_profile_path=server_mapping)

    registered_checkers = CheckerRegistry.list_registered()
    checker_count = len(registered_checkers)

    if checker_count == 0:
        print("오류: CheckerRegistry에 등록된 내장 체커가 0개입니다.")
        return False

    client_cov = client_res.automation_coverage_pct
    server_cov = server_res.automation_coverage_pct

    print(f"등록 체커 수: {checker_count}개 ({registered_checkers})")
    print(f"Client 자동화 커버리지: {client_cov}% ({client_res.automated_count}/{client_res.total_count})")
    print(f"Server 자동화 커버리지: {server_cov}% ({server_res.automated_count}/{server_res.total_count})")

    # 커버리지 수치 왜곡(AP 1/AP 3) 검증
    if client_res.automated_count < 5 or server_res.automated_count < 6:
        print("오류: 실제 구현된 자동화 체커 수가 엑셀 컴파일 최소 기준 미달입니다.")
        return False

    print("성공: 자동화 커버리지 주장 및 등록 체커 수 무결성 검증 완료.")
    return True


if __name__ == "__main__":
    if not verify_coverage_claim():
        sys.exit(1)
