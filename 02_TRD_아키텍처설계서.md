# TRD: 기술/아키텍처 설계서 (v2.3 최신 반영)

관련 문서: `01_PRD.md`(요구사항), `03_정적분석_룰카탈로그.md`, `04_AI_프롬프트_설계서.md`

---

## 1. 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│                     사용자 UI (Desktop)                    │
│   파일선택 / 결과트리 / 위반목록 / AI가이드 / Diff뷰어 / 설정  │
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│                  App Core (Orchestrator)                  │
│   요청 라우팅, 파이프라인 단계 실행, 진행상태/취소 관리        │
└──┬───────────┬───────────────┬───────────────┬────────────┘
   │           │               │               │
┌──▼───┐   ┌───▼────┐   ┌──────▼──────┐  ┌─────▼─────┐
│ 파서  │   │ 정적룰  │   │  AI 리뷰    │  │ WinMerge  │
│ 모듈  │   │ 엔진    │   │  엔진       │  │ 연동 모듈  │
│(PNL/  │   │(Excel  │   │(Provider   │  │(subprocess │
│ XML/  │   │ 룰정의) │   │ 추상화,    │  │ + report   │
│ CTL)  │   │        │   │ 프롬프트)   │  │ 파서)      │
└──┬───┘   └───┬────┘   └──────┬──────┘  └─────┬─────┘
   │           │               │               │
   └───────────┴───────┬───────┴───────────────┘
                        │
              ┌─────────▼──────────┐
              │  결과 통합 / 리포트  │
              │  생성기 (JSON/HTML) │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  자동수정 파일 생성  │
              │  (옵션, 원본 불변)   │
              └────────────────────┘
```

핵심 설계 원칙:
- **원본 불변(Immutability)**: 어떤 단계에서도 사용자의 원본 파일을 덮어쓰지 않는다. 모든 산출물은 별도 파일/리포트로 생성된다.
- **단계별 독립 실행 가능**: 정적검사만/AI리뷰만/Diff만 개별적으로도 동작해야 하며, AI나 WinMerge가 없어도 정적검사 결과는 제공되어야 한다(Graceful Degradation).
- **Provider 추상화**: 사내 AI 모델(Gemma 계열)의 API가 변경/교체되어도 코어 로직이 영향받지 않도록 인터페이스로 분리한다.

---

## 2. 기술 스택 (제안)

| 영역 | 제안 기술 | 비고 |
|---|---|---|
| 언어/런타임 | Python 3.12 | Windows 10/11 64-bit 기준 |
| 패키지/환경관리 | `uv` 또는 `poetry` | 재현 가능한 빌드 |
| XML/설정 파싱 | `lxml` 또는 `xml.etree.ElementTree` | PNL이 XML 유사구조인 경우 활용, 아니면 커스텀 파서 |
| CTL 파서 | 1차: 정규식 기반 경량 파서 / 2차 고도화: `lark` 등 문법 파서 | 정확도-개발비용 트레이드오프, Phase별 단계적 고도화 |
| 인코딩 감지 | `chardet` 또는 `charset-normalizer` | 사내 파일 EUC-KR/UTF-8 혼재 가능성 대응 |
| 룰 엔진 | 자체 구현 (BaseRule 추상클래스 + Excel Rule Compiler) | |
| AI 연동 | `httpx`(비동기) | 사내 REST 엔드포인트 호출, 기본 타임아웃 60초·최대 3회 재시도 |
| GUI | **`pywebview` + HTML/CSS/JS (Vanilla JS 기본, 필요 시 Alpine.js만 허용)** | 확정. WinMerge HTML 리포트 임베딩 편의성, Diff/탭 UI 구현 용이성 근거 |
| 패키징 | `PyInstaller` (`--onedir` 기본, `--onefile` 선택) | 사내 배포용 데스크톱 패키지 |
| Diff 연동 | WinMerge CLI(`WinMergeU.exe`) + `subprocess` | Windows 전용, 미설치 시 `difflib` 폴백 |
| 테스트 | `pytest` | |
| 로깅 | 표준 `logging` + 파일 핸들러(로테이션) | |

> **결정 확정**: GUI는 `pywebview` + HTML/CSS/JS로 확정합니다(PyQt6/Tkinter/Streamlit 등은 채택하지 않음).
> 근거: (1) WinMerge가 생성하는 HTML 리포트를 변환 없이 그대로 임베딩 가능, (2) 위반목록/AI가이드/구조리뷰/
> Diff/Errors 등 다수 탭 UI를 웹 기술로 빠르게 구성 가능, (3) Python 로직은 `pywebview`의 `js_api` 바인딩으로
> 프론트엔드 JS에서 직접 호출 가능해 별도 백엔드 서버(FastAPI 등)가 불필요. 상세 구현 지침은
> `05_개발로드맵_바이브코딩_태스크.md` Phase 8 참조.

---

## 3. 모듈/디렉토리 구조 (제안)

```
wincc_reviewer/
├── app/
│   ├── main.py                      # 진입점
│   ├── ui/                          # UI 레이어 (pywebview + Vanilla HTML/CSS/JS)
│   │   ├── views/
│   │   └── assets/
│   ├── core/
│   │   ├── pipeline.py              # Orchestrator: 전체 파이프라인 실행/취소/진행률
│   │   ├── models.py                # IR, Violation, ReviewResult 등 데이터클래스
│   │   ├── parser/
│   │   │   ├── base_parser.py
│   │   │   ├── pnl_parser.py
│   │   │   ├── xml_parser.py
│   │   │   └── ctl_parser.py
│   │   ├── input_normalization/
│   │   │   ├── service.py          # PNL/XML → canonical text
│   │   │   ├── encoding_detector.py
│   │   │   └── models.py
│   │   ├── rules/
│   │   │   ├── base_rule.py
│   │   │   ├── rule_engine.py
│   │   │   ├── excel_rule_loader.py # 엑셀 입력/레거시 양식 어댑터
│   │   │   ├── excel_rule_compiler.py # 엑셀 → 내부 RuleDefinition 컴파일러
│   │   │   ├── rule_schema_validator.py # 엑셀 구조/값 검증
│   │   │   ├── rule_cache.py         # 정상 컴파일 룰셋 캐시/롤백
│   │   │   ├── applicability_mapper.py # 체크리스트 항목 ↔ 실행 룰 묶음
│   │   │   └── ruleset/             # 내부 캐시 산출물
│   │   ├── ai/
│   │   │   ├── provider_base.py     # AIProvider 추상 인터페이스
│   │   │   ├── gemma_provider.py    # 사내 Gemma REST 클라이언트 구현체
│   │   │   ├── mock_provider.py     # 개발/테스트용 목업
│   │   │   ├── prompts/             # 프롬프트 템플릿 (jinja2 등)
│   │   │   ├── review_stage2.py     # 룰위반 기반 가이드 로직
│   │   │   ├── review_structural.py # 전체 구조 리뷰 로직 (청킹/맵리듀스)
│   │   │   └── autofix.py           # 자동수정 생성 로직
│   │   ├── diff/
│   │   │   ├── winmerge_runner.py   # subprocess 래퍼
│   │   │   ├── winmerge_report_parser.py
│   │   │   └── difflib_fallback.py
│   │   ├── runtime/
│   │   │   ├── session_store.py     # run_id, TTL/LRU
│   │   │   ├── locks.py              # per-file/per-run lock
│   │   │   └── workspace.py          # 격리 작업 디렉터리
│   │   └── report/
│   │       └── report_builder.py    # 통합 리포트(JSON/HTML) 생성
│   └── config/
│       ├── (코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx  # Client 룰 원천
│       ├── (코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx  # Server 룰 원천
│       ├── settings.yaml            # AI 엔드포인트, WinMerge 경로 등
│       └── ruleset_profiles/        # 프로젝트별 룰 프로파일
├── tests/
│   ├── fixtures/                    # 샘플 PNL/XML/CTL 파일 및 결과서 양식
│   └── ...
├── docs/                            # 본 문서 세트
└── build/                           # PyInstaller 빌드 산출물
```

---

## 4. 데이터 흐름 (End-to-End 파이프라인)

1. **파일 입력**: 단일/다중 파일 또는 폴더 선택
2. **타입 판별 & 룰셋 매핑 (Rule Target Routing)**:
   - 파일 확장자에 따른 룰셋 자동 분류: `.pnl`, `.xml` ➔ Client 결과서 룰셋 / `.ctl` ➔ Server 결과서 룰셋
   - 사용자 선택 오버라이드(Override): 사용자가 UI/설정에서 수동으로 Client 또는 Server 기준을 지정한 경우 사용자 설정 적용
3. **엑셀 단일 원천 기반 룰 컴파일 및 갱신**:
   - 사용자가 편집하는 Client/Server 엑셀 파일의 SHA256과 문서 버전을 체크한다.
   - 변경 시 `excel_rule_loader.py`가 입력을 읽고 `excel_rule_compiler.py`가 검증된 행만 내부 `RuleDefinition[]`으로 정규화한다.
   - 컴파일 실패 시 직전 정상 룰셋을 유지하고, 오류가 해결된 뒤에만 새 룰셋을 원자적으로 적용한다.
   - 내부 정규화 결과는 캐시용 산출물이며 사용자가 직접 편집하지 않는다.
4. **입력 정규화 및 파싱 → IR 생성**
   - PNL/XML은 필요 시 canonical text로 변환하고 원본·canonical 해시와 인코딩을 기록한다.
   - CTL: 함수 목록, 전역/지역 변수, 호출관계, 원본 라인 매핑 정보
   - PNL: 도형(shape) 목록, 이벤트별 임베디드 CTRL 스크립트
   - XML: 트리 구조 + (해당 시) 스키마 매칭 여부
5. **체크리스트 적용성 매핑** → 하나의 checklist item에 연결된 여러 `rule_id`와 `automation_mode`를 확인한다.
6. **1차 정적 룰 검사** → `Violation[]` (rule_id, severity, file, line, message, snippet)
7. **(옵션) 2차 AI 리뷰**
   - a) 룰 위반 기반 가이드: 위반 항목 + 주변 코드 컨텍스트 → AI에 질의 → 수정 가이드 생성
   - b) 전체 구조 리뷰: 파일 전체(필요 시 청킹) → AI에 질의 → 구조/설계 피드백 생성
8. **(옵션) 자동수정 파일 생성**: AI에 수정 요청 → 코드 추출 → `원본명_ai_fixed.확장자`로 별도 저장 (원본 불변)
9. **(옵션) WinMerge 비교**: 원본 vs 수정본 실행 → 리포트 생성(XML/HTML) → 실제 변경 라인만 추출
10. **결과 통합**: 룰위반 + 체크리스트 적용성 + AI가이드 + 구조리뷰 + 실변경 Diff를 하나의 리포트로 통합
11. **UI 표시 및 내보내기**: 통합 리포트, 수정 파일, WinMerge 리포트 원본까지 저장/내보내기

---

## 5. 상세 기능 설계

### 5.1 파일 파서 모듈
- **선행 필수 태스크(스파이크)**: 실제 사내 WinCC OA 프로젝트의 PNL/CTL/XML 샘플을 다수 확보하여
  구조를 실제로 분석한다. PNL이 완전한 XML인지, 바이너리/혼합 포맷인지에 따라 파서 전략이 크게 달라진다.
- CTL 파서: 1차로 정규식/토큰 기반 경량 파서(함수 선언부, 전역변수 선언, 주석, 문자열 리터럴 식별)로
  시작하고, 이후 필요 시 `lark` 등을 이용한 정식 문법 파서로 고도화한다.
- PNL 파서: 도형별 이벤트 핸들러에 포함된 CTRL 스크립트를 추출해 CTL 파서와 동일한 방식으로 재사용 분석한다.
- 공통: 인코딩 자동 감지(EUC-KR/UTF-8 등 혼재 가능성) 및 파싱 실패 시 원본 라인은 보존한 채 "파싱불가"
  상태로 표시하고 파이프라인 전체가 중단되지 않도록 한다.

### 5.2 정적 룰 엔진
- `BaseRule` 추상클래스: `check(ir) -> list[Violation]`
- **엑셀 단일 원천 및 내장 Rule Compiler**:
  - `config/` 디렉토리의 Client/Server 엑셀 파일을 실행 룰의 단일 원천으로 사용한다.
  - `ExcelRuleCompiler`가 체크리스트형 기존 결과서 시트와 선택적인 `RuleDefinitions` 시트를 모두 지원한다. 기존 결과서에서 실행 메타데이터가 없는 행은 `manual_review`로 정규화한다.
  - **룰 자동 업데이트 파이프라인**: SHA256과 문서 버전을 감지하여 변경 시 검증 → 컴파일 미리보기 → 적용 순서로 갱신한다. 컴파일 오류가 발생하면 직전 정상 캐시를 유지한다.
- **확장자 기반 자동 분류 및 사용자 오버라이드 (Rule Target Router)**:
  - 파일 확장자에 맞춰 타겟 룰셋을 기본 자동 분류 적용한다:
    - `.pnl`, `.xml` ➔ Client 코드리뷰 결과서 룰셋
    - `.ctl` ➔ Server 코드리뷰 결과서 룰셋
  - 사용자가 UI 설정에서 명시적으로 특정 결과서 기준(Client vs Server)을 지정한 경우 사용자 선택(Override) 옵션이 자동 분류 결과보다 우선 적용된다.
- 룰 정의는 사용자가 편집하는 엑셀에서 관리한다. 앱 내부에서는 패턴 매칭형, 내장 checker형, 수동 검토형으로 정규화한다.
- 심각도: Critical / High / Medium / Low / Info (상세는 `03_정적분석_룰카탈로그.md`)
- 룰셋은 프로젝트/팀별 프로파일로 on/off 구성 가능해야 한다.

#### Checklist Applicability Map

`parsed_rules`는 엑셀 체크리스트 행과 분해된 check point를 보존하고, `review_applicability`는 각 체크리스트 항목에 연결된 실행 룰 목록과 적용 모드를 보존한다.

```yaml
checklist_item: "DP Query 최적화 구현"
automation_mode: auto_violation_only
required_rule_ids:
  - PERF-02
  - PERF-02-WHERE-DPT-IN-01
  - DB-01
  - DB-ERR-01
  - SEC-01
manual_only: false
```

적용성 매핑은 컴파일된 내부 캐시이며, 엑셀의 기술 메타데이터·매핑 시트에서 생성한다. `required_rule_ids` 중 미존재 룰이 있으면 `mapping_incomplete`로 표시한다.

#### Excel Rule Compiler 계약

기존 체크리스트의 시각적 형식은 유지한다. `대분류`, `중분류`, `소분류`, `검증 조건`, `비고` 열을 기본 입력으로 사용하고, 다음 기술 메타데이터 열은 기존 열의 우측 또는 숨김 영역에 추가할 수 있다. 별도 `RuleDefinitions` 시트는 선택사항이다.

| 열 | 필수 | 설명 |
|---|---:|---|
| `rule_id` | 권장 | 전역 유일한 룰 ID. 비어 있으면 원본 시트·셀·조건의 안정적 해시로 생성 |
| `enabled` | 예 | TRUE/FALSE |
| `file_types` | 권장 | CTL, PNL, XML 중 하나 이상. 비어 있으면 대상 시트/파일 프로파일 사용 |
| `category` | 권장 | NAM, ERR, RES 등. 기본 체크리스트의 대분류·중분류에서 보조 생성 |
| `severity` | 권장 | Critical/High/Medium/Low/Info. 자연어로 추론하지 않음 |
| `checker_type` | 예 | regex / builtin / manual. 메타데이터가 없으면 manual |
| `checker_key` | 조건부 | 내장 checker 이름 또는 정규식 키 |
| `message` | 예 | 위반 메시지 |
| `fix_hint` | 아니오 | AI 가이드에 전달할 수정 힌트 |
| `autofix_allowed` | 예 | 기본 FALSE |
| `rule_version` | 예 | 변경 시 증가 |

`checker_type=manual`인 행은 자동 NG를 만들지 않고 검토 대기 결과만 생성한다. 엑셀의 자연어 `검증 조건`만으로 임의의 Python 코드를 생성하거나 실행하지 않는다. 체크리스트 행을 추가하는 것만으로 자동검사 알고리즘이 생기는 것은 아니며, 자동검사는 기존 내장 checker 또는 정규식 유형을 지정한 경우에만 수행한다.

#### 체크리스트 행과 검사 로직 연결 계약

검사 로직 연결은 다음 우선순위로 결정한다.

1. 엑셀 행의 `checker_type`과 `checker_key`를 명시적으로 사용한다.
2. 명시값이 없으면 기존 버전 호환을 위한 `legacy_mapping_profile`의 안정적인 `source_key` 매핑을 사용한다.
3. 매핑을 찾지 못하거나 설정이 불완전하면 `manual_review`로 처리한다. 자연어 문장을 임의의 코드로 실행하지 않는다.

```text
Excel row → source_key / rule_id 생성 → checker_type 판정
→ builtin registry 또는 regex compiler 조회
→ IR에 대한 check 실행 → Violation[] 또는 ManualReview[] 생성
```

`source_key`는 파일명이나 행 번호가 아니라 `workbook_role + sheet_name + rule_id` 조합으로 만든다. 자동검사 대상 행은 엑셀에 `rule_id`를 반드시 명시한다. 기존 v2.0 행처럼 ID가 없는 항목은 자동 생성 ID와 변경 경고를 표시하고, 사용자가 안정적인 ID를 확정하기 전까지 `manual_review`로 처리한다.

**내장 checker registry 계약**

내장 checker는 코드에 등록된 안전한 검사 함수 목록이며 엑셀에는 함수 경로를 직접 입력하지 않는다.

| checker_key | 파일 타입 | 입력 IR | 검사 예 |
|---|---|---|---|
| `ctl.dp_return_value` | CTL | 호출 AST/토큰 | DP 함수 반환값 검사 여부 |
| `ctl.dp_batch_and_change_guard` | CTL/PNL | 호출·데이터흐름 IR | 일괄 처리 및 변경 시에만 DP 쓰기 여부 |
| `ctl.dp_connect_pair` | CTL/PNL | 호출·이벤트 IR | connect/disconnect 대응 여부 |
| `ctl.loop_delay` | CTL | 제어흐름 IR | 무한 루프 내 delay 여부 |
| `ctl.hardcoded_dp_name` | CTL/PNL | 문자열·호출 IR | DP 이름 하드코딩 여부 |
| `xml.required_elements` | XML | XML 트리 IR | 필수 요소·속성 누락 여부 |
| `pnl.empty_handler` | PNL | 도형·이벤트 IR | 빈 이벤트 핸들러 여부 |

각 checker는 `check(parsed_file, rule_definition) -> list[Violation]` 계약을 지키며, 지원하지 않는 파일 타입·IR 상태에서는 예외 대신 `unsupported` 상태를 반환한다. checker마다 양성·음성 fixture, 예상 라인, 오탐 가능성, 지원 WinCC OA 버전을 문서화한다.

**정규식 checker 계약**

정규식은 엑셀 메타데이터로 설정한다. `pattern`, 허용된 `flags`, 검사 대상(`code`/`comment`/`string`), `exclude_pattern`, 주변 `line_scope`를 사용하며, 타임아웃·최대 패턴 길이·최대 매칭 수 제한을 둔다. 복잡한 구조·호출 관계·짝 검사에는 정규식 대신 builtin checker를 사용한다.

**레거시 체크리스트 매핑**

기존 양식은 `대분류/중분류/소분류/검증 조건`으로 후보를 식별하고 `legacy_mapping_profile`과 대조한다. 이 프로파일은 프로그램 코드에만 두지 않고 엑셀의 기술 메타데이터 또는 버전관리되는 매핑 시트에서 관리한다. 정확한 매핑표에 등록된 항목만 자동화하며, 자연어 유사도만으로 자동 매핑하지 않는다. 나머지는 `manual_review`로 표시한다.

### 5.3 AI 리뷰 엔진
- `AIProvider` 추상 인터페이스로 사내 Gemma 모델 REST API를 감싼다. 모델 교체/버전업 시 구현체만 교체.
- 세 가지 리뷰 모드는 프롬프트 템플릿과 출력 스키마가 다르므로 별도 모듈로 분리한다
  (`review_stage2.py`, `review_structural.py`, `autofix.py`). 상세 프롬프트는 `04_AI_프롬프트_설계서.md` 참조.
- 컨텍스트 길이 제한 대응: 모델의 실제 컨텍스트 윈도우 확인 후(TBD), 초과 시 함수 단위로 분할하여
  개별 리뷰 후 요약을 통합하는 맵-리듀스 방식을 사용한다.
- **Rate Limit/일시적 오류 대응**: `AIProvider` 공통 계층에 지수 백오프(Exponential Backoff) 재시도
  로직을 구현한다(예: 1초→2초→4초, 최대 N회). 429(Rate Limit)/5xx/타임아웃 등 일시적 오류에 한해
  재시도하며, Stage2 가이드/전체 구조 리뷰/자동수정 세 가지 모드 모두 이 공통 로직을 재사용해 중복
  구현하지 않는다.
- **토큰 한도 방어**: 청크(코드 본문 + 프롬프트 오버헤드) 크기가 모델 최대 컨텍스트의 안전마진
  (예: 70~80%)을 넘지 않도록 사이즈 제한 규칙을 두고, 초과 시 청크를 더 잘게 분할한다. 이 규칙은
  전체 구조 리뷰(맵-리듀스)와 자동수정 생성 양쪽에 동일하게 적용한다.
- 응답은 JSON 스키마를 강제하고, JSON 파싱 실패 시 제한된 횟수 재시도 후 실패하면 원문(raw text)을
  그대로 사용자에게 노출하는 폴백을 둔다. (이 재시도는 위 네트워크/Rate Limit 백오프와는 별개로,
  "정상 응답은 왔으나 JSON 형식이 아닌 경우"에 대한 재시도이다.)

### 5.4 전체 구조 리뷰 기능
- 단일 파일 또는 서로 참조하는 여러 CTL 파일을 묶어 아키텍처/설계 수준 피드백(중복 로직, 함수 분리 필요성,
  순환 참조 가능성, 전역 상태 과다 사용 등)을 제공한다.
- 대용량 대응: 파일이 매우 클 경우 함수 단위로 나눠 개별 리뷰한 뒤, 결과를 다시 AI에 요약 요청하는
  2단계(map → reduce) 처리를 기본으로 한다.

### 5.5 자동 수정 파일 생성 기능
- 기본값은 **OFF**(안전장치). 사용자가 명시적으로 옵션을 켰을 때만 동작한다.
- AI 응답에서 코드 블록만 추출하여 원본과 동일한 확장자로, `원본파일명_ai_fixed.ctl`과 같이 별도 파일로 저장한다.
- 원본 파일은 어떤 경우에도 덮어쓰지 않는다.
- 자동수정 결과는 "그대로 적용 가능"이 아니라 "검토용 초안"이라는 점을 UI 문구로 명확히 안내한다.

### 5.6 WinMerge 연동 Diff 리포트 기능
- WinMerge CLI(`WinMergeU.exe`)를 `subprocess`로 호출하여 사용자가 선택한 원본·수정 파일 쌍 또는 `_ai_fixed` 파일을 비교하고 리포트를
  생성한다. 정확한 커맨드라인 옵션(예: 리포트 출력 경로/포맷 지정 옵션)은 **사내에 설치된 WinMerge
  버전의 공식 문서/도움말(`WinMergeU.exe /?`, 설정 메뉴의 "보고서 생성" 옵션)로 반드시 재확인**해야 한다
  (버전별 옵션명이 다를 수 있음 — 로드맵 Phase 6의 스파이크 태스크 참조).
- 생성된 리포트(XML/HTML)를 파싱하여 변경된 라인 범위 목록(`DiffChange[]`)을 추출한다.
- 이 실제 변경 라인만을 기준으로, "이 변경이 타당한가/의도치 않은 부작용은 없는가"를 AI에게 재질의하는
  검증 루프를 옵션으로 둔다(4장 6절 프롬프트 참조).
- WinMerge가 설치되어 있지 않은 환경에서는 Python 표준 라이브러리 `difflib`을 이용한 자체 diff로 대체하는
  폴백 경로를 반드시 마련한다(1차 릴리즈에서 Windows 외 환경 지원 시 특히 중요).

### 5.7 리포트 및 결과 뷰어 UI 및 환경 설정 관리
* 좌측 파일 트리와 우측 상세 패널 (위반목록 탭 / AI가이드 탭 / 구조리뷰 탭 / Diff 탭 / 환경 설정 탭) 구조를 제공한다.
* Diff 탭은 WinMerge가 생성한 HTML 리포트를 임베디드 웹뷰로 표시하거나, 추출한 변경 라인을 자체 UI로 렌더링한다.
* 환경 설정 탭은 프로그램 UI 내에서 설정 파일을 동적으로 조회하고 편집할 수 있도록 지원하며, 사용자가 언제든지 저장경로를 변경하거나 다른 YAML 설정 파일을 선택하여 불러올 수 있다. `JSApi` 바인딩을 통해 다음 세 가지 메소드를 제공한다:
  * `get_settings(custom_path: str | None) -> dict`: 기본 또는 지정된 경로의 설정 파일을 읽어 딕셔너리로 반환.
  * `update_settings(new_settings: dict, custom_path: str | None) -> dict`: 사용자 인터페이스에서 수정된 설정 데이터로 사용자 지정 저장 경로의 YAML 파일을 즉시 갱신 및 저장.
  * `list_ai_models(options: dict) -> dict`: 설정된 호스트 및 포트의 로컬 AI 서버 또는 선택된 제공자(provider)에 접속하여 사용 가능한 AI 모델 리스트를 동적 조회하여 반환.

### 5.8 설정 관리
* AI 모델 엔드포인트 및 타임아웃, 모델 선택, 자동수정 옵션 허용 여부, 저장 경로 등을 설정 화면에서 통합 관리한다.
* AI 모델 선택 시 텍스트 수동 입력 대신, AI 제공자 및 로컬 AI 서버와 연결하여 조회된 지원 모델 목록을 콤보박스 선택 리스트 형태로 제공하여 오타 및 호환성 오류를 원천 방지한다.
* 설정 파일의 저장 경로는 기본 `config/settings.yaml` 외에도 사용자가 언제든지 원하는 디렉토리 경로로 자유롭게 변경하여 저장 및 다시 읽기가 가능하다.
* 설정은 즉시 반영되며 기본 타임아웃은 60초, 최대 재시도는 3회로 유지한다.

---

## 6. 데이터 모델 (예시 스키마)

```yaml
Violation:
  rule_id: string          # 예: CTL-RES-001
  severity: enum[Critical, High, Medium, Low, Info]
  file: string
  line_start: int
  line_end: int
  message: string
  snippet: string

AIGuide:
  rule_id: string
  explanation: string
  fix_guide: string
  fixed_snippet: string | null
  confidence: enum[High, Medium, Low]

StructuralReviewResult:
  summary: string
  strengths: list[string]
  issues:
    - category: string
      description: string
      severity: enum[Critical, High, Medium, Low, Info]
      location: string | null
  recommendations: list[string]

DiffChange:
  file: string
  line_start_original: int
  line_end_original: int
  line_start_modified: int
  line_end_modified: int
  change_type: enum[added, removed, modified]

ParseStatus:
  file: string
  status: enum[ok, parse_failed]
  error_message: string | null    # status가 parse_failed일 때 실패 사유

ReviewReport:
  run_id: string
  file: string
  input_sha256: string
  ruleset_version: string
  ruleset_source_sha256: string
  prompt_version: string | null
  model_id: string | null
  app_version: string
  encoding: string
  newline_style: string
  canonical_file_id: string
  canonical_sha256: string | null
  detected_encoding: string
  checklist_applicability: list[ChecklistApplicability]
  metrics: Metrics
  parse_status: ParseStatus
  stage_status: map[string, StageStatus]
  violations: list[Violation]        # parse_status.status == parse_failed 이면 항상 빈 리스트
  ai_guides: list[AIGuide]
  structural_review: StructuralReviewResult | null
  diff_changes: list[DiffChange]
  generated_at: datetime
```

```yaml
StageStatus:
  status: enum[pending, running, succeeded, skipped, failed, cancelled]
  error_code: string | null
  message: string | null
  started_at: datetime | null
  finished_at: datetime | null

ChecklistApplicability:
  checklist_item: string
  automation_mode: enum[auto_full, auto_violation_only, manual]
  required_rule_ids: list[string]
  resolved_rule_ids: list[string]
  missing_rule_ids: list[string]
  status: enum[resolved, mapping_incomplete, manual_review]

Metrics:
  timings_ms: map[string, int]
  cache_hits: map[string, int]
  cache_misses: map[string, int]
  file_count: int
  violation_count: int
  optional_dependencies: map[string, object]
```

> `parse_status.status == parse_failed`인 파일은 룰검사/AI리뷰/Diff 단계를 모두 건너뛰며, 통합 리포트
> 생성 시(`report_builder.py`) 이런 파일들만 모아 별도 **Errors 섹션**으로 표기한다(7장, 로드맵 Phase 7 참조).

---

## 7. 에러 처리 및 로깅

| 상황 | 처리 방침 |
|---|---|
| 파싱 실패 | `parse_status.status = parse_failed`로 표시하고 룰검사/AI리뷰/Diff 단계는 스킵, 파이프라인은 나머지 파일 계속 처리. 최종 리포트에서는 별도 **Errors 섹션**에 실패 사유(`error_message`)와 함께 표기 |
| AI 응답 타임아웃/실패 | 재시도(N회) 후 실패 시 정적룰 결과만으로 리포트 생성, 사용자에게 실패 사실 명시 |
| AI 응답 JSON 파싱 실패 | 재시도 후 실패 시 raw text를 "형식 미보장" 표기로 노출 |
| WinMerge 미설치/실행실패 | `difflib` 폴백 사용 여부를 사용자에게 확인 후 진행 |
| 설정 오류(엔드포인트 등) | 앱 시작 시 검증, 실패 항목은 설정화면에 하이라이트 |

로그는 파일 기반(로테이션)으로 남기며, 최소한 다음을 포함한다: 처리 파일명, 적용 룰셋, AI 호출
성공/실패 여부 및 소요시간, 자동수정 적용 여부.

---

## 8. 배포 전략

- `PyInstaller --onedir`를 기본으로 빌드하고, 리소스·시작시간·백신 오탐을 검증한 경우에만 `--onefile`을 선택한다. 산출물은 사내 배포 채널(공유폴더/사내 소프트웨어센터 등)로 배포한다.
- WinMerge 연동 기능을 포함하는 배포본은 Windows 환경을 전제로 하며, 대상 PC에 WinMerge가 사전 설치되어
  있어야 한다(또는 설치 안내 포함).
- 버전 관리는 시맨틱 버저닝(`v1.0.0`)을 따르고, 자동 업데이트 기능은 1차 범위 밖(향후 검토)으로 한다.

## 9. 보안 고려사항

- 소스코드가 외부 퍼블릭 AI 서비스로 전송되지 않도록, AI 엔드포인트는 사내망 주소만 허용하는 화이트리스트를
  코드 레벨에서 강제한다(설정으로 우회 가능한 구조를 지양).
- 사내 API 통신은 사내 보안 정책에 따른 인증/TLS 방식을 적용한다(세부 스펙은 인프라팀 확인 필요, TBD).
- 로그에 소스코드 스니펫이 과도하게 남지 않도록 로그 레벨/마스킹 정책을 마련한다.

## 10. 성능 고려사항

- 다수 파일 일괄 처리 시 정적 룰 검사는 멀티프로세싱으로 병렬화 가능(AI 호출은 API 동시성 제한 고려해
  별도 큐 관리).
- AI 호출은 상대적으로 비용/시간이 크므로, 동일 파일·동일 코드 스니펫에 대한 재요청을 줄이기 위한
  캐싱(파일 해시 기반)을 고려한다.
- 단계별 `collect`, `normalize`, `parse`, `static_rules`, `ai`, `diff`, `report`, `excel`, `total` 시간을 기록한다.
- 동일 장비·동일 샘플을 최소 3회 실행하고 p95가 기준 대비 20% 이상 악화되면 release gate에서 경고한다.
- Excel 리포트는 기본 지연 생성할 수 있으며, HTML/JSON 결과를 먼저 제공한다.
- 세션은 `run_id`, TTL/LRU, per-file lock을 사용하여 중복 실행과 작업 디렉터리 충돌을 방지한다.

## 11. 구현 계약(Implementation Contract)

### 11.1 파이프라인 단계 상태

각 파일과 각 단계는 다음 상태 중 하나를 갖는다: `pending`, `running`, `succeeded`, `skipped`, `failed`, `cancelled`.
단계 실패는 기본적으로 해당 파일만 실패 처리하며, 배치 전체는 계속 진행한다. 상태에는 `error_code`, `message`, `started_at`, `finished_at`을 함께 기록한다.

### 11.2 파일 및 작업 디렉터리 경계

- 입력 파일은 읽기 전용으로 열고, 원본 경로에는 어떤 단계도 출력하지 않는다.
- 작업 디렉터리는 실행마다 새로 생성하며 `input/`, `output/`, `report/`, `logs/`로 분리한다.
- 출력 파일명은 원본 파일명에서 경로 구분자와 제어문자를 제거한 안전한 이름으로 만든다.
- 동일 이름의 결과는 덮어쓰지 않고 실행 ID를 포함하거나 충돌을 명시적으로 거부한다.

### 11.3 최소 인터페이스

```python
class Parser(Protocol):
    def parse(self, path: Path) -> ParsedFile: ...

class RuleChecker(Protocol):
    def check(self, parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]: ...

class AIProvider(Protocol):
    def review(self, request: AIRequest) -> AIResponse: ...

class DiffProvider(Protocol):
    def compare(self, original: Path, modified: Path) -> DiffResult: ...
```

구현체는 네트워크·GUI·파일 시스템을 직접 혼합하지 않으며, Core가 의존성 주입으로 선택한다. Mock 구현체로 외부 AI와 WinMerge 없이 테스트할 수 있어야 한다.

### 11.4 결과 재현성

`ReviewReport`에는 `run_id`, `input_sha256`, `ruleset_version`, `ruleset_source_sha256`, `prompt_version`, `model_id`, `app_version`, `encoding`, `newline_style`을 포함한다. 캐시 적중 결과도 동일 메타데이터를 남긴다.

### 11.5 보안 경계

- AI URL은 허용된 HTTPS 호스트·포트 목록과 일치할 때만 호출한다. 리다이렉트는 기본 차단한다.
- API 인증정보는 설정 파일에 평문으로 저장하지 않으며, 로그·예외·리포트에서 토큰을 마스킹한다.
- 코드 안의 주석·문자열은 신뢰할 수 없는 입력으로 취급하고, 프롬프트 지시로 해석하지 않는다.
- HTML 리포트와 WinMerge 결과는 외부 리소스 로딩·스크립트 실행을 차단한 상태로 표시한다.

## 12. 설계 결정 기록(ADR) 대상

다음 결정은 구현 전에 짧은 ADR로 확정한다: `Checklist Excel Schema`, `Legacy Excel Adapter Scope`, `Optional RuleDefinitions Sheet`, `PNL Parser Strategy`, `AI API Contract`, `Autofix Validation Level`, `WinMerge Report Format`, `PyInstaller WebView Runtime`, `Log/Sample Data Retention`.

## 13. 구현 완료 아키텍처 및 품질 게이트 실증 명세 (v2.0 최신화)

### 13.1. 멀티 포맷 통합 리포트 생성기 (`app/core/report/`)
1. **JSON 리포트 (`ReviewReport`)**: 파이프라인 IR, 위반 목록, 파싱 에러, 체크리스트 매핑 정보, 실행 지표를 일원화하여 출력합니다.
2. **HTML 리포트 (`HTMLReportBuilder`)**: 외부 CDN 의존성 0개(완전 오프라인 호환), 위반 심각도/상태별 필터 바, AI 허위 경보 배지, WinMerge Side-by-Side Diff 뷰어를 내장합니다.
3. **CSV 리포트 (`CSVReportBuilder`)**: 다국어 호환 `utf-8-sig` 인코딩을 적용하여 엑셀에서 바로 열람 가능한 스프레드시트를 제공합니다.
4. **Excel 납품용 리포트 (`ExcelReportBuilder`)**: 고객 제출용 요약 시트, 위반 사항 시트, 컬럼 오토피트(AutoFit) 및 심각도 컬러 하이라이팅 서식을 적용하여 `.xlsx` 파일로 내보냅니다.
5. **PDF 납품용 인증서 리포트 (`PDFReportBuilder`)**: 요약 및 주요 위반 지표를 정형화된 납품용 문서 형식(`.pdf`)으로 생성합니다.

### 13.2. SHA256 해시 증분 캐싱 및 WinMerge Diff 연동 엔진
1. **증분 분석 캐시 (`review_cache.json`)**: 원본 소스 파일의 SHA256 해시와 변경 이력을 대조하여 수정 없는 파일은 분석을 스킵하고 즉시 결과를 반환합니다.
2. **WinMerge 1-Click GUI Diff (`WinMergeRunner`)**: 자동 수정 제안과 원본 코드를 비교하고, HTML 리포트 내 클릭 이벤트 연동으로 WinMerge 프로세스를 원클릭 기동합니다.

### 13.3. AI 허위 경보(False Positive) 필터링 및 신뢰도 검증 루프 (`FalsePositiveFilter`)
1. **AI 검증 모델 확장**: `Violation` 모델에 `confidence_score`(0.0~1.0), `false_positive_probability`(0.0~1.0), `is_false_positive`(bool), `ai_verification_reason`(str) 4개 필드를 적용하였습니다.
2. **도메인 안전 컨텍스트 식별**: `@safe` 주석, SCADA 안전 래퍼(`safeDpSet`), 예외 처리 핸들러(`getLastError`) 동반 시 오탐으로 분류하고 신뢰도 점수를 보고서에 시각화합니다.

### 13.4. 아키텍처 가시성: 기술 부채 핫스팟 히트맵 및 릴리스 품질 트렌드 대시보드 (`HotspotCalculator`)
1. **심각도 가중치 기반 기술 부채 점수 산출 (`app/core/report/hotspot_calculator.py`)**: `CRITICAL` 10점, `HIGH` 5점, `MEDIUM` 2점, `LOW` 1점의 가중치를 적용하여 파일별 누적 기술 부채 점수(`HotspotScore`)를 계산하고 고위험 상위 파일을 식별합니다.
2. **시각적 히트맵 카드 및 인터랙티브 필터**: HTML 리포트 상단에 결함 밀집 파일의 히트맵 카드 및 심각도 CSS 프로그레스 바를 렌더링하며, 클릭 시 해당 소스 파일 위반 목록만 필터링하는 `filterByFile` 기능을 제공합니다.
3. **릴리스 품질 트렌드 및 퇴보(Regression) 감시**: 직전 릴리스 대비 신규 유입/해결/유지 결함 통계 및 품질 추이 요약(`trend_summary`)을 리포트 대시보드에 표시합니다.

### 13.5. AI 자율 최적화: 오탐 피드백 기반 엑셀 룰 카탈로그 자율 최적화 루프 (`RuleOptimizer`)
1. **오탐 피드백 지속 학습 로거 (`app/core/ai/rule_optimizer.py`)**: 사용자 및 AI 오탐 판정(`False Positive`) 이력을 JSON 파일(`config/fp_feedback_log.json`)에 영구 로깅하고 통계를 관리합니다.
2. **SCADA 래퍼 함수 분석 및 룰 추천기**: 특정 Rule ID에 대해 오탐이 임계치(기본 2건 이상) 누적될 경우, 스니펫 내 공통 도메인 래퍼 함수(예: `safeDpSet`, `checkAuth`)를 정규식 빈도 분석하여 엑셀 룰 카탈로그(B/C/D열)에 등록할 제외 키워드(`exclude_keyword`) 및 YAML 최적화 구문을 자동 추천합니다.
3. **CLI 연동**: `python -m app.main --suggest-rules` 옵션 실행을 통해 룰 최적화 추천 마크다운 리포트를 즉시 렌더링합니다.

### 13.6. 데스크톱 GUI 다이얼로그 안전성 및 자가 진단 상태 바 (`JSApi` & Self-Check)
1. **다이얼로그 제어 흐름 안전성 강화**: `select_input_path`에서 데스크톱 `create_file_dialog`를 ESC나 취소로 닫을 경우, 2차 Tkinter 폴백 다이얼로그로 떨어지는 조건 누수(Fall-through)를 원천 차단(`return {"selected_path": None}`)하였습니다.
2. **실시간 시스템 환경 자가 진단 하단 바**: Python 런타임 버전, WinMerge CLI 가용성, Excel 룰셋 파일 유효성, 로컬 AI 서버 응답 상태를 1초 이내에 진단하고 GUI 하단 바에 시각화합니다.

### 13.7. 전체 회귀 테스트 및 품질 게이트 통과 실증
1. **테스트 스위트 커버리지**: CLI, Parser(CTL/XML/PNL), RuleEngine, AIProvider, DiffRunner, Cache, UI JS API, ReportBuilder, FalsePositiveFilter, HotspotCalculator, RuleOptimizer, DPVariableTracker, AutofixValidator, QualityTrendDB 전 계층 검증
2. **최종 실증 검증 수치**: **193 passed in 7.12s (100% PASS)**

### 13.8. 로드맵 P0, P1, P2, P3, P4, P5 전체 과제 100% 최종 완전 타결 (v2.3 최신화 완료)
1. **저장소 위생 및 CI CD 파이프라인 연동**: `.gitignore`, `LICENSE`, `.github/workflows/test.yml`(Windows 러너, ruff, mypy, pytest cov) 및 release.yml 파이프라인
2. **동적 엑셀 파서 (`ExcelRuleLoader.find_header_and_columns`)**: 엑셀 1~30행 동적 스캔으로 헤더 및 대분류, 중분류, 소분류 열 좌표 자동 탐지
3. **보안 API 키 및 소스코드 로그 마스킹 (`app/utils/log_masker.py`)**: `WINCC_AI_API_KEY`, `LOCAL_AI_API_KEY` 연동 및 소스 스니펫 로그 마스킹
4. **AI 서버 장애 정밀 폴백 (`[AI FALLBACK]`)**: AI 연결 실패 시 명시적 경고 로그 및 리포트 안내 메타데이터 부여
5. **Precision 및 Recall 실측 엔진 (`scripts/03_precision_recall_evaluator.py`)**: 정적 검정률 실측 통계 산출 및 CSV/JSON 내보내기
6. **자동화 커버리지 지표 (`automation_coverage_pct`)**: 엑셀 체크리스트 매핑 대비 자동 검사 커버리지 수치 시각화
7. **git diff 기반 변경 라인 필터 (`app/core/diff_filter.py`)**: Unified diff 분석 및 변경 행 결함 선별 검사
8. **프로젝트 레벨 교차 파일 분석 (`app/core/cross_file_analyzer.py`)**: 복수 파일간 중복 스크립트 결함(`CROSS_FILE_DUPLICATE`) 탐지
9. **AI 심각도 정렬 및 미실행 표기**: 심각도 순 AI 리뷰 할당 및 초과 시 `[AI UNREVIEWED: max limit exceeded]` 표기
10. **위험 수용 이력 관리 (`app/core/accepted_risk.py`)**: `ACCEPTED_RISK` 승인자, 사유, 승인 일자 감사 추적
11. **순환 복잡도 및 구조 분석 (`app/core/complexity.py`)**: Cyclomatic Complexity 및 최대 중첩 깊이 측정
12. **SCADA 보안 체커 (`app/rules/check_scada_security_exec.py`)**: `system()`, `popen()`, `exec()` 등 외부 프로세스 명령 주입 검출
13. **1문단 리뷰 요약 엔진 (`app/core/review_summary.py`)**: 1문단 결함 요약문 자동 생성
14. **VCS 인라인 코멘트 포맷터 (`app/core/vcs_commenter.py`)**: GitHub PR 및 GitLab MR 페이로드 포맷터
15. **CLI 빌드 파이프라인 심각도 exit code 제어 (`--fail-on-severity`)**: 지정 심각도 이상 결함 감지 시 프로세스 exit code 1 반환
16. **인코딩 신뢰도 미달 경고 배너**: 비표준 인코딩 감지 시 `[ENCODING WARNING]` 경고 안내 부여
17. **릴리스 품질 트렌드 visual diff 대시보드 차트**: 이전 Run 대비 New, Fixed, Persistent 비율 및 visual diff 차트 시각화
18. **DP 계층 변수 추적기 (`wincc_reviewer/app/core/dp_variable_tracker.py`)**: 스크립트 내 `dpConnect`, `dpGet`, `dpSet`, `dpQuery` 연산 및 콜백 체인 정밀 추적
19. **자동 수정 샌드박스 AST 구문 검증기 (`wincc_reviewer/app/core/autofix_validator.py`)**: `.autofix_sandbox` 임시 공간 사전 파싱 검증으로 문법 파손 시 자동 롤백
20. **장기 품질 트렌드 DB 연동 (`wincc_reviewer/app/core/report/quality_trend_db.py`)**: `quality_trend_db.json` 장기 DB에 결함 수 및 기술 부채 점수 변동 저장
21. **현장 데이터 익명화 유틸리티 (`scripts/04_anonymize_dataset.py`)**: IP 주소, 이메일, 비밀번호 마스킹 및 `secondary_data/anonymized_fixtures` 데이터셋 변환
22. **사내 Open WebUI 및 타 IP 로컬 AI 서버 연동 5대 파라미터 구성**: Host, Port, Endpoint, API Key, Model ID 명세
23. **GUI 탭 전환 CSS 우선순위 버그 정정**: `.view-pane` 인라인 display 오버라이드 정정으로 탭 스위칭 정상화
24. **파이프라인 os 및 SeverityLevel 임포트 누락 버그 정정**: `NameError` 사전 차단 및 안정성 확증
25. **회귀 테스트 193개 수트전수 100% 통과 (193 passed in 7.12s)**




