"""Консольная точка входа для ядра агента."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from .agent import run_agent
from .conversation import Conversation
from .mcp_client import DEFAULT_MCP_URL, open_weather_session


async def answer_question(
    question: str, model: str, mcp_url: str, conversation: Conversation
) -> str:
    async with AsyncOpenAI() as client, open_weather_session(mcp_url) as session:
        return await run_agent(
            session, client, model=model, question=question, conversation=conversation,
        )


def read_question() -> str:
    try:
        return input("Ваш вопрос о погоде: ").strip()
    except EOFError:
        return ""


def main() -> int:
    print("Введите /clear для очистки диалога или нажмите Enter без вопроса для выхода.")
    question = read_question()
    if not question:
        print("Вопрос не должен быть пустым.")
        return 0

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not os.getenv("OPENAI_API_KEY", "").strip() or not model:
        print("Укажите OPENAI_API_KEY и OPENAI_MODEL в .env.", file=sys.stderr)
        return 1

    mcp_url = os.getenv("MCP_URL", DEFAULT_MCP_URL).strip() or DEFAULT_MCP_URL
    conversation = Conversation()
    while question:
        if question == "/clear":
            conversation.clear()
            print("Диалог очищен.")
        else:
            try:
                answer = asyncio.run(answer_question(question, model, mcp_url, conversation))
            except Exception:
                print("Не удалось получить ответ. Проверьте настройки и доступ к сервисам.", file=sys.stderr)
            else:
                print(answer)
        question = read_question()
    return 0


if __name__ == "__main__":
    sys.exit(main())
