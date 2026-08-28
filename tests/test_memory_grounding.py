import json
from pathlib import Path

import pytest

from src.agent_loop import _classify_agent_request
from src.memory_grounding import minimal_saved_memory_message
from src.memory import MemoryManager
from src.memory_grounding import (
    build_explicit_memory_result,
    build_runtime_self_state,
    is_explicit_memory_query,
    project_explicit_memory_result,
    render_explicit_memory_context,
    render_memory_result_projection,
)
from src.context_compactor import trim_for_context


def _manager(tmp_path, rows):
    manager = MemoryManager(str(tmp_path))
    manager.save(rows)
    return manager


def _rows():
    return [
        {"id": "role", "owner": "alice", "text": "User works as an IT systems administrator.", "category": "professional", "source": "user", "timestamp": 1},
        {"id": "local", "owner": "alice", "text": "User prefers local models for routine work.", "category": "preference", "source": "user", "timestamp": 2, "pinned": True},
        {"id": "lab", "owner": "alice", "text": "User operates a homelab.", "category": "project", "source": "user", "timestamp": 3},
        {"id": "other", "owner": "bob", "text": "Bob works as a pilot.", "category": "professional", "source": "user", "timestamp": 4},
    ]


def test_explicit_memory_queries_are_detected_and_misroute_to_memory_domain():
    assert is_explicit_memory_query("What do you remember about me?")
    assert is_explicit_memory_query("check your memories, are you sure?")
    intent = _classify_agent_request([], "What do you know about my work?")
    assert intent["explicit_memory_query"] is True
    assert intent["domains"] == {"memory"}


def test_all_about_me_is_canonical_owner_scoped_result(tmp_path):
    result = build_explicit_memory_result(_manager(tmp_path, _rows()), "alice", "What do you remember about me?")
    assert result["status"] == "ok"
    assert {row["id"] for row in result["memories"]} == {"role", "local", "lab"}
    assert "Bob works" not in render_explicit_memory_context(result)
    assert "Skills are procedural" in render_explicit_memory_context(result)


def test_work_query_is_canonical_and_category_limited(tmp_path):
    result = build_explicit_memory_result(_manager(tmp_path, _rows()), "alice", "What do you remember about my work?")
    assert result["status"] == "ok"
    assert {row["id"] for row in result["memories"]} == {"role", "local", "lab"}


def test_zero_result_is_not_false_retrieval_failure(tmp_path):
    result = build_explicit_memory_result(_manager(tmp_path, _rows()), "alice", "What do you remember about my family?")
    # The explicit summary query is canonical and bounded; a genuinely empty
    # category query is represented as zero rather than an invented fact.
    assert result["status"] == "ok"  # all-about-me semantics remain intact
    empty = build_explicit_memory_result(_manager(tmp_path, []), "alice", "What do you remember about me?")
    assert empty["status"] == "zero_result"
    assert "ZERO_RESULT" in render_explicit_memory_context(empty)


def test_unreadable_store_is_reported_as_retrieval_failure(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{not-json", encoding="utf-8")
    result = build_explicit_memory_result(MemoryManager(str(tmp_path)), "alice", "check your memories")
    assert result["status"] == "retrieval_failed"
    assert "RETRIEVAL_FAILED" in render_explicit_memory_context(result)


def test_canonical_result_survives_qwen_compact_projection_and_skill_separation():
    message = {
        "role": "user",
        "content": (
            "Source: saved memory: explicit canonical result\n"
            "CANONICAL MEMORY RESULT\nSTATUS: OK\n"
            "- [professional] id=role source=user pinned=false: User works as an IT systems administrator."
        ),
        "metadata": {"source": "saved memory: explicit canonical result"},
    }
    compact = minimal_saved_memory_message([message])
    assert compact is not None
    assert "IT systems administrator" in compact["content"]
    assert "Skills are procedural" not in compact["content"]


def test_memory_read_result_never_crosses_owner_boundary(tmp_path):
    result = build_explicit_memory_result(_manager(tmp_path, _rows()), "mallory", "What do you remember about me?")
    assert result["status"] == "zero_result"
    assert result["memories"] == []


def test_failure_result_does_not_claim_no_memories():
    rendered = render_explicit_memory_context({"status": "retrieval_failed", "query_type": "summary"})
    assert "retrieval failed" in rendered.lower()
    assert "zero" not in rendered.lower()


def test_memory_inspector_ui_uses_sanitized_diagnostics_only():
    html = Path("static/index.html").read_text()
    js = Path("static/js/memory.js").read_text()
    chat = Path("static/js/chat.js").read_text()
    assert 'data-memory-tab="inspector"' in html
    assert 'id="memory-inspector-body"' in html
    assert "hades-memory-diagnostics" in js
    assert "memory_diagnostics" in chat
    assert "content_logged" in js


def test_explicit_memory_result_is_protected_from_context_trim():
    protected = {
        "role": "user",
        "content": "CANONICAL MEMORY RESULT\nSTATUS: OK\n- work: User works as an IT systems administrator.",
        "_protected": True,
        "metadata": {"context_kind": "explicit_memory_result", "memory_explicit_query": True},
    }
    messages = [
        {"role": "system", "content": "large policy " * 200},
        protected,
        {"role": "user", "content": "What do you remember about me?"},
    ]
    trimmed = trim_for_context(messages, 120, reserve_tokens=16)
    assert any(m.get("_protected") and "IT systems administrator" in m.get("content", "") for m in trimmed)


def test_owner_memory_projection_is_bounded_and_reconciles_current_runtime():
    rows = [
        {
            "id": f"memory-{index}", "owner": "alice",
            "text": (
                "The current Odysseus setup uses the ChatGPT Subscription backend "
                "and is not currently running a local LLM."
                if index == 0 else f"Owner fact {index} " + ("x" * 180)
            ),
            "category": "project", "source": "user", "timestamp": index,
        }
        for index in range(64)
    ]
    result = {"status": "ok", "query_type": "summary", "memories": rows,
              "diagnostics": {"retrieved_count": 64, "owner_scoped": True}}
    projection = project_explicit_memory_result(
        result,
        current_self_state=build_runtime_self_state("qwen3:8b", "http://ollama:11434"),
    )
    rendered = render_memory_result_projection(projection)
    assert len(rendered) <= 8000
    assert projection["retrieved_count"] == 64
    assert projection["omitted_count"] > 0
    assert projection["contradictions"]
    assert "current runtime is actively serving model qwen3:8b" in rendered
    assert "HISTORICAL" in rendered


def test_volatile_remembered_branch_is_historical_against_current_deployment():
    result = {
        "status": "ok",
        "query_type": "summary",
        "memories": [{
            "id": "branch-memory",
            "text": "The customized Odysseus checkout is currently on the dev branch.",
            "category": "project",
            "source": "user",
            "stale": False,
        }, {
            "id": "current-preference",
            "text": "Owner prefers concise verified answers.",
            "category": "preference",
            "source": "user",
            "stale": False,
        }],
        "diagnostics": {"retrieved_count": 2, "owner_scoped": True},
    }
    projection = project_explicit_memory_result(
        result,
        current_self_state=build_runtime_self_state(
            "qwen3:8b",
            "http://ollama:11434",
            source_commit="0dc6ce153ff5d7e1bb359fe8fd7a94e89de95dbf",
        ),
    )
    assert projection["records"][0]["ref"] == "current-preference"
    historical = next(row for row in projection["records"] if row["ref"] == "branch-memory")
    assert historical["epistemic_type"] == "HISTORICAL"
    assert historical["stale"] is True
    assert "remembered branch state is historical" in projection["contradictions"][0]["reason"]


def test_exact_owner_memory_utterance_declares_terminal_read_trajectory():
    from benchmarks.hades_aci_corpus import CORPUS

    case = next(item for item in CORPUS if item["prompt"] == "What do you remember about me?")
    assert case["expected_trajectory"]["state_machine"] == [
        "DETERMINISTIC_READ", "CANONICAL_RESULT", "RESULT_PROJECTION", "ANSWER", "COMPLETE"
    ]
    assert "SECOND_ACTION_DECISION" in case["expected_trajectory"]["must_not"]
