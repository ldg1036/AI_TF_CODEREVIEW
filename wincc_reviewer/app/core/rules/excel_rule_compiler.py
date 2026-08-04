"""
Excel Rule Compiler (08_ADR_실제_Excel_양식_계약.md & 09_구현착수_패키지_계약.md §5 기준).

Excel 파서(ExcelRuleLoader)의 파싱 결과와 승인된 레거시 매핑 프로파일(legacy_mapping_profile)을
검증·조합하여 내부 RuleDefinition[]으로 컴파일합니다.

컴파일 정책:
1. v2.0 파일의 category/subcategory/check_item/condition을 보존하고 source_key를 대조합니다.
2. 매핑되지 않은 항목이나 rule_ids가 없는 항목은 자동 PASS가 아니라 MANUAL_REVIEW 상태로 분류합니다.
3. 매핑 프로파일 미등록 source_key, 중복 source_key 발생 시 ExcelCompileError를 발생시킵니다.
4. Excel SHA256과 프로파일 버전을 결과 메타데이터에 기록합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.models import CheckerType, RuleDefinition, SeverityLevel
from app.core.rules.excel_rule_loader import ExcelRuleLoader, RawExcelRow


class ExcelCompileError(Exception):
    """Excel 룰 컴파일 오류 예외."""

    pass


@dataclass
class RuleCompileResult:
    """Excel 룰 컴파일 결과."""

    rules: list[RuleDefinition]
    file_sha256: str
    profile_version: str
    total_count: int
    manual_review_count: int
    automated_count: int
    unmapped_count: int = 0


class ExcelRuleCompiler:
    """Excel 체크리스트 및 매핑 프로파일 컴파일러."""

    @classmethod
    def compile_rules(
        cls,
        excel_path: Path,
        mapping_profile_path: Path,
        verify_sha256: bool = True,
    ) -> RuleCompileResult:
        """
        Excel 파일과 레거시 매핑 프로파일 YAML을 읽어 RuleDefinition 목록으로 컴파일합니다.

        Args:
            excel_path: Client 또는 Server Excel 결과서 파일 경로
            mapping_profile_path: legacy_mapping (client.yaml 또는 server.yaml) 경로
            verify_sha256: Excel SHA256 해시 검증 여부 (기본 True)

        Returns:
            RuleCompileResult

        Raises:
            ExcelCompileError: 컴파일 실패 시 (파일 누락, SHA 불일치, 매핑 누락, 중복 key 등)
        """
        excel_path = Path(excel_path)
        mapping_path = Path(mapping_profile_path)

        if not mapping_path.exists():
            raise ExcelCompileError(f"매핑 프로파일 파일을 찾을 수 없습니다: {mapping_path}")

        # 1. Excel 파싱
        try:
            raw_rows, file_sha256 = ExcelRuleLoader.load_excel(excel_path)
        except Exception as e:
            raise ExcelCompileError(f"Excel 파일 파싱 실패: {e}") from e

        # 2. 매핑 프로파일 YAML 로드
        try:
            with open(mapping_path, encoding="utf-8") as f:
                profile = yaml.safe_load(f)
        except Exception as e:
            raise ExcelCompileError(f"매핑 프로파일 읽기 실패 ({mapping_path}): {e}") from e

        profile_version = str(profile.get("profile_version", "1.0.0"))
        expected_sha256 = profile.get("source_excel_sha256")

        # 3. SHA256 검증
        if verify_sha256 and expected_sha256 and expected_sha256 != file_sha256:
            raise ExcelCompileError(
                f"Excel SHA256 해시 불일치: 프로파일({expected_sha256[:8]}...) != 실제({file_sha256[:8]}...)"
            )

        # 4. 매핑 엔트리 사전 구축 및 중복 검증
        entries_list = profile.get("entries", [])
        mapping_dict: dict[str, dict[str, Any]] = {}
        for entry in entries_list:
            skey = entry.get("source_key")
            if not skey:
                raise ExcelCompileError("매핑 프로파일 항목에 source_key가 없습니다.")
            if skey in mapping_dict:
                raise ExcelCompileError(f"매핑 프로파일 내 중복된 source_key 존재: {skey}")
            mapping_dict[skey] = entry

        # 5. RawExcelRow -> RuleDefinition 변환
        compiled_rules: list[RuleDefinition] = []
        manual_review_count = 0
        automated_count = 0
        unmapped_count = 0

        for idx, row in enumerate(raw_rows):
            entry = mapping_dict.get(row.source_key)

            if entry is None:
                # 매핑 프로파일에 등록되지 않은 항목 발생 시 컴파일 에러
                unmapped_count += 1
                raise ExcelCompileError(
                    f"매핑 프로파일에 등록되지 않은 항목 존재 (row {row.row_index}): {row.source_key}"
                )

            automation_mode = entry.get("automation_mode", "manual")
            rule_ids = entry.get("rule_ids", [])
            checker_type_str = entry.get("checker_type", "manual")

            # Enum 체커 타입 정규화
            try:
                checker_type = CheckerType(checker_type_str)
            except ValueError:
                checker_type = CheckerType.MANUAL

            # rule_ids가 없거나 automation_mode가 manual인 경우 MANUAL_REVIEW로 분류
            is_manual = automation_mode == "manual" or not rule_ids or checker_type == CheckerType.MANUAL

            if is_manual:
                manual_review_count += 1
                rule_id = f"MANUAL-{idx+1:03d}" if not rule_ids else str(rule_ids[0])
                rule_def = RuleDefinition(
                    rule_id=rule_id,
                    source_key=row.source_key,
                    file_types=["CTL", "PNL"],
                    checker_type=CheckerType.MANUAL,
                    enabled=True,
                    rule_version=profile_version,
                    category=row.category,
                    subcategory=row.subcategory,
                    check_item=row.check_item,
                    condition=row.condition,
                    severity=SeverityLevel.INFO,
                    message=f"[MANUAL_REVIEW] {row.check_item}: {row.condition}",
                )
            else:
                automated_count += 1
                rule_id = str(rule_ids[0])
                rule_def = RuleDefinition(
                    rule_id=rule_id,
                    source_key=row.source_key,
                    file_types=entry.get("file_types", ["CTL", "PNL"]),
                    checker_type=checker_type,
                    enabled=entry.get("enabled", True),
                    rule_version=profile_version,
                    category=row.category,
                    subcategory=row.subcategory,

                    check_item=row.check_item,
                    condition=row.condition,
                    severity=SeverityLevel(entry.get("severity", "Medium")),
                    checker_key=entry.get("checker_key", ""),
                    pattern=entry.get("pattern", ""),
                    message=entry.get("message", f"[{rule_id}] 위반: {row.check_item}"),
                    fix_hint=entry.get("fix_hint", ""),
                    autofix_allowed=entry.get("autofix_allowed", False),
                )

            compiled_rules.append(rule_def)

        return RuleCompileResult(
            rules=compiled_rules,
            file_sha256=file_sha256,
            profile_version=profile_version,
            total_count=len(compiled_rules),
            manual_review_count=manual_review_count,
            automated_count=automated_count,
            unmapped_count=unmapped_count,
        )
