import os
import sys
import re
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SUSPICIOUS_KEYWORDS = [
    "padding",
    "stress testing",
    "dummy",
    "placeholder",
    "lorem ipsum"
]

def analyze_file(file_path: Path) -> dict:
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="utf-8-sig")
        except:
            return {"error": "encoding"}

    lines = content.splitlines()
    total_lines = len(lines)
    if total_lines == 0:
        return {"error": "empty"}

    valid_lines_count = 0
    suspicious_lines_count = 0
    line_counts: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # 순수 주석 라인 판별
        if stripped.startswith("//") or stripped.startswith("#") or (stripped.startswith("/*") and stripped.endswith("*/")) or stripped.startswith("<!--"):
            lower_line = stripped.lower()
            if any(k in lower_line for k in SUSPICIOUS_KEYWORDS):
                suspicious_lines_count += 1
            continue

        valid_lines_count += 1

        # 반복 라인 탐지
        line_counts[stripped] = line_counts.get(stripped, 0) + 1

        # 의심 키워드 탐지
        lower_line = stripped.lower()
        if any(k in lower_line for k in SUSPICIOUS_KEYWORDS):
            suspicious_lines_count += 1

    real_code_line_ratio = valid_lines_count / total_lines if total_lines > 0 else 0.0
    suspicious_ratio = suspicious_lines_count / total_lines if total_lines > 0 else 0.0
    
    max_repetition = max(line_counts.values()) if line_counts else 0

    return {
        "total_lines": total_lines,
        "valid_lines": valid_lines_count,
        "real_code_line_ratio": real_code_line_ratio,
        "suspicious_ratio": suspicious_ratio,
        "max_repetition": max_repetition
    }

def validate_dataset(dataset_dir: Path) -> bool:
    logger.info(f"데이터셋 진위성 검증 시작: {dataset_dir}")
    
    is_real_world = "real_world" in dataset_dir.name.lower() or "raw" in dataset_dir.name.lower()
    
    files = list(dataset_dir.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in [".ctl", ".pnl", ".xml", ".json", ".txt", ".py", ".md", ".csv"]]
    
    if not files:
        logger.warning("검증할 대상 파일이 없습니다.")
        return True

    all_passed = True

    for f in files:
        if "real_world" in f.name.lower() or "raw" in f.name.lower():
            file_is_real_world = True
        else:
            file_is_real_world = is_real_world

        res = analyze_file(f)
        if "error" in res:
            continue
        
        reasons = []
        if res["real_code_line_ratio"] < 0.70:
            reasons.append(f"실행가능 코드 비율 미달 ({res['real_code_line_ratio']*100:.1f}% < 70%)")
        
        if res["max_repetition"] >= 10:
            reasons.append(f"동일 라인 반복 초과 (최대 {res['max_repetition']}회 >= 10회)")
            
        if res["suspicious_ratio"] >= 0.05:
            reasons.append(f"의심 키워드 비율 초과 ({res['suspicious_ratio']*100:.1f}% >= 5%)")

        if file_is_real_world and reasons:
            logger.error(f"[FAIL] {f.name}: 'real_world'/'raw' 라벨 기준 미달 -> {', '.join(reasons)}")
            all_passed = False
        elif reasons:
            logger.warning(f"[WARNING] {f.name}: 진위성 의심 -> {', '.join(reasons)}")

    if not all_passed:
        logger.error("[결과] 진위성 기준을 미달하는 파일들이 발견되었습니다. 'real_world' 라벨을 사용할 수 없으며, 'stress_test_dataset/' 등으로 변경해야 합니다.")
        return False
        
    logger.info("[결과] 데이터셋 진위성 검증 통과 (PASS).")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_dataset_authenticity.py <dataset_directory>")
        sys.exit(1)
        
    target_dir = Path(sys.argv[1]).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: 디렉토리를 찾을 수 없습니다: {target_dir}")
        sys.exit(1)
        
    if not validate_dataset(target_dir):
        sys.exit(1)
