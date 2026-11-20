"""Открывает внешние клиенты на время одного сообщения чата."""

from openai import AsyncOpenAI

from .agent import run_agent
from .config import Settings
from .conversation import Conversation
from .mcp_client import open_weather_session


async def answer_question(question: str, settings: Settings, conversation: Conversation) -> str:
    async with (
        AsyncOpenAI(api_key=settings.api_key, base_url=settings.base_url) as client,
        open_weather_session(settings.mcp_url) as session,
    ):
        return await run_agent(
            session, client, model=settings.model, question=question, conversation=conversation,
        )
