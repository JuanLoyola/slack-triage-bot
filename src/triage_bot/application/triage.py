"""The use case: turn an incoming message into a routing decision."""

from __future__ import annotations

import logging

from triage_bot.application.agent import TriageAgent
from triage_bot.domain.models import IncomingMessage, Priority, TriageDecision
from triage_bot.domain.ports import HistoryStore, RateLimiter

logger = logging.getLogger(__name__)

# Below this confidence we refuse to auto-route: better to bother a human than to
# confidently send a payroll incident to the marketing board.
CONFIDENCE_THRESHOLD = 0.75


class RateLimited(RuntimeError):
    """An author blew through their token budget; don't call the LLM for them."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__(f"rate limited, retry in {retry_after_seconds:.0f}s")
        self.retry_after_seconds = retry_after_seconds


class TriageService:
    def __init__(
        self,
        agent: TriageAgent,
        history: HistoryStore,
        limiter: RateLimiter,
    ) -> None:
        self._agent = agent
        self._history = history
        self._limiter = limiter

    def handle(self, message: IncomingMessage) -> TriageDecision:
        previous = self._history.find(message.id)
        if previous is not None:
            # Slack retries deliveries; don't burn tokens on the same message twice.
            logger.info("replaying stored decision for %s", message.id)
            return previous

        # Throttle per author before spending anything: one noisy channel shouldn't
        # drain the whole token budget.
        budget = self._limiter.check(message.author)
        if not budget.allowed:
            logger.info("rate limited %s, retry in %.0fs", message.author,
                        budget.retry_after_seconds)
            raise RateLimited(budget.retry_after_seconds)

        outcome = self._agent.triage(message)
        verdict = outcome.classification
        escalated = verdict.confidence < CONFIDENCE_THRESHOLD or verdict.priority is Priority.P0

        decision = TriageDecision(
            message_id=message.id,
            category=verdict.category,
            priority=verdict.priority,
            team=verdict.team,
            summary=verdict.summary,
            confidence=verdict.confidence,
            escalated=escalated,
            attempts=outcome.attempts,
        )
        self._history.save(decision)
        return decision
