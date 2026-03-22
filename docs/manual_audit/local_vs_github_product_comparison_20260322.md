# 로컬 프로그램 vs GitHub 프로그램 제품 비교 보고서

작성 시각: 2026-03-22 KST

대상

- 로컬 제품: `D:\AI_TF_CODEREVIEW-main`
- GitHub 저장소: `https://github.com/3914590/https-github.com-ldg1036-AI_studio_WInccOA`

## 한눈에 보는 결론

- 현재 로컬 프로그램을 기준 제품으로 유지해도 된다.
- GitHub 저장소는 로컬 프로그램의 상위 버전이라기보다, `WinCC OA 리뷰를 빠르게 체험하는 AI Studio/Vite 단일 앱`에 가깝다.
- 로컬 제품은 `규칙 검출`, `운영 검증`, `보고서`, `triage`, `autofix`, `실브라우저 smoke`, `release gate`까지 포함한 운영형 제품이고, GitHub 저장소는 `프런트 단독 UX + Gemini 보강`에 강점이 있다.
- 따라서 권장 전략은 `로컬 제품 유지 + GitHub 저장소를 UX/아이디어 소스처럼 부분 참고`이다.

최종 판정

- 기준 제품: 로컬 프로그램
- 참고 소스: GitHub 저장소
- 직접 병합 필요성: 낮음
- 부분 이식 가치: 높음

## 제품 구조 비교 표

| 항목 | 로컬 프로그램 | GitHub 저장소 | 판정 |
| --- | --- | --- | --- |
| 런타임 구조 | Python backend + frontend + tools + reports + config | Vite/React 단일 앱 + Gemini service | 로컬 우세 |
| 엔트리포인트 | `python backend/server.py`, `python backend/main.py` | `npm run dev` | 용도 다름 |
| 입력 처리 | `.ctl`, `_pnl.txt`, `_xml.txt`, raw `.txt` 옵션, canonical normalization | 코드 텍스트 직접 입력 중심 | 로컬 우세 |
| 결과 산출 | UI, HTML, Excel, REVIEWED.txt, diff/apply | 화면 내 리뷰/리팩터링 코드/문서/플로우차트 | 로컬 우세 |
| 운영 도구 | release gate, UI smoke, benchmark, Ctrlpp smoke, config alignment | build/lint/dev 수준 | 로컬 우세 |
| AI 의존성 | Ollama optional, fail-soft | Gemini API 중심, 실질적 핵심 의존 | 로컬 우세 |

핵심 차이

- 로컬은 `실사용 운영형 제품`이고, GitHub 저장소는 `프런트 중심 프로토타입/데모형 제품`에 가깝다.
- GitHub 저장소 최상위 구조는 `.git`, `docs`, `src`가 핵심이고, 로컬은 `backend`, `frontend`, `tools`, `Config`, `CodeReview_Report`, `workspace`까지 포함한다.
- GitHub 저장소는 `src/services/ruleEngine.ts`, `src/services/gemini.ts`, `src/App.tsx` 중심의 단일 실행 흐름이다.

## 기능 비교 표

| 기능 | 로컬 프로그램 | GitHub 저장소 | 판정 |
| --- | --- | --- | --- |
| P1 정적 규칙 검출 | 있음, P1 matrix와 sample audit로 검증 | 있음, `src/rules.json` + 프런트 rule engine | 로컬 우세 |
| P2 Ctrlpp 연동 | 있음 | 없음 | 로컬 압승 |
| P3 Live AI | 있음, optional/fail-soft | 있음, Gemini 중심 | 용도 다름 |
| 보고서 | Excel/HTML/REVIEWED.txt | 화면 결과 중심 | 로컬 우세 |
| triage/suppress | 있음 | 없음 | 로컬 우세 |
| rules 관리 | list/create/replace/delete/import/rollback | 정적 `rules.json` 편집 수준 | 로컬 우세 |
| autofix prepare/apply | 있음, semantic guard/quality gate 포함 | refactoredCode 제안 중심 | 로컬 우세 |
| 추가 AI 도구 | 비교/prepare/autofix | 문서화, 유닛테스트 생성, 포맷팅, 플로우차트 | GitHub 일부 우세 |
| UX 진입 장벽 | 상대적으로 높음 | 예제 코드 포함, 바로 체험 가능 | GitHub 우세 |

## 검출 / AI / 보고서 / 운영 성숙도 비교

### 1. 제품 목적과 사용자 흐름

로컬 현재 상태

- 파일 선택, 분석, 비교, triage, Excel 생성, autofix, 운영 검증까지 하나의 제품 흐름으로 이어진다.
- 최근 감사 기준으로 대표 샘플 검출과 gate가 모두 녹색이다.

GitHub 저장소 상태

- `src/App.tsx` 기준으로 코드 입력 후 리뷰, 성능 분석, 코드 완성, 문서 생성, 플로우차트 생성 같은 생성형 UX가 중심이다.
- 예제 코드가 여러 개 내장되어 있어 초심자가 바로 써보기 쉽다.

차이 핵심

- 로컬은 `실제 프로젝트 처리`, GitHub는 `단일 코드 블록 체험`에 초점이 맞춰져 있다.

로컬 기준 판정

- 운영 제품 기준에서는 로컬이 더 완성도가 높다.
- 첫인상과 체험성은 GitHub 쪽이 더 좋다.

권장 액션

- GitHub의 `예제 기반 빠른 시작 UX`만 로컬 onboarding에 부분 도입한다.

### 2. 규칙 검출 구조

로컬 현재 상태

- P1/P2/P3 구조가 분리되어 있고, P1은 규칙 정의/health/matrix/sample audit로 검증된다.
- recent release gate 기준 `p1_rule_matrix PASS`, `p1_sample_audit PASS`, `ui_real_smoke PASS`, `canonical_boundary_parity PASS`다.

GitHub 저장소 상태

- `src/services/ruleEngine.ts`가 `src/rules.json`을 읽어 프런트 내부에서 규칙을 수행한다.
- regex, and/or/not/scope/if, 일부 composite/function 기반 규칙은 있지만, 실행 환경은 프런트 단일 경로다.

차이 핵심

- GitHub는 규칙 엔진이 있어도 `프런트 내 정적 엔진` 수준이고, 로컬은 `운영형 백엔드 검출기 + 검증 체계`다.

로컬 기준 판정

- WinCC OA 코드리뷰 정확도와 운영 신뢰성 기준으로 로컬이 명확히 우세하다.

권장 액션

- GitHub 쪽 규칙 JSON 표현 방식은 `룰 미리보기/샘플 설명 UI` 아이디어로만 참고한다.

### 3. AI 연동 방식

로컬 현재 상태

- Ollama 기반 local AI를 optional하게 붙이고, 실패 시 fail-soft로 동작한다.
- live AI generate/compare/prepare는 지원하지만 apply는 conservative gate로 보수적으로 막는다.

GitHub 저장소 상태

- `src/services/gemini.ts`가 핵심이며, `GEMINI_API_KEY`가 사실상 필수다.
- Gemini가 리뷰, 성능 분석, 포맷팅, 유닛테스트, 문서, 플로우차트 생성까지 맡는다.

차이 핵심

- 로컬은 `AI 보조`, GitHub는 `AI 중심`이다.

로컬 기준 판정

- 기업형/내부망/운영형 제품으로는 로컬 구조가 더 안전하다.
- 데모성과 생성형 확장성은 GitHub 쪽이 더 풍부하다.

권장 액션

- GitHub의 `문서 생성`, `유닛테스트 생성`, `정적 플로우차트 생성`은 로컬에 추가 가치가 있다.
- Gemini 단일 의존 구조는 그대로 가져오지 않는다.

### 4. 운영/검증 성숙도

로컬 현재 상태

- 최신 gate 기준 `15 passed, 0 failed`다.
- backend unittest, verification profile, config alignment, template coverage, p1 rule matrix, sample audit, frontend unit, Ctrlpp smoke, UI benchmark, UI real smoke, live_ai_ui까지 운영 검증이 있다.

GitHub 저장소 상태

- `package.json` 기준 `dev`, `build`, `preview`, `lint`만 있고, 전용 gate나 운영 smoke, benchmark 체계는 확인되지 않았다.
- 탐색 기준으로 `src/components` 7개, `src/services` 3개 수준의 소형 앱이다.

차이 핵심

- GitHub는 빌드 가능한 앱이고, 로컬은 검증 가능한 제품이다.

로컬 기준 판정

- 운영 성숙도는 로컬이 압도적으로 높다.

권장 액션

- GitHub 저장소는 운영형 기준이 아니라 `아이디어 프로토타입` 기준으로만 참고한다.

### 5. 확장성과 유지보수성

로컬 현재 상태

- 백엔드/프런트/도구가 분리되어 있고 rules 관리, normalization, reports, audit 경로가 있다.
- 반면 mixin 기반 백엔드는 파일 수가 많고, 프런트 orchestration 파일은 아직 큰 편이다.

GitHub 저장소 상태

- 소규모 React 앱으로 구조는 단순하다.
- 단순한 대신 백엔드, 지속 저장, 운영용 상태 관리, 다중 채널 출력이 없다.

차이 핵심

- GitHub는 작아서 이해하기 쉽고, 로컬은 크지만 제품 책임을 더 많이 감당한다.

로컬 기준 판정

- 유지보수 단순성은 GitHub가 낫지만, 기능 책임까지 포함하면 로컬 구조가 더 적합하다.

권장 액션

- GitHub의 `작은 컴포넌트 중심 UI 구성`은 참고하되, 로컬의 백엔드/운영 분리는 유지한다.

### 6. 도입 가치

로컬 현재 상태

- 실사용 제품 기준 기능 대부분을 이미 보유한다.

GitHub 저장소 상태

- 데모성 기능과 초심자 친화 UX가 강하다.

차이 핵심

- GitHub 저장소에서 가져올 가치는 `검출 엔진`이 아니라 `보여주는 방식`과 `생성형 부가도구`에 있다.

로컬 기준 판정

- 직접 합치는 것보다 `아이디어 선별 이식`이 맞다.

권장 액션

- 부분 이식만 진행한다.

## 로컬이 우세한 부분

1. 실제 WinCC OA 프로젝트 입력 경계 처리
2. P1/P2/P3 다층 구조와 규칙 정확도 검증 체계
3. Excel/HTML/REVIEWED.txt 등 다중 산출물
4. release gate, smoke, benchmark, full audit 같은 운영 체계
5. CtrlppCheck 연동과 triage/autofix 안전장치

## GitHub 쪽에서 가져올 만한 부분

1. 예제 코드 기반 빠른 시작 UX
2. 코드 리뷰 외 `문서 생성`, `유닛 테스트 생성`, `플로우차트 생성` 같은 보조 도구
3. split/unified diff를 바로 체험하는 단순한 화면 구성
4. “규칙 결과 + AI 보강 결과”를 초보자에게 이해시키는 단일 화면 흐름
5. 정적 플로우차트 생성처럼 AI 없이도 쓸 수 있는 부가 기능

## 실제로 가져올 기능 Top 5

1. 초심자용 예제 코드 preset
2. 정적 플로우차트 생성 기능
3. 코드 기반 문서 초안 생성
4. 단일 파일 데모 모드
5. 리뷰 결과의 split/unified diff 체험 UX 단순화

## 굳이 합치지 말아야 할 요소 Top 5

1. Gemini API 단일 의존 구조
2. 프런트 내부 정적 규칙 엔진을 로컬 백엔드 대신 쓰는 방식
3. 백엔드 없는 단일 앱 구조
4. 운영 검증 없이 build/lint 중심으로 끝나는 품질 체계
5. 결과 저장/보고서/triage 없이 화면 중심으로만 끝나는 흐름

## 현재 로컬 프로그램 개선 제안

### 즉시 반영 가치가 높은 항목

1. 시작 화면에 `예제 코드 열기`와 `빠른 체험 모드` 추가
2. Live AI 외에 `정적 플로우차트 생성` 보조 메뉴 추가
3. `문서 초안 생성`, `유닛 테스트 초안 생성` 같은 비파괴 AI 도구 추가
4. 대시보드보다 더 가벼운 `single-file review mode` 추가
5. 신규 사용자를 위한 “무엇을 먼저 눌러야 하는지” 단계형 UX 보강

### 가져오지 않는 편이 나은 항목

1. Gemini 전용 의존 구조
2. rules.json만으로 끝나는 프런트 단독 규칙 엔진
3. 서버/리포트/게이트 없는 단순 앱 구조
4. WinCC OA 실제 입력 파일 경계를 생략하는 설계
5. 운영 성숙도보다 데모성을 우선하는 기본 구조

### 유지보수 관점의 로컬 개선 포인트

1. 프런트 orchestration 파일을 더 잘게 나누기
2. 백엔드 mixin 계약을 기능 단위 service 계층으로 더 명확히 정리하기
3. onboarding/demo 모드를 별도 계층으로 두어 운영 UI와 분리하기
4. 보조 AI 기능은 `generate-only`와 `apply-capable`를 더 명확히 구분하기
5. 비교 대상 GitHub 앱처럼 “작게 체험 가능한 흐름”을 로컬 안에 별도 모드로 제공하기

## 종합 결론

- 로컬 프로그램은 현재 기준으로 `WinCC OA 운영형 코드리뷰 제품`으로 유지할 가치가 충분하다.
- GitHub 저장소는 `프런트 UX와 생성형 보조기능 아이디어 소스`로 보는 것이 가장 정확하다.
- 두 제품을 통째로 합치는 것보다, GitHub의 장점인 `빠른 체험성`, `문서/유닛테스트/플로우차트 생성`, `초심자 친화 UX`만 선별해서 로컬 제품에 붙이는 전략이 가장 효율적이다.
