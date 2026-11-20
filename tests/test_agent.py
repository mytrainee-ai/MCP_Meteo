import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from mcp.types import CallToolResult, ListToolsResult, Tool
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
)

from src.agent import MAX_STEPS, run_agent
from src.conversation import Conversation


@pytest.fixture
def session():
    session = AsyncMock()
    session.list_tools.return_value = ListToolsResult(tools=[
        Tool(name="geocode_location", input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }),
        Tool(name="get_weather_forecast", input_schema={"type": "object"}),
    ])
    session.call_tool.return_value = CallToolResult(
        content=[],
        structured_content={"temperature": 3},
    )
    return session


def tool_call(name, call_id, arguments):
    return ResponseFunctionToolCall(
        type="function_call", name=name, call_id=call_id, arguments=arguments
    )


def final_response(text):
    message = ResponseOutputMessage(
        id="msg_test",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
    )
    return SimpleNamespace(output=[message], output_text=text)


def model_with_responses(*responses):
    history_snapshots = []
    pending = iter(responses)

    async def create(**request):
        history_snapshots.append(deepcopy(request["input"]))
        response = next(pending)
        if not hasattr(response, "status"):
            response.status = "completed"
        return response

    client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(side_effect=create)))
    return client, history_snapshots


@pytest.mark.asyncio
async def test_agent_forwards_multiple_results_with_matching_call_ids(session):
    calls = [
        tool_call("geocode_location", "call_city", '{"name":"Москва"}'),
        tool_call("get_weather_forecast", "call_weather", '{"latitude":55.75}'),
    ]
    client, history = model_with_responses(
        SimpleNamespace(output=calls),
        SimpleNamespace(output=[], output_text="В Москве 3 °C."),
    )

    answer = await run_agent(session, client, model="test-model", question="Погода в Москве?")

    assert answer == "В Москве 3 °C."
    assert history[0] == [{"role": "user", "content": "Погода в Москве?"}]
    assert [item["call_id"] for item in history[1][1:3]] == ["call_city", "call_weather"]
    assert [item["call_id"] for item in history[1][3:]] == ["call_city", "call_weather"]
    assert all(item["type"] == "function_call_output" for item in history[1][3:])
    assert json.loads(history[1][4]["output"])["data"] == {"temperature": 3}
    assert session.call_tool.await_args_list == [
        call("geocode_location", arguments={"name": "Москва"}),
        call("get_weather_forecast", arguments={"latitude": 55.75}),
    ]
    first_request = client.responses.create.await_args_list[0].kwargs
    assert first_request["model"] == "test-model"
    assert first_request["store"] is False
    assert first_request["include"] == ["reasoning.encrypted_content"]
    assert {tool["name"] for tool in first_request["tools"]} == {
        "geocode_location", "get_weather_forecast",
    }


@pytest.mark.asyncio
async def test_agent_blocks_invalid_and_unknown_calls(session):
    client, history = model_with_responses(
        SimpleNamespace(output=[
            tool_call("geocode_location", "invalid", '{"name":77}'),
            tool_call("unknown_tool", "unknown", "{}"),
        ]),
        SimpleNamespace(output=[], output_text="Уточните город."),
    )

    assert await run_agent(session, client, model="test-model", question="Погода?") == "Уточните город."
    session.call_tool.assert_not_awaited()
    assert [item["call_id"] for item in history[1][3:]] == ["invalid", "unknown"]
    assert all(json.loads(item["output"])["is_error"] for item in history[1][3:])


@pytest.mark.asyncio
async def test_agent_reports_mcp_failure_to_model_without_service_details(session):
    session.call_tool.side_effect = RuntimeError("Underlying service diagnostic")
    client, history = model_with_responses(
        SimpleNamespace(output=[tool_call("get_weather_forecast", "forecast", "{}")]),
        SimpleNamespace(output=[], output_text="Данные о погоде недоступны."),
    )

    answer = await run_agent(session, client, model="test-model", question="Погода?")

    assert answer == "Данные о погоде недоступны."
    result = history[1][-1]
    assert result["call_id"] == "forecast"
    payload = json.loads(result["output"])
    assert payload["is_error"] is True
    assert "diagnostic" not in payload["error"]


@pytest.mark.asyncio
async def test_agent_caps_model_steps_without_unused_final_tool_call(session):
    response = SimpleNamespace(output=[
        tool_call("geocode_location", "call_city", '{"name":"Москва"}'),
    ])
    client, _ = model_with_responses(*([response] * MAX_STEPS))
    conversation = Conversation()

    answer = await run_agent(
        session, client, model="test-model", question="Погода?", conversation=conversation,
    )

    assert answer == "Агент достиг лимита шагов."
    assert client.responses.create.await_count == MAX_STEPS
    assert session.call_tool.await_count == MAX_STEPS - 1
    assert conversation.snapshot()[1] == []


@pytest.mark.asyncio
async def test_follow_up_receives_previous_city_and_tool_history_until_clear(session):
    reasoning = ResponseReasoningItem(
        id="rs_test", type="reasoning", summary=[], encrypted_content="encrypted-test-data",
    )
    client, requests = model_with_responses(
        SimpleNamespace(output=[
            reasoning,
            tool_call("geocode_location", "find_city", '{"name":"Москва"}'),
        ]),
        final_response("Сейчас в Москве 3 °C."),
        final_response("Завтра в Москве 5 °C."),
        final_response("Для какого города нужен прогноз?"),
    )
    conversation = Conversation()

    await run_agent(
        session, client, model="test-model", question="Погода в Москве?", conversation=conversation,
    )
    follow_up = await run_agent(
        session, client, model="test-model", question="А завтра?", conversation=conversation,
    )

    assert follow_up == "Завтра в Москве 5 °C."
    assert requests[2][0]["content"] == "Погода в Москве?"
    assert requests[2][1]["encrypted_content"] == "encrypted-test-data"
    assert requests[2][2]["call_id"] == requests[2][3]["call_id"] == "find_city"
    assert requests[2][4]["content"][0]["text"] == "Сейчас в Москве 3 °C."
    assert requests[2][-1] == {"role": "user", "content": "А завтра?"}

    conversation.clear()
    after_clear = await run_agent(
        session, client, model="test-model", question="А завтра?", conversation=conversation,
    )

    assert after_clear == "Для какого города нужен прогноз?"
    assert requests[3] == [{"role": "user", "content": "А завтра?"}]


@pytest.mark.asyncio
async def test_agent_passes_clarification_with_original_question(session):
    client, requests = model_with_responses(
        final_response("Какой Спрингфилд вы имеете в виду? Укажите штат."),
        final_response("Завтра в Спрингфилде, Иллинойс, 5 °C."),
    )
    conversation = Conversation()

    await run_agent(
        session, client, model="test-model",
        question="Какая погода завтра в Спрингфилде?", conversation=conversation,
    )
    answer = await run_agent(
        session, client, model="test-model", question="Иллинойс.", conversation=conversation,
    )

    assert answer == "Завтра в Спрингфилде, Иллинойс, 5 °C."
    assert requests[1][0]["content"] == "Какая погода завтра в Спрингфилде?"
    assert "Укажите штат" in requests[1][1]["content"][0]["text"]
    assert requests[1][2] == {"role": "user", "content": "Иллинойс."}


@pytest.mark.asyncio
async def test_incomplete_answer_does_not_change_conversation(session):
    client, requests = model_with_responses(
        final_response("Сейчас в Москве 3 °C."),
        SimpleNamespace(output=[
            tool_call("get_weather_forecast", "forecast", '{"latitude":59.94}'),
        ]),
        SimpleNamespace(status="incomplete", output=[], output_text="В Петербурге"),
        final_response("Завтра в Москве 5 °C."),
    )
    conversation = Conversation()

    await run_agent(
        session, client, model="test-model", question="Погода в Москве?", conversation=conversation,
    )
    before = conversation.snapshot()
    with pytest.raises(RuntimeError, match="не завершила"):
        await run_agent(
            session, client, model="test-model",
            question="Погода в Петербурге?", conversation=conversation,
        )

    assert conversation.snapshot() == before
    assert requests[2][-1]["call_id"] == "forecast"

    await run_agent(
        session, client, model="test-model", question="А завтра?", conversation=conversation,
    )
    assert requests[3] == [*before[1], {"role": "user", "content": "А завтра?"}]
