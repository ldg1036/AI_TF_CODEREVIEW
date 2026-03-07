"""
CtrlppCheck 실행 래퍼

실행 전 업데이트를 확인하고 ctrlppcheck.exe를 호출합니다.
"""

import os
import sys
import subprocess
import argparse
from typing import List, Optional

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

# 업데이트 모듈 import
sys.path.insert(0, TOOLS_DIR)
try:
    from ctrlppcheck_updater import check_and_update, CtrlppCheckUpdater, TKINTER_AVAILABLE
except ImportError:
    print("업데이트 모듈을 찾을 수 없습니다.")
    check_and_update = None
    CtrlppCheckUpdater = None
    TKINTER_AVAILABLE = False


def get_ctrlppcheck_exe() -> str:
    """
    ctrlppcheck.exe 경로 반환
    
    Returns:
        exe 파일 경로
    """
    # 여러 가능한 경로 확인
    possible_paths = [
        # v1.0.2 구조
        os.path.join(BASE_DIR, "tools", "CtrlppCheck", "v1.0.2", "extract", 
                     "WinCCOA_QualityChecks", "bin", "ctrlppcheck", "ctrlppcheck.exe"),
        # 기본 구조
        os.path.join(BASE_DIR, "tools", "CtrlppCheck", "extract", 
                     "WinCCOA_QualityChecks", "bin", "ctrlppcheck", "ctrlppcheck.exe"),
        # 다운로드만 있는 경우
        os.path.join(BASE_DIR, "tools", "CtrlppCheck", "download", "ctrlppcheck.exe"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return possible_paths[0]  # 기본값 반환


def get_config_paths() -> dict:
    """
    설정 파일 경로들 반환
    
    Returns:
        설정 파일 경로 딕셔너리
    """
    extract_base = os.path.join(BASE_DIR, "tools", "CtrlppCheck", "extract", "WinCCOA_QualityChecks")
    
    return {
        "library": os.path.join(extract_base, "data", "ctrlPpCheck", "cfg", "ctrl.xml"),
        "rule_file": os.path.join(extract_base, "data", "ctrlPpCheck", "rule", "ctrl.xml"),
        "naming_rule": os.path.join(extract_base, "data", "ctrlPpCheck", "rule", "variableNaming.xml"),
        "function_naming": os.path.join(extract_base, "data", "ctrlPpCheck", "rule", "functionNaming.xml"),
        "class_naming": os.path.join(extract_base, "data", "ctrlPpCheck", "rule", "classNaming.xml"),
    }


def build_command(args: argparse.Namespace, exe_path: str) -> List[str]:
    """
    ctrlppcheck 명령어 구성
    
    Args:
        args: 명령줄 인자
        exe_path: exe 파일 경로
        
    Returns:
        명령어 리스트
    """
    cmd = [exe_path]
    
    config = get_config_paths()
    
    # 기본 필수 옵션
    if args.project_name:
        cmd.append(f"--winccoa-projectName={args.project_name}")
    else:
        cmd.append("--winccoa-projectName=CodeReview")
    
    # 활성화 옵션
    if args.enable:
        cmd.append(f"--enable={args.enable}")
    elif args.all:
        cmd.append("--enable=all")
    
    # 설정 파일들
    if args.library:
        cmd.append(f"--library={args.library}")
    elif os.path.exists(config["library"]):
        cmd.append(f"--library={config['library']}")
    
    if args.rule_file:
        cmd.append(f"--rule-file={args.rule_file}")
    elif os.path.exists(config["rule_file"]):
        cmd.append(f"--rule-file={config['rule_file']}")
    
    if args.naming_rule:
        cmd.append(f"--naming-rule-file={args.naming_rule}")
    elif os.path.exists(config["naming_rule"]):
        cmd.append(f"--naming-rule-file={config['naming_rule']}")
    
    # 플랫폼
    if args.platform:
        cmd.append(f"--platform={args.platform}")
    
    # 출력 형식
    if args.xml:
        cmd.append("--xml")
    
    if args.quiet:
        cmd.append("--quiet")
    
    if args.verbose:
        cmd.append("--verbose")
    
    # 억제 옵션
    if args.inline_suppr:
        cmd.append("--inline-suppr")
    
    if args.inconclusive:
        cmd.append("--inconclusive")
    
    # 추가 옵션
    if args.output_file:
        cmd.append(f"--output-file={args.output_file}")
    
    if args.suppressions:
        cmd.append(f"--suppressions-list={args.suppressions}")
    
    # 입력 파일/경로
    if args.files:
        cmd.extend(args.files)
    
    return cmd


def run_ctrlppcheck(cmd: List[str]) -> int:
    """
    ctrlppcheck 실행
    
    Args:
        cmd: 명령어 리스트
        
    Returns:
        종료 코드
    """
    print(f"실행: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode
    except FileNotFoundError:
        print(f"오류: ctrlppcheck.exe를 찾을 수 없습니다.")
        print(f"경로: {cmd[0]}")
        return 1
    except Exception as e:
        print(f"실행 오류: {e}")
        return 1


def check_update_before_run(skip_update: bool = False) -> bool:
    """
    실행 전 업데이트 확인
    
    Args:
        skip_update: 업데이트 건너뛰기
        
    Returns:
        계속 진행 여부
    """
    if skip_update or check_and_update is None:
        return True
    
    print("\n" + "=" * 60)
    print("CtrlppCheck 업데이트 확인 중...")
    print("=" * 60 + "\n")
    
    try:
        updated, message = check_and_update(auto_check=False)
        print(f"\n{message}")
        return True
    except Exception as e:
        print(f"업데이트 확인 실패: {e}")
        print("계속 진행합니다...")
        return True


def create_parser() -> argparse.ArgumentParser:
    """
    명령줄 인자 파서 생성
    
    Returns:
        argparse 파서
    """
    parser = argparse.ArgumentParser(
        description='CtrlppCheck 실행 래퍼 - 업데이트 확인 후 실행',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 실행
  python ctrlppcheck_wrapper.py script.ctl
  
  # 모든 검사 활성화
  python ctrlppcheck_wrapper.py --all script.ctl
  
  # XML 출력
  python ctrlppcheck_wrapper.py --xml --output-file=result.xml script.ctl
  
  # 업데이트만 확인
  python ctrlppcheck_wrapper.py --check-update
        """
    )
    
    # 업데이트 관련 옵션
    parser.add_argument(
        '--check-update', '-U',
        action='store_true',
        help='업데이트만 확인하고 종료'
    )
    parser.add_argument(
        '--skip-update', '-S',
        action='store_true',
        help='업데이트 확인 건너뛰기'
    )
    
    # CtrlppCheck 옵션
    parser.add_argument(
        '--project-name', '-p',
        default='CodeReview',
        help='WinCC OA 프로젝트 이름 (기본값: CodeReview)'
    )
    parser.add_argument(
        '--enable', '-e',
        help='활성화할 검사 유형 (all, warning, style, performance, portability, information)'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='모든 검사 활성화'
    )
    parser.add_argument(
        '--library', '-L',
        help='라이브러리 설정 파일 경로'
    )
    parser.add_argument(
        '--rule-file', '-R',
        help='규칙 파일 경로'
    )
    parser.add_argument(
        '--naming-rule', '-N',
        help='네이밍 규칙 파일 경로'
    )
    parser.add_argument(
        '--platform',
        choices=['win32A', 'win32W', 'win64', 'unix32', 'unix64', 'native'],
        default='win64',
        help='대상 플랫폼 (기본값: win64)'
    )
    parser.add_argument(
        '--xml', '-x',
        action='store_true',
        help='XML 형식으로 출력'
    )
    parser.add_argument(
        '--output-file', '-o',
        help='출력 파일 경로'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='진행 상황 표시 안 함'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='상세 출력'
    )
    parser.add_argument(
        '--inline-suppr',
        action='store_true',
        help='인라인 억제 활성화'
    )
    parser.add_argument(
        '--inconclusive',
        action='store_true',
        help='불확실한 결과도 보고'
    )
    parser.add_argument(
        '--suppressions',
        help='억제 목록 파일 경로'
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='분석할 파일 또는 디렉토리'
    )
    
    return parser


def main():
    """메인 함수"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 업데이트만 확인
    if args.check_update:
        if check_and_update:
            updated, message = check_and_update(auto_check=False)
            print(f"\n{message}")
            sys.exit(0 if updated else 1)
        else:
            print("업데이트 모듈을 사용할 수 없습니다.")
            sys.exit(1)
    
    # 업데이트 확인
    if not check_update_before_run(args.skip_update):
        sys.exit(1)
    
    # exe 경로 확인
    exe_path = get_ctrlppcheck_exe()
    if not os.path.exists(exe_path):
        print(f"오류: ctrlppcheck.exe를 찾을 수 없습니다.")
        print(f"경로: {exe_path}")
        print("\n먼저 업데이트를 실행하세요:")
        print("  python ctrlppcheck_wrapper.py --check-update")
        sys.exit(1)
    
    # 입력 파일 확인
    if not args.files:
        print("오류: 분석할 파일 또는 디렉토리를 지정하세요.")
        print("\n사용법:")
        print("  python ctrlppcheck_wrapper.py [옵션] 파일또는디렉토리")
        print("\n도움말:")
        print("  python ctrlppcheck_wrapper.py --help")
        sys.exit(1)
    
    # 명령어 구성
    cmd = build_command(args, exe_path)
    
    # 실행
    exit_code = run_ctrlppcheck(cmd)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
