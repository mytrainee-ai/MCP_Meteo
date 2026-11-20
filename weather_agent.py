
import asyncio
import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from mcp import ClientSession
from mcp.client.streamable_http import (
    streamable_http_client,
)


load_dotenv()

MCP_URL = "https://weather.chukai.io/mcp"
MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

client = AsyncOpenAI()


def convert_mcp_tools(mcp_tools):
    """Преобразует MCP-инструменты в OpenAI functions."""

    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
            "strict": False,
        }
        for tool in mcp_tools
    ]


def serialize_mcp_result(result):
    """Преобразует результат MCP в строку для LLM."""

    if result.structured_content is not None:
        data = result.structured_content
    else:
        data = [
            block.text
            for block in result.content
            if block.type == "text"
        ]

    return json.dumps(
        {
            "is_error": result.is_error,
            "data": data,
        },
        ensure_ascii=False,
    )


async def run_agent(session, question):
    """Выполняет цикл LLM -> MCP -> LLM."""

    mcp_tools = await session.list_tools()

    # Для урока разрешаем только два инструмента.
    allowed_names = {
        "geocode_location",
        "get_weather_forecast",
    }

    selected_tools = [
        tool
        for tool in mcp_tools.tools
        if tool.name in allowed_names
    ]

    if len(selected_tools) != len(allowed_names):
        raise RuntimeError(
            "Не найдены необходимые MCP-инструменты"
        )

    openai_tools = convert_mcp_tools(selected_tools)

    history = [
        {
            "role": "user",
            "content": question,
        }
    ]

    instructions = (
        "Ты AI-агент погоды. Отвечай на русском языке. "
        "Для погодных вопросов используй MCP-инструменты. "
        "Сначала найди координаты города, затем получи погоду. "
        "Не придумывай погодные данные. "
        "Если город неоднозначен, уточни страну. "
        "Учитывай часовой пояс и дату прогноза."
    )

    for step in range(6):
        print(f"\n=== ШАГ АГЕНТА {step + 1} ===")

        response = await client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=history,
            tools=openai_tools,
        )

        # Сохраняем все элементы ответа модели.
        history.extend(
            item.model_dump(exclude_none=True)
            for item in response.output
        )

        calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        # Если вызовов нет, модель завершила работу.
        if not calls:
            return response.output_text

        for call in calls:
            print(f"LLM выбрала: {call.name}")

            if call.name not in allowed_names:
                output = json.dumps({
                    "is_error": True,
                    "error": "Инструмент запрещён",
                })
            else:
                try:
                    arguments = json.loads(call.arguments)

                    if not isinstance(arguments, dict):
                        raise ValueError(
                            "Аргументы должны быть объектом"
                        )

                    print("Аргументы:", arguments)

                    result = await session.call_tool(
                        call.name,
                        arguments=arguments,
                    )

                    output = serialize_mcp_result(result)

                except Exception as error:
                    output = json.dumps({
                        "is_error": True,
                        "error": str(error),
                    }, ensure_ascii=False)

            # Возвращаем результат вызова модели.
            history.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": output,
            })

    return "Агент достиг лимита шагов."


async def main():
    question = input("Ваш вопрос о погоде: ").strip()

    if not question:
        print("Вопрос не должен быть пустым.")
        return

    async with streamable_http_client(MCP_URL) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()
            print("MCP-соединение установлено.")

            answer = await run_agent(session, question)

            print("\n=== ОТВЕТ AI-АГЕНТА ===")
            print(answer)


if __name__ == "__main__":
    asyncio.run(main())
