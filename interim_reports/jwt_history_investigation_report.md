# JWT 키 Git 히스토리 조사 결과 보고서

작성일: 2026-08-10

## 조사 배경

여러 라운드에 걸쳐 "config/settings.yaml에서 JWT 키 발견" → "삭제 완료"로 보고되었으나,
`git log --all -p | grep eyJ`에서 여전히 검출된다는 문제가 제기되었습니다.

## 조사 방법 및 결과

### 1단계: settings.yaml 특정 파일 히스토리 조사

```
git log --all -p -- config/settings.yaml | grep eyJ → 0건
git log --all --oneline -- config/settings.yaml → (출력 없음)
git ls-files config/settings.yaml → (출력 없음, untracked)
```

**결론**: `config/settings.yaml` 파일 자체가 Git 히스토리에 한 번도 커밋된 적이 없습니다.
`.gitignore`에 등록되어 있으며, 히스토리에 존재하는 것은 `config/settings.yaml.example`뿐입니다.

### 2단계: 전체 히스토리에서 eyJ 패턴 조사

```
git log --all -p | grep eyJ → 20건 검출
```

20건을 개별 분석한 결과:
- Base64 인코딩된 DigiCert CA 인증서 번들 내 우연한 문자열 일치 (`weyJ`, `veyJ`): 14건
- numpy wheel RECORD 파일의 SHA256 해시 내 우연한 문자열 일치 (`IqeyJf`): 4건
- 동일 내용의 추가(+)/삭제(-) 쌍: 2건

**예시**:
```
-DpFrdRbhIfzYJsdHt6bPWHJxfrrhTZVHO8mvbaG0weyJ9rQPOLXiZNwlz6bb65pc  ← CA 인증서 Base64
-emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=  ← CA 인증서 Base64
-numpy/lib/user_array.pyi,sha256=IaCNerLboKjt3Fm-_k_d8IqeyJf7Lc9Pr5ROUr6wleM,54  ← wheel 해시
```

### 3단계: yaml 파일 한정 조사

```
git log --all -p -- "*.yaml" | grep eyJ → 0건
```

## 최종 판정

**JWT 키가 실제로 Git 히스토리에 노출된 적이 없습니다.**

`eyJ` 검출 20건은 모두 인증서 번들/패키지 해시의 우연한 Base64 부분 문자열 일치입니다.
JWT 토큰은 일반적으로 `eyJhbGci`(alg 헤더) 또는 `eyJzdWIi`(sub 클레임) 패턴으로 시작하며,
검출된 20건 중 이러한 패턴과 일치하는 것은 0건입니다.

## 조치 사항

- `git filter-repo` 실행: **불필요** (실행 시 히스토리 재작성으로 기존 참조를 깨뜨릴 위험만 발생)
- 키 폐기(rotate): **해당 없음** (노출된 키가 없으므로)
- `config/settings.yaml`은 `.gitignore`에 등록되어 있어 향후에도 실수로 커밋되지 않음
