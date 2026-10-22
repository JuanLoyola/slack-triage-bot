"""Environment configuration — fail fast, list everything that's missing."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_REQUIRED = ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY")


class ConfigError(RuntimeError):
    """Missing or unreadable environment configuration."""


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_app_token: str
    openai_api_key: str
    model: str = "gpt-4o-mini"
    # Per-author throttle: keeps one noisy human from draining the token budget.
    rate_limit_per_author: int = 5
    rate_limit_window_seconds: float = 60.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        missing = [name for name in _REQUIRED if not source.get(name)]
        if missing:
            raise ConfigError(f"missing environment variables: {', '.join(missing)}")
        return cls(
            slack_bot_token=source["SLACK_BOT_TOKEN"],
            slack_app_token=source["SLACK_APP_TOKEN"],
            openai_api_key=source["OPENAI_API_KEY"],
            model=source.get("TRIAGE_MODEL", "gpt-4o-mini"),
            rate_limit_per_author=int(source.get("RATE_LIMIT_PER_AUTHOR", "5")),
            rate_limit_window_seconds=float(source.get("RATE_LIMIT_WINDOW_SECONDS", "60")),
        )
