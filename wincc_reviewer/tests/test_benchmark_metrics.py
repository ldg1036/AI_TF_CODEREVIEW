import importlib.util
import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent.parent
script_path = base_dir / 'scripts' / '15_run_large_scale_benchmark.py'

spec = importlib.util.spec_from_file_location('run_large_scale_benchmark', script_path)
run_large_scale_benchmark = importlib.util.module_from_spec(spec)
sys.modules['run_large_scale_benchmark'] = run_large_scale_benchmark
spec.loader.exec_module(run_large_scale_benchmark)

def test_calculate_metrics_normal():
    tp, fp, fn = 168, 42, 98
    precision, recall = run_large_scale_benchmark.calculate_metrics(tp, fp, fn)
    assert round(precision, 1) == 80.0
    assert round(recall, 1) == 63.2
    assert precision != recall

def test_calculate_metrics_zero_denominators():
    precision, recall = run_large_scale_benchmark.calculate_metrics(0, 0, 0)
    assert precision == 100.0
    assert recall == 100.0
