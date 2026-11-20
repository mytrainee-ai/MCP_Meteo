"""Браузерный чат Weather AI Agent."""

import asyncio
from typing import Literal, NotRequired, TypedDict

import streamlit as st
from openai import (
    APITimeoutError,
    AuthenticationError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from src import config, service
from src.conversation import Conversation


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    text: str
    error: NotRequired[bool]


def clear_chat() -> None:
    state = st.session_state
    if state.pending_question is None:
        state.chat_messages.clear()
        state.conversation.clear()


def queue_question() -> None:
    state = st.session_state
    question = (state.weather_input or "").strip()
    if question and state.pending_question is None:
        state.chat_messages.append({"role": "user", "text": question})
        state.pending_question = question


def render_message(message: ChatMessage) -> None:
    with st.chat_message(message["role"]):
        if message.get("error"):
            st.error(message["text"])
        else:
            st.markdown(message["text"])


def get_reply(question: str, settings: config.Settings, conversation: Conversation) -> ChatMessage:
    try:
        answer = asyncio.run(service.answer_question(question, settings, conversation))
    except (TimeoutError, APITimeoutError):
        error = "Превышено время ожидания прогноза. Попробуйте отправить вопрос ещё раз."
    except (AuthenticationError, PermissionDeniedError):
        error = "Провайдер отклонил доступ. Проверьте ключ API и доступ к выбранной модели."
    except RateLimitError:
        error = "Провайдер ограничил число запросов. Попробуйте ещё раз чуть позже."
    except OpenAIError:
        error = "Провайдер модели не смог обработать запрос. Проверьте адрес API и модель."
    except Exception:
        error = "Не удалось получить прогноз. Проверьте доступность погодного сервера и повторите запрос."
    else:
        return {"role": "assistant", "text": answer}

    return {"role": "assistant", "text": error, "error": True}


def main() -> None:
    st.set_page_config(page_title="Weather AI Agent", page_icon="🌤️")
    st.title("Weather AI Agent")
    st.caption("Спросите о текущей погоде или прогнозе. Можно продолжить вопросом «А завтра?».")

    state = st.session_state
    if "conversation" not in state:
        state.conversation = Conversation()
        state.chat_messages = []
        state.pending_question = None

    question = state.pending_question
    busy = question is not None
    st.button("Очистить чат", on_click=clear_chat, disabled=busy or not state.chat_messages)

    for message in state.chat_messages:
        render_message(message)

    try:
        settings = config.load_settings()
    except config.SettingsError as error:
        state.pending_question = None
        st.error(str(error))
        st.chat_input("Задайте вопрос о погоде", key="weather_input", disabled=True)
        return

    st.chat_input(
        "Задайте вопрос о погоде",
        key="weather_input",
        on_submit=queue_question,
        disabled=busy,
    )

    if busy:
        with st.chat_message("assistant"), st.spinner("Получаю погодные данные…"):
            reply = get_reply(question, settings, state.conversation)
        state.chat_messages.append(reply)
        state.pending_question = None
        st.rerun()


if __name__ == "__main__":
    main()
