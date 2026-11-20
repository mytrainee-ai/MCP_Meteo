import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from anyio import sleep_forever

from src import service
from src.agent import TurnResult
from src.config import Settings
from src.conversation import Conversation


@pytest.fixture
def settings():
    return Settings(
        api_key="private-test-key",
        model="test-model",
        base_url="https://provider.invalid/v1",
        mcp_url="https://weather.invalid/mcp",
        max_steps=4,
        max_tool_calls=2,
        request_timeout_seconds=0.05,
        debug=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_phase", ["initialize", "generate", "close"])
async def test_service_times_out_and_leaves_history_unchanged(monkeypatch, settings, blocked_phase):
    closed = []

    @asynccontextmanager
    async def openai_client(**kwargs):
        try:
            yield object()
        finally:
            closed.append("OpenAI")

    @asynccontextmanager
    async def mcp_session(url):
        try:
            if blocked_phase == "initialize":
                await sleep_forever()
            yield object()
            if blocked_phase == "close":
                await sleep_forever()
        finally:
            closed.append("MCP")

    async def generate_turn(*args, **kwargs):
        if blocked_phase == "generate":
            await sleep_forever()
        return TurnResult("Forecast", [{"role": "assistant", "content": "Forecast"}])

    monkeypatch.setattr(service, "AsyncOpenAI", openai_client)
    monkeypatch.setattr(service, "open_weather_session", mcp_session)
    monkeypatch.setattr(service, "generate_turn", generate_turn)
    conversation = Conversation()
    before = conversation.snapshot()

    with pytest.raises(TimeoutError):
        await service.answer_question("Weather question", settings, conversation)

    assert closed == ["MCP", "OpenAI"]
    assert conversation.snapshot() == before


@pytest.mark.asyncio
async def test_service_passes_limits_and_logs_without_request_details(monkeypatch, settings, caplog):
    settings_seen = {}

    @asynccontextmanager
    async def openai_client(**kwargs):
        settings_seen.update(kwargs)
        yield "client"

    @asynccontextmanager
    async def mcp_session(url):
        assert url == settings.mcp_url
        yield "session"

    items = [{"role": "assistant", "content": "Private weather reply"}]
    generate_turn = AsyncMock(return_value=TurnResult("Private weather reply", items))
    monkeypatch.setattr(service, "AsyncOpenAI", openai_client)
    monkeypatch.setattr(service, "open_weather_session", mcp_session)
    monkeypatch.setattr(service, "generate_turn", generate_turn)
    conversation = Conversation()

    with caplog.at_level(logging.DEBUG, logger="src"):
        answer = await service.answer_question("Private question", settings, conversation)

    assert answer == "Private weather reply"
    assert conversation.snapshot()[1] == items
    assert settings_seen["timeout"] == settings.request_timeout_seconds
    assert settings_seen["max_retries"] == 0
    generate_turn.assert_awaited_once_with(
        "session", "client", model=settings.model, question="Private question", history=[],
        max_steps=4, max_tool_calls=2,
    )
    assert "Запрос начат." in caplog.text and "Запрос завершён." in caplog.text
    assert "Private question" not in caplog.text
    assert "Private weather reply" not in caplog.text
    assert settings.api_key not in caplog.text
