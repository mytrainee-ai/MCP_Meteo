"""Преобразование схем и результатов между MCP и Responses API."""

import json
import math
from typing import Any

from jsonschema import ValidationError
from jsonschema.validators import validator_for
from mcp.types import CallToolResult, TextContent, Tool
from openai.types.responses import FunctionToolParam
from referencing import Registry
from referencing.exceptions import Unresolvable

MAX_TOOL_OUTPUT_BYTES = 32 * 1024


def to_function_tool(tool: Tool) -> FunctionToolParam:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description or "",
        "parameters": tool.input_schema,
        "strict": False,
    }


def parse_finite_float(raw_number: str) -> float:
    number = float(raw_number)
    if not math.isfinite(number):
        raise ValueError("JSON number must be finite")
    return number


def parse_tool_arguments(raw_arguments: str, tool: Tool) -> dict[str, Any]:
    try:
        arguments = json.loads(
            raw_arguments, parse_float=parse_finite_float, parse_constant=parse_finite_float,
        )
    except ValueError:
        raise ValueError("Аргументы инструмента должны быть корректным JSON.") from None

    if not isinstance(arguments, dict):
        raise ValueError("Аргументы инструмента должны быть JSON-объектом.")

    schema = tool.input_schema
    # Схема приходит с сервера. Внешние ссылки не должны инициировать HTTP-запросы.
    validator = validator_for(schema)(schema, registry=Registry())
    try:
        validator.validate(arguments)
    except ValidationError as error:
        raise ValueError(
            f"Аргументы не соответствуют JSON Schema: {error.json_path}, правило {error.validator}."
        ) from None
    except Unresolvable:
        raise ValueError("Схема инструмента содержит недоступную ссылку.") from None
    return arguments


def serialize_tool_error(message: str) -> str:
    return json.dumps({"is_error": True, "error": message}, ensure_ascii=False)


def serialize_mcp_result(result: CallToolResult) -> str:
    if result.is_error:
        return serialize_tool_error("MCP-инструмент сообщил об ошибке.")

    data = result.structured_content
    if data is None:
        parsed_blocks = []
        for block in result.content:
            if isinstance(block, TextContent):
                try:
                    parsed_blocks.append(json.loads(block.text))
                except json.JSONDecodeError:
                    continue

        if not parsed_blocks:
            return serialize_tool_error("Ответ MCP-инструмента не содержит JSON.")
        data = parsed_blocks[0] if len(parsed_blocks) == 1 else parsed_blocks

    try:
        output = json.dumps(
            {"is_error": False, "data": data},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        size = len(output.encode("utf-8"))
    except (TypeError, ValueError):
        return serialize_tool_error("Ответ MCP-инструмента не удалось преобразовать в JSON.")

    if size > MAX_TOOL_OUTPUT_BYTES:
        return serialize_tool_error("Ответ MCP-инструмента слишком большой. Запросите меньше данных.")
    return output
