# WinCC OA 코드 리뷰어

최종 검증일: 2026-03-09

## 소개

이 프로젝트는 WinCC OA 프로젝트 코드를 대상으로 정적 규칙 검사, CtrlppCheck, AI 리뷰를 한 화면에서 수행할 수 있는 코드 리뷰 도구입니다.

주요 목적은 다음과 같습니다.

- WinCC OA 코드의 P1, P2, P3 리뷰를 한 번에 수행
- 체크리스트 기반 결과서를 HTML, Excel, REVIEWED TXT 형태로 생성
- 이슈 상세 화면에서 AI 개선 제안과 비교 화면 제공
- 필요 시 source autofix 준비, diff 확인, 적용까지 연결

## 지원 입력과 출력

### 지원 입력

- `.ctl`
- `.pnl`, `.xml`에서 변환된 텍스트 파일 (`*_pnl.txt`, `*_xml.txt`)
- 필요 시 raw `.txt` 입력

### 생성 결과

- 웹 UI 결과 화면
- HTML 리포트
- Excel 리포트
- REVIEWED TXT (`*_REVIEWED.txt`)

Excel 결과서는 현재 아래 기준으로 채워집니다.

- `F열`: 1차 검증
- `G열`: 검증 결과
- `H열`: 비고

## 핵심 기능

### 1. 코드 분석

- `P1`: 정적 규칙 기반 분석
- `P2`: CtrlppCheck 기반 분석
- `P3`: Live AI 기반 리뷰 및 개선 제안

P2와 P3는 선택적으로 켜고 끌 수 있습니다.  
필수 의존성이 없는 경우에도 가능한 범위까지 계속 진행하는 fail-soft 흐름을 사용합니다.

### 2. 현재 UI 흐름

현재 UI는 크게 4개 영역으로 구성됩니다.

1. 좌측 사이드바
   - 프로젝트 파일 선택
   - 외부 파일 추가
   - 폴더 선택
   - 결과 필터
2. 상단 헤더
   - `CtrlppCheck 사용 (P2)`
   - `Live AI 사용 (P3)`
   - `P3 모델`
   - `Live AI에 프로젝트 MCP 문맥 포함`
   - `검증 레벨`
   - `검증 프로파일`
   - `선택 항목 분석`
   - `Excel 결과 생성`
3. 작업공간
   - 코드 뷰어
   - 결과 리스트
4. 우측 이슈 상세 패널
   - 이슈 상세
   - AI 제안
   - 필요 시 `추가 AI 분석`

참고:

- MCP 문맥 상태는 실제 요청 예정이거나 요청 시간이 있을 때만 짧게 표시됩니다.
- Excel 다운로드는 헤더에서 접힘 패널 형태로 표시됩니다.

### 3. AI 제안과 추가 AI 분석

이슈 상세의 `AI 제안` 탭에서 다음을 할 수 있습니다.

- 기존 P3 리뷰 확인
- P1/P2 원본 이슈와 P3 제안 비교
- `추가 AI 분석`으로 선택 이슈 1건만 즉시 재분석

즉, 배치 분석에서 P3가 생성되지 않았거나 보강이 필요할 때 전체 재분석 없이 이슈 단위로 다시 생성할 수 있습니다.

### 4. Excel 결과 생성

프론트에서는 분석 완료 직후 Excel을 항상 즉시 만들지 않습니다.

- 분석은 먼저 수행
- 필요할 때 `Excel 결과 생성` 버튼으로 별도 생성
- 생성이 완료되면 헤더에서 파일별 다운로드

관련 API:

- `POST /api/report/excel`
- `GET /api/report/excel/download?output_dir=...&name=...`

### 5. Autofix

Autofix는 다음 흐름으로 동작합니다.

1. `autofix/prepare`
2. diff 확인
3. `autofix/apply`

지원 특징:

- `rule`, `llm`, `auto(rule-first, llm-fallback)` 방식
- hash / anchor / syntax / heuristic 검증
- optional Ctrlpp regression 검증
- multi-hunk 안전 정책
- 백업 파일 및 감사 로그 유지

## 체크리스트 판정 기준

결과서의 체크리스트 항목은 모두 같은 방식으로 판정하지 않습니다.  
현재는 보수적으로 아래 기준을 사용합니다.

### 완전 자동

- `Loop문 내에 처리 조건`
- `while` 패턴이 있는 경우에만 `OK / NG / N/A`를 자동 판정

### 부분 자동

- `메모리 누수 체크`
- `하드코딩 지양`
- `디버깅용 로그 작성 확인`

부분 자동 항목은 다음 원칙을 따릅니다.

- 위반 검출 시 `NG`
- 미검출 시 `OK`로 확정하지 않고 `N/A + 수동 확인 권장`

### 수동 확인

- `쿼리 주석 처리`

이 항목은 형식 품질까지 자동 보장하기 어렵기 때문에 현재는 수동 확인 대상으로 유지합니다.

## API 요약

주요 API는 다음과 같습니다.

- `POST /api/analyze/start`
- `GET /api/analyze/status?job_id=...`
- `GET /api/health/deps`
- `GET /api/rules/health`
- `POST /api/report/excel`
- `GET /api/report/excel/download?output_dir=...&name=...`
- `POST /api/ai-review/generate`

## 빠른 시작

### UI 서버 실행

```powershell
python backend/server.py
```

접속 주소:

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
python backend/main.py --selected-files GoldenTime.ctl --enable-live-ai
python backend/main.py --selected-files raw_input.txt --allow-raw-txt
```

## 프론트 기준 사용 순서

1. 좌측 사이드바에서 분석할 파일을 선택합니다.
2. 필요하면 외부 파일 추가 또는 폴더 선택으로 입력 대상을 확장합니다.
3. 상단 헤더에서 `P2`, `P3`, 모델, MCP 문맥 포함 여부를 설정합니다.
4. `선택 항목 분석`을 실행합니다.
5. 결과 리스트에서 항목을 선택해 우측 이슈 상세를 확인합니다.
6. 필요하면 `AI 제안` 탭에서 `추가 AI 분석`을 실행합니다.
7. Excel이 필요하면 `Excel 결과 생성` 후 다운로드합니다.

## 검증 및 테스트

### 기본 검증

```powershell
python -m unittest backend.tests.test_api_and_reports -v
python -m unittest backend.tests.test_todo_rule_mining -v
python -m unittest backend.tests.test_winccoa_context_server -v
python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
```

### 프론트/실서버 스모크

```powershell
node --check frontend/renderer.js
node tools/playwright_ui_real_smoke.js --target-file BenchmarkP1Fixture.ctl
```

### 선택 실행

- Ctrlpp smoke

```powershell
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
```

- UI benchmark

```powershell
node tools/playwright_ui_benchmark.js --iterations 3
```

## 프로젝트 구조

```text
AI_TF_CODEREVIEW-main/
├─ backend/
├─ frontend/
├─ tools/
│  ├─ perf/
│  └─ ctrlpp/
├─ Config/
├─ CodeReview_Data/
├─ CodeReview_Report/
├─ docs/
├─ workspace/
├─ README.md
└─ todo.md
```

## 참고 문서

- `docs/user_operations_guide.md`
- `docs/release_gate_checklist.md`
- `docs/release_packaging_criteria.md`
- `improvement_recommendations.md`
