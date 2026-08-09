# CFA 기반 룰 고도화 및 도메인 RAG 도입 개선 방안

현재 시스템의 코드를 분석한 결과, 기획된 목표(다중 라인 예외 처리 감지 및 가상 함수 추론 환각 방지)를 달성하기 위해 구현 방식의 근본적인 전환이 필요합니다. 아래는 이를 위한 구체적인 기술적 개선 방안입니다.

---

## 1. 정규식 래퍼에서 "진성(True) Tree-sitter AST 파서"로의 전환

현재 `tree_sitter_parser.py` 코드를 보면, 모듈 이름은 Tree-sitter지만 내부 `parse_code_to_ast()` 함수는 `tree_sitter` 라이브러리를 쓰지 않고 **정규식(`re.search`)에 의존하여 주석과 함수 선언을 추출하는 과도기적(Mock) 형태**로 구현되어 있습니다.

### 🛠️ 개선 액션
1. **Tree-sitter 문법 컴파일 및 연동**: C++ 문법(`tree-sitter-cpp`) 패키지를 정식으로 로드하여, 소스 코드를 문자열이 아닌 **순수 노드 트리(Node Tree)** 객체로 파싱해야 합니다. (WinCC OA의 CTRL 스크립트 문법은 C++과 매우 흡사하므로 C++ 파서를 기반으로 커스터마이징 가능).
2. **Tree-sitter Query(TSQ) 도입**: 코드를 탐색할 때 파이썬 반복문 대신 Tree-sitter의 강력한 S-표현식 쿼리를 사용합니다.
   - *예시*: `(call_expression function: (identifier) @func_name arguments: (argument_list) @args)`

---

## 2. 제어 흐름 분석(CFA)을 통한 다중 라인 예외 처리 정밀 감지

현재 `checker_registry.py`의 `check_try_catch_exception` 함수는 단순히 텍스트 내에 `try`와 `catch`라는 단어가 존재하는지만(boolean) 검사하므로, 해당 `catch`가 내가 호출한 API의 에러를 잡는 것인지 알 수 없습니다.

### 🛠️ 개선 액션
1. **스코프 기반 부모 노드 추적 (Traverse Up)**:
   - `dpGet`이나 `dpSet` 노드가 발견되면, AST 트리를 거슬러 올라가며 가장 가까운 상위 블록이 `try_statement` 노드 내부에 속해 있는지 확인합니다.
2. **Catch 블록 매핑 유효성 검사**:
   - `try_statement` 형제 노드에 유효한 `catch_clause` 노드가 붙어 있는지, 그리고 `catch` 내부 스코프에 사내 표준 에러 핸들링 함수(예: 로그 기록)가 실제로 존재하는지 AST 구문 트리의 자식 노드를 검사하여 정확히 판별합니다.

---

## 3. 심볼 테이블(Symbol Table) 구축을 통한 함수 섀도잉 및 콜백 검증

AST가 완전히 구축되면 단순히 구문만 보는 것을 넘어 "이름 공간(Scope)"을 완벽히 통제할 수 있습니다.

### 🛠️ 개선 액션
1. **전역 심볼 수집기 개발**: AST를 1차 순회하여 전역 변수, 함수 선언(`FunctionDeclaration`)을 메모리에 심볼 테이블 형태로 해싱해 둡니다.
2. **콜백 함수 인자(Signature) 교차 검증**:
   - `dpConnect("myCallback", ...)` 구문을 만나면 문자열 `"myCallback"`을 심볼 테이블에서 조회합니다.
   - 함수가 없으면 즉시 에러(컴파일 타임 에러 시뮬레이션)를 발생시키고, 함수가 있다면 AST 노드의 `parameter_list`를 까보고 `string dp, anytype val` 등의 시그니처가 WinCC 표준에 맞는지까지 교차 검증합니다.

---

## 4. 도메인 RAG 고도화: AI 환각(Hallucination)의 원천 차단

LLM이 `dpGetMany`와 같이 존재하지 않는 가상 함수를 만들어내거나, 범용 C++ 코딩 스타일로 코드를 수정해버리는 현상을 막으려면 프롬프트만으로는 부족합니다.

### 🛠️ 개선 액션
1. **Vector DB 기반 API 매뉴얼 임베딩**:
   - WinCC OA 공식 문서(특히 dp 관련 API 및 비동기 콜백 제약사항)와 사내 코딩 컨벤션 문서를 청크 단위로 Vector DB(예: ChromaDB)에 저장합니다.
2. **Hard-Constraint 프롬프팅 주입**:
   - 위반 사항이 발견되면 RAG 검색을 통해 **관련된 API의 올바른 시그니처와 사내 Golden Sample(정답 코드)만 추출**하여 프롬프트에 주입합니다.
   - **프롬프트 제약 추가**: *"다음 제공된 API(예: dpGet, dpSet) 목록 외의 함수는 절대 사용하지 마시오. 가상의 함수를 발명할 경우 코드 생성에 실패한 것으로 간주함."*
3. **AST 기반 사후 검증 (Post-Validation)**:
   - AI가 수정된 코드(Autofix)를 반환하면, 이를 다시 Tree-sitter AST 파서에 넣어 "생성된 함수명들이 심볼 테이블이나 허용 API 리스트에 존재하는지" 프로그램적으로 검사합니다. 존재하지 않는다면 AI 응답을 기각(Reject)합니다.
