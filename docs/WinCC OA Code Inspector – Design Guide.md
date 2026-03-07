# WinCC OA Code Inspector 설계 가이드 (v3.0)

마지막 업데이트: 2026-02-27 (현재 구현 기준)

이 문서는 WinCC OA 코드리뷰 프로그램의 설계 원칙, 모듈 책임, 성능/안전성 기준을 설명한다.

## 1. 설계 목표

1. WinCC OA 코드(`.ctl`)와 변환된 UI 텍스트(`*_pnl.txt`, `*_xml.txt`)를 일관된 파이프라인으로 분석한다.
2. 정적 규칙(P1), CtrlppCheck(P2), AI 리뷰(P3)를 분리된 책임으로 처리한다.
3. 로컬 데스크톱 환경에서 중간 배치(대략 5~50 파일) 기준으로 체감 성능이 유지되도록 한다.
4. 자동수정은 승인형(diff review) 기반으로 안전하게 적용한다.

## 2. 핵심 설계 원칙

### 2.1 기능 분리
- 분석 오케스트레이션: `backend/core/analysis_pipeline.py`
- 분석 엔진/세션/자동수정: `backend/main.py` (`CodeInspectorApp`)
- HTTP API: `backend/server.py`
- 리포트 생성: `backend/core/reporter.py`
- AI 리뷰/프롬프트: `backend/core/llm_reviewer.py`
- UI 렌더링: `frontend/renderer.js`

### 2.2 Fail-soft 기본 정책
- LLM/CtrlppCheck는 실패해도 가능한 범위에서 P1/P2/P3 중 일부 결과를 유지한다.
- 자동수정은 검증 실패 시 적용하지 않고 중단한다.

### 2.3 성능 관측성 우선
- `/api/analyze` 응답에 `metrics`를 포함한다.
- 성능 개선은 체감이 아니라 수치(단계별 timing, 호출 수, 캐시 hit/miss)로 확인한다.

## 3. 분석 파이프라인 설계

1. 파일 수집 (`/api/files`, 선택 파일 검증)
2. 필요 시 `.pnl/.xml -> *_txt` 변환
3. 파일별 분석 실행 (bounded parallel)
4. 결과 집계 및 요약 생성
5. 리포트 생성 (Annotated TXT / HTML / Excel)
6. 세션 캐시 저장 (AI 리뷰 적용/자동수정용)

### 3.1 병렬화 전략
- 파일 단위 병렬 분석 수행
- 리소스 고갈 방지를 위해 세마포어로 경로별 동시성 제한
  - CtrlppCheck
  - Live AI
  - Reporter
  - Excel 생성

### 3.2 변환 캐시 전략
- `.pnl/.xml` 변환 결과는 `mtime + size` 기준으로 캐시 재사용
- 전역 락 대신 source 단위 락으로 요청 간 병렬성 저하를 줄임

## 4. 리포트/세션 설계

### 4.1 리포트
- 기본 산출물:
  - Annotated TXT (`*_REVIEWED.txt`)
  - HTML 요약
  - Excel 체크리스트
- 성능 옵션:
  - `defer_excel_reports=true`로 Excel 생성 지연
  - `/api/report/excel`로 후속 flush

### 4.2 세션 캐시
- 분석 세션은 output dir 기준으로 관리
- TTL/LRU eviction 적용
- per-session / per-file lock 적용
- 자동수정 proposal/상태/감사로그와 연결

## 5. 자동수정(Autofix) 설계

### 5.1 기본 원칙
- 대상: `.ctl`만
- 방식: Diff 승인형 (무승인 자동적용 금지)
- 검증:
  - base hash
  - anchor/context
  - 기본 문법 precheck
  - heuristic 회귀검사
  - optional Ctrlpp 회귀검사

### 5.2 Generator 전략
- `llm`: AI 리뷰 코드블록 기반 제안
- `rule`: 결정적(rule-first) 텍스트 정규화/템플릿 제안
- `auto`: 내부 정책으로 `rule-first` 후 `llm-fallback`

## 6. 프론트엔드 설계 포인트

- 결과 테이블 virtualization(가상 스크롤)
- 코드뷰 virtualization(라인 윈도우 렌더링)
- AI 카드에서 `Diff Preview / Apply Source / Apply REVIEWED` 분리
- autofix validation 결과(회귀/오류) 표시

## 7. 운영/품질 게이트

- UI 벤치: `tools/playwright_ui_benchmark.js`
- HTTP 성능 baseline: `tools/http_perf_baseline.py`
- 기준 문서:
  - `docs/performance.md`
  - `docs/autofix_safety.md`
  - `docs/encoding_policy.md`

## 8. 인코딩 규칙 (중요)

- 텍스트 소스/문서는 UTF-8 고정
- `.editorconfig` 기준 준수
- 인코딩 이상 발생 시 전체 재저장보다 손상 구간만 복구 후 diff 검토

