"""Configuration: fail fast and name every missing variable at once."""

import pytest

from triage_bot.config import ConfigError, Settings

FULL_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-test",
    "SLACK_APP_TOKEN": "xapp-test",
    "OPENAI_API_KEY": "sk-test",
}


def test_reports_every_missing_variable():
    with pytest.raises(ConfigError) as exc:
        Settings.from_env({})

    message = str(exc.value)
    assert "SLACK_BOT_TOKEN" in message
    assert "OPENAI_API_KEY" in message


def test_reads_settings_and_defaults_the_model():
    settings = Settings.from_env(FULL_ENV)

    assert settings.slack_bot_token == "xoxb-test"
    assert settings.model == "gpt-4o-mini"

    custom = Settings.from_env({**FULL_ENV, "TRIAGE_MODEL": "gpt-4o"})
    assert custom.model == "gpt-4o"
