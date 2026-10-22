"""Composition root: the only place that knows how the pieces fit together."""

from __future__ import annotations

import logging

from slack_bolt.adapter.socket_mode import SocketModeHandler

from triage_bot.application.agent import TriageAgent
from triage_bot.application.triage import TriageService
from triage_bot.config import ConfigError, Settings
from triage_bot.infrastructure.history import InMemoryHistory
from triage_bot.infrastructure.openai_gateway import OpenAIGateway
from triage_bot.infrastructure.rate_limit import SlidingWindowLimiter
from triage_bot.infrastructure.slack_bot import build_slack_app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    llm = OpenAIGateway(api_key=settings.openai_api_key, model=settings.model)
    limiter = SlidingWindowLimiter(
        max_requests=settings.rate_limit_per_author,
        window_seconds=settings.rate_limit_window_seconds,
    )
    service = TriageService(TriageAgent(llm), InMemoryHistory(), limiter)
    app = build_slack_app(service, settings)

    logging.getLogger(__name__).info("starting triage bot (model=%s)", settings.model)
    SocketModeHandler(app, settings.slack_app_token).start()


if __name__ == "__main__":
    main()
