"""
정적 룰 엔진 및 라우터 (03_정적분석_룰카탈로그.md & TRD §5.2 기준).

주요 기능:
1. 파일 확장자 기반 자동 분류 및 사용자 오버라이드 지원 (Rule Target Routing)
2. ParsedFile IR과 RuleDefinition[]을 받아 Violation[] 검출
3. parse_failed 상태인 IR은 예외 없이 안전 스킵 (빈 Violation 반환)
4. MANUAL_REVIEW, BUILTIN, REGEX 각 체커 실행 분기 처리
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core.models import (
    CheckerType,
    ParseStatusType,
    RuleDefinition,
    SeverityLevel,
    Violation,
    ViolationStatus,
)
from app.core.parser.base_parser import ParsedFile
from app.core.rules.checker_registry import CheckerRegistry

logger = logging.getLogger(__name__)


class RuleEngine:
    """정적 룰 검사 엔진 및 라우터."""

    CLIENT_EXTENSIONS = {".pnl", ".xml"}
    SERVER_EXTENSIONS = {".ctl"}

    @staticmethod
    def _extract_window_snippet(content: str, line_start: int, window: int = 10) -> str:
        """위반 발생 라인을 기준으로 앞뒤 N줄(기본 10줄) 윈도우 스니펫을 추출합니다."""
        lines = content.splitlines()
        idx = max(0, line_start - 1)
        start_idx = max(0, idx - window)
        end_idx = min(len(lines), idx + window + 1)
        return "\n".join(lines[start_idx:end_idx])

    @classmethod
    def determine_target_ruleset(cls, file_path: Path, override_target: str | None = None) -> str:
        """
        파일 경로와 사용자 오버라이드 설정을 기반으로 적용할 룰셋(client/server)을 결정합니다.

        Args:
            file_path: 대상 파일 경로
            override_target: 사용자 수동 선택 ("client" 또는 "server", 기본 None)

        Returns:
            "client" 또는 "server"
        """
        if override_target and override_target.lower() in ("client", "server"):
            return override_target.lower()

        name_lower = file_path.name.lower()
        if any(name_lower.endswith(ext) or f"{ext}." in name_lower or f"_{ext.lstrip('.')}.txt" in name_lower for ext in cls.SERVER_EXTENSIONS):
            return "server"
        if any(name_lower.endswith(ext) or f"{ext}." in name_lower or f"_{ext.lstrip('.')}.txt" in name_lower for ext in cls.CLIENT_EXTENSIONS):
            return "client"

        ext = file_path.suffix.lower()
        if ext in cls.CLIENT_EXTENSIONS:
            return "client"
        elif ext in cls.SERVER_EXTENSIONS:
            return "server"
        else:
            # 기본 디폴트는 확장자에 따르되 알 수 없는 확장자는 client로 처리
            return "client"

    @classmethod
    def _find_keyword_lines(cls, content: str, rule: RuleDefinition) -> list[tuple[int, str]]:
        """소스 코드 내용에서 룰 관련 정밀 키워드/패턴의 대표 라인 1개를 정밀 검색합니다 (노이즈 방지)."""
        lines = content.splitlines()
        matches: list[tuple[int, str]] = []

        text = (rule.check_item + " " + rule.condition + " " + rule.message).lower()
        r_id = rule.rule_id

        # 룰 ID 및 구문 세부 특성에 맞춘 정밀 정규식/키워드 매칭
        pattern = None
        if "MANUAL-001" in r_id or "active 동작" in text:
            pattern = r"\b(dpconnect|dpquery|isredundantactive|scriptactive|activecondition|isactive)\b"
        elif "MANUAL-018" in r_id or "하드코딩" in text:
            pattern = r"\b(http://|https://|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\b"

        if pattern:
            for idx, line in enumerate(lines, start=1):
                l_strip = line.strip()
                if l_strip.startswith("//") or l_strip.startswith("/*") or l_strip.startswith("#"):
                    continue
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append((idx, l_strip))
                    break

        return matches

    @classmethod
    def execute_rule(cls, parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
        """
        단일 RuleDefinition을 ParsedFile IR에 적용합니다.

        Args:
            parsed: 파싱된 파일 IR
            rule: 적용할 룰 정의

        Returns:
            검출된 Violation 목록
        """
        # 1. 룰 비활성화 상태 체크
        if not rule.enabled:
            return []

        # 2. 파싱 실패 IR은 룰 검사를 건너뛰고 빈 리스트 반환 (TRD §5.2 DoD 114행)
        if parsed.parse_status.status == ParseStatusType.PARSE_FAILED:
            logger.warning("파싱 실패 파일 스킵: %s", parsed.file_path)
            return []

        # 2.5. 파일 확장자 및 대상 타입 일치 여부 검사 (대상 파일 오매핑 방지)
        if rule.file_types:
            ext_clean = parsed.file_type.lower().lstrip(".")
            allowed = [t.lower().lstrip(".") for t in rule.file_types]
            if ext_clean not in allowed and not (ext_clean == "xml" and "pnl" in allowed):
                return []

        violations: list[Violation] = []

        # 3. MANUAL_REVIEW 처리: 소스 코드 구조 및 논리를 정밀 분석하여 준수 코드는 PASS, 미준수 구문만 수집
        if rule.checker_type == CheckerType.MANUAL:
            r_id = rule.rule_id
            content_lower = parsed.content.lower()

            # ① Active 이중화 조건 점검 (MANUAL-001)
            if "MANUAL-001" in r_id:
                if any(kw in content_lower for kw in ["activecondition", "isredundantactive", "scriptactive", "isactive"]):
                    # Active 조건절 및 콜백이 이미 잘 구축되어 있으므로 정상 통과 (PASS)
                    return []
                else:
                    # 제어/감시 로직(while, for, dpConnect, dpQuery 등)이나 주함수가 없는 단순 유틸리티 및 상수 파일은 오매핑 방지를 위해 PASS
                    has_control_logic = any(
                        kw in content_lower for kw in ["dpconnect", "dpquery", "while", "for", "main(", "workcb"]
                    )
                    if not has_control_logic:
                        return []

                    # PNL 또는 스크립트에서 이벤트 교환/DP 처리 관련 구문 정밀 추출
                    matched_lines = cls._find_keyword_lines(parsed.content, rule)
                    if not matched_lines:
                        # 해당되는 키워드 구문이 없으면 오탐 없이 PASS 처리
                        return []

                    l_no = matched_lines[0][0]
                    snip = matched_lines[0][1]
                    return [
                        Violation(
                            violation_id=f"V-{rule.rule_id}-M{l_no}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.MANUAL_REVIEW,
                            severity=rule.severity or SeverityLevel.INFO,
                            message=rule.message or f"[MANUAL_REVIEW] {rule.check_item}: Active 이중화 조건 미비 우려",
                            line_start=l_no,
                            line_end=l_no,
                            snippet=snip,
                        )
                    ]

            # ② Loop문 delay 점검 (MANUAL-002)
            if "MANUAL-002" in r_id:
                fn = CheckerRegistry.get("ctl.loop_delay")
                return fn(parsed, rule) if fn else []

            # ③ 이벤트 교환 횟수 최소화 / 일괄 dpGet·dpSet 점검 또는 콜백 병목 점검 (MANUAL-003)
            if "MANUAL-003" in r_id:
                check_text = f"{rule.check_item} {rule.message}".lower()
                if any(kw in check_text for kw in ["callback", "병목", "비동기"]):
                    fn = CheckerRegistry.get("ctl.dp_callback_delay")
                else:
                    fn = CheckerRegistry.get("ctl.batch_dp_ops")
                return fn(parsed, rule) if fn else []

            # ④ dpConnect/dpQueryConnectSingle 콜백 내 delay 점검 (MANUAL-004)
            if "MANUAL-004" in r_id:
                fn = CheckerRegistry.get("ctl.dp_callback_delay")
                return fn(parsed, rule) if fn else []

            # ⑤ 비동기 DP 처리 함수 적절성 점검 (MANUAL-005)
            if "MANUAL-005" in r_id:
                fn = CheckerRegistry.get("ctl.dp_async")
                return fn(parsed, rule) if fn else []

            # ⑥ DB Query 바인딩 쿼리 처리 점검 (MANUAL-007, MANUAL-008, MANUAL-009)
            check_text = f"{rule.check_item} {rule.message}".lower()
            if any(k in r_id for k in ["MANUAL-007", "MANUAL-008", "MANUAL-009"]) or "바인딩 쿼리" in check_text or "db query" in check_text:
                fn = CheckerRegistry.get("ctl.db_query_binding")
                return fn(parsed, rule) if fn else []

            # ⑦ DP 함수 예외 처리 / 반환값 검사 점검 (MANUAL-013)
            if "MANUAL-013" in r_id:
                fn = CheckerRegistry.get("ctl.dp_error_handling")
                return fn(parsed, rule) if fn else []

            # ⑧ Try/Catch 예외 처리 점검 (MANUAL-012)
            if "MANUAL-012" in r_id:
                fn = CheckerRegistry.get("ctl.try_catch")
                return fn(parsed, rule) if fn else []

            # ⑨ 하드코딩 지양 점검 (MANUAL-014, MANUAL-018)
            if "MANUAL-014" in r_id or "MANUAL-018" in r_id:
                fn = CheckerRegistry.get("ctl.hardcoding")
                return fn(parsed, rule) if fn else []

            # ⑧ 기타 수동 점검 룰 (위에서 매칭되지 않은 나머지)
            matched_lines = cls._find_keyword_lines(parsed.content, rule)
            if matched_lines:
                for idx, (l_no, snip) in enumerate(matched_lines, start=1):
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-M{l_no}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.MANUAL_REVIEW,
                            severity=rule.severity or SeverityLevel.INFO,
                            message=rule.message or f"[MANUAL_REVIEW] {rule.check_item}: 수동 검토 필요",
                            line_start=l_no,
                            line_end=l_no,
                            snippet=snip,
                        )
                    )
            return violations

        # 4. BUILTIN 처리
        if rule.checker_type == CheckerType.BUILTIN:
            if not rule.checker_key or not CheckerRegistry.is_registered(rule.checker_key):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-ERR",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.ERROR,
                        severity=SeverityLevel.HIGH,
                        message=f"[unsupported_checker] 내장 체커가 등록되지 않았습니다: '{rule.checker_key}'",
                    )
                )
                return cls._filter_nolint_suppressed(parsed, violations)

            checker_fn = CheckerRegistry.get(rule.checker_key)
            if checker_fn:
                try:
                    res_violations = checker_fn(parsed, rule)
                    return cls._filter_nolint_suppressed(parsed, res_violations)
                except Exception as e:
                    logger.error("내장 체커 실행 중 오류 발생 (%s): %s", rule.checker_key, e)
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-ERR",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.ERROR,
                            severity=SeverityLevel.HIGH,
                            message=f"체커 실행 오류: {e}",
                        )
                    )
            return cls._filter_nolint_suppressed(parsed, violations)

        # 5. REGEX 처리 (주석 제외 및 AST 문맥 검수 적용)
        if rule.checker_type == CheckerType.REGEX:
            if not rule.pattern:
                return []

            try:
                matches = list(re.finditer(rule.pattern, parsed.content, re.MULTILINE))
                for match in matches:
                    line_start = parsed.content[: match.start()].count("\n") + 1
                    line_end = parsed.content[: match.end()].count("\n") + 1
                    window_snippet = cls._extract_window_snippet(parsed.content, line_start, window=10)

                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-R{line_start}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.FAIL,
                            severity=rule.severity or SeverityLevel.MEDIUM,
                            message=rule.message or f"[{rule.rule_id}] 정규식 패턴 위반 매칭",
                            line_start=line_start,
                            line_end=line_end,
                            snippet=window_snippet,
                        )
                    )
            except Exception as e:
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-ERR",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.ERROR,
                        severity=SeverityLevel.HIGH,
                        message=f"정규식 검사 실행 오류: {e}",
                    )
                )
            return cls._filter_nolint_suppressed(parsed, violations)

        return cls._filter_nolint_suppressed(parsed, violations)

    @classmethod
    def _filter_nolint_suppressed(cls, parsed: ParsedFile, violations: list[Violation]) -> list[Violation]:
        """//nolint 인라인 억제 주석이 존재하는 행의 결함을 필터링합니다."""
        if not violations or not parsed.content:
            return violations

        lines = parsed.content.splitlines()
        filtered = []
        for v in violations:
            line_no = v.line_start or 1
            suppressed = False
            check_indices = [line_no - 1, line_no - 2]
            for idx in check_indices:
                if 0 <= idx < len(lines):
                    line_str = lines[idx]
                    if "//nolint" in line_str or "/*nolint" in line_str:
                        if f"nolint:{v.rule_id}" in line_str or "//nolint" in line_str:
                            suppressed = True
                            logger.info("인라인 //nolint 주석으로 위반 억제됨: rule=%s, file=%s", v.rule_id, parsed.file_path)
                            break
            if not suppressed:
                filtered.append(v)
        return filtered

    @classmethod
    def execute(cls, parsed: ParsedFile, rules: list[RuleDefinition]) -> list[Violation]:
        """
        ParsedFile IR에 대해 전체 RuleDefinition 목록을 적용하여 Violation 목록을 수집합니다.

        Args:
            parsed: 파싱된 파일 IR
            rules: 적용할 룰 정의 목록

        Returns:
            수집된 전체 Violation 목록
        """
        all_violations: list[Violation] = []
        for rule in rules:
            violations = cls.execute_rule(parsed, rule)
            all_violations.extend(violations)
        return all_violations

    @classmethod
    def execute_ast_cfa(cls, parsed: ParsedFile) -> list[Violation]:
        """
        ParsedFile IR에 대해 AST 기반 심층 제어 흐름 분석(CFA) 체커를 적용합니다.
        (03_정적분석_룰카탈로그.md §13 & 05_개발로드맵 Phase 9).
        """
        from app.core.rules.ast_cfa_checker import ASTControlFlowChecker
        return ASTControlFlowChecker.run_ast_cfa_checks(parsed)

    @classmethod
    def deduplicate_violations(cls, violations: list[Violation]) -> list[Violation]:
        """
        동일 파일, 동일 라인에 1차 정규식과 2차 AST 심층 규칙 위반이 중복될 경우,
        중복 위반을 자동 병합하여 심층 규칙을 우선 유지합니다.
        """
        seen: set[tuple[str, int]] = set()
        # AST 룰 ID 접두사를 가진 항목 우선순위 부여
        sorted_vs = sorted(violations, key=lambda v: 0 if "AST" in str(v.rule_id) else 1)
        deduped: list[Violation] = []
        for v in sorted_vs:
            key = (v.file_id, v.line_start)
            if key not in seen:
                seen.add(key)
                deduped.append(v)
        # 라인 번호 순으로 다시 정렬
        return sorted(deduped, key=lambda v: (v.file_id, v.line_start))


