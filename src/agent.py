"""Цикл Responses API с вызовом погодных MCP-инструментов."""

from mcp import ClientSession
from openai import AsyncOpenAI

from .mcp_client import list_weather_tools
from .tool_adapter import (
    parse_tool_arguments,
    serialize_mcp_result,
    serialize_tool_error,
    to_function_tool,
)

MAX_STEPS = 6
INSTRUCTIONS = (
    "Ты AI-агент погоды. Отвечай на русском языке. "
    "Для погодных вопросов используй MCP-инструменты. "
    "Сначала найди координаты города, затем получи погоду. "
    "Не придумывай погодные данные. Если данных нет, сообщи об этом. "
    "Если город неоднозначен, уточни населённый пункт. "
    "Учитывай часовой пояс и дату прогноза."
)


async def run_agent(
    session: ClientSession, client: AsyncOpenAI, *, model: str, question: str
) -> str:
    """Обрабатывает один вопрос в пределах открытой MCP-сессии."""

    tools = await list_weather_tools(session)
    function_tools = [to_function_tool(tool) for tool in tools.values()]
    history = [{"role": "user", "content": question}]

    for step in range(1, MAX_STEPS + 1):
        response = await client.responses.create(
            model=model,
            instructions=INSTRUCTIONS,
            input=history,
            tools=function_tools,
        )
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if not response.output_text:
                raise RuntimeError("Модель не вернула текстовый ответ.")
            return response.output_text

        if step == MAX_STEPS:
            break

        history.extend(
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in response.output
        )

        for call in calls:
            tool = tools.get(call.name)
            if tool is None:
                output = serialize_tool_error("Инструмент запрещён.")
            else:
                try:
                    arguments = parse_tool_arguments(call.arguments, tool)
                except ValueError as error:
                    output = serialize_tool_error(str(error))
                else:
                    try:
                        result = await session.call_tool(call.name, arguments=arguments)
                        output = serialize_mcp_result(result)
                    except Exception:
                        output = serialize_tool_error("Не удалось получить данные от MCP-инструмента.")

            history.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": output,
            })

    return "Агент достиг лимита шагов."
