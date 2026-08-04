# 룰 기반 검출 로직 정밀 점검 및 개선 보고서

## 1. 개요 및 점검 목적
* 본 보고서는 WinCC OA 코드 리뷰 자동화 도구의 전체 9종 내장 체커 검출 로직을 대상으로, 체계적 진단 방법론을 적용하여 False Negative(미검출) 및 False Positive(오검출) 발생 여부를 과학적으로 검증하고, 발견된 결함을 즉시 수정한 결과를 기술합니다.

## 2. 검증 방법론
* **정밀 진단 스크립트**: `scripts/12_checker_accuracy_diagnostic.py`를 작성하여 9종 체커 각각에 대해 positive(반드시 검출해야 하는 위반 코드) 및 negative(반드시 PASS해야 하는 준수 코드) 총 26건의 테스트 시나리오를 자동 공급하고 검출 정확도를 검증하였습니다.
* **과학적 대조 실험 설계**: 각 체커별로 최소 2~5건의 시나리오를 구성하여, 단일 변인(예: delay 유무, try/catch 유무, IP 유형, 루프 조건 형태) 변경에 따른 검출/미검출 분기를 독립적으로 검증하였습니다.

## 3. 발견된 결함 및 수정 내역

### 결함 1: for(;;) 무한루프 미검출 (check_loop_delay)
* **원인 분석**: `check_loop_delay` 체커의 for 루프 유한 판별 조건에서 `";" in loop_cond` 조건이 `for(;;)`처럼 빈 세미콜론만 존재하는 무한루프도 유한 루프로 오판하여 검사를 건너뛰고 있었습니다.
* **수정 내용**: for 루프의 유한 판별 로직을 세밀하게 재설계하여, 세미콜론으로 분리된 3개 세그먼트 중 조건부(2번째)에 실질적인 비교 연산자(`<`, `>`, `=`, `!`)가 있는 경우만 유한 루프로 인정하도록 변경하였습니다. `for(;;)` 등 빈 조건부는 무한 루프로 정확히 식별하여 검사 대상에 포함됩니다.
* **영향 범위**: `checker_registry.py` 112~127행의 for 루프 스킵 조건 분기 전체 재구성.

## 4. 체커별 최종 검증 결과

| 체커 키 | 체커 설명 | positive 시나리오 | negative 시나리오 | 결과 |
| :--- | :--- | :---: | :---: | :---: |
| `ctl.dp_connect_pair` | dpConnect/dpDisconnect 짝 검사 | 1건 | 2건 | 3/3 PASS |
| `ctl.loop_delay` | 무한 루프 delay 누락 검사 | 2건 | 3건 | 5/5 PASS |
| `ctl.try_catch` | DP 함수 try/catch 예외 처리 검사 | 1건 | 3건 | 4/4 PASS |
| `ctl.batch_dp_ops` | 단건 dpGet/dpSet 연속 호출 검사 | 1건 | 2건 | 3/3 PASS |
| `ctl.hardcoding` | IP/URL 하드코딩 지양 검사 | 1건 | 3건 | 4/4 PASS |
| `ctl.dp_error_handling` | dpGet/dpSet 반환값 검사 누락 | 1건 | 2건 | 3/3 PASS |
| `ctl.dp_callback_delay` | 콜백 내 delay 비동기 지연 위험 | 1건 | 1건 | 2/2 PASS |
| `ctl.db_query_binding` | SQL 동적 결합 바인딩 쿼리 검사 | 1건 | 1건 | 2/2 PASS |
| **합계** | **9종 체커** | **9건** | **17건** | **26/26 PASS** |

## 5. 회귀 테스트 검증
* 전체 프로젝트 테스트 스위트 101건이 100% 통과(101 passed in 5.95s)하여 수정 사항의 안정성이 확보되었습니다.
* `test_smoke.py`의 `test_main_no_args_returns_zero` 테스트는 `main()` 함수의 GUI 구동 변경에 맞추어 `launch_ui` 모킹으로 갱신하였습니다.

## 6. 참조 산출물
* 진단 스크립트: `scripts/12_checker_accuracy_diagnostic.py`
* 수정 대상 파일: `app/core/rules/checker_registry.py` (for(;;) 무한루프 판별 로직)
* 수정 대상 파일: `tests/test_smoke.py` (GUI 구동 모킹 갱신)
