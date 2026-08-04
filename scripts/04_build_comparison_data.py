import os
import json

# Ensure intermediate_results directory exists
os.makedirs('intermediate_results', exist_ok=True)

# 1. Tool Review Results Data
tool_data = {
    "target_file": r"C:\Users\39145\Downloads\Coder_Wincc-main\CodeReview_Data\새 폴더\CA2_Na2SO3_VALVE.pnl",
    "total_violations": 2,
    "violations": [
        {
            "rule_id": "MANUAL_001",
            "line": 1,
            "severity": "Info",
            "message": "Event, Ctrl Manager 이벤트 교환 횟수 최소화: 일괄 dpGet/dpSet 처리 및 값 변경 시에만 dpSet 처리 여부 검토"
        },
        {
            "rule_id": "MANUAL_012",
            "line": 2305,
            "severity": "Info",
            "message": "DP 함수 예외 처리: dpConnect 호출 후 결과 예외 처리 미비"
        }
    ]
}

with open(os.path.join('intermediate_results', 'tool_review_results.json'), 'w', encoding='utf-8') as f:
    json.dump(tool_data, f, ensure_ascii=False, indent=2)

# 2. Direct Review Results Data (LLM Expert Analysis)
direct_data = {
    "target_file": r"C:\Users\39145\Downloads\Coder_Wincc-main\CodeReview_Data\새 폴더\CA2_Na2SO3_VALVE.pnl",
    "total_findings": 5,
    "findings": [
        {
            "issue_id": "DIRECT_001",
            "category": "Event Traffic Optimization",
            "lines": "36 to 50",
            "severity": "High",
            "title": "동일 콜백 함수에 대한 dpConnect 연속 13회 다중 단일 호출",
            "description": "CB_value_textfield_dpid 콜백 함수에 대해 13개의 DP 요소를 개별 dpConnect로 등록하여 Event Manager 수신 트래픽 부하 유발",
            "recommendation": "dyn_string 배열을 이용해 dpConnect 1회 호출로 일괄 결합 등록"
        },
        {
            "issue_id": "DIRECT_002",
            "category": "Resource & Memory Leak",
            "lines": "2305",
            "severity": "High",
            "title": "dpConnect 바인딩 해제(dpDisconnect) 누락",
            "description": "패널 종결 시 dpDisconnect 해제 처리가 누락되어 패널 재오픈 또는 소멸 시 이벤트 리소스 및 메모리 누수 위험 존재",
            "recommendation": "패널 Destroy/Close 이벤트에 dpDisconnect 구문 추가"
        },
        {
            "issue_id": "DIRECT_003",
            "category": "Exception Handling",
            "lines": "36 to 53",
            "severity": "Medium",
            "title": "dpConnect 실행 직후 getLastError 예외 수집 명시적 검증 누락",
            "description": "dpConnect 호출 직후 getLastError() 수집 없이 dynlen(err)만 검사하여 실제 바인딩 실패 예외 감지 불가",
            "recommendation": "err = getLastError(); 구문을 dpConnect 호출 바로 다음에 명시적으로 작성"
        },
        {
            "issue_id": "DIRECT_004",
            "category": "Defensive Programming",
            "lines": "50, 2305",
            "severity": "Medium",
            "title": "Dollar Parameter($DP3) 검증 미비",
            "description": "$DP3 파라미터가 비어있거나 올바르지 않은 DP 이름일 때의 유효성 검사(isDollarDefined/dpExists) 누락",
            "recommendation": "isDollarDefined(\"$DP3\") 및 dpExists() 조건문을 통한 방어적 프로그래밍 구현"
        },
        {
            "issue_id": "DIRECT_005",
            "category": "State & Scope Management",
            "lines": "98 to 101",
            "severity": "Low",
            "title": "전역 dyn_string 변수 초기화(dynClear) 누락",
            "description": "DYN_ALL_MAP_EDITABLE_VALUES 등 전역 배열 변수가 재호출 시 초기화되지 않아 데이터 누적 오류 가능성 존재",
            "recommendation": "초기화 함수(MAPP) 시작 시 dynClear() 호출"
        }
    ]
}

with open(os.path.join('intermediate_results', 'direct_review_results.json'), 'w', encoding='utf-8') as f:
    json.dump(direct_data, f, ensure_ascii=False, indent=2)

# 3. Comparison Metrics Data
metrics_data = {
    "comparison_summary": {
        "tool_detected_count": 2,
        "direct_detected_count": 5,
        "common_detected_count": 2,
        "tool_only_count": 0,
        "direct_only_count": 3
    },
    "evaluation": {
        "tool_strengths": "빠른 자동 검사 speed, 엑셀 룰 세트 기반 정량적 기준 제시, 수천 개 파일 일괄 처리 용이",
        "tool_weaknesses": "키워드 정규식 기반 정적 탐지로 심치 맥락 파악 부족, 수동 검토(MANUAL_REVIEW) 라벨링 위주로 구체적 코드 가이드 미비",
        "direct_strengths": "구문 맥락(Context) 및 데이터 흐름 이해, 메모리/이벤트 트래픽/방어 프로그래밍 등 심층 결함 도출, 구체적 개선 코드 제시",
        "direct_weaknesses": "인간/LLM 직접 리뷰 특성상 대규모 파일셋 전수 검사 시 시간 소요 및 일관성 유지를 위한 하부 시스템 필요"
    }
}

with open(os.path.join('intermediate_results', 'comparison_metrics.json'), 'w', encoding='utf-8') as f:
    json.dump(metrics_data, f, ensure_ascii=False, indent=2)

print("All intermediate review results successfully stored.")
