"""Offline regression checks for discovery, restriction and argument drift."""

import copy
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
        shutil.copytree(checker.PLUGIN_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))
        reviewed = json.loads((self.root / "scripts/reviewed_tools.json").read_text())
        self.restricted_names = set(reviewed["read_only"])
        self.catalog = {name: {"inputSchema": {"properties": {}}}
                        for group in (reviewed["read_only"], reviewed["excluded"]) for name in group}
        examples = json.loads((self.root / "scripts/tool_examples.json").read_text())
        for name, arguments in examples.items():
            properties = {}
            for parameter, value in arguments.items():
                kind = ("boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float))
                        else "object" if isinstance(value, dict) else "array" if isinstance(value, list)
                        else "string")
                properties[parameter] = {"type": kind}
            self.catalog[name]["inputSchema"] = {"properties": properties, "required": list(arguments)}
        for name in checker.RESPONSE_TOOLS:
            self.catalog[name]["inputSchema"]["properties"]["respond"] = {
                "oneOf": [{"type": "array", "items": {"type": "object"}}, {"type": "object"}],
            }

    def edit_json(self, path, change):
        target = self.root / path
        data = json.loads(target.read_text())
        change(data)
        target.write_text(json.dumps(data))

    def fetch(self, connection):
        if "X-MCP-Tools" in connection.get("headers", {}):
            return {name: self.catalog[name] for name in self.restricted_names}
        return self.catalog

    def test_local_files_and_new_server_contract(self):
        self.assertEqual(checker.check_plugin(self.root, offline=True)[0], [])
        errors, warnings, _ = checker.check_plugin(self.root, fetch=self.fetch, require_response_arrays=True)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_hosted_placement(self):
        self.edit_json("mcp.json", lambda data: data["mcpServers"]["limacharlie"].pop("placement"))
        errors, _, _ = checker.check_plugin(self.root, offline=True)
        self.assertTrue(any("placement=server" in error for error in errors))

    def test_shared_urls_and_restricted_actions(self):
        def change(data):
            connections = data["mcpServers"]
            connections["limacharlie-actions"] = copy.deepcopy(connections["limacharlie"])
        self.edit_json("mcp.json", change)
        errors, _, _ = checker.check_plugin(self.root, offline=True)
        self.assertTrue(any("share a URL" in error for error in errors))
        self.assertTrue(any("retain the full tool set" in error for error in errors))

    def test_new_and_missing_server_tools_are_reported(self):
        self.catalog["unreviewed_action"] = {"inputSchema": {"properties": {}}}
        del self.catalog["replay_dr_rule"]
        errors, _, _ = checker.check_plugin(self.root, fetch=self.fetch)
        self.assertTrue(any("new server tools to classify" in error for error in errors))
        self.assertTrue(any("reviewed tools missing from the full-access catalog" in error for error in errors))

    def test_header_ignored_by_server(self):
        errors, _, _ = checker.check_plugin(self.root, fetch=lambda _: self.catalog)
        self.assertTrue(any("catalog does not match X-MCP-Tools" in error for error in errors))

    def test_parameters_are_checked_per_tool(self):
        def change(data):
            # This name is valid on replay, but not on historical event reads.
            data["get_historic_events"]["start_time"] = data["get_historic_events"].pop("start")
        self.edit_json("scripts/tool_examples.json", change)
        errors, _, _ = checker.check_plugin(self.root, fetch=self.fetch)
        self.assertTrue(any("get_historic_events example parameters" in error for error in errors))

    def test_wrong_argument_type_is_rejected(self):
        self.edit_json("scripts/tool_examples.json",
                       lambda data: data["run_lcql_query"].update(limit=True))
        errors, _, _ = checker.check_plugin(self.root, fetch=self.fetch)
        self.assertIn("run_lcql_query.limit: example type conflicts with the server schema", errors)

    def test_legacy_response_schema_is_explicit(self):
        for name in checker.RESPONSE_TOOLS:
            self.catalog[name]["inputSchema"]["properties"]["respond"] = {"type": "object"}
        errors, warnings, _ = checker.check_plugin(self.root, fetch=self.fetch)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 3)
        errors, warnings, _ = checker.check_plugin(self.root, fetch=self.fetch, require_response_arrays=True)
        self.assertEqual(len(errors), 3)
        self.assertEqual(warnings, [])

    def test_live_catalog_request_preserves_headers(self):
        connection = {"url": "https://example.invalid/mcp", "headers": {"X-MCP-Tools": "who_am_i"}}
        body = json.dumps({"result": {"tools": [{"name": "who_am_i", "inputSchema": {}}]}}).encode()
        with patch.object(checker.urllib.request, "urlopen", return_value=io.BytesIO(body)) as request:
            self.assertEqual(set(checker.live_tools(connection)), {"who_am_i"})
            sent = request.call_args.args[0]
            self.assertEqual(sent.get_header("X-mcp-tools"), "who_am_i")
            self.assertEqual(json.loads(sent.data)["method"], "tools/list")


if __name__ == "__main__":
    unittest.main()
