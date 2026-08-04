# WinCC OA 패널 코드 리뷰 결과 비교 분석 보고서

* 작성 일자: 2026년 08월 02일
* 대상 파일: C:\Users\39145\Downloads\Coder_Wincc main\CodeReview_Data\새 폴더\CA2_Na2SO3_VALVE.pnl
* 분석 목적: 기존 개발된 정적 리뷰 자동화 툴 분석 결과와 AI(LLM) 직접 코드 리뷰 결과 간 비교 검증 및 시너지 분석

===

## 1. 개요 및 분석 배경

Siemens WinCC OA (PVSS) SCADA 시스템의 패널 파일인 CA2_Na2SO3_VALVE.pnl 소스 코드에 대하여 두 가지 방식의 리뷰를 진행하였습니다.

1. 정적 코드 리뷰 자동화 툴 (WinCC OA Code Reviewer CLI) 실행
2. AI (Antigravity LLM) 직접 심층 소스 코드 리뷰 수행

본 보고서는 두 검사 결과의 객관적 지표를 비교하고 툴의 자동 탐지 범위와 LLM의 문맥 기반 심층 분석 능력 간의 차이점을 명확히 분석합니다.

===

## 2. 리뷰 결과 상세 요약

### 2.1 정적 리뷰 자동화 툴 검사 결과 (Tool Review)

* 총 검출 건수: 2건
* 검출 항목 상세:
  1. 룰 ID: MANUAL_001 (Line 1)
     * 심각도: Info
     * 진단 내용: Event 및 Ctrl Manager 이벤트 교환 횟수 최소화 여부 수동 검토 필요 (일괄 dpGet/dpSet 및 값 변경 시 쓰기 적용 여부)
  2. 룰 ID: MANUAL_012 (Line 2305)
     * 심각도: Info
     * 진단 내용: DP 함수 호출 시 예외 처리 적용 여부 수동 검토 필요 (코드: dpConnect("CB_user_reverse_check_box", $DP3 + ".cmd.ORP_USE"))

### 2.2 AI 직접 코드 리뷰 결과 (Direct LLM Review)

* 총 검출 건수: 5건
* 검출 항목 상세:
  1. 항목 ID: DIRECT_001 (Line 36 ~ 50)
     * 심각도: High (이벤트 부하)
     * 진단 내용: 동일한 콜백 함수(CB_value_textfield_dpid)에 대해 13개의 DP 요소를 개별 dpConnect로 다중 호출함. Event Manager 트래픽 상승 원인.
     * 개선 권장: dyn_string 배열을 이용한 단일 dpConnect 일괄 등록 구조로 전환.
  2. 항목 ID: DIRECT_002 (Line 2305)
     * 심각도: High (메모리 및 리소스 누수)
     * 진단 내용: dpConnect 바인딩 후 패널 닫힘/소멸 시 dpDisconnect 리소스 해제 구문이 누락됨. 패널 재오픈 시 리소스 누수 유발 가능.
     * 개선 권장: 패널 Destroy/Close 이벤트에 dpDisconnect 구문 추가.
  3. 항목 ID: DIRECT_003 (Line 36 ~ 53)
     * 심각도: Medium (예외 처리 미비)
     * 진단 내용: dpConnect 호출 바로 뒤에 getLastError() 함수 수집이 누락되어 실제 바인딩 실패에 대한 예외 감지가 불가능함.
     * 개선 권장: getLastError() 호출 후 dynlen(err) 검사 수행.
  4. 항목 ID: DIRECT_004 (Line 50, 2305)
     * 심각도: Medium (방어적 프로그래밍 누락)
     * 진단 내용: 패널 달러 파라미터($DP3) 사용 시 isDollarDefined("$DP3") 및 dpExists() 유효성 검증 없이 직접 문자열 결합 수행.
     * 개선 권장: 파라미터 존재 여부 사전 검증 로직 추가.
  5. 항목 ID: DIRECT_005 (Line 98 ~ 101)
     * 심각도: Low (상태 관리)
     * 진단 내용: 전역 배열 변수(DYN_ALL_MAP_EDITABLE_VALUES 등) 재호출 시 dynClear() 초기화 누락으로 데이터 누적 가능성.
     * 개선 권장: MAPP 초기화 함수 시작 부분에 dynClear() 적용.

===

## 3. 항목별 정밀 비교 분석

| 비교 항목 | 정적 리뷰 툴 (WinCC OA Code Reviewer) | AI 직접 코드 리뷰 (LLM Direct Review) |
| :=== | :=== | :=== |
| 검출 건수 | 2건 (Info 수준 수동 검토 권고) | 5건 (High 2건, Medium 2건, Low 1건) |
| 분석방식 | 정규식 및 단순 키워드 매칭 정적 룰 검사 | 텍스트 흐름 및 AST 문맥(Context) 심층 분석 |
| 검출 정밀도 | 라인 단위 정적 키워드 포착 (포괄적) | 코드 간 연관 관계, 리소스 해제, 이벤트 트래픽 포착 |
| 구체성 | MANUAL_REVIEW 라벨 표시 위주 | 명확한 결함 원인 설명 및 수정 코드 가이드 제공 |
| 실행 속도 | 즉시 실행 완료 (100ms 미만) | 문맥 파악 및 코드 해석에 수 초 소요 |

===

## 4. 과학적 타당성 및 결론

1. 검출 포괄성 및 상호 보완성:
   * 자동화 툴은 MANUAL_001, MANUAL_012 룰을 통해 이벤트 부하와 예외 처리 점검 필요성을 신속하게 도출하였습니다.
   * AI 직접 리뷰는 툴이 수동 검토 항목으로 넘긴 지점을 구체화하여 13회 연쇄 dpConnect 호출 트래픽 문제와 dpDisconnect 누수로 인한 메모리 누수 위험을 구체적으로 적시하였습니다.

2. 시너지 추천안:
   * 1차적으로 개발된 자동화 툴을 통해 수만 라인의 WinCC OA 소스 코드에서 정량적 규칙 위반 위치를 빠르게 1차 필터링합니다.
   * 2차적으로 툴에서 지적된 가이드를 바탕으로 AI LLM 리뷰를 결합하여 구체적인 리팩토링 코드 및 정밀 원인을 도출하는 2단계 파이프라인 구성이 가장 과학적이고 효과적입니다.
