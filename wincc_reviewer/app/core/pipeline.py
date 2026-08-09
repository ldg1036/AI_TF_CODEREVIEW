"""
WinCC OA 코드 리뷰 자동화 도구 — Core Pipeline Orchestrator.

전체 파이프라인 흐름 (TRD §4):
1. 입력 파일 수집 (.ctl, .pnl, .xml)
2. Client/Server Excel 룰 컴파일 및 매핑 로드
3. 입력 정규화 및 파싱 (NormalizationService -> ParsedFile)
4. 타겟 룰셋 라우팅 및 정적 룰 검사 (RuleEngine -> Violation[])
5. 결과 통합 및 JSON/HTML 리포트 내보내기 (ReportBuilder, HTMLReportBuilder)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.input_normalization.service import NormalizationService
from app.core.models import Metrics, ReviewReport, SeverityLevel, Violation
from app.core.parser.base_parser import ParsedFile
from app.core.report.html_report_builder import HTMLReportBuilder
from app.core.report.report_builder import ReportBuilder
from app.core.rules.excel_rule_compiler import ExcelRuleCompiler, RuleCompileResult
from app.core.rules.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


def _resolve_default_output_dir() -> Path:
    cwd = Path.cwd()
    if (cwd / "wincc_reviewer").exists():
        return cwd / "output"
    if cwd.name == "wincc_reviewer" and cwd.parent.exists():
        return cwd.parent / "output"
    return cwd / "output"


@dataclass
class PipelineConfig:
    """파이프라인 실행 설정."""

    input_path: Path | None = None
    rule_source: Path | None = None
    output_dir: Path = field(default_factory=_resolve_default_output_dir)
    no_ai: bool = True  # AI는 기본 OFF (09_구현착수 §7)
    no_autofix: bool = True  # 자동수정은 기본 OFF (TRD §5.5)
    enable_autofix: bool = False  # 옵션: 자동수정 제안 및 적용
    enable_diff: bool = False  # 옵션: WinMerge Diff 뷰어 연동
    target_ruleset: str = "auto"  # 'auto', 'client', 'server'
    max_ai_reviews: int | None = 10  # AI API 요청 건수 제한 (Rate limit 방어)
    use_cache: bool = True  # Phase 2: SHA256 해시 기반 점진적 검사 캐시 활성화
    extract_scripts_only: bool = True  # PNL/XML에서 레이아웃 노드를 제외하고 스크립트만 정제 파싱

    log_level: str = "INFO"


class Pipeline:
    """리뷰 파이프라인 오케스트레이터."""

    SUPPORTED_EXTENSIONS = {".ctl", ".pnl", ".xml"}

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def _collect_files(self) -> list[Path]:
        """입력 경로에서 대상 파일들을 수집합니다."""
        if self.config.input_path is None:
            return []

        input_path = Path(self.config.input_path)
        if not input_path.exists():
            logger.error("입력 경로를 찾을 수 없습니다: %s", input_path)
            return []

        if input_path.is_file():
            return [input_path]

        collected: list[Path] = []
        for file_path in input_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                name_lower = file_path.name.lower()
                if ext in self.SUPPORTED_EXTENSIONS or any(kw in name_lower for kw in [".ctl.", ".pnl.", ".xml.", "_ctl.txt", "_pnl.txt", "_xml.txt"]):
                    collected.append(file_path)
        return sorted(collected)

    def _get_project_config_dir(self) -> Path:
        """기본 config 디렉터리 경로를 반환합니다."""
        # app/core/pipeline.py 기준 루트/config 탐색
        current_file = Path(__file__).resolve()
        # project_root: wincc_reviewer/ -> parent -> 클로드prd/config
        candidate1 = current_file.parent.parent.parent.parent / "config"
        if candidate1.exists():
            return candidate1
        # fallback: ./config
        return Path("./config")

    def _load_rulesets(self) -> dict[str, RuleCompileResult]:
        """Client 및 Server Excel 룰셋을 컴파일하여 반환합니다."""
        config_dir = self._get_project_config_dir()
        rulesets: dict[str, RuleCompileResult] = {}

        # 1. Client 룰셋
        client_excel = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
        client_mapping = config_dir / "legacy_mapping" / "client.yaml"
        if client_excel.exists() and client_mapping.exists():
            try:
                res = ExcelRuleCompiler.compile_rules(client_excel, client_mapping)
                rulesets["client"] = res
            except Exception as e:
                logger.error("Client Excel 룰셋 컴파일 실패: %s", e)

        # 2. Server 룰셋
        server_excel = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
        server_mapping = config_dir / "legacy_mapping" / "server.yaml"
        if server_excel.exists() and server_mapping.exists():
            try:
                res = ExcelRuleCompiler.compile_rules(server_excel, server_mapping)
                rulesets["server"] = res
            except Exception as e:
                logger.error("Server Excel 룰셋 컴파일 실패: %s", e)

        return rulesets

    def _get_cache_file_path(self) -> Path:
        """캐시 파일 경로를 반환합니다."""
        config_dir = self._get_project_config_dir()
        cache_dir = config_dir.parent / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "review_cache.json"

    def _load_review_cache(self) -> dict[str, dict]:
        """디스크에서 기존 리뷰 캐시를 읽어옵니다."""
        if not self.config.use_cache:
            return {}
        cache_path = self._get_cache_file_path()
        if not cache_path.exists():
            return {}
        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug("리뷰 캐시 읽기 실패: %s", e)
            return {}

    def _save_review_cache(self, cache_data: dict[str, dict]) -> None:
        """리뷰 캐시를 디스크에 저장합니다."""
        if not self.config.use_cache:
            return
        cache_path = self._get_cache_file_path()
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug("리뷰 캐시 저장 실패: %s", e)

    @staticmethod
    def _compute_file_sha256(file_path: Path) -> str:
        """파일의 SHA256 해시값을 빠르게 계산합니다."""
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    @staticmethod
    def _dict_to_violation(vd: dict) -> Violation:
        """JSON 딕셔너리로부터 Violation 데이터클래스 객체를 안전하게 복원합니다."""
        from app.core.models import SeverityLevel, ViolationStatus
        vd_copy = dict(vd)
        if isinstance(vd_copy.get("status"), str):
            vd_copy["status"] = ViolationStatus(vd_copy["status"])
        if isinstance(vd_copy.get("severity"), str):
            vd_copy["severity"] = SeverityLevel(vd_copy["severity"])
        return Violation(**vd_copy)

    def run(self) -> ReviewReport:
        """
        전체 파이프라인을 실행합니다.

        Returns:
            통합 리뷰 리포트 (ReviewReport)
        """
        start_time = time.time()
        logger.info("파이프라인 실행 시작: input=%s", self.config.input_path)

        # 1. 대상 파일 수집
        files = self._collect_files()
        logger.info("수집된 대상 파일: %d개", len(files))

        # 2. Excel 룰셋 컴파일
        rulesets = self._load_rulesets()

        # 2.5. 점진적 캐시 로드
        cache_data = self._load_review_cache()
        new_cache_data: dict[str, dict] = {}
        cache_hits = 0

        parsed_files: list[ParsedFile] = []
        all_violations: list[Violation] = []

        # 3. 파일별 정규화, 파싱 및 정적 룰 검사 실행 (캐시 히트 시 스킵)
        for file_path in files:
            str_path = str(file_path.resolve())
            current_sha = self._compute_file_sha256(file_path)

            cached_entry = cache_data.get(str_path)
            if (
                self.config.use_cache
                and cached_entry
                and current_sha
                and cached_entry.get("sha256") == current_sha
            ):
                # 해시 일치 -> 캐시된 결과 즉시 사용
                cache_hits += 1
                from app.core.models import ParseStatus, ParseStatusType
                file_type = cached_entry.get("file_type", "ctl")
                cached_violations_raw = cached_entry.get("violations", [])
                cached_violations = [self._dict_to_violation(vd) for vd in cached_violations_raw]


                parsed_files.append(
                    ParsedFile(
                        file_path=file_path,
                        file_type=file_type,
                        parse_status=ParseStatus(status=ParseStatusType.PARSED),
                        original_sha256=current_sha,
                    )
                )
                all_violations.extend(cached_violations)
                new_cache_data[str_path] = cached_entry
                continue

            # 캐시 미스 -> 실제 파싱 및 정규화 수행
            parsed = NormalizationService.normalize_and_parse(file_path, extract_scripts_only=self.config.extract_scripts_only)
            parsed_files.append(parsed)

            # 적용할 타겟 룰셋 라우팅 (client/server)
            target_ruleset_name = RuleEngine.determine_target_ruleset(file_path)
            compile_result = rulesets.get(target_ruleset_name)

            file_violations: list[Violation] = []
            if compile_result:
                rules = compile_result.rules
                violations = RuleEngine.execute(parsed, rules)
                ast_violations = RuleEngine.execute_ast_cfa(parsed)
                file_violations = RuleEngine.deduplicate_violations(violations + ast_violations)
                all_violations.extend(file_violations)

            if current_sha:
                import dataclasses
                new_cache_data[str_path] = {
                    "sha256": current_sha,
                    "file_type": parsed.file_type,
                    "violations": [dataclasses.asdict(v) for v in file_violations],
                }


        # 변경된 캐시 저장
        self._save_review_cache(new_cache_data)
        if self.config.use_cache and len(files) > 0:
            logger.info("점진적 검사 캐시: 총 %d개 중 %d개 파일 캐시 히트 (재 파싱 스킵)", len(files), cache_hits)


        # 3.5. AI 2차 심층 리뷰 연동 (비동기 병렬 처리)
        ai_provider = None
        if not self.config.no_ai and all_violations:
            import concurrent.futures

            import yaml

            from app.core.ai.domain_rag import WinCCDomainRAG
            from app.core.ai.gemini_provider import GeminiAIProvider
            from app.core.ai.local_provider import LocalAIConfig, LocalAIProvider
            from app.core.ai.provider_base import AIRequest

            ai_provider_type = "gemini"
            local_cfg = LocalAIConfig()

            # settings.yaml을 읽어 AI 프로바이더 결정
            config_dir = self._get_project_config_dir()
            settings_path = config_dir / "settings.yaml"
            if settings_path.exists():
                try:
                    with open(settings_path, "r", encoding="utf_8_sig") as f:
                        settings = yaml.safe_load(f)
                        if isinstance(settings, dict) and "ai" in settings:
                            ai_settings = settings["ai"]
                            ai_provider_type = str(ai_settings.get("provider", "gemini")).lower()
                            if "local_server" in ai_settings:
                                ls = ai_settings["local_server"]
                                env_key = os.environ.get("WINCC_AI_API_KEY") or os.environ.get("LOCAL_AI_API_KEY")
                                local_cfg = LocalAIConfig(
                                    host=str(ls.get("host", "127.0.0.1")),
                                    port=int(ls.get("port", 8000)),
                                    api_key=env_key or str(ls.get("api_key", "")),
                                    endpoint=str(ls.get("endpoint", "/v1/chat/completions")),
                                    model_id=str(ls.get("model_id", "sane_local_llm")),
                                    timeout_seconds=int(ai_settings.get("timeout_seconds", 60)),
                                    max_retries=int(ai_settings.get("max_retries", 3)),
                                    temperature=float(ai_settings.get("temperature", 0.2)),
                                )
                except Exception as e:
                    logger.error("settings.yaml AI 설정 로딩 실패, 기본 Gemini 사용: %s", e)

            if ai_provider_type == "local":
                local_provider_inst = LocalAIProvider(local_cfg)
                if not local_provider_inst.health_check(check_timeout=2.0):
                    logger.warning("로컬 AI 사전 헬스체크 실패 (서버 미가동): 빠른 폴백 모드로 정적 분석만 진행합니다.")
                    ai_provider = None
                else:
                    ai_provider = local_provider_inst
                    logger.info("로컬 AI 사전 헬스체크 성공! (%s:%s, 모델: %s) 2차 심층 리뷰를 실행합니다.", local_cfg.host, local_cfg.port, local_cfg.model_id)
            else:
                ai_provider = GeminiAIProvider()
                logger.info("Gemini AI 2차 심층 리뷰를 병렬 실행합니다 (대상 위반: %d건)", len(all_violations))

            # 심각도(Critical > High > Medium > Low) 우선순위로 정렬하여 AI 리뷰 대상 선정
            severity_order = {
                SeverityLevel.CRITICAL: 0,
                SeverityLevel.HIGH: 1,
                SeverityLevel.MEDIUM: 2,
                SeverityLevel.LOW: 3,
                SeverityLevel.INFO: 4,
            }
            sorted_violations = sorted(
                all_violations,
                key=lambda item: severity_order.get(item.severity, 5)
            )

            max_limit = self.config.max_ai_reviews
            if max_limit is not None and len(sorted_violations) > max_limit:
                targets = sorted_violations[:max_limit]
                unreviewed = sorted_violations[max_limit:]
                for uv in unreviewed:
                    uv.ai_analysis = "[AI UNREVIEWED: max limit exceeded]"
            else:
                targets = sorted_violations

            import threading
            ai_failed_count = 0
            _ai_fail_lock = threading.Lock()

            def _run_single_ai_review(v):
                nonlocal ai_failed_count
                try:
                    enriched_context = WinCCDomainRAG.build_domain_prompt(v.snippet or "", v.message, [v.rule_id])
                    req = AIRequest(
                        code=v.snippet or v.message,
                        rule_id=v.rule_id,
                        context=enriched_context,
                    )
                    ai_resp = ai_provider.review(req)
                    if ai_resp.is_success:
                        v.ai_analysis = ai_resp.content
                    else:
                        with _ai_fail_lock:
                            ai_failed_count += 1
                        v.ai_analysis = "[AI FALLBACK] AI 서버 응답 미수신으로 정적 룰 검사 결과만으로 대체함."
                except Exception as e:
                    with _ai_fail_lock:
                        ai_failed_count += 1
                    logger.warning("[AI FALLBACK] AI 서버 연동 실패. 정적 분석 룰 검사 결과만으로 진행합니다. (원인: %s)", e)
                    v.ai_analysis = "[AI FALLBACK] AI 서버 연동 실패로 정적 룰 검사 결과만으로 대체함."

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                list(executor.map(_run_single_ai_review, targets))

            if ai_failed_count > 0:
                logger.warning("[AI FALLBACK NOTICE] 총 %d건의 위반 항목에서 AI 서버 폴백이 활성화되었습니다.", ai_failed_count)





        # 3.6. 자동수정(AutoFix) 및 WinMerge Diff 연동 (TRD §5.5 & §5.6)
        if self.config.enable_autofix or self.config.enable_diff:
            from app.core.autofix.engine import AutofixEngine
            from app.core.diff.winmerge_runner import WinMergeRunner

            autofix_engine = AutofixEngine(enabled=self.config.enable_autofix)
            diff_runner = WinMergeRunner()

            for parsed_file in parsed_files:
                if not parsed_file.file_path or not parsed_file.file_path.exists():
                    continue
                file_violations = [v for v in all_violations if str(v.file_id) == str(parsed_file.file_path)]
                if not file_violations:
                    continue

                if self.config.enable_autofix:
                    fixed_path, success = autofix_engine.apply_autofix(parsed_file.file_path, file_violations)
                    if success and self.config.enable_diff:
                        diff_result = diff_runner.compare(parsed_file.file_path, fixed_path)
                        if diff_result.is_success:
                            logger.debug("Diff 추출 성공: %s (%d건 변경)", parsed_file.file_path, len(diff_result.changes))

        # 3.7. AI 허위 경보(False Positive) 필터링 및 신뢰도 점수 산출
        try:
            from app.core.ai.false_positive_filter import FalsePositiveFilter
            parsed_files_map = {str(pf.file_path): pf for pf in parsed_files if pf.file_path}
            for pf in parsed_files:
                if pf.file_path:
                    parsed_files_map[pf.file_path.name] = pf
            FalsePositiveFilter.filter_violations(
                all_violations,
                parsed_files_map=parsed_files_map,
                ai_provider=ai_provider if not self.config.no_ai else None,
            )
        except Exception as exc:
            logger.warning("AI 허위 경보(False Positive) 필터링 실행 중 오류: %s", exc)

        end_time = time.time()

        total_ms = int((end_time - start_time) * 1000)

        # 4. 실행 지표 수집
        metrics = Metrics()
        metrics.timings_ms["total"] = total_ms
        metrics.file_count = len(parsed_files)
        metrics.violation_count = len(all_violations)
        metrics.cache_hits["files"] = cache_hits
        metrics.cache_misses["files"] = len(files) - cache_hits

        run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        rule_source_name = str(self.config.rule_source or "Client/Server Excel Config")

        # 5. 결과 통합 리포트 생성
        report = ReportBuilder.build_report(
            run_id=run_id,
            rule_source=rule_source_name,
            parsed_files=parsed_files,
            violations=all_violations,
            metrics=metrics,
        )

        # 5.5. 체크리스트 적용성 매핑 정보(ChecklistApplicability) 탑재
        try:
            from app.core.rules.applicability_mapper import ApplicabilityMapper
            config_dir = self._get_project_config_dir()
            ca_list = []
            for profile_name in ["client.yaml", "server.yaml"]:
                profile_path = config_dir / "legacy_mapping" / profile_name
                if profile_path.exists():
                    app_report = ApplicabilityMapper.map_profile(profile_path)
                    ca_items = ApplicabilityMapper.to_checklist_applicability(app_report)
                    ca_list.extend(ca_items)
            if ca_list:
                report.checklist_applicability = ca_list
                logger.info("체크리스트 적용성 매핑 정보 %d건 탑재 완료", len(ca_list))
        except Exception as e:
            logger.warning("체크리스트 적용성 매핑 탑재 중 예외 발생: %s", e)


        # 6. JSON & HTML 리포트 출력 디렉터리 저장
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / f"{run_id}_review_report.json"
        html_path = output_dir / f"{run_id}_review_report.html"

        ReportBuilder.export_json(report, json_path)
        HTMLReportBuilder.export_html(report, html_path)

        logger.info("리포트 저장 완료: JSON=%s, HTML=%s", json_path, html_path)
        return report

    def cancel(self) -> None:
        """실행 중인 파이프라인을 취소합니다."""
        logger.info("파이프라인 취소가 요청되었습니다.")
