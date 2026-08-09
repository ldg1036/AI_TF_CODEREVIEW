"""
WinCC OA 코드 리뷰 자동화 도구 — Tree sitter 기반 구문 AST 파서 단위 테스트 스위트.
"""

from __future__ import annotations

import pytest

from app.core.parser.tree_sitter_parser import TreeSitterASTParser


class TestTreeSitterASTParser:
    """TreeSitterASTParser 기능 실증 테스트 스위트."""

    def test_parse_code_to_ast_comments_and_functions(self):
        """AST 노드 추출 및 주석/함수 선언 파싱 검증."""
        code = """
        // 단일 주석 예시
        void main() {
            int a = 10;
            /* 블록 주석
               내부 구문 */
            string msg = "hello world";
        }
        """

        parser = TreeSitterASTParser()
        nodes = parser.parse_code_to_ast(code)
        assert len(nodes) >= 3

        node_types = [n.node_type for n in nodes]
        assert "Comment" in node_types
        assert "FunctionDeclaration" in node_types
        assert "StringLiteral" in node_types

    def test_extract_scopes_and_is_line_in_comment_scope(self):
        """스코프 정보 추출 및 라인 범위 인지 기능 검증."""
        code = """line 1
        /* 
           주석 스코프 테스트
        */
        void runProcess() {
            dpSet("tag", 1);
        }
        """

        parser = TreeSitterASTParser()
        scopes = parser.extract_scopes(code)
        assert len(scopes) >= 1

        # 블록 주석 내부 라인 3 검사
        is_comment = parser.is_line_in_comment_scope(3, scopes)
        assert is_comment is True

        # 주석 바깥 라인 6 검사
        is_comment_line_6 = parser.is_line_in_comment_scope(6, scopes)
        assert is_comment_line_6 is False
