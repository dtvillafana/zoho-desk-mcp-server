# ServiceDesk Plus MCP Server

A Python [FastMCP](https://gofastmcp.com/) server for an **on-premises ManageEngine ServiceDesk Plus** instance. It uses the ServiceDesk Plus REST API v3 and a technician API key. It does not call an LLM API and works with any MCP-compatible client.

API behavior follows the [ServiceDesk Plus on-premises API v3 documentation](https://www.manageengine.com/products/service-desk/sdpop-v3-api/).

## Features

- Requests: list, search, create, read, update, assign, pick up, close, trash, restore, permanently delete, merge, tag, summarize
- Request context: notes, resolutions, tasks, drafts, and attachments
- General tasks and ServiceDesk users/technicians
- Optional Slack notifications when notes are added through MCP
- Restricted generic API v3 tool for modules supported by your installed ServiceDesk version
- Structured MCP output, typed arguments, and MCP safety annotations
- Reproducible Nix flake package and development shell

The generic `servicedesk_api_request` tool is intentionally restricted to the configured host's `/api/v3` path. This gives access to version- or edition-specific modules without allowing arbitrary outbound URLs.

## Requirements

- Nix with flakes enabled
- ServiceDesk Plus on-premises with REST API v3
- A technician API key with the permissions needed for your intended operations
- Network access from the MCP host to the ServiceDesk server

Generate a key from **Admin → Technicians/Users**, edit the account, and generate an API key. ServiceDesk applies the permissions of the account that owns the key; use an SDAdmin/full-permission technician only if the MCP server truly needs that level of access.

## Configuration

Environment variables take precedence over `config.json`.

| Variable | Required | Description |
|---|---:|---|
| `SERVICEDESK_BASE_URL` | yes | Instance origin, e.g. `https://servicedesk.internal:8080` |
| `SERVICEDESK_API_KEY` | yes | Technician API key/authtoken |
| `SERVICEDESK_VERIFY_TLS` | no | Set `false` only for a trusted self-signed on-prem certificate |
| `SERVICEDESK_TIMEOUT_SECONDS` | no | HTTP timeout; default `30` |
| `SERVICEDESK_CONFIG` | no | Explicit JSON config path |
| `SLACK_WEBHOOK_URL` | no | Webhook for MCP note notifications |

The base URL can include `/api/v3`; the server adds it when omitted.

Alternatively, copy the example:

```bash
cp config.example.json config.json
```

The server checks, in order:

1. `SERVICEDESK_CONFIG`
2. `./config.json`
3. `$XDG_CONFIG_HOME/servicedesk-mcp/config.json`

`config.json` is ignored by Git.

## Run with Nix

```bash
export SERVICEDESK_BASE_URL="https://servicedesk.example.internal:8080"
export SERVICEDESK_API_KEY="..."
nix run .
```

Build and check:

```bash
nix build
nix flake check
```

Enter the development environment:

```bash
nix develop
ruff check .
ruff format --check .
pytest
```

## MCP client configuration

Build once with `nix build`, then point any MCP client at the resulting executable:

```json
{
  "mcpServers": {
    "servicedesk": {
      "command": "/absolute/path/to/zoho-desk-mcp-server/result/bin/servicedesk-mcp-server",
      "args": [],
      "env": {
        "SERVICEDESK_BASE_URL": "https://servicedesk.example.internal:8080",
        "SERVICEDESK_API_KEY": "your-technician-api-key"
      }
    }
  }
}
```

This standard stdio MCP configuration is not tied to Claude, OpenAI, Gemini, or any other model provider.

## Security

- Keep API keys out of source control and client configs that are synced or shared.
- Prefer a dedicated ServiceDesk technician and grant only the permissions required.
- Keep TLS verification enabled. If the instance uses an internal CA, install that CA in the MCP host's trust store instead of disabling verification.
- Treat attachment downloads as sensitive customer data. Downloaded files use private directory/file permissions.
- The API key has the authority of its ServiceDesk user. MCP annotations advise clients about destructive tools but are not an authorization boundary.

## Development layout

```text
flake.nix                         Nix package and development shell
pyproject.toml                    Python package metadata and tooling
src/servicedesk_mcp/client.py     ServiceDesk API v3 client
src/servicedesk_mcp/config.py     Environment/JSON configuration
src/servicedesk_mcp/server.py     FastMCP server entry point
src/servicedesk_mcp/tools.py      MCP tools
tests/                            Unit tests with mocked HTTP
```

## License

GPL-2.0-or-later.
