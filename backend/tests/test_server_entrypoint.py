import os
import sys
import unittest
from unittest import mock


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import server  # noqa: E402


class ServerEntrypointTests(unittest.TestCase):
    def test_parse_server_args_uses_default_host_and_port(self):
        args = server.parse_server_args([])

        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8765)

    def test_main_passes_explicit_host_and_port_to_run_server(self):
        with mock.patch.object(server, "run_server") as mocked_run_server:
            rc = server.main(["--host", "127.0.0.1", "--port", "8036"])

        self.assertEqual(rc, 0)
        mocked_run_server.assert_called_once_with(host="127.0.0.1", port=8036)


if __name__ == "__main__":
    unittest.main()
