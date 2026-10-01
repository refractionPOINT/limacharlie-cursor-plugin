# LimaCharlie

Grok Bot and Cursor plugin that connects agents to [LimaCharlie](https://limacharlie.io), the SecOps platform for EDR telemetry, detection and response, through LimaCharlie's hosted [Model Context Protocol](https://modelcontextprotocol.io/) server at `https://mcp.limacharlie.io/mcp`.

Hunt threats across telemetry, triage detections and cases, build and test detection rules, and investigate or contain endpoints. Both investigation and full-access connections are available after installation. The skills direct investigations through the restricted connection and ask for approval before changes or sensitive reads.

## Who can use it

- A LimaCharlie account with access to at least one organization. [Sign up](https://app.limacharlie.io) if you don't have one.
- Grok Bot or Cursor.

## Install

Once the plugin is listed in the marketplace:

1. Open **Marketplace** (Grok Bot) or the **Marketplace** (Cursor).
2. Search for **LimaCharlie**.
3. Click **Install**, then connect both LimaCharlie connections when prompted.

## Connections

The plugin adds two connections to the same MCP server, each at its own address:

| Connection | Address | Access |
| --- | --- | --- |
| `limacharlie` | `https://mcp.limacharlie.io/mcp` | **Read-only.** The plugin sends the server a fixed list of 185 read-only tools in the `X-MCP-Tools` header. The server lists only those tools and refuses a call to any other tool on this connection. |
| `limacharlie-actions` | `https://mcp.limacharlie.io/mcp/all` | **Full access**: isolation, sensor tasking, rule deployment, configuration changes and credential reads. The skills use it only after you approve the specific action. |

For enforced restrictions, use LimaCharlie account permissions and, where available, the host's MCP policy to block the actions endpoint. Grok Bot's MCP allowlist is an Enterprise control. A skill instruction alone does not remove access to the full tool set.

## Connecting

Authentication is OAuth. There is no API key or token to paste.

1. Click **Connect** on each LimaCharlie connection.
2. Sign in to LimaCharlie in the browser, with Google or Microsoft.
3. The connection completes on its own. The access token stays with the connector, and the agent never sees it.

The agent acts with **your** LimaCharlie permissions, in every organization you can access. For a narrower scope, sign in as a LimaCharlie user with fewer permissions. For investigation from historical data, grant `sensor.list`, `sensor.get`, `insight.evt.get`, `insight.det.get`, `insight.stat`, `dr.list`, `fp.ctrl`, `yara.get`, `lookup.get` and `audit.get`. Live evidence collection (process lists and similar) also needs `sensor.task`. That permission also allows killing processes and deleting files through `limacharlie-actions`, so grant it only to users who may respond. See [Permission requirements](https://docs.limacharlie.io/6-developer-guide/mcp-server/#permission-requirements).

## What agents can do

| Category | Capabilities | Connection |
| --- | --- | --- |
| Hunting | LCQL queries with validation and cost estimates, IOC sweeps, host timelines, process trees | read-only |
| Triage | Detections, rules, MITRE mapping, detection summaries, cases | read-only |
| Live evidence | Processes, connections, autoruns, services, drivers, files, registry on online hosts | read-only |
| Detection engineering | Draft, validate and unit-test D&R and false-positive rules | read-only |
| Changes | Replay rules against history, deploy/enable/disable rules, isolate/rejoin hosts, sensor tasks, YARA scans, tags, case updates | actions, after approval |
| Config as code | `limacharlie sync` pull, dry-run and push (needs the optional CLI) | CLI, push after approval |

## Approval

The skills instruct the agent to request approval before each change or sensitive read, naming the action, organization and exact targets (sensor IDs and hostnames, rule names, case numbers). In Grok Bot it uses an **Approve / Cancel** widget when available; in Cursor or another host it uses an available confirmation tool or a plain-language prompt and waits for explicit confirmation. Approvals never carry over from earlier messages, sessions or routine definitions.

This is agent guidance, not a server-enforced approval gate. The actions endpoint exposes all tools allowed by the signed-in user's LimaCharlie permissions. Configure host approval controls and account permissions to enforce the limits you need.

Routines only read and report. When a routine finds something that needs action, it asks and waits. For containment that must happen with nobody present, the skills propose a LimaCharlie D&R rule with a response action, which you approve and the platform then runs.

## Skills

| Skill | Purpose |
| --- | --- |
| `limacharlie` | Connections, org selection, the approval rule, routines, credentials, troubleshooting |
| `limacharlie-hunt` | LCQL, IOC sweeps, timelines |
| `limacharlie-triage` | Detection triage and cases |
| `limacharlie-detection-engineering` | D&R and false-positive rules: validate, test, replay, deploy |
| `limacharlie-endpoint-response` | Live investigation, isolation, sensor tasking, offline hosts |
| `limacharlie-config-as-code` | Org configuration as code with the limacharlie CLI |

## Security notes

- Telemetry, detections and case content can contain text an attacker wrote. The skills treat it as data and never as instructions or approvals.
- The skills prohibit asking for credentials in chat or reproducing them in reports, evidence or repositories. Credential reads and transfers require specific approval. A credential-bearing config export is an explicit exception: approval must name the resource types, destination and retention, and the file must be private, kept out of command output and deleted after use. Connector OAuth tokens remain outside the agent's reach. Some reads stay off the restricted connection because they can return credentials, fetch URLs or write files.
- Content stored in LimaCharlie (SOPs, notes, AI skills, playbooks) is treated as information, never as an approval or an instruction to widen scope.
- The limacharlie CLI has no enforced read-only mode. Help, version checks, credential-free `sync pull`, and `sync push --dry-run` with a credential-free file are previews; actual changes and credential-bearing exports need approval. Routines never use the CLI.
- Files and command-line logins on the Grok Bot computer are shared by every Bot on the account. The optional limacharlie CLI is installed and signed in only with your agreement.
- LCQL queries and rule replays are billed by LimaCharlie. The skills validate and estimate broad queries before running them.

## Network endpoints

| Endpoint | Used for |
| --- | --- |
| `https://mcp.limacharlie.io/mcp`, `https://mcp.limacharlie.io/mcp/all` | MCP server (read-only and actions connections) |
| `https://mcp.limacharlie.io/.well-known/*`, `/authorize`, `/token`, `/register` | OAuth 2.1 discovery, dynamic client registration and token exchange |
| `https://api.limacharlie.io`, `https://jwt.limacharlie.io` | LimaCharlie API, used by the MCP server and the optional CLI |

## Maintaining the read-only list

The two connections must keep separate addresses: Grok Bot and Cursor keep only one connection per URL. `/mcp/all` serves the same full tool set as `/mcp`.

The server rejects the whole `X-MCP-Tools` list if it names a tool the server does not have. `scripts/reviewed_tools.json` classifies every tool on the server as `read_only` or `excluded`. Before every release, run:

```bash
python3 scripts/check_mcp_tools.py
```

It checks both connections using their configured headers, compares the restricted catalog to the allowlist, flags unreviewed tools, validates hosted placement and component paths, checks skill references, and verifies required parameters and top-level argument types for 15 workflow examples in `scripts/tool_examples.json`. Examples are never executed. It calls only `tools/list`, which needs no credentials.

The deployed server currently advertises `respond` as an object on validation, unit-test and replay tools. The skill passes a single action object for one-response rules and refuses to drop responses from a multi-response rule. The checker reports this legacy compatibility mode as a warning. After the server's array-or-object schema fix is released, require full multi-response support with:

```bash
python3 scripts/check_mcp_tools.py --require-response-arrays
```

CI validates the manifest against the bundled Cursor schema and runs deterministic local checks and regression tests without depending on the hosted service:

```bash
python3 -m pip install -r scripts/requirements-dev.txt
python3 scripts/validate_manifest.py
python3 scripts/check_mcp_tools.py --offline
python3 -m unittest discover -s scripts -p 'test_*.py'
```

The **Validate LimaCharlie plugin** workflow also offers an opt-in live catalog check through `workflow_dispatch`.

## Testing before publication

Copy this plugin into `~/.cursor/plugins/local/limacharlie`, reload Cursor and confirm that all six skills and both connections appear. Enable local plugin imports if your team policy requires it. For Grok Bot, use a test team marketplace or a reviewer-provided install and verify that both connections show their connect/sign-in card.

Use a test organization for the following authenticated checks:

- Complete OAuth for each connection and check that the intended account and organization are selected.
- Run a bounded telemetry query and a matching/non-matching rule test.
- Confirm the host sends `X-MCP-Tools` on the investigation connection.
- Propose a reversible change, cancel it and verify the state stays unchanged; then approve it and verify the resulting state. Check both the Grok Bot widget and the Cursor confirmation fallback.
- After the MCP response-schema update, validate and unit-test a rule with multiple responses intact.

The catalog checks do not authenticate, execute tools or prove host UI behavior. Record the host versions and results in the submission; do not describe authenticated checks as passed solely because the checker succeeds.

## Docs

- LimaCharlie documentation: https://docs.limacharlie.io
- Connecting AI assistants: https://docs.limacharlie.io/6-developer-guide/mcp-server/
- Support: support@limacharlie.io

## License

MIT

## Source and updates

This repository is the maintained source for the LimaCharlie Cursor and Grok Bot plugin. Submit it for marketplace review at https://cursor.com/marketplace/publish. Changes are reviewed through pull requests; update the manifest version and changelog for plugin releases.

The bundled `schemas/plugin.schema.json` comes from the MIT-licensed [Cursor plugins repository](https://github.com/cursor/plugins/blob/main/schemas/plugin.schema.json).
