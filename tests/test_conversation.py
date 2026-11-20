import pytest

from src.conversation import Conversation


def weather_turn(city):
    return [
        {"role": "user", "content": city},
        {"type": "function_call", "call_id": city, "name": "geocode_location", "arguments": "{}"},
        {"type": "function_call_output", "call_id": city, "output": "{}"},
        {"role": "assistant", "content": f"Погода в городе {city}"},
    ]


def test_conversation_trims_whole_turns():
    conversation = Conversation(max_turns=2)
    for city in ("Москва", "Берлин", "Париж"):
        revision, _ = conversation.snapshot()
        conversation.commit_turn(revision, weather_turn(city))

    assert conversation.snapshot()[1] == [*weather_turn("Берлин"), *weather_turn("Париж")]


def test_conversations_are_isolated_and_snapshots_can_be_modified():
    first = Conversation()
    second = Conversation()
    revision, _ = first.snapshot()
    first.commit_turn(revision, weather_turn("Москва"))

    _, history = first.snapshot()
    history[0]["content"] = "Париж"

    assert first.snapshot()[1] == weather_turn("Москва")
    assert second.snapshot()[1] == []


def test_clear_rejects_turn_started_before_reset():
    conversation = Conversation()
    revision, _ = conversation.snapshot()

    conversation.clear()

    with pytest.raises(RuntimeError, match="Диалог изменился"):
        conversation.commit_turn(revision, weather_turn("Москва"))
    assert conversation.snapshot()[1] == []
