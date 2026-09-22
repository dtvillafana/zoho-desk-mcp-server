"""Optional Slack notifications for write actions."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx


async def notify_slack(
    webhook_url: str | None,
    action: str,
    request: dict[str, Any],
    content: str,
) -> None:
    if not webhook_url:
        return
    clean = re.sub(r"<[^>]*>", "", content)[:500]
    request_id = request.get("id", "unknown")
    subject = request.get("subject", "")
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"ServiceDesk: {action}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Request #{request_id}* {subject}\n{clean}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": datetime.now(UTC).isoformat(timespec="seconds")}
                ],
            },
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json=message)
    except httpx.HTTPError:
        # Notification failures must never make the ServiceDesk operation fail.
        return
