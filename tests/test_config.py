import pytest

from src import config


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda _: None)
    for name in (
        "OPENAI_BASE_URL", "MCP_URL", "AGENT_MAX_STEPS", "AGENT_MAX_TOOL_CALLS",
        "REQUEST_TIMEOUT_SECONDS", "DEBUG",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")


def test_load_settings_uses_reliability_defaults():
    settings = config.load_settings()

    assert settings.max_steps == 6
    assert settings.max_tool_calls == 10
    assert settings.request_timeout_seconds == 30
    assert settings.debug is False
    assert "test-key" not in repr(settings)


def test_load_settings_uses_configured_limits(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_STEPS", "4")
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "3")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("DEBUG", "TRUE")

    settings = config.load_settings()

    assert settings.max_steps == 4
    assert settings.max_tool_calls == 3
    assert settings.request_timeout_seconds == 1.5
    assert settings.debug is True


@pytest.mark.parametrize(("name", "raw_value"), [
    ("AGENT_MAX_STEPS", "0"),
    ("AGENT_MAX_TOOL_CALLS", "1.5"),
    ("REQUEST_TIMEOUT_SECONDS", "-1"),
    ("REQUEST_TIMEOUT_SECONDS", "nan"),
    ("REQUEST_TIMEOUT_SECONDS", "inf"),
    ("DEBUG", "sometimes"),
])
def test_invalid_settings_name_the_variable_without_exposing_value(monkeypatch, name, raw_value):
    monkeypatch.setenv(name, raw_value)

    with pytest.raises(config.SettingsError, match=name) as caught:
        config.load_settings()

    assert "test-key" not in str(caught.value)
