"""
Data Flow Analysis (DFA) Engine.
AST 파싱을 보조하여 데이터 흐름(Taint)을 추적하는 초경량 엔진입니다.
"""
from __future__ import annotations
import re

class TaintTracker:
    def __init__(self, sources: list[str], sinks: list[str]):
        self.sources = sources
        self.sinks = sinks
        self.tainted_vars: set[str] = set()

    def track(self, code_lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
        violations: list[tuple[int, str]] = []
        
        for idx, line in code_lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # 1. Assignment parsing
            if '=' in line_clean and '==' not in line_clean and '!=' not in line_clean:
                parts = line_clean.split('=', 1)
                left = parts[0].strip()
                right = parts[1].strip()

                left_var = left.split()[-1].replace('*', '')

                is_tainted = False
                for src in self.sources:
                    if src in right:
                        is_tainted = True
                        break
                
                if not is_tainted:
                    for tvar in self.tainted_vars:
                        if re.search(rf'\b{tvar}\b', right):
                            is_tainted = True
                            break

                if is_tainted:
                    self.tainted_vars.add(left_var)
                else:
                    if left_var in self.tainted_vars:
                        self.tainted_vars.remove(left_var)

            # 2. Sink usage parsing
            for sink in self.sinks:
                sink_call = rf'{sink}\s*\('
                if re.search(sink_call, line_clean):
                    for tvar in self.tainted_vars:
                        if re.search(rf'\b{tvar}\b', line_clean):
                            violations.append((idx, line_clean))
                            break
                            
        return violations