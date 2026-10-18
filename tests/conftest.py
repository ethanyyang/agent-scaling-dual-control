"""Test support: import the transfer-testing modules and fake the provider.

Run from the tau2 environment:  cd tau2-bench && uv run python -m pytest ../tests -q
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Fn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, name, arguments, id="call_1"):
        self.id = id
        self.function = _Fn(name, arguments)


class _Msg:
    def __init__(self, content, tool_calls):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, content, tool_calls, finish_reason):
        self.message = _Msg(content, tool_calls)
        self.finish_reason = finish_reason


class _Details:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    def __init__(self, prompt, completion, cached=0, reasoning=None):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.prompt_tokens_details = _Details(cached_tokens=cached)
        self.completion_tokens_details = _Details(reasoning_tokens=reasoning)

    def get(self, key, default=None):
        return getattr(self, key, default)


class FakeResponse:
    """Just enough of litellm's ModelResponse for budget_layer.metered_generate."""

    def __init__(self, content=None, tool_calls=None, completion=10, prompt=100, cached=0, reasoning=None, finish_reason="stop", raw_arguments=None):
        tcs = None
        if tool_calls:
            tcs = [_TC(name, json.dumps(args) if raw_arguments is None else raw_arguments) for name, args in tool_calls]
        self.choices = [_Choice(content, tcs, finish_reason)]
        self.usage = _Usage(prompt, completion, cached, reasoning)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return {"fake": True}


class FakeProvider:
    """Sequential scripted responses; records every request's kwargs."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, **kwargs):
        self.requests.append(kwargs)
        if not self.responses:
            raise AssertionError("fake provider ran out of scripted responses")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def provider(monkeypatch):
    """Install a FakeProvider; tests call provider.script([...]) then run the agent."""
    import budget_layer

    holder = {"p": FakeProvider([])}

    def install(responses):
        holder["p"] = FakeProvider(responses)
        monkeypatch.setattr(budget_layer.llm_utils, "completion", holder["p"])
        monkeypatch.setattr(budget_layer.llm_utils, "get_response_cost", lambda r: 0.001)
        return holder["p"]

    install([])
    return types.SimpleNamespace(script=install, current=lambda: holder["p"])
