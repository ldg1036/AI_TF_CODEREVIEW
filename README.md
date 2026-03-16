# WinCC OA Code Inspector

Last validated: 2026-03-17

## 개요

`WinCC OA Code Inspector`는 WinCC OA 프로젝트 코드 리뷰를 자동화하고, 작업공간 UI에서 분석 결과를 검토/비교/triage 할 수 있게 만든 도구입니다.

주요 분석 축:
- `P1`: 정적 규칙 기반 분석
- `P2`: `CtrlppCheck` 연동
- `P3`: 선택형 Live AI 리뷰

지원 입력:
- `.ctl`
- `.pnl`, `.xml`에서 변환된 텍스트 (`*_pnl.txt`, `*_xml.txt`)
- raw `.txt` (`--allow-raw-txt` 또는 UI 옵션 사용 시)

주요 출력:
- 대시보드 / 작업공간 / 설정 UI
- HTML 리포트
- Excel 리포트
- Annotated TXT (`*_REVIEWED.txt`)
- source autofix 비교/적용 결과

## 현재 UI 구조

### 1. 대시보드
- 프로젝트 요약
- 전체 이슈 / 현재 검토 대상 / 치명 / 경고
- 중복 정리 요약
- 우선 수정 추천 Top 5
- compact 시스템 상태 요약

### 2. 작업공간
- 파일 목록 / 파일 검색
- 코드 뷰어
- 결과 리스트 / 결과 검색 / preset (`기본 보기`, `P1만`, `치명/경고`)
- P1 triage (`숨김 처리`, `숨김 해제`, `사유`, `메모`)
- AI / compare / autofix 흐름
- 코드 뷰어와 결과 리스트 사이 세로 리사이즈

### 3. 설정
- 운영 검증 상세
  - UI benchmark
  - real UI smoke
  - Ctrlpp integration
- 규칙 / 의존성 관리
  - rules health
  - P1 rule CRUD
  - import dry-run preview
  - rollback latest

## 주요 기능

### 분석
- `POST /api/analyze`
- `POST /api/analyze/start`
- `GET /api/analyze/status?job_id=...`
- bounded parallel 분석
- `.pnl/.xml -> *_txt` 변환 캐시
- `metrics`, `verification_level`, optional dependency 상태 제공

### Autofix
- `POST /api/autofix/prepare`
- `POST /api/autofix/apply`
- `GET /api/autofix/file-diff`
- hash / anchor / syntax / heuristic / optional Ctrlpp regression 검증
- diff 승인형 source apply / REVIEWED apply

### P1 Triage
- `GET /api/triage/p1`
- `POST /api/triage/p1/upsert`
- `POST /api/triage/p1/delete`
- suppressed P1 기본 숨김
- `Show suppressed` 토글
- 재분석 후 동일 fingerprint P1 이슈 자동 숨김 유지

### Rules Manage
- list / create / replace / delete
- export
- import merge / replace
- import dry-run preview
- rollback latest

### 운영/검증
- dependency health
- operations latest
- analysis diff latest / runs / compare
- release gate
- UI benchmark / real smoke / Ctrlpp integration smoke

## 빠른 시작

### 필수 준비

```powershell
python -m pip install -r requirements-dev.txt
npm install
```

선택 의존성:
- `CtrlppCheck`
- `Ollama`
- Playwright browser (`npx playwright install chromium`)

### UI 서버 실행

```powershell
python backend/server.py
```

접속:

```text
http://127.0.0.1:8765
```

### CLI 분석 실행

```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

추가 예시:

```powershell
python backend/main.py --selected-files GoldenTime.ctl --enable-ctrlppcheck
python backend/main.py --selected-files GoldenTime.ctl --enable-live-ai --ai-with-context
python backend/main.py --selected-files raw_input.txt --allow-raw-txt
```

## 프론트 테스트 / 게이트

프론트 빠른 단위 테스트:

```powershell
npm run test:frontend
```

로컬 빠른 게이트:

```powershell
python tools/run_local_quality_gate.py
```

확장 게이트:

```powershell
python tools/run_local_extended_gate.py
```

통합 게이트:

```powershell
python tools/release_gate.py
python tools/release_gate.py --profile ci
```

## 권장 검증

백엔드 / API 변경:

```powershell
python -m unittest backend.tests.test_api_and_reports -v
python backend/system_verification.py
```

프론트 렌더링 / UX 변경:

```powershell
npm run test:frontend
node tools/playwright_ui_real_smoke.js --timeout-ms 120000
```

설정 / rules / template 변경:

```powershell
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
```

## 프로젝트 구조

```text
AI_TF_CODEREVIEW-main/
├─ backend/
├─ frontend/
├─ tools/
├─ Config/
├─ CodeReview_Data/
├─ docs/
├─ workspace/
│  ├─ runtime/
│  │  ├─ CodeReview_Report/
│  │  ├─ refactor_backups/
│  │  ├─ rule_backups/
│  │  └─ triage/
│  ├─ documentation/
│  └─ resources/
├─ CodeReview_Report/
├─ README.md
└─ todo.md
```

## 추가 문서

- 운영 가이드: `docs/user_operations_guide.md`
- 릴리스 체크리스트: `docs/release_gate_checklist.md`
- 성능/게이트 가이드: `docs/performance.md`
- 패키징 기준: `docs/release_packaging_criteria.md`
- tools 설명: `tools/README.md`
