import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from src.capability_dependencies import (
    DEPENDENCY_REGISTRY,
    HOST_PACKAGE_ALLOWLIST,
    REGISTRY,
    DependencyStatus,
    artifact_manager,
    dependency_manager,
    inspect_capability_dependencies,
    inspect_action_dependencies,
    inspect_dependency,
    verify,
)
from src.capability_registry import capability_for_tool


def test_shared_resource_backend_exposes_one_contract_vocabulary_without_secrets():
    contracts = dependency_manager.contracts()
    assert {item["dependency_id"] for item in contracts["dependencies"]} >= {"binary.nmap", "binary.iproute2"}
    assert "artifact.huggingface_snapshot" in {item["artifact_id"] for item in contracts["artifacts"]}
    assert "runtime.ollama" in {item["runtime_id"] for item in contracts["runtimes"]}
    assert "secret_value" not in json.dumps(contracts)


def test_missing_host_dependency_is_typed_and_requires_normal_authority():
    inspected = inspect_dependency("binary.nmap", available_executables=[], platform_key="arch")
    assert inspected["status"] == DependencyStatus.REQUIRES_APPROVAL.value
    assert inspected["installation_class"] == "HOST_PACKAGE"
    assert inspected["package"] == "nmap"
    plan = dependency_manager.ensure("network.discover_hosts", available_executables=[], platform_key="arch")
    assert plan["status"] == DependencyStatus.REQUIRES_APPROVAL.value
    assert plan["packages"] == ["nmap"]
    assert plan["resume_original_objective"] is True
    assert plan["execution_authority"] == "canonical_broker_or_ssh_capability"


def test_available_dependency_does_not_create_an_install_action():
    result = inspect_capability_dependencies("network.discover_hosts", available_executables=["nmap"], platform_key="arch")
    assert result["status"] == DependencyStatus.AVAILABLE.value
    plan = dependency_manager.resolve("network.discover_hosts", available_executables=["nmap"], platform_key="arch")
    assert plan["action"] == "none"
    assert plan["resume_original_objective"] is False


def test_verification_failure_and_version_mismatch_are_not_capability_gaps():
    broken = verify("binary.nmap", observed_executables=["nmap"], platform_key="arch", verification_ok=False)
    assert broken["status"] == DependencyStatus.BROKEN.value
    assert broken["verified"] is False

    mismatch = inspect_dependency("binary.nmap", available_executables=["nmap"], versions={"nmap": "6.4"}, platform_key="arch")
    assert mismatch["status"] == DependencyStatus.VERSION_MISMATCH.value


def test_action_spec_declares_prerequisite_without_granting_install_authority():
    action = capability_for_tool("manage_homelab").actions["execute_network_discovery"]
    assert action.dependencies == ("binary.nmap",)
    assert action.approval.value == "exact"
    assert action.executor_key == "manage_homelab"


def test_action_dependency_projection_uses_the_registered_action_contract():
    inspected = inspect_action_dependencies(
        "manage_homelab", "execute_network_discovery",
        available_executables=[], platform_key="arch",
    )
    assert inspected["canonical_source"] == "ActionSpec.dependencies"
    assert [item["dependency_id"] for item in inspected["dependencies"]] == ["binary.nmap"]
    assert inspected["status"] == DependencyStatus.REQUIRES_APPROVAL.value
    assert dependency_manager.inspect_action(
        "manage_homelab", "plan_service_restart", available_executables=[], platform_key="arch"
    )["dependencies"] == []


def test_action_dependency_plan_preserves_same_action_and_uses_bounded_installation():
    plan = dependency_manager.ensure_action(
        "manage_homelab", "execute_network_discovery",
        available_executables=[], platform_key="arch", target_asset="lab-network",
    )
    assert plan["action"] == "host_or_remote_package_install"
    assert plan["packages"] == ["nmap"]
    assert plan["target_asset"] == "lab-network"
    assert plan["resume_original_objective"] is True
    assert plan["resume_same_action"] is True
    assert plan["execution_authority"] == "canonical_broker_or_ssh_capability"


def test_action_dependency_plan_blocks_unknown_action_without_install_metadata():
    plan = dependency_manager.ensure_action(
        "manage_homelab", "not_registered", available_executables=[], platform_key="arch",
    )
    assert plan["action"] == "blocked"
    assert plan["resume_original_objective"] is False
    assert "packages" not in plan


def test_legacy_admin_ssh_action_delegates_to_hardened_transport(monkeypatch):
    from src import builtin_actions

    captured = {}

    def fake_run_ssh_command(remote, port, command, **kwargs):
        captured.update({"remote": remote, "port": port, "command": command, **kwargs})
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(builtin_actions, "run_ssh_command", fake_run_ssh_command)
    output, success = asyncio.run(
        builtin_actions.action_ssh_command(
            "owner", command="systemctl status jellyfin", host="admin@thanatos",
            ssh_port="2222",
        )
    )
    assert (output, success) == ("ok", True)
    assert captured == {
        "remote": "admin@thanatos", "port": "2222",
        "command": "systemctl status jellyfin", "timeout": 120,
        "connect_timeout": 10, "strict_host_key_checking": True,
    }


def test_cookbook_user_package_allowlist_is_owned_by_dependency_manager():
    approved = dependency_manager.plan_user_package("hf_transfer")
    assert approved["status"] == "READY_FOR_ADAPTER"
    assert approved["installation_class"] == "USER_SCOPED"
    assert approved["installer_id"] == "installer.user_pip"
    assert dependency_manager.plan_user_package("https://evil.example/x.whl")["status"] == "UNSUPPORTED"


def test_local_cookbook_system_install_projects_to_privileged_broker():
    source = (Path(__file__).parents[1] / "routes" / "shell_routes.py").read_text()
    start = source.index('async def install_system_deps')
    end = source.index('async def rebuild_engine', start)
    endpoint = source[start:end]
    assert 'client_request' in endpoint
    assert '"action": "install_packages"' in endpoint
    assert '"execution_authority": "privileged_broker"' in endpoint


def test_cookbook_host_package_mapping_is_owned_by_dependency_manager():
    plan = dependency_manager.plan_host_packages(["build-essential", "tmux", "not-reviewed"])
    assert plan["requested"] == ["build-essential", "tmux"]
    assert plan["rejected"] == ["not-reviewed"]
    assert plan["packages_by_manager"]["pacman"] == ["base-devel", "tmux"]
    assert plan["packages_by_manager"]["dnf"] == ["gcc", "gcc-c++", "make", "tmux"]
    assert plan["approval_required"] is True


def test_remote_package_projection_reuses_host_allowlist_and_marks_ssh_boundary():
    plan = dependency_manager.plan_remote_packages(
        ["nmap", "not-reviewed"], target_asset="asset-thanatos",
    )
    assert plan["status"] == "READY_FOR_ADAPTER"
    assert plan["requested"] == ["nmap"]
    assert plan["installation_class"] == "REMOTE_PACKAGE"
    assert plan["installer_id"] == "installer.remote_ssh"
    assert plan["target_asset"] == "asset-thanatos"
    assert plan["execution_authority"] == "canonical_ssh"
    assert plan["approval_required"] is True

    missing_target = dependency_manager.plan_remote_packages(["nmap"], target_asset=None)
    assert missing_target["status"] == "UNSUPPORTED"
    assert missing_target["reason"] == "remote_target_asset_required"


def test_cookbook_host_packages_are_accepted_by_the_privileged_broker():
    from src.privileged_broker import ALLOWED_PACKAGES

    assert HOST_PACKAGE_ALLOWLIST <= ALLOWED_PACKAGES


def test_legacy_dependency_operations_are_only_a_projection_of_typed_specs():
    assert REGISTRY["network_discovery"].executables == (DEPENDENCY_REGISTRY["binary.nmap"].binary,)
    assert REGISTRY["network_interface_inspection"].executables == ("ip", "ss")
    assert REGISTRY["network_interface_inspection"].packages == {"arch": "iproute2", "debian": "iproute2", "ubuntu": "iproute2"}
    assert REGISTRY["dns_diagnostics"].executables == ("dig", "host", "nslookup")
    assert REGISTRY["dns_diagnostics"].packages == {"arch": "bind", "debian": "bind9", "ubuntu": "bind9"}


def test_legacy_health_projection_is_served_by_the_shared_dependency_manager():
    result = dependency_manager.inspect_operation(
        "network_discovery", available=[], platform_key="arch",
    )
    assert result["canonical_source"] == "DEPENDENCY_REGISTRY"
    assert result["missing_executables"] == ["nmap"]
    assert result["packages"] == ["nmap"]


def test_artifact_manager_rejects_unknown_artifact_and_keeps_source_opaque():
    assert artifact_manager.plan_artifact("artifact.unknown")["status"] == "UNSUPPORTED"
    plan = artifact_manager.plan_artifact("artifact.huggingface_snapshot", source_reference="org/model")
    assert plan["status"] == "READY_FOR_ADAPTER"
    assert plan["resumable"] is True
    assert plan["source_policy"] == "huggingface_allowlisted_transport"


def test_shared_artifact_manager_projects_known_cookbook_runtimes():
    ollama = artifact_manager.plan_runtime_for_command(
        "ollama serve qwen3:8b", platform_key="linux",
    )
    assert ollama["runtime_id"] == "runtime.ollama"
    assert ollama["status"] == "READY_FOR_ADAPTER"
    assert ollama["artifacts"][0]["artifact_id"] == "artifact.ollama_model"

    vllm = artifact_manager.plan_runtime_for_command(
        "vllm serve org/model", platform_key="macos",
    )
    assert vllm["status"] == "UNSUPPORTED"
    assert vllm["reason"] == "unsupported_platform"


def test_unknown_cookbook_command_remains_compatibility_adapter_input():
    assert artifact_manager.plan_runtime_for_command("custom-server --model x") is None


def test_canonical_homelab_path_uses_dependency_manager_directly():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "homelab_operations.py").read_text(encoding="utf-8")
    assert "from src.capability_dependencies import capability_health" not in source
    assert "capability_health(" not in source
    assert "remediation_handoff(" not in source
    assert "dependency_manager.inspect_operation" in source
    assert "dependency_manager.resume_receipt" in source


def test_canonical_status_projections_do_not_call_compatibility_health_wrapper():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    persistent = (root / "src" / "persistent_agent.py").read_text(encoding="utf-8")
    intelligence = (root / "routes" / "intelligence_routes.py").read_text(encoding="utf-8")
    assert "from src.capability_dependencies import capability_health" not in persistent
    assert "from src.capability_dependencies import capability_health" not in intelligence
    assert "dependency_manager.inspect_operation" in persistent
    assert "dependency_manager.inspect_operation" in intelligence


def test_cookbook_download_uses_artifact_projection_without_a_second_dependency_owner():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "routes" / "cookbook_routes.py").read_text(encoding="utf-8")
    assert "from src.capability_dependencies import artifact_manager, dependency_manager" not in source
    assert "artifact_manager.plan_artifact" in source


def test_teacher_escalation_reenters_canonical_aci_path():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    loop = (root / "src" / "agent_loop.py").read_text(encoding="utf-8")
    teacher = (root / "src" / "teacher_escalation.py").read_text(encoding="utf-8")
    assert '_aci_enabled = _aci_mode in {"shadow", "aci"}' in loop
    assert 'and not _is_teacher_run' not in loop.split("_aci_enabled =", 1)[1].split("\n", 1)[0]
    teacher_call = teacher.split("async for evt_str in stream_aci_turn(", 1)[1].split("):", 1)[0]
    assert 'aci_mode="aci"' in teacher_call


def test_network_remediation_projection_is_owned_by_intent_contracts():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    loop = (root / "src" / "agent_loop.py").read_text(encoding="utf-8")
    contracts = (root / "src" / "intent_contracts.py").read_text(encoding="utf-8")
    assert "def explicitly_allows_diagnostic_install" in contracts
    assert "def network_substantive_fallback_command" in contracts
    assert "def _explicitly_allows_diagnostic_install" not in loop
    assert "def _network_substantive_fallback_command" not in loop


def test_foreground_chat_cannot_select_legacy_or_shadow_orchestration():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    assert 'aci_mode="aci"' in source
    assert 'get_setting("hades_aci_mode"' not in source


def test_aci_domain_projection_comes_from_canonical_tool_bindings():
    from src.tool_bindings import tools_for_domains

    network = tools_for_domains({"network_ops"})
    assert "manage_homelab" in network
    assert "bash" not in network
    assert "run_shell" not in network

    assets = tools_for_domains({"asset_inventory"})
    assert assets == {"manage_assets", "privileged_action"}


def test_all_nonlegacy_stream_callers_explicitly_enter_aci():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    callers = []
    legacy_alias_calls = []
    for base in (root / "routes", root / "src", root / "core"):
        for path in base.rglob("*.py"):
            if path.name == "agent_loop.py" or path == root / "src" / "aci.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)
                if name not in {"stream_aci_turn", "stream_agent_loop"}:
                    continue
                callers.append(path)
                if name == "stream_agent_loop":
                    legacy_alias_calls.append((path, node.lineno))
                mode = next((kw.value for kw in node.keywords if kw.arg == "aci_mode"), None)
                assert isinstance(mode, ast.Constant) and mode.value == "aci", (
                    f"non-ACI production caller: {path}:{node.lineno}"
                )
    assert callers
    assert not legacy_alias_calls, f"legacy stream aliases remain: {legacy_alias_calls}"


def test_authoritative_dogfood_runner_enters_through_aci():
    """Dogfood evidence must exercise the production control-plane seam."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "scripts" / "hades_dogfood.py").read_text(encoding="utf-8")
    assert "from src.aci import stream_aci_turn" in source
    assert "from src.agent_loop import stream_agent_loop" not in source
    assert "async for chunk in stream_aci_turn(" in source


def test_aci_projection_failure_cannot_silently_reenter_legacy_router():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "agent_loop.py").read_text(encoding="utf-8")
    block = source.split('logger.exception("[hades-aci] packet construction failed")', 1)[1].split(
        "    # A caller/RAG route", 1
    )[0]
    assert 'if _aci_mode == "aci"' in block
    assert '_aci_model_fallback_reason = "aci_projection_failure"' in block
    assert '_aci_enabled = False' not in block.split("else:", 1)[0]


def test_tool_policy_name_discovery_does_not_import_legacy_prompt_registry():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "tool_policy.py").read_text(encoding="utf-8")
    assert "from src.agent_loop import TOOL_SECTIONS" not in source
    from src.tool_policy import known_tool_names
    names = known_tool_names()
    assert {"bash", "manage_research", "generate_image"} <= names
