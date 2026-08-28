from routes import chat_routes


def test_post_response_failure_cannot_abort_terminal_delivery_boundary(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError("optional post-response failure")

    monkeypatch.setattr(chat_routes, "run_post_response_tasks", fail)

    # The wrapper deliberately absorbs optional work failures. The enclosing
    # stream can therefore continue to its single terminal [DONE] emission.
    assert chat_routes._run_post_response_tasks_safely("session") is None
    assert len(calls) == 1
