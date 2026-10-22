"""Decisions from this process, kept in memory."""

from __future__ import annotations

from threading import Lock

from triage_bot.domain.models import TriageDecision


class InMemoryHistory:
    """Good enough for a single-process bot.

    The port it satisfies is the interesting part: when we outgrow one process,
    Postgres drops in behind the same two methods and nothing else changes.
    """

    def __init__(self) -> None:
        self._decisions: dict[str, TriageDecision] = {}
        # slack-bolt dispatches events concurrently; the lock keeps a
        # read-then-write (find/save) from interleaving on the same message.
        self._lock = Lock()

    def find(self, message_id: str) -> TriageDecision | None:
        with self._lock:
            return self._decisions.get(message_id)

    def save(self, decision: TriageDecision) -> None:
        with self._lock:
            self._decisions[decision.message_id] = decision
