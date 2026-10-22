"""Boundaries between the domain and the outside world.

Each protocol is a small contract. The application only ever sees these shapes,
so swapping OpenAI for another provider — or a dict for Postgres — stays a
one-file change instead of a refactor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from triage_bot.domain.models import TriageDecision


@dataclass(frozen=True)
class LLMReply:
    content: str
    model: str
    tokens_in: int
    tokens_out: int


class LLMGateway(Protocol):
    def complete(self, prompt: str) -> LLMReply: ...


class HistoryStore(Protocol):
    def find(self, message_id: str) -> TriageDecision | None: ...

    def save(self, decision: TriageDecision) -> None: ...


@dataclass(frozen=True)
class RateLimit:
    allowed: bool
    retry_after_seconds: float = 0.0


class RateLimiter(Protocol):
    """Throttle per key (a Slack author) before we spend tokens on them."""

    def check(self, key: str) -> RateLimit: ...
