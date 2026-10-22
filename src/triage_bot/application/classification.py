"""The wire format we ask the model for."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from triage_bot.domain.models import Category, Priority, Team


class Classification(BaseModel):
    """Validating at the boundary means the rest of the system can trust the
    object it receives — no defensive checks scattered downstream."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
    team: Team
    summary: str = Field(min_length=5, max_length=160)
    confidence: float = Field(ge=0.0, le=1.0)
