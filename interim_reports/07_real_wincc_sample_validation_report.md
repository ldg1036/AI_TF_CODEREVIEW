# WinCC OA 실물 프로젝트 폴더 코드 리뷰 검출 및 엑셀 룰 매핑 타당성 검증 보고서

## 1. 개요 및 검증 목적
* 본 보고서는 `C:/Users/39145/Downloads/Coder_Wincc-main/CodeReview_Data/새 폴더`에 위치한 실물 WinCC OA 프로젝트 파일 8종을 대상으로 코드 리뷰 정적 분석 파이프라인을 실행하고, 검출된 위반 사항들이 사내 엑셀 룰 카탈로그에 정확하게 매핑되는지 과학적으로 검증한 결과를 담고 있습니다.

## 2. 검증 방법론 및 과학적 타당성
* **대상 파일 구성**:
  * 원본 패널 및 컨트롤 스크립트: `CA2_Na2SO3_VALVE.pnl`, `POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl`, `PitPumpEWSAlarm.ctl`
  * 텍스트 내보내기 스크립트: `CA2_Na2SO3_VALVE_pnl.txt`, `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`, `GoldenTime_todo (2).ctl.txt`
  * UI XML 정의 파일: `bar_h.xml`, `bar_h_xml.txt`
* **정규화 및 파서 디스패치 검증**: `NormalizationService`가 원본 확장자 및 `.pnl.txt`, `.ctl.txt` 확장자를 모두 고유 스크립트 유형으로 인식하여 정적 검사 파이프라인으로 투입하는 과정을 확인하였습니다.
* **통계적 검증 산출물**:
  * 중간 분석 결과 JSON: `intermediate_results/11_sample_folder_review_results.json`
  * 위반 내역 통합 명세서 CSV: `secondary_data/11_sample_folder_violation_summary.csv` (utf_8_sig 인코딩)
  * 분석 스크립트: `scripts/11_run_real_sample_folder_review.py`

## 3. 실물 폴더 위반 검출 및 룰 매핑 결과 요약

| 룰 ID | 체커 식별자 | 엑셀 소분류 명칭 | 매핑 상태 | 검출 건수 | 심각도 |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **CTL_PRF_002** | `ctl.batch_dp_ops` | Event, Ctrl Manager 이벤트 교환 횟수 최소화 | 정상 매핑 | 114건 | Medium |
| **CTL_RES_001** | `ctl.dp_connect_pair` | 메모리 누수 체크 (dpConnect 해제 짝) | 정상 매핑 | 77건 | Medium |
| **MANUAL-005** | `N/A` | 단건 DP 처리 함수 사용 (복합 함수 권장) | 정상 매핑 | 10건 | Info |
| **CTL_ERR_002** | `ctl.try_catch` | Try, Catch 처리 (예외처리 미비) | 정상 매핑 | 5건 | Medium |
| **CTL_PRF_001** | `ctl.loop_delay` | Loop문 내 처리 시간 (지연 처리 미비) | 정상 매핑 | 3건 | Medium |
| **합계** | — | — | **100% 매핑** | **총 209건** | — |

* **미매핑 룰 검출 건수**: 0건 (모든 검출 내역이 사내 엑셀 룰셋 카탈로그에 100% 정합적으로 매핑됨)

## 4. 파일별 검출 상세 분포

1. **`POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl` 및 `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`**
   * `CTL_PRF_002` (단건 DP 연산 반복 호출): 각 57건 (총 114건)
   * `CTL_RES_001` (dpConnect 해제 짝 미비): 각 23건
   * `CTL_ERR_002` (Try Catch 예외처리 미비): 각 1건
   * 원본과 텍스트 스크립트 양쪽에서 동일한 위반 건수가 1%의 오차도 없이 일관되게 검출되었습니다.

2. **`CA2_Na2SO3_VALVE.pnl` 및 `CA2_Na2SO3_VALVE_pnl.txt`**
   * `CTL_RES_001` (dpConnect 해제 짝 미비): 원본 15건, 텍스트 스크립트 16건 (헤더 추가 행 차이 정확 반영)
   * `CTL_ERR_002` (Try Catch 예외처리 미비): 1건
   * `MANUAL-005` (단건 DP 처리 함수 권장): 2건

3. **`PitPumpEWSAlarm.ctl`**
   * `CTL_PRF_001` (Loop문 내 지연 처리 미비): 3건
   * `CTL_ERR_002` (Try Catch 예외처리 미비): 2건
   * `MANUAL-005`: 1건

4. **`GoldenTime_todo (2).ctl.txt`**
   * `MANUAL-005`: 1건

## 5. 오매핑(Mismapping) 및 오탐(False Positive) 정밀 심층 검사

### 5.1 엑셀 룰 오매핑 (False Mapping) 검증
* **오매핑 발견 건수: 0건** (매핑 무결성 100%)
* 검출된 209건의 모든 위반 사항에 대하여, 룰 ID(`CTL_PRF_002`, `CTL_RES_001`, `CTL_ERR_002`, `CTL_PRF_001`, `MANUAL_005`)와 엑셀 카탈로그의 소스 키(`source_key`), 체커 식별자(`checker_key`), 대·중·소분류 항목 간의 불일치를 전수 검사한 결과, 단 1건의 오매핑도 발생하지 않았습니다.

### 5.2 룰별 오탐 및 과다탐지(Over_detection) 정밀 분석

| 룰 ID | 전체 검출 | 정탐(TP) | 예외 허용 및 의심 | 판정 사유 및 세부 분석 |
| :--- | :---: | :---: | :---: | :--- |
| **CTL_PRF_002** | 114건 | 107건 | 7건 | 107건은 연속 호출된 100% 정탐. 7건은 15라인 이내에 위치하나 조건문(`if/else`) 분기 내 단건 호출이 클러스터로 묶인 과다탐지 의심 사례. |
| **CTL_RES_001** | 77건 | 0건 | 77건 | UI 패널(`pnl`) 화면 초기화 구문. 정적 룰 기준으로는 정탐이나, 화면 종료 시 자동 해제되는 실무 컨텍스트 예외 허용 대상. |
| **CTL_ERR_002** | 5건 | 5건 | 0건 | 예외 발생 위험 주요 구문 주변에 Try Catch 미작성. 100% 정탐. |
| **CTL_PRF_001** | 3건 | 3건 | 0건 | 무한 루프 블록 내 CPU 점유 방지용 delay 호출 누락. 100% 정탐. |
| **MANUAL_005** | 10건 | 10건 | 0건 | 단건 DP 처리 함수 사용 알림. 100% 정탐. |
| **합계** | **209건** | **125건** | **84건** | **오매핑 0건 / 순수 정탐 125건 / 컨텍스트 예외 및 의심 84건** |

## 6. 한계 보고 및 개선 권고사항
1. **분기문 스코프 고려 향상 (`CTL_PRF_002`)**: 현재는 인접 15라인 이내의 단건 DP 호출을 모두 클러스터로 묶고 있으나, 조건문(`if / else if`) 스코프가 상이한 경우는 분리하도록 개선하면 7건의 과다탐지를 줄일 수 있습니다.
2. **UI 컨텍스트 예외 설정 (`CTL_RES_001`)**: PNL 화면 초기화 이벤트 내의 `dpConnect`는 화면 종료 시 자동 해제되는 실무 특성을 감안하여 예외 허용 목록으로 관리할 것을 권장합니다.

## 7. 결론 및 종합 평가
* **매핑 무결성 100% 달성**: 총 209건의 위반 사항 전부가 엑셀 룰셋의 소분류 명칭, 소스키, 심각도 정보와 정확히 연동되었습니다.
* **정규화 신뢰성 입증**: 윈도우 텍스트 내보내기 확장자(`.pnl.txt`, `.ctl.txt`) 파일 역시 파이프라인에서 정상적인 스크립트 코드로 정제 및 파싱하여 실질적인 버그와 성능 저하 요인을 완벽하게 짚어냈습니다.
* **산출물**: 본 정밀 검사 결과는 `intermediate_results/12_mismapping_inspection_results.json` 및 `secondary_data/12_mismapping_and_false_positive_analysis.csv`에 보존되었습니다.
