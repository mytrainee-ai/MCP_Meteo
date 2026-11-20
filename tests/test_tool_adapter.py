import json

import pytest
from mcp.types import CallToolResult, TextContent, Tool

from src.tool_adapter import (
    MAX_TOOL_OUTPUT_BYTES,
    parse_tool_arguments,
    serialize_mcp_result,
    to_function_tool,
)


@pytest.fixture
def geocode():
    return Tool(
        name="geocode_location",
        description="Find a city",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )


def test_tool_schema_is_forwarded(geocode):
    assert to_function_tool(geocode) == {
        "type": "function",
        "name": "geocode_location",
        "description": "Find a city",
        "parameters": geocode.input_schema,
        "strict": False,
    }
    assert parse_tool_arguments('{"name":"Москва"}', geocode) == {"name": "Москва"}


@pytest.mark.parametrize("raw_arguments", ["{", "[]", "{}", '{"name":10}'])
def test_invalid_arguments_are_rejected(raw_arguments, geocode):
    with pytest.raises(ValueError):
        parse_tool_arguments(raw_arguments, geocode)


def test_remote_schema_reference_is_rejected_without_fetching():
    tool = Tool(
        name="geocode_location",
        input_schema={"$ref": "https://example.invalid/schema"},
    )

    with pytest.raises(ValueError, match="недоступную ссылку"):
        parse_tool_arguments("{}", tool)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e1000"])
def test_non_finite_numbers_are_not_accepted_as_arguments(number):
    tool = Tool(name="get_weather_forecast", input_schema={"type": "object"})

    with pytest.raises(ValueError, match="корректным JSON"):
        parse_tool_arguments('{"latitude":' + number + '}', tool)


def test_structured_content_takes_precedence():
    result = CallToolResult(
        structured_content={"temperature": 0},
        content=[TextContent(type="text", text='{"temperature":30}')],
    )

    assert json.loads(serialize_mcp_result(result)) == {
        "is_error": False,
        "data": {"temperature": 0},
    }


def test_json_is_read_from_a_text_block():
    result = CallToolResult(content=[
        TextContent(type="text", text="Weather report"),
        TextContent(type="text", text='{"temperature":-5}'),
    ])

    assert json.loads(serialize_mcp_result(result)) == {
        "is_error": False,
        "data": {"temperature": -5},
    }


@pytest.mark.parametrize("is_error", [False, True])
def test_error_or_non_json_result_has_no_weather_data(is_error):
    result = CallToolResult(
        is_error=is_error,
        content=[TextContent(type="text", text="Underlying service diagnostic")],
    )

    payload = json.loads(serialize_mcp_result(result))
    assert payload["is_error"] is True
    assert "data" not in payload
    assert "diagnostic" not in payload["error"]


def test_oversize_mcp_result_is_replaced_with_a_small_error():
    result = CallToolResult(
        content=[],
        structured_content={"data": "я" * (MAX_TOOL_OUTPUT_BYTES // 2)},
    )

    output = serialize_mcp_result(result)
    payload = json.loads(output)

    assert len(output.encode("utf-8")) < MAX_TOOL_OUTPUT_BYTES
    assert payload["is_error"] is True
    assert "слишком большой" in payload["error"]
    assert "data" not in payload
