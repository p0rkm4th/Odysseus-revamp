import asyncio
import json
from types import SimpleNamespace

from src.intent_contracts import compile_intent, resolve_intent
from src.tool_execution import NO_TOOL_SECURITY_CONTEXT, execute_tool_block


def _block(payload):
    return SimpleNamespace(tool_type="developer_read", content=json.dumps(payload))


def test_developer_read_phrasing_resolves_to_canonical_contract():
    cases = {
        "Search the code for build_candidate": "search_code",
        "Read src/app.py": "view_file_region",
        "Show me the repo map": "show_repo_map",
    }
    for utterance, action in cases.items():
        frame = compile_intent(utterance)
        resolved = resolve_intent(frame)
        assert frame.domain_concept == "DEVELOPER"
        assert frame.operation_class == "READ"
        assert resolved.action_id == action
        assert resolved.binding_name == "developer_read"


def test_developer_explanation_does_not_enter_read_contract():
    frame = compile_intent("Explain what a repository map is")
    assert frame.domain_concept != "DEVELOPER"


def test_developer_read_adapter_is_workspace_confined(tmp_path, monkeypatch):
    monkeypatch.setattr("src.tool_execution.owner_is_admin_or_single_user", lambda owner: True)
    (tmp_path / "app.py").write_text("def build_candidate():\n    return True\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("workspace notes\n", encoding="utf-8")

    async def run(payload):
        return await execute_tool_block(
            _block(payload), owner="admin", workspace=str(tmp_path),
            security_context=NO_TOOL_SECURITY_CONTEXT,
        )

    _, search = asyncio.run(run({"action": "search_code", "query": "build_candidate"}))
    assert search["exit_code"] == 0
    assert search["data"]["workspace_scoped"] is True
    assert "app.py" in search["output"]

    _, view = asyncio.run(run({"action": "view_file_region", "path": "app.py", "start_line": 1, "end_line": 1}))
    assert view["exit_code"] == 0
    assert "build_candidate" in view["output"]

    _, repo_map = asyncio.run(run({"action": "show_repo_map", "query": "*.py"}))
    assert repo_map["exit_code"] == 0
    assert "app.py" in repo_map["output"]

    _, blocked = asyncio.run(run({"action": "view_file_region", "path": "/etc/hosts"}))
    assert blocked["exit_code"] == 1
    assert "outside the allowed roots" in blocked["error"] or "outside the workspace" in blocked["error"]


def test_developer_read_returns_explicit_bounded_status_and_line_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr("src.tool_execution.owner_is_admin_or_single_user", lambda owner: True)
    source = tmp_path / "app.py"
    source.write_text("\n".join(f"line_{i}" for i in range(1, 130)), encoding="utf-8")

    async def run(payload):
        return await execute_tool_block(
            _block(payload), owner="admin", workspace=str(tmp_path),
            security_context=NO_TOOL_SECURITY_CONTEXT,
        )

    _, view = asyncio.run(run({"action": "view_file_region", "path": "app.py"}))
    assert view["success"] is True
    assert view["data"]["status"] == "SUCCESS_WITH_OUTPUT"
    assert view["data"]["start_line"] == 1
    assert "     1\tline_1" in view["output"]
    assert "   100\tline_100" in view["output"]
    assert "line_101" not in view["output"]

    _, empty = asyncio.run(run({"action": "search_code", "query": "does_not_exist"}))
    assert empty["success"] is True
    assert empty["data"]["status"] == "SUCCESS_WITH_OUTPUT"
    assert "No matches" in empty["output"]
