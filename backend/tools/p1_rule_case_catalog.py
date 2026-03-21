from copy import deepcopy
from typing import Any, Dict, Optional


_COMPLEXITY_POS = "main(){\n" + "\n".join(["int a=0;" for _ in range(520)]) + "\n}"
_COMPLEXITY_NEG = "main(){\n  int a=0;\n  int b=1;\n  DebugN(a+b);\n}\n"


# Curated rule cases prioritized for previously failed rules + STYLE-HEADER-01.
_RULE_CASES: Dict[str, Dict[str, Any]] = {
    "PERF-02": {
        "file_type": "Server",
        "positive_code": 'main(){ dpQuery("SELECT \'_online.._value\' FROM \'**\'", result); }',
        "negative_code": 'main(){ dpQuery("SELECT \'_online.._value\' FROM \'A.B.C\'", result); }',
        "notes": "regex wildcard FROM '*.**' trigger",
    },
    "SEC-01": {
        "file_type": "Server",
        "positive_code": 'main(){ sprintf(sql, "SELECT * FROM users WHERE name = \'%s\'", input); }',
        "negative_code": 'main(){ dpQuery("SELECT * FROM users WHERE id = $1", args); }',
        "notes": "sprintf + SQL keyword + %s",
    },
    "legacy-check_complexity": {
        "file_type": "Server",
        "positive_code": _COMPLEXITY_POS,
        "negative_code": _COMPLEXITY_NEG,
        "notes": "line-count trigger (>500 lines) for COMP-01",
    },
    "DB-ERR-01": {
        "file_type": "Server",
        "positive_code": 'main(){ dpQuery("SELECT * FROM T", result); }',
        "negative_code": 'main(){ dpQuery("SELECT * FROM T", result); DebugTN(getLastError()); }',
        "notes": "query call without logging",
    },
    "EXC-DP-01": {
        "file_type": "Server",
        "positive_code": 'main(){ dpSet("A.B.C", 1); }',
        "negative_code": 'main(){ try { dpSet("A.B.C", 1); } catch { DebugTN(getLastError()); } }',
        "notes": "dp function call missing exception contract",
    },
    "CFG-01": {
        "file_type": "Server",
        "positive_code": (
            "bool load_config(){\n"
            "  string config_line = raw_config_list[1];\n"
            "  dyn_string a = strsplit(config_line, \",\");\n"
            "  dyn_string b = strsplit(config_line, \";\");\n"
            "  return true;\n"
            "}"
        ),
        "negative_code": (
            "bool load_config(){\n"
            "  string config_line = raw_config_list[1];\n"
            "  dyn_string parts = strsplit(config_line, \"|\");\n"
            "  dyn_string tank_list = strsplit(parts[6], \",\");\n"
            "  if (dynlen(parts) < 7) { return false; }\n"
            "  return true;\n"
            "}"
        ),
        "notes": "same source split with conflicting delimiters",
    },
    "CFG-ERR-01": {
        "file_type": "Server",
        "positive_code": (
            "bool load_config(){\n"
            "  dyn_string parts = strsplit(raw, \",\");\n"
            "  if (dynlen(parts) < 7) {\n"
            "    continue;\n"
            "  }\n"
            "  return true;\n"
            "}"
        ),
        "negative_code": (
            "bool load_config(){\n"
            "  dyn_string parts = strsplit(raw, \",\");\n"
            "  if (dynlen(parts) < 7) { return false; }\n"
            "  return true;\n"
            "}"
        ),
        "notes": "continue without fail return",
    },
    "PERF-SETMULTIVALUE-ADOPT-01": {
        "file_type": "Server",
        "positive_code": (
            "void f(){\n"
            "  setValue(\"A.B.C1\", v1);\n"
            "  setValue(\"A.B.C2\", v2);\n"
            "  setValue(\"A.B.C3\", v3);\n"
            "}"
        ),
        "negative_code": 'void f(){ setMultiValue("A.B.C1", v1, "A.B.C2", v2, "A.B.C3", v3); }',
        "notes": "nearby setValue cluster without setMultiValue",
    },
    "PERF-GETMULTIVALUE-ADOPT-01": {
        "file_type": "Server",
        "positive_code": (
            "void f(){\n"
            "  getValue(\"A.B.C1\", v1);\n"
            "  getValue(\"A.B.C2\", v2);\n"
            "  getValue(\"A.B.C3\", v3);\n"
            "}"
        ),
        "negative_code": "void f(){ getMultiValue(dpList, values); }",
        "notes": "nearby getValue cluster without getMultiValue/cache",
    },
    "SAFE-DIV-01": {
        "file_type": "Server",
        "positive_code": (
            "bool load_config(){\n"
            "  dyn_string parts = strsplit(raw_config_list[1], \"|\");\n"
            "  int count = dynlen(parts);\n"
            "  ratio = total / count;\n"
            "  return true;\n"
            "}"
        ),
        "negative_code": (
            "bool load_config(){\n"
            "  dyn_string parts = strsplit(raw_config_list[1], \"|\");\n"
            "  int count = dynlen(parts);\n"
            "  if (count > 0) { ratio = total / (float)count; }\n"
            "  return true;\n"
            "}"
        ),
        "notes": "strong config parsing context division without guard",
    },
    "PERF-DPSET-CHAIN": {
        "file_type": "Server",
        "positive_code": (
            "main(){\n"
            "  dpSet(\"A.B.C\", 1);\n"
            "  dpSet(\"A.B.D\", 2);\n"
            "}"
        ),
        "negative_code": (
            "main(){\n"
            "  if (oldVal != newVal) { dpSetWait(\"A.B.C\", newVal); }\n"
            "  dpSet(\"A.B.D\", 2);\n"
            "}"
        ),
        "notes": "consecutive dpSet without guard/batch",
    },
    "VAL-01": {
        "file_type": "Server",
        "positive_code": (
            "main(){\n"
            "  int value;\n"
            "  dpGet(\"A.B.C\", value);\n"
            "}"
        ),
        "negative_code": (
            "main(){\n"
            "  int value;\n"
            "  dpGet(\"A.B.C\", value);\n"
            "  if (strlen(text) > 0) { value = atoi(text); }\n"
            "}"
        ),
        "notes": "input source without validation helper",
    },
    "STD-01": {
        "file_type": "Server",
        "positive_code": (
            "main(){\n"
            "  int missing\n"
            "}"
        ),
        "negative_code": (
            "main(){\n"
            "  int ready = 1;\n"
            "}"
        ),
        "notes": "declaration semicolon missing",
    },
    "HARD-03": {
        "file_type": "Server",
        "positive_code": (
            "void f(){\n"
            "  fallback = 0.001;\n"
            "  if (x < 0.001) return;\n"
            "}"
        ),
        "negative_code": (
            "const float MIN_USAGE = 0.001;\n"
            "void f(){\n"
            "  fallback = MIN_USAGE;\n"
            "  if (x < MIN_USAGE) return;\n"
            "}"
        ),
        "notes": "repeated float literal hardcoding",
    },
    "UI-BLOCK": {
        "file_type": "Server",
        "positive_code": "Initialize(){ delay(1); }",
        "negative_code": "Initialize(){ dpSetWait(\"A.B\", 1); }",
        "notes": "Initialize event + delay(",
    },
    "LOG-DBG-01": {
        "file_type": "Server",
        "positive_code": (
            "main(){\n"
            "  catch {\n"
            "    err = getLastError;\n"
            "  }\n"
            "}"
        ),
        "negative_code": (
            "main(){\n"
            "  catch {\n"
            "    DebugTN(getLastError());\n"
            "  }\n"
            "}"
        ),
        "notes": "trigger word exists but no writeLog/DebugN/DebugTN call",
    },
    "LOG-LEVEL-01": {
        "file_type": "Server",
        "positive_code": (
            "main(){\n"
            "  catch {\n"
            "    writeLog(\"Script\", \"failed\", LV_INFO);\n"
            "  }\n"
            "}"
        ),
        "negative_code": (
            "main(){\n"
            "  catch {\n"
            "    writeLog(\"Script\", \"failed\", LV_WARN);\n"
            "  }\n"
            "}"
        ),
        "notes": "error trigger logged only at info level",
    },
    "DUP-ACT-01": {
        "file_type": "Client",
        "positive_code": (
            "main(){\n"
            "  setValue(\"OBJ_A\", \"visible\", true);\n"
            "  setValue(\"OBJ_A\", \"visible\", false);\n"
            "  setValue(\"OBJ_A\", \"visible\", true);\n"
            "}"
        ),
        "negative_code": (
            "main(){\n"
            "  if (prev != value) {\n"
            "    setValue(\"OBJ_A\", \"visible\", value);\n"
            "    setValue(\"OBJ_A\", \"visible\", value);\n"
            "  }\n"
            "}"
        ),
        "notes": "duplicate same target/attr with no guard keyword",
    },
    "STYLE-HEADER-01": {
        "file_type": "Server",
        "positive_code": (
            "void f(){\n"
            "  int x = 0;\n"
            "}\n"
        ),
        "negative_code": (
            "// header line 1\n"
            "// header line 2\n"
            "void f(){\n"
            "  int x = 0;\n"
            "}\n"
        ),
        "notes": "header comment count threshold(>=2) clear",
    },
    "STYLE-NAME-01": {
        "file_type": "Server",
        "positive_code": (
            "int value = 0;\n"
            "main(){\n"
            "  DebugN(value);\n"
            "}\n"
        ),
        "negative_code": (
            "int g_value = 0;\n"
            "const int g_release_version = 1;\n"
            "main(){\n"
            "  DebugN(g_value);\n"
            "}\n"
        ),
        "notes": "generic global without g_ prefix remains a style hit",
    },
}


def get_rule_case(rule_id: str) -> Optional[Dict[str, Any]]:
    row = _RULE_CASES.get(str(rule_id or ""))
    if row is None:
        return None
    return deepcopy(row)
