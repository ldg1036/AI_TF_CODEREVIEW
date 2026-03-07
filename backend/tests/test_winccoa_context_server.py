import http.client
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tools.winccoa_context_server import WinCCOAContextHandler, WinCCOAContextProvider


class WinCCOAContextProviderTests(unittest.TestCase):
    def test_rules_index_exposes_rule_ids_and_type_counts(self):
        provider = WinCCOAContextProvider(project_root=PROJECT_ROOT)
        payload = provider.rules_index()

        self.assertIn("counts", payload)
        self.assertIn("types", payload)
        self.assertIn("Client", payload["types"])
        self.assertIn("Server", payload["types"])
        self.assertGreater(payload["counts"]["indexed_items"], 0)
        self.assertGreater(len(payload.get("rule_ids", [])), 0)

    def test_get_rule_resolves_known_rule_id(self):
        provider = WinCCOAContextProvider(project_root=PROJECT_ROOT)
        payload = provider.get_rule("PERF-02")

        self.assertTrue(payload["found"])
        self.assertEqual(payload["rule_id"], "PERF-02")
        self.assertIn("items", payload)
        self.assertGreaterEqual(len(payload["items"]), 1)

    def test_template_coverage_is_fail_soft_when_loader_errors(self):
        def raising_loader(_project_root):
            raise RuntimeError("coverage unavailable for test")

        provider = WinCCOAContextProvider(project_root=PROJECT_ROOT, template_coverage_loader=raising_loader)
        payload = provider.find_template_coverage(query="dp", scope="Client")

        self.assertFalse(payload["available"])
        self.assertIn("coverage unavailable for test", payload["error"])


class _StubProvider:
    def context_payload(self):
        return {"projectName": "Stub", "read_only": True}

    def drivers_payload(self):
        return {"drivers": [{"name": "PROJECT_CONTEXT"}, {"name": "RULE_INDEX"}]}

    def rules_index(self):
        return {"counts": {"indexed_items": 2}, "rule_ids": ["R1", "R2"]}

    def get_rule(self, rule_id):
        return {"found": True, "rule_id": rule_id, "items": [{"item": "Sample"}]}

    def find_template_coverage(self, query="", scope=None, refresh=False, include_unmatched_rows=False):
        return {
            "available": True,
            "query": query,
            "scope": scope or "all",
            "refresh": bool(refresh),
            "include_unmatched_rows": bool(include_unmatched_rows),
        }


class WinCCOAContextApiTests(unittest.TestCase):
    def setUp(self):
        self.provider = _StubProvider()

        def handler(*args, **kwargs):
            return WinCCOAContextHandler(*args, provider=self.provider, **kwargs)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)

    def _request(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        conn.close()
        return resp.status, json.loads(raw) if raw else {}

    def test_context_and_drivers_endpoints(self):
        status, payload = self._request("/context")
        self.assertEqual(status, 200)
        self.assertEqual(payload["projectName"], "Stub")

        status, payload = self._request("/drivers")
        self.assertEqual(status, 200)
        self.assertIn("drivers", payload)
        self.assertEqual(len(payload["drivers"]), 2)

    def test_get_rule_endpoint_requires_rule_id(self):
        status, payload = self._request("/tools/get_rule")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_tool_endpoints_forward_query_parameters(self):
        status, payload = self._request("/tools/get_rule?rule_id=R1")
        self.assertEqual(status, 200)
        self.assertEqual(payload["rule_id"], "R1")

        status, payload = self._request(
            "/tools/find_template_coverage?q=dp&scope=Client&refresh=true&include_unmatched_rows=yes"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["query"], "dp")
        self.assertEqual(payload["scope"], "Client")
        self.assertTrue(payload["refresh"])
        self.assertTrue(payload["include_unmatched_rows"])


if __name__ == "__main__":
    unittest.main()
