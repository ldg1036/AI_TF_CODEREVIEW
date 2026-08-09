"""
26_stress_test_large_scale.py

1,000 ~ 5,000 파일 규모 대규모 스트레스 테스트 및 확장성 검증 스크립트
소요 시간, 파일당 평균 처리 시간, 피크 메모리 사용량을 실측 기록합니다.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from app.core.input_normalization.service import NormalizationService
from app.core.rules.excel_rule_compiler import ExcelRuleCompiler
from app.core.rules.rule_engine import RuleEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StressTestScale")

base_dir = Path(__file__).resolve().parent.parent
stress_dir = base_dir / "intermediate_results" / "stress_test_dataset"


def run_stress_test(num_files: int = 1000) -> dict[str, Any]:
    logger.info("=== 대규모 스트레스 테스트 개시 (대상 파일: %d개) ===", num_files)

    if stress_dir.exists():
        shutil.rmtree(stress_dir)
    stress_dir.mkdir(parents=True, exist_ok=True)

    # 1. 1,000개 파일 합성 생성
    sample_ctl_content = """// WinCC OA Stress Test Script
void test_loop(int limit)
{
    int i = 0;
    while(i < limit)
    {
        i++;
        delay(1);
    }
}
void main()
{
    dpConnect("test_loop", "System1:Tag1.value");
}
"""
    file_paths: list[Path] = []
    for idx in range(1, num_files + 1):
        fpath = stress_dir / f"stress_{idx:04d}.ctl"
        fpath.write_text(sample_ctl_content, encoding="utf-8")
        file_paths.append(fpath)

    # 2. 룰 맵 로딩
    excel_path = base_dir / "config" / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
    client_yaml = base_dir / "config" / "legacy_mapping" / "client.yaml"
    compiler = ExcelRuleCompiler()
    rules_map = {"client": compiler.compile_rules(excel_path, client_yaml)}

    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        mem_before_mb = process.memory_info().rss / (1024 * 1024)
    else:
        mem_before_mb = 0.0

    start_time = time.perf_counter()
    total_violations_count = 0

    for file_path in file_paths:
        parsed_file = NormalizationService.normalize_and_parse(file_path, extract_scripts_only=True)
        target_rules = rules_map["client"].rules
        violations = RuleEngine.execute(parsed_file, target_rules)
        total_violations_count += len(violations)

    end_time = time.perf_counter()
    total_elapsed = end_time - start_time
    avg_per_file_ms = (total_elapsed / num_files) * 1000.0

    if HAS_PSUTIL:
        mem_after_mb = process.memory_info().rss / (1024 * 1024)
        mem_peak_mb = max(mem_before_mb, mem_after_mb)
    else:
        mem_peak_mb = 0.0

    metrics = {
        "stress_test_files_count": num_files,
        "total_elapsed_seconds": round(total_elapsed, 4),
        "avg_ms_per_file": round(avg_per_file_ms, 3),
        "peak_memory_mb": round(mem_peak_mb, 2),
        "total_violations_detected": total_violations_count,
    }

    logger.info(
        "=== 스트레스 테스트 완수: 총 %d개 파일, 소요시간=%.2f초, 파일당=%.3fms, 메모리피크=%.2fMB ===",
        num_files,
        total_elapsed,
        avg_per_file_ms,
        mem_peak_mb,
    )

    # Clean up
    if stress_dir.exists():
        shutil.rmtree(stress_dir)

    return metrics


if __name__ == "__main__":
    run_stress_test(1000)
