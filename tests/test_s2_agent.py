from __future__ import annotations

import json

from tau2.data_model.message import ToolMessage, UserMessage
from tau2.environment.tool import as_tool
from tau2.environment.toolkit import ToolType, is_tool

import budget_layer as bl
from conftest import FakeResponse
from m1_agent import MAS_METADATA_KEY
from s2_agent import ALLOWANCE_PARAGRAPH_START, S2Agent, draft_of, review_outcome, strip_s2_allowance_paragraph


@is_tool(ToolType.READ)
def read_record(record_id: str) -> str:
    """Read a record."""
    return record_id


@is_tool(ToolType.WRITE)
def update_record(record_id: str, value: str) -> str:
    """Update a record."""
    return record_id


TOOLS = [as_tool(read_record), as_tool(update_record)]
S2_MARK = "You work alone. You handle each turn in two steps"


def plan(draft, facts=None, completion=40):
    return FakeResponse(content=json.dumps({
        "task_ledger": {"facts": facts or [], "guesses": [], "plan": ["step"]},
        "progress_ledger": {"last_step": "", "result": "", "got_what_was_needed": True, "stalled": False},
        "policy_check": {"rules": ["quoted line"], "requires": "verify X"},
        "draft": draft,
    }), completion=completion)


def tool(name, args, completion=15):
    return FakeResponse(tool_calls=[(name, args)], completion=completion)


def text(t, completion=12):
    return FakeResponse(content=t, completion=completion)


def make_agent(limit=5000, cap=2000, w=300, a_min=20):
    cfg = bl.BudgetConfig(limit=limit, per_call_cap=cap, wrapup_threshold=w, min_call_allowance=a_min)
    return S2Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={"temperature": 0.0}, budget_config=cfg)


def last_user_text(request):
    return request["messages"][-1]["content"]


def test_role_block_and_parser_agree_and_prompt_is_base_plus_block():
    agent = make_agent()
    block = bl.load_role_block("s2_single_agent")
    assert agent.system_prompt == bl.render_base_prompt("POLICY") + "\n\n" + block
    for key in ('"task_ledger"', '"progress_ledger"', '"policy_check"', '"draft"', "message|tool_call", '\\"tool\\"', '\\"arguments\\"'):
        assert key in block
    assert "DRAFT v1" not in block  # the HTML header never reaches the model


def test_uncapped_drops_only_the_allowance_paragraph():
    block = bl.load_role_block("s2_single_agent")
    stripped = strip_s2_allowance_paragraph(block)
    assert ALLOWANCE_PARAGRAPH_START in block and ALLOWANCE_PARAGRAPH_START not in stripped
    assert len(block.split("\n\n")) - len(stripped.split("\n\n")) == 1
    cfg = bl.BudgetConfig.uncapped_with_guard(b_1x=2000, per_call_p95=900, per_call_median=50)
    agent = S2Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={}, budget_config=cfg)
    assert agent.system_prompt == bl.render_base_prompt("POLICY") + "\n\n" + stripped


def test_turn_is_plan_without_tools_then_act_with_tools_in_one_context(provider):
    p = provider.script([
        plan({"type": "tool_call", "content": {"tool": "read_record", "arguments": {"record_id": "1"}}}),
        tool("read_record", {"record_id": "1"}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="look me up"), state)
    assert reply.tool_calls[0].name == "read_record" and reply.content is None
    plan_req, act_req = p.requests
    # the plan call sees the same tools but may not call them; the act call may
    assert plan_req["tools"] == act_req["tools"] and plan_req["tool_choice"] == "none" and act_req["tool_choice"] == "auto"
    # one context: both calls carry the same system prompt and the same conversation before the instruction
    assert plan_req["messages"][0] == act_req["messages"][0]
    assert S2_MARK in plan_req["messages"][0]["content"]
    assert plan_req["messages"][1:-1] == act_req["messages"][1:-1]
    assert plan_req["messages"][1]["content"] == "look me up"
    assert "Plan now (step 1)" in last_user_text(plan_req) and "Processing allowance" in last_user_text(plan_req)
    assert "Review and act now (step 2)" in last_user_text(act_req) and '"policy_check"' in last_user_text(act_req)
    assert "policy_check_missing" not in reply.raw_data[MAS_METADATA_KEY]["events"]
    assert all(r["max_tokens"] <= 2000 for r in p.requests)
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert meta["architecture"] == "S2" and meta["llm_calls"] == 2
    assert [c["call_name"] for c in meta["components"]] == ["s2_plan", "s2_act"]
    assert meta["review"]["outcome"] == "kept"
    assert reply.usage["completion_tokens"] == 55
    assert reply.raw_data[bl.BUDGET_METADATA_KEY]["spent"] == 55
    assert reply.raw_data[bl.TERMINATION_KEY] == bl.TERMINATION_NORMAL
    assert state.task_ledger["plan"] == ["step"]


def test_tool_results_come_back_natively_and_review_can_revise(provider):
    p = provider.script([
        plan({"type": "tool_call", "content": {"tool": "read_record", "arguments": {"record_id": "1"}}}),
        tool("read_record", {"record_id": "1"}),
        plan({"type": "tool_call", "content": {"tool": "update_record", "arguments": {"record_id": "1", "value": "x"}}}),
        text("Before I change anything, can you confirm the new value?"),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    turn1, _ = agent.generate_next_message(UserMessage(role="user", content="change my record"), state)
    tc = turn1.tool_calls[0]
    result = ToolMessage(id=tc.id, role="tool", content="record 1: value y", requestor="assistant")
    turn2, _ = agent.generate_next_message(result, state)
    assert turn2.content.startswith("Before I change") and not turn2.tool_calls
    assert turn2.raw_data[MAS_METADATA_KEY]["review"]["outcome"] == "revised_to_message"
    # the tool result sits in the native history of both calls of turn 2
    for req in p.requests[2:]:
        assert any(m["role"] == "tool" and m["content"] == "record 1: value y" for m in req["messages"])


def test_unparsable_plan_is_retried_once_then_the_agent_acts_without_a_plan(provider):
    p = provider.script([text("not json"), text("still not json"), text("Could you give me your record id?")])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.content == "Could you give me your record id?"
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert meta["events"].count("plan_parse_failed") == 1 and meta["llm_calls"] == 3
    assert meta["review"]["outcome"] == "no_draft"
    assert "No plan is available" in last_user_text(p.requests[2]) and p.requests[2]["tools"]


def test_truncated_plan_is_not_retried(provider):
    p = provider.script([FakeResponse(content='{"task_ledger": {', completion=2000, finish_reason="length"), text("Hello, how can I help?")])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "plan_truncated" in meta["events"] and meta["llm_calls"] == 2
    assert reply.content == "Hello, how can I help?"


def test_truncated_act_is_never_executed_and_a_closing_message_follows(provider):
    p = provider.script([
        plan({"type": "tool_call", "content": {"tool": "update_record", "arguments": {"record_id": "1", "value": "x"}}}),
        FakeResponse(tool_calls=[("update_record", {"record_id": "1", "value": "x"})], completion=2000, finish_reason="length"),
        text("I could not complete the change; here is where things stand."),
    ])
    agent = make_agent(limit=20000)
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    assert not reply.tool_calls and reply.content.startswith("I could not complete")
    assert p.requests[2]["tools"] is None
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "act_truncated" in meta["events"] and meta["review"]["outcome"] == "forced_closing"


def test_wrapup_turn_is_one_call_without_tools_and_without_a_plan(provider):
    p = provider.script([text("Here is a summary of what was done.")])
    agent = make_agent(limit=1000, cap=500, w=300, a_min=20)
    state = agent.get_init_state()
    state.budget.ledger.commit(state.budget.ledger.reserve(800), 800)  # 200 left, below w = 300
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="anything else?"), state)
    assert len(p.requests) == 1 and p.requests[0]["tools"] is None
    assert "Only a message to the customer is allowed now" in last_user_text(p.requests[0])
    assert "processing allowance nearly used" in p.requests[0]["messages"][0]["content"]
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert meta["wrapup_triggered"] and meta["review"]["outcome"] == "wrapup_turn" and not meta["plans"]


def test_exhaustion_before_the_first_call_ends_the_episode(provider):
    p = provider.script([])
    agent = make_agent(limit=10, cap=10, w=1, a_min=20)
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert bl.is_exhaustion_message(reply) and S2Agent.is_stop(reply)
    assert not p.requests


def test_draft_and_review_outcome_helpers():
    assert draft_of(None) is None and draft_of({"draft": "x"}) is None
    assert draft_of({"draft": {"type": "message", "content": "hi"}}) == {"type": "message", "text": "hi"}
    d = draft_of({"draft": {"type": "tool_call", "content": json.dumps({"tool": "read_record", "arguments": {"record_id": 1}})}})
    assert d == {"type": "tool_call", "tool": "read_record", "arguments": {"record_id": 1}}
    from tau2.data_model.message import AssistantMessage, ToolCall

    call = AssistantMessage(role="assistant", tool_calls=[ToolCall(id="1", name="read_record", arguments={"record_id": "1"})])
    assert review_outcome(d, call) == "kept"  # "1" vs 1 after type normalisation
    other = AssistantMessage(role="assistant", tool_calls=[ToolCall(id="1", name="read_record", arguments={"record_id": "2"})])
    assert review_outcome(d, other) == "revised_arguments"
    assert review_outcome({"type": "message", "text": "a"}, AssistantMessage.text("b")) == "reworded"
    assert review_outcome({"type": "message", "text": "a"}, call) == "revised_to_tool_call"
    assert review_outcome(None, call) == "no_draft"


def test_json_act_reply_never_reaches_the_customer(provider):
    leak = json.dumps({"plan": ["Inform the customer", "Offer options"]})
    p = provider.script([
        plan({"type": "message", "content": "Your line is over its limit."}),
        text(leak),
        text("Your line is over its data limit; would you like to add data or change plans?"),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="my data is slow"), state)
    assert not reply.content.startswith("{") and reply.content.startswith("Your line is over")
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "act_json_reply" in meta["events"] and "act_json_retry" in meta["events"]
    assert "forced_closing" not in meta["events"]
    # the retry is an ordinary act call: same tools, no wrap-up notice, a reminder appended
    assert p.requests[2]["tools"] and "processing allowance nearly used" not in p.requests[2]["messages"][0]["content"]
    assert "Your previous reply was JSON" in p.requests[2]["messages"][-1]["content"]
    assert meta["review"]["outcome"] == "reworded"


def test_json_act_reply_retry_can_make_the_tool_call(provider):
    provider.script([
        plan({"type": "tool_call", "content": {"tool": "read_record", "arguments": {"record_id": "1"}}}),
        text('{"plan": ["read the record"]}'),
        tool("read_record", {"record_id": "1"}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="look me up"), state)
    assert reply.tool_calls[0].name == "read_record"
    assert reply.raw_data[MAS_METADATA_KEY]["review"]["outcome"] == "kept"


def test_json_act_reply_with_a_message_draft_uses_the_message(provider):
    wrapped = json.dumps({"draft": {"type": "message", "content": "Could you confirm your phone number?"}})
    provider.script([plan({"type": "message", "content": "Could you confirm your phone number?"}), text(wrapped)])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.content == "Could you confirm your phone number?"
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "act_json_used_message" in meta["events"] and meta["review"]["outcome"] == "kept"


def test_second_json_reply_becomes_the_holding_line(provider):
    from m1_agent import FALLBACK_HOLDING_MESSAGE

    provider.script([plan({"type": "message", "content": "x"}), text('{"plan": []}'), text('{"still": "json"}')])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.content == FALLBACK_HOLDING_MESSAGE
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "fallback_text" in meta["events"] and meta["review"]["outcome"] == "fallback_text"


def test_openai_namespace_prefix_on_drafted_tool_names_is_ignored():
    d = draft_of({"draft": {"type": "tool_call", "content": {"tool": "functions.read_record", "arguments": {"record_id": "1"}}}})
    assert d["tool"] == "read_record"


def test_plan_that_returns_a_tool_call_is_never_executed(provider):
    p = provider.script([
        tool("update_record", {"record_id": "1", "value": "x"}),  # provider ignored tool_choice "none"
        plan({"type": "message", "content": "Which record?"}),
        text("Which record should I change?"),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    assert reply.content == "Which record should I change?" and not reply.tool_calls
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "plan_returned_tool_call" in meta["events"] and meta["llm_calls"] == 3


def test_no_plan_retry_after_the_wrapup_threshold_is_crossed(provider):
    # w = 300 of 1000: the first (unparsable) plan spends 750, so the retry is skipped and the act call closes
    p = provider.script([text("not json", completion=750), text("To sum up, here is where things stand.")])
    agent = make_agent(limit=1000, cap=900, w=300, a_min=20)
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert len(p.requests) == 2 and p.requests[1]["tools"] is None
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert meta["wrapup_triggered"] and meta["review"]["outcome"] == "wrapup_after_plan"
    assert "processing allowance nearly used" in p.requests[1]["messages"][0]["content"]


def test_flat_draft_and_missing_policy_check_are_handled(provider):
    provider.script([
        FakeResponse(content=json.dumps({
            "task_ledger": {"facts": [], "guesses": [], "plan": []},
            "progress_ledger": {},
            "draft": {"type": "tool_call", "tool": "read_record", "arguments": {"record_id": "1"}},
        }), completion=30),
        tool("read_record", {"record_id": "1"}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="look me up"), state)
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert meta["review"]["outcome"] == "kept" and "policy_check_missing" in meta["events"]
