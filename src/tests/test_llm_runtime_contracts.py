import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from _runtime import llm_runtime
from _runtime.llm_runtime import (
    FallbackPolicy,
    LlmErrorKind,
    LlmInvocationError,
    LlmRequest,
    LlmResult,
    ProviderResponse,
    StructuredOutputContract,
    classify_exception,
    invoke_llm,
    invoke_structured_llm,
    validate_structured_output,
)


def test_classifies_request_timeout_as_transient():
    import requests

    assert classify_exception(requests.Timeout()) == LlmErrorKind.TRANSIENT


def test_validates_required_structured_keys():
    contract = StructuredOutputContract("action", required_keys=["name"])
    assert validate_structured_output('{"name": "read-file"}', contract)["name"] == "read-file"


def test_rejects_unvalidated_structured_action():
    with pytest.raises(LlmInvocationError) as error:
        validate_structured_output('{"args": {}}', StructuredOutputContract("action", required_keys=["name"]))
    assert error.value.kind == LlmErrorKind.MALFORMED_RESPONSE


def test_explicit_provider_does_not_rotate_after_authentication_failure(monkeypatch):
    calls = []

    def fail(provider, model, *_args):
        calls.append((provider, model))
        raise ValueError("Missing API key for provider")

    monkeypatch.setattr(llm_runtime, "_generate_single_response", fail)
    with pytest.raises(LlmInvocationError) as error:
        invoke_llm(LlmRequest.from_prompt("openai", "gpt-test", "hello"))
    assert error.value.kind == LlmErrorKind.AUTHENTICATION
    assert calls == [("openai", "gpt-test")]


def test_rotation_requires_explicit_policy(monkeypatch):
    monkeypatch.setattr(llm_runtime, "_generate_single_response", lambda *_args: ProviderResponse("ok", "groq", "model"))
    with pytest.raises(LlmInvocationError) as error:
        invoke_llm(LlmRequest.from_prompt("rotation", "rotation", "hello"))
    assert error.value.kind == LlmErrorKind.INVALID_REQUEST


def test_structured_output_repairs_once(monkeypatch):
    responses = iter([
        LlmResult("not json", "openai", "test", 1),
        LlmResult('{"name": "read-file"}', "openai", "test", 1),
    ])
    monkeypatch.setattr(llm_runtime, "invoke_llm", lambda _request: next(responses))
    result, value = invoke_structured_llm(LlmRequest.from_prompt(
        "openai", "test", "choose", output_contract=StructuredOutputContract("action", required_keys=["name"]),
    ))
    assert value["name"] == "read-file"
    assert result.retry_trace == [{"kind": "structured_repair", "attempt": "1"}]
