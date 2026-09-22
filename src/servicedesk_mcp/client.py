"""Async REST client for ManageEngine ServiceDesk Plus on-premises API v3."""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Literal

import httpx

from servicedesk_mcp.config import ServiceDeskConfig

Json = dict[str, Any]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE"]


class ServiceDeskError(RuntimeError):
    """A ServiceDesk API or transport error safe to return to an MCP caller."""


class ServiceDeskClient:
    def __init__(
        self, config: ServiceDeskConfig, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.config = config
        self._http = httpx.AsyncClient(
            base_url=f"{config.api_url}/",
            headers={
                "Accept": "application/vnd.manageengine.sdp.v3+json",
                "authtoken": config.api_key,
            },
            timeout=config.timeout_seconds,
            verify=config.verify_tls,
            transport=transport,
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._http.aclose()

    @staticmethod
    def list_info(
        limit: int = 50,
        start_index: int = 1,
        sort_field: str | None = None,
        sort_order: Literal["asc", "desc"] = "desc",
        criteria: Json | list[Json] | None = None,
        filter_name: str | None = None,
    ) -> Json:
        info: Json = {
            "row_count": max(1, min(limit, 100)),
            "start_index": max(1, start_index),
            "get_total_count": True,
        }
        if sort_field:
            info.update(sort_field=sort_field, sort_order=sort_order)
        if criteria:
            info["search_criteria"] = criteria
        if filter_name:
            info["filter_by"] = {"name": filter_name}
        return {"list_info": info}

    async def request(
        self,
        method: HttpMethod,
        endpoint: str,
        input_data: Json | None = None,
    ) -> Json:
        path = endpoint.strip().lstrip("/")
        if path.startswith("api/v3/"):
            path = path.removeprefix("api/v3/")
        if not path or ".." in path.split("/") or "://" in path:
            raise ServiceDeskError("Endpoint must remain within the configured /api/v3 API")
        encoded = json.dumps(input_data, separators=(",", ":")) if input_data is not None else None
        kwargs: dict[str, Any] = {}
        if encoded is not None:
            if method == "GET":
                kwargs["params"] = {"input_data": encoded}
            else:
                kwargs["data"] = {"input_data": encoded}
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ServiceDeskError(f"ServiceDesk request failed: {exc}") from exc
        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            preview = response.text[:500]
            raise ServiceDeskError(
                f"ServiceDesk returned non-JSON (HTTP {response.status_code}): {preview}"
            ) from exc
        if response.is_error:
            raise ServiceDeskError(
                f"ServiceDesk API error (HTTP {response.status_code}): {json.dumps(body)}"
            )
        status = body.get("response_status") if isinstance(body, dict) else None
        statuses = status if isinstance(status, list) else [status]
        if any(isinstance(item, dict) and item.get("status") == "failed" for item in statuses):
            raise ServiceDeskError(f"ServiceDesk API rejected the operation: {json.dumps(body)}")
        return body

    async def download(
        self,
        endpoint: str,
        file_name: str,
        output_directory: str | None = None,
    ) -> Json:
        path = endpoint.strip().lstrip("/").removeprefix("api/v3/")
        if ".." in path.split("/") or "://" in path:
            raise ServiceDeskError("Download endpoint must remain within /api/v3")
        try:
            response = await self._http.get(path)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ServiceDeskError(f"Attachment download failed: {exc}") from exc
        safe_name = re.sub(r"[^\w. -]", "_", Path(file_name).name) or "attachment"
        base = (
            Path(output_directory).expanduser()
            if output_directory
            else Path(gettempdir()) / "servicedesk"
        )
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        base = base.resolve()
        destination = (base / safe_name).resolve()
        if destination.parent != base:
            raise ServiceDeskError("Refusing to write attachment outside its output directory")
        destination.write_bytes(response.content)
        destination.chmod(0o600)
        return {
            "path": str(destination),
            "bytes": len(response.content),
            "content_type": response.headers.get("content-type")
            or mimetypes.guess_type(safe_name)[0]
            or "application/octet-stream",
        }

    async def upload_attachment(self, request_id: str, file_path: str) -> Json:
        source = Path(file_path).expanduser().resolve(strict=True)
        endpoint = f"requests/{request_id}/attachments"
        try:
            with source.open("rb") as stream:
                response = await self._http.post(
                    endpoint,
                    files={"file": (source.name, stream, mimetypes.guess_type(source.name)[0])},
                )
        except (OSError, httpx.HTTPError) as exc:
            raise ServiceDeskError(f"Attachment upload failed: {exc}") from exc
        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            raise ServiceDeskError(
                f"Attachment upload returned HTTP {response.status_code}"
            ) from exc
        if response.is_error:
            raise ServiceDeskError(f"Attachment upload failed: {json.dumps(body)}")
        return body
