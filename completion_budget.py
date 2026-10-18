"""System-wide completion-token accounting for budget-matched agent runs.

Ported by hand from branch test/glm46-airline (dce0a24), unchanged in logic:
one ledger per episode; reserve before a call, commit provider-reported
completion tokens after it, release on a failed call; a snapshot exposes
spent / reserved / remaining / overrun for the audit trail (ANALYSIS.md §4.3).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from typing import Any


class BudgetExhausted(RuntimeError):
    """Raised when no completion-token allowance remains."""


@dataclass(frozen=True)
class BudgetReservation:
    """An allowance reserved for one in-flight LLM call."""

    reservation_id: str
    tokens: int


@dataclass(frozen=True)
class BudgetSnapshot:
    """Auditable state of an episode-level completion-token budget."""

    limit: int
    spent: int
    reserved: int
    remaining: int
    exhausted: bool
    overrun: int

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


class CompletionTokenBudget:
    """Thread-safe shared completion-token ledger.

    Reservations prevent concurrent workers from each seeing and spending the
    same remaining allowance. Actual provider-reported completion tokens are
    committed after a response; unused reservation is released automatically.
    """

    def __init__(self, limit: int):
        if limit <= 0:
            raise ValueError("Completion-token budget must be positive")
        self.limit = limit
        self._spent = 0
        self._reserved = 0
        self._open: dict[str, int] = {}
        self._lock = threading.Lock()

    def reserve(self, requested: int | None = None) -> BudgetReservation:
        """Reserve up to ``requested`` tokens, or all available tokens."""
        if requested is not None and requested <= 0:
            raise ValueError("Requested reservation must be positive")
        with self._lock:
            available = max(self.limit - self._spent - self._reserved, 0)
            if available == 0:
                raise BudgetExhausted("Completion-token budget is exhausted")
            tokens = available if requested is None else min(requested, available)
            reservation_id = uuid.uuid4().hex
            self._open[reservation_id] = tokens
            self._reserved += tokens
            return BudgetReservation(reservation_id=reservation_id, tokens=tokens)

    def commit(self, reservation: BudgetReservation, actual_tokens: int) -> None:
        """Commit provider-reported use and close a reservation."""
        if actual_tokens < 0:
            raise ValueError("Actual token use cannot be negative")
        with self._lock:
            reserved = self._pop_open(reservation)
            self._reserved -= reserved
            self._spent += actual_tokens

    def release(self, reservation: BudgetReservation) -> None:
        """Close a failed/cancelled call without charging completion tokens."""
        with self._lock:
            reserved = self._pop_open(reservation)
            self._reserved -= reserved

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            remaining = max(self.limit - self._spent - self._reserved, 0)
            return BudgetSnapshot(
                limit=self.limit,
                spent=self._spent,
                reserved=self._reserved,
                remaining=remaining,
                exhausted=remaining == 0,
                overrun=max(self._spent - self.limit, 0),
            )

    def _pop_open(self, reservation: BudgetReservation) -> int:
        try:
            reserved = self._open.pop(reservation.reservation_id)
        except KeyError as exc:
            raise ValueError("Reservation is unknown or already closed") from exc
        if reserved != reservation.tokens:
            raise ValueError("Reservation token count does not match the ledger")
        return reserved


def completion_tokens_from_usage(usage: Any) -> int:
    """Read completion tokens from a litellm usage object or dict; fail loudly if absent."""
    if usage is None:
        raise ValueError("LLM response is missing usage; an unmetered call would invalidate the comparison")
    for key in ("completion_tokens", "output_tokens"):
        value = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
        if value is not None:
            return int(value)
    raise ValueError("LLM response usage has no completion-token field")
