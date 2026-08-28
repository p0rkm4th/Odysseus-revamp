"""Regression for persisted canonical answers with tool audit metadata."""

from pathlib import Path


RENDERER = Path(__file__).resolve().parents[1] / "static/js/chatRenderer.js"


def test_tool_history_fallback_renders_persisted_answer_when_round_texts_absent():
    source = RENDERER.read_text(encoding="utf-8")
    assert "Canonical deterministic reads persist their authoritative answer" in source
    assert "if (!lastMsgAi && String(textRaw || '').trim())" in source
    assert "markdownModule.processWithThinking(text)" in source
    assert "wrap.dataset.dbId = metadata._db_id" in source
