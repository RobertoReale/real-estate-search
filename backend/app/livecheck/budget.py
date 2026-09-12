"""What a live check is allowed to spend, and the refusals that enforce it.

The instrument runs from the machine the owner's scans go out from, which makes
its own thoroughness the danger: a matrix of five transports against two portals
is a retry loop wearing a lab coat, and invariant 8 exists because that is what
gets this residential address flagged for a day. So every limit here is a
refusal returned *before* a request is made, never a retry after one failed, and
a refused attempt is reported rather than silently dropped — an operator must be
able to see that the tool stopped asking, and why.

Two ledgers, because the two costs have nothing to do with each other:

- **Direct rungs** (`curl:*`, `curl+cookie`, `browser`) leave from this
  connection. They are governed by the per-portal request cap, by the spacing
  between requests, and by the blocked streak that abandons a portal which has
  said no three times running. Nothing about them costs money.
- **The paid rung** leaves from the provider's exit, so it costs credits instead
  of reputation. It is governed by the per-run credit cap and by a floor under
  the account balance, and asking for it at all takes `--paid`.

The streak deliberately cuts a run short. Against a portal that is refusing
everything, the first rung's answer is the finding and the remaining rungs are
just more requests from an address that has already been told no; `--rungs`
exists so a deliberate operator can measure a later rung on its own instead.
"""

import random
import time

from ..scrapers.transport import ESTIMATED_CREDITS_PER_PAGE

# The measured page price, which lives with the provider code that reads the
# receipts (`scrapers/transport.py`) because the scans account for their own
# spending against the same figure. Re-exported under the name this module has
# always used.
#
# The cap is checked against it *before* a call and charged the receipt after,
# which means one page may overshoot the cap by the difference and the next call
# is then refused. Refusing afterwards is the honest half: the alternative is
# pretending a bill was smaller than it was.
CREDITS_PER_PAGE = ESTIMATED_CREDITS_PER_PAGE

DEFAULT_MAX_REQUESTS = 12
DEFAULT_MAX_CREDITS = CREDITS_PER_PAGE
DEFAULT_CREDIT_FLOOR = 500
BLOCKED_STREAK_LIMIT = 3

# Jitter only ever *adds* to the configured delay. The scrapers' own
# `polite_sleep` may undershoot it slightly, which is right for a scan reading
# page after page of one search; here the whole point is to be gentler than a
# scan, so the floor is the setting and the randomness sits above it.
JITTER = (1.0, 1.35)


class Budget:
    """The spending limits of one run, and the clock that spaces it out.

    `sleep`, `now` and `rng` are injected so the offline tests can drive a whole
    run without waiting six seconds between attempts.
    """

    def __init__(
        self,
        *,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        delay_seconds: float = 6.0,
        max_credits: int = DEFAULT_MAX_CREDITS,
        credit_floor: int = DEFAULT_CREDIT_FLOOR,
        paid: bool = False,
        sleep=time.sleep,
        now=time.monotonic,
        rng: random.Random | None = None,
    ):
        self.max_requests = max_requests
        self.delay_seconds = delay_seconds
        self.max_credits = max_credits
        self.credit_floor = credit_floor
        self.paid = paid
        self.credits_spent = 0
        self._sleep = sleep
        self._now = now
        self._rng = rng or random.Random()
        self._requests: dict[str, int] = {}
        self._streak: dict[str, int] = {}
        self._last_at: dict[str, float] = {}

    # --- the residential connection -------------------------------------

    def refuse_direct(self, portal: str) -> str:
        """Why `portal` must not be asked again from this connection — empty
        when it may. The streak is checked first because it is the answer that
        explains the run stopping early."""
        if self._streak.get(portal, 0) >= BLOCKED_STREAK_LIMIT:
            return f"dropped after {BLOCKED_STREAK_LIMIT} blocked attempts in a row"
        if self._requests.get(portal, 0) >= self.max_requests:
            return f"request cap reached ({self.max_requests} per run)"
        return ""

    def wait(self, portal: str) -> None:
        """Sleep until this portal may politely be asked again."""
        last = self._last_at.get(portal)
        if last is None:
            return
        gap = self.delay_seconds * self._rng.uniform(*JITTER)
        remaining = gap - (self._now() - last)
        if remaining > 0:
            self._sleep(remaining)

    def record_request(self, portal: str) -> None:
        """One request has just left for `portal`."""
        self._requests[portal] = self._requests.get(portal, 0) + 1
        self._last_at[portal] = self._now()

    def record_outcome(self, portal: str, blocked: bool) -> None:
        """Extend or clear the blocked streak. Anything that is not a block
        clears it: a rung that got through proves the address is still welcome,
        whatever the previous rung was told."""
        if blocked:
            self._streak[portal] = self._streak.get(portal, 0) + 1
        else:
            self._streak[portal] = 0

    def requests_made(self, portal: str) -> int:
        return self._requests.get(portal, 0)

    def blocked_streak(self, portal: str) -> int:
        return self._streak.get(portal, 0)

    # --- the paid provider ----------------------------------------------

    def refuse_paid(self, remaining_credits: int | None, cost: int = CREDITS_PER_PAGE) -> str:
        """Why the paid rung must not run — empty when it may.

        `remaining_credits` is what the provider says is left on the account;
        `None` means it would not say. Unknown is refused rather than assumed,
        because "we could not check the balance" is not "the balance is fine" —
        `--credit-floor 0` is the explicit way to take that risk on a provider
        that publishes no account endpoint.
        """
        if not self.paid:
            return "the paid rung needs --paid"
        if self.credits_spent + cost > self.max_credits:
            return (
                f"credit cap reached (--max-credits {self.max_credits}, {self.credits_spent} spent)"
            )
        if self.credit_floor > 0:
            if remaining_credits is None:
                return "the provider did not report its remaining credits (--credit-floor 0 to proceed anyway)"
            if remaining_credits < self.credit_floor:
                return (
                    f"the account has {remaining_credits} credits left, "
                    f"below the floor (--credit-floor {self.credit_floor})"
                )
        return ""

    def spend(self, credits: int | None, fallback: int = CREDITS_PER_PAGE) -> None:
        """Charge the run for a paid call. The provider reports what it actually
        billed; when it does not, the measured page price is charged instead, so
        an unreadable receipt can never make the cap look untouched."""
        self.credits_spent += fallback if credits is None else credits

    # --- what the report records ----------------------------------------

    def as_dict(self) -> dict:
        return {
            "max_requests": self.max_requests,
            "delay_seconds": self.delay_seconds,
            "blocked_streak_limit": BLOCKED_STREAK_LIMIT,
            "paid": self.paid,
            "max_credits": self.max_credits,
            "credit_floor": self.credit_floor,
        }
