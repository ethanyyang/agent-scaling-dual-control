from __future__ import annotations

import pytest

from completion_budget import BudgetExhausted, CompletionTokenBudget


def test_calls_share_one_episode_budget():
    b = CompletionTokenBudget(100)
    r1 = b.reserve(60)
    r2 = b.reserve(60)  # only 40 left to reserve
    assert r1.tokens == 60 and r2.tokens == 40
    b.commit(r1, 55)
    b.commit(r2, 30)
    s = b.snapshot()
    assert s.spent == 85 and s.reserved == 0 and s.remaining == 15 and not s.exhausted


def test_failed_call_releases_reservation():
    b = CompletionTokenBudget(100)
    r = b.reserve(70)
    b.release(r)
    assert b.snapshot().remaining == 100


def test_exhaustion_raises_and_overrun_is_recorded():
    b = CompletionTokenBudget(50)
    r = b.reserve()
    b.commit(r, 80)  # provider ignored the cap
    s = b.snapshot()
    assert s.overrun == 30 and s.exhausted
    with pytest.raises(BudgetExhausted):
        b.reserve(1)


def test_parallel_reservations_never_exceed_remaining():
    b = CompletionTokenBudget(100)
    a = b.reserve(50)
    c = b.reserve(50)
    with pytest.raises(BudgetExhausted):
        b.reserve(1)
    b.commit(a, 10)
    b.commit(c, 10)
    assert b.snapshot().remaining == 80
