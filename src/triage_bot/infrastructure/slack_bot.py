"""Slack adapter: events in, formatted replies out."""

from __future__ import annotations

import re

from slack_bolt import App

from triage_bot.application.agent import ClassificationError
from triage_bot.application.triage import RateLimited, TriageService
from triage_bot.config import Settings
from triage_bot.domain.models import IncomingMessage, TriageDecision

_MENTION = re.compile(r"<@[^>]+>")


def render(decision: TriageDecision) -> str:
    header = f"*{decision.priority.value} · {decision.category.value}* → `{decision.team.value}`"
    escalation = (
        "\n:warning: Low confidence or P0 — a human should double-check this one."
        if decision.escalated
        else ""
    )
    meta = f"_confidence {decision.confidence:.0%} · attempt {decision.attempts}_"
    return f"{header}\n> {decision.summary}\n{meta}{escalation}"


def build_slack_app(service: TriageService, settings: Settings) -> App:
    app = App(token=settings.slack_bot_token)

    # We react to app_mention instead of every message on purpose: the bot stays
    # quiet until asked, and can't fall into the classic reply-to-itself loop.
    @app.event("app_mention")
    def handle_mention(body, say, logger):
        event = body["event"]
        text = _MENTION.sub("", event.get("text", "")).strip()
        message = IncomingMessage(
            # Stable id so redeliveries of the same message dedupe in history.
            id=event.get("client_msg_id") or f"{event['channel']}:{event['ts']}",
            text=text,
            author=event.get("user", "unknown"),
            channel=event["channel"],
        )
        try:
            say(render(service.handle(message)))
        except ClassificationError:
            logger.exception("triage failed for %s", message.id)
            say(
                ":shrug: I couldn't classify that one — three attempts and still no valid "
                "JSON. Over to a human before I loop forever."
            )
        except RateLimited as limit:
            # Not an error: the author spent their budget. Tell them when to come
            # back instead of silently dropping the mention.
            say(
                f":hourglass_flowing_sand: You're triaging faster than I can think — "
                f"give me ~{limit.retry_after_seconds:.0f}s and mention me again."
            )

    return app
