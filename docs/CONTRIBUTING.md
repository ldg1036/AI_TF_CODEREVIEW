# 개발자 기여 및 신규 룰 체커 작성 지침서 (CONTRIBUTING)

본 지침서는 WinCC OA Code Reviewer 프로젝트에 신규 정적 분석 룰 체커를 추가하거나 소스 코드를 개선하고자 하는 개발자를 위한 기여 가이드라인입니다.

## 1. 신규 정적 분석 룰 체커 추가 가이드

1. wincc_reviewer/app/core/rules/checkers/ 디렉터리에 새로운 체커 모듈 작성
2. CheckerRegistry.register 데코레이터를 사용하여 신규 체커 클래스 등록
3. BaseRule 클래스를 상속받고 check_rule 메서드를 구현하여 소스 코드 위반 탐지 로직 작성

```python
from app.core.rules.checker_registry import CheckerRegistry
from app.core.rules.base_rule import BaseRule

@CheckerRegistry.register("ctl.sample_checker")
class SampleChecker(BaseRule):
    def check_rule(self, code, file_path):
        violations = []
        # 위반 탐지 로직 작성
        return violations
```

## 2. 엑셀 룰 카탈로그 연동 방법

1. config/ 폴더 내 (코드리뷰결과서_Client).xlsx 또는 (코드리뷰결과서_Server).xlsx 파일에 신규 Rule ID 등록
2. ExcelSchemaLinter 가 스키마 유효성을 사전 검증하도록 룰 명세 표기

## 3. 코드 품질 검증 및 테스트 제출 전 필수 실행

코드 제출 전 아래 검증 스크립트들을 반드시 실행하여 결함 0건 상태를 확인해야 합니다.

1. 유닛 테스트 수트 구동: pytest wincc_reviewer/tests
2. 변수 및 함수 AST 무결성 검수: python scripts/23_inspect_code_variables_and_functions.py
3. 에이전트 검증 프로토콜 구동: python scripts/16_verify_agent_protocol.py
