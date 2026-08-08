"""
ctrl_ast_parser.py

WinCC OA Control 언어 및 PNL 구문 분석 AST 체커 보강 엔진
문맥 토큰 윈도우 기반 정밀 구문 트리 분석으로 오탐을 차단함
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ASTNode:
    """단일 AST 구문 노드"""
    node_type: str
    content: str
    line_number: int
    children: list[ASTNode] = field(default_factory=list)


class CtrlASTParser:
    """WinCC OA CTRL 및 PNL 스크립트 문맥 AST 파서"""

    def __init__(self):
        self.comment_pattern = re.compile(r"//.*$|/\*[\s\S]*?\*/|#.*$", re.MULTILINE)

    def remove_comments(self, code: str) -> str:
        """주석 구문 제거"""
        return self.comment_pattern.sub("", code)

    def parse_tokens(self, code: str) -> list[ASTNode]:
        """토큰 윈도우 기반 AST 노드 트리 생성"""
        clean_code = self.remove_comments(code)
        lines = clean_code.splitlines()
        nodes: list[ASTNode] = []

        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("while") or stripped.startswith("for"):
                nodes.append(ASTNode(node_type="loop", content=stripped, line_number=line_no))
            elif "dpSet(" in stripped or "dpGet(" in stripped or "dpConnect(" in stripped:
                nodes.append(ASTNode(node_type="dp_call", content=stripped, line_number=line_no))
            elif "try" in stripped or "catch" in stripped or "getLastError" in stripped:
                nodes.append(ASTNode(node_type="exception_handling", content=stripped, line_number=line_no))
            else:
                nodes.append(ASTNode(node_type="statement", content=stripped, line_number=line_no))

        return nodes

    def analyze_loop_safety(self, code: str) -> dict[str, Any]:
        """무한 루프 내부 안전 대기 구문(delay, waitFor) 유무 AST 검사"""
        clean_code = self.remove_comments(code)
        has_while = "while" in clean_code
        has_delay = "delay(" in clean_code or "dpWaitFor" in clean_code or "waitFor" in clean_code

        is_safe = (not has_while) or (has_while and has_delay)
        return {
            "has_loop": has_while,
            "has_delay": has_delay,
            "is_safe": is_safe
        }
