# LimaCharlie Cursor plugin

Connect Cursor and Grok Bot to [LimaCharlie](https://limacharlie.io) through its hosted MCP server.

This plugin provides connectivity only. LimaCharlie skills, workflows and agent instructions are maintained in [lc-ai](https://github.com/refractionPOINT/lc-ai).

## Connection

The plugin configures one hosted HTTP connection, `limacharlie`, at `https://mcp.limacharlie.io/mcp`. It uses OAuth and exposes the full tool set allowed by the signed-in user's LimaCharlie permissions. There is no plugin tool filter or bundled approval policy.

## Install and authorize

Once listed in the marketplace:

1. Open Marketplace in Grok Bot or Cursor and install **LimaCharlie**.
2. Authorize the LimaCharlie connection and complete sign-in in your browser.

You need a LimaCharlie account with access to an organization. No API key or token needs to be pasted into the plugin. Configure access through LimaCharlie permissions and your host's approval controls.

For local development in Cursor, copy this repository into `~/.cursor/plugins/local/limacharlie`, restart Cursor and confirm the connection appears. This directory is Cursor's local plugin mechanism; it is not a documented local install mechanism for Grok Bot.

## Validation

```bash
python3 -m pip install -r scripts/requirements-dev.txt
python3 scripts/validate_manifest.py
python3 scripts/check_mcp_tools.py --offline
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Check hosted tool discovery without authenticating or executing any tools:

```bash
python3 scripts/check_mcp_tools.py
```

CI runs manifest and connection checks. Its optional live check calls only `tools/list`; authenticated OAuth and host UI behavior require a separate smoke test.

## Maintenance and publication

This repository is the maintained source. Submit its URL at https://cursor.com/marketplace/publish. Update the manifest version and changelog for releases.

The bundled manifest schema comes from the [Cursor plugins repository](https://github.com/cursor/plugins/blob/main/schemas/plugin.schema.json); its license is in `schemas/LICENSE`.

## Documentation and support

- [LimaCharlie MCP documentation](https://docs.limacharlie.io/6-developer-guide/mcp-server/)
- [LimaCharlie skills and instructions](https://github.com/refractionPOINT/lc-ai)
- support@limacharlie.io

## License

MIT
