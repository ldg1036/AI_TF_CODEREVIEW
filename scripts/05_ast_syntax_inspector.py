"""
전체 파이썬 코드베이스 미정의 변수(NameError) 및 엉뚱한 변수 참조 정밀 스캔 엔진.
"""

import ast
from pathlib import Path


class UndefinedNameVisitor(ast.NodeVisitor):

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.scopes = [set(dir(__builtins__))]
        self.undefined_names = []

    def push_scope(self):
        self.scopes.append(set())

    def pop_scope(self):
        self.scopes.pop()

    def add_name(self, name: str):
        self.scopes[-1].add(name)

    def is_defined(self, name: str) -> bool:
        for s in reversed(self.scopes):
            if name in s:
                return True
        return False

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.add_name(name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.add_name(name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.add_name(node.name)
        self.push_scope()
        for arg in node.args.args:
            self.add_name(arg.arg)
        if node.args.vararg:
            self.add_name(node.args.vararg.arg)
        if node.args.kwarg:
            self.add_name(node.args.kwarg.arg)
        self.generic_visit(node)
        self.pop_scope()

    def visit_ClassDef(self, node):
        self.add_name(node.name)
        self.push_scope()
        self.generic_visit(node)
        self.pop_scope()

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.add_name(target.id)
            elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                for el in target.elts:
                    if isinstance(el, ast.Name):
                        self.add_name(el.id)
        self.generic_visit(node)

    def visit_For(self, node):
        if isinstance(node.target, ast.Name):
            self.add_name(node.target.id)
        elif isinstance(node.target, ast.Tuple):
            for el in node.target.elts:
                if isinstance(el, ast.Name):
                    self.add_name(el.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            # Exception block variable or builtins
            if not self.is_defined(node.id) and node.id not in ("self", "cls", "__file__", "__name__"):
                self.undefined_names.append((node.lineno, node.id))
        self.generic_visit(node)


def inspect_all_scripts(root_dir: Path) -> dict:
    py_files = list(root_dir.rglob("*.py"))
    findings = []

    for p in py_files:
        if "__pycache__" in str(p) or ".venv" in str(p):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(p))
            visitor = UndefinedNameVisitor(p)
            visitor.visit(tree)
            if visitor.undefined_names:
                # filter out dynamically imported or false positives if any
                filtered = [u for u in visitor.undefined_names if u[1] not in ("open", "print", "len", "str", "int", "float", "bool", "dict", "list", "set", "tuple", "range", "enumerate", "isinstance", "issubclass", "getattr", "setattr", "hasattr", "super", "type", "Exception", "ValueError", "TypeError", "KeyError", "AttributeError", "RuntimeError", "NameError", "ZeroDivisionError", "FileNotFoundError", "IOError", "FileExistsError", "PermissionError", "ImportError", "SyntaxError", "IndentationError", "StopIteration", "any", "all", "map", "filter", "zip", "sum", "min", "max", "abs", "round", "repr", "dir", "vars", "id", "hash", "input", "object", "bytes", "bytearray", "classmethod", "staticmethod", "property", "slice")]
                if filtered:
                    findings.append({"file": str(p.relative_to(root_dir)), "issues": filtered})
        except Exception as e:
            findings.append({"file": str(p.relative_to(root_dir)), "issues": [(-1, str(e))]})

    return {"total_files": len(py_files), "issues_count": len(findings), "details": findings}


if __name__ == "__main__":
    res = inspect_all_scripts(Path("wincc_reviewer"))
    print(f"스캔된 파일 수: {res['total_files']}개")
    print(f"미정의/엉뚱한 변수 우려 파일 수: {res['issues_count']}개")
    for item in res["details"]:
        print(f"\n[파일]: {item['file']}")
        for line, name in item["issues"]:
            print(f"  - {line}행: {name}")
