# 17_RAW데이터_실운영_무결성_및_사람라벨링_실행계획서.md

# RAW 데이터 실운영 네트워크 무결성 검증 및 2인 독립 사람 라벨링 실행계획서

작성 목적: 16회차 수집 파이프라인에서 드러난 자가 마킹 승인 취약점과 웹 HTTP 200 OK 네트워크 존재성 검증 미비점을 전면 해소하고, 2인 독립 사람 라벨링(Ground Truth) 체계를 정립하여 골든셋 v3의 과학적 신뢰성과 투명성을 완성한다.

범위: 본 문서는 실제 웹 HTTP 접속 기반 무결성 검증, 사람 승인 서명 검증, 2인 독립 라벨러 기반 Ground Truth 산출 및 Fleiss Kappa 합의율 평가 스펙을 다룬다.

===

## 0. 개요 및 핵심 개편 방향

기존 수집 방식의 한계를 극복하고 실운영 수준의 신뢰도를 확보하기 위해 다음 4대 개편을 강제한다.

* 실시간 HTTP 200 OK 웹 응답 검증: 모든 원본 소스는 실제 웹 통신을 수행하여 HTTP status 200 OK 응답을 확인한 경우에만 매니페스트에 편입한다.
* 사람 승인 서명(Human_in_the_Loop Signature) 강제: raw_source_candidates.yaml에 사람이 직접 작성한 승인자 이메일, 승인 일시, 사유가 포함되어야 다운로드가 허용된다.
* 2인 독립 사람 라벨링(Ground Truth) 체계: 수집된 원본 데이터에 대해 2명의 사람이 독립적으로 라벨링을 수행하며 rationale 및 소요 시간을 기록한다.
* 골든셋 정밀도 평가의 물리적 분리: 사람 라벨링이 완료되지 않은 원본 파일은 synthetic: false 일지라도 골든셋 정밀도 평가 대상에서 배제한다.

===

## 1. 네트워크 HTTP 200 OK 존재성 검증 규격

1. 수집 파이프라인 실행 시 candidates 목록의 origin_url로 실제 HTTP HEAD 또는 GET 요청을 발송한다.
2. HTTP status code가 200 OK가 아니거나 타임아웃(5초) 발생 시 매니페스트 등록을 즉시 차단하고 로그를 남긴다.
3. verify_raw_sample_provenance.py CI 게이트는 매니페스트 내 origin_url에 대해 무작위 핑 테스트를 수행하여 URL 실존성을 자동 검증한다.

===

## 2. 사람 승인 서명 (Human_in_the_Loop) 규격

raw_source_candidates.yaml의 candidate 항목은 다음 3가지 사람 서명 필드를 필수로 포함해야 승인(approved: true)으로 인정된다.

* approver_email: 승인자 공식 이메일 주소 (AI 에이전트 계정 불가)
* approved_at: 사람이 검토를 완료한 타임스탬프 (YYYY_MM_DD HH:MM:SS)
* approval_rationale: URL 접속 및 라이선스 확인 결과 사유 (최소 10자 이상)

AI 에이전트가 위 승인 서명 없이 approved: true를 임의로 마킹하는 경우 CI 빌드에서 자동 거부된다.

===

## 3. 2인 독립 사람 라벨링 (Ground Truth) 및 합의율 규격

### 3.1 라벨링 스펙
* 라벨러 조건: SCADA / WinCC OA 도메인 지식을 가진 2인의 독립 검토자
* 기록 항목:
  1. labeler1_id 및 labeler2_id
  2. is_true_positive (정탐 여부 boolean)
  3. rationale (판단 근거 문구, 템플릿 재사용 금지)
  4. labeling_duration_seconds (라벨링 소요 시간)

### 3.2 상호 합의율 (Inter_Annotator Agreement) 지표
2인 라벨러 간의 일치도를 측정하기 위해 Cohen Kappa 및 Fleiss Kappa 지표를 산출한다.
* Kappa >= 0.81: 완벽한 합의 (골든셋 최종 승인)
* 0.61 <= Kappa < 0.81: 상당한 합의 (불일치 항목 재검토 후 확정)
* Kappa < 0.61: 합의 실패 (해당 샘플 골든셋 제외)

===

## 4. 파이프라인 및 CI 게이트 연동

1. scripts/16_collect_raw_samples_web.py: HTTP 200 OK 네트워크 통신 수집 및 승인 서명 검증
2. scripts/verify_raw_sample_provenance.py: 로컬 파일 존재성, SHA256, HTTP 200 OK 실존성, 사람 승인 서명 CI 자동 검증
3. .github/workflows/test.yml: 모든 Pull Request 및 Commit 시 자동 실행

===

## 5. 완료 기준 (DoD)

* raw_samples_manifest.json의 모든 URL이 실제 HTTP 200 OK 접속 가능함
* raw_source_candidates.yaml 내 사람 승인 서명 유효성 검증 PASS
* verify_raw_sample_provenance.py CI 게이트 통과
* 2인 독립 라벨링 합의율 Kappa 지표 0.81 이상 달성
* interim_reports/17_raw_provenance_and_human_labeling_report.md 작성 완료
