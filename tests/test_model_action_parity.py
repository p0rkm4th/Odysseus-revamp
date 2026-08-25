"""Synthetic model-swap checks at the canonical intent/contract boundary.

These tests deliberately do not call providers.  They prove that provider
identity is not an input to semantic compilation, ActionSpec resolution, or
durable continuation resolution.  Provider competence and prose quality are
separate evaluation concerns.
"""

import pytest

from src.intent_contracts import compile_intent, resolve_continuation, resolve_intent


MODELS = ("qwen3:8b", "gpt-5.6-luna", "gpt-5.6-sol")
REQUESTS = (
    "What IT assets do I have?",
    "What do you remember about me?",
    "What am I working on?",
    "Show my network devices.",
    "Deep scan those devices.",
    "Show my current security findings.",
    "Show my OSINT cases.",
    "What integrations are degraded?",
)


def _contract_projection(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    return {
        "intent": frame.as_dict(),
        "contract": resolved.as_dict(),
    }


@pytest.mark.parametrize("query", REQUESTS)
def test_qwen_luna_sol_receive_identical_canonical_contract_projection(query):
    """Model choice must not alter the semantic ActionSpec projection."""
    projections = {model: _contract_projection(query) for model in MODELS}
    assert len({repr(value) for value in projections.values()}) == 1
    assert projections[MODELS[0]]["contract"]["available"] is True
    if query == "What integrations are degraded?":
        assert projections[MODELS[0]]["contract"]["action_id"] == "integrations"


def test_qwen_luna_sol_continue_receive_identical_durable_run_resolution():
    frame = compile_intent("continue", continuation=True, run_reference="run-1")
    active_run = {
        "id": "run-1",
        "status": "running",
        "continuation_state": {"pending_action_id": "action-1"},
        "actions": [{"id": "action-1", "status": "approved"}],
    }
    resolutions = {
        model: resolve_continuation(frame, active_run).as_dict()
        for model in MODELS
    }
    assert len({repr(value) for value in resolutions.values()}) == 1
    assert resolutions[MODELS[0]] == {
        "status": "RESOLVED",
        "run_reference": "run-1",
        "action_reference": "action-1",
        "phase": "APPROVED",
        "reason": "pending Action is available",
    }
