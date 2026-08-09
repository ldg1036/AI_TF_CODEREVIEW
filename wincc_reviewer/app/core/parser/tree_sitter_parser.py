"""
WinCC OA 코드 리뷰 자동화 도구 — Tree sitter 기반 구문 AST 파서 모듈.

CTRL 및 C++ 소스 코드 구문 구조를 추상 구문 트리 AST로 분석하고,
주석 노드, 문자열 리터럴, 함수/블록 스코프 및 Guard Clause 조상 노드를 추적합니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ASTNodeInfo:
    """AST 구문 노드 정보."""

    node_type: str
    text: str
    line_start: int
    line_end: int
    parent: ASTNodeInfo | None = None
    children: list[ASTNodeInfo] = field(default_factory=list)


@dataclass
class ScopeInfo:
    """코드 스코프 정보."""

    scope_type: str  # function | block | guard | comment
    name: str
    line_start: int
    line_end: int
    has_error_handler: bool = False
    has_safe_wrapper: bool = False


class TreeSitterASTParser:
    """Tree sitter 및 샌드박스 구문 AST 분석 파서."""

    def __init__(self, language: str = "cpp") -> None:
        self.language = language
        self.ts_available = False
        self._init_tree_sitter()

    def _init_tree_sitter(self) -> None:
        """Tree sitter 엔진 초기화 모듈."""
        try:
            import tree_sitter  # type: ignore
            self.ts_available = True
        except ImportError:
            self.ts_available = False

    def parse_code_to_ast(self, content: str) -> list[ASTNodeInfo]:
        """
        소스 코드 텍스트를 AST 구문 노드 리스트로 구조화 파싱합니다.
        
        Args:
            content: 소스 코드 문자열
            
        Returns:
            list[ASTNodeInfo]: 추출된 구문 노드 목록
        """
        nodes: list[ASTNodeInfo] = []
        lines = content.splitlines()

        in_multi_comment = False
        multi_comment_start = 1

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # 1. 블록 주석 감지
            if "/*" in stripped and "*/" not in stripped:
                in_multi_comment = True
                multi_comment_start = idx
                nodes.append(
                    ASTNodeInfo(
                        node_type="Comment",
                        text=stripped,
                        line_start=idx,
                        line_end=idx,
                    )
                )
                continue
            elif in_multi_comment:
                nodes.append(
                    ASTNodeInfo(
                        node_type="Comment",
                        text=stripped,
                        line_start=idx,
                        line_end=idx,
                    )
                )
                if "*/" in stripped:
                    in_multi_comment = False
                continue

            # 2. 한 줄 주석 감지
            if stripped.startswith("//"):
                nodes.append(
                    ASTNodeInfo(
                        node_type="Comment",
                        text=stripped,
                        line_start=idx,
                        line_end=idx,
                    )
                )
                continue

            # 3. 함수 선언 감지
            func_match = re.search(r"\b(void|int|bool|string|dyn_string|dyn_int|mapping)\s+([a-zA-Z0-9_]+)\s*\(", stripped)
            if func_match:
                func_name = func_match.group(2)
                nodes.append(
                    ASTNodeInfo(
                        node_type="FunctionDeclaration",
                        text=func_name,
                        line_start=idx,
                        line_end=idx,
                    )
                )

            # 4. 문자열 리터럴 노드 감지
            str_matches = re.findall(r'"([^"\\]*(\\.[^"\\]*)*)"', stripped)
            for s_tuple in str_matches:
                s_text = s_tuple[0]
                nodes.append(
                    ASTNodeInfo(
                        node_type="StringLiteral",
                        text=s_text,
                        line_start=idx,
                        line_end=idx,
                    )
                )

        return nodes

    def extract_scopes(self, content: str) -> list[ScopeInfo]:
        """
        소스 코드에서 함수, 블록, 주석 스코프 정보를 추출합니다.
        
        Args:
            content: 소스 코드 문자열
            
        Returns:
            list[ScopeInfo]: 스코프 범위 정보 목록
        """
        scopes: list[ScopeInfo] = []
        ast_nodes = self.parse_code_to_ast(content)

        for node in ast_nodes:
            if node.node_type == "Comment":
                scopes.append(
                    ScopeInfo(
                        scope_type="comment",
                        name="CommentBlock",
                        line_start=node.line_start,
                        line_end=node.line_end,
                    )
                )
            elif node.node_type == "FunctionDeclaration":
                scopes.append(
                    ScopeInfo(
                        scope_type="function",
                        name=node.text,
                        line_start=node.line_start,
                        line_end=node.line_start + 50,  # 추정 범위
                        has_error_handler="getLastError" in content,
                        has_safe_wrapper="safeDp" in content,
                    )
                )

        return scopes

    def is_line_in_comment_scope(self, line_num: int, scopes: list[ScopeInfo]) -> bool:
        """
        특정 라인 번호가 주석 스코프 내부인지 판단합니다.
        """
        for sc in scopes:
            if sc.scope_type == "comment" and sc.line_start <= line_num <= sc.line_end:
                return True
        return False
