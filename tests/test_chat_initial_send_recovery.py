from pathlib import Path


def test_chat_default_model_bootstrap_retries_transient_startup_read():
    source = (Path(__file__).parents[1] / "static/js/chat.js").read_text(encoding="utf-8")
    assert "for (let attempt = 0; attempt < 3; attempt += 1)" in source
    assert "fetch('/api/default-chat', { credentials: 'same-origin' })" in source
    assert "setTimeout(resolve, 250)" in source
