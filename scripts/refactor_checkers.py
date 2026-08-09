import os
import re

source_file = r'wincc_reviewer\app\core\rules\checker_registry.py'
dest_dir = r'wincc_reviewer\app\core\rules\checkers'

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

header = '''\"\"\"Builtin Checker Registry & Modules\"\"\"
from __future__ import annotations
import re
from typing import Any

from app.core.models import RuleDefinition, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile
'''

functions = re.split(r'^(?=def )', content, flags=re.MULTILINE)

groups = {
    'resource': ['check_dp_connect_pair', 'check_file_handle_leak', 'check_pnl_scope_leak', 'check_unmatched_lock_unlock', 'check_missing_panel_on_close'],
    'security': ['check_sql_injection_risk', 'check_scada_security_exec', 'check_sprintf_buffer_overflow_risk', 'check_file_open_mode_check'],
    'performance': ['check_loop_delay', 'check_batch_dp_operations', 'check_dp_in_loop', 'check_dp_callback_delay'],
    'error_handling': ['check_try_catch_exception', 'check_dp_function_error_handling', 'check_unhandled_dp_query_error', 'check_callback_error_handling', 'check_dp_set_wait_timeout', 'check_dp_async_handling'],
    'quality': ['check_hardcoding', 'check_dpe_hardcoding', 'check_magic_number', 'check_dead_code_and_unused', 'check_unused_function_param', 'check_duplicated_code', 'check_global_scope_shadowing', 'check_global_var_naming_convention', 'check_uninitialized_var', 'check_dyn_array_out_of_bounds', 'check_child_panel_parameter_mismatch', 'check_debug_log_level', 'check_config_integrity']
}

module_contents = {k: header for k in groups.keys()}
helper_functions = []

for block in functions:
    if not block.strip().startswith('def '):
        continue

    match = re.match(r'^def ([a-zA-Z0-9_]+)\(', block)
    if not match:
        continue
    func_name = match.group(1)

    matched = False
    for mod, funcs in groups.items():
        if func_name in funcs:
            module_contents[mod] += '\n' + block
            matched = True
            break

    if not matched:
        helper_functions.append(block)

# _PNL_INIT_CONTEXT_KEYWORDS 같은 전역 변수도 추출해야 하므로 content에서 def 이전 부분을 추출
pre_defs = content.split('def ')[0]
globals_match = re.search(r'# _+PNL_INIT_CONTEXT_KEYWORDS.*?(?=\n\n)', pre_defs, re.DOTALL)
global_vars = globals_match.group(0) if globals_match else ''
# 실제로 pre_defs 중 변수 선언 부분을 찾아야함.
global_vars = '''
_PNL_INIT_CONTEXT_KEYWORDS = [
    "scopelib::",
    "initialize(",
    "panelonopen(",
    "event_panel",
    "panel_on_open",
    "panel_on_start",
    "initpanel(",
    "main(",
]
'''

shared_helpers = global_vars + '\n' + '\n'.join(helper_functions)
for mod in module_contents:
    module_contents[mod] = module_contents[mod].replace(header, header + '\n' + shared_helpers + '\n')

for mod, text in module_contents.items():
    with open(os.path.join(dest_dir, f'{mod}.py'), 'w', encoding='utf-8') as f:
        f.write(text)

print('Split into modules complete.')
