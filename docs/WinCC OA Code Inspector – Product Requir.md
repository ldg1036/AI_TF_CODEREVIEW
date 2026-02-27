# WinCC OA Code Inspector 제품 요구사항(PRD) (v3.0)

마지막 업데이트: 2026-02-27 (현재 구현 기준)

이 문서는 WinCC OA Code Inspector의 기능 요구사항, 비기능 요구사항, 운영 정책을 현재 구현 상태 기준으로 정리한다.

## 1. 제품 목표

1. WinCC OA 코드와 관련 텍스트를 빠르게 분석하여 코드리뷰 효율을 높인다.
2. 정적 규칙, CtrlppCheck, AI 리뷰를 한 화면에서 비교/검토할 수 있게 한다.
3. 승인형 자동수정(diff 기반)으로 반복 작업을 줄이되 안전성을 유지한다.

## 2. 범위 (In Scope)

- WinCC OA `.ctl` 분석
- 변환된 `.pnl/.xml -> *_txt` 분석 흐름
- P1(휴리스틱), P2(CtrlppCheck), P3(AI 리뷰)
- HTML/Excel/Annotated TXT 리포트
- HTTP API + 로컬 UI
- Diff 승인형 source autofix (`.ctl`)

## 3. 범위 제외 (Out of Scope)

- `.pnl/.xml` 원본 직접 자동수정
- 무승인 자동적용
- 대규모 서버/분산 처리 전용 아키텍처
- 외부 SaaS LLM 강제 의존

## 4. 기능 요구사항 (FR)

### FR-01. 파일 선택 및 분석
- 사용자는 파일 목록에서 분석 대상을 선택할 수 있어야 한다.
- 선택 파일 검증 실패 시 명확한 오류를 반환해야 한다.

### FR-02. 다중 분석 결과 통합 표시
- P1/P2/P3 결과를 통합 UI에서 필터링할 수 있어야 한다.
- 코드뷰어 라인 점프가 virtualization 환경에서도 동작해야 한다.

### FR-03. 성능 관측
- `/api/analyze` 응답에 성능 메타데이터(`metrics`)가 포함되어야 한다.
- 캐시/LLM/Ctrlpp 호출 정보가 확인 가능해야 한다.

### FR-04. 리포트 생성
- Annotated TXT, HTML, Excel 산출물을 제공해야 한다.
- Excel 지연 생성(`defer_excel_reports`) 및 flush API를 지원해야 한다.

### FR-05. AI 리뷰 반영
- `REVIEWED.txt` 반영과 source autofix 적용 경로를 구분해야 한다.
- source autofix는 diff preview 후 승인 적용이어야 한다.

### FR-06. 자동수정 안전성
- `.ctl`만 적용 허용
- hash/anchor 검증
- 기본 문법 precheck
- heuristic 회귀검사
- optional Ctrlpp 회귀검사
- 백업/감사로그/원자적 쓰기

### FR-07. 하이브리드 자동수정 제안
- `llm`, `rule`, `auto` generator 선택을 지원해야 한다.
- `auto`는 rule-first, llm-fallback 정책을 따른다.

### FR-08. 자동수정 품질 지표
- apply 응답에 `quality_metrics`를 포함해야 한다.
- 실패 시 `error_code`를 반환해야 한다.
- 세션 기준 통계(`/api/autofix/stats`)를 제공해야 한다.

## 5. 비기능 요구사항 (NFR)

### NFR-01. 성능
- 로컬 데스크톱 기준 중간 배치(5~50 파일)에서 실사용 가능한 응답성을 유지해야 한다.
- UI 렌더링은 virtualization 기반으로 freeze를 최소화해야 한다.

### NFR-02. 안정성
- LLM/Ctrlpp 실패 시 가능한 범위 내 fail-soft 처리
- 동시 요청 간 세션/리포트 혼선 방지

### NFR-03. 유지보수성
- 오케스트레이션/분석/API/UI 책임 분리
- 타입 명확화(TypedDict 등)로 IDE 추론 및 리팩터링 안정성 확보

### NFR-04. 운영성
- 성능 baseline/임계치 관리 문서 제공
- Ctrlpp 통합 스모크, Playwright UI 벤치 스크립트 제공
- 인코딩 정책(UTF-8 고정) 준수

## 6. 운영 기본값(현재 정책)

- 자동수정 대상: `.ctl`
- 자동수정 방식: Diff 승인형
- LLM provider 기본: 로컬/사내(예: Ollama)
- 성능 판단 기준: 중간 배치 중심
- 인코딩 규칙: UTF-8 고정 (`.editorconfig`, `docs/encoding_policy.md`)

## 7. 성공 기준

- 분석 기능(P1/P2/P3)이 안정적으로 동작한다.
- 성능 적정성을 metrics/UI benchmark로 수치 설명 가능하다.
- source autofix가 검증/백업/감사로그를 포함한 승인형 흐름으로 동작한다.
- 핵심 회귀 테스트와 통합 스모크(환경 의존 포함)가 운영 가능하다.

