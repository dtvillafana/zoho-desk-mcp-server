"""FastMCP stdio server entry point."""

from __future__ import annotations

from fastmcp import FastMCP

from servicedesk_mcp import __version__
from servicedesk_mcp.client import ServiceDeskClient
from servicedesk_mcp.config import load_config
from servicedesk_mcp.tools import register_tools


def create_server(client: ServiceDeskClient | None = None) -> FastMCP:
    service_client = client or ServiceDeskClient(load_config())
    mcp = FastMCP(
        name="ServiceDesk Plus On-Premises",
        version=__version__,
        instructions=(
            "Manage an on-premises ManageEngine ServiceDesk Plus instance. "
            "Read-only tools may be used freely; confirm outward-facing, mutating, "
            "or destructive actions with the user."
        ),
        on_duplicate="error",
    )
    register_tools(mcp, service_client)
    return mcp


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
