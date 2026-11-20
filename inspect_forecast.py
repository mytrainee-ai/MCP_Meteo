# изучаем схему прогноза. Чтобы правильно вызвать get_weather_forecast, нужно узнать его входные параметры.

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

            tools = await session.list_tools()

            for tool in tools.tools:
                if tool.name == "get_weather_forecast":

                    print("Название:", tool.name)
                    print("Описание:", tool.description)

                    print("\nINPUT SCHEMA:")
                    print(json.dumps(
                        tool.input_schema,
                        indent=2,
                        ensure_ascii=False
                    ))
                    return

            print("Инструмент не найден")


if __name__ == "__main__":
    asyncio.run(main())
















