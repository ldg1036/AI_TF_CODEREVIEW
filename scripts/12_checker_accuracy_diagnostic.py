"""
룰 기반 검출 정확도 진단 스크립트.

각 체커별로 (1) 반드시 검출해야 하는 positive 위반 코드와 (2) 반드시 PASS해야 하는 negative 준수 코드를
공급하여 모든 체커의 False Negative(미검출) 및 False Positive(오검출) 발생 여부를 동시에 검증합니다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wincc_reviewer"))

from app.core.parser.base_parser import ParsedFile, ParseStatus, ParseStatusType
from app.core.rules.rule_engine import RuleEngine
from app.core.models import RuleDefinition, CheckerType

# ──────────────── 헬퍼 ────────────────

def make_parsed(code: str, name: str = "test.ctl", ext: str = "ctl") -> ParsedFile:
    return ParsedFile(
        file_path=Path(name),
        file_type=ext,
        parse_status=ParseStatus(status=ParseStatusType.PARSED),
        content=code,
    )

def make_rule(rule_id: str, checker_type: str = "BUILTIN", checker_key: str = "",
              file_types=None) -> RuleDefinition:
    ct = {"BUILTIN": CheckerType.BUILTIN, "MANUAL": CheckerType.MANUAL,
          "REGEX": CheckerType.REGEX}[checker_type]
    return RuleDefinition(
        rule_id=rule_id,
        source_key=f"test|{rule_id}",
        file_types=file_types or ["CTL"],
        checker_type=ct,
        checker_key=checker_key,
        enabled=True,
        rule_version="1.0.0",
    )

results = []

def check(label: str, expect_detected: bool, code: str, rule: RuleDefinition):
    parsed = make_parsed(code)
    violations = RuleEngine.execute(parsed, [rule])
    detected = len(violations) > 0
    ok = detected == expect_detected
    status = "PASS" if ok else "**FAIL**"
    direction = "검출" if expect_detected else "PASS(미검출)"
    results.append((status, rule.rule_id, label, direction, len(violations)))
    if not ok:
        print(f"  [FAIL] {rule.rule_id} | {label} | 기대={direction} 실제={len(violations)}건")

# ──────── 1. ctl.dp_connect_pair ────────
rule_connect = make_rule("CTL_RES_001", "BUILTIN", "ctl.dp_connect_pair")

check("dpConnect만 있고 dpDisconnect 없음 → 검출", True,
      'void main(){\n  dpConnect("cb","S1:Tag.val");\n}', rule_connect)

check("dpConnect + dpDisconnect 쌍 존재 → PASS", False,
      'void main(){\n  dpConnect("cb","S1:Tag.val");\n}\nvoid onClose(){\n  dpDisconnect("cb","S1:Tag.val");\n}', rule_connect)

check("dpConnect가 주석 내부에만 존재 → PASS", False,
      '// dpConnect("cb","S1:Tag.val");\nvoid main(){}', rule_connect)

# ──────── 2. ctl.loop_delay ────────
rule_loop = make_rule("CTL_PRF_001", "BUILTIN", "ctl.loop_delay")

check("while(TRUE) 루프에 delay 없음 → 검출", True,
      'void main(){\n  while(TRUE){\n    dpGet("S:T.v",v);\n  }\n}', rule_loop)

check("while(TRUE) 루프에 delay 있음 → PASS", False,
      'void main(){\n  while(TRUE){\n    delay(1);\n    dpGet("S:T.v",v);\n  }\n}', rule_loop)

check("for(;;) 무한루프에 delay 없음 → 검출", True,
      'void main(){\n  for(;;){\n    dpSet("S:T.v",1);\n  }\n}', rule_loop)

check("for(int i=0; i<10; i++) 유한루프 delay 없음 → PASS", False,
      'void main(){\n  for(int i=0; i<10; i++){\n    dpSet("S:T.v",i);\n  }\n}', rule_loop)

check("while(i < count) 유한루프 delay 없음 → PASS", False,
      'void main(){\n  int i=0;\n  while(i < count){\n    i++;\n  }\n}', rule_loop)

# ──────── 3. ctl.try_catch ────────
rule_try = make_rule("CTL_ERR_002", "BUILTIN", "ctl.try_catch")

check("DP 함수 호출 함수에 try/catch 없음 → 검출", True,
      'void readTag(){\n  dpGet("S:T.v",v);\n}', rule_try)

check("DP 함수 호출 함수에 try/catch 있음 → PASS", False,
      'void readTag(){\n  try{\n    dpGet("S:T.v",v);\n  }catch{\n    DebugN("err");\n  }\n}', rule_try)

check("getLastError로 에러 처리 → PASS", False,
      'void readTag(){\n  dpGet("S:T.v",v);\n  if(getLastError()!=0){\n    DebugN("err");\n  }\n}', rule_try)

check("DP 함수 없는 일반 함수 → PASS", False,
      'void calcSum(int a, int b){\n  return a+b;\n}', rule_try)

# ──────── 4. ctl.batch_dp_ops ────────
rule_batch = make_rule("CTL_PRF_002", "BUILTIN", "ctl.batch_dp_ops")

check("단건 dpGet 5회 연속 호출 → 검출", True,
      'void main(){\n  dpGet("S:T1.v",v1);\n  dpGet("S:T2.v",v2);\n  dpGet("S:T3.v",v3);\n  dpGet("S:T4.v",v4);\n  dpGet("S:T5.v",v5);\n}', rule_batch)

check("다중 인자 dpGet 일괄처리 → PASS", False,
      'void main(){\n  dpGet("S:T1.v",v1,"S:T2.v",v2,"S:T3.v",v3,"S:T4.v",v4);\n}', rule_batch)

check("dpGet 호출 1건 → PASS", False,
      'void main(){\n  dpGet("S:T1.v",v1);\n}', rule_batch)

# ──────── 5. ctl.hardcoding ────────
rule_hc = make_rule("CTL_HARD_001", "BUILTIN", "ctl.hardcoding")

check("실제 IP 192.168.1.100 하드코딩 → 검출", True,
      'void main(){\n  string host = "192.168.1.100";\n}', rule_hc)

check("127.0.0.1 로컬 루프백 → PASS", False,
      'void main(){\n  string host = "127.0.0.1";\n}', rule_hc)

check("version 1.0.0.0 → PASS", False,
      'void main(){\n  string app_version = "version 1.0.0.0";\n}', rule_hc)

check("주석 내 IP → PASS", False,
      '// 서버 IP: 10.0.0.1\nvoid main(){}', rule_hc)

# ──────── 6. ctl.dp_error_handling ────────
rule_err = make_rule("CTL_ERR_003", "BUILTIN", "ctl.dp_error_handling")

check("dpGet 반환값 미검사 단독 호출 → 검출", True,
      'void main(){\n  dpGet("S:T.v",v);\n}', rule_err)

check("err = dpGet(...) 반환값 할당 → PASS", False,
      'void main(){\n  int err = dpGet("S:T.v",v);\n}', rule_err)

check("dpGet 후 if문 에러 체크 → PASS", False,
      'void main(){\n  dpGet("S:T.v",v);\n  if(err!=0) DebugN("err");\n}', rule_err)

# ──────── 7. ctl.dp_callback_delay ────────
rule_cbdelay = make_rule("MANUAL-004", "BUILTIN", "ctl.dp_callback_delay")

check("콜백 내 delay 있음 → 검출", True,
      'main(){\n  dpConnect("workCb","S:T.v");\n}\nvoid workCb(string dp, anytype val){\n  delay(5);\n  DebugN(val);\n}', rule_cbdelay)

check("콜백 내 delay 없음 → PASS", False,
      'main(){\n  dpConnect("workCb","S:T.v");\n}\nvoid workCb(string dp, anytype val){\n  DebugN(val);\n}', rule_cbdelay)

# ──────── 8. ctl.db_query_binding ────────
rule_dbq = make_rule("CTL_DB_001", "BUILTIN", "ctl.db_query_binding")

check("SQL + 문자열 동적 결합 → 검출", True,
      'void main(){\n  string q = "SELECT * FROM users WHERE id = " + userId;\n  dbExecuteQuery(q);\n}', rule_dbq)

check("DB함수 없는 일반 코드 → PASS", False,
      'void main(){\n  string msg = "Hello " + name;\n}', rule_dbq)


# ──────── 결과 출력 ────────
print("\n" + "="*80)
print("룰 기반 검출 정확도 종합 진단 결과")
print("="*80)
print(f"{'상태':<8} {'룰 ID':<16} {'시나리오':<45} {'기대':<12} {'건수'}")
print("-"*80)
for status, rid, label, direction, cnt in results:
    print(f"{status:<8} {rid:<16} {label:<45} {direction:<12} {cnt}")

total = len(results)
passed = sum(1 for r in results if r[0] == "PASS")
failed = total - passed
print("-"*80)
print(f"총 {total}건: 성공 {passed}건, 실패 {failed}건")
if failed > 0:
    print("\n*** 아래 항목은 검출 로직 개선이 필요합니다 ***")
    for r in results:
        if r[0] == "**FAIL**":
            print(f"  - [{r[1]}] {r[2]}")
