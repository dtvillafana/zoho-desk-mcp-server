import asyncio
import json

import httpx

from servicedesk_mcp.client import ServiceDeskClient
from servicedesk_mcp.config import ServiceDeskConfig
from servicedesk_mcp.server import create_server


def test_server_registers_feature_tools() -> None:
    async def run() -> None:
        client = ServiceDeskClient(
            ServiceDeskConfig("https://sdp.internal", "token"),
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        )
        server = create_server(client)
        tools = await server.list_tools()
        names = {tool.name for tool in tools}
        assert "servicedesk_list_requests" in names
        assert "servicedesk_create_request" in names
        assert "servicedesk_add_request_note" in names
        assert "servicedesk_create_request_task" in names
        assert "servicedesk_create_draft" in names
        assert "servicedesk_download_request_attachment" in names
        assert "servicedesk_api_request" in names
        assert len(names) >= 35
        await client.close()

    asyncio.run(run())


def test_list_request_filters_includes_required_module() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v3/list_view_filters/show_all"
            assert json.loads(request.url.params["input_data"]) == {"module": "request"}
            return httpx.Response(200, json={"show_all": []})

        client = ServiceDeskClient(
            ServiceDeskConfig("https://sdp.internal", "token"),
            transport=httpx.MockTransport(handler),
        )
        server = create_server(client)
        await server.call_tool("servicedesk_list_request_filters", {})
        await client.close()

    asyncio.run(run())
