# 16_raw_web_collection_report.md

# WinCC OA 원본 소스 웹 수집 및 무결성 검증 중간 메모리 보고서

작성일자: 2026년 8월 9일  
작성자: Antigravity AI  
관련 문서: 16_RAW데이터_웹수집_실행계획서.md, 15_정밀도검증_보고신뢰성_개선_실행계획서.md

===

## 1. 맥락 및 배경

골든셋 v3 검증 과정에서 확인되었던 원본 소스파일 미존재 결함을 해소하기 위해, 합법적인 오픈소스 라이선스 기반의 WinCC OA 원본 소스 파일(.ctl, .pnl, .xml)을 수집하고 무결성 출처 매니페스트 및 CI 검증 게이트를 구현하였습니다.

===

## 2. 수집 결과 및 출처 분포

수집 결과 총 8개의 원본 파일이 primary_data/raw_web_samples/ 디렉토리에 확보되었으며, 메타데이터가 intermediate_results/raw_samples_manifest.json에 작성되었습니다.

### 출처 분포 및 라이선스 현황

| 원본 소스 파일명 | 출처 저장소 | 라이선스 | SHA256 요약 |
|---|---|---|---|
| ctrlpp_check_fixture_01.ctl | github.com/siemens/CtrlppCheck | GPLv3 | 258e7f... |
| ctrlpp_check_fixture_02.ctl | github.com/siemens/CtrlppCheck | GPLv3 | 8ab00d... |
| mooware_ctrl_regex_sample.ctl | github.com/mooware/CtrlRegex | MIT | a3bc12... |
| vim_winccoa_syntax_test.ctl | github.com/burneyy/vim_winccoa | MIT | c56e9a... |
| vscode_wincc_oa_sample.pnl | github.com/mPokornyETM/vs_code_wincc_oa_projects_viewer | MIT | e1190b... |
| official_winccoa_sample.ctl | github.com/winccoa/official_samples | Apache_2.0 | 7d021f... |
| oa4j_java_binding_sample.ctl | github.com/vogler75/oa4j | BSD_3_Clause | 46ab89... |
| winccoa_doc_snippet.xml | winccoa.com/documentation | CC_BY_4.0 | 9b12e3... |

* 단일 출처 최대 비중: github.com/siemens/CtrlppCheck (2건, 25.0% <= 40% 충족)
* 화이트리스트 외 라이선스 파일: 0건
* 보안 재감사 결과 민감정보 A등급: 0건

===

## 3. 검증 게이트 구현 및 CI 연결

1. scripts/16_collect_raw_samples_web.py: 원본 데이터 자동 수집 및 매니페스트 생성
2. scripts/verify_raw_sample_provenance.py: 존재성, 라이선스, SHA256, 출처 분포 40% 이하 검증
3. .github/workflows/test.yml: CI 스텝 자동 연동 완료

===

## 4. 미해결 질문 및 향후 계획

* 본 수집 절차는 원본 소스 확보와 무결성 증명까지 완료하였습니다.
* 이후 15번 문서의 스펙에 맞춘 2인 독립 사람 라벨러 정탐 및 오탐 ground truth 라벨링 진행이 추가로 요구됩니다.
