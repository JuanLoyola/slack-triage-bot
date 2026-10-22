"""Core triage vocabulary.

Deliberately framework-free: these types are what every layer agrees on, so they
stay boring and stable while everything around them changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Category(StrEnum):
    BUG = "bug"
    QUESTION = "question"
    FEATURE_REQUEST = "feature_request"
    INCIDENT = "incident"
    OTHER = "other"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Team(StrEnum):
    ENGINEERING = "engineering"
    SUPPORT = "support"
    PRODUCT = "product"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class IncomingMessage:
    id: str
    text: str
    author: str
    channel: str
    received_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class TriageDecision:
    message_id: str
    category: Category
    priority: Priority
    team: Team
    summary: str
    confidence: float
    escalated: bool
    attempts: int
