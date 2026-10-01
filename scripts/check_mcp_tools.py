#!/usr/bin/env python3
"""Check the connectivity package; live mode calls only tools/list."""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def check_plugin(root, *, offline=False):
    manifest = json.loads((root / ".cursor-plugin/plugin.json").read_text())
    for key in ("skills", "rules", "agents", "commands", "hooks"):
        if key in manifest or (root / key).exists():
            raise ValueError(f"connectivity-only plugin must not bundle {key}")
    for component in ("mcpServers", "logo"):
        path = Path(manifest[component])
        if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
            raise ValueError(f"invalid {component} path: {path}")
    config = json.loads((root / manifest["mcpServers"]).read_text())
    expected = {"mcpServers": {"limacharlie": {
        "type": "http", "url": "https://mcp.limacharlie.io/mcp", "placement": "server",
    }}}
    if config != expected:
        raise ValueError("expected one hosted LimaCharlie connection with no tool filter or static credentials")
    if offline:
        return "OK: connectivity-only plugin with one full-access hosted MCP connection"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    request = urllib.request.Request(config["mcpServers"]["limacharlie"]["url"], data=body,
                                    headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if "error" in result:
        raise ValueError(f"tools/list failed: {result['error']}")
    tools = result["result"]["tools"]
    if not tools or len({t["name"] for t in tools}) != len(tools):
        raise ValueError("expected a non-empty catalog with unique tool names")
    return f"OK: hosted MCP discovery exposes {len(tools)} tools; no tools executed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="check files without network access")
    args = parser.parse_args()
    try:
        print(check_plugin(PLUGIN_ROOT, offline=args.offline))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
