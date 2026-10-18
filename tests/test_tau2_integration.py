"""End-to-end: M1 and budgeted S1 inside tau2's real runner (mock domain, offline).

The provider is faked at `tau2.utils.llm_utils.completion`, so the user simulator,
the M1 components and the S1 agent all get canned replies, while tau2's
orchestrator, environment (tool execution), checkpointing and ACTION evaluation
run for real. This is the check that the agents plug into tau2 correctly: message
validation, tool routing, stop handling, and the metadata that reaches results.json.
"""
from __future__ import annotations

import json

import pytest
from tau2.data_model.simulation import TextRunConfig
from tau2.evaluator.evaluator import EvaluationType
from tau2.registry import registry
from tau2.runner.batch import run_tasks
from tau2.runner.helpers import get_tasks

import budget_layer as bl
from conftest import FakeResponse
from m1_agent import MAS_METADATA_KEY, make_m1_factory
from s1_agent import make_s1_factory
from s2_agent import make_s2_factory

ORDER = {"tool": "create_task", "arguments": {"user_id": "user_1", "title": "Important Meeting"}}
TASK_ID = "create_task_1"


class Router:
    """Routes each request by the system prompt: user simulator, orchestrator, database agent, S1."""

    def __init__(self):
        self.user_turns = 0
        self.requests = []

    def __call__(self, **kwargs):
        self.requests.append(kwargs)
        msgs = kwargs["messages"]
        system = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""
        last = (msgs[-1].get("content") or "") if msgs else ""
        if "orchestrator of a small support team" in system:
            if "Result of your write assignment" in last:
                return self._plan({"type": "message", "content": "Done: the task 'Important Meeting' has been created for user_1."})
            return self._plan({"type": "write", "content": ORDER})
        if "database agent on a small support team" in system:
            return FakeResponse(tool_calls=[("create_task", ORDER["arguments"])], completion=15)
        if "You work alone. You handle each turn in two steps" in system:  # S2 (checked before S1: same base prompt)
            done = any(m["role"] == "tool" for m in msgs)
            if "Plan now (step 1)" in last:
                draft = ({"type": "message", "content": "Done: the task 'Important Meeting' has been created for user_1."} if done
                         else {"type": "tool_call", "content": ORDER})
                return FakeResponse(content=json.dumps({
                    "task_ledger": {"facts": ["customer wants a task created"], "guesses": [], "plan": ["create it", "confirm"]},
                    "progress_ledger": {"last_step": "", "result": "", "got_what_was_needed": True, "stalled": False},
                    "policy_check": {"rules": ["quoted line"], "requires": "nothing unverified"},
                    "draft": draft,
                }), completion=40)
            if done:
                return FakeResponse(content="Done: the task 'Important Meeting' has been created for user_1.", completion=20)
            return FakeResponse(tool_calls=[("create_task", ORDER["arguments"])], completion=15)
        if "<policy>" in system:  # S1: the stock agent prompt
            if any(m["role"] == "tool" for m in msgs):
                return FakeResponse(content="Done: the task 'Important Meeting' has been created for user_1.", completion=20)
            return FakeResponse(tool_calls=[("create_task", ORDER["arguments"])], completion=15)
        # user simulator
        self.user_turns += 1
        if self.user_turns == 1:
            return FakeResponse(content="Hi, please create a task called 'Important Meeting' for user_1.", completion=12)
        return FakeResponse(content="Great, thanks! ###STOP###", completion=6)

    @staticmethod
    def _plan(action):
        return FakeResponse(content=json.dumps({
            "task_ledger": {"facts": ["customer wants a task created"], "guesses": [], "plan": ["create it", "confirm"]},
            "progress_ledger": {"assignments": [], "advice": [], "stalled": False},
            "ask_advisor": None,
            "action": action,
        }), completion=30)


@pytest.fixture
def router(monkeypatch):
    r = Router()
    monkeypatch.setattr(bl.llm_utils, "completion", r)
    monkeypatch.setattr(bl.llm_utils, "get_response_cost", lambda resp: 0.0)
    return r


def run_mock(tmp_path, agent_name, factory):
    if registry.get_agent_factory(agent_name) is None:
        registry.register_agent_factory(factory, agent_name)
    tasks = get_tasks("mock", task_ids=[TASK_ID])
    config = TextRunConfig(
        domain="mock", agent=agent_name, user="user_simulator",
        llm_agent="fake/agent", llm_args_agent={"temperature": 0.0},
        llm_user="fake/user", llm_args_user={},
        task_ids=[TASK_ID], num_trials=1, max_steps=30, max_errors=3, max_concurrency=1, seed=300,
        auto_resume=True, save_to=agent_name,
    )
    save_dir = tmp_path / agent_name
    save_dir.mkdir()
    results = run_tasks(config, tasks, save_path=save_dir / "results.json", save_dir=save_dir,
                        evaluation_type=EvaluationType.ACTION, console_display=False)
    return json.loads((save_dir / "results.json").read_text()), results


def test_m1_runs_a_mock_task_end_to_end(tmp_path, router):
    cfg = bl.BudgetConfig(limit=5000, per_call_cap=2000, wrapup_threshold=300, min_call_allowance=20)
    saved, _ = run_mock(tmp_path, "test_m1_mock", make_m1_factory(cfg, None, 4))
    sim = saved["simulations"][0]
    assert sim["termination_reason"] == "user_stop"
    assert sim["reward_info"]["reward"] == 1.0  # create_task executed with the ordered arguments

    agent_msgs = [m for m in sim["messages"] if m["role"] == "assistant"]
    tool_msgs = [m for m in sim["messages"] if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["requestor"] == "assistant"
    assert any(m.get("tool_calls") for m in agent_msgs) and agent_msgs[-1]["content"].startswith("Done:")

    # per-turn metadata survives serialisation, and analyzers' usage shape is present
    metered = [m for m in agent_msgs if (m.get("raw_data") or {}).get(MAS_METADATA_KEY)]
    assert metered, "M1 turns must carry transfer_testing_multi_agent metadata"
    write_turn = next(m for m in metered if m["raw_data"][MAS_METADATA_KEY]["assignments"])
    a = write_turn["raw_data"][MAS_METADATA_KEY]["assignments"][0]
    assert a["kind"] == "write" and a["executed_as_issued"] is True
    assert write_turn["raw_data"][bl.BUDGET_METADATA_KEY]["spent"] > 0
    assert write_turn["raw_data"]["usage"]["completion_tokens"] == write_turn["usage"]["completion_tokens"]
    assert all(m["raw_data"][bl.TERMINATION_KEY] == bl.TERMINATION_NORMAL for m in metered)

    # the orchestrator never saw tools; the database agent did
    orch = [r for r in router.requests if "orchestrator of a small support team" in r["messages"][0]["content"]]
    dba = [r for r in router.requests if "database agent on a small support team" in r["messages"][0]["content"]]
    assert orch and all(r["tools"] is None for r in orch)
    assert dba and all(r["tools"] and r["tool_choice"] == "auto" for r in dba)
    assert all(r["max_tokens"] <= 2000 for r in orch + dba)


def test_budgeted_s1_runs_a_mock_task_end_to_end(tmp_path, router):
    cfg = bl.BudgetConfig(limit=5000, per_call_cap=2000, wrapup_threshold=300, min_call_allowance=20)
    saved, _ = run_mock(tmp_path, "test_s1_mock", make_s1_factory(cfg, None))
    sim = saved["simulations"][0]
    assert sim["termination_reason"] == "user_stop" and sim["reward_info"]["reward"] == 1.0
    agent_msgs = [m for m in sim["messages"] if m["role"] == "assistant"]
    assert all((m.get("raw_data") or {}).get(bl.BUDGET_METADATA_KEY) for m in agent_msgs if m.get("usage"))
    s1 = [r for r in router.requests if "<policy>" in r["messages"][0]["content"]]
    assert s1 and all(r["max_tokens"] == 2000 for r in s1)
    assert all(r["tool_choice"] == "auto" for r in s1 if r["tools"])  # S1 unchanged by the tool_choice parameter


def test_s1_exhaustion_ends_the_episode_inside_tau2(tmp_path, router):
    # 1 token of budget: the first agent call is refused and the labelled stop message ends the run
    cfg = bl.BudgetConfig(limit=1, per_call_cap=1, wrapup_threshold=1, min_call_allowance=5)
    saved, _ = run_mock(tmp_path, "test_s1_exhausted", make_s1_factory(cfg, None))
    sim = saved["simulations"][0]
    agent_msgs = [m for m in sim["messages"] if m["role"] == "assistant"]
    assert agent_msgs[-1]["raw_data"][bl.TERMINATION_KEY] == bl.TERMINATION_EXHAUSTED
    assert sim["termination_reason"] == "agent_stop"
    assert sim["reward_info"]["reward"] == 0.0


def test_m1_uncapped_arm_runs_with_guard_only(tmp_path, router):
    # §8 addendum 2026-09-24: no episode ceiling, no wrap-up, no allowance line; per-call guard c kept.
    cfg = bl.BudgetConfig.uncapped_with_guard(b_1x=2000, per_call_p95=900, per_call_median=50)
    assert cfg.limit is None and cfg.wrapup_threshold is None and cfg.per_call_cap == 2000
    saved, _ = run_mock(tmp_path, "test_m1_uncapped", make_m1_factory(cfg, None, 4))
    sim = saved["simulations"][0]
    assert sim["termination_reason"] == "user_stop" and sim["reward_info"]["reward"] == 1.0
    agent_msgs = [m for m in sim["messages"] if m["role"] == "assistant"]
    metered = [m for m in agent_msgs if (m.get("raw_data") or {}).get(MAS_METADATA_KEY)]
    assert metered
    snap = metered[-1]["raw_data"][bl.BUDGET_METADATA_KEY]
    assert snap["limit"] is None and snap["remaining"] is None and snap["spent"] > 0
    assert all(m["raw_data"][bl.TERMINATION_KEY] == bl.TERMINATION_NORMAL for m in metered)
    orch = [r for r in router.requests if "orchestrator of a small support team" in r["messages"][0]["content"]]
    dba = [r for r in router.requests if "database agent on a small support team" in r["messages"][0]["content"]]
    # every team call carries the guard, and no call is shown a budget line
    assert orch and dba and all(r["max_tokens"] == 2000 for r in orch + dba)
    assert not any("allowance" in (msg.get("content") or "").lower() and "remaining" in (msg.get("content") or "").lower()
                   for r in orch for msg in r["messages"])


def test_s2_runs_a_mock_task_end_to_end(tmp_path, router):
    cfg = bl.BudgetConfig(limit=5000, per_call_cap=2000, wrapup_threshold=300, min_call_allowance=20)
    saved, _ = run_mock(tmp_path, "test_s2_mock", make_s2_factory(cfg, None))
    sim = saved["simulations"][0]
    assert sim["termination_reason"] == "user_stop"
    assert sim["reward_info"]["reward"] == 1.0  # create_task executed by S2's own native tool call
    agent_msgs = [m for m in sim["messages"] if m["role"] == "assistant"]
    assert any(m.get("tool_calls") for m in agent_msgs) and agent_msgs[-1]["content"].startswith("Done:")
    metered = [m for m in agent_msgs if (m.get("raw_data") or {}).get(MAS_METADATA_KEY)]
    assert metered and all(m["raw_data"][MAS_METADATA_KEY]["architecture"] == "S2" for m in metered)
    assert all(m["raw_data"][MAS_METADATA_KEY]["llm_calls"] == 2 for m in metered)
    assert all(m["raw_data"][MAS_METADATA_KEY]["review"]["outcome"] == "kept" for m in metered)
    assert all(m["raw_data"][bl.TERMINATION_KEY] == bl.TERMINATION_NORMAL for m in metered)
    assert metered[-1]["raw_data"][bl.BUDGET_METADATA_KEY]["spent"] == sum(m["usage"]["completion_tokens"] for m in metered)
    s2 = [r for r in router.requests if "You work alone. You handle each turn in two steps" in r["messages"][0]["content"]]
    plans = [r for r in s2 if "Plan now (step 1)" in r["messages"][-1]["content"]]
    acts = [r for r in s2 if "Review and act now (step 2)" in r["messages"][-1]["content"]]
    assert len(plans) == len(acts) == len(metered)
    assert all(r["tools"] and r["tool_choice"] == "none" for r in plans) and all(r["tools"] and r["tool_choice"] == "auto" for r in acts)
    assert all(r["max_tokens"] <= 2000 for r in s2)


def test_m1_a1_runs_a_mock_task_end_to_end(tmp_path, router):
    """G1 write-order fix A1: the orchestrator's calls carry the tool definitions with tool_choice "none"."""
    cfg = bl.BudgetConfig(limit=5000, per_call_cap=2000, wrapup_threshold=300, min_call_allowance=20)
    saved, _ = run_mock(tmp_path, "test_m1_a1_mock", make_m1_factory(cfg, None, 4, 1.0, True))
    sim = saved["simulations"][0]
    assert sim["termination_reason"] == "user_stop" and sim["reward_info"]["reward"] == 1.0
    metered = [m for m in sim["messages"] if m["role"] == "assistant" and (m.get("raw_data") or {}).get(MAS_METADATA_KEY)]
    assert metered and all(m["raw_data"][MAS_METADATA_KEY]["orchestrator_tool_definitions"] is True for m in metered)
    orch = [r for r in router.requests if "orchestrator of a small support team" in r["messages"][0]["content"]]
    dba = [r for r in router.requests if "database agent on a small support team" in r["messages"][0]["content"]]
    assert orch and all(r["tools"] and r["tool_choice"] == "none" for r in orch)
    assert dba and all(r["tools"] and r["tool_choice"] == "auto" for r in dba)
    assert [t["function"]["name"] for t in orch[0]["tools"]] == [t["function"]["name"] for t in dba[0]["tools"]]
