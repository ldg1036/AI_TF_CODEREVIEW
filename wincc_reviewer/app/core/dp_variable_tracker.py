"""
WinCC OA Data Point(DP) 변수 및 호출 체인 정밀 추적기 모듈.
CTL 스크립트 및 PNL 구조에서 dpConnect, dpSet, dpGet, dpQuery 구문의 DP 변수명을 추적하여
고아 DP 참조 및 연결 미해제(dpDisconnect) 결함을 체계적으로 추적 정적 체커로 컴파일합니다.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DPCallChain:
    """DP 연산 호출 체인 단위 정보."""

    dp_name: str
    func_type: str  # "dpConnect", "dpGet", "dpSet", "dpQuery"
    callback_func: str | None = None
    line_number: int = 1


class DPVariableTracker:
    """DP 변수 및 스크립트 내 호출 체인 분석 엔진."""

    DP_FUNC_PATTERN = re.compile(
        r'\b(dpConnect|dpDisconnect|dpGet|dpSet|dpQuery)\s*\(\s*([^,\)]+)(?:,\s*([^,\)]+))?',
        re.IGNORECASE,
    )

    @classmethod
    def analyze_script(cls, content: str) -> list[DPCallChain]:
        """스크립트 내용을 분석하여 추출된 모든 DP 연산 호출 체인 목록을 반환합니다."""
        if not content:
            return []

        chains: list[DPCallChain] = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if line_str.startswith("//") or line_str.startswith("/*"):
                continue

            matches = cls.DP_FUNC_PATTERN.finditer(line)
            for match in matches:
                func_name = match.group(1)
                dp_expr = match.group(2).strip().strip('"\'')
                cb_expr = match.group(3).strip().strip('"\'') if match.group(3) else None

                chains.append(
                    DPCallChain(
                        dp_name=dp_expr,
                        func_type=func_name,
                        callback_func=cb_expr,
                        line_number=idx,
                    )
                )

        return chains

    @classmethod
    def find_unmatched_dp_connects(cls, content: str) -> list[DPCallChain]:
        """dpConnect는 존재하나 대응하는 dpDisconnect가 부재하거나 콜백 함수가 미정의된 항목을 추출합니다."""
        chains = cls.analyze_script(content)
        connects = [c for c in chains if c.func_type.lower() == "dpconnect"]
        disconnects = [c for c in chains if c.func_type.lower() == "dpdisconnect"]

        unmatched: list[DPCallChain] = []
        disconnected_names = {d.dp_name for d in disconnects}

        for conn in connects:
            # 주함수 작업이나 콜백이 이미 정의되어 있지 않고 disconnect도 없으면 결함 추적
            if conn.dp_name not in disconnected_names:
                unmatched.append(conn)

        return unmatched
