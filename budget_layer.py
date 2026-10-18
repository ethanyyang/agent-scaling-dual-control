"""Shared budget layer for S1 (capped reruns) and M1: base-prompt loading with a
hash check, metered LLM calls with a per-call cap, the wrap-up notice, and the
exhaustion label. Implements ANALYSIS.md §4.1 to §4.3 and the rule table in
docs/budget-protocol.md (R1 to R10).

Design notes
- Every model call in the study goes through `metered_generate`. It reserves
  an allowance before the call, commits the provider-reported completion
  tokens after it, and records a per-call snapshot on the returned message.
- The metering hole in the branch reference (a response that arrives but
  fails tool-call JSON parsing was released and never charged) is closed:
  usage is read and committed BEFORE tool calls are parsed. A parse failure
  or `finish_reason == "length"` is recorded as `truncated` and the tool call
  is dropped, never executed (R6).
- Nothing here depends on the architecture; S1 and M1 both use it.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from tau2.data_model.message import AssistantMessage, Message, SystemMessage, ToolCall
from tau2.environment.tool import Tool
from tau2.utils import llm_utils

from completion_budget import (
    BudgetExhausted,
    BudgetReservation,
    CompletionTokenBudget,
    completion_tokens_from_usage,
)

ROOT = Path(__file__).resolve().parent
BASE_PROMPT_PATH = ROOT / "prompts" / "base_system_prompt.md"
WRAPUP_NOTICE_PATH = ROOT / "prompts" / "budget_wrapup_notice.md"
ROLES_DIR = ROOT / "prompts" / "roles"

BUDGET_METADATA_KEY = "transfer_testing_completion_budget"
CALL_METADATA_KEY = "transfer_testing_call"
TERMINATION_KEY = "transfer_testing_termination"
TERMINATION_NORMAL = "normal"
TERMINATION_EXHAUSTED = "budget_exhausted"

# Fixed exhaustion message (hashed into the protocol record at the freeze).
DEFAULT_EXHAUSTED_MESSAGE = (
    "I'm sorry, but I'm unable to continue within the available processing "
    "budget. Anything not yet completed will need to be handled separately."
)


# ---------------------------------------------------------------------------
# Prompt files
# ---------------------------------------------------------------------------


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_html_comment_header(text: str) -> str:
    """Prompt files carry an HTML comment header with provenance; the model never sees it."""
    text = text.lstrip()
    if text.startswith("<!--"):
        end = text.index("-->")
        text = text[end + 3 :]
    return text.strip()


def load_prompt_block(path: Path) -> str:
    return strip_html_comment_header(path.read_text(encoding="utf-8"))


def load_base_prompt_template(expected_sha256: Optional[str] = None) -> str:
    """The tau2 default agent prompt with a `{domain_policy}` placeholder (ANALYSIS.md §2).

    If `expected_sha256` is given (the digest recorded in §2), a mismatch raises,
    so a drifted prompt file cannot silently enter a run (protocol R10).
    """
    template = load_prompt_block(BASE_PROMPT_PATH)
    if "{domain_policy}" not in template:
        raise ValueError("base prompt template has no {domain_policy} placeholder")
    if expected_sha256 and not sha256_text(template).startswith(expected_sha256.rstrip("…")):
        raise ValueError(
            f"base prompt hash {sha256_text(template)[:16]} does not match the recorded {expected_sha256[:16]}"
        )
    return template


def render_base_prompt(domain_policy: str, expected_sha256: Optional[str] = None) -> str:
    # str.replace, not str.format: the policy text contains braces.
    return load_base_prompt_template(expected_sha256).replace("{domain_policy}", domain_policy)


def load_role_block(name: str, **fills: str) -> str:
    """Role block appended after the base prompt; `{role}` style fills are literal replacements."""
    text = load_prompt_block(ROLES_DIR / f"{name}.md")
    for key, value in fills.items():
        text = text.replace("{" + key + "}", value)
    return text


def load_wrapup_notice() -> str:
    return WRAPUP_NOTICE_PATH.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Budget configuration and per-episode state
# ---------------------------------------------------------------------------


@dataclass
class BudgetConfig:
    """Frozen per-cell values from ANALYSIS.md §4.2 and docs/budget-protocol.md §1."""

    limit: Optional[int]  # B (None = uncapped, used only for S1 calibration)
    per_call_cap: Optional[int]  # c = P95 of S1 per-call completion tokens
    wrapup_threshold: Optional[int]  # w = max(0.15 * B, 2 * median S1 per-call)
    min_call_allowance: int  # a_min = median S1 per-call completion tokens
    exhausted_message: str = DEFAULT_EXHAUSTED_MESSAGE

    @classmethod
    def uncapped(cls) -> "BudgetConfig":
        return cls(limit=None, per_call_cap=None, wrapup_threshold=None, min_call_allowance=1)

    @classmethod
    def uncapped_with_guard(cls, b_1x: int, per_call_p95: int, per_call_median: int, cap_rule: str = "b1x") -> "BudgetConfig":
        """Uncapped arm (ANALYSIS.md §8 addendum 2026-09-24): no episode ceiling, no wrap-up
        notice and no allowance line; only tau2's step and error limits end an episode. The
        per-call guard c is kept as a runaway stop, with the same value as in the capped arms."""
        if cap_rule == "b1x":
            cap = int(b_1x)
        elif cap_rule == "p95":
            cap = int(per_call_p95)
        else:
            raise ValueError(f"unknown cap_rule {cap_rule!r}")
        return cls(limit=None, per_call_cap=cap, wrapup_threshold=None, min_call_allowance=max(1, int(per_call_median)))

    @classmethod
    def from_calibration(
        cls, b_1x: int, per_call_p95: int, per_call_median: int, multiplier: float = 1.0, cap_rule: str = "p95"
    ) -> "BudgetConfig":
        """cap_rule: "p95" = c is the S1 per-call P95 (original §4.2 wording); "b1x" = c is B_1x
        itself, a runaway guard that touches 0 to 1% of S1 episodes (CHANGELOG 2026-09-2x).
        The cap never scales with `multiplier`: the same c applies in every arm."""
        limit = max(1, int(round(b_1x * multiplier)))
        a_min = max(1, int(per_call_median))
        w = max(int(round(0.15 * limit)), 2 * a_min)
        if cap_rule == "b1x":
            cap = int(b_1x)
        elif cap_rule == "p95":
            cap = int(per_call_p95)
        else:
            raise ValueError(f"unknown cap_rule {cap_rule!r}")
        return cls(limit=limit, per_call_cap=cap, wrapup_threshold=w, min_call_allowance=a_min)

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "per_call_cap": self.per_call_cap,
            "wrapup_threshold": self.wrapup_threshold,
            "min_call_allowance": self.min_call_allowance,
            "exhausted_message_sha256": sha256_text(self.exhausted_message),
        }


@dataclass
class CallRecord:
    component: str
    call_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    reasoning_tokens: Optional[int]
    max_tokens_sent: Optional[int]
    finish_reason: Optional[str]
    truncated: bool
    cost: float
    seconds: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class EpisodeBudget:
    """One episode's ledger plus the wrap-up / exhaustion state and the per-call log."""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self.ledger = CompletionTokenBudget(config.limit) if config.limit else None
        self.wrapup_triggered = False
        self.calls: list[CallRecord] = []

    # --- state queries -----------------------------------------------------
    @property
    def remaining(self) -> Optional[int]:
        return self.ledger.snapshot().remaining if self.ledger else None

    def exhausted_before_call(self) -> bool:
        return self.ledger is not None and self.remaining < self.config.min_call_allowance

    def needs_wrapup(self) -> bool:
        return (
            self.ledger is not None
            and not self.wrapup_triggered
            and self.config.wrapup_threshold is not None
            and self.remaining < self.config.wrapup_threshold
        )

    def allowance(self, per_call_cap: Optional[int] = None) -> Optional[int]:
        """Tokens this call may spend: min(remaining, per-call cap); None when uncapped.

        `per_call_cap` overrides the cell's c for this call (M1 orchestrator and
        advisor calls, whose thinking is longer than an S1 turn's; see CHANGELOG
        2026-09-20). The episode ledger always binds.
        """
        cap = per_call_cap if per_call_cap is not None else self.config.per_call_cap
        if self.ledger is None:
            return cap
        rem = self.remaining
        return min(rem, cap) if cap else rem

    def snapshot(self) -> dict[str, Any]:
        base: dict[str, Any] = (
            self.ledger.snapshot().to_dict()
            if self.ledger
            else {"limit": None, "spent": sum(c.completion_tokens for c in self.calls), "reserved": 0, "remaining": None, "exhausted": False, "overrun": 0}
        )
        base.update(
            {
                "per_call_cap": self.config.per_call_cap,
                "wrapup_threshold": self.config.wrapup_threshold,
                "min_call_allowance": self.config.min_call_allowance,
                "wrapup_triggered": self.wrapup_triggered,
                "n_calls": len(self.calls),
                "truncated_calls": sum(1 for c in self.calls if c.truncated),
            }
        )
        return base


INTERNAL_NOTE = "[INTERNAL, not from the customer]"


def budget_status_line(budget: "EpisodeBudget", labels: Optional[dict[str, str]] = None) -> Optional[str]:
    """One line telling the agent its remaining allowance and what its calls have cost so far.

    Shown on every call of a capped condition (S1 under a cap, M1), so the agent can
    decide how to spend; the wrap-up notice still fires below `w`. Returns None when
    the episode is uncapped (calibration). `labels` maps call_name -> short label
    (default: the call_name itself). Averages are this episode's own, so nothing
    is leaked about other tasks.
    """
    if budget.ledger is None:
        return None
    snap = budget.ledger.snapshot()
    parts = [
        f"{INTERNAL_NOTE} Processing allowance: {snap.remaining} of {snap.limit} output tokens left for this whole conversation"
        f" (your thinking counts; each call is capped at {budget.config.per_call_cap})."
    ]
    if budget.calls:
        by: dict[str, list[int]] = {}
        for c in budget.calls:
            by.setdefault(c.call_name, []).append(c.completion_tokens)
        labels = labels or {}
        avg = ", ".join(f"{labels.get(k, k)} {sum(v) // len(v)}" for k, v in by.items())
        parts.append(f"Average cost of your calls so far: {avg}. Last call: {budget.calls[-1].completion_tokens}.")
    parts.append("Plan your spending so the customer's request is resolved before the allowance runs out.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Metered generation
# ---------------------------------------------------------------------------

REASONING_ONLY_CUTOFF_MARKER = "unable to complete request: max_output_tokens"


def _is_reasoning_only_cutoff(exc: BaseException) -> bool:
    return REASONING_ONLY_CUTOFF_MARKER in str(exc)


def _reasoning_only_cutoff_reply(
    model: str,
    call_name: str,
    component: str,
    budget: "EpisodeBudget",
    reservation: Optional[BudgetReservation],
    max_tokens_sent: int,
    seconds: float,
    exc: BaseException,
) -> AssistantMessage:
    completion_tokens = int(max_tokens_sent)
    if reservation is not None:
        budget.ledger.commit(reservation, completion_tokens)
    record = CallRecord(
        component=component, call_name=call_name, model=model,
        prompt_tokens=0, completion_tokens=completion_tokens, cached_tokens=0, reasoning_tokens=completion_tokens,
        max_tokens_sent=max_tokens_sent, finish_reason="length", truncated=True, cost=0.0, seconds=seconds,
    )
    budget.calls.append(record)
    raw: dict[str, Any] = {
        CALL_METADATA_KEY: {**record.to_dict(), "parse_error": None, "usage_source": "cap (provider returned no usage)", "provider_error": str(exc)[:300]},
        BUDGET_METADATA_KEY: {**budget.snapshot(), "component": component},
    }
    return AssistantMessage(
        role="assistant", content=None, tool_calls=None, cost=0.0,
        usage={"prompt_tokens": 0, "completion_tokens": completion_tokens, "cached_tokens": 0, "reasoning_tokens": completion_tokens},
        raw_data=raw, generation_time_seconds=seconds,
    )


def _usage_fields(response: Any) -> tuple[int, int, int, Optional[int]]:
    """(prompt, completion, cached_input, reasoning) from a litellm ModelResponse."""
    usage = response.get("usage") if hasattr(response, "get") else getattr(response, "usage", None)
    if usage is None:
        raise ValueError("LLM response is missing usage; an unmetered call would invalidate the comparison")
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = completion_tokens_from_usage(usage)
    cached = 0
    reasoning: Optional[int] = None
    pd = getattr(usage, "prompt_tokens_details", None)
    if pd is not None:
        cached = int(getattr(pd, "cached_tokens", 0) or 0)
    cd = getattr(usage, "completion_tokens_details", None)
    if cd is not None and getattr(cd, "reasoning_tokens", None) is not None:
        reasoning = int(cd.reasoning_tokens)
    return prompt, completion, cached, reasoning


def _parse_tool_calls(choice: Any) -> tuple[Optional[list[ToolCall]], Optional[str]]:
    raw = getattr(choice.message, "tool_calls", None) or []
    calls: list[ToolCall] = []
    for tc in raw:
        try:
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments)))
        except Exception as exc:  # truncated or malformed arguments
            return None, f"{type(exc).__name__}: {exc}"
    return (calls or None), None


def metered_generate(
    *,
    model: str,
    messages: list[Message],
    tools: Optional[list[Tool]],
    llm_args: dict[str, Any],
    call_name: str,
    component: str,
    budget: EpisodeBudget,
    per_call_cap: Optional[int] = None,
    tool_choice: Optional[str] = None,
) -> AssistantMessage:
    """One LLM call charged to the episode ledger (protocol R1, R3, R6, R8).

    `tool_choice` defaults to "auto" when tools are passed (S1, M1). S2's plan call passes
    the tools with tool_choice "none", so it sees the same context as its act call.

    Raises BudgetExhausted if no allowance remains. Never raises on a truncated
    or unparsable tool call: the message comes back with no tool calls and
    `raw_data[CALL_METADATA_KEY]["truncated"] == True`, and the tokens are charged.
    """
    llm_utils.validate_message_history(messages)
    litellm_messages = llm_utils.to_litellm_messages(messages)
    tools_schema = [t.openai_schema for t in tools] if tools else None

    kwargs = dict(llm_args)
    if kwargs.get("num_retries") is None:
        kwargs["num_retries"] = llm_utils.DEFAULT_MAX_RETRIES
    reservation: Optional[BudgetReservation] = None
    max_tokens_sent: Optional[int] = None
    allowance = budget.allowance(per_call_cap)
    if budget.ledger is not None:
        # R7: below a_min no call is attempted (a 4-token call can only be cut).
        if allowance is None or allowance <= 0 or budget.exhausted_before_call():
            raise BudgetExhausted(f"remaining allowance {budget.remaining} is below a_min {budget.config.min_call_allowance}")
        reservation = budget.ledger.reserve(allowance)
        max_tokens_sent = reservation.tokens
    elif allowance:
        max_tokens_sent = allowance
    if max_tokens_sent is not None:
        configured = kwargs.get("max_tokens")
        kwargs["max_tokens"] = min(int(configured), max_tokens_sent) if configured else max_tokens_sent

    t0 = time.perf_counter()
    try:
        response = llm_utils.completion(
            model=model,
            messages=litellm_messages,
            tools=tools_schema,
            tool_choice=(tool_choice if tool_choice is not None else "auto") if tools_schema else None,
            **kwargs,
        )
    except Exception as exc:
        if max_tokens_sent is not None and _is_reasoning_only_cutoff(exc):
            # OpenAI Responses route (litellm bridge): when thinking alone fills
            # max_output_tokens the bridge raises instead of returning a message.
            # The provider stopped exactly at the cap, so the spend is the cap:
            # charge it and return an empty truncated reply (R6), never uncharged.
            return _reasoning_only_cutoff_reply(
                model, call_name, component, budget, reservation, max_tokens_sent, time.perf_counter() - t0, exc
            )
        # No response arrived, so nothing was generated; release and re-raise.
        if reservation is not None:
            budget.ledger.release(reservation)
        raise
    seconds = time.perf_counter() - t0

    # Charge the ledger BEFORE anything can fail (closes the metering hole).
    prompt_tokens, completion_tokens, cached_tokens, reasoning_tokens = _usage_fields(response)
    if reservation is not None:
        budget.ledger.commit(reservation, completion_tokens)
    cost = float(llm_utils.get_response_cost(response) or 0.0)

    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    content = getattr(choice.message, "content", None)
    tool_calls, parse_error = _parse_tool_calls(choice)
    truncated = finish_reason == "length" or parse_error is not None
    if truncated:
        tool_calls = None  # a truncated tool call is never executed (R6)

    record = CallRecord(
        component=component,
        call_name=call_name,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
        max_tokens_sent=max_tokens_sent,
        finish_reason=finish_reason,
        truncated=truncated,
        cost=cost,
        seconds=seconds,
    )
    budget.calls.append(record)

    raw = response.to_dict() if hasattr(response, "to_dict") else {}
    raw[CALL_METADATA_KEY] = {**record.to_dict(), "parse_error": parse_error}
    raw[BUDGET_METADATA_KEY] = {**budget.snapshot(), "component": component}
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
    }
    return AssistantMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        cost=cost,
        usage=usage,
        raw_data=raw,
        generation_time_seconds=seconds,
    )


# ---------------------------------------------------------------------------
# Helpers shared by the agent classes
# ---------------------------------------------------------------------------


def call_is_truncated(message: AssistantMessage) -> bool:
    return bool(((message.raw_data or {}).get(CALL_METADATA_KEY) or {}).get("truncated"))


def exhaustion_message(config: BudgetConfig, budget: EpisodeBudget, extra: Optional[dict] = None) -> AssistantMessage:
    """The fixed customer-facing stop message, labelled for the taxonomy (R7)."""
    raw = {
        TERMINATION_KEY: TERMINATION_EXHAUSTED,
        "synthetic_budget_exhaustion": True,
        BUDGET_METADATA_KEY: {**budget.snapshot(), "exhausted": True},
    }
    if extra:
        raw.update(extra)
    return AssistantMessage.text(
        config.exhausted_message,
        usage={"prompt_tokens": 0, "completion_tokens": 0},
        cost=0.0,
        raw_data=raw,
    )


def is_exhaustion_message(message: AssistantMessage) -> bool:
    return (message.raw_data or {}).get(TERMINATION_KEY) == TERMINATION_EXHAUSTED


def wrapup_system_message() -> SystemMessage:
    return SystemMessage(role="system", content=load_wrapup_notice())


def strip_text_when_tool_call(message: AssistantMessage) -> Optional[str]:
    """tau2 rejects a turn with both text and tool calls; keep the text in metadata."""
    if message.tool_calls and message.content:
        stray = message.content
        message.content = None
        return stray
    return None


def sum_usage(messages: list[AssistantMessage]) -> dict[str, Any]:
    out = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0}
    for m in messages:
        u = m.usage or {}
        for k in out:
            v = u.get(k)
            if v:
                out[k] += int(v)
    return out


def usage_for_analyzers(usage: dict[str, Any]) -> dict[str, Any]:
    """Shape that analyze_run.py / calibrate_budget.py already read from raw_data['usage']."""
    return {
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["prompt_tokens"] + usage["completion_tokens"],
        "prompt_tokens_details": {"cached_tokens": usage["cached_tokens"]},
        "completion_tokens_details": {"reasoning_tokens": usage["reasoning_tokens"]},
    }
