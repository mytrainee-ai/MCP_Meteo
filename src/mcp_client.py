"""Подключение к погодному MCP-серверу и получение схем инструментов."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import PaginatedRequestParams, Tool

DEFAULT_MCP_URL = "https://weather.chukai.io/mcp"
WEATHER_TOOLS = frozenset({"geocode_location", "get_weather_forecast"})


@asynccontextmanager
async def open_weather_session(url: str) -> AsyncIterator[ClientSession]:
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def list_weather_tools(session: ClientSession) -> dict[str, Tool]:
    tools: dict[str, Tool] = {}
    seen_cursors: set[str] = set()
    params = None

    while True:
        page = await session.list_tools(params=params)
        for tool in page.tools:
            if tool.name in WEATHER_TOOLS:
                tools[tool.name] = tool

        cursor = page.next_cursor
        if WEATHER_TOOLS <= tools.keys() or cursor is None:
            break
        if cursor in seen_cursors:
            raise RuntimeError("MCP-сервер повторил указатель страницы инструментов.")
        seen_cursors.add(cursor)
        params = PaginatedRequestParams(cursor=cursor)

    if missing := WEATHER_TOOLS - tools.keys():
        raise RuntimeError(f"На MCP-сервере нет инструментов: {', '.join(sorted(missing))}.")
    return tools
