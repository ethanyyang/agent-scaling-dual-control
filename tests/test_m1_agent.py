from __future__ import annotations

import json

from tau2.data_model.message import ToolMessage, UserMessage
from tau2.environment.tool import as_tool
from tau2.environment.toolkit import ToolType, is_tool

import budget_layer as bl
from conftest import FakeResponse
from m1_agent import INTERNAL, MAS_METADATA_KEY, M1Agent


@is_tool(ToolType.READ)
def read_record(record_id: str) -> str:
    """Read a record."""
    return record_id


@is_tool(ToolType.WRITE)
def update_record(record_id: str, value: str) -> str:
    """Update a record."""
    return record_id


TOOLS = [as_tool(read_record), as_tool(update_record)]


def plan(action, ask=None, facts=None):
    return FakeResponse(content=json.dumps({
        "task_ledger": {"facts": facts or [], "guesses": [], "plan": ["step"]},
        "progress_ledger": {"assignments": [], "advice": [], "stalled": False},
        "ask_advisor": ask,
        "action": action,
    }), completion=30)


def act(action):
    return FakeResponse(content=json.dumps({"action": action}), completion=20)


def advisor(text="rule X applies"):
    return FakeResponse(content=json.dumps({"finding": text, "recommendation": "verify Y", "policy_basis": ["line"]}), completion=25)


def db_tool(name, args):
    return FakeResponse(tool_calls=[(name, args)], completion=15)


def db_report(result="found it", records=None):
    return FakeResponse(content=json.dumps({"result": result, "records": records or {}, "deviation": None}), completion=12)


def make_agent(limit=5000, cap=2000, w=300, a_min=20, k=4):
    cfg = bl.BudgetConfig(limit=limit, per_call_cap=cap, wrapup_threshold=w, min_call_allowance=a_min)
    return M1Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={"temperature": 0.0}, budget_config=cfg, read_call_limit=k)


def roles_of(request):
    return [m["role"] for m in request["messages"]]


def test_plan_to_message_costs_one_call(provider):
    p = provider.script([plan({"type": "message", "content": "Hi, how can I help?"})])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hello"), state)
    assert reply.content == "Hi, how can I help?" and reply.tool_calls is None
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert meta["llm_calls"] == 1 and meta["components"][0]["component"] == "orchestrator"
    assert p.requests[0]["tools"] is None  # orchestrator never gets tools
    assert "orchestrator of a small support team" in p.requests[0]["messages"][0]["content"]
    assert reply.usage["completion_tokens"] == 30
    assert reply.raw_data[bl.TERMINATION_KEY] == "normal"


def test_read_assignment_routes_tool_results_to_database_agent_then_reports(provider):
    p = provider.script([
        plan({"type": "read", "content": "find the customer's record"}),
        db_tool("read_record", {"record_id": "1"}),
        # next turn: tool result arrives -> db agent reports -> orchestrator plans -> message
        db_report("record 1 found", {"record_id": "1"}),
        plan({"type": "message", "content": "I found your record."}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    turn1, _ = agent.generate_next_message(UserMessage(role="user", content="look me up"), state)
    assert turn1.tool_calls[0].name == "read_record"
    assert p.requests[1]["tools"] is not None  # database agent has the tools
    assert state.assignment is not None and state.assignment.kind == "read" and state.assignment.calls_made == 1
    assert turn1.raw_data[MAS_METADATA_KEY]["llm_calls"] == 2

    turn2, _ = agent.generate_next_message(ToolMessage(id="call_1", role="tool", content="{...}", requestor="assistant"), state)
    assert turn2.content == "I found your record."
    meta = turn2.raw_data[MAS_METADATA_KEY]
    assert [c["component"] for c in meta["components"]] == ["database_agent", "orchestrator"]
    assert state.assignment is None and meta["assignments"][0]["report"]["result"] == "record 1 found"
    assert INTERNAL in p.requests[3]["messages"][-1]["content"] and "Report from the database agent" in p.requests[3]["messages"][-1]["content"]


def test_write_assignment_is_checked_against_the_order(provider):
    order = {"tool": "update_record", "arguments": {"record_id": "1", "value": "x"}}
    p = provider.script([
        plan({"type": "write", "content": order}),
        db_tool("update_record", {"record_id": "1", "value": "x"}),
        plan({"type": "message", "content": "Done."}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    turn1, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    a = turn1.raw_data[MAS_METADATA_KEY]["assignments"][0]
    assert a["kind"] == "write" and a["executed_as_issued"] is True and a["order_check"] == "exact"
    assert "Write assignment (exact single call)" in p.requests[1]["messages"][-1]["content"]
    turn2, _ = agent.generate_next_message(ToolMessage(id="call_1", role="tool", content="ok", requestor="assistant"), state)
    assert turn2.content == "Done."
    assert "Result of your write assignment" in p.requests[2]["messages"][-1]["content"]
    assert state.assignment is None


def test_write_misexecution_is_logged(provider):
    order = {"tool": "update_record", "arguments": {"record_id": "1", "value": "x"}}
    provider.script([plan({"type": "write", "content": order}), db_tool("update_record", {"record_id": "2", "value": "x"})])
    agent = make_agent()
    state = agent.get_init_state()
    turn1, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    a = turn1.raw_data[MAS_METADATA_KEY]["assignments"][0]
    assert a["executed_as_issued"] is False and a["order_check"] == "argument_mismatch"


def test_read_call_limit_forces_a_report(provider):
    p = provider.script([
        plan({"type": "read", "content": "find everything"}),
        db_tool("read_record", {"record_id": "1"}),
        db_report("that is all"),                       # forced: no tools on this call
        plan({"type": "message", "content": "Here is what I found."}),
    ])
    agent = make_agent(k=1)
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="look"), state)
    turn2, _ = agent.generate_next_message(ToolMessage(id="call_1", role="tool", content="r", requestor="assistant"), state)
    assert p.requests[2]["tools"] is None
    assert "reached the call limit" in p.requests[2]["messages"][-1]["content"]
    assert turn2.content == "Here is what I found."


def test_write_inside_read_assignment_is_blocked(provider):
    provider.script([
        plan({"type": "read", "content": "check the record"}),
        db_tool("update_record", {"record_id": "1", "value": "x"}),   # illegal in a read assignment
        plan({"type": "message", "content": "I checked."}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    turn1, _ = agent.generate_next_message(UserMessage(role="user", content="check"), state)
    assert turn1.tool_calls is None and turn1.content == "I checked."
    assert "db_write_in_read_assignment_blocked" in turn1.raw_data[MAS_METADATA_KEY]["events"]


def test_advisor_is_consulted_then_act_call_decides(provider):
    p = provider.script([
        plan({"type": "message", "content": "draft"}, ask="which rule applies?"),
        advisor(),
        act({"type": "message", "content": "Final answer after advice."}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="can I cancel?"), state)
    assert reply.content == "Final answer after advice."
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert [c["component"] for c in meta["components"]] == ["orchestrator", "advisor", "orchestrator"]
    assert meta["advisor"][0]["question"] == "which rule applies?" and meta["advisor"][0]["reply"]["finding"] == "rule X applies"
    assert "policy advisor on a small support team" in p.requests[1]["messages"][0]["content"]
    assert "Policy advisor reply" in p.requests[2]["messages"][-1]["content"]


def test_unparsable_plan_is_retried_once_then_forced_message(provider):
    provider.script([
        FakeResponse(content="not json", completion=5),
        FakeResponse(content="still not json", completion=5),
        FakeResponse(content="Let me help you with that.", completion=8),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.content == "Let me help you with that."
    assert "forced_message:plan_unparsable" in reply.raw_data[MAS_METADATA_KEY]["events"]


def test_wrapup_forces_a_customer_message(provider):
    p = provider.script([
        plan({"type": "message", "content": "first"}),                 # spends 30 -> remaining 70 < w
        plan({"type": "read", "content": "one more lookup"}),           # wrap-up active: read not allowed
        act({"type": "message", "content": "We are done for now."}),
    ])
    agent = make_agent(limit=100, cap=100, w=80, a_min=5)
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="and?"), state)
    assert reply.content == "We are done for now."
    assert state.budget.wrapup_triggered
    assert any(m["role"] == "system" and "allowance" in m["content"] for m in p.requests[1]["messages"])
    assert "Only a customer message is allowed now" in p.requests[2]["messages"][-1]["content"]


def test_exhaustion_stops_the_episode_with_the_label(provider):
    provider.script([plan({"type": "message", "content": "first"})])
    agent = make_agent(limit=40, cap=40, w=5, a_min=20)
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hi"), state)  # spends 30 -> remaining 10 < a_min
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="more"), state)
    assert reply.raw_data[bl.TERMINATION_KEY] == bl.TERMINATION_EXHAUSTED and agent.is_stop(reply)


def test_turn_usage_sums_every_component(provider):
    provider.script([
        plan({"type": "message", "content": "draft"}, ask="q"),
        FakeResponse(content=json.dumps({"finding": "f"}), completion=25, prompt=500, cached=200, reasoning=20),
        act({"type": "message", "content": "ok"}),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.usage["completion_tokens"] == 30 + 25 + 20
    assert reply.raw_data["usage"]["completion_tokens_details"]["reasoning_tokens"] == 20
    assert reply.raw_data["usage"]["prompt_tokens_details"]["cached_tokens"] == 200
    assert state.budget.ledger.snapshot().spent == 75


def test_truncated_plan_is_not_retried(provider):
    # Plan cut at the cap (finish_reason length): no second plan call; straight to the forced message.
    p = provider.script([
        FakeResponse(content='{"task_ledger": {"facts": ["cut', completion=100, finish_reason="length"),
        FakeResponse(content="Let me check that for you.", completion=8),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.content == "Let me check that for you."
    events = reply.raw_data[MAS_METADATA_KEY]["events"]
    assert "plan_truncated" in events and "forced_message:plan_unparsable" in events
    assert [r["messages"][-1]["content"].endswith("Reply only with the plan JSON.") for r in p.requests] == [True, False]
    assert len(p.requests) == 2


def test_orchestrator_is_told_its_allowance_and_costs(provider):
    p = provider.script([
        plan({"type": "message", "content": "first"}),
        plan({"type": "message", "content": "second"}),
    ])
    agent = make_agent(limit=5000, cap=2000)
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    first = p.requests[0]["messages"][-1]["content"]
    assert "Processing allowance: 5000 of 5000 output tokens left" in first and "capped at 2000" in first
    assert "Average cost" not in first  # nothing spent yet
    agent.generate_next_message(UserMessage(role="user", content="more"), state)
    second = p.requests[1]["messages"][-1]["content"]
    assert "Processing allowance: 4970 of 5000" in second and "plan 30" in second and "Last call: 30" in second


def test_uncapped_calibration_shows_no_allowance(provider):
    p = provider.script([plan({"type": "message", "content": "first"})])
    agent = M1Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={}, budget_config=bl.BudgetConfig.uncapped())
    state = agent.get_init_state()
    agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert "Processing allowance" not in p.requests[0]["messages"][-1]["content"]


def test_orchestrator_cap_multiplier_applies_to_orchestrator_and_advisor_only(provider):
    p = provider.script([
        plan({"type": "read", "content": "look up the record"}, ask="which rule?"),
        advisor(),
        act({"type": "read", "content": "look up the record"}),
        db_tool("read_record", {"record_id": "1"}),
    ])
    cfg = bl.BudgetConfig(limit=50000, per_call_cap=1000, wrapup_threshold=300, min_call_allowance=20)
    agent = M1Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={}, budget_config=cfg, orchestrator_cap_mult=4)
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.tool_calls[0].name == "read_record"
    assert [r["max_tokens"] for r in p.requests] == [4000, 4000, 4000, 1000]  # plan, advisor, act, db read
    assert reply.raw_data[MAS_METADATA_KEY]["orchestrator_cap"] == 4000


def test_forced_message_never_sends_json_or_a_cut_reply(provider):
    # cut plan -> forced message call also returns cut JSON -> fixed holding line, never the JSON
    provider.script([
        FakeResponse(content='{"task_ledger": {"facts": ["cut', completion=100, finish_reason="length"),
        FakeResponse(content='{"task_ledger": {"facts": ["cut again', completion=100, finish_reason="length"),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert not reply.content.startswith("{") and "bear with me" in reply.content
    events = reply.raw_data[MAS_METADATA_KEY]["events"]
    assert "forced_message:json_reply_discarded" in events and "forced_message:fallback_text" in events


def test_forced_message_uses_a_message_action_if_the_model_replies_in_json(provider):
    p = provider.script([
        FakeResponse(content="not json", completion=5),
        FakeResponse(content="still not json", completion=5),
        FakeResponse(content=json.dumps({"action": {"type": "message", "content": "Here is the answer."}}), completion=8),
    ])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.content == "Here is the answer."
    assert "FOR THIS REPLY ONLY" in p.requests[2]["messages"][0]["content"]
    assert "forced_message:json_reply_used_action" in reply.raw_data[MAS_METADATA_KEY]["events"]


def test_uncapped_arm_drops_only_the_allowance_paragraph():
    import m1_agent as ma
    from budget_layer import load_role_block
    full = load_role_block("m1_orchestrator")
    stripped = ma.strip_allowance_paragraph(full)
    assert "processing allowance" in full and "processing allowance" not in stripped
    assert len(full.split("\n\n")) - len(stripped.split("\n\n")) == 1
    capped = bl.BudgetConfig(limit=5000, per_call_cap=2000, wrapup_threshold=300, min_call_allowance=20)
    uncapped = bl.BudgetConfig.uncapped_with_guard(2000, 900, 50)
    def orch_prompt(cfg):
        agent = ma.M1Agent(tools=[], domain_policy="POLICY", llm="fake/agent", llm_args={}, budget_config=cfg)
        return agent.orchestrator_prompt
    assert "processing allowance" in orch_prompt(capped)
    assert "processing allowance" not in orch_prompt(uncapped)


# --- G1 write-order fix A1 (CHANGELOG 2026-10-12): the orchestrator sees the tool definitions -------------

def make_a1_agent(limit=5000, cap=2000, w=300, a_min=20, k=4):
    cfg = bl.BudgetConfig(limit=limit, per_call_cap=cap, wrapup_threshold=w, min_call_allowance=a_min)
    return M1Agent(tools=TOOLS, domain_policy="POLICY", llm="m", llm_args={"temperature": 0.0}, budget_config=cfg,
                   read_call_limit=k, orchestrator_tool_definitions=True)


def tool_names(request):
    return sorted(t["function"]["name"] for t in (request["tools"] or []))


def test_as_built_orchestrator_gets_no_tools_and_no_tool_choice(provider):
    p = provider.script([plan({"type": "message", "content": "Hi."})])
    agent = make_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hello"), state)
    assert p.requests[0]["tools"] is None and p.requests[0]["tool_choice"] is None
    assert reply.raw_data[MAS_METADATA_KEY]["orchestrator_tool_definitions"] is False


def test_a1_orchestrator_sees_tool_definitions_and_cannot_call_them(provider):
    order = {"tool": "update_record", "arguments": {"record_id": "1", "value": "x"}}
    p = provider.script([
        plan({"type": "write", "content": order}, ask="may I update?"),
        advisor(),
        act({"type": "write", "content": order}),
        db_tool("update_record", {"record_id": "1", "value": "x"}),
    ])
    agent = make_a1_agent()
    state = agent.get_init_state()
    turn, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    plan_req, adv_req, act_req, db_req = p.requests
    for r in (plan_req, act_req):  # orchestrator: the same definitions the database agent has, tool_choice "none"
        assert tool_names(r) == ["read_record", "update_record"] and r["tool_choice"] == "none"
    assert adv_req["tools"] is None  # the advisor is unchanged
    assert tool_names(db_req) == ["read_record", "update_record"] and db_req["tool_choice"] == "auto"
    a = turn.raw_data[MAS_METADATA_KEY]["assignments"][0]
    assert a["executed_as_issued"] is True and a["order_check"] == "exact"
    assert turn.tool_calls[0].name == "update_record"  # the database agent's call is the turn
    assert turn.raw_data[MAS_METADATA_KEY]["orchestrator_tool_definitions"] is True


def test_a1_tool_call_from_orchestrator_is_charged_dropped_and_the_plan_retried(provider):
    p = provider.script([
        db_tool("update_record", {"record_id": "1", "value": "x"}),   # provider ignored tool_choice "none"
        plan({"type": "message", "content": "Let me check that for you."}),
    ])
    agent = make_a1_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="change it"), state)
    assert reply.content == "Let me check that for you." and reply.tool_calls is None
    meta = reply.raw_data[MAS_METADATA_KEY]
    assert "orchestrator_returned_tool_call:m1_plan" in meta["events"]
    assert meta["llm_calls"] == 2 and reply.raw_data[bl.BUDGET_METADATA_KEY]["spent"] == 15 + 30  # both calls charged
    assert all(r["tool_choice"] == "none" for r in p.requests)


def test_a1_forced_message_never_executes_a_tool_call(provider):
    provider.script([
        FakeResponse(content="not json", completion=5),
        FakeResponse(content="still not json", completion=5),
        db_tool("update_record", {"record_id": "1", "value": "x"}),   # forced-message call returns a tool call
    ])
    agent = make_a1_agent()
    state = agent.get_init_state()
    reply, _ = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    assert reply.tool_calls is None and "bear with me" in reply.content
    events = reply.raw_data[MAS_METADATA_KEY]["events"]
    assert "orchestrator_returned_tool_call:m1_forced_message" in events and "forced_message:fallback_text" in events
