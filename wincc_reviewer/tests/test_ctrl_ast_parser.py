"""
test_ctrl_ast_parser.py

CtrlASTParser 파서 모듈 유닛 테스트 (R2 호출부 증명)
"""

from __future__ import annotations

from app.core.parsers.ctrl_ast_parser import CtrlASTParser


class TestCtrlASTParser:
    """CtrlASTParser AST 문맥 분석 기능 검증"""

    def test_remove_comments(self):
        parser = CtrlASTParser()
        code = "int x = 10; // comment line\n/* multi line */ int y = 20;"
        clean = parser.remove_comments(code)
        assert "// comment" not in clean
        assert "/* multi line */" not in clean
        assert "int x = 10;" in clean

    def test_parse_tokens(self):
        parser = CtrlASTParser()
        code = "while(true) {\n  dpSet(\"test.val\", 1);\n  delay(1);\n}"
        nodes = parser.parse_tokens(code)
        assert len(nodes) >= 2
        assert any(n.node_type == "loop" for n in nodes)
        assert any(n.node_type == "dp_call" for n in nodes)

    def test_analyze_loop_safety(self):
        parser = CtrlASTParser()
        unsafe_code = "while(true) { x++; }"
        safe_code = "while(true) { delay(1); }"

        res_unsafe = parser.analyze_loop_safety(unsafe_code)
        res_safe = parser.analyze_loop_safety(safe_code)

        assert res_unsafe["is_safe"] is False
        assert res_safe["is_safe"] is True
