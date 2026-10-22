"""The agent harness.

A raw LLM call is a guess; this module turns it into something the rest of the
code can rely on: context in, structured (and validated) classification out,
with the model's own errors fed back to it until it gets the shape right.

No agent framework here on purpose — the loop is ~30 lines, and hiding it
behind a library would remove exactly the part worth understanding.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from pydantic import ValidationError

from triage_bot.application.classification import Classification
from triage_bot.domain.models import IncomingMessage
from triage_bot.domain.ports import LLMGateway

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You triage messages that land in an internal Slack workspace.

Classify the message and reply with ONLY a JSON object shaped exactly like:
{"category": "...", "priority": "...", "team": "...", "summary": "...", "confidence": 0.0}

Allowed values:
- category: bug | question | feature_request | incident | other
- priority: P0 (production down or users blocked) | P1 (degraded) | P2 (normal) | P3 (nice to have)
- team: engineering | support | product
- summary: one line (max ~120 chars) describing what the requester actually needs
- confidence: 0.0 to 1.0 — how sure you are of this classification

If you are guessing, say so with a low confidence: a human reviews anything under
the threshold. No prose, no markdown fences, JSON only.
"""

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class ClassificationError(RuntimeError):
    """The model never produced a usable answer within the attempt budget."""


@dataclass(frozen=True)
class AgentOutcome:
    classification: Classification
    attempts: int
    tokens_in: int
    tokens_out: int
    elapsed_ms: int


def build_prompt(message: IncomingMessage, feedback: str | None = None) -> str:
    parts = [
        _SYSTEM_PROMPT,
        f"Channel: {message.channel}",
        f"Author: {message.author}",
        "Message:",
        message.text,
    ]
    if feedback:
        # Autocorrection: the previous answer was rejected by the validator, so we
        # hand the exact reasons back instead of retrying blind and hoping.
        parts += [
            "",
            "Your previous attempt was rejected:",
            feedback,
            "",
            "Fix it and reply with the corrected JSON only.",
        ]
    return "\n".join(parts)


def _digest(exc: ValidationError) -> str:
    """Condense pydantic's output into feedback a model can act on (top 3 issues)."""
    issues = [
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()[:3]
    ]
    return "; ".join(issues)


def _bare_json(raw: str) -> str:
    # Models love wrapping JSON in markdown fences; strip them before parsing.
    return _FENCE.sub("", raw.strip()).strip()


class TriageAgent:
    def __init__(self, llm: LLMGateway, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._llm = llm
        self._max_attempts = max_attempts

    def triage(self, message: IncomingMessage) -> AgentOutcome:
        feedback: str | None = None
        tokens_in = tokens_out = 0
        last_problem = "no attempt yet"
        started = time.perf_counter()

        for attempt in range(1, self._max_attempts + 1):
            reply = self._llm.complete(build_prompt(message, feedback))
            tokens_in += reply.tokens_in
            tokens_out += reply.tokens_out

            try:
                classification = Classification.model_validate_json(_bare_json(reply.content))
            except ValidationError as exc:
                last_problem = _digest(exc)
                feedback = last_problem
                logger.warning(
                    "attempt %d for %s rejected: %s", attempt, message.id, last_problem
                )
                continue

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "triaged %s on attempt %d in %dms (%d prompt / %d completion tokens)",
                message.id,
                attempt,
                elapsed_ms,
                tokens_in,
                tokens_out,
            )
            return AgentOutcome(classification, attempt, tokens_in, tokens_out, elapsed_ms)

        raise ClassificationError(
            f"{message.id}: gave up after {self._max_attempts} attempts "
            f"— last problem: {last_problem}"
        )
