"""
19_build_anonymized_golden_fixtures.py

primary_data 원시 파일의 식별정보를 도메인 익명화 픽스처로 전환하는 파이프라인
"""

import os
import re
import sys

def build_anonymized_fixtures():
    primary_dir = "primary_data"
    target_dir = os.path.join("wincc_reviewer", "tests", "fixtures", "anonymized")
    os.makedirs(target_dir, exist_ok=True)

    if not os.path.exists(primary_dir):
        print(f"primary_data 디렉토리 부재: {primary_dir}")
        return False

    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    created_count = 0

    for root, _, files in os.walk(primary_dir):
        for f in files:
            if f.endswith((".ctl", ".pnl", ".xml")):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()

                anonymized_content = ip_pattern.sub("127.0.0.1", content)
                dest_path = os.path.join(target_dir, f"anon_{f}")
                with open(dest_path, "w", encoding="utf-8") as fp:
                    fp.write(anonymized_content)
                created_count += 1

    print(f"Phase 0 익명화 픽스처 파이프라인 완료: 총 {created_count}개 픽스처 생성")
    return True

def main():
    print("=== Phase 0 익명화 픽스처 생성 파이프라인 시작 ===")
    ok = build_anonymized_fixtures()
    if ok:
        print("=== Phase 0 익명화 픽스처 파이프라인 성공 ===")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
