"""Настройки модели и погодного MCP-сервера."""

import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .mcp_client import DEFAULT_MCP_URL

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
MAX_STEPS = 6
MAX_TOOL_CALLS = 10
REQUEST_TIMEOUT_SECONDS = 30.0


class SettingsError(ValueError):
    """Параметры приложения отсутствуют или имеют неверный формат."""


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str
    base_url: str
    mcp_url: str
    max_steps: int = MAX_STEPS
    max_tool_calls: int = MAX_TOOL_CALLS
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    debug: bool = False


def read_positive_setting(name: str, default: int | float) -> int | float:
    try:
        value = type(default)(os.getenv(name, "").strip() or default)
        if value > 0 and (isinstance(value, int) or math.isfinite(value)):
            return value
    except ValueError:
        pass

    expected = "положительное целое число" if isinstance(default, int) else "положительное число"
    raise SettingsError(f"Укажите {expected} для {name} в .env.")


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not model:
        raise SettingsError("Укажите OPENAI_API_KEY и OPENAI_MODEL в .env и перезапустите приложение.")

    debug = os.getenv("DEBUG", "false").strip().lower() or "false"
    if debug not in {"true", "false"}:
        raise SettingsError("Укажите DEBUG=true или DEBUG=false в .env.")

    return Settings(
        api_key=api_key,
        model=model,
        base_url=os.getenv("OPENAI_BASE_URL", "").strip() or DEFAULT_OPENAI_BASE_URL,
        mcp_url=os.getenv("MCP_URL", "").strip() or DEFAULT_MCP_URL,
        max_steps=int(read_positive_setting("AGENT_MAX_STEPS", MAX_STEPS)),
        max_tool_calls=int(read_positive_setting("AGENT_MAX_TOOL_CALLS", MAX_TOOL_CALLS)),
        request_timeout_seconds=float(read_positive_setting("REQUEST_TIMEOUT_SECONDS", REQUEST_TIMEOUT_SECONDS)),
        debug=debug == "true",
    )


def configure_logging(debug: bool) -> None:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger(__package__).setLevel(logging.DEBUG if debug else logging.WARNING)
