"""Focused regression coverage for the first-class inventory/privilege tools."""

import argparse
import json

import pytest

from src import asset_inventory as inventory
from src.agent_loop import (
    _assemble_prompt,
    _asset_read_request,
    _is_explicit_continuation,
    _privileged_action_requires_exact_approval,
)
from src.privileged_broker import (
    peer_is_allowed,
    validate_packages,
)
from src.tool_capabilities import (
    ToolRunSecurityContext,
    capabilities_for_action,
)
from src.tool_execution import _ody_v34_asset_argv
from src.tool_parsing import parse_tool_blocks
from src.tool_policy import ToolPolicy


def _asset_args(**overrides):
    values = {
        "id": None,
        "name": "asset",
        "type": "unknown",
        "status": "active",
        "manufacturer": None,
        "model": None,
        "serial": None,
        "system_uuid": None,
        "hostname": None,
        "mac": None,
        "location": None,
        "notes": None,
        "source": "test",
        "confidence": 1.0,
        "attributes": None,
        "asset": None,
        "kind": "observation",
        "text": None,
        "json": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_broker_accepts_allowlisted_packages_and_rejects_shell_inputs():
    assert validate_packages(["nmap", "iproute2", "ethtool"]) == [
        "nmap",
        "iproute2",
        "ethtool",
    ]

    invalid = [
        ["curl"],
        ["https://example.invalid/pkg.deb"],
        ["/tmp/package.deb"],
        ["--no-install-recommends"],
        ["nmap;id"],
        ["nmap && id"],
        ["nmap name"],
        ["bad package!"],
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            validate_packages(value)


def test_broker_peer_boundary_requires_pid_uid_and_gid():
    assert peer_is_allowed(1, 1000, 1000, 1, 1000, 1000)
    assert not peer_is_allowed(2, 1000, 1000, 1, 1000, 1000)
    assert not peer_is_allowed(1, 1001, 1000, 1, 1000, 1000)
    assert not peer_is_allowed(1, 1000, 1001, 1, 1000, 1000)


def test_privileged_actions_are_action_aware_and_policy_still_wins():
    status = capabilities_for_action(
        "privileged_action", {"action": "status"}
    )
    assert status.known
    assert not status.effects
    assert not _privileged_action_requires_exact_approval(
        "privileged_action", json.dumps({"action": "status"})
    )

    install_content = json.dumps(
        {"action": "install_packages", "packages": ["nmap"]}
    )
    assert _privileged_action_requires_exact_approval(
        "privileged_action", install_content
    )

    security = ToolRunSecurityContext(external_untrusted_context_seen=True)
    assert security.decision_for("privileged_action", {"action": "status"}).allowed
    assert not security.decision_for(
        "privileged_action", {"action": "install_packages", "packages": ["nmap"]}
    ).allowed

    policy = ToolPolicy(disabled_tools=frozenset({"privileged_action"}))
    assert policy.blocks("privileged_action")


def test_asset_identity_and_relationships_use_temporary_database(monkeypatch, tmp_path):
    monkeypatch.setattr(inventory, "DB_PATH", tmp_path / "assets.db")
    inventory.cmd_add(
        _asset_args(
            name="physical-host",
            type="computer",
            serial="SERIAL-1",
            system_uuid="UUID-1",
        )
    )
    inventory.cmd_add(
        _asset_args(
            name="runtime",
            type="container",
            attributes=json.dumps({"ip": "172.18.0.2"}),
        )
    )
    inventory.cmd_add(
        _asset_args(
            name="other-runtime",
            type="container",
            attributes=json.dumps({"ip": "172.18.0.2"}),
        )
    )

    conn = inventory.db()
    assert inventory.resolve(conn, "SERIAL-1")["name"] == "physical-host"
    assert conn.execute("SELECT count(*) FROM assets").fetchone()[0] == 3

    runtime = inventory.resolve(conn, "runtime")
    host = inventory.resolve(conn, "physical-host")
    inventory.cmd_observe(
        _asset_args(asset=runtime["id"], kind="test", text="seen")
    )
    inventory.cmd_link(
        argparse.Namespace(
            parent=host["id"],
            child=runtime["id"],
            relation="runs_on",
            source="test",
            notes=None,
        )
    )
    assert conn.execute(
        "SELECT count(*) FROM observations"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT count(*) FROM relationships WHERE relation='runs_on'"
    ).fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize(
    ("action", "payload", "expected"),
    [
        ("summary", {}, ["summary"]),
        ("list", {"limit": 3}, ["list", "--limit", "3"]),
        ("search", {"query": "host"}, ["search", "host"]),
        ("get", {"asset": "host"}, ["get", "host"]),
        ("add", {"name": "host"}, ["add", "--name", "host"]),
        ("update", {"asset": "host", "name": "new"}, ["update", "host", "--name", "new"]),
        ("record_observation", {"kind": "scan", "data": {"ok": True}}, ["observe", "--kind", "scan", "--json", '{"ok": true}']),
        ("link_component", {"parent": "host", "child": "runtime"}, ["link", "host", "runtime", "--relation", "installed_in"]),
        ("unlink_component", {"parent": "host", "child": "runtime"}, ["unlink", "--parent", "host", "--child", "runtime", "--relation", "installed_in"]),
        ("retire", {"asset": "host"}, ["retire", "host"]),
        ("merge", {"source_asset": "old", "target_asset": "new"}, ["merge", "old", "new"]),
    ],
)
def test_manage_assets_dispatch_mapping(action, payload, expected):
    argv = _ody_v34_asset_argv({"action": action, **payload})
    assert argv[0:3] == [argv[0], "-m", "src.asset_inventory"]
    assert argv[3:] == expected


def test_strict_text_contracts_and_fenced_code_safety():
    prompt = _assemble_prompt(
        {"manage_assets", "privileged_action"},
        disabled_tools=set(),
        compact=False,
        intent_domains={"asset_inventory"},
    )
    assert "### `manage_assets`" in prompt
    assert "### `privileged_action`" in prompt
    assert '<invoke name="manage_assets">' in prompt
    assert '<invoke name="privileged_action">' in prompt
    assert parse_tool_blocks("```manage_assets\n{}\n```", skip_fenced=True) == []


def test_explicit_it_asset_reads_select_canonical_domain_without_shell_fallback():
    assert _asset_read_request("Explain my current IT asset inventory, what do I have?")
    assert _asset_read_request("What servers do I have?")
    assert _asset_read_request("Show unidentified devices")
    assert _asset_read_request("What do we know about Cerberus?")
    assert not _asset_read_request("Update the asset hostname")


def test_canonical_asset_reads_are_read_only_and_need_no_approval():
    from src.capability_registry import action_for_tool, requires_exact_approval
    action = action_for_tool("manage_assets", {"action": "list"})
    assert action.effects == ("read_private",)
    assert action.approval.value == "none"
    assert requires_exact_approval("manage_assets", {"action": "list"}) is False


@pytest.mark.asyncio
async def test_manage_assets_read_returns_structured_canonical_result(monkeypatch):
    import src.tool_execution as tool_execution

    class Completed:
        returncode = 0
        stdout = '[{"id":"cerberus","name":"Cerberus","type":"server","status":"active"}]'
        stderr = ""

    monkeypatch.setattr(tool_execution._ody_v34_subprocess, "run", lambda *args, **kwargs: Completed())
    block = type("Block", (), {"content": json.dumps({"action": "list", "limit": 500})})()
    binding, result = await tool_execution._execute_manage_assets_binding(block, owner="alice")
    assert binding == "manage_assets"
    assert result["exit_code"] == 0
    assert result["data"]["status"] == "SUCCESS"
    assert result["data"]["assets"][0]["id"] == "cerberus"
    assert result["data"]["owner_scope"] == "alice"


@pytest.mark.asyncio
async def test_manage_assets_read_failure_is_not_zero_inventory(monkeypatch):
    import src.tool_execution as tool_execution

    class Completed:
        returncode = 1
        stdout = ""
        stderr = "CMDB unavailable"

    monkeypatch.setattr(tool_execution._ody_v34_subprocess, "run", lambda *args, **kwargs: Completed())
    block = type("Block", (), {"content": json.dumps({"action": "list"})})()
    _, result = await tool_execution._execute_manage_assets_binding(block, owner="alice")
    assert result["exit_code"] == 1
    assert "error" in result
    assert "assets" not in result.get("data", {})


@pytest.mark.parametrize(
    "text",
    [
        "Continue",
        "please continue",
        "continue please",
        "yes, continue",
        "yes, please continue",
        "go ahead",
        "keep going",
        "proceed",
        "resume",
        "carry on",
    ],
)
def test_general_continuation_phrases(text):
    assert _is_explicit_continuation(text)


@pytest.mark.parametrize(
    "text",
    [
        "thanks",
        "okay, what is DNS?",
        "yes, search the web for X",
        "please inspect the unrelated repository",
    ],
)
def test_substantive_requests_do_not_inherit_stale_context(text):
    assert not _is_explicit_continuation(text)
