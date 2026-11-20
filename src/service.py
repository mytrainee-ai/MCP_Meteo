"""Открывает внешние клиенты на время одного сообщения чата."""

import logging

from anyio import fail_after
from openai import AsyncOpenAI

from .agent import generate_turn
from .config import Settings, configure_logging
from .conversation import Conversation
from .mcp_client import open_weather_session

logger = logging.getLogger(__name__)


async def answer_question(question: str, settings: Settings, conversation: Conversation) -> str:
    configure_logging(settings.debug)
    revision, history = conversation.snapshot()
    logger.debug("Запрос начат. Тайм-аут %.2f с.", settings.request_timeout_seconds)
    try:
        with fail_after(settings.request_timeout_seconds):
            async with (
                AsyncOpenAI(
                    api_key=settings.api_key,
                    base_url=settings.base_url,
                    timeout=settings.request_timeout_seconds,
                    max_retries=0,
                ) as client,
                open_weather_session(settings.mcp_url) as session,
            ):
                result = await generate_turn(
                    session, client,
                    model=settings.model, question=question, history=history,
                    max_steps=settings.max_steps, max_tool_calls=settings.max_tool_calls,
                )
    except Exception as error:
        logger.warning("Запрос завершился ошибкой: %s.", type(error).__name__)
        raise

    if result.items is not None:
        conversation.commit_turn(revision, result.items)
    logger.debug("Запрос завершён.")
    return result.text
