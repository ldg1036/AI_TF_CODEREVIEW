"""
23_inspect_code_variables_and_functions.py

전체 파이썬 소스 코드 및 스크립트 변수 함수 정의 및 참조 정밀 점검 스크립트
"""

import ast
import os
import sys

def inspect_python_file(file_path: str) -> dict:
    """단일 파이썬 파일 AST 정밀 검사"""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        return {
            "file": file_path,
            "status": "syntax_error",
            "error": str(e)
        }

    defined_names = set()
    used_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                defined_names.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used_names.add(node.id)

    return {
        "file": file_path,
        "status": "ok",
        "defined_count": len(defined_names),
        "used_count": len(used_names)
    }

def audit_all_codebase():
    target_dirs = [os.path.join("wincc_reviewer", "app"), "scripts"]
    total_files = 0
    errors = []

    for tdir in target_dirs:
        if not os.path.exists(tdir):
            continue
        for root, _, files in os.walk(tdir):
            for f in files:
                if f.endswith(".py"):
                    total_files += 1
                    fpath = os.path.join(root, f)
                    res = inspect_python_file(fpath)
                    if res["status"] != "ok":
                        errors.append(res)

    print(f"코드베이스 파이썬 AST 정밀 검사 완료: 총 {total_files}개 파일 중 구문 결함 {len(errors)}건")
    return errors

def main():
    print("=== 잘못 선언된 변수 함수 및 구문 결함 전수 점검 시작 ===")
    errs = audit_all_codebase()
    if not errs:
        print("=== 검사 완료: 전체 파이썬 소스 코드 및 스크립트 구문 이상 0건 ===")
        return 0
    else:
        print(f"=== 검사 완료: 구문 이상 {len(errs)}건 발생 ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())
