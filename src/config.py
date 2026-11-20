"""Настройки модели и погодного MCP-сервера."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .mcp_client import DEFAULT_MCP_URL

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class SettingsError(ValueError):
    """Параметры для обращения к провайдеру не заданы."""


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str
    base_url: str
    mcp_url: str


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not model:
        raise SettingsError("Укажите OPENAI_API_KEY и OPENAI_MODEL в .env и перезапустите приложение.")

    return Settings(
        api_key=api_key,
        model=model,
        base_url=os.getenv("OPENAI_BASE_URL", "").strip() or DEFAULT_OPENAI_BASE_URL,
        mcp_url=os.getenv("MCP_URL", "").strip() or DEFAULT_MCP_URL,
    )
