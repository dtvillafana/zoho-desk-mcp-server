# Quick start

```bash
export SERVICEDESK_BASE_URL="https://servicedesk.example.internal:8080"
export SERVICEDESK_API_KEY="your-technician-api-key"
nix run .
```

For an MCP client, first run `nix build`, then configure its stdio server command as:

```text
/absolute/path/to/this/repository/result/bin/servicedesk-mcp-server
```

Pass the same two environment variables in the client's MCP server configuration. See `README.md` for the complete example, TLS settings, development commands, and tool coverage.
