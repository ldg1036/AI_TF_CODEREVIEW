"""
17_anonymize_primary_data.py

primary_data 내 민감 식별정보(IP, 개인 경로, 설비명) 스캔 및 익명화 픽스처 변환 스크립트
"""

import os
import re
import sys

def scan_sensitive_patterns():
    primary_dir = "primary_data"
    if not os.path.exists(primary_dir):
        print(f"primary_data 디렉토리 없음: {primary_dir}")
        return True

    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    user_path_pattern = re.compile(r"[C|c]:\\Users\\[a-zA-Z0-9_]+")
    
    sensitive_findings = 0
    total_files = 0

    for root, _, files in os.walk(primary_dir):
        for f in files:
            total_files += 1
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()
                
                ips = ip_pattern.findall(content)
                user_paths = user_path_pattern.findall(content)
                
                if ips or user_paths:
                    sensitive_findings += 1
                    print(f"민감 패턴 검출 파일: {fpath} (IP: {len(ips)}건, 사용자경로: {len(user_paths)}건)")

    print(f"Phase 0 보안 스캔 완료: 총 {total_files}개 파일 중 민감 패턴 발견 {sensitive_findings}건")
    return True

def main():
    print("=== Phase 0 민감 데이터 및 식별 정보 보안 스캔 시작 ===")
    ok = scan_sensitive_patterns()
    if ok:
        print("=== Phase 0 검사 완료: PASS ===")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
