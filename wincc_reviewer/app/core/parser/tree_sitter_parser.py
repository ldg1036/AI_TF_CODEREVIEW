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
        self.parser = None
        self._init_tree_sitter()

    def _init_tree_sitter(self) -> None:
        """Tree sitter 엔진 초기화 모듈."""
        try:
            import tree_sitter
            import tree_sitter_cpp
            
            try:
                # v0.22+ API
                self.ts_language = tree_sitter.Language(tree_sitter_cpp.language())
            except TypeError:
                # v0.21 API
                self.ts_language = tree_sitter.Language(tree_sitter_cpp.language(), "cpp")
            
            self.parser = tree_sitter.Parser()
            self.parser.set_language(self.ts_language)
            self.ts_available = True
        except Exception as e:
            self.ts_available = False
            self.parser = None

    def get_raw_tree(self, content: str) -> Any:
        """순수 tree-sitter Tree 객체를 반환합니다."""
        if not self.ts_available or not self.parser:
            return None
        return self.parser.parse(bytes(content, "utf8"))

    def parse_code_to_ast(self, content: str) -> list[ASTNodeInfo]:
        """
        소스 코드 텍스트를 AST 구문 노드 리스트로 구조화 파싱합니다.
        
        Args:
            content: 소스 코드 문자열
            
        Returns:
            list[ASTNodeInfo]: 추출된 구문 노드 목록
        """
        nodes: list[ASTNodeInfo] = []
        
        # 1. Tree-sitter가 사용 가능하면 순회하여 노드를 생성합니다.
        if self.ts_available and self.parser:
            tree = self.parser.parse(bytes(content, "utf8"))
            
            def traverse(node, parent_ast: ASTNodeInfo | None = None):
                # 0-indexed line to 1-indexed line
                line_start = node.start_point[0] + 1
                line_end = node.end_point[0] + 1
                
                ast_node = ASTNodeInfo(
                    node_type=node.type,
                    text=node.text.decode("utf8") if node.text else "",
                    line_start=line_start,
                    line_end=line_end,
                    parent=parent_ast
                )
                nodes.append(ast_node)
                
                if parent_ast:
                    parent_ast.children.append(ast_node)
                    
                for child in node.children:
                    traverse(child, ast_node)
                    
            traverse(tree.root_node)
            return nodes

        # 2. Fallback: 기존 정규식 기반 로직
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

        # ts가 가능할 때는 function_definition 노드를 찾음
        for node in ast_nodes:
            if node.node_type in ("comment", "Comment"):
                scopes.append(
                    ScopeInfo(
                        scope_type="comment",
                        name="CommentBlock",
                        line_start=node.line_start,
                        line_end=node.line_end,
                    )
                )
            elif node.node_type in ("function_definition", "FunctionDeclaration"):
                # tree-sitter 사용 시 함수 이름 추출 로직 (단순화: text를 사용)
                name = node.text if node.node_type == "FunctionDeclaration" else "function"
                scopes.append(
                    ScopeInfo(
                        scope_type="function",
                        name=name,
                        line_start=node.line_start,
                        line_end=node.line_end,  # tree-sitter는 끝 줄을 정확히 안다 (fallback은 start+50이지만 여기선 node.line_end 사용)
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
