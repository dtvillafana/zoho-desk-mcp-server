import asyncio
import json
from urllib.parse import parse_qs

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
        assert "servicedesk_list_support_groups" in names
        assert "servicedesk_get_support_group" in names
        assert "servicedesk_list_technicians" in names
        assert "servicedesk_get_technician" in names
        assert "servicedesk_list_orgusers" in names
        assert "servicedesk_get_orguser" in names
        assert "servicedesk_update_orguser" in names
        assert "servicedesk_list_roles" in names
        assert "servicedesk_list_org_roles" in names
        assert "servicedesk_list_open_requests_for_support_group_members" in names
        assert "servicedesk_list_active_assigned_requests" in names
        assert "servicedesk_create_request" in names
        assert "servicedesk_add_request_note" in names
        assert "servicedesk_create_request_task" in names
        assert "servicedesk_create_draft" in names
        assert "servicedesk_download_request_attachment" in names
        assert "servicedesk_api_request" in names
        assert len(names) >= 35
        await client.close()

    asyncio.run(run())


def test_support_group_and_technician_list_tools_use_valid_endpoints() -> None:
    async def run() -> None:
        seen_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_paths.append(request.url.path)
            if request.url.path == "/api/v3/support_groups/1":
                return httpx.Response(200, json={"support_group": {"id": "1"}})

            input_data = json.loads(request.url.params["input_data"])
            assert input_data["list_info"]["sort_field"] == "name"
            if request.url.path == "/api/v3/support_groups":
                return httpx.Response(200, json={"support_groups": []})
            if request.url.path == "/api/v3/technicians":
                return httpx.Response(200, json={"technicians": []})
            raise AssertionError(f"Unexpected endpoint: {request.url.path}")

        client = ServiceDeskClient(
            ServiceDeskConfig("https://sdp.internal", "token"),
            transport=httpx.MockTransport(handler),
        )
        server = create_server(client)
        await server.call_tool("servicedesk_list_support_groups", {})
        await server.call_tool("servicedesk_get_support_group", {"group_id": "1"})
        await server.call_tool("servicedesk_list_technicians", {})
        assert seen_paths == [
            "/api/v3/support_groups",
            "/api/v3/support_groups/1",
            "/api/v3/technicians",
        ]
        await client.close()

    asyncio.run(run())


def test_list_open_requests_for_support_group_members_filters_assignments() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v3/support_groups":
                input_data = json.loads(request.url.params["input_data"])
                assert input_data["list_info"]["start_index"] == 1
                return httpx.Response(
                    200,
                    json={
                        "support_groups": [{"id": "1", "name": "IT"}],
                        "list_info": {"has_more_rows": False},
                    },
                )
            if request.url.path == "/api/v3/support_groups/1":
                return httpx.Response(
                    200,
                    json={
                        "support_group": {
                            "id": "1",
                            "name": "IT",
                            "technicians": [
                                {"id": "10", "name": "Ada"},
                                {"id": "20", "name": "Grace"},
                            ],
                        }
                    },
                )

            assert request.url.path == "/api/v3/requests"
            input_data = json.loads(request.url.params["input_data"])
            assert input_data["list_info"]["search_criteria"] == {
                "field": "status.name",
                "condition": "is",
                "value": "Open",
            }
            return httpx.Response(
                200,
                json={
                    "list_info": {"total_count": 3, "has_more_rows": False},
                    "requests": [
                        {"id": "1", "technician": {"id": "10", "name": "Ada"}},
                        {"id": "2", "technician": {"id": "20", "name": "Grace"}},
                        {"id": "3", "technician": {"id": "30", "name": "Linus"}},
                    ],
                },
            )

        client = ServiceDeskClient(
            ServiceDeskConfig("https://sdp.internal", "token"),
            transport=httpx.MockTransport(handler),
        )
        server = create_server(client)
        result = await server.call_tool(
            "servicedesk_list_open_requests_for_support_group_members", {"group_name": "it"}
        )
        content = result.structured_content
        assert content["list_info"] == {
            "total_count": 2,
            "open_total_count": 3,
            "inspected_open_count": 3,
            "has_more_rows": False,
        }
        assert content["counts_by_technician"] == {"Ada": 1, "Grace": 1}
        assert [request["id"] for request in content["requests"]] == ["1", "2"]
        await client.close()

    asyncio.run(run())


def test_list_active_assigned_requests_resolves_email_and_filters_closed() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            input_data = json.loads(request.url.params["input_data"])
            criteria = input_data["list_info"]["search_criteria"]
            if request.url.path == "/api/v3/users":
                assert criteria == {
                    "field": "email_id",
                    "condition": "is",
                    "value": "david@example.com",
                }
                return httpx.Response(200, json={"users": [{"id": "42", "name": "David"}]})

            assert request.url.path == "/api/v3/requests"
            assert criteria == {"field": "technician.id", "condition": "is", "value": "42"}
            return httpx.Response(
                200,
                json={
                    "list_info": {"total_count": 2, "has_more_rows": False},
                    "requests": [
                        {"id": "1", "status": {"name": "Open"}},
                        {"id": "2", "status": {"name": "Closed"}},
                    ],
                },
            )

        client = ServiceDeskClient(
            ServiceDeskConfig("https://sdp.internal", "token"),
            transport=httpx.MockTransport(handler),
        )
        server = create_server(client)
        result = await server.call_tool(
            "servicedesk_list_active_assigned_requests",
            {"technician_email": "david@example.com"},
        )
        assert result.structured_content["list_info"] == {
            "total_count": 1,
            "assigned_total_count": 2,
            "has_more_rows": False,
        }
        assert [request["id"] for request in result.structured_content["requests"]] == ["1"]
        await client.close()

    asyncio.run(run())


def test_technician_orguser_and_role_tools_use_valid_endpoints() -> None:
    async def run() -> None:
        seen: list[tuple[str, str, dict]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payload = {}
            if request.method == "GET" and request.url.params.get("input_data"):
                payload = json.loads(request.url.params["input_data"])
            elif request.method == "PUT":
                payload = json.loads(parse_qs(request.content.decode())["input_data"][0])
            seen.append((request.method, request.url.path, payload))
            return httpx.Response(200, json={"response_status": {"status": "success"}})

        client = ServiceDeskClient(
            ServiceDeskConfig("https://sdp.internal", "token"),
            transport=httpx.MockTransport(handler),
        )
        server = create_server(client)
        await server.call_tool("servicedesk_get_technician", {"technician_id": "113705"})
        await server.call_tool(
            "servicedesk_list_orgusers", {"is_org_admin": True, "limit": 100, "start_index": 1}
        )
        await server.call_tool("servicedesk_get_orguser", {"user_id": "113705"})
        await server.call_tool(
            "servicedesk_update_orguser", {"user_id": "113705", "is_org_admin": True}
        )
        await server.call_tool("servicedesk_list_roles", {})
        await server.call_tool("servicedesk_list_org_roles", {})
        assert seen == [
            ("GET", "/api/v3/technicians/113705", {}),
            (
                "GET",
                "/api/v3/orgusers",
                {
                    "list_info": {
                        "row_count": 100,
                        "start_index": 1,
                        "get_total_count": True,
                        "search_criteria": {
                            "field": "is_org_admin",
                            "condition": "is",
                            "value": "true",
                        },
                    }
                },
            ),
            ("GET", "/api/v3/orgusers/113705", {}),
            ("PUT", "/api/v3/orgusers/113705", {"orguser": {"is_org_admin": True}}),
            (
                "GET",
                "/api/v3/roles",
                {
                    "list_info": {
                        "row_count": 50,
                        "start_index": 1,
                        "get_total_count": True,
                        "sort_field": "name",
                        "sort_order": "asc",
                    }
                },
            ),
            (
                "GET",
                "/api/v3/org_roles",
                {
                    "list_info": {
                        "row_count": 50,
                        "start_index": 1,
                        "get_total_count": True,
                        "sort_field": "name",
                        "sort_order": "asc",
                    }
                },
            ),
        ]
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
