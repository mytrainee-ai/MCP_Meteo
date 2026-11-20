"""Память завершённых обменов для одной сессии агента."""

from collections import deque
from copy import deepcopy

from openai.types.responses import ResponseInputParam

DEFAULT_MAX_TURNS = 8


class Conversation:
    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS) -> None:
        if max_turns < 1:
            raise ValueError("Лимит истории должен быть положительным.")
        self._turns: deque[ResponseInputParam] = deque(maxlen=max_turns)
        self._revision = 0

    def snapshot(self) -> tuple[int, ResponseInputParam]:
        history = [item for turn in self._turns for item in turn]
        return self._revision, deepcopy(history)

    def commit_turn(self, revision: int, turn: ResponseInputParam) -> None:
        if revision != self._revision:
            raise RuntimeError("Диалог изменился, пока агент готовил ответ.")
        self._turns.append(deepcopy(turn))
        self._revision += 1

    def clear(self) -> None:
        self._turns.clear()
        self._revision += 1
