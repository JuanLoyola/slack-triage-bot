"""Agent harness: valid output, self-correction, and the give-up budget."""

import pytest

from triage_bot.application.agent import ClassificationError, TriageAgent
from triage_bot.domain.models import Category, Priority

GOOD_JSON = (
    '{"category": "bug", "priority": "P1", "team": "engineering", '
    '"summary": "Checkout breaks on Safari mobile", "confidence": 0.9}'
)
BROKEN_JSON = '{"category": "tanque", "priority": "urgent"}'


def test_classifies_in_one_attempt_when_the_model_behaves(llm, message):
    llm.push(GOOD_JSON)

    outcome = TriageAgent(llm).triage(message)

    assert outcome.attempts == 1
    assert outcome.classification.category is Category.BUG
    assert outcome.classification.priority is Priority.P1
    assert "previous attempt" not in llm.prompts[0]


def test_feeds_validation_errors_back_to_the_model(llm, message):
    llm.push(BROKEN_JSON)
    llm.push(GOOD_JSON)

    outcome = TriageAgent(llm).triage(message)

    assert outcome.attempts == 2
    retry_prompt = llm.prompts[1]
    assert "previous attempt was rejected" in retry_prompt
    # the missing field is named in the feedback, so the model knows what to fix
    assert "confidence" in retry_prompt


def test_tolerates_markdown_fences(llm, message):
    llm.push(f"```json\n{GOOD_JSON}\n```")

    outcome = TriageAgent(llm).triage(message)

    assert outcome.attempts == 1


def test_gives_up_after_the_attempt_budget(llm, message):
    for _ in range(3):
        llm.push(BROKEN_JSON)

    with pytest.raises(ClassificationError, match="gave up after 3 attempts"):
        TriageAgent(llm).triage(message)

    assert len(llm.prompts) == 3
