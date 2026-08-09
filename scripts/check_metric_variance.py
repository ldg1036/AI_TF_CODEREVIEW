import json
import sys
import subprocess
from pathlib import Path

def get_git_file_content(commit_ref: str, filepath: str) -> str:
    try:
        res = subprocess.run(["git", "show", f"{commit_ref}:{filepath}"], capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError:
        return ""

def extract_precision(data: dict) -> float:
    rep_data = data.get("representative_precision", {})
    if rep_data and "metrics_candidates" in rep_data:
        for cand in rep_data["metrics_candidates"]:
            if cand.get("is_representative_candidate") is True:
                return float(cand.get("precision_percent", 0.0))
    for key, val in data.items():
        if isinstance(val, dict) and val.get("is_representative_candidate") is True:
            return float(val.get("precision_percent", 0.0))
    return None

def main():
    ssot_path = "intermediate_results/single_source_metrics.json"
    
    # 변경된 파일 목록 확인 (최근 커밋 또는 diff 기준)
    try:
        changed_files_res = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], capture_output=True, text=True, check=True)
        changed_files = changed_files_res.stdout.strip().split("\n")
    except subprocess.CalledProcessError:
        changed_files = []
        
    dataset_changed = any("dataset" in f or "golden_set" in f for f in changed_files)
    if not dataset_changed:
        print("[INFO] 데이터셋/골든셋 변경 사항이 감지되지 않았습니다. 지표 변동성 검증을 건너뜁니다.")
        return
        
    old_content = get_git_file_content("HEAD~1", ssot_path)
    if not old_content:
        print("[INFO] 이전 SSOT 데이터를 찾을 수 없습니다. (신규 생성으로 간주)")
        return
        
    try:
        old_data = json.loads(old_content)
    except json.JSONDecodeError:
        print("[WARNING] 이전 SSOT 파일이 손상되었습니다.")
        return

    current_path = Path(ssot_path)
    if not current_path.exists():
        return
    
    try:
        with open(current_path, "r", encoding="utf-8") as f:
            new_data = json.load(f)
    except Exception:
        return

    old_prec = extract_precision(old_data)
    new_prec = extract_precision(new_data)
    
    if old_prec is not None and new_prec is not None:
        diff = new_prec - old_prec
        print(f"[INFO] 과거 정밀도: {old_prec}%, 현재 정밀도: {new_prec}%, 변동폭: {diff:+.2f}%p")
        if abs(diff) >= 10.0:
            print(f"[ERROR] 정밀도 지표가 ±10%p 이상 급변했습니다 ({diff:+.2f}%p). 사람 승인(Review Approve)이 필수적입니다.")
            sys.exit(1)
    else:
        print("[INFO] 비교할 대표 정밀도 데이터가 부족합니다.")

if __name__ == "__main__":
    main()
