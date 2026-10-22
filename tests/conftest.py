"""Shared fixtures: a scripted LLM so tests never hit the network or a wallet."""

from __future__ import annotations

from collections import deque

import pytest

from triage_bot.domain.models import IncomingMessage
from triage_bot.domain.ports import LLMReply


class ScriptedLLM:
    """Fake gateway: the test scripts the model's replies, then asserts on prompts."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self._replies: deque[LLMReply] = deque()

    def push(self, content: str) -> None:
        self._replies.append(
            LLMReply(content=content, model="scripted", tokens_in=42, tokens_out=17)
        )

    def complete(self, prompt: str) -> LLMReply:
        self.prompts.append(prompt)
        if not self._replies:
            raise AssertionError("the code called the LLM more times than the test scripted")
        return self._replies.popleft()


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM()


@pytest.fixture
def message() -> IncomingMessage:
    return IncomingMessage(
        id="msg-1",
        text="Hola, el checkout no responde en Safari mobile desde ayer",
        author="U123",
        channel="C456",
    )
