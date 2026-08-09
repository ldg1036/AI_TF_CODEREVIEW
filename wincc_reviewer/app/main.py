"""
WinCC OA 코드 리뷰 자동화 도구 — CLI 진입점.

표준 실행 명령 (09_구현착수_패키지_계약.md §3):
    python -m app.main --help
    python -m app.main --input <file-or-directory>
    python -m app.main --input <file> --rule-source <client-or-server.xlsx> --no-ai
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
from pathlib import Path

from app import __version__
from app.core.pipeline import Pipeline, PipelineConfig

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성합니다."""
    parser = argparse.ArgumentParser(
        prog="wincc-reviewer",
        description="WinCC OA 코드 리뷰 자동화 도구: 정적룰 기반 1차 검사 + AI 기반 2차 심층 리뷰",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "사용 예시:\n"
            "  python -m app.main --help\n"
            "  python -m app.main --input ./src/\n"
            "  python -m app.main --input file.ctl --rule-source server.xlsx --no-ai\n"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--input",
        type=Path,
        help="검사 대상 파일 또는 디렉터리 경로",
    )

    parser.add_argument(
        "--rule-source",
        type=Path,
        help="룰 원천 Excel 파일 경로 (Client 또는 Server 결과서)",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        default=False,
        help="AI 리뷰를 비활성화하고 정적 룰 검사만 수행 (기본: AI 비활성)",
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        default=False,
        help="pywebview 기반 데스크톱 GUI 모드 실행",
    )

    parser.add_argument(
        "--autofix",
        action="store_true",
        default=False,
        help="위반 코드 자동수정(AutoFix) 제안 생성",
    )

    parser.add_argument(
        "--diff",
        action="store_true",
        default=False,
        help="WinMerge 기반 원본/수정본 Diff 생성",
    )

    parser.add_argument(
        "--suggest-rules",
        action="store_true",
        default=False,
        help="AI 오탐 피드백 로그 기반 엑셀 룰 카탈로그 자율 최적화 추천 리포트 출력",
    )


    parser.add_argument(
        "--max-ai-reviews",
        type=int,
        default=10,
        help="AI 2차 심층 리뷰 최대 수행 위반 건수 (기본: 10, 0: 전체)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="결과 출력 디렉터리 (기본: ./output/)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="로그 레벨 (기본: INFO)",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="설정 파일 경로 (기본: config/settings.yaml)",
    )

    parser.add_argument(
        "--fail-on-severity",
        choices=["Critical", "High", "Medium", "Low", "Info", "critical", "high", "medium", "low", "info"],
        help="지정한 심각도 이상의 결함이 존재하면 exit code 1로 종료합니다.",
    )

    parser.add_argument(
        "--post-pr-comment",
        choices=["github", "gitlab"],
        help="리뷰 위반 항목을 GitHub PR 또는 GitLab MR 인라인 코멘트 JSON 페이로드 파일로 내보냅니다.",
    )

    parser.add_argument(
        "--diff-only",
        action="store_true",
        default=False,
        help="git diff 변경 라인 범위 내 위반 결함만 수집하여 리뷰합니다.",
    )

    return parser


def _setup_logging(level: str, log_dir: Path | None = None) -> None:
    """로깅을 설정합니다. 콘솔 및 파일 핸들러(로테이션) 포함."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stderr),
    ]

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "wincc_reviewer.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            handlers.append(file_handler)
        except Exception as e:
            sys.stderr.write(f"로그 파일 생성 실패: {e}\n")

    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        handlers=handlers,
        force=True,
    )


def _get_default_output_dir() -> Path:
    """CWD 위치와 무관하게 최상위 프로젝트 output 디렉터리를 탐색 및 결정합니다."""
    cwd = Path.cwd()
    if (cwd / "wincc_reviewer").exists():
        return cwd / "output"
    if cwd.name == "wincc_reviewer" and cwd.parent.exists():
        return cwd.parent / "output"
    return cwd / "output"


def main(argv: list[str] | None = None) -> int:
    """
    메인 진입점.

    Returns:
        종료 코드 (0: 성공, 1: 오류)
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    output_dir = args.output or _get_default_output_dir()
    log_dir = output_dir / "logs"
    _setup_logging(args.log_level, log_dir=log_dir)

    if args.suggest_rules:
        logger.info("AI 오탐 피드백 기반 룰 카탈로그 자율 최적화 추천 엔진을 실행합니다...")
        from app.core.ai.rule_optimizer import RuleOptimizer

        optimizer = RuleOptimizer()
        suggestions = optimizer.analyze_and_suggest(min_fp_threshold=2)
        report_md = optimizer.render_markdown_report(suggestions)
        print("\n" + report_md)
        return 0

    # 09_구현착수_패키지_계약.md §3: GUI는 python -m app.main의 기본 모드로 실행
    if args.gui or args.input is None:
        logger.info("pywebview 데스크톱 GUI 모드를 시작합니다. (CLI 도움말은 --help 참조)")
        try:
            from app.ui.app import launch_ui
            launch_ui()
            return 0
        except Exception as e:
            logger.error("GUI 모드 실행 실패 (CLI 사용법: python -m app.main --help): %s", e)
            return 1

    # 파이프라인 설정 구성
    output_dir = args.output or _get_default_output_dir()
    config = PipelineConfig(
        input_path=args.input,
        rule_source=args.rule_source,
        output_dir=output_dir,
        no_ai=args.no_ai,
        enable_autofix=args.autofix,
        enable_diff=args.diff,
        max_ai_reviews=None if args.max_ai_reviews == 0 else args.max_ai_reviews,
        log_level=args.log_level,
    )

    logger.info("입력 경로: %s", args.input)

    try:
        pipeline = Pipeline(config)
        report = pipeline.run()
        logger.info("코드 리뷰 성공적으로 완료. 리포트 저장 위치: %s", output_dir)

        if args.fail_on_severity:
            sev_map = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            target_rank = sev_map.get(str(args.fail_on_severity).lower(), 1)
            for v in getattr(report, "violations", []):
                v_sev = str(getattr(v, "severity", "info")).lower()
                v_rank = sev_map.get(v_sev, 4)
                if v_rank <= target_rank:
                    logger.error("[BUILD FAIL] 지정 임계치(%s) 이상 심각도 결함 감지로 exit code 1 반환", args.fail_on_severity)
                    return 1

        # CLI 성공 리포트 요약 출력
        print("\n==========================================")
        print("  WinCC OA Code Review Completed")
        print("==========================================")
        print(f" - Run ID: {report.run_id}")
        print(f" - Files Scanned: {report.metrics.file_count}")
        print(f" - Violations Found: {report.metrics.violation_count}")
        print(f" - Parse Errors: {len(report.errors)}")
        print(f" - JSON Report: {output_dir / f'{report.run_id}_review_report.json'}")
        print(f" - HTML Report: {output_dir / f'{report.run_id}_review_report.html'}")
        print("==========================================\n")
        return 0

    except Exception as e:
        logger.error("파이프라인 실행 중 오류 발생: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
