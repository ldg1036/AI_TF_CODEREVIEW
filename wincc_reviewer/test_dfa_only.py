import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.rules.dfa_engine import TaintTracker

tracker = TaintTracker(
    sources=["getUserText", "dpGet", "ui_getText", "recv"],
    sinks=["dpQuery", "dbOpenNames", "dbExecuteQuery", "dbExecute"]
)
lines = [
    (1, 'main() { '),
    (2, '    string ext = ui_getText("Input");'),
    (3, '    string safe = ext;'),
    (4, '    dpQuery("SELECT * FROM _configs WHERE x LIKE '" + safe + "'");'),
    (5, '}')
]
violations = tracker.track(lines)
print('VIOLATIONS:', violations)
