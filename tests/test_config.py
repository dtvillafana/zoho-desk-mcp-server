from pathlib import Path

import pytest

from servicedesk_mcp.config import load_config


def test_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICEDESK_BASE_URL", "https://sdp.internal/")
    monkeypatch.setenv("SERVICEDESK_API_KEY", "secret")
    monkeypatch.setenv("SERVICEDESK_VERIFY_TLS", "false")
    monkeypatch.setenv("SERVICEDESK_TIMEOUT_SECONDS", "12.5")

    config = load_config()

    assert config.api_url == "https://sdp.internal/api/v3"
    assert config.api_key == "secret"
    assert config.verify_tls is False
    assert config.timeout_seconds == 12.5


def test_environment_overrides_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"baseUrl":"https://file","apiKey":"file-key"}', encoding="utf-8")
    monkeypatch.setenv("SERVICEDESK_CONFIG", str(path))
    monkeypatch.setenv("SERVICEDESK_API_KEY", "env-key")

    assert load_config().api_key == "env-key"


def test_missing_credentials_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for name in ("SERVICEDESK_CONFIG", "SERVICEDESK_BASE_URL", "SERVICEDESK_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="SERVICEDESK_BASE_URL"):
        load_config()
