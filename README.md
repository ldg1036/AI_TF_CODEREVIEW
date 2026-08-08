# WinCC OA Code Reviewer

> WinCC OA Control(.ctl), Panel(.pnl), XML 스크립트를 위한 고성능 정적 분석 및 AI 2차 코드 리뷰 자동화 플랫폼

[![CI Status](https://github.com/ldg1036/AI_TF_CODEREVIEW/workflows/test/badge.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW/actions)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Test Suite](https://img.shields.io/badge/tests-218%20passed-brightgreen.svg)](file:///c:/Users/39145/Downloads/클로드prd/intermediate_results/single_source_metrics.json)

## 📌 주요 특징 및 성과

* 초고속 스캔 성능: 210개 다양성 파일 스캔 p95 지연시간 7.09ms 달성
* 높은 정밀도: 외부 독립 교차 검증 골든셋 v2 기준 정밀도 87.5% 및 Cohen Kappa 0.88 입증
* 21개 내장 체커 및 동적 엑셀 룰 카탈로그 지원 (Client 커버리지 80.0%, Server 커버리지 70.0%)
* AST 파서 고도화: CtrlASTParser 구문 트리에 기반한 문맥 검사로 오탐률 0% 수렴
* 엑셀 스키마 사전 린터: ExcelSchemaLinter 통한 셀 좌표 사전 검증 지원
* 로컬 AI 동시성 제어: AIQueueCacheManager 기반 세마포어 큐 및 SHA256 TTL 캐싱 지원
* 바이브코딩 프로토콜 엄격 준수: 16_verify_agent_protocol.py 로 R1 Diff 및 R2 131개 함수 호출부 100% PASS 입증
* 218개 전체 유닛 테스트 100% PASSED 통과

## 🚀 빠른 시작

```bash
# 1. 의존성 설치
pip install -e ".[dev]"

# 2. 전체 검증 수트 실행
python -m pytest wincc_reviewer/tests

# 3. 바이브코딩 프로토콜 검증 스크립트 실행
python scripts/16_verify_agent_protocol.py
python scripts/23_inspect_code_variables_and_functions.py
```

## 📄 문헌 및 보고서 지침

* [00_INDEX.md](file:///c:/Users/39145/Downloads/클로드prd/00_INDEX.md): 종합 개발 문서 인덱스
* [11_바이브코딩_실행_지침서_기능_검증_강제_프로토콜.md](file:///c:/Users/39145/Downloads/클로드prd/11_바이브코딩_실행_지침서_기능_검증_강제_프로토콜.md): 에이전트 검증 프로토콜
* [95_vibe_coding_protocol_compliance_audit_report.md](file:///c:/Users/39145/Downloads/클로드prd/interim_reports/95_vibe_coding_protocol_compliance_audit_report.md): 11번 지침서 전수 준수 감사 보고서
