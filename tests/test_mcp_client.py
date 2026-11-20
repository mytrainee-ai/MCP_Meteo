from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from mcp.types import ListToolsResult, Tool

from src import mcp_client


@pytest.mark.asyncio
async def test_open_weather_session_initializes_and_closes_on_error(monkeypatch):
    events = []
    session = AsyncMock()

    @asynccontextmanager
    async def transport(url):
        events.append(url)
        try:
            yield "read stream", "write stream"
        finally:
            events.append("close transport")

    @asynccontextmanager
    async def session_context(read_stream, write_stream):
        assert (read_stream, write_stream) == ("read stream", "write stream")
        try:
            yield session
        finally:
            events.append("close session")

    monkeypatch.setattr(mcp_client, "streamable_http_client", transport)
    monkeypatch.setattr(mcp_client, "ClientSession", session_context)

    with pytest.raises(RuntimeError, match="query failed"):
        async with mcp_client.open_weather_session("https://example.invalid/mcp") as opened:
            assert opened is session
            session.initialize.assert_awaited_once()
            raise RuntimeError("query failed")

    assert events == ["https://example.invalid/mcp", "close session", "close transport"]


@pytest.mark.asyncio
async def test_list_weather_tools_filters_names_and_reads_next_page():
    geocode = Tool(name="geocode_location", input_schema={"type": "object"})
    forecast = Tool(name="get_weather_forecast", input_schema={"type": "object"})
    extra = Tool(name="extra_tool", input_schema={"type": "object"})
    session = AsyncMock()
    session.list_tools.side_effect = [
        ListToolsResult(tools=[geocode, extra], next_cursor="page-2"),
        ListToolsResult(tools=[forecast]),
    ]

    assert await mcp_client.list_weather_tools(session) == {
        geocode.name: geocode,
        forecast.name: forecast,
    }
    first, second = session.list_tools.await_args_list
    assert first.kwargs["params"] is None
    assert second.kwargs["params"].cursor == "page-2"


@pytest.mark.asyncio
async def test_list_weather_tools_reports_missing_tool():
    session = AsyncMock()
    session.list_tools.return_value = ListToolsResult(
        tools=[Tool(name="geocode_location", input_schema={})],
    )

    with pytest.raises(RuntimeError, match="get_weather_forecast"):
        await mcp_client.list_weather_tools(session)
