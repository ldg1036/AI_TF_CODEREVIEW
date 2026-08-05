# PNL 및 XML 스크립트 전용 추출 UI 옵션 연동 보고서

## 1. 개요 및 배경

사용자가 UI 메인 화면 및 환경설정(`settings.yaml`)에서 PNL/XML 파일 검사 시 레이아웃 태그를 제외하고 스크립트만 추출하여 리뷰할지 여부를 자유롭게 선택할 수 있도록 옵션 체계를 구축하였습니다.

## 2. 주요 구현 내역

1. **`app/core/pipeline.py` 설정 연동**
   * `PipelineConfig` 데이터클래스에 `extract_scripts_only: bool = True` 필드 추가
   * `Pipeline.run()` 시 `NormalizationService`로 해당 옵션을 전달하도록 연결

2. **파서 및 정규화 서비스 연동**
   * `NormalizationService.normalize_and_parse()`에 `extract_scripts_only` 매개변수 반영 및 캐시 키 분리
   * `PNLParser` 및 `XMLParser`에 `extract_scripts_only` 플래그 주석 및 조건부 정제 처리 적용

3. **`app/ui/api.py` 및 `app/ui/index.html` 연동**
   * 메인 사이드바 옵션 창에 **"PNL/XML 스크립트만 추출하여 리뷰"** 체크박스 추가
   * `settings.yaml` 파일에 `parser.extract_scripts_only` 항목을 실시간 로딩 및 저장하도록 연결

## 3. 기대 효과

* 사용자의 선택에 따라 원본 XML 태그 구문 전체 검사 또는 순수 스크립트 정제 검사로 유연하게 전환 가능
* 기본 설정(`True`) 유지 시 AI 프롬프트 경량화 및 정적 검사 속도 극대화 지속 유지
