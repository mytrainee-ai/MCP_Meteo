
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://weather.chukai.io/mcp"


async def main():
    async with streamable_http_client(MCP_URL) as (
        read_stream,
        write_stream,
        # _, не в этой версии
    ):
        async with ClientSession(
            read_stream, write_stream
        ) as session:
            await session.initialize()

            result = await session.list_tools()

            for tool in result.tools:

                print(f"Инструмент: {tool.name}")
                print(f"Описание: {tool.description}")
                print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())
