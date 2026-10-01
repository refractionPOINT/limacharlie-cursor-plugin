"""Regression checks for connectivity-only packaging and discovery."""
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_mcp_tools as checker


class PluginChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "plugin"
        shutil.copytree(checker.PLUGIN_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", ".git", ".venv"))

    def test_connection_configuration(self):
        checker.check_plugin(self.root, offline=True)
        path = self.root / "mcp.json"
        config = json.loads(path.read_text())
        config["mcpServers"]["limacharlie"]["headers"] = {"X-MCP-Tools": "who_am_i"}
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "no tool filter"):
            checker.check_plugin(self.root, offline=True)

    def test_bundled_skills_are_rejected(self):
        (self.root / "skills").mkdir()
        with self.assertRaisesRegex(ValueError, "must not bundle skills"):
            checker.check_plugin(self.root, offline=True)

    def test_live_discovery_only_lists_tools(self):
        result = {"result": {"tools": [{"name": "who_am_i"}]}}
        with patch.object(checker.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(result).encode())) as call:
            self.assertIn("1 tools", checker.check_plugin(self.root))
            request = call.call_args.args[0]
            self.assertEqual(json.loads(request.data)["method"], "tools/list")
            self.assertEqual(request.full_url, "https://mcp.limacharlie.io/mcp")
            self.assertIsNone(request.get_header("X-mcp-tools"))

    def test_discovery_error_is_reported(self):
        result = {"error": {"code": -32603, "message": "unavailable"}}
        with patch.object(checker.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(result).encode())):
            with self.assertRaisesRegex(ValueError, "tools/list failed"):
                checker.check_plugin(self.root)


if __name__ == "__main__":
    unittest.main()
