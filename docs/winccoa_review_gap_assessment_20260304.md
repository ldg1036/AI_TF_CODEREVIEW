# WinCC OA 자동 코드리뷰 프로그램 보완점 테스트/검토 (2026-03-04)

## 1) 수행한 테스트 범위

- API/리포트 핵심 회귀: `python -m unittest backend.tests.test_api_and_reports -v`
- WinCC OA 컨텍스트 서버: `python -m unittest backend.tests.test_winccoa_context_server -v`
- 핵심 진입점 문법 점검: `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`
- 규칙/설정 정합성: `python backend/tools/check_config_rule_alignment.py --json`
- 템플릿 커버리지 도구 실행성: `python backend/tools/analyze_template_coverage.py`
- Ctrlpp 연동 스모크(바이너리 미존재 허용): `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`

## 2) 현재 상태 요약

### 긍정 신호

1. 컨텍스트 서버 테스트는 통과하여 룰 조회/엔드포인트 위임 동작이 안정적임.
2. 핵심 실행 파일(`main.py`, `server.py`, `analysis_pipeline.py`)은 py_compile 기준 문법상 문제 없음.
3. `check_config_rule_alignment` 결과에서 mismatch 0건으로, 현재 P1 규칙/파싱/적용성 매핑 정합성은 양호함.
4. CtrlppCheck 바이너리 미설치 환경에서도 fail-soft로 리포트를 남기며 종료하므로, 운영 안정성 전략은 유지됨.

### 부족/보완 필요 신호

1. **Excel 리포트 및 템플릿 커버리지 검증의 실행 전제(openpyxl)가 보장되지 않음.**
   - `test_api_and_reports`에서 Excel 관련 테스트 다수가 `ModuleNotFoundError: openpyxl`로 실패.
   - `analyze_template_coverage.py`도 동일 원인으로 실패.
   - 결과적으로 “보고서 품질 회귀”를 CI/현장에서 상시 검증하기 어려움.

2. **리포트 품질 테스트가 환경 의존 실패를 명확히 분리하지 못함.**
   - 현재는 의존성 미충족 시 hard fail 형태로 나타나, 실제 코드 결함과 환경 결함의 구분 비용이 큼.

3. **Autofix 고급 경로(T3 structured instruction)는 로드맵상 여전히 기본 OFF 상태.**
   - 운영 기본값 기준에서는 instruction 경로의 실효 적용률/안정성 확보가 미완료로 해석 가능.

4. **선택적 도구(LLM/Ctrlpp/Playwright) 가용성에 따라 검증 범위가 크게 축소될 수 있음.**
   - fail-soft 설계는 바람직하지만, “무엇이 실제로 검증되었는가”를 한눈에 보여주는 검증 레벨 지표가 부족함.

## 3) 우선순위별 보완 제안

## P0 (즉시)

1. **검증 환경 프로파일 표준화**
   - `requirements-dev.txt` 또는 `pyproject optional-deps`에 `openpyxl` 포함.
   - `make verify-core`, `make verify-report` 같은 프로파일 명령으로 검증 레벨을 명시.

2. **환경 의존 테스트의 fail-soft/skip 정책 정교화**
   - Excel 관련 테스트는 `openpyxl` 미설치 시 명시적 skip 처리(원인 메시지 포함).
   - 단, 릴리스 게이트 파이프라인에서는 `openpyxl` 설치를 강제하여 skip이 발생하지 않도록 분리.

3. **검증 결과 요약 아티팩트 도입**
   - 실행한 체크 항목을 `passed/failed/skipped(optional missing)`로 JSON 요약 저장.
   - 운영자는 “리뷰 엔진은 정상인데 리포트 검증이 빠진 상태”를 즉시 식별 가능.

## P1 (단기)

1. **Autofix structured instruction 경로의 실데이터 재현성 강화**
   - drift 데이터셋 기준 anchor mismatch 주요 원인 분석 자동 리포트화.
   - `instruction_apply_rate`, `validation_fail_reason`를 릴리스 노트에 자동 첨부.

2. **규칙 커버리지 공백 자동 탐지 고도화**
   - 현재 정합성(mismatch 0건) 외에, 실제 샘플 데이터 대비 “미검출 패턴 후보”를 주기적으로 산출.
   - TODO mining 결과를 규칙 제안 PR 템플릿으로 자동 연결.

3. **리포트 신뢰도 메타데이터 노출**
   - UI/Excel/HTML에 “검증 레벨(예: CORE_ONLY / CORE+REPORT / FULL_WITH_OPTIONALS)” 배지 표기.

## P2 (중기)

1. **운영 계측 강화**
   - `/api/analyze` metrics에 optional dependency 가용성/사용 여부 필드 추가.
   - 장기적으로 장애 분석 시 “LLM 비활성 상태 결과”와 “LLM 활성 상태 결과”를 분리 비교.

2. **성능/품질 통합 대시보드**
   - 기존 perf baseline + rule alignment + smoke 결과를 단일 markdown/json 리포트로 집계.

## 4) 결론

현재 시스템은 P1/P2/P3 구조와 fail-soft 전략이 잘 잡혀 있어 실무 적용 기반은 충분합니다.
다만, 이번 점검 기준으로는 **리포트 계층(Excel) 검증이 환경 의존성(openpyxl) 때문에 안정적으로 보장되지 않는 점**이 가장 큰 보완 포인트입니다.

즉, 다음 액션의 핵심은 “새 기능 추가”보다 먼저
1) 검증 환경 표준화,
2) 선택 의존성의 명시적 검증 레벨화,
3) structured autofix 경로의 운영 가시성 강화
입니다.
