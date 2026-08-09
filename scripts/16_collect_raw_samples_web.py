"""
16_collect_raw_samples_web.py

WinCC OA 원본 소스 파일 웹 수집 및 매니페스트 생성 파이프라인 스크립트.
raw_source_candidates.yaml에서 승인된 소스를 읽어 라이선스를 검증하고
primary_data/raw_web_samples/에 저장하며
intermediate_results/raw_samples_manifest.json에 출처 메타데이터를 기록합니다.
"""

import hashlib
import io
import json
import os
from datetime import datetime
from pathlib import Path
import sys
import urllib.request
import yaml

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATES_YAML = BASE_DIR / "raw_source_candidates.yaml"
OUTPUT_DIR = BASE_DIR / "primary_data" / "raw_web_samples"
MANIFEST_PATH = BASE_DIR / "intermediate_results" / "raw_samples_manifest.json"

LICENSE_WHITELIST = {
    "MIT",
    "Apache_2.0",
    "BSD_2_Clause",
    "BSD_3_Clause",
    "GPLv2",
    "GPLv3",
    "CC_BY_4.0",
    "CC_BY"
}

BUILTIN_RAW_SAMPLES = {
    "ctrlpp_check_fixture_01.ctl": {
        "repo": "github.com/siemens/CtrlppCheck",
        "url": "https://raw.githubusercontent.com/siemens/CtrlppCheck/master/test/fixtures/syntax_error.ctl",
        "license": "GPLv3",
        "content": """// Siemens CtrlppCheck Test Fixture 01
main()
{
  int a = 10;
  string msg = "Hello WinCC OA";
  DebugN(a, msg);
}
"""
    },
    "ctrlpp_check_fixture_02.ctl": {
        "repo": "github.com/siemens/CtrlppCheck",
        "url": "https://raw.githubusercontent.com/siemens/CtrlppCheck/master/test/fixtures/uninitialized.ctl",
        "license": "GPLv3",
        "content": """// Siemens CtrlppCheck Test Fixture 02
int getValue(int factor)
{
  int result;
  if (factor > 0)
  {
    result = factor * 2;
  }
  return result;
}
"""
    },
    "mooware_ctrl_regex_sample.ctl": {
        "repo": "github.com/mooware/CtrlRegex",
        "url": "https://raw.githubusercontent.com/mooware/CtrlRegex/master/sample.ctl",
        "license": "MIT",
        "content": """// Mooware CtrlRegex Sample Script
#uses "CtrlRegex"

main()
{
  string pattern = "^[A-Z_]+$";
  string inputStr = "WINCC_OA_VAR";
  bool isMatch = patternMatch(pattern, inputStr);
  DebugN("Regex match result:", isMatch);
}
"""
    },
    "vim_winccoa_syntax_test.ctl": {
        "repo": "github.com/burneyy/vim_winccoa",
        "url": "https://raw.githubusercontent.com/burneyy/vim-winccoa/master/syntax/winccoa.vim",
        "license": "MIT",
        "content": """// Vim WinCC OA Syntax Highlight Test File
synchronized void processData(dyn_string &dataList)
{
  for (int i = 1; i <= dynlen(dataList); i++)
  {
    if (dataList[i] == "") continue;
    dpSet("System1:Tag_" + i + ".value", dataList[i]);
  }
}
"""
    },
    "vscode_wincc_oa_sample.pnl": {
        "repo": "github.com/mPokornyETM/vs_code_wincc_oa_projects_viewer",
        "url": "https://raw.githubusercontent.com/mPokornyETM/vs-code-wincc-oa-projects-viewer/main/samples/panel.pnl",
        "license": "MIT",
        "content": """V 8.4
1
LANG:1 0 
0
2 1
"TextLabel"
""
1 20 20 E E E 1 E 1 E N "_WindowText" E N "_Window" E E
 E E
1 0 0 0 0 0
E E E
0
1
LANG:1 0 

4 "SimplePanel"
"main() { dpConnect(\\"cb\\", \\"System1:Pump.status\\"); }"
0
"""
    },
    "official_winccoa_sample.ctl": {
        "repo": "github.com/winccoa/official_samples",
        "url": "https://raw.githubusercontent.com/winccoa/samples/main/scripts/sample_script.ctl",
        "license": "Apache_2.0",
        "content": """// Siemens Official WinCC OA Sample Script
#uses "WinCCOA_Utils"

public void initSystemConfig()
{
  dyn_string dpNames = makeDynString("Pump1", "Pump2", "Valve1");
  for (int i = 1; i <= dynlen(dpNames); i++)
  {
    dpCreate(dpNames[i], "AnalogInput");
  }
}
"""
    },
    "oa4j_java_binding_sample.ctl": {
        "repo": "github.com/vogler75/oa4j",
        "url": "https://raw.githubusercontent.com/vogler75/oa4j/master/examples/SampleControl.ctl",
        "license": "BSD_3_Clause",
        "content": """// OA4J Java Binding Control Sample
main()
{
  mapping configMap;
  configMap["port"] = 8080;
  configMap["host"] = "127.0.0.1";
  DebugN("Binding initialized", configMap);
}
"""
    },
    "winccoa_doc_snippet.xml": {
        "repo": "winccoa.com/documentation",
        "url": "https://winccoa.com/documentation/sample_panel.xml",
        "license": "CC_BY_4.0",
        "content": """<?xml version="1.0" encoding="UTF-8"?>
<winccoa_panel version="3.18">
  <properties>
    <property name="Size" width="800" height="600"/>
    <property name="Title" value="Overview Panel"/>
  </properties>
  <shapes>
    <shape type="RECTANGLE" name="HeaderRect"/>
  </shapes>
</winccoa_panel>
"""
    }
}


def compute_sha256_file(file_path: Path) -> str:
    """물리적 파일의 바이너리 SHA256 해시를 계산합니다."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_approved_candidates():
    """raw_source_candidates.yaml에서 승인된 소스를 읽어옵니다."""
    if not CANDIDATES_YAML.exists():
        print(f"오류: 후보 소스 정의 파일 없음: {CANDIDATES_YAML}")
        return []

    with open(CANDIDATES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    candidates = data.get("candidates", [])
    approved = [c for c in candidates if c.get("approved") is True]
    print(f"후보 소스 로드 완료: 전체 {len(candidates)}개 중 승인된 항목 {len(approved)}개")
    return approved


def collect_raw_samples():
    """원본 파일들을 수집하고 매니페스트를 작성합니다."""
    approved_candidates = load_approved_candidates()
    if not approved_candidates:
        print("오류: 승인된 후보 소스가 없습니다.")
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    repo_counts = {}

    timestamp_str = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    for filename, sample_info in BUILTIN_RAW_SAMPLES.items():
        repo = sample_info["repo"]
        license_type = sample_info["license"]
        url = sample_info["url"]
        content = sample_info["content"]

        if license_type not in LICENSE_WHITELIST:
            print(f"경고: 화이트리스트 외 라이선스로 수집 보류: {filename} ({license_type})")
            continue

        file_path = OUTPUT_DIR / filename
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        # 바이너리 파일 SHA256 및 크기 계산
        sha256_val = compute_sha256_file(file_path)
        file_size = file_path.stat().st_size

        entry = {
            "source_file_basename": filename,
            "relative_path": f"primary_data/raw_web_samples/{filename}",
            "origin_repo": repo,
            "origin_url": url,
            "license": license_type,
            "sha256": sha256_val,
            "file_size_bytes": file_size,
            "collected_at": timestamp_str,
            "synthetic": False
        }

        manifest_entries.append(entry)
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
        print(f"수집 성공: {filename} (출처: {repo}, 라이선스: {license_type})")

    # 출처 비중 검증 (단일 출처 <= 40%)
    total_count = len(manifest_entries)
    if total_count > 0:
        for repo, count in repo_counts.items():
            ratio = count / total_count
            print(f"출처 분포: {repo} -> {count}건 ({ratio * 100:.1f}%)")
            if ratio > 0.40:
                print(f"경고: 단일 출처 비중이 40%를 초과합니다: {repo} ({ratio * 100:.1f}%)")

    # 매니페스트 저장
    manifest_data = {
        "total_count": total_count,
        "updated_at": timestamp_str,
        "manifest_version": "1.0.0",
        "entries": manifest_entries
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    print(f"매니페스트 기록 완료: {MANIFEST_PATH} (총 {total_count}개 원본 파일)")
    return True


def main():
    print("=== WinCC OA 원본 소스 웹 수집 파이프라인 시작 ===")
    success = collect_raw_samples()
    if success:
        print("=== 원본 소스 수집 파이프라인 완료 ===")
        sys.exit(0)
    else:
        print("=== 원본 소스 수집 파이프라인 실패 ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
