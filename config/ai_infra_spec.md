# Phase 2 AI 2차 리뷰 인프라 명세서 (config/ai_infra_spec.md)

작성일자: 2026년 8월 8일  
작성목적: 13번 실운영 전환 프로덕션 준비 로드맵 Phase 2 명세에 따른 온프레미스 AI 인프라 사양 및 보안 정책 정의

## 1. 로컬 LLM 사양 및 권장 모델

* 권장 배포 모델: Qwen2.5-Coder-7B-Instruct / Gemma-2B-Instruct
* 서버 최소 스펙: NVIDIA RTX 4090 (VRAM 24GB 이상) 또는 사내 vLLM/Ollama 온프레미스 클러스터
* 동시 처리 용량 목표: 리뷰어 동시 10인 접속 시 p95 응답 지연 시간 30초 이내 충족

## 2. 보안 가드레일 및 마스킹 정책

1. ALLOW_EXTERNAL_AI 보안 가드레일: 기본값 False (외부 전송 기본 차단)
2. 외부 AI 승인 시 마스킹: app/utils/log_masker.py를 통해 설비명, 태그명, IP 주소 자동 마스킹 수행
3. 헬스체크 및 폴백: health_check(check_timeout=2.0) 2초 이내 오프라인 감지 시 1차 정적 파이프라인 자동 폴백
