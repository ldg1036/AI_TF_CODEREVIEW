# WinCC OA 코드리뷰 자동화 도구 신규 개발자 인수인계 및 개발 환경 셋팅 가이드

## 1. 개요
본 문서는 `wincc_reviewer` 프로젝트를 새로 전달받은 개발자가 환경을 셋팅하고 파이프라인 구조를 이해하여 지속 개발 및 유지보수를 수행하기 위해 필요한 백그라운드 작업과 기술 명세를 정리한 온보딩 가이드입니다.

## 2. 개발 환경 셋팅 및 사전 준비 (Prerequisites)

### 2.1 필수 시스템 환경
* 운영체제: Windows 10 또는 Windows 11 (64비트 필수)
* 제약 사유: Siemens WinCC OA 시스템, WinMerge CLI, pywebview 데스크톱 GUI가 Windows OS 전용에 의존함
* Python 런타임: 버전 3.12 이상

### 2.2 패키지 설치 및 가상환경 가동
```bash
# 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\activate

# 개발용 패키지 의존성 설치
pip install -e ".[dev]"
```

## 3. 핵심 아키텍처 및 디렉토리 구조 이해

```
wincc_reviewer/
├── app/
│   ├── main.py                      # CLI 및 파이프라인 진입점
│   ├── ui/                          # pywebview GUI 및 JS API 바인딩
│   ├── core/
│   │   ├── pipeline.py              # 전체 파이프라인 실행 및 오케스트레이터
│   │   ├── models.py                # IR, Violation, ReviewReport 데이터 모델
│   │   ├── rules/                   # 동적 엑셀 파서 및 정적 룰 엔진
│   │   │   ├── excel_rule_loader.py # 동적 헤더 스캔 (1~30행)
│   │   │   ├── excel_rule_compiler.py# 룰 컴파일 및 커버리지 계산
│   │   │   └── rule_engine.py       # 룰 실행 및 //nolint 억제 필터링
│   │   ├── parser/                  # CTL, PNL, XML 파서 및 인코딩 경고
│   │   ├── report/                  # JSON, HTML, CSV, Excel, PDF 리포트 생성기
│   │   ├── diff_filter.py          # git diff 변경 라인 스캔
│   │   ├── vcs_commenter.py         # GitHub PR / GitLab MR 인라인 코멘트 포맷터
│   │   ├── accepted_risk.py         # ACCEPTED_RISK 승인 감사 추적
│   │   ├── complexity.py            # 순환 복잡도 및 중첩 깊이 측정
│   │   ├── dp_variable_tracker.py   # DP 변수 호출 체인 추적기
│   │   └── autofix_validator.py     # 샌드박스 패치 AST 구문 검증기
│   └── rules/                       # 내장 정적 체커 모듈 (SCADA 보안 체커 등)
├── scripts/                         # 백그라운드 평가 및 익명화 스크립트
├── tests/                           # 193개 유닛 및 회귀 테스트 수트
└── config/                          # settings.yaml 및 Client/Server 엑셀 양식
```

## 4. 룰 카탈로그 수정 및 신규 정적 체커 추가 방법

### 4.1 엑셀 룰 카탈로그 수정
* 원천 위치: `config/(클라이언트) 코드 리뷰 결과서.xlsx` 및 `config/(서버) 코드 리뷰 결과서.xlsx`
* 엑셀 양식이 변경되어도 상단 1~30행을 동적 스캔하여 열 좌표를 자동 인지합니다.

### 4.2 신규 정적 체커 작성 및 레지스트리 등록 절차
1. `wincc_reviewer/app/rules/` 위치에 신규 체커 모듈 작성 (예: `check_custom_rule.py`)
2. 체커 함수 정의: `def check_custom_rule(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:`
3. `CheckerRegistry.register("ctl.custom_rule", check_custom_rule)` 등록
4. `wincc_reviewer/app/rules/__init__.py`에서 모듈을 임포트하여 자동 등록되도록 설정

## 5. 보안 및 백그라운드 관리 작업

### 5.1 API 키 및 환경변수 셋팅
* 사내 AI API 연동 시 환경변수 `WINCC_AI_API_KEY` 및 `LOCAL_AI_API_KEY` 사용 지원
* `app/utils/log_masker.py`에 의해 소스코드 스니펫 및 API 키는 로그 파일에 자동 마스킹됨

### 5.2 픽스처 데이터 익명화 스크립트 기동
```bash
python scripts/04_anonymize_dataset.py
```

## 6. 테스트, 회귀 검증 및 CI CD 워크플로우

### 6.1 회귀 테스트 전수 실행
```bash
pytest wincc_reviewer/tests/ -v
```

### 6.2 Precision 및 Recall 정밀 측정 스크립트 기동
```bash
python scripts/03_precision_recall_evaluator.py
```

### 6.3 GitHub Actions 파이프라인
* `.github/workflows/test.yml`: Push 및 PR 시 자동 pytest, ruff 린트, mypy 타입 체크 수행
* `.github/workflows/release.yml`: `git tag v*` push 시 PyInstaller 자동 빌드 및 Releases 이관

## 7. 지속 개발 시 필수 개발 준수 규칙 (Strict Rules)
* **원본 불변성 원칙**: 사용자의 원본 소스 파일은 어떠한 경우에도 직접 덮어쓰지 않습니다. 모든 자동 수정 결과물은 `.autofix.ctl` 별도 산출물로 생성됩니다.
* **텍스트 표기 규칙**: 보고서, 마크다운 문서, 코드 주석 작성 시 하이픈 기호를 사용하지 않습니다.
