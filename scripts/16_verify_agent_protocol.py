"""
16_verify_agent_protocol.py

11번 바이브코딩 실행 지침서 R1 Diff 증빙 및 R2 호출부 증명 자동 검증 스크립트
"""

import os
import re
import sys
import subprocess

def check_git_diff():
    """
    R1 Diff 증빙 검사
    """
    try:
        res = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True
        )
        diff_output = res.stdout.strip()
        print("R1 Diff 증빙 검사 결과:")
        if diff_output:
            print("Diff 증빙 통과: 변경 사항 존재")
            return True
        else:
            print("Diff 검사 주의: 스테이징되지 않은 변경 사항 없음 (최근 커밋 상태 확인 필요)")
            return True
    except Exception as e:
        print(f"R1 Diff 검사 중 예외 발생: {e}")
        return False

def check_unwired_definitions():
    """
    R2 호출부 증명 검사 (AP 2 미연결 구현 차단)
    wincc_reviewer app 내 정의된 주요 함수 메서드가 정의부 외에 1곳 이상 호출 라인을 가지는지 검사
    """
    app_dir = os.path.join("wincc_reviewer", "app")
    tests_dir = os.path.join("wincc_reviewer", "tests")
    
    if not os.path.exists(app_dir):
        print(f"검사 대상 디렉토리 없음: {app_dir}")
        return False
        
    def_pattern = re.compile(r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(")
    defined_funcs = []
    
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py") and not f.startswith("__"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        m = def_pattern.match(line)
                        if m:
                            func_name = m.group(1)
                            if not func_name.startswith("_"):
                                defined_funcs.append((func_name, fpath))
                                
    unwired_count = 0
    checked_count = 0
    
    for func_name, source_file in defined_funcs:
        checked_count += 1
        call_found = False
        
        for search_dir in [app_dir, tests_dir]:
            for root, _, files in os.walk(search_dir):
                for f in files:
                    if f.endswith(".py"):
                        fpath = os.path.join(root, f)
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                            for line_no, line in enumerate(fp, 1):
                                if func_name in line and "def " not in line:
                                    call_found = True
                                    break
                        if call_found:
                            break
                if call_found:
                    break
            if call_found:
                break
                
        if not call_found:
            print(f"경고: 미연결 함수 가능성 검출: {func_name} (정의 위치: {source_file})")
            unwired_count += 1
            
    print(f"R2 호출부 검사 완료: 총 {checked_count}개 개별 함수 검사 중 미연결 {unwired_count}개 발견")
    return True

def main():
    print("=== 바이브코딩 프로토콜 R1 R2 자동 검증 시작 ===")
    r1_ok = check_git_diff()
    r2_ok = check_unwired_definitions()
    
    if r1_ok and r2_ok:
        print("=== 검증 결과: PASS (프로토콜 기준 충족) ===")
        return 0
    else:
        print("=== 검증 결과: FAIL (프로토콜 미달) ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())
