from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from streamlit.testing.v1 import AppTest

from src import config, service

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


@pytest.fixture
def weather_reply(monkeypatch):
    settings = config.Settings(
        api_key="test-key",
        model="test-model",
        base_url="https://provider.invalid/v1",
        mcp_url="https://weather.invalid/mcp",
    )
    monkeypatch.setattr(config, "load_settings", lambda: settings)

    async def answer_question(question, actual_settings, conversation):
        assert actual_settings is settings
        revision, history = conversation.snapshot()
        if question == "А завтра?":
            answer = "Завтра в Москве 5 °C." if history else "Уточните город."
        else:
            answer = "Сейчас в Москве 3 °C."
        conversation.commit_turn(revision, [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])
        return answer

    reply = AsyncMock(side_effect=answer_question)
    monkeypatch.setattr(service, "answer_question", reply)
    return reply


def test_streamlit_chat_keeps_context_and_clears_both_histories(weather_reply):
    app = AppTest.from_file(APP_PATH).run()
    assert not app.exception
    assert app.title[0].value == "Weather AI Agent"
    assert app.button[0].label == "Очистить чат"
    assert app.button[0].proto.disabled

    app.chat_input[0].set_value("Какая погода в Москве?").run()
    assert not app.exception
    assert [message.name for message in app.chat_message] == ["user", "assistant"]
    assert [element.value for element in app.markdown] == [
        "Какая погода в Москве?", "Сейчас в Москве 3 °C.",
    ]

    app.chat_input[0].set_value("А завтра?").run()
    assert app.markdown[-1].value == "Завтра в Москве 5 °C."

    app.button[0].click().run()
    assert not app.chat_message
    assert app.session_state["conversation"].snapshot()[1] == []

    app.chat_input[0].set_value("А завтра?").run()
    assert not app.exception
    assert app.markdown[-1].value == "Уточните город."
    assert weather_reply.await_count == 3


def test_streamlit_sessions_are_isolated(weather_reply):
    first = AppTest.from_file(APP_PATH).run()
    second = AppTest.from_file(APP_PATH).run()

    first.chat_input[0].set_value("Какая погода в Москве?").run()
    second.chat_input[0].set_value("А завтра?").run()

    assert not first.exception and not second.exception
    assert first.markdown[-1].value == "Сейчас в Москве 3 °C."
    assert second.markdown[-1].value == "Уточните город."


def test_streamlit_handles_service_error_and_can_continue(weather_reply):
    app = AppTest.from_file(APP_PATH).run()
    answer = weather_reply.side_effect
    weather_reply.side_effect = RuntimeError("Private service diagnostic")

    app.chat_input[0].set_value("Погода в Москве?").run()

    assert not app.exception
    assert app.error[0].value.startswith("Не удалось получить прогноз.")
    assert "Private service diagnostic" not in app.error[0].value
    assert app.session_state["conversation"].snapshot()[1] == []
    assert not app.session_state["pending_question"]
    assert not app.chat_input[0].proto.disabled

    weather_reply.side_effect = answer
    app.chat_input[0].set_value("А завтра?").run()
    assert app.markdown[-1].value == "Уточните город."


def test_streamlit_shows_timeout_as_a_retryable_error(weather_reply):
    app = AppTest.from_file(APP_PATH).run()
    weather_reply.side_effect = TimeoutError("Private timeout diagnostic")

    app.chat_input[0].set_value("Погода в Москве?").run()

    assert not app.exception
    assert app.error[0].value.startswith("Превышено время ожидания")
    assert "Private timeout diagnostic" not in app.error[0].value
    assert not app.chat_input[0].proto.disabled


def test_streamlit_shows_missing_settings_and_disables_input(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda _: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    app = AppTest.from_file(APP_PATH).run()

    assert not app.exception
    assert "OPENAI_API_KEY" in app.error[0].value
    assert app.chat_input[0].proto.disabled
