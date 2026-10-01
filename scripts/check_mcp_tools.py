#!/usr/bin/env python3
"""Validate plugin discovery, reviewed tools and example argument contracts.

Default: check both live catalogs using their configured headers. Only tools/list
is called; example arguments are never executed. --offline checks local files
without depending on server availability. --require-response-arrays also fails
if a server has not yet published the response-array schema update.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
READ_ONLY_SERVER = "limacharlie"
ACTIONS_SERVER = "limacharlie-actions"
RESPONSE_TOOLS = {"validate_dr_rule_components", "test_dr_rule_events", "replay_dr_rule"}

# Name patterns that must never be on the read-only connection.
FORBIDDEN_PATTERNS = [
    r"^(set|delete|create|add|remove|update|merge|import|rename|reset|dismiss|"
    r"enable|disable|subscribe|unsubscribe|start|terminate|rekey|upgrade|mass)_",
    r"^(isolate|rejoin)_network$", r"^(seal|unseal)_sensor$", r"^task_sensor$",
    r"^reliable_tasking$", r"^memory_dump_sensor$", r"^extension_request$",
    r"^lc_call_tool$", r"^replay_dr_rule$", r"^collect_velociraptor_artifact$",
    r"^vulnerability_(scan|set_|bulk_|reset_)",
    r"^cloudsec_(set_|bulk_|dismiss_|restore_|ingest_|test_|code_scan|code_autofix|code_provenance_push|create_remediation|decide_remediation)",
    # Reads that return credentials or configs that can embed them.
    r"^get_secret$", r"installation_key", r"^list_outputs$", r"^get_org_value$",
    r"^(get|list)_(cloud_sensors?|external_adapters?|extension_configs?)$",
    r"^get_extension_config$", r"^(get_rule|list_rules)$",
    # URL fetches, file writes, stored ARLs and other agents' histories.
    r"^resolve_arl$", r"^get_payload$", r"^yara_scan_", r"^(get|list)_yara_(sources?|rules?)$",
    r"^(get|list)_ai_(chat|session)", r"^request_feedback_",
]


# snake_case words the skills use that are values, not tools or parameters.
NON_TOOL_WORDS = {
    "artifact_event", "file_hash", "file_name", "file_path", "package_name", "service_name",
}


def live_tools(server: dict) -> dict[str, dict]:
    """Fetch a connection's catalog with exactly its configured headers."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    request = urllib.request.Request(server["url"], data=body, headers={
        "content-type": "application/json", **server.get("headers", {}),
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if "error" in result:
        raise ValueError(f"{server['url']}: tools/list failed: {result['error']}")
    tools = result["result"]["tools"]
    names = [tool["name"] for tool in tools]
    if len(names) != len(set(names)):
        raise ValueError(f"{server['url']}: duplicate tool names")
    return {tool["name"]: tool for tool in tools}


def matches_type(value: object, schema: dict) -> bool:
    """Check example parameter types (including response unions and array items).

    This is deliberately a type contract check, not a full JSON Schema validator.
    """
    for union in ("oneOf", "anyOf"):
        if union in schema:
            count = sum(matches_type(value, branch) for branch in schema[union])
            if (union == "oneOf" and count != 1) or (union == "anyOf" and count == 0):
                return False
    kinds = schema.get("type", [])
    if isinstance(kinds, str):
        kinds = [kinds]
    types = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "boolean": isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
    }
    if kinds and not any(types.get(kind, False) for kind in kinds):
        return False
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return all(matches_type(item, schema["items"]) for item in value)
    return True


def example_errors(examples: dict, catalog: dict) -> list[str]:
    errors = []
    for name, arguments in examples.items():
        if name not in catalog:
            errors.append(f"example tool missing on the server: {name}")
            continue
        schema = catalog[name]["inputSchema"]
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - arguments.keys()
        unknown = arguments.keys() - properties.keys()
        if missing or unknown:
            errors.append(f"{name} example parameters: missing={sorted(missing)}, unknown={sorted(unknown)}")
        for parameter in arguments.keys() & properties.keys():
            if not matches_type(arguments[parameter], properties[parameter]):
                errors.append(f"{name}.{parameter}: example type conflicts with the server schema")
    return errors


def check_plugin(root: Path, *, offline: bool = False, require_response_arrays: bool = False,
                 fetch=live_tools) -> tuple[list[str], list[str], str]:
    config = json.loads((root / "mcp.json").read_text())["mcpServers"]
    server = config[READ_ONLY_SERVER]
    allowlist = [t.strip() for t in server["headers"]["X-MCP-Tools"].split(",") if t.strip()]
    errors = []
    warnings = []
    if set(config) != {READ_ONLY_SERVER, ACTIONS_SERVER}:
        errors.append("expected the investigation and full-access connections")
    for name, connection in config.items():
        if connection.get("placement") != "server" or connection.get("type") != "http":
            errors.append(f"{name}: hosted HTTP connections require placement=server")
        if not connection["url"].startswith("https://"):
            errors.append(f"{name}: hosted connection must use HTTPS")
    if "X-MCP-Tools" in config[ACTIONS_SERVER].get("headers", {}):
        errors.append("actions connection must retain the full tool set")

    urls = [c["url"] for c in config.values()]
    if len(urls) != len(set(urls)):
        errors.append(f"connections share a URL, so clients will drop one of them: {urls}")

    reviewed = json.loads((root / "scripts" / "reviewed_tools.json").read_text())
    reviewed_read_only = set(reviewed["read_only"])
    reviewed_excluded = set(reviewed["excluded"])
    available = reviewed_read_only | reviewed_excluded
    if reviewed_read_only & reviewed_excluded:
        errors.append("reviewed read_only and excluded classifications overlap")
    for group in ("read_only", "excluded"):
        if len(reviewed[group]) != len(set(reviewed[group])):
            errors.append(f"duplicate names in reviewed {group}")
    if set(allowlist) != reviewed_read_only:
        errors.append(
            "X-MCP-Tools does not match reviewed read_only: "
            f"extra={sorted(set(allowlist) - reviewed_read_only)} "
            f"missing={sorted(reviewed_read_only - set(allowlist))}"
        )
    examples = json.loads((root / "scripts" / "tool_examples.json").read_text())
    if not offline:
        actions = fetch(config[ACTIONS_SERVER])
        restricted = fetch(server)
        available = set(actions)
        unreviewed = sorted(available - reviewed_read_only - reviewed_excluded)
        if unreviewed:
            errors.append(f"new server tools to classify in reviewed_tools.json: {unreviewed}")
        missing_reviewed = sorted((reviewed_read_only | reviewed_excluded) - available)
        if missing_reviewed:
            errors.append(f"reviewed tools missing from the full-access catalog: {missing_reviewed}")
        if set(restricted) != set(allowlist):
            errors.append("investigation catalog does not match X-MCP-Tools: "
                          f"extra={sorted(set(restricted) - set(allowlist))}, "
                          f"missing={sorted(set(allowlist) - set(restricted))}")
        errors.extend(example_errors(examples, actions))
        for name in sorted(RESPONSE_TOOLS):
            if name not in actions:
                errors.append(f"response tool missing: {name}")
                continue
            response_schema = actions[name]["inputSchema"]["properties"]["respond"]
            if not matches_type([{"action": "report", "name": "test"}], response_schema):
                message = f"{name}: legacy object-only respond schema; single-action compatibility only"
                (errors if require_response_arrays else warnings).append(message)

    unknown = sorted(set(allowlist) - available)
    if unknown:
        errors.append(f"allowlisted tools missing on the server: {unknown}")
    if len(allowlist) != len(set(allowlist)):
        errors.append("allowlist has duplicate names")
    forbidden = sorted(t for t in allowlist if any(re.search(p, t) for p in FORBIDDEN_PATTERNS))
    if forbidden:
        errors.append(f"allowlist contains state-changing or credential tools: {forbidden}")

    cited = set()
    for skill in (root / "skills").glob("*/SKILL.md"):
        content = skill.read_text()
        frontmatter = content.split("---", 2)
        if not content.startswith("---\n") or len(frontmatter) != 3:
            errors.append(f"{skill.parent.name}: missing YAML frontmatter")
        elif not all(re.search(rf"^{field}: .+", frontmatter[1], re.M) for field in ("name", "description")):
            errors.append(f"{skill.parent.name}: missing name or description")
        for name in re.findall(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`", skill.read_text()):
            cited.add((name, skill.parent.name))
    parameters = {parameter for arguments in examples.values() for parameter in arguments}
    known = available | parameters | NON_TOOL_WORDS
    missing = sorted({f"{name} ({skill})" for name, skill in cited if name not in known})
    if missing:
        errors.append(f"skills mention tools or parameters that are not on the server: {missing}")

    manifest = json.loads((root / ".cursor-plugin" / "plugin.json").read_text())
    for component in ("skills", "mcpServers", "logo"):
        path = Path(manifest[component])
        if path.is_absolute() or ".." in path.parts or not (root / path).exists():
            errors.append(f"invalid {component} path: {path}")
    cited_tools = {n for n, _ in cited if n in available}
    mode = "offline reviewed catalog" if offline else "live server catalogs"
    summary = (f"{len(allowlist)} investigation tools, {len(cited_tools)} cited tools, "
               f"{len(available)} full-access tools, {len(examples)} argument examples ({mode})")
    return errors, warnings, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="check local files without network access")
    parser.add_argument("--require-response-arrays", action="store_true",
                        help="require the server's multi-response schema fix")
    args = parser.parse_args()
    if args.offline and args.require_response_arrays:
        parser.error("response-array capability requires a live catalog")
    try:
        errors, warnings, summary = check_plugin(PLUGIN_ROOT, offline=args.offline,
                                               require_response_arrays=args.require_response_arrays)
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: plugin check failed: {error}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
