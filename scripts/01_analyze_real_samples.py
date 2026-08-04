"""
WinCC OA 실물 프로젝트 샘플 파일 전수 분석 및 파이프라인 검증 스크립트.
"""

from pathlib import Path
import sys
import json

# wincc_reviewer 패키지 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wincc_reviewer"))

from app.core.input_normalization.service import NormalizationService
from app.core.rules.excel_rule_compiler import ExcelRuleCompiler
from app.core.rules.rule_engine import RuleEngine
from app.core.pipeline import Pipeline, PipelineConfig

def run_real_sample_analysis():
    project_root = Path(__file__).resolve().parent.parent
    primary_data_dir = project_root / "primary_data"
    config_dir = project_root / "config"

    print("=== WinCC OA 실물 샘플 데이터 검증 시작 ===")
    
    # 1. 대상 파일 수집
    sample_files = sorted(list(primary_data_dir.glob("*")))
    print(f"수집된 실물 샘플 파일 수: {len(sample_files)}개")

    # 2. 엑셀 룰셋 컴파일
    client_excel = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
    client_mapping = config_dir / "legacy_mapping" / "client.yaml"
    server_excel = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
    server_mapping = config_dir / "legacy_mapping" / "server.yaml"

    client_ruleset = ExcelRuleCompiler.compile_rules(client_excel, client_mapping)
    server_ruleset = ExcelRuleCompiler.compile_rules(server_excel, server_mapping)

    print(f"Client 룰 컴파일 완료: {len(client_ruleset.rules)}개 룰")
    print(f"Server 룰 컴파일 완료: {len(server_ruleset.rules)}개 룰")

    # 3. 각 파일별 파싱 및 룰 실행 분석
    results = []
    for file_path in sample_files:
        if file_path.is_dir():
            continue

        print(f"\n[분석 대상] {file_path.name}")
        parsed = NormalizationService.normalize_and_parse(file_path)
        
        status_str = parsed.parse_status.status.value if hasattr(parsed.parse_status.status, 'value') else str(parsed.parse_status.status)
        funcs = parsed.metadata.get("functions", [])
        gvars = parsed.metadata.get("global_variables", [])
        comments = parsed.metadata.get("comment_lines", [])

        print(f"  * 파싱 상태: {status_str}")
        print(f"  * 감지 인코딩: {parsed.detected_encoding}")
        print(f"  * 추출 함수 수: {len(funcs)}개")
        print(f"  * 추출 전역변수 수: {len(gvars)}개")
        print(f"  * 추출 주석 라인 수: {len(comments)}개")

        # 확장자별 룰셋 라우팅
        target_name = RuleEngine.determine_target_ruleset(file_path)
        ruleset = client_ruleset.rules if target_name == "client" else server_ruleset.rules
        
        violations = RuleEngine.execute(parsed, ruleset)
        print(f"  * 타겟 룰셋: {target_name}")
        print(f"  * 검출된 위반 수: {len(violations)}개")

        for v in violations[:5]:  # 상위 5개 출력
            line_str = f"라인 {v.line_start}" if v.line_start else "라인 미지정"
            print(f"    * [{v.rule_id}] [{v.severity.value}] {v.message} ({line_str})")

        results.append({
            "filename": file_path.name,
            "encoding": parsed.detected_encoding,
            "parse_status": status_str,
            "target_ruleset": target_name,
            "functions_count": len(funcs),
            "global_vars_count": len(gvars),
            "violations_count": len(violations),
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity.value,
                    "message": v.message,
                    "line_start": v.line_start
                }
                for v in violations
            ]
        })

    # 4. 파이프라인 전체 실행 파이프라인 테스트
    pipeline_cfg = PipelineConfig(
        input_path=primary_data_dir,
        output_dir=project_root / "intermediate_results" / "real_sample_run"
    )
    pipeline = Pipeline(pipeline_cfg)
    report = pipeline.run()
    print(f"\n=== 전체 파이프라인 실행 결과 ===")
    print(f"수집 파일: {report.metrics.file_count}개")
    print(f"총 위반 수: {report.metrics.violation_count}개")
    print(f"소요 시간: {report.metrics.timings_ms.get('total', 0)} ms")

    # intermediate_results에 분석 결과 저장
    output_res_path = project_root / "intermediate_results" / "real_samples_analysis_result.json"
    output_res_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_res_path, "w", encoding="utf-8-sig") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n분석 결과 저장 완료: {output_res_path}")

if __name__ == "__main__":
    run_real_sample_analysis()
