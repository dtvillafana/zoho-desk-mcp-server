"""FastMCP tools for ServiceDesk Plus API v3."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from servicedesk_mcp.client import HttpMethod, Json, ServiceDeskClient
from servicedesk_mcp.notifications import notify_slack

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
DELETE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
RAW_API = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
StartIndex = Annotated[
    int,
    "One-based row offset. Advance by limit (for example: 1, 101, 201 when limit is 100)",
]


def _ref(identifier: str | None = None, name: str | None = None) -> Json | None:
    if identifier:
        return {"id": identifier}
    if name:
        return {"name": name}
    return None


def _compact(values: Json) -> Json:
    return {key: value for key, value in values.items() if value is not None}


def register_tools(mcp: FastMCP, client: ServiceDeskClient) -> None:
    """Register provider-neutral ServiceDesk tools on a FastMCP server."""

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_requests(
        status: Annotated[str | None, "Status name, such as Open or Closed"] = None,
        limit: Annotated[int, "Number of requests (1-100)"] = 50,
        start_index: StartIndex = 1,
        sort_by: Annotated[str, "ServiceDesk field used for sorting"] = "last_updated_time",
        sort_order: Literal["asc", "desc"] = "desc",
        filter_name: Annotated[str | None, "Saved request filter name"] = None,
    ) -> Json:
        """List ServiceDesk requests with pagination and optional status filtering."""
        criteria = {"field": "status.name", "condition": "is", "value": status} if status else None
        data = client.list_info(limit, start_index, sort_by, sort_order, criteria, filter_name)
        return await client.request("GET", "requests", data)

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_open_requests(limit: int = 50, start_index: StartIndex = 1) -> Json:
        """List open requests, newest activity first."""
        data = client.list_info(
            limit,
            start_index,
            "last_updated_time",
            "desc",
            {"field": "status.name", "condition": "is", "value": "Open"},
        )
        return await client.request("GET", "requests", data)

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_request(request_id: str) -> Json:
        """Get one request by its ServiceDesk request ID."""
        return await client.request("GET", f"requests/{request_id}")

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_request_full(request_id: str) -> Json:
        """Get a request plus its notes, tasks, drafts, resolution, and summary."""
        endpoints = {
            "request": f"requests/{request_id}",
            "notes": f"requests/{request_id}/notes",
            "tasks": f"requests/{request_id}/tasks",
            "drafts": f"requests/{request_id}/drafts",
            "resolution": f"requests/{request_id}/resolutions",
            "summary": f"requests/{request_id}/summary",
        }

        async def fetch(name: str, endpoint: str) -> tuple[str, Any]:
            try:
                return name, await client.request("GET", endpoint)
            except (
                Exception
            ) as exc:  # Return partial context when an optional module is unavailable.
                return name, {"error": str(exc)}

        return dict(await asyncio.gather(*(fetch(*item) for item in endpoints.items())))

    @mcp.tool(annotations=WRITE)
    async def servicedesk_create_request(
        subject: str,
        description: str | None = None,
        requester_id: str | None = None,
        requester_name: str | None = None,
        requester_email: str | None = None,
        technician_id: str | None = None,
        technician_name: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        item: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Json:
        """Create a ServiceDesk request. IDs are preferred over names when both are provided."""
        requester = _ref(requester_id, requester_name)
        if requester_email:
            requester = {**(requester or {}), "email_id": requester_email}
        request = _compact(
            {
                "subject": subject,
                "description": description,
                "requester": requester,
                "technician": _ref(technician_id, technician_name),
                "group": _ref(group_id, group_name),
                "priority": _ref(name=priority),
                "status": _ref(name=status),
                "category": _ref(name=category),
                "subcategory": _ref(name=subcategory),
                "item": _ref(name=item),
                "udf_fields": custom_fields,
            }
        )
        return await client.request("POST", "requests", {"request": request})

    @mcp.tool(annotations=WRITE)
    async def servicedesk_update_request(
        request_id: str,
        subject: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        technician_id: str | None = None,
        technician_name: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Json:
        """Update editable fields on a request."""
        request = _compact(
            {
                "subject": subject,
                "description": description,
                "status": _ref(name=status),
                "priority": _ref(name=priority),
                "technician": _ref(technician_id, technician_name),
                "group": _ref(group_id, group_name),
                "udf_fields": custom_fields,
            }
        )
        return await client.request("PUT", f"requests/{request_id}", {"request": request})

    @mcp.tool(annotations=WRITE)
    async def servicedesk_assign_request(
        request_id: str,
        technician_id: str | None = None,
        technician_name: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
    ) -> Json:
        """Assign a request to a technician and/or support group."""
        assignment = _compact(
            {
                "technician": _ref(technician_id, technician_name),
                "group": _ref(group_id, group_name),
            }
        )
        return await client.request("PUT", f"requests/{request_id}/assign", {"request": assignment})

    @mcp.tool(annotations=WRITE)
    async def servicedesk_pickup_request(request_id: str) -> Json:
        """Assign a request to the technician represented by the configured API key."""
        return await client.request("PUT", f"requests/{request_id}/pickup", {})

    @mcp.tool(annotations=WRITE)
    async def servicedesk_close_request(
        request_id: str,
        closure_comments: str | None = None,
        closure_code: str | None = None,
        requester_acknowledged: bool | None = None,
    ) -> Json:
        """Close a request with optional closure details."""
        closure = _compact(
            {
                "closure_comments": closure_comments,
                "closure_code": _ref(name=closure_code),
                "requester_ack_resolution": requester_acknowledged,
            }
        )
        return await client.request(
            "PUT", f"requests/{request_id}/close", {"request": {"closure_info": closure}}
        )

    @mcp.tool(annotations=DELETE)
    async def servicedesk_trash_request(request_id: str) -> Json:
        """Move a request to trash."""
        return await client.request("DELETE", f"requests/{request_id}/move_to_trash")

    @mcp.tool(annotations=DELETE)
    async def servicedesk_delete_request(request_id: str) -> Json:
        """Permanently delete a request that is already in trash."""
        return await client.request("DELETE", f"requests/{request_id}")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_restore_request(request_id: str) -> Json:
        """Restore a request from trash."""
        return await client.request("PUT", f"requests/{request_id}/restore_from_trash", {})

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_search_requests(
        query: str,
        limit: int = 50,
        start_index: StartIndex = 1,
    ) -> Json:
        """Search request subjects and descriptions for text."""
        criteria = [
            {"field": "subject", "condition": "contains", "value": query},
            {
                "field": "description",
                "condition": "contains",
                "value": query,
                "logical_operator": "or",
            },
        ]
        return await client.request(
            "GET", "requests", client.list_info(limit, start_index, criteria=criteria)
        )

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_request_filters() -> Json:
        """List saved request views/filters available to the API-key user."""
        return await client.request("GET", "list_view_filters/show_all", {"module": "request"})

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_request_summary(request_id: str) -> Json:
        """Get ServiceDesk's summary and metrics for a request."""
        return await client.request("GET", f"requests/{request_id}/summary")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_merge_requests(request_id: str, merge_request_ids: list[str]) -> Json:
        """Merge duplicate requests into a primary request."""
        merge_requests = [{"id": identifier} for identifier in merge_request_ids]
        return await client.request(
            "PUT", f"requests/{request_id}/merge_requests", {"requests": merge_requests}
        )

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_request_notes(
        request_id: str, limit: int = 50, start_index: StartIndex = 1
    ) -> Json:
        """List public and private notes on a request."""
        return await client.request(
            "GET",
            f"requests/{request_id}/notes",
            client.list_info(limit, start_index, "added_time"),
        )

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_request_note(request_id: str, note_id: str) -> Json:
        """Get one request note."""
        return await client.request("GET", f"requests/{request_id}/notes/{note_id}")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_add_request_note(
        request_id: str,
        description: str,
        show_to_requester: bool = False,
        mark_first_response: bool = False,
        add_to_linked_requests: bool = False,
    ) -> Json:
        """Add a private technician note or requester-visible response."""
        result = await client.request(
            "POST",
            f"requests/{request_id}/notes",
            {
                "note": {
                    "description": description,
                    "show_to_requester": show_to_requester,
                    "mark_first_response": mark_first_response,
                    "add_to_linked_requests": add_to_linked_requests,
                }
            },
        )
        request = (await client.request("GET", f"requests/{request_id}")).get("request", {})
        await notify_slack(client.config.slack_webhook_url, "note added", request, description)
        return result

    @mcp.tool(annotations=WRITE)
    async def servicedesk_update_request_note(
        request_id: str, note_id: str, description: str, show_to_requester: bool = False
    ) -> Json:
        """Update an existing request note."""
        return await client.request(
            "PUT",
            f"requests/{request_id}/notes/{note_id}",
            {"note": {"description": description, "show_to_requester": show_to_requester}},
        )

    @mcp.tool(annotations=DELETE)
    async def servicedesk_delete_request_note(request_id: str, note_id: str) -> Json:
        """Delete a request note."""
        return await client.request("DELETE", f"requests/{request_id}/notes/{note_id}")

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_resolution(request_id: str) -> Json:
        """Get a request's resolution."""
        return await client.request("GET", f"requests/{request_id}/resolutions")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_set_resolution(request_id: str, content: str) -> Json:
        """Set or replace a request's resolution content."""
        return await client.request(
            "POST", f"requests/{request_id}/resolutions", {"resolution": {"content": content}}
        )

    @mcp.tool(annotations=WRITE)
    async def servicedesk_add_request_tags(request_id: str, tags: list[str]) -> Json:
        """Add tag names to a request."""
        return await client.request(
            "POST", f"requests/{request_id}/tag", {"tags": [{"name": tag} for tag in tags]}
        )

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_request_tasks(
        request_id: str, limit: int = 50, start_index: StartIndex = 1
    ) -> Json:
        """List tasks associated with a request."""
        return await client.request(
            "GET", f"requests/{request_id}/tasks", client.list_info(limit, start_index)
        )

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_request_task(request_id: str, task_id: str) -> Json:
        """Get one task associated with a request."""
        return await client.request("GET", f"requests/{request_id}/tasks/{task_id}")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_create_request_task(
        request_id: str,
        title: str,
        description: str | None = None,
        owner_id: str | None = None,
        owner_name: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        percentage_completion: int | None = None,
    ) -> Json:
        """Create a task under a request."""
        task = _compact(
            {
                "title": title,
                "description": description,
                "owner": _ref(owner_id, owner_name),
                "group": _ref(group_id, group_name),
                "priority": _ref(name=priority),
                "status": _ref(name=status),
                "percentage_completion": percentage_completion,
            }
        )
        return await client.request("POST", f"requests/{request_id}/tasks", {"task": task})

    @mcp.tool(annotations=WRITE)
    async def servicedesk_update_request_task(
        request_id: str,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        owner_id: str | None = None,
        owner_name: str | None = None,
        status: str | None = None,
        percentage_completion: int | None = None,
    ) -> Json:
        """Update a request task."""
        task = _compact(
            {
                "title": title,
                "description": description,
                "owner": _ref(owner_id, owner_name),
                "status": _ref(name=status),
                "percentage_completion": percentage_completion,
            }
        )
        return await client.request("PUT", f"requests/{request_id}/tasks/{task_id}", {"task": task})

    @mcp.tool(annotations=DELETE)
    async def servicedesk_delete_request_task(request_id: str, task_id: str) -> Json:
        """Delete a task from a request."""
        return await client.request("DELETE", f"requests/{request_id}/tasks/{task_id}")

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_tasks(limit: int = 50, start_index: StartIndex = 1) -> Json:
        """List general ServiceDesk tasks."""
        return await client.request("GET", "tasks", client.list_info(limit, start_index))

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_task(task_id: str) -> Json:
        """Get a general task."""
        return await client.request("GET", f"tasks/{task_id}")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_create_task(
        title: str,
        description: str | None = None,
        owner_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ) -> Json:
        """Create a general ServiceDesk task."""
        task = _compact(
            {
                "title": title,
                "description": description,
                "owner": _ref(owner_id),
                "status": _ref(name=status),
                "priority": _ref(name=priority),
            }
        )
        return await client.request("POST", "tasks", {"task": task})

    @mcp.tool(annotations=WRITE)
    async def servicedesk_update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        owner_id: str | None = None,
        status: str | None = None,
        percentage_completion: int | None = None,
    ) -> Json:
        """Update a general ServiceDesk task."""
        task = _compact(
            {
                "title": title,
                "description": description,
                "owner": _ref(owner_id),
                "status": _ref(name=status),
                "percentage_completion": percentage_completion,
            }
        )
        return await client.request("PUT", f"tasks/{task_id}", {"task": task})

    @mcp.tool(annotations=DELETE)
    async def servicedesk_delete_task(task_id: str) -> Json:
        """Delete a general ServiceDesk task."""
        return await client.request("DELETE", f"tasks/{task_id}")

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_drafts(request_id: str) -> Json:
        """List email drafts saved on a request."""
        return await client.request("GET", f"requests/{request_id}/drafts", {})

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_draft(request_id: str, draft_id: str) -> Json:
        """Get one request email draft."""
        return await client.request("GET", f"requests/{request_id}/drafts/{draft_id}")

    @mcp.tool(annotations=WRITE)
    async def servicedesk_create_draft(
        request_id: str,
        subject: str,
        description: str,
        to: list[str],
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        draft_type: str = "reply",
    ) -> Json:
        """Save an email draft on a request without sending it."""
        draft = {
            "subject": subject,
            "description": description,
            "type": draft_type,
            "to": [{"email_id": address} for address in to],
            "cc": [{"email_id": address} for address in cc or []],
            "bcc": [{"email_id": address} for address in bcc or []],
        }
        return await client.request("POST", f"requests/{request_id}/drafts", {"draft": draft})

    @mcp.tool(annotations=DELETE)
    async def servicedesk_delete_draft(request_id: str, draft_id: str) -> Json:
        """Delete an email draft from a request."""
        return await client.request("DELETE", f"requests/{request_id}/drafts/{draft_id}")

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_list_users(limit: int = 50, start_index: StartIndex = 1) -> Json:
        """List ServiceDesk users and technicians visible to the API-key user."""
        return await client.request("GET", "users", client.list_info(limit, start_index))

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_get_user(user_id: str) -> Json:
        """Get a ServiceDesk user or technician by ID."""
        return await client.request("GET", f"users/{user_id}")

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_find_user_by_email(email: str, limit: int = 20) -> Json:
        """Find ServiceDesk users by email address."""
        criteria = {"field": "email_id", "condition": "is", "value": email}
        return await client.request("GET", "users", client.list_info(limit, criteria=criteria))

    @mcp.tool(annotations=READ_ONLY)
    async def servicedesk_download_request_attachment(
        request_id: str,
        attachment_id: str,
        file_name: str,
        output_directory: str | None = None,
    ) -> Json:
        """Download a request attachment to a private local file."""
        return await client.download(
            f"requests/{request_id}/attachments/{attachment_id}/download",
            file_name,
            output_directory,
        )

    @mcp.tool(annotations=WRITE)
    async def servicedesk_upload_request_attachment(request_id: str, file_path: str) -> Json:
        """Upload a local file as a request attachment."""
        return await client.upload_attachment(request_id, file_path)

    @mcp.tool(annotations=DELETE)
    async def servicedesk_delete_request_attachment(request_id: str, attachment_id: str) -> Json:
        """Delete an attachment from a request."""
        return await client.request("DELETE", f"requests/{request_id}/attachments/{attachment_id}")

    @mcp.tool(annotations=RAW_API)
    async def servicedesk_api_request(
        method: HttpMethod,
        endpoint: Annotated[str, "Path relative to /api/v3, never a full URL"],
        input_data: Annotated[dict[str, Any] | None, "ServiceDesk input_data JSON object"] = None,
    ) -> Json:
        """Call an API v3 endpoint not yet covered by a dedicated tool.

        This preserves access to installed-version-specific ServiceDesk modules while
        restricting requests to the configured on-premises server and /api/v3 path.
        """
        return await client.request(method, endpoint, input_data)
