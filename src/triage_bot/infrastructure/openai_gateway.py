"""OpenAI adapter — the only place that knows which LLM provider we use."""

from __future__ import annotations

from openai import OpenAI

from triage_bot.domain.ports import LLMReply


class OpenAIGateway:
    def __init__(self, api_key: str, model: str, temperature: float = 0.0) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        # Triage is classification, not creative writing: same input, same answer.
        self._temperature = temperature

    def complete(self, prompt: str) -> LLMReply:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = response.usage
        return LLMReply(
            content=response.choices[0].message.content or "",
            model=response.model,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )
