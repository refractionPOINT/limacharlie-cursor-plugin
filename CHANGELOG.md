# Changelog

All notable changes to this plugin will be documented here.

## 1.0.0 — initial release

- Added two MCP connections to LimaCharlie's hosted Streamable HTTP server:
  - `limacharlie` (`https://mcp.limacharlie.io/mcp`), restricted to 185 reviewed read-only tools through the `X-MCP-Tools` header. The server enforces the list on every call. Reads that return credentials, fetch URLs or write files stay off it.
  - `limacharlie-actions` (`https://mcp.limacharlie.io/mcp/all`), with the full tool set. Skills request approval before changes and sensitive reads; account permissions and host policies enforce access limits.
- Auth is OAuth 2.1 with PKCE and dynamic client registration, signing in with Google or Microsoft. The plugin ships no client ID, secret or variables.
- Added six skills:
  - `limacharlie`: connections, org selection, the approval rule, routines, credentials and troubleshooting.
  - `limacharlie-hunt`, `limacharlie-triage`, `limacharlie-detection-engineering`, `limacharlie-endpoint-response` and `limacharlie-config-as-code`.
- Added `scripts/check_mcp_tools.py` and `scripts/reviewed_tools.json`. Together they check the read-only list against a reviewed classification of every server tool, flag new tools that have not been classified, and check every tool the skills mention against the live server.
- Declared hosted `placement: server` on both connections for Grok Bot connect/sign-in cards.
- Added explicit confirmation fallbacks for Cursor and a consistent, approved private-file exception for credential exports.
- Added 15 argument-contract examples, offline regression tests and a dedicated CI workflow; live checks verify both catalogs and report legacy response-schema compatibility.
- Documented single-response compatibility with existing MCP schemas and the publication smoke-test checklist.
- Targets Grok Bot and Cursor.
- Logo: LimaCharlie's official mark.

- Package the plugin as a standalone public repository with manifest validation and CI.
- Refresh the reviewed catalog for Cloud Security and Email Security additions while retaining the investigation allowlist and unrestricted full-access connection.
