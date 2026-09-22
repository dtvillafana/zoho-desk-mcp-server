"""Configuration for an on-premises ServiceDesk Plus server."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ServiceDeskConfig:
    base_url: str
    api_key: str
    verify_tls: bool = True
    timeout_seconds: float = 30.0
    slack_webhook_url: str | None = None

    @property
    def api_url(self) -> str:
        base = self.base_url.rstrip("/")
        return base if base.endswith("/api/v3") else f"{base}/api/v3"


_FILE_KEYS = {
    "baseUrl": "base_url",
    "base_url": "base_url",
    "apiKey": "api_key",
    "api_key": "api_key",
    "authtoken": "api_key",
    "verifyTls": "verify_tls",
    "verify_tls": "verify_tls",
    "timeoutSeconds": "timeout_seconds",
    "timeout_seconds": "timeout_seconds",
    "slackWebhookUrl": "slack_webhook_url",
    "slack_webhook_url": "slack_webhook_url",
}


def config_search_paths() -> list[Path]:
    paths: list[Path] = []
    if configured := os.environ.get("SERVICEDESK_CONFIG"):
        paths.append(Path(configured).expanduser())
    paths.append(Path.cwd() / "config.json")
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    paths.append(xdg / "servicedesk-mcp" / "config.json")
    return paths


def _load_file() -> dict[str, Any]:
    for path in config_search_paths():
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError(f"{path} must contain a JSON object")
            return {
                mapped: value
                for key, value in raw.items()
                if (mapped := _FILE_KEYS.get(key)) is not None and value not in (None, "")
            }
    return {}


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.lower() not in {"0", "false", "no", "off"}


def load_config() -> ServiceDeskConfig:
    data = _load_file()
    env_values: dict[str, Any] = {
        "base_url": os.environ.get("SERVICEDESK_BASE_URL"),
        "api_key": os.environ.get("SERVICEDESK_API_KEY") or os.environ.get("SERVICEDESK_AUTHTOKEN"),
        "verify_tls": _env_bool("SERVICEDESK_VERIFY_TLS"),
        "timeout_seconds": os.environ.get("SERVICEDESK_TIMEOUT_SECONDS"),
        "slack_webhook_url": os.environ.get("SLACK_WEBHOOK_URL"),
    }
    data.update({key: value for key, value in env_values.items() if value is not None})
    if not data.get("base_url") or not data.get("api_key"):
        raise ValueError(
            "Set SERVICEDESK_BASE_URL and SERVICEDESK_API_KEY, or provide them in config.json"
        )
    return ServiceDeskConfig(
        base_url=str(data["base_url"]),
        api_key=str(data["api_key"]),
        verify_tls=bool(data.get("verify_tls", True)),
        timeout_seconds=float(data.get("timeout_seconds", 30.0)),
        slack_webhook_url=data.get("slack_webhook_url"),
    )
