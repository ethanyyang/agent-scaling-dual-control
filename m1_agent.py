"""M1: Kim et al.'s centralized pattern adapted to dual control (ANALYSIS.md §2).

Components, all on the same model and the same episode ledger:
- orchestrator: the only component that speaks to the customer; plans; keeps a
  task ledger and a progress ledger; issues assignments. Never receives tools.
- database agent: the only component that emits tool calls; executes
  goal-level read assignments (up to `k` consecutive calls) and single-call
  write assignments exactly as issued; reports back in a fixed JSON format.
- policy advisor: reasoning-only worker consulted at the orchestrator's
  discretion; fresh context per call; fixed JSON reply.

One tau2 "turn" = whatever internal calls are needed until an external output
exists: a customer message or a tool call. Tool results are routed to the
database agent while a read assignment is open, otherwise to the orchestrator.
Every call is metered and capped by the shared budget layer; the wrap-up
notice and the exhaustion stop apply to the whole system.

Logging (per outgoing message, in raw_data[MAS_METADATA_KEY]): every internal
call with its usage, every assignment with its report and, for writes, whether
the executed tool call matched the order; advisor questions and replies; the
ledgers after the turn. These feed the G1 indicators and the order-misexecution
failure class without any judge.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from pydantic import ConfigDict
from tau2.agent.base_agent import ValidAgentInputMessage
from tau2.agent.llm_agent import LLMAgent, LLMAgentState
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    MultiToolMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool
from tau2.environment.toolkit import TOOL_TYPE_ATTR, ToolType

from budget_layer import (
    budget_status_line,
    BUDGET_METADATA_KEY,
    TERMINATION_KEY,
    TERMINATION_NORMAL,
    BudgetConfig,
    BudgetExhausted,
    EpisodeBudget,
    call_is_truncated,
    exhaustion_message,
    is_exhaustion_message,
    load_role_block,
    load_wrapup_notice,
    metered_generate,
    render_base_prompt,
    strip_text_when_tool_call,
    sum_usage,
    usage_for_analyzers,
)

MAS_METADATA_KEY = "transfer_testing_multi_agent"
INTERNAL = "[INTERNAL, not from the customer]"
BUDGET_LABELS = {
    "m1_plan": "plan", "m1_act": "act after advice", "m1_advisor": "advisor question",
    "m1_db_read": "database call", "m1_db_write": "database write", "m1_db_report": "database report",
    "m1_forced_message": "message",
}
FALLBACK_HOLDING_MESSAGE = "I'm still working on this for you. Could you bear with me a moment, and let me know if anything has changed on your side?"
MAX_ROUNDS_PER_TURN = 4  # orchestrator <-> database-agent bounces before a forced customer message
DEFAULT_READ_CALL_LIMIT = 4  # k, frozen in docs/budget-protocol.md


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def parse_json_object(text: Optional[str]) -> Optional[dict]:
    """Lenient JSON-object parse: strips code fences, falls back to the outermost braces."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    for candidate in (t, t[t.find("{") : t.rfind("}") + 1] if "{" in t and "}" in t else ""):
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


ALLOWANCE_PARAGRAPH_START = "Your team has a fixed processing allowance"


def strip_allowance_paragraph(block: str) -> str:
    """Remove the budget paragraph of the orchestrator role block (uncapped arm only)."""
    paras = block.split("\n\n")
    kept = [p for p in paras if not p.strip().startswith(ALLOWANCE_PARAGRAPH_START)]
    if len(kept) != len(paras) - 1:
        raise ValueError("orchestrator role block: expected exactly one allowance paragraph")
    return "\n\n".join(kept)


def render_transcript(messages: list[Message]) -> str:
    """Plain-text view of the conversation for tool-less calls (orchestrator, advisor)."""
    lines: list[str] = []
    for m in messages:
        if isinstance(m, UserMessage):
            if m.tool_calls:
                for tc in m.tool_calls:
                    lines.append(f"CUSTOMER -> TOOL {tc.name}({json.dumps(tc.arguments, ensure_ascii=False)})")
            if m.content:
                lines.append(f"CUSTOMER: {m.content}")
        elif isinstance(m, AssistantMessage):
            if m.tool_calls:
                for tc in m.tool_calls:
                    lines.append(f"AGENT -> TOOL {tc.name}({json.dumps(tc.arguments, ensure_ascii=False)})")
            if m.content:
                lines.append(f"AGENT: {m.content}")
        elif isinstance(m, ToolMessage):
            who = "customer's device" if m.requestor == "user" else "tool"
            lines.append(f"TOOL RESULT ({who}{', error' if m.error else ''}): {m.content}")
    return "\n".join(lines) if lines else "(no messages yet)"


def _norm(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _loose(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _loose(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_loose(v) for v in obj]
    return str(obj)


class Assignment:
    def __init__(self, kind: str, content: Any, issued_in_round: int):
        self.kind = kind  # "read" | "write"
        self.content = content  # read: goal text; write: {"tool": ..., "arguments": {...}} or text
        self.issued_in_round = issued_in_round
        self.status = "open"  # open | executing_write | closed
        self.calls_made = 0
        self.tool_calls_log: list[dict] = []
        self.report: Optional[dict] = None
        self.executed_as_issued: Optional[bool] = None
        self.order_check: Optional[str] = None

    @property
    def spec(self) -> Optional[dict]:
        if self.kind != "write":
            return None
        c = self.content
        if isinstance(c, dict) and "tool" in c:
            return c
        if isinstance(c, str):
            return parse_json_object(c)
        return None

    def describe(self) -> str:
        if self.kind == "read":
            return f"Read assignment (goal): {self.content}"
        spec = self.spec
        if spec:
            return f"Write assignment (exact single call): tool `{spec.get('tool')}` with arguments {json.dumps(spec.get('arguments', {}), ensure_ascii=False)}"
        return f"Write assignment (exact single call): {self.content}"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "content": self.content,
            "status": self.status,
            "calls_made": self.calls_made,
            "tool_calls": self.tool_calls_log,
            "report": self.report,
            "executed_as_issued": self.executed_as_issued,
            "order_check": self.order_check,
        }


class TurnLog:
    def __init__(self) -> None:
        self.components: list[dict] = []
        self.events: list[str] = []
        self.assignments: list[dict] = []
        self.advisor: list[dict] = []
        self.plans: list[dict] = []
        self.replies: list[AssistantMessage] = []

    def add_call(self, component: str, call_name: str, reply: AssistantMessage, output: Any) -> None:
        rec = (reply.raw_data or {}).get("transfer_testing_call") or {}
        self.replies.append(reply)
        self.components.append(
            {
                "component": component,
                "call_name": call_name,
                "usage": reply.usage,
                "cost": reply.cost,
                "finish_reason": rec.get("finish_reason"),
                "truncated": rec.get("truncated"),
                "max_tokens_sent": rec.get("max_tokens_sent"),
                "output": output,
            }
        )


class M1State(LLMAgentState):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    budget: Any = None
    task_ledger: dict = {}
    progress_ledger: dict = {}
    assignment: Any = None  # open Assignment or None
    last_closed_assignment: Any = None
    turn_index: int = 0


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------


class M1Agent(LLMAgent[M1State]):
    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        llm: str,
        llm_args: Optional[dict] = None,
        budget_config: Optional[BudgetConfig] = None,
        base_prompt_sha256: Optional[str] = None,
        read_call_limit: int = DEFAULT_READ_CALL_LIMIT,
        orchestrator_cap_mult: float = 1.0,
        orchestrator_tool_definitions: bool = False,
    ):
        super().__init__(tools=tools, domain_policy=domain_policy, llm=llm, llm_args=llm_args)
        # G1 write-order fix A1 (ANALYSIS.md CHANGELOG 2026-10-12): the orchestrator must state each write
        # as an exact call, so its calls carry the tool definitions with tool_choice "none" (it still cannot
        # call a tool; every tool call is made by the database agent). Off = M1 as built (v6), unchanged.
        self.orchestrator_tool_definitions = orchestrator_tool_definitions
        self.budget_config = budget_config or BudgetConfig.uncapped()
        self.base_prompt_sha256 = base_prompt_sha256
        self.read_call_limit = read_call_limit
        # Per-call cap for orchestrator and advisor calls = orchestrator_cap_mult * c.
        # The database agent keeps c (its calls are S1-like). The episode ledger always binds.
        self.orchestrator_cap_mult = orchestrator_cap_mult
        c = self.budget_config.per_call_cap
        self.orchestrator_cap = int(round(c * orchestrator_cap_mult)) if c else None
        base = render_base_prompt(domain_policy, base_prompt_sha256)
        orchestrator_block = load_role_block("m1_orchestrator")
        if self.budget_config.limit is None:
            # Uncapped arm (§8 addendum 2026-09-24): there is no allowance and no status line, so the
            # one paragraph of the frozen v6 block that describes them is removed; nothing else changes.
            orchestrator_block = strip_allowance_paragraph(orchestrator_block)
        self.orchestrator_prompt = base + "\n\n" + orchestrator_block
        self.database_prompt = base + "\n\n" + load_role_block("m1_database_agent")
        self.advisor_prompt = base + "\n\n" + load_role_block("m1_advisor")
        self.write_tool_names = {
            t.name for t in tools if getattr(getattr(t, "_func", None), TOOL_TYPE_ATTR, None) == ToolType.WRITE
        }

    # --- tau2 interface ----------------------------------------------------
    @property
    def system_prompt(self) -> str:
        return self.orchestrator_prompt

    def get_init_state(self, message_history: Optional[list[Message]] = None) -> M1State:
        base = super().get_init_state(message_history)
        return M1State(
            system_messages=base.system_messages,
            messages=base.messages,
            budget=EpisodeBudget(self.budget_config),
            task_ledger={"facts": [], "guesses": [], "plan": []},
            progress_ledger={"assignments": [], "advice": [], "stalled": False},
        )

    @classmethod
    def is_stop(cls, message: AssistantMessage) -> bool:
        if is_exhaustion_message(message):
            return True
        return super().is_stop(message)

    # --- one turn ----------------------------------------------------------
    def _generate_next_message(self, message: ValidAgentInputMessage, state: M1State) -> AssistantMessage:
        if isinstance(message, UserMessage) and message.is_audio:
            raise ValueError("User message cannot be audio.")
        incoming_tool_results: list[ToolMessage] = []
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
            incoming_tool_results = list(message.tool_messages)
        else:
            state.messages.append(message)
            if isinstance(message, ToolMessage):
                incoming_tool_results = [message]
        state.turn_index += 1
        turn = TurnLog()
        budget: EpisodeBudget = state.budget
        note: Optional[str] = None

        try:
            # 1. Route tool results to whoever owns the open assignment.
            a: Optional[Assignment] = state.assignment
            if incoming_tool_results and a is not None:
                if a.kind == "read" and a.status == "open":
                    out = self._database_step(state, turn)
                    if out is not None:
                        return self._finalize(out, state, turn)
                    note = self._report_note(state.last_closed_assignment)
                else:  # a write was executed last turn
                    a.status = "closed"
                    a.report = {"result": "executed", "tool_results": [t.content for t in incoming_tool_results]}
                    state.last_closed_assignment = a
                    state.assignment = None
                    turn.assignments.append(a.to_dict())
                    note = f"{INTERNAL} Result of your write assignment ({a.describe()}):\n" + "\n".join(
                        f"- {'ERROR: ' if t.error else ''}{t.content}" for t in incoming_tool_results
                    )
            elif incoming_tool_results:
                note = f"{INTERNAL} Tool results received:\n" + "\n".join(f"- {t.content}" for t in incoming_tool_results)

            # 2. Orchestrator loop: plan (+ advisor + act) until a customer message or a tool call exists.
            for round_idx in range(MAX_ROUNDS_PER_TURN):
                if budget.exhausted_before_call():
                    return self._finalize(exhaustion_message(self.budget_config, budget), state, turn)
                plan = self._orchestrator_plan(state, turn, note)
                if plan is None:
                    return self._finalize(self._forced_message(state, turn, "plan_unparsable"), state, turn)
                self._absorb_ledgers(state, plan)
                turn.plans.append(plan)
                action = plan.get("action") if isinstance(plan.get("action"), dict) else None
                question = plan.get("ask_advisor")
                if isinstance(question, str) and question.strip() and question.strip().lower() != "null":
                    advice = self._advisor(state, turn, question.strip())
                    action = self._orchestrator_act(state, turn, plan, advice)
                if budget.wrapup_triggered and (action is None or action.get("type") != "message"):
                    action = self._orchestrator_act(state, turn, plan, None, force_message=True)
                if action is None:
                    return self._finalize(self._forced_message(state, turn, "action_unparsable"), state, turn)
                kind = str(action.get("type", "")).lower()
                content = action.get("content")
                if kind == "message":
                    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                    if not text.strip():
                        return self._finalize(self._forced_message(state, turn, "empty_message"), state, turn)
                    return self._finalize(AssistantMessage.text(text), state, turn)
                if kind not in ("read", "write"):
                    return self._finalize(self._forced_message(state, turn, f"unknown_action_type:{kind}"), state, turn)
                state.assignment = Assignment(kind, content, round_idx)
                out = self._database_step(state, turn)
                if out is not None:
                    return self._finalize(out, state, turn)
                note = self._report_note(state.last_closed_assignment)
            turn.events.append("max_rounds_reached")
            return self._finalize(self._forced_message(state, turn, "max_rounds"), state, turn)
        except BudgetExhausted:
            return self._finalize(exhaustion_message(self.budget_config, budget), state, turn)

    # --- orchestrator calls --------------------------------------------------
    def _context_block(self, state: M1State, note: Optional[str]) -> str:
        parts = [
            f"{INTERNAL} Conversation so far:\n<conversation>\n{render_transcript(state.messages)}\n</conversation>",
            f"Your task ledger: {_norm(state.task_ledger)}",
            f"Your progress ledger: {_norm(state.progress_ledger)}",
        ]
        status = budget_status_line(state.budget, BUDGET_LABELS)
        if status:
            parts.append(status)
        if note:
            parts.append(note)
        return "\n\n".join(parts)

    def _orch_tools(self) -> dict:
        """Tool arguments for orchestrator calls: none (as built) or the definitions with tool_choice "none" (A1)."""
        if self.orchestrator_tool_definitions:
            return {"tools": self.tools, "tool_choice": "none"}
        return {"tools": None}

    @staticmethod
    def _drop_orchestrator_tool_calls(reply: AssistantMessage, turn: "TurnLog", call_name: str) -> None:
        """A provider that ignores tool_choice "none" (Ollama does) may return tool calls: charged, never executed."""
        if reply.tool_calls:
            turn.events.append(f"orchestrator_returned_tool_call:{call_name}")
            reply.tool_calls = None

    def _orchestrator_messages(self, state: M1State, budget: EpisodeBudget, user_text: str) -> list[Message]:
        if budget.needs_wrapup():
            budget.wrapup_triggered = True
        system = self.orchestrator_prompt
        if budget.wrapup_triggered:
            system += "\n\n" + load_wrapup_notice() + "\nOnly a customer message is allowed now; do not issue assignments."
        return [SystemMessage(role="system", content=system), UserMessage(role="user", content=user_text)]

    def _orchestrator_plan(self, state: M1State, turn: TurnLog, note: Optional[str]) -> Optional[dict]:
        budget: EpisodeBudget = state.budget
        text = self._context_block(state, note) + "\n\nPlan now. Reply only with the plan JSON."
        for attempt in range(2):
            reply = metered_generate(
                model=self.llm, messages=self._orchestrator_messages(state, budget, text), **self._orch_tools(),
                llm_args=self.llm_args, call_name="m1_plan", component="orchestrator", budget=budget,
                per_call_cap=self.orchestrator_cap,
            )
            self._drop_orchestrator_tool_calls(reply, turn, "m1_plan")
            plan = parse_json_object(reply.content)
            turn.add_call("orchestrator", "m1_plan", reply, plan if plan is not None else (reply.content or "")[:2000])
            if plan is not None:
                return plan
            if call_is_truncated(reply):
                # Cut at the per-call cap (thinking used the room): the same call would be cut
                # again, so no second allowance is spent on it (smoke run 2026-09-20).
                turn.events.append("plan_truncated")
                break
            text += f"\n\n{INTERNAL} Your previous reply was not a valid JSON object. Reply only with the JSON object described in your instructions."
            if budget.exhausted_before_call():
                break
        turn.events.append("plan_parse_failed")
        return None

    def _orchestrator_act(self, state: M1State, turn: TurnLog, plan: dict, advice: Optional[dict], force_message: bool = False) -> Optional[dict]:
        budget: EpisodeBudget = state.budget
        parts = [self._context_block(state, None), f"Your plan: {_norm(plan)}"]
        if advice is not None:
            parts.append(f"Policy advisor reply: {_norm(advice)}")
        if force_message:
            parts.append(f"{INTERNAL} Only a customer message is allowed now. Set action.type to \"message\".")
        parts.append("Act now. Reply only with the action JSON.")
        text = "\n\n".join(parts)
        for attempt in range(2):
            reply = metered_generate(
                model=self.llm, messages=self._orchestrator_messages(state, budget, text), **self._orch_tools(),
                llm_args=self.llm_args, call_name="m1_act", component="orchestrator", budget=budget,
                per_call_cap=self.orchestrator_cap,
            )
            self._drop_orchestrator_tool_calls(reply, turn, "m1_act")
            obj = parse_json_object(reply.content)
            action = obj.get("action") if obj and isinstance(obj.get("action"), dict) else (obj if obj and "type" in obj else None)
            turn.add_call("orchestrator", "m1_act", reply, action if action is not None else (reply.content or "")[:2000])
            if action is not None:
                return action
            if call_is_truncated(reply):
                turn.events.append("act_truncated")
                break
            text += f"\n\n{INTERNAL} Your previous reply was not a valid action JSON object. Reply only with {{\"action\": {{\"type\": ..., \"content\": ...}}}}."
            if budget.exhausted_before_call():
                break
        turn.events.append("act_parse_failed")
        return None

    def _absorb_ledgers(self, state: M1State, plan: dict) -> None:
        if isinstance(plan.get("task_ledger"), dict):
            state.task_ledger = plan["task_ledger"]
        if isinstance(plan.get("progress_ledger"), dict):
            state.progress_ledger = plan["progress_ledger"]

    def _forced_message(self, state: M1State, turn: TurnLog, reason: str) -> AssistantMessage:
        """Last resort inside a turn: one tool-less call asking for a customer message; else the exhaustion text."""
        budget: EpisodeBudget = state.budget
        turn.events.append(f"forced_message:{reason}")
        if budget.exhausted_before_call():
            return exhaustion_message(self.budget_config, budget, {"forced_reason": reason})
        text = self._context_block(state, None) + f"\n\n{INTERNAL} Write your next message to the customer as plain text, following the policy. No JSON, no assignment."
        messages = self._orchestrator_messages(state, budget, text)
        # The role block demands JSON; for this one call the system message overrides it.
        messages[0] = SystemMessage(
            role="system",
            content=messages[0].content + "\n\nFOR THIS REPLY ONLY: write the next message to the customer as plain text. No JSON, no ledgers, no assignment.",
        )
        try:
            reply = metered_generate(
                model=self.llm, messages=messages, **self._orch_tools(),
                llm_args=self.llm_args, call_name="m1_forced_message", component="orchestrator", budget=budget,
                per_call_cap=self.orchestrator_cap,
            )
        except BudgetExhausted:
            return exhaustion_message(self.budget_config, budget, {"forced_reason": reason})
        self._drop_orchestrator_tool_calls(reply, turn, "m1_forced_message")
        turn.add_call("orchestrator", "m1_forced_message", reply, (reply.content or "")[:2000])
        content = (reply.content or "").strip()
        if content.startswith("{") or content.startswith("```"):
            # The model produced JSON anyway: use its message action if there is one, never the raw JSON.
            obj = parse_json_object(content)
            action = (obj or {}).get("action") if isinstance((obj or {}).get("action"), dict) else None
            content = str(action.get("content") or "").strip() if action and action.get("type") == "message" else ""
            turn.events.append("forced_message:json_reply" + ("_used_action" if content else "_discarded"))
        if not content or call_is_truncated(reply):
            if budget.exhausted_before_call():
                return exhaustion_message(self.budget_config, budget, {"forced_reason": reason})
            # Protocol fallback: a fixed holding line, counted so it can be reported.
            turn.events.append("forced_message:fallback_text")
            return AssistantMessage.text(FALLBACK_HOLDING_MESSAGE)
        return AssistantMessage.text(content)

    # --- advisor -------------------------------------------------------------
    def _advisor(self, state: M1State, turn: TurnLog, question: str) -> dict:
        budget: EpisodeBudget = state.budget
        text = (
            f"{INTERNAL} Conversation so far:\n<conversation>\n{render_transcript(state.messages)}\n</conversation>\n\n"
            f"Question from the orchestrator: {question}\n\nReply only with the JSON described in your instructions."
        )
        reply = metered_generate(
            model=self.llm, messages=[SystemMessage(role="system", content=self.advisor_prompt), UserMessage(role="user", content=text)],
            tools=None, llm_args=self.llm_args, call_name="m1_advisor", component="advisor", budget=budget,
            per_call_cap=self.orchestrator_cap,
        )
        advice = parse_json_object(reply.content) or {"finding": (reply.content or "").strip(), "recommendation": None, "policy_basis": []}
        turn.add_call("advisor", "m1_advisor", reply, advice)
        turn.advisor.append({"question": question, "reply": advice})
        return advice

    # --- database agent ------------------------------------------------------
    def _database_step(self, state: M1State, turn: TurnLog) -> Optional[AssistantMessage]:
        """Advance the open assignment: returns a tool-call message (the turn) or None after a report."""
        budget: EpisodeBudget = state.budget
        a: Assignment = state.assignment
        forced_report = a.kind == "read" and a.calls_made >= self.read_call_limit
        instruction = [
            f"{INTERNAL} {a.describe()}",
            f"Orchestrator task ledger: {_norm(state.task_ledger)}",
            f"Tool calls made in this assignment so far: {a.calls_made} of at most {self.read_call_limit}.",
        ]
        if a.kind == "write":
            instruction.append("Make exactly that single tool call now, or report why you cannot.")
        elif forced_report:
            instruction.append("You have reached the call limit for this assignment. Report now; do not call a tool.")
        else:
            instruction.append("Continue: make the next tool call, or report if the goal is met or cannot be met.")
        messages: list[Message] = [SystemMessage(role="system", content=self.database_prompt)] + list(state.messages) + [
            UserMessage(role="user", content="\n".join(instruction))
        ]
        tools = None if forced_report else self.tools
        call_name = "m1_db_write" if a.kind == "write" else "m1_db_read"
        reply = metered_generate(
            model=self.llm, messages=messages, tools=tools, llm_args=self.llm_args,
            call_name=call_name, component="database_agent", budget=budget,
        )

        if reply.tool_calls and not call_is_truncated(reply):
            stray = strip_text_when_tool_call(reply)
            if a.kind == "write":
                reply.tool_calls = reply.tool_calls[:1]  # a write assignment is one call
                tc = reply.tool_calls[0]
                self._check_write_order(a, tc.name, tc.arguments)
                a.status = "executing_write"
            else:
                if any(tc.name in self.write_tool_names for tc in reply.tool_calls):
                    # A read assignment must not write. Drop the call and force a report next round.
                    turn.events.append("db_write_in_read_assignment_blocked")
                    reply.tool_calls = None
                    a.status = "closed"
                    a.report = {"result": None, "deviation": "attempted a write inside a read assignment; blocked"}
                    state.last_closed_assignment = a
                    state.assignment = None
                    turn.add_call("database_agent", call_name, reply, a.report)
                    turn.assignments.append(a.to_dict())
                    return None
                a.calls_made += len(reply.tool_calls)
            a.tool_calls_log.extend({"name": tc.name, "arguments": tc.arguments} for tc in reply.tool_calls)
            turn.add_call("database_agent", call_name, reply, [{"name": tc.name, "arguments": tc.arguments} for tc in reply.tool_calls])
            if stray:
                turn.events.append("db_stray_text_dropped")
            turn.assignments.append(a.to_dict())
            return reply

        # Report (or truncation): close the assignment and hand control back.
        if call_is_truncated(reply):
            report = {"result": None, "records": {}, "deviation": "database agent call truncated at the token cap"}
            turn.events.append("db_call_truncated")
        else:
            report = parse_json_object(reply.content) or {"result": (reply.content or "").strip(), "records": {}, "deviation": None}
        a.report = report
        a.status = "closed"
        state.last_closed_assignment = a
        state.assignment = None
        turn.add_call("database_agent", call_name, reply, report)
        turn.assignments.append(a.to_dict())
        return None

    def _check_write_order(self, a: Assignment, name: str, arguments: dict) -> None:
        spec = a.spec
        if not spec:
            a.executed_as_issued = None
            a.order_check = "unverifiable_order_format"
            return
        want_name = spec.get("tool")
        want_args = spec.get("arguments", {}) if isinstance(spec.get("arguments"), dict) else {}
        if name != want_name:
            a.executed_as_issued = False
            a.order_check = f"tool_mismatch:{want_name}->{name}"
        elif _norm(want_args) == _norm(arguments):
            a.executed_as_issued = True
            a.order_check = "exact"
        elif _norm(_loose(want_args)) == _norm(_loose(arguments)):
            a.executed_as_issued = True
            a.order_check = "exact_after_type_normalisation"
        else:
            a.executed_as_issued = False
            a.order_check = "argument_mismatch"

    def _report_note(self, a: Optional[Assignment]) -> str:
        if a is None:
            return f"{INTERNAL} The database agent returned no report."
        return f"{INTERNAL} Report from the database agent on your {a.kind} assignment ({a.describe()}):\n{_norm(a.report)}"

    # --- output assembly -------------------------------------------------------
    def _finalize(self, out: AssistantMessage, state: M1State, turn: TurnLog) -> AssistantMessage:
        budget: EpisodeBudget = state.budget
        usage = sum_usage(turn.replies)
        cost = sum(float(r.cost or 0.0) for r in turn.replies)
        raw = dict(out.raw_data or {})
        raw[MAS_METADATA_KEY] = {
            "architecture": "M1",
            "turn_index": state.turn_index,
            "llm_calls": len(turn.components),
            "components": turn.components,
            "assignments": turn.assignments,
            "advisor": turn.advisor,
            "plans": turn.plans,
            "events": turn.events,
            "task_ledger": state.task_ledger,
            "progress_ledger": state.progress_ledger,
            "open_assignment": state.assignment.to_dict() if state.assignment else None,
            "wrapup_triggered": budget.wrapup_triggered,
            "orchestrator_cap": self.orchestrator_cap,
            "orchestrator_tool_definitions": self.orchestrator_tool_definitions,
        }
        raw[BUDGET_METADATA_KEY] = budget.snapshot()
        raw.setdefault(TERMINATION_KEY, TERMINATION_NORMAL)
        raw["usage"] = usage_for_analyzers(usage)
        out.raw_data = raw
        out.usage = {"prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
                     "cached_tokens": usage["cached_tokens"], "reasoning_tokens": usage["reasoning_tokens"]}
        out.cost = cost
        out.generation_time_seconds = sum(float(r.generation_time_seconds or 0.0) for r in turn.replies)
        return out


def make_m1_factory(
    budget_config: Optional[BudgetConfig] = None,
    base_prompt_sha256: Optional[str] = None,
    read_call_limit: int = DEFAULT_READ_CALL_LIMIT,
    orchestrator_cap_mult: float = 1.0,
    orchestrator_tool_definitions: bool = False,
):
    def create(tools, domain_policy, **kwargs):
        return M1Agent(
            tools=tools, domain_policy=domain_policy, llm=kwargs.get("llm"), llm_args=kwargs.get("llm_args"),
            budget_config=budget_config, base_prompt_sha256=base_prompt_sha256, read_call_limit=read_call_limit,
            orchestrator_cap_mult=orchestrator_cap_mult, orchestrator_tool_definitions=orchestrator_tool_definitions,
        )

    return create
