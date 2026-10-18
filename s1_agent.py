"""S1: the tau2 default agent with a meter bolted on.

Behaviour is the stock `LLMAgent` (same prompt, same one-call-per-turn loop,
same tools). What is added: the base prompt is loaded from
prompts/base_system_prompt.md and hash-checked (protocol R10); every call goes
through `metered_generate`; and, when a budget is configured (G1 / R1 capped
reruns), the per-call cap, wrap-up notice and exhaustion stop apply exactly as
they do in M1. With `BudgetConfig.uncapped()` (calibration) nothing is enforced
and only the per-call snapshot is recorded.
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
    budget_status_line,
    TERMINATION_KEY,
    TERMINATION_NORMAL,
    BudgetConfig,
    BudgetExhausted,
    EpisodeBudget,
    call_is_truncated,
    exhaustion_message,
    is_exhaustion_message,
    metered_generate,
    render_base_prompt,
    strip_text_when_tool_call,
    usage_for_analyzers,
    load_wrapup_notice,
)


class S1State(LLMAgentState):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    budget: Any = None


class BudgetedS1Agent(LLMAgent[S1State]):
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

    @property
    def system_prompt(self) -> str:
        return render_base_prompt(self.domain_policy, self.base_prompt_sha256)

    def get_init_state(self, message_history: Optional[list[Message]] = None) -> S1State:
        base = super().get_init_state(message_history)
        return S1State(system_messages=base.system_messages, messages=base.messages, budget=EpisodeBudget(self.budget_config))

    @classmethod
    def is_stop(cls, message: AssistantMessage) -> bool:
        if is_exhaustion_message(message):
            return True
        return super().is_stop(message)

    def _generate_next_message(self, message: ValidAgentInputMessage, state: S1State) -> AssistantMessage:
        if isinstance(message, UserMessage) and message.is_audio:
            raise ValueError("User message cannot be audio.")
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)
        budget: EpisodeBudget = state.budget

        if budget.exhausted_before_call():
            return exhaustion_message(self.budget_config, budget)

        if budget.needs_wrapup():
            budget.wrapup_triggered = True
        # One system message only (some providers reject or merge a second one): the
        # allowance line (capped runs) and the wrap-up notice are appended to the base prompt.
        extra = [x for x in (budget_status_line(budget, {"agent_response": "reply"}),) if x]
        if budget.wrapup_triggered:
            extra.append(load_wrapup_notice())
        system_messages = state.system_messages
        if extra:
            system_messages = [SystemMessage(role="system", content="\n\n".join([state.system_messages[0].content, *extra]))]

        messages = system_messages + state.messages
        # After wrap-up only a customer-facing turn is allowed (R5): no tools.
        tools = None if budget.wrapup_triggered else self.tools
        try:
            reply = metered_generate(
                model=self.llm, messages=messages, tools=tools, llm_args=self.llm_args,
                call_name="agent_response", component="agent", budget=budget,
            )
        except BudgetExhausted:
            return exhaustion_message(self.budget_config, budget)

        if call_is_truncated(reply) or (not reply.tool_calls and not (reply.content or "").strip()):
            # R6: never execute a truncated tool call; ask for a closing customer message instead.
            if budget.exhausted_before_call():
                return exhaustion_message(self.budget_config, budget, {"truncated_first_attempt": True})
            try:
                closing_system = [SystemMessage(role="system", content=state.system_messages[0].content + "\n\n" + load_wrapup_notice())]
                reply = metered_generate(
                    model=self.llm, messages=closing_system + state.messages,
                    tools=None, llm_args=self.llm_args, call_name="agent_response_after_truncation",
                    component="agent", budget=budget,
                )
            except BudgetExhausted:
                return exhaustion_message(self.budget_config, budget, {"truncated_first_attempt": True})
            if not (reply.content or "").strip():
                return exhaustion_message(self.budget_config, budget, {"truncated_first_attempt": True})

        stray = strip_text_when_tool_call(reply)
        raw = dict(reply.raw_data or {})
        raw[TERMINATION_KEY] = TERMINATION_NORMAL
        raw[BUDGET_METADATA_KEY] = budget.snapshot()
        raw["usage"] = usage_for_analyzers(reply.usage or {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0})
        if stray:
            raw["stray_text_with_tool_call"] = stray
        reply.raw_data = raw
        return reply


def make_s1_factory(budget_config: Optional[BudgetConfig] = None, base_prompt_sha256: Optional[str] = None):
    """Factory for `registry.register_agent_factory`, closed over the cell's budget."""

    def create(tools, domain_policy, **kwargs):
        return BudgetedS1Agent(
            tools=tools, domain_policy=domain_policy, llm=kwargs.get("llm"), llm_args=kwargs.get("llm_args"),
            budget_config=budget_config, base_prompt_sha256=base_prompt_sha256,
        )

    return create
