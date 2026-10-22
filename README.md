# Slack Triage Agent

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-12%20passing-brightgreen)
![Style](https://img.shields.io/badge/ruff-clean-red)
![CI](https://img.shields.io/badge/GitHub%20Actions-CI-blue)

An internal Slack bot that reads an `@mention`, classifies the message with an LLM
**(category · priority · owning team)** and replies with a routing decision — or
admits it isn't sure and escalates to a human.

A raw LLM call is a guess. This project wraps it in a **validation harness**:
structured output is checked against a schema, the model's own errors are fed
back to it for correction, and a hard attempt budget guarantees termination.

> Built as a portfolio project for **AI Automation / AI Engineering** roles:
> Python, LLM agents, self-correction loops, Slack integration, CI/CD and
> production-minded plumbing.

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Design notes](#design-notes)
- [TDD walkthrough](#tdd-walkthrough)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Observability](#observability)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)

---

## What it does

```
You                     Triage Bot
───                     ──────────
@TriageBot el checkout no responde
en Safari mobile desde ayer  ───▶  (LLM call #1 — validated ✅)


                        *P1 · bug* → `engineering`
                        > Checkout button unresponsive on mobile Safari
                        _confidence 92% · attempt 1_
```

Rules applied by the application (not the prompt — code is the contract):

| Condition | Result |
|-----------|--------|
| confidence ≥ 0.75, not P0 | Auto-routed to the owning team |
| confidence < 0.75 | **Escalated** — a human double-checks |
| priority = P0 | **Always escalated**, no matter the confidence |
| Model returns invalid JSON twice | Errors are fed back as feedback (self-correction) |
| Still invalid on attempt 3 | Gives up gracefully, bot tells the channel it needs a human |
| Slack redelivers the same message | Served from history — zero extra tokens |

## Architecture

Hexagonal-lite (ports & adapters) with a strict dependency rule:
**domain ← application ← infrastructure**, wired only at the composition root.

```
                    Slack (Socket Mode)
                          │  app_mention event
             ┌────────────▼──────────────┐
             │  infrastructure/slack_bot  │  ← adapter: parse event, render reply
             └────────────┬──────────────┘
                          │ IncomingMessage
             ┌────────────▼──────────────┐
             │   application/triage.py    │  ← use case: dedupe · escalate · persist
             └───────┬──────────┬────────┘
                     │          │
      ┌──────────────▼───┐   ┌──▼──────────────────────┐
      │ application/agent │   │ infrastructure/history   │
      │  (the harness)    │   │  (in-memory, behind port)│
      └──────────────┬───┘   └─────────────────────────┘
                     │ LLMGateway (Protocol)
             ┌───────▼──────────────┐
             │ infrastructure/openai │  ← the only file that knows the provider
             └──────────────────────┘

             main.py = composition root (builds the graph above)
```

| Layer | Package | Depends on | Never imports |
|-------|---------|-----------|---------------|
| Domain | `domain/` | stdlib only | frameworks, I/O |
| Application | `application/` | domain | Slack, OpenAI |
| Infrastructure | `infrastructure/` | domain (+ bolt/openai) | — |
| Wiring | `main.py` | everything | — |

## Design notes

**Ports & adapters.** The domain defines two tiny contracts — `LLMGateway` and
`HistoryStore` — as `Protocol`s. Tests substitute a scripted fake in one line;
swapping OpenAI for Anthropic, or the dict for Postgres, touches exactly one file.

**Per-author throttling, before any spend.** A `RateLimiter` port (also in the
domain) is checked in the use case, before the LLM is called: one noisy human
spamming @mentions can't drain the token budget. Over the limit raises
`RateLimited`, which the Slack adapter answers with a friendly "give me ~Ns".
Redeliveries of an already-answered message replay from history and are *not*
throttled — Slack's own retries shouldn't penalise the author (tested). Default
5 mentions/minute, tunable via `RATE_LIMIT_PER_AUTHOR` / `RATE_LIMIT_WINDOW_SECONDS`.

**No agent framework — on purpose.** The "agent" here is context → validate →
feed errors back → retry: ~30 lines. Wrapping that in a library would hide the
part worth understanding. (LangGraph earns its place when the graph grows branches
and state — see the roadmap.)

**SOLID, dialed in, no ceremony.**
- *SRP*: one reason to change per module (prompt lives with the agent, escalation
  rules live with the use case, rendering lives with the Slack adapter).
- *OCP*: new LLM provider or new storage = new adapter, zero edits to the use case.
- *DIP*: the application depends on abstractions, wired in `main.py`.
- *YAGNI (explicit)*: `TriageService` takes the concrete `TriageAgent`, not an
  interface — there is one implementation. Abstracting it now would be theater.

**The Clean Coder, in practice.** Tests first (red → green → refactor per feature),
small units with names that read like English, no dead code, and a hard stop:
`max_attempts` exists so the system fails loudly instead of looping forever.

**Microservice habits without the tax.** Bounded context (triage, and nothing
else), a literal contract at the model boundary (JSON schema in the prompt +
Pydantic validation), 12-factor config (env vars, fail-fast with every missing
key listed), idempotency (redeliveries don't re-spend tokens), structured logs
per attempt, container-ready image. It ships as **one deployable** because
splitting one bot into services would be ceremony, not architecture.

## TDD walkthrough

Every feature started as a failing test. The interesting three:

| Feature | 🔴 Red | 🟢 Green | 🔵 Refactor |
|---------|--------|----------|-------------|
| Self-correction | `test_feeds_validation_errors_back_to_the_model` | feedback string appended to prompt | error digest helper (`_digest`) |
| Bounded retries | `test_gives_up_after_the_attempt_budget` | loop + `ClassificationError` | fence-stripping extracted (`_bare_json`) |
| Escalation rules | `test_low_confidence_escalates_to_a_human` | threshold + P0 check | `CONFIDENCE_THRESHOLD` named constant |
| Idempotency | `test_duplicate_delivery_uses_the_stored_decision` | history lookup first | `InMemoryHistory` behind a lock |
| Config | `test_reports_every_missing_variable` | scan + raise | — |

Run them: `pytest` — 12 tests, no network, no API keys, fakes at the boundaries.

## Tech stack

| Concern | Choice | Why |
|---------|--------|-----|
| Language | Python 3.11+ | Target stack for AI engineering roles |
| LLM output validation | Pydantic v2 | `model_validate_json` + precise errors for feedback |
| LLM provider | OpenAI SDK (`temperature=0`) | Deterministic classification |
| Slack | slack-bolt (Socket Mode) | No public URL needed; official framework |
| Lint / format | ruff | Fast, one tool |
| Tests | pytest | Fixtures = scripted fake gateway |
| CI | GitHub Actions | Lint + tests on every push/PR |
| Packaging | src-layout + `pyproject.toml` | Imports resolve exactly like in prod |

## Getting started

**Prerequisites:** Python 3.11+, a [Slack app](https://api.slack.com/apps) with
Socket Mode enabled (scopes: `app_mentions:read`, `chat:write`; an app-level token
with `connections:write`), and an OpenAI API key.

```bash
# 1. install (editable + dev tools)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. verify — no keys needed, everything runs against fakes
pytest
ruff check src tests

# 3. configure
cp .env.example .env    # fill in SLACK_BOT_TOKEN, SLACK_APP_TOKEN, OPENAI_API_KEY

# 4. run
python -m triage_bot

# ...or containerize it
docker build -t triage-bot .
docker run --env-file .env triage-bot
```

Then invite the bot to a channel (`/invite @TriageBot`) and mention it.

## Observability

Every classification emits one log line with what you'd actually alert on:

```
INFO triage_bot.application.agent: triaged msg-1 on attempt 1 in 412ms (583 prompt / 74 completion tokens)
WARN triage_bot.application.agent: attempt 1 for msg-1 rejected: confidence: Field required; ...
```

- **Latency & token usage** per attempt (cost visibility built in from day one).
- **Rejected attempts** logged with the exact validation feedback.
- **Failures** raise a typed `ClassificationError`; the Slack adapter converts it
  into a human hand-off instead of a stack trace in the channel.

## Project structure

```
slack-triage-bot/
├── README.md
├── pyproject.toml            # deps, pytest & ruff config
├── Dockerfile
├── .github/workflows/ci.yml  # lint + tests gate
├── src/triage_bot/
│   ├── main.py               # composition root
│   ├── config.py             # env settings, fail-fast
│   ├── domain/
│   │   ├── models.py         # enums + frozen dataclasses
│   │   └── ports.py          # LLMGateway / HistoryStore protocols
│   ├── application/
│   │   ├── classification.py # Pydantic wire schema
│   │   ├── agent.py          # the harness: validate → feedback → retry
│   │   └── triage.py         # use case: dedupe, escalate, persist
│   └── infrastructure/
│       ├── openai_gateway.py # provider adapter
│       ├── slack_bot.py      # event adapter + rendering
│       └── history.py        # in-memory store (Postgres-ready port)
└── tests/
    ├── conftest.py           # ScriptedLLM fake + fixtures
    ├── unit/                 # agent, use case, config
    └── integration/          # message → postable reply
```

## Demo (record on Slack Free — $0)

Slack's Free plan is enough: workspace $0 (no card), and custom apps, Socket
Mode and bot tokens are all free — the plan's limits (90-day history, 10 app
installations) don't touch a demo. The one possible cost is OpenAI tokens for
the takes: a full run is ~6 `gpt-4o-mini` calls (well under $0.01) — put a $1
usage limit in the OpenAI dashboard if you want a hard cap.

1. **Workspace** — <https://slack.com/get-started#/create> (free, no card).
2. **App** — <https://api.slack.com/apps> → *Create New App → From scratch*:
   - enable **Socket Mode** → App-Level Token with `connections:write` → `xapp-…`
   - **OAuth & Permissions** → Bot Token Scopes `app_mentions:read` +
     `chat:write` → *Install to Workspace* → `xoxb-…`
3. **`.env`** — copy `.env.example`, fill the two Slack tokens and the OpenAI key.
4. **Run** — `python -m triage_bot.main`, then `/invite @YourBot` in a channel.
5. **Take (~60 s)** — record with **Win+G** (Xbox Game Bar, built into Windows)
   or OBS: mention a normal bug → the bot classifies it (category, priority,
   team); mention a P0 or a vague low-confidence message → it escalates to
   humans instead of guessing.
6. **Publish** — save as `hub/public/demos/slack-triage.mp4` (any 16:9), set
   `video.ready = true` for this project in `hub/lib/projects.ts`, rebuild the hub.

## Roadmap

- [ ] **LangGraph multi-step agent** — route incidents with tools (query status
      page, check on-call) instead of a single completion.
- [ ] **Postgres `HistoryStore`** — same two methods, add TTL cleanup.
- [ ] **`/health` endpoint + Prometheus metrics** — attempts histogram, token cost.
- [ ] **Slack interactivity** — "Looks wrong" button → reopen triage with feedback.
- [ ] **Evaluation set** — 30 labeled messages, run in CI to catch prompt regressions.

---

**Author:** Juan Loyola — Full Stack Developer expanding into AI Engineering
· [linkedin.com/in/loyolajuan](https://linkedin.com/in/loyolajuan) · jloyoladev@gmail.com
