
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_URL = "https://weather.chukai.io/mcp"


async def main():
    # 1. Подключаемся к MCP-серверу
    async with streamable_http_client(MCP_URL) as (
        read_stream,
        write_stream,
    ):

        # 2. Создаём MCP-сессию
        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            # 3. Инициализируем соединение
            await session.initialize()

            # 4. Получаем список инструментов
            tools = await session.list_tools()

            # 5. Находим нужный инструмент
            geocode = next(
                (
                    tool for tool in tools.tools
                    if tool.name == "geocode_location"
                ),
                None
            )

            if geocode is None:
                print("Инструмент не найден")
                return

            # 6. Выводим схему аргументов
            print("Схема инструмента:")
            print(json.dumps(
                geocode.input_schema,
                indent=2,
                ensure_ascii=False
            ))

            # 7. Вызываем инструмент
            result = await session.call_tool(
                "geocode_location",
                arguments={"name": "Moscow"}
            )

            # 8. Проверяем ошибку инструмента
            if result.is_error:
                print("Инструмент сообщил об ошибке:")
            else:
                print("Результат вызова:")

            # 9. Выводим ответ
            for content in result.content:
                if content.type == "text":
                    print(content.text)

            if result.structured_content is not None:
                print("Структурированный ответ:")
                print(json.dumps(
                    result.structured_сontent,
                    indent=2,
                    ensure_ascii=False
                ))


if __name__ == "__main__":
    asyncio.run(main())
