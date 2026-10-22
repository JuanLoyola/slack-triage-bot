"""Use case rules: escalation thresholds and idempotent handling."""

from triage_bot.application.agent import TriageAgent
from triage_bot.application.triage import RateLimited, TriageService
from triage_bot.infrastructure.history import InMemoryHistory
from triage_bot.infrastructure.rate_limit import PermissiveRateLimiter

LOW_CONFIDENCE = (
    '{"category": "question", "priority": "P2", "team": "support", '
    '"summary": "How do I reset my password?", "confidence": 0.4}'
)
P0_INCIDENT = (
    '{"category": "incident", "priority": "P0", "team": "engineering", '
    '"summary": "Payments API down for everyone", "confidence": 0.97}'
)
CONFIDENT_BUG = (
    '{"category": "bug", "priority": "P2", "team": "engineering", '
    '"summary": "Typo on the pricing page", "confidence": 0.88}'
)


def _service(llm) -> TriageService:
    return TriageService(TriageAgent(llm), InMemoryHistory(), PermissiveRateLimiter())


def test_low_confidence_escalates_to_a_human(llm, message):
    llm.push(LOW_CONFIDENCE)

    decision = _service(llm).handle(message)

    assert decision.escalated is True
    assert decision.attempts == 1


def test_p0_escalates_even_when_the_model_is_confident(llm, message):
    llm.push(P0_INCIDENT)

    decision = _service(llm).handle(message)

    assert decision.escalated is True


def test_confident_non_critical_message_routes_without_a_human(llm, message):
    llm.push(CONFIDENT_BUG)

    decision = _service(llm).handle(message)

    assert decision.escalated is False


def test_duplicate_delivery_uses_the_stored_decision(llm, message):
    llm.push(CONFIDENT_BUG)
    service = _service(llm)

    first = service.handle(message)
    second = service.handle(message)

    assert first == second
    assert len(llm.prompts) == 1  # no second LLM call for a redelivered message


class BudgetExceeded:
    """A limiter that has already decided this author is over budget."""

    def check(self, key):
        from triage_bot.domain.ports import RateLimit

        return RateLimit(allowed=False, retry_after_seconds=42.0)


def test_throttled_author_is_rejected_before_spending_tokens(llm, message):
    service = TriageService(TriageAgent(llm), InMemoryHistory(), BudgetExceeded())

    try:
        service.handle(message)
    except RateLimited as exc:
        assert exc.retry_after_seconds == 42.0
    else:
        raise AssertionError("expected RateLimited")

    assert llm.prompts == []  # the throttle fires before any LLM call


def test_redelivery_of_a_stored_decision_is_not_throttled(llm, message):
    """A retry of a message we already answered replays from history — the
    author shouldn't be penalised (or charged) for Slack's own redelivery."""
    llm.push(CONFIDENT_BUG)
    history = InMemoryHistory()
    first = TriageService(TriageAgent(llm), history, PermissiveRateLimiter()).handle(message)

    # Same message again, but now with a limiter that would block the author.
    throttled = TriageService(TriageAgent(llm), history, BudgetExceeded())

    assert throttled.handle(message) == first  # history wins over the throttle
