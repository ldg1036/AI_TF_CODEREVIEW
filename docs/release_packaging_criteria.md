# Release Packaging Criteria

Last Updated: 2026-03-06

## Goal

Define what should be included in a final deliverable package and what should be treated as runtime output only.

## 1. Minimum Release Acceptance

A build is ready to package when these are true:
- `.\run_release_gate.bat` passes
- if live AI is part of the promised scope, `.\run_release_gate.bat live-ai` passes
- latest release gate JSON and Markdown summaries are available

## 2. Package Contents

Include:
- `backend/`
- `frontend/`
- `Config/`
- `CodeReview_Data/` only if the delivery is expected to include sample or fixture inputs
- `tools/`
- `requirements-dev.txt`
- `package.json`
- `package-lock.json`
- `README.md`
- `docs/user_operations_guide.md`
- `docs/release_gate_checklist.md`
- `docs/release_packaging_criteria.md`

Include only when needed by the recipient:
- `tools/CtrlppCheck/` runtime install cache
- `node_modules/`

Guideline:
- do not ship bulky caches unless the target environment is offline or preinstallation is intentionally part of delivery

## 3. Do Not Treat As Source Deliverables

Do not package as canonical source artifacts:
- `CodeReview_Report/`
- temporary logs
- ad-hoc benchmark outputs not referenced by the release notes
- editor-specific or local machine metadata

These are runtime or evidence artifacts, not part of the clean source package.

## 4. Optional Dependency Policy

### CtrlppCheck

Policy:
- optional unless explicitly required by the delivery scope
- if required, confirm the binary is installable and the direct smoke passes

### Ollama / Live AI

Policy:
- optional unless live AI is part of the acceptance scope
- if required, confirm the live AI release gate passes

### Playwright

Policy:
- optional for normal runtime
- required only for UI benchmark and real UI smoke validation

## 5. Recommended Packaging Profiles

### Clean source package

Use when:
- recipient can install dependencies locally

Include:
- source, config, docs, wrappers

Exclude:
- runtime reports
- downloaded browsers
- runtime caches

### Operator-ready local package

Use when:
- recipient is non-developer
- environment is controlled or partly offline

Include:
- clean source package contents
- optionally `tools/CtrlppCheck/`
- optionally Playwright browser/runtime if the target machine cannot install it itself

## 6. Release Notes Checklist

For each packaged build, record:
- release date
- release gate JSON path
- release gate Markdown path
- whether live AI was included in scope
- whether Ctrlpp was included in scope
- any intentional optional dependency exclusions

## 7. Recommended Final Decision Rule

Use this simple rule:
- if the promised features are covered by the passed release gate profile, package it
- if a promised optional feature was not checked, do not claim it as release-ready
