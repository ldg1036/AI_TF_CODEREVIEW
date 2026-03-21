import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.heuristic_checker import HeuristicChecker  # noqa: E402


def _rule_ids(results):
    ids = set()
    for item in results or []:
        for violation in item.get("violations", []) or []:
            ids.add(str(violation.get("rule_id", "") or ""))
    return ids


class P1PrecisionTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = HeuristicChecker()

    def test_perf_01_requires_delay_inside_callback_body(self):
        code = """
void OnDpChanged()
{
  delay(1);
}

main()
{
  dpConnect("OnDpChanged", "System1:Example.Value:_online.._value");
}
""".strip()

        results = self.checker.analyze_raw_code("sample.ctl", code)
        self.assertIn("PERF-01", _rule_ids(results))

    def test_perf_01_does_not_fire_for_connect_then_delay_in_main(self):
        code = """
void OnDpChanged()
{
  int count = 1;
}

main()
{
  dpConnect("OnDpChanged", "System1:Example.Value:_online.._value");
  delay(1);
}
""".strip()

        results = self.checker.analyze_raw_code("sample.ctl", code)
        self.assertNotIn("PERF-01", _rule_ids(results))

    def test_cfg_01_ignores_nested_valid_strsplit_sources(self):
        code = """
bool load_config()
{
  string config_file = "config/sample.ini";
  dyn_string raw_config_list;
  dyn_string parts = strsplit(raw_config_list[1], "|");
  dyn_string tank_list = strsplit(parts[6], ",");
  if (dynlen(parts) < 6)
  {
    return false;
  }
  return true;
}
""".strip()

        results = self.checker.analyze_raw_code("sample.ctl", code)
        self.assertNotIn("CFG-01", _rule_ids(results))

    def test_safe_div_01_ignores_guarded_casted_denominator(self):
        code = """
bool load_config()
{
  dyn_string parts;
  float sum = 10.0;
  int validCount = 1;
  if (dynlen(parts) < 1)
  {
    return false;
  }
  if (validCount > 0)
  {
    float avg = sum / (float)validCount;
  }
  return true;
}
""".strip()

        results = self.checker.analyze_raw_code("sample.ctl", code)
        self.assertNotIn("SAFE-DIV-01", _rule_ids(results))

    def test_style_name_01_ignores_fixture_locals_and_function_names(self):
        code = """
bool load_config()
{
  int v1 = 1;
  return true;
}

main()
{
  int v2 = 2;
}
""".strip()

        results = self.checker.analyze_raw_code("sample.ctl", code)
        self.assertNotIn("STYLE-NAME-01", _rule_ids(results))


if __name__ == "__main__":
    unittest.main()
