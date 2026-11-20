# исследуем ответ сервера

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_URL = "https://weather.chukai.io/mcp"


async def main():
    async with streamable_http_client(MCP_URL) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            result = await session.call_tool(
                "geocode_location",
                arguments={"name": "Moscow"}
            )

            if result.is_error:
                print("Ошибка MCP-инструмента")
                for block in result.content:
                    if block.type == "text":
                        print(block.text)
                return

            print("=== STRUCTURED CONTENT ===")
            print(json.dumps(
                result.structured_content,
                indent=2,
                ensure_ascii=False
            ))

            print("\n=== CONTENT ===")
            for block in result.content:
                if block.type == "text":
                    print(block.text)


if __name__ == "__main__":
    asyncio.run(main())












