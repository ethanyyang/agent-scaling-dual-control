from __future__ import annotations

import pytest
from tau2.data_model.message import SystemMessage, UserMessage
from tau2.environment.tool import as_tool
from tau2.environment.toolkit import ToolType, is_tool

import budget_layer as bl
from conftest import FakeResponse
from s1_agent import BudgetedS1Agent


@is_tool(ToolType.READ)
def read_record(record_id: str) -> str:
    """Read a record."""
    return record_id


@is_tool(ToolType.WRITE)
def update_record(record_id: str) -> str:
    """Update a record."""
    return record_id


TOOLS = [as_tool(read_record), as_tool(update_record)]
MSGS = [SystemMessage(role="system", content="sys"), UserMessage(role="user", content="hi")]


def cfg(limit=1000, cap=300, w=200, a_min=50):
    return bl.BudgetConfig(limit=limit, per_call_cap=cap, wrapup_threshold=w, min_call_allowance=a_min)


def test_base_prompt_matches_tau2_default_and_hash_check_bites():
    from tau2.agent.llm_agent import AGENT_INSTRUCTION, SYSTEM_PROMPT

    rendered = bl.render_base_prompt("POLICY")
    assert rendered == SYSTEM_PROMPT.format(agent_instruction=AGENT_INSTRUCTION, domain_policy="POLICY")
    with pytest.raises(ValueError):
        bl.load_base_prompt_template(expected_sha256="0000000000000000")


def test_per_call_cap_bounds_max_tokens_and_ledger_is_charged(provider):
    p = provider.script([FakeResponse(content="ok", completion=120)])
    b = bl.EpisodeBudget(cfg(limit=1000, cap=300))
    reply = bl.metered_generate(model="m", messages=MSGS, tools=None, llm_args={}, call_name="t", component="agent", budget=b)
    assert p.requests[0]["max_tokens"] == 300
    assert b.ledger.snapshot().spent == 120
    assert reply.usage["completion_tokens"] == 120
    assert reply.raw_data[bl.BUDGET_METADATA_KEY]["remaining"] == 880


def test_remaining_below_cap_shrinks_the_allowance(provider):
    p = provider.script([FakeResponse(content="ok", completion=10)])
    b = bl.EpisodeBudget(cfg(limit=1000, cap=300))
    b.ledger.commit(b.ledger.reserve(900), 900)
    bl.metered_generate(model="m", messages=MSGS, tools=None, llm_args={}, call_name="t", component="agent", budget=b)
    assert p.requests[0]["max_tokens"] == 100


def test_truncated_tool_call_is_charged_and_never_executed(provider):
    # arguments cut mid-JSON, finish_reason length: the metering hole in the branch reference
    provider.script([FakeResponse(tool_calls=[("read_record", None)], raw_arguments='{"record_id": "1', completion=77, finish_reason="length")])
    b = bl.EpisodeBudget(cfg())
    reply = bl.metered_generate(model="m", messages=MSGS, tools=TOOLS, llm_args={}, call_name="t", component="agent", budget=b)
    assert reply.tool_calls is None
    assert bl.call_is_truncated(reply)
    assert b.ledger.snapshot().spent == 77
    assert b.snapshot()["truncated_calls"] == 1


def test_provider_exception_releases_reservation(provider):
    provider.script([RuntimeError("boom")])
    b = bl.EpisodeBudget(cfg())
    with pytest.raises(RuntimeError):
        bl.metered_generate(model="m", messages=MSGS, tools=None, llm_args={}, call_name="t", component="agent", budget=b)
    s = b.ledger.snapshot()
    assert s.reserved == 0 and s.spent == 0


def test_usage_details_are_kept(provider):
    provider.script([FakeResponse(content="ok", completion=50, prompt=400, cached=300, reasoning=40)])
    b = bl.EpisodeBudget(bl.BudgetConfig.uncapped())
    reply = bl.metered_generate(model="m", messages=MSGS, tools=None, llm_args={}, call_name="t", component="agent", budget=b)
    assert reply.usage == {"prompt_tokens": 400, "completion_tokens": 50, "cached_tokens": 300, "reasoning_tokens": 40}
    assert "max_tokens" not in provider.current().requests[0]  # uncapped calibration sends no cap


def make_s1(budget_config):
    return BudgetedS1Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={"temperature": 0.0}, budget_config=budget_config)


def test_s1_wrapup_notice_injected_once_then_tools_withheld(provider):
    p = provider.script([FakeResponse(content="first", completion=850), FakeResponse(content="closing", completion=10), FakeResponse(content="bye", completion=5)])
    agent = make_s1(cfg(limit=1000, cap=900, w=200, a_min=10))
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hello"), state)
    assert not state.budget.wrapup_triggered
    agent.generate_next_message(UserMessage(role="user", content="more"), state)  # remaining 150 < w
    assert state.budget.wrapup_triggered
    assert any(m["role"] == "system" and "allowance" in m["content"] for m in p.requests[1]["messages"])
    assert p.requests[1]["tools"] is None  # R5: only a customer-facing turn after wrap-up
    agent.generate_next_message(UserMessage(role="user", content="again"), state)
    notices = [m for m in p.requests[2]["messages"] if m["role"] == "system" and "allowance" in m["content"]]
    assert len(notices) == 1


def test_s1_exhaustion_message_is_labelled_and_stops(provider):
    provider.script([FakeResponse(content="first", completion=995)])
    agent = make_s1(cfg(limit=1000, cap=1000, w=50, a_min=20))
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hello"), state)
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="more"), state)  # remaining 5 < a_min
    assert reply.raw_data[bl.TERMINATION_KEY] == bl.TERMINATION_EXHAUSTED
    assert agent.is_stop(reply)
    assert reply.content == agent.budget_config.exhausted_message


def test_s1_truncated_tool_call_becomes_a_closing_message(provider):
    provider.script([
        FakeResponse(tool_calls=[("update_record", None)], raw_arguments='{"record_id": "1', completion=30, finish_reason="length"),
        FakeResponse(content="I could not complete that; here is where we stand.", completion=20),
    ])
    agent = make_s1(cfg(limit=1000, cap=300, w=100, a_min=10))
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    assert reply.tool_calls is None and "could not" in reply.content
    assert state.budget.ledger.snapshot().spent == 50


def test_capped_s1_is_told_its_allowance_uncapped_is_not(provider):
    p = provider.script([FakeResponse(content="a", completion=40), FakeResponse(content="b", completion=10)])
    agent = make_s1(cfg(limit=1000, cap=300, w=100, a_min=10))
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hello"), state)
    sys0 = p.requests[0]["messages"][0]
    assert sys0["role"] == "system" and "Processing allowance: 1000 of 1000" in sys0["content"]
    assert sum(m["role"] == "system" for m in p.requests[0]["messages"]) == 1
    agent.generate_next_message(UserMessage(role="user", content="more"), state)
    assert "Processing allowance: 960 of 1000" in p.requests[1]["messages"][0]["content"] and "reply 40" in p.requests[1]["messages"][0]["content"]

    p = provider.script([FakeResponse(content="a", completion=40)])
    agent = make_s1(bl.BudgetConfig.uncapped())
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hello"), state)
    assert "Processing allowance" not in p.requests[0]["messages"][0]["content"]


def test_reasoning_only_cutoff_on_responses_route_is_charged_at_the_cap(provider):
    # litellm's chat->Responses bridge raises when thinking alone fills max_output_tokens
    provider.script([RuntimeError("OpenAIException - gpt-5.4-nano-2026-03-17 unable to complete request: max_output_tokens")])
    b = bl.EpisodeBudget(cfg(limit=1000, cap=300))
    reply = bl.metered_generate(model="m", messages=MSGS, tools=TOOLS, llm_args={}, call_name="t", component="agent", budget=b)
    assert reply.tool_calls is None and reply.content is None and bl.call_is_truncated(reply)
    assert b.ledger.snapshot().spent == 300 and b.ledger.snapshot().reserved == 0
    assert b.snapshot()["truncated_calls"] == 1
    assert reply.raw_data[bl.CALL_METADATA_KEY]["usage_source"].startswith("cap")


def test_other_provider_errors_still_release_and_raise(provider):
    provider.script([RuntimeError("OpenAIException - rate limit")])
    b = bl.EpisodeBudget(cfg(limit=1000, cap=300))
    with pytest.raises(RuntimeError):
        bl.metered_generate(model="m", messages=MSGS, tools=None, llm_args={}, call_name="t", component="agent", budget=b)
    assert b.ledger.snapshot().spent == 0 and b.ledger.snapshot().reserved == 0


def test_cap_rule_b1x_sets_c_to_b1x_and_never_scales_with_the_multiplier():
    a = bl.BudgetConfig.from_calibration(7123, 1326, 352, multiplier=4.0, cap_rule="b1x")
    assert a.limit == 28492 and a.per_call_cap == 7123
    b = bl.BudgetConfig.from_calibration(7123, 1326, 352, multiplier=4.0)
    assert b.per_call_cap == 1326
    with pytest.raises(ValueError):
        bl.BudgetConfig.from_calibration(7123, 1326, 352, cap_rule="max")


def test_no_call_below_a_min(provider):
    p = provider.script([FakeResponse(content="x", completion=10)])
    b = bl.EpisodeBudget(cfg(limit=1000, cap=300, w=100, a_min=50))
    b.ledger.commit(b.ledger.reserve(960), 960)  # remaining 40 < a_min 50
    with pytest.raises(bl.BudgetExhausted):
        bl.metered_generate(model="m", messages=MSGS, tools=None, llm_args={}, call_name="t", component="agent", budget=b)
    assert p.requests == []  # nothing was sent to the provider


def test_uncapped_with_guard_keeps_cap_and_drops_ceiling():
    cfg = bl.BudgetConfig.uncapped_with_guard(6159, 1662, 309)
    assert (cfg.limit, cfg.per_call_cap, cfg.wrapup_threshold, cfg.min_call_allowance) == (None, 6159, None, 309)
    assert bl.BudgetConfig.uncapped_with_guard(6159, 1662, 309, cap_rule="p95").per_call_cap == 1662
    b = bl.EpisodeBudget(cfg)
    assert b.ledger is None and b.allowance() == 6159 and not b.exhausted_before_call() and not b.needs_wrapup()
    assert bl.budget_status_line(b) is None
