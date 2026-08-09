import os
import sys
from pathlib import Path

# Add wincc_reviewer to path
sys.path.insert(0, os.path.abspath('wincc_reviewer'))

from app.core.pipeline import Pipeline, PipelineConfig
from app.core.rules.checker_registry import CheckerRegistry
from app.core.rules.excel_rule_compiler import ExcelRuleCompiler

pnl_path = r'C:\Users\39145\Downloads\Coder_Wincc-main\CodeReview_Data\새 폴더\CA2_Na2SO3_VALVE.pnl'

print("=== 1. Registered Checkers ===")
for key in sorted(CheckerRegistry._registry.keys()):
    print(f"Checker: {key}")

print("\n=== 2. Compiling Rules from Client Excel ===")
config_dir = Path('config')
client_yaml = config_dir / 'legacy_mapping' / 'client.yaml'

excel_files = list(config_dir.glob('*.xlsx'))
client_excel = [f for f in excel_files if 'Client' in f.name][0]

result = ExcelRuleCompiler.compile_rules(client_excel, client_yaml, verify_sha256=False)
print(f"Total Rules: {result.total_count} | Automated: {result.automated_count} | Manual: {result.manual_review_count}")

print("\n--- Compiled Rules Details ---")
for r in result.rules:
    print(f"Rule ID: {r.rule_id:15s} | CheckerType: {r.checker_type.value:10s} | Key: {r.checker_key}")

print("\n=== 3. Executing Review Pipeline ===")
config = PipelineConfig(input_path=Path(pnl_path), no_ai=True)
pipeline = Pipeline(config)
report = pipeline.run()

print(f"\nTotal Violations Detected: {len(report.violations)}")
for v in report.violations:
    print(f"[{v.status.value:13s}] Rule: {v.rule_id:12s} | Line: {v.line_start:4d} | Sev: {v.severity.value:7s} | Msg: {v.message[:70]}")
