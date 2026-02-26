# Workspace Layout (Grouped Actual Paths + Legacy Compatibility Junctions)

Actual grouped directories:
- workspace/resources/Config
- workspace/resources/CodeReview_Data
- workspace/runtime/CodeReview_Report
- workspace/documentation/docs

Legacy paths kept at repo root as junctions for compatibility:
- Config
- CodeReview_Data
- CodeReview_Report
- docs

Code directories (`backend`, `frontend`, `tools`) remain at root because many scripts compute project roots from `__file__`/`Path.resolve()` and would require wider path migration.
