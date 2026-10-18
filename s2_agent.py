"""S2: the strong single agent (ANALYSIS.md §2, §8): single-context plan -> execute -> review/revise.

One agent, one model, one context. Every call sees the same conversation as S1
does (native tool calls and tool results), under the base prompt plus one role
block (prompts/roles/s2_single_agent.md). Each tau2 turn has two calls:

- plan (tools shown, tool_choice "none", so the context is the act call's): a JSON
  update of the task and progress ledgers, a policy check (the rules that apply,
  quoted, and what they require), and a draft of the next action (a customer
  message or one tool call);
- act (native tools): the agent reviews the draft against its policy check, the
  conversation and its plan, revises it if needed, and acts. The act call's output
  is the turn: a tool call in the same native format as S1, or a customer message.

S2 does in one context the work M1 splits across three: M1's orchestrator plans,
its advisor states the policy rules, its database agent makes the tool calls. S2
never sees gold actions, evaluator outputs, assertions, or reward.

Budget: the same layer as S1 and M1 (per-call cap c, episode ceiling, wrap-up
notice, exhaustion stop). After the wrap-up notice fires, a turn is one call with
no tools and no plan (as in S1): only a closing customer message is allowed (R5).
A truncated or empty act call is never executed; one closing call without tools
follows, as in S1 (R6). An act reply that is JSON text is never sent to the customer:
a drafted message inside it is used, otherwise the act call is repeated once with
a reminder, and a second JSON reply becomes the drafted message inside it or the
fixed holding line (as in M1).

Logging (per outgoing message, raw_data[MAS_METADATA_KEY], the key M1 uses, so the
same health and analysis scripts read both): every call with its usage, the plan,
events, the ledgers, and the review outcome (draft kept or revised), computed from
the logs without a judge.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import ConfigDict
from tau2.agent.base_agent import ValidAgentInputMessage
from tau2.agent.llm_agent import LLMAgent, LLMAgentState
from tau2.data_model.message import AssistantMessage, Message, MultiToolMessage, SystemMessage, UserMessage
from tau2.environment.tool import Tool

from budget_layer import (
    BUDGET_METADATA_KEY,
    TERMINATION_KEY,
    TERMINATION_NORMAL,
    BudgetConfig,
    BudgetExhausted,
    EpisodeBudget,
    budget_status_line,
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
from m1_agent import FALLBACK_HOLDING_MESSAGE, INTERNAL, MAS_METADATA_KEY, TurnLog, _loose, _norm, parse_json_object

ROLE_BLOCK = "s2_single_agent"
BUDGET_LABELS = {"s2_plan": "plan", "s2_act": "act", "s2_act_after_truncation": "message"}
ALLOWANCE_PARAGRAPH_START = "You have a fixed processing allowance"


def strip_s2_allowance_paragraph(block: str) -> str:
    """Remove the allowance paragraph of the S2 block (episodes without a ceiling only)."""
    paras = block.split("\n\n")
    kept = [p for p in paras if not p.strip().startswith(ALLOWANCE_PARAGRAPH_START)]
    if len(kept) != len(paras) - 1:
        raise ValueError("S2 role block: expected exactly one allowance paragraph")
    return "\n\n".join(kept)


def draft_of(plan: Optional[dict]) -> Optional[dict]:
    """The plan's draft as {"type": "message"|"tool_call", ...}, or None if absent or malformed."""
    if not isinstance(plan, dict) or not isinstance(plan.get("draft"), dict):
        return None
    d = plan["draft"]
    kind = str(d.get("type", "")).lower().strip()
    content = d.get("content")
    if kind == "message":
        return {"type": "message", "text": content if isinstance(content, str) else _norm(content)}
    if kind in ("tool_call", "tool", "read", "write"):
        spec = content if isinstance(content, dict) else parse_json_object(content if isinstance(content, str) else None)
        if not (isinstance(spec, dict) and spec.get("tool")) and d.get("tool"):
            spec = d  # flat draft: {"type": "tool_call", "tool": ..., "arguments": ...}
        if isinstance(spec, dict) and spec.get("tool"):
            args = spec.get("arguments") if isinstance(spec.get("arguments"), dict) else {}
            name = str(spec["tool"])
            if name.startswith("functions."):  # OpenAI models name tools by their namespace (smoke 2026-09-25)
                name = name[len("functions."):]
            return {"type": "tool_call", "tool": name, "arguments": args}
        return {"type": "tool_call", "tool": None, "arguments": None}
    return None


def review_outcome(draft: Optional[dict], out: AssistantMessage) -> str:
    """How the act call's output relates to the plan's draft (logged; no judge).

    kept: same tool and arguments (after type normalisation), or the same message text;
    revised_arguments / revised_tool: a tool call that differs from the drafted one;
    reworded: a message whose text differs from the drafted text;
    revised_to_message / revised_to_tool_call: the kind of action changed;
    no_draft: the plan had no usable draft (or no plan was parsed).
    """
    if draft is None:
        return "no_draft"
    if out.tool_calls:
        if draft["type"] != "tool_call":
            return "revised_to_tool_call"
        tc = out.tool_calls[0]
        if draft["tool"] is None or draft["tool"] != tc.name:
            return "revised_tool"
        if len(out.tool_calls) == 1 and _norm(_loose(draft["arguments"])) == _norm(_loose(tc.arguments)):
            return "kept"
        return "revised_arguments"
    if draft["type"] != "message":
        return "revised_to_message"
    return "kept" if (out.content or "").strip() == (draft["text"] or "").strip() else "reworded"


def looks_like_json(text: Optional[str]) -> bool:
    t = (text or "").strip()
    return t.startswith("{") or t.startswith("```")


def message_inside_json(text: Optional[str]) -> str:
    """A customer message the model wrapped in JSON (a message draft), else ""."""
    obj = parse_json_object(text)
    if not obj:
        return ""
    d = draft_of(obj) or draft_of({"draft": obj})
    if d and d["type"] == "message" and isinstance(d.get("text"), str) and not looks_like_json(d["text"]):
        return d["text"].strip()
    return ""


class S2State(LLMAgentState):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    budget: Any = None
    task_ledger: dict = {}
    progress_ledger: dict = {}
    turn_index: int = 0


class S2Agent(LLMAgent[S2State]):
    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        llm: str,
        llm_args: Optional[dict] = None,
        budget_config: Optional[BudgetConfig] = None,
        base_prompt_sha256: Optional[str] = None,
    ):
        super().__init__(tools=tools, domain_policy=domain_policy, llm=llm, llm_args=llm_args)
        self.budget_config = budget_config or BudgetConfig.uncapped()
        self.base_prompt_sha256 = base_prompt_sha256
        block = load_role_block(ROLE_BLOCK)
        if self.budget_config.limit is None:
            block = strip_s2_allowance_paragraph(block)
        self.role_block = block
        self.agent_prompt = render_base_prompt(domain_policy, base_prompt_sha256) + "\n\n" + block

    # --- tau2 interface ----------------------------------------------------
    @property
    def system_prompt(self) -> str:
        return self.agent_prompt

    def get_init_state(self, message_history: Optional[list[Message]] = None) -> S2State:
        base = super().get_init_state(message_history)
        return S2State(
            system_messages=base.system_messages,
            messages=base.messages,
            budget=EpisodeBudget(self.budget_config),
            task_ledger={"facts": [], "guesses": [], "plan": []},
            progress_ledger={"last_step": "", "result": "", "got_what_was_needed": True, "stalled": False},
        )

    @classmethod
    def is_stop(cls, message: AssistantMessage) -> bool:
        if is_exhaustion_message(message):
            return True
        return super().is_stop(message)

    # --- one turn ----------------------------------------------------------
    def _generate_next_message(self, message: ValidAgentInputMessage, state: S2State) -> AssistantMessage:
        if isinstance(message, UserMessage) and message.is_audio:
            raise ValueError("User message cannot be audio.")
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)
        state.turn_index += 1
        turn = TurnLog()
        budget: EpisodeBudget = state.budget
        plan: Optional[dict] = None
        draft: Optional[dict] = None

        try:
            if budget.exhausted_before_call():
                return self._finalize(exhaustion_message(self.budget_config, budget), state, turn, None)
            if budget.needs_wrapup():
                budget.wrapup_triggered = True

            if not budget.wrapup_triggered:
                plan = self._plan(state, turn)
                if plan is not None:
                    self._absorb_ledgers(state, plan)
                    turn.plans.append(plan)
                    draft = draft_of(plan)
                    if draft is None:
                        turn.events.append("draft_missing_or_malformed")
                    pc = plan.get("policy_check")
                    if not (isinstance(pc, dict) and pc.get("rules")):
                        turn.events.append("policy_check_missing")
                if budget.exhausted_before_call():
                    return self._finalize(exhaustion_message(self.budget_config, budget), state, turn, draft)
                if budget.needs_wrapup():
                    budget.wrapup_triggered = True
                    turn.events.append("wrapup_after_plan")

            out = self._act(state, turn, plan)
            return self._finalize(out, state, turn, draft)
        except BudgetExhausted:
            return self._finalize(exhaustion_message(self.budget_config, budget), state, turn, draft)

    # --- calls ---------------------------------------------------------------
    def _system(self, budget: EpisodeBudget) -> SystemMessage:
        content = self.agent_prompt
        if budget.wrapup_triggered:
            content += "\n\n" + load_wrapup_notice()
        return SystemMessage(role="system", content=content)

    def _plan(self, state: S2State, turn: TurnLog) -> Optional[dict]:
        budget: EpisodeBudget = state.budget
        parts = [
            f"{INTERNAL} Your task ledger: {_norm(state.task_ledger)}",
            f"Your progress ledger: {_norm(state.progress_ledger)}",
        ]
        status = budget_status_line(budget, BUDGET_LABELS)
        if status:
            parts.append(status)
        parts.append("Plan now (step 1). Do not call tools. Reply only with the plan JSON.")
        text = "\n\n".join(parts)
        for attempt in range(2):
            reply = metered_generate(
                model=self.llm, messages=[self._system(budget)] + list(state.messages) + [UserMessage(role="user", content=text)],
                tools=self.tools, tool_choice="none", llm_args=self.llm_args, call_name="s2_plan", component="agent", budget=budget,
            )
            if reply.tool_calls:
                # The provider ignored tool_choice "none": the call is charged, never executed.
                turn.events.append("plan_returned_tool_call")
                reply.tool_calls = None
            plan = parse_json_object(reply.content)
            turn.add_call("agent", "s2_plan", reply, plan if plan is not None else (reply.content or "")[:2000])
            if plan is not None:
                return plan
            if call_is_truncated(reply):
                # Cut at the per-call cap: the same call would be cut again (as in M1).
                turn.events.append("plan_truncated")
                break
            text += f"\n\n{INTERNAL} Your previous reply was not a valid JSON object. Reply only with the plan JSON described in your instructions."
            if budget.exhausted_before_call() or budget.needs_wrapup():
                break  # no retry once the wrap-up threshold is crossed: the act call closes (R4, as in M1)
        turn.events.append("plan_parse_failed")
        return None

    def _act(self, state: S2State, turn: TurnLog, plan: Optional[dict]) -> AssistantMessage:
        budget: EpisodeBudget = state.budget
        status = budget_status_line(budget, BUDGET_LABELS)
        if budget.wrapup_triggered:
            # R5: after the wrap-up notice only a customer-facing turn is allowed, with no tools and no plan.
            text = f"{INTERNAL} Only a message to the customer is allowed now. Write it as plain text. Do not call tools and do not reply with JSON."
            tools = None
        elif plan is not None:
            text = (
                f"{INTERNAL} Your plan for this turn: {_norm(plan)}\n\n"
                "Review and act now (step 2). Check the draft against the policy rules you listed, the facts in the "
                "conversation, and your plan, and revise it if needed. Then call the tool, or write your message to the "
                "customer as plain text. Do not reply with JSON."
            )
            tools = self.tools
        else:
            text = (
                f"{INTERNAL} No plan is available for this turn. Review the conversation against the policy and act now "
                "(step 2): call the tool, or write your message to the customer as plain text. Do not reply with JSON."
            )
            tools = self.tools
        if status:
            text = f"{text}\n\n{status}"
        reply = self._act_call(state, turn, text, tools)

        if not reply.tool_calls and not call_is_truncated(reply) and looks_like_json(reply.content):
            # JSON text never reaches the customer. A message drafted inside it is used; otherwise the act
            # call is repeated once with a reminder (smoke 2026-09-25: a closing call here carried the
            # wrap-up notice and ended conversations that had budget left).
            inner = message_inside_json(reply.content)
            if inner:
                turn.events.append("act_json_used_message")
                reply.content = inner
            else:
                turn.events.append("act_json_reply")
                if budget.exhausted_before_call():
                    return exhaustion_message(self.budget_config, budget)
                retry_text = (
                    f"{text}\n\n{INTERNAL} Your previous reply was JSON, which the customer cannot receive. "
                    "Call the tool, or write your message to the customer as plain text."
                )
                turn.events.append("act_json_retry")
                reply = self._act_call(state, turn, retry_text, tools)
                if not reply.tool_calls and not call_is_truncated(reply) and looks_like_json(reply.content):
                    inner = message_inside_json(reply.content)
                    turn.events.append("act_json_retry_" + ("used_message" if inner else "fallback_text"))
                    if not inner:
                        turn.events.append("fallback_text")
                    reply.content = inner or FALLBACK_HOLDING_MESSAGE

        if call_is_truncated(reply) or (not reply.tool_calls and not (reply.content or "").strip()):
            # R6: never execute a truncated tool call; ask for a closing customer message instead (as in S1).
            turn.events.append("forced_closing")
            turn.events.append("act_truncated" if call_is_truncated(reply) else "act_empty")
            if budget.exhausted_before_call():
                return exhaustion_message(self.budget_config, budget, {"truncated_first_attempt": True})
            closing = SystemMessage(role="system", content=self.agent_prompt + "\n\n" + load_wrapup_notice())
            closing_text = f"{INTERNAL} Write your next message to the customer as plain text. Do not call tools and do not reply with JSON."
            try:
                reply = metered_generate(
                    model=self.llm, messages=[closing] + list(state.messages) + [UserMessage(role="user", content=closing_text)],
                    tools=None, llm_args=self.llm_args, call_name="s2_act_after_truncation", component="agent", budget=budget,
                )
            except BudgetExhausted:
                return exhaustion_message(self.budget_config, budget, {"truncated_first_attempt": True})
            turn.add_call("agent", "s2_act_after_truncation", reply, (reply.content or "")[:2000])
            if looks_like_json(reply.content):
                inner = message_inside_json(reply.content)
                turn.events.append("closing_json_reply" + ("_used_message" if inner else "_discarded"))
                if inner:
                    reply.content = inner
                else:
                    turn.events.append("fallback_text")
                    reply.content = FALLBACK_HOLDING_MESSAGE
            if not (reply.content or "").strip():
                return exhaustion_message(self.budget_config, budget, {"truncated_first_attempt": True})

        stray = strip_text_when_tool_call(reply)
        if stray:
            turn.events.append("stray_text_with_tool_call_dropped")
        # The act reply is the turn (as in S1); usage, cost and metadata are set in _finalize from the whole turn.
        return reply

    def _act_call(self, state: S2State, turn: TurnLog, text: str, tools) -> AssistantMessage:
        budget: EpisodeBudget = state.budget
        reply = metered_generate(
            model=self.llm, messages=[self._system(budget)] + list(state.messages) + [UserMessage(role="user", content=text)],
            tools=tools, llm_args=self.llm_args, call_name="s2_act", component="agent", budget=budget,
        )
        turn.add_call("agent", "s2_act", reply, [{"name": tc.name, "arguments": tc.arguments} for tc in reply.tool_calls] if reply.tool_calls else (reply.content or "")[:2000])
        return reply

    def _absorb_ledgers(self, state: S2State, plan: dict) -> None:
        if isinstance(plan.get("task_ledger"), dict):
            state.task_ledger = plan["task_ledger"]
        if isinstance(plan.get("progress_ledger"), dict):
            state.progress_ledger = plan["progress_ledger"]

    # --- output assembly -----------------------------------------------------
    @staticmethod
    def _outcome(turn: TurnLog, draft: Optional[dict], out: AssistantMessage, exhausted: bool, budget: EpisodeBudget) -> Optional[str]:
        """Review outcome for the turn; forced turns are labelled apart so they never count as reviews."""
        if exhausted:
            return None
        if "forced_closing" in turn.events:
            return "forced_closing"
        if "fallback_text" in turn.events:
            return "fallback_text"
        if "wrapup_after_plan" in turn.events:
            return "wrapup_after_plan"
        if not turn.plans and budget.wrapup_triggered:
            return "wrapup_turn"
        return review_outcome(draft, out)

    def _finalize(self, out: AssistantMessage, state: S2State, turn: TurnLog, draft: Optional[dict]) -> AssistantMessage:
        budget: EpisodeBudget = state.budget
        usage = sum_usage(turn.replies)
        cost = sum(float(r.cost or 0.0) for r in turn.replies)
        raw = dict(out.raw_data or {})
        exhausted = is_exhaustion_message(out)
        raw[MAS_METADATA_KEY] = {
            "architecture": "S2",
            "turn_index": state.turn_index,
            "llm_calls": len(turn.components),
            "components": turn.components,
            "assignments": [],
            "advisor": [],
            "plans": turn.plans,
            "events": turn.events,
            "task_ledger": state.task_ledger,
            "progress_ledger": state.progress_ledger,
            "review": {"draft": draft, "outcome": self._outcome(turn, draft, out, exhausted, budget)},
            "wrapup_triggered": budget.wrapup_triggered,
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


def make_s2_factory(budget_config: Optional[BudgetConfig] = None, base_prompt_sha256: Optional[str] = None):
    """Factory for `registry.register_agent_factory`, closed over the cell's budget."""

    def create(tools, domain_policy, **kwargs):
        return S2Agent(
            tools=tools, domain_policy=domain_policy, llm=kwargs.get("llm"), llm_args=kwargs.get("llm_args"),
            budget_config=budget_config, base_prompt_sha256=base_prompt_sha256,
        )

    return create
