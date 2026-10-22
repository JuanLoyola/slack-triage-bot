"""The sliding window itself: allowed up to N, then blocked, then freed."""

from triage_bot.infrastructure.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_limiter(max_requests: int = 3, window: float = 60.0):
    clock = FakeClock()
    return SlidingWindowLimiter(max_requests, window, clock=clock), clock


def test_allows_up_to_the_limit():
    limiter, _ = make_limiter(max_requests=3)

    assert all(limiter.check("U123").allowed for _ in range(3))


def test_blocks_the_request_over_the_limit():
    limiter, _ = make_limiter(max_requests=3)
    for _ in range(3):
        limiter.check("U123")

    budget = limiter.check("U123")

    assert not budget.allowed
    assert budget.retry_after_seconds > 0


def test_window_slides_and_frees_a_slot():
    limiter, clock = make_limiter(max_requests=2, window=60.0)
    limiter.check("U123")
    limiter.check("U123")

    clock.advance(30)
    assert not limiter.check("U123").allowed  # still inside the window

    clock.advance(31)  # first hit is now 61s old
    assert limiter.check("U123").allowed


def test_authors_have_independent_budgets():
    limiter, _ = make_limiter(max_requests=1)
    assert limiter.check("U123").allowed

    assert limiter.check("U999").allowed  # another human, another bucket
