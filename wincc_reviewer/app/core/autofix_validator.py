"""
자동 수정(Autofix) 패치 구문의 샌드박스 AST 유효성 사전 검증 엔진.
제안된 수정 스크립트를 임시 샌드박스 공간에 가상 저장하여 파싱 문법 유효성(Syntax Validation)을 검증하고,
구문 파손(PARSE_FAILED) 감지 시 자동으로 수정 패치를 롤백하여 원본의 100% 안전성을 가드합니다.
"""

import logging
import tempfile
from pathlib import Path
from app.core.models import ParseStatusType
from app.core.parser.ctl_parser import CTLParser

logger = logging.getLogger(__name__)


class AutofixValidator:
    """자동 수정 코드 패치 샌드박스 안전 검증기."""

    @classmethod
    def validate_patch(cls, original_file_path: Path, modified_content: str) -> tuple[bool, str]:
        """
        수정된 소스 코드가 문법적으로 안전한지 샌드박스 파싱 검증을 수행합니다.

        Returns:
            (is_valid: bool, reason: str)
        """
        if not modified_content or not modified_content.strip():
            return False, "수정 코드가 비어 있습니다."

        try:
            with tempfile.TemporaryDirectory(prefix="autofix_sandbox_") as tmp_dir:
                tmp_path = Path(tmp_dir) / original_file_path.name
                tmp_path.write_text(modified_content, encoding="utf-8")

                # 파서를 통한 구문 파싱 검증
                parser = CTLParser()
                parsed = parser.parse(tmp_path)

                if parsed.parse_status.status == ParseStatusType.PARSE_FAILED:
                    logger.warning("Autofix 패치 샌드박스 검증 실패 (구문 파손): %s", parsed.parse_status.message)
                    return False, f"구문 파손 감지: {parsed.parse_status.message}"

                return True, "샌드박스 AST 구문 검증 성공"
        except Exception as e:
            logger.error("샌드박스 검증 중 예외 발생: %s", e)
            return False, f"검증 예외: {e}"
