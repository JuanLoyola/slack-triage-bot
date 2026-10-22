"""End-to-end (minus Slack's servers): message in, postable reply out."""

from triage_bot.application.agent import TriageAgent
from triage_bot.application.triage import TriageService
from triage_bot.infrastructure.history import InMemoryHistory
from triage_bot.infrastructure.rate_limit import PermissiveRateLimiter
from triage_bot.infrastructure.slack_bot import render

GOOD_JSON = (
    '{"category": "bug", "priority": "P1", "team": "engineering", '
    '"summary": "Checkout button unresponsive on mobile Safari", "confidence": 0.92}'
)
LOW_CONFIDENCE_JSON = (
    '{"category": "question", "priority": "P3", "team": "product", '
    '"summary": "Ideas about the new branding maybe?", "confidence": 0.5}'
)


def _service(llm) -> TriageService:
    return TriageService(TriageAgent(llm), InMemoryHistory(), PermissiveRateLimiter())


def test_message_becomes_a_postable_reply(llm, message):
    llm.push(GOOD_JSON)

    reply = render(_service(llm).handle(message))

    assert "*P1 · bug*" in reply
    assert "`engineering`" in reply
    assert "92%" in reply
    assert "double-check" not in reply


def test_escalated_decision_asks_for_a_human(llm, message):
    llm.push(LOW_CONFIDENCE_JSON)

    reply = render(_service(llm).handle(message))

    assert "double-check" in reply
