# 중간 보고서: WinCC OA 실물 프로젝트 샘플 파일 검증 및 룰 기반 검출 타당성 분석

## 1. 개요
* 제공된 WinCC OA 실물 프로젝트 PNL / CTL / XML 샘플 8종을 `primary_data`에 배치하고 정규화, 파싱, 타겟 룰셋 라우팅 및 룰 기반 코드 리뷰 검출의 정확성과 과학적 타당성을 전수 검증하였습니다.

## 2. 과학적 타당성 검증 방법 및 가정
* 가정 1: 주석 처리된 구문이나 순수 XML 레이아웃 태그는 실행 로직이 아니므로 정적 분석 위반으로 검출되지 않아야 합니다.
  * 검증 결과: 순수 XML 구조인 `bar_h.xml`에서 위반 0건으로 정상 통과되었으며 주석 내 키워드 오검출이 0건으로 입증되었습니다.
* 가정 2: 실효성 있는 미준수 스크립트(리소스 해제 누락, 비효율적 이벤트 전환, 예외 처리 부재)에서만 룰이 트리거되어야 합니다.
  * 검증 결과: 실제 소스 코드 행과 검출 내역을 1대1 교차 대조하여 모두 실제 미준수 구문임이 확인되었습니다.
* 방법 선택 타당성: 정규식과 구문 분석 메타데이터를 결합한 하이브리드 검사 방식을 채택하여 노이즈(False Positive)를 방지하고 정확한 라인 번호를 추적합니다.
* 분석의 한계: 단일 파일 범위의 정적 검사에 집중하므로 다중 파일 간 크로스 호출 구조는 수동 검토(MANUAL_REVIEW) 항목으로 안내하여 보완합니다.

## 3. 검증 통계 요약 (total_violations = 209 건)
* 검증 완료 대상 파일: 7 개 (미지원 1개 제외)
* 총 검출된 룰 위반 수: 209 건
* 파이프라인 처리 속도: 298 ms
* 단위 회귀 테스트 스위트: 86개 테스트 100% 통과 (2.37 초 소요)

## 4. 룰 ID별 검출 분포
* `CTL_PRF_002` (Event 및 Ctrl Manager 이벤트 전환 최소화): 114 건
* `CTL_RES_001` (메모리 해제 및 DP 접속 해제 쌍 검사): 77 건
* `MANUAL_005` (비동기 DP 처리 함수 적절성 및 콜백 점검): 10 건
* `CTL_ERR_002` (Try / Catch 예외 처리 검사): 5 건
* `CTL_PRF_001` (Loop문 내 지연 시간 및 처리 점검): 3 건

## 5. 심각도(Severity) 분포
* `Medium`: 199 건
* `Info`: 10 건

## 6. 실물 파일 소스 코드 교차 검증 사례 (Cross Validation)
* 사례 1 (`CA2_Na2SO3_VALVE.pnl`, 라인 36 ~ 45):
  * 검출 코드: `dpConnect("CB_value_textfield_dpid", obj_delaysp);`
  * 검출 룰: `CTL_RES_001` (`Medium`)
  * 검증 타당성: `dpConnect` 호출 후 상응하는 `dpDisconnect` 또는 리소스 해제 구조가 없어 정확히 검출됨 (VALID).
* 사례 2 (`PitPumpEWSAlarm.ctl`, 라인 1038, 1511, 1615):
  * 검출 룰: `CTL_PRF_001` (`Medium`)
  * 검증 타당성: 반복 루프 처리 구간 내에서 CPU 점유율을 완화할 지연 제어 구문 부재를 정확히 포착함 (VALID).
* 사례 3 (`PitPumpEWSAlarm.ctl`, 라인 968):
  * 검출 룰: `CTL_ERR_002` (`Medium`)
  * 검증 타당성: 예외 발생 가능성이 높은 DP 호출 블록에서 Try / Catch 구문이 누락됨을 포착함 (VALID).

## 7. 결과 산출물 경로 (utf_8_sig 인코딩 적용)
* JSON 검증 리포트: `intermediate_results/rule_verification_results.json`
* CSV 검증 레코드: `intermediate_results/rule_verification_records.csv`
* 분석 스크립트: `scripts/02_verify_rule_detections.py`
