import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from servicedesk_mcp.client import ServiceDeskClient, ServiceDeskError
from servicedesk_mcp.config import ServiceDeskConfig


def make_client(handler) -> ServiceDeskClient:
    return ServiceDeskClient(
        ServiceDeskConfig("https://sdp.internal", "token"),
        transport=httpx.MockTransport(handler),
    )


def test_get_encodes_input_data_and_authenticates() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v3/requests"
            assert request.headers["authtoken"] == "token"
            value = json.loads(request.url.params["input_data"])
            assert value["list_info"]["row_count"] == 10
            return httpx.Response(200, json={"requests": []})

        client = make_client(handler)
        result = await client.request("GET", "requests", client.list_info(10))
        await client.close()
        assert result == {"requests": []}

    asyncio.run(run())


def test_list_info_uses_one_based_row_offset() -> None:
    assert ServiceDeskClient.list_info(100, 201)["list_info"]["start_index"] == 201


def test_write_uses_form_encoded_input_data() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            form = parse_qs(request.content.decode())
            assert json.loads(form["input_data"][0]) == {"request": {"subject": "Test"}}
            return httpx.Response(200, json={"response_status": {"status": "success"}})

        client = make_client(handler)
        await client.request("POST", "requests", {"request": {"subject": "Test"}})
        await client.close()

    asyncio.run(run())


def test_rejects_external_endpoint() -> None:
    async def run() -> None:
        client = make_client(lambda request: httpx.Response(500))
        with pytest.raises(ServiceDeskError, match="within"):
            await client.request("GET", "https://attacker.invalid/")
        await client.close()

    asyncio.run(run())


def test_api_failure_becomes_safe_exception() -> None:
    async def run() -> None:
        client = make_client(
            lambda request: httpx.Response(403, json={"response_status": {"status": "failed"}})
        )
        with pytest.raises(ServiceDeskError, match="HTTP 403"):
            await client.request("GET", "requests")
        await client.close()

    asyncio.run(run())
