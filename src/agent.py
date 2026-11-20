"""Цикл Responses API с вызовом погодных MCP-инструментов."""

import logging
from dataclasses import dataclass

from mcp import ClientSession
from openai import AsyncOpenAI
from openai.types.responses import ResponseInputParam

from .config import MAX_STEPS, MAX_TOOL_CALLS
from .conversation import Conversation
from .mcp_client import list_weather_tools
from .tool_adapter import (
    parse_tool_arguments,
    serialize_mcp_result,
    serialize_tool_error,
    to_function_tool,
)

logger = logging.getLogger(__name__)
INSTRUCTIONS = (
    "Ты AI-агент погоды. Отвечай на русском языке. "
    "Для погодных вопросов используй MCP-инструменты. "
    "Сначала найди координаты города, затем получи погоду. "
    "Не придумывай погодные данные. Если данных нет, сообщи об этом. "
    "Для связанных вопросов («А завтра?», «А вечером?») учитывай город, "
    "который был однозначно выбран в диалоге. "
    "Если подходящий город неизвестен или неоднозначен, попроси уточнение. "
    "Учитывай уточнение пользователя при ответе на исходный вопрос о погоде. "
    "Учитывай часовой пояс и дату прогноза."
)


@dataclass(frozen=True)
class TurnResult:
    text: str
    items: ResponseInputParam | None = None


async def generate_turn(
    session: ClientSession,
    client: AsyncOpenAI,
    *,
    model: str,
    question: str,
    history: ResponseInputParam,
    max_steps: int,
    max_tool_calls: int,
) -> TurnResult:
    """Готовит обмен для записи после завершения внешних операций."""

    turn: ResponseInputParam = [{"role": "user", "content": question}]
    tool_calls = 0

    tools = await list_weather_tools(session)
    function_tools = [to_function_tool(tool) for tool in tools.values()]

    for step in range(1, max_steps + 1):
        logger.debug("Шаг Responses API %d из %d.", step, max_steps)
        response = await client.responses.create(
            model=model,
            instructions=INSTRUCTIONS,
            input=[*history, *turn],
            tools=function_tools,
            store=False,
            include=["reasoning.encrypted_content"],
        )
        if response.status not in (None, "completed"):
            raise RuntimeError("Модель не завершила ответ.")

        calls = [item for item in response.output if item.type == "function_call"]
        if calls and step == max_steps:
            break

        turn.extend(
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in response.output
        )

        if not calls:
            answer = response.output_text
            if not answer.strip():
                raise RuntimeError("Модель не вернула текстовый ответ.")
            return TurnResult(answer, turn)

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
                    if tool_calls >= max_tool_calls:
                        logger.debug("Достигнут лимит MCP-вызовов (%d).", max_tool_calls)
                        return TurnResult("Агент достиг лимита вызовов MCP.")
                    tool_calls += 1
                    logger.debug("MCP-вызов %d из %d: %s.", tool_calls, max_tool_calls, tool.name)
                    try:
                        result = await session.call_tool(call.name, arguments=arguments)
                        output = serialize_mcp_result(result)
                    except Exception as error:
                        logger.debug("Ошибка MCP-вызова: %s.", type(error).__name__)
                        output = serialize_tool_error("Не удалось получить данные от MCP-инструмента.")

            turn.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": output,
            })

    logger.debug("Достигнут лимит шагов Responses API (%d).", max_steps)
    return TurnResult("Агент достиг лимита шагов.")


async def run_agent(
    session: ClientSession,
    client: AsyncOpenAI,
    *,
    model: str,
    question: str,
    conversation: Conversation | None = None,
    max_steps: int = MAX_STEPS,
    max_tool_calls: int = MAX_TOOL_CALLS,
) -> str:
    """Обрабатывает вопрос, используя предоставленные клиентские сессии."""

    if conversation is None:
        conversation = Conversation()
    revision, history = conversation.snapshot()
    result = await generate_turn(
        session, client, model=model, question=question, history=history,
        max_steps=max_steps, max_tool_calls=max_tool_calls,
    )
    if result.items is not None:
        conversation.commit_turn(revision, result.items)
    return result.text
