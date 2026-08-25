from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.economic_mandates import BudgetUsage, EconomicRuntimeControls, evaluate_economic_action
from core.telegram_models import TelegramApprovalCallback, TelegramConnection, TelegramPairingCode
from src.economic_mandates import EconomicAction
from src.osint_policy import OsintPolicyError, build_plan, validate_request
from src.telegram_store import TelegramStore, TelegramStoreError
from src.homelab_operations import HomelabOperationError, HomelabOperations, HomelabReceiptStore, _parse_nmap_services, _parse_nmap_xml
import asyncio


def test_economic_control_plane_defaults_to_kill_switch_and_no_execution():
    decision = evaluate_economic_action(
        None, EconomicAction.RESEARCH_OPPORTUNITY,
        usage_after_action=BudgetUsage(), owner="alice",
        controls=EconomicRuntimeControls(),
    )
    assert not decision.allowed
    assert "configured" in decision.reason


def test_osint_rejects_private_and_credential_targets():
    for target in ("http://127.0.0.1:7000", "https://user:pass@example.com", "192.168.1.10"):
        try:
            validate_request({"action": "plan", "target": target})
        except OsintPolicyError:
            pass
        else:
            raise AssertionError(target)
    action, target, objective, sources = validate_request({"action": "plan", "target": "example.com"})
    plan = build_plan(target, objective, sources)
    assert action == "plan"
    assert plan["scope"] == "public_source_only"


def test_telegram_pairing_is_one_use_and_callback_is_one_use():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    store = TelegramStore(db)
    issued = store.issue_pairing_code(owner="alice")
    connection = store.claim_pairing_code(code=issued.code, telegram_user_id=7, private_chat_id=7, display_username="alice")
    assert connection.owner == "alice"
    try:
        store.claim_pairing_code(code=issued.code, telegram_user_id=7, private_chat_id=7)
    except TelegramStoreError:
        pass
    else:
        raise AssertionError("pairing code was reusable")
    callback = store.create_approval_callback(
        owner="alice", telegram_user_id=7, private_chat_id=7,
        odysseus_session_id="session-1", approval_digest="a" * 64,
        allowed_decision="approve",
    )
    consumed = store.consume_approval_callback(
        owner="alice", telegram_user_id=7, private_chat_id=7,
        callback_data="a:" + callback.opaque_id,
    )
    assert consumed.opaque_id == callback.opaque_id
    try:
        store.consume_approval_callback(
            owner="alice", telegram_user_id=7, private_chat_id=7,
            callback_data="a:" + callback.opaque_id,
        )
    except TelegramStoreError:
        pass
    else:
        raise AssertionError("approval callback was reusable")


def test_homelab_network_plan_is_private_and_nmap_candidates_are_review_only(tmp_path):
    async def runner(argv, timeout):
        return 0, "active"

    async def run():
        ops = HomelabOperations(receipt_store=HomelabReceiptStore(tmp_path / "receipts.jsonl"), runner=runner)
        planned = await ops.execute({"action": "plan_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED"}, owner="alice")
        assert planned["target"] == "192.168.10.0/24"
        assert "asset_draft_candidates" not in planned
        try:
            await ops.execute({"action": "plan_network_discovery", "cidr": "8.8.8.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED"}, owner="alice")
        except HomelabOperationError:
            pass
        else:
            raise AssertionError("public discovery scope was accepted")

    asyncio.run(run())
    xml = '<nmaprun><host><status state="up"/><address addr="192.168.10.4" addrtype="ipv4"/><address addr="AA:BB:CC:DD:EE:FF" addrtype="mac"/><hostnames><hostname name="switch"/></hostnames></host></nmaprun>'
    candidates = _parse_nmap_xml(xml, cidr="192.168.10.0/24")
    assert candidates[0]["ip_addresses"] == ["192.168.10.4"]
    assert candidates[0]["hostname"] == "switch"


def test_network_context_read_separates_vpn_and_runtime_interfaces(monkeypatch):
    import src.privileged_broker as broker
    monkeypatch.setattr(
        broker,
        "client_request",
        lambda request, socket_path=None, timeout=15: {
            "ok": True,
            "execution_location": "HOST",
            "addresses": '[{"ifname":"eth0","operstate":"UP","addr_info":[{"local":"10.20.0.4","prefixlen":24,"family":"inet"}]},{"ifname":"tun0","operstate":"UNKNOWN","addr_info":[{"local":"100.64.0.2","prefixlen":32,"family":"inet"}]},{"ifname":"docker0","operstate":"UP","addr_info":[{"local":"172.30.0.1","prefixlen":16,"family":"inet"}]}]',
            "routes": '[{"dst":"default","dev":"tun0"}]',
        },
    )

    async def run():
        result = await HomelabOperations().execute({"action": "read_network_context"}, owner="alice")
        assert result["status"] == "SUCCESS_WITH_DATA"
        assert {item["kind"] for item in result["interfaces"]} == {"HOST_LOCAL", "VPN", "APPLICATION_RUNTIME"}
        assert any(scope["ownership"] == "VPN/CORPORATE_OR_UNKNOWN" for scope in result["candidate_scopes"])
        assert any(scope["ownership"] == "RUNTIME_INTERNAL" for scope in result["candidate_scopes"])
        assert result["vpn_present"] is True

    asyncio.run(run())


def test_network_context_fails_closed_when_broker_is_not_host(monkeypatch):
    import src.privileged_broker as broker
    monkeypatch.setattr(
        broker, "client_request",
        lambda request, socket_path=None, timeout=15: {
            "ok": True, "execution_location": "APPLICATION_RUNTIME",
            "addresses": "[]", "routes": "[]",
        },
    )

    result = asyncio.run(HomelabOperations().execute(
        {"action": "read_network_context"}, owner="alice",
    ))
    assert result["status"] == "UNAVAILABLE"
    assert result["error_code"] == "HOST_NETWORK_CONTEXT_UNAVAILABLE"
    assert result["observation_location"] == "APPLICATION_RUNTIME"


def test_private_scope_without_ownership_authorization_is_rejected():
    async def run():
        try:
            await HomelabOperations().execute(
                {"action": "plan_network_discovery", "cidr": "10.20.0.0/24"},
                owner="alice",
            )
        except HomelabOperationError as exc:
            assert "private addressing alone is not authorization" in str(exc)
        else:
            raise AssertionError("unowned private scope was accepted")

    asyncio.run(run())


def test_privileged_broker_network_discovery_is_bounded(monkeypatch):
    import src.privileged_broker as broker

    monkeypatch.setattr(broker.shutil, "which", lambda name: "/usr/bin/nmap" if name == "nmap" else None)
    monkeypatch.setattr(
        broker, "run_root",
        lambda argv, timeout=300: {"returncode": 0, "output": "<nmaprun/>"},
    )
    result = broker.handle({"action": "run_network_discovery", "cidr": "192.168.10.0/24"}, 1, 1000)
    assert result["ok"] is True
    assert result["cidr"] == "192.168.10.0/24"
    assert result["action"] == "run_network_discovery"
    for cidr in ("8.8.8.0/24", "192.168.10.0/23", "192.168.10.1"):
        rejected = broker.handle({"action": "run_network_discovery", "cidr": cidr}, 1, 1000)
        assert rejected["ok"] is False


def test_privileged_broker_service_enumeration_is_bounded_and_version_only(monkeypatch):
    import src.privileged_broker as broker
    captured = []
    monkeypatch.setattr(broker.shutil, "which", lambda name: "/usr/bin/nmap" if name == "nmap" else None)
    monkeypatch.setattr(
        broker, "run_root",
        lambda argv, timeout=300: captured.append((argv, timeout)) or {"returncode": 0, "output": "<nmaprun/>"},
    )
    result = broker.handle(
        {"action": "run_network_service_enumeration", "targets": ["192.168.10.4", "192.168.10.5"]},
        1, 1000,
    )
    assert result["ok"] is True
    argv, timeout = captured[0]
    assert argv[1:7] == ["-sV", "--version-light", "-Pn", "-n", "--max-retries", "1"]
    assert "-p" in argv and "1-1024" in argv
    assert argv[-2:] == ["192.168.10.4", "192.168.10.5"]
    assert timeout == 90
    for targets in (["8.8.8.8"], ["192.168.10.4"] * 257):
        rejected = broker.handle({"action": "run_network_service_enumeration", "targets": targets}, 1, 1000)
        assert rejected["ok"] is False


def test_service_parser_preserves_observed_services_and_ignores_out_of_scope_hosts():
    xml = (
        '<nmaprun><host><address addr="192.168.10.4" addrtype="ipv4"/><ports>'
        '<port protocol="tcp" portid="443"><state state="open"/>'
        '<service name="https" product="nginx" version="1.2"/></port>'
        '<port protocol="tcp" portid="22"><state state="closed"/></port>'
        '</ports></host><host><address addr="192.168.10.99" addrtype="ipv4"/>'
        '<ports><port protocol="tcp" portid="80"><state state="open"/></port></ports></host></nmaprun>'
    )
    observations = _parse_nmap_services(xml, targets=["192.168.10.4"])
    assert observations == [{
        "ip": "192.168.10.4",
        "services": [{
            "port": 443, "protocol": "tcp", "service": "https",
            "product": "nginx", "version": "1.2",
            "evidence": "nmap_service_version_observation",
        }],
        "observation_kind": "observed",
    }]


def test_network_service_enumeration_persists_through_existing_cmdb_writer(tmp_path, monkeypatch):
    import src.privileged_broker as broker
    recorded = []

    def request(payload, timeout=5):
        if payload.get("action") == "run_network_service_enumeration":
            return {
                "ok": True, "returncode": 0,
                "output": ('<nmaprun><host><address addr="192.168.10.4" addrtype="ipv4"/><ports>'
                            '<port protocol="tcp" portid="443"><state state="open"/>'
                            '<service name="https" product="nginx" version="1.2"/></port>'
                            '</ports></host></nmaprun>'),
            }
        return {"ok": True, "network_scanner_available": True}

    monkeypatch.setattr(broker, "client_request", request)

    async def run():
        ops = HomelabOperations(
            receipt_store=HomelabReceiptStore(tmp_path / "receipts.jsonl"),
            observation_recorder=lambda payload: recorded.append(payload),
        )
        plan = await ops.execute(
            {"action": "plan_network_service_enumeration", "targets": ["192.168.10.4"]}, owner="alice",
        )
        result = await ops.execute(
            {"action": "execute_network_service_enumeration", "targets": ["192.168.10.4"], "plan_digest": plan["operation_digest"]},
            owner="alice",
        )
        assert result["success"] is True
        assert result["observations_recorded"] is True
        assert result["network_map_reconciled"] is True
        assert result["role_hypotheses"][0]["classification"] == "INFERRED"
        assert result["role_hypotheses"][0]["canonical_identity_updated"] is False
        assert recorded[0]["hosts"][0]["kind"] == "network_service"
        assert recorded[0]["hosts"][0]["open_ports"][0]["service"] == "https"

    asyncio.run(run())


def test_discovery_plan_is_single_use_and_unrelated_homelab_actions_fail(tmp_path, monkeypatch):
    import src.privileged_broker as broker

    def request(payload, timeout=5):
        if payload.get("action") == "status":
            return {"ok": True, "network_scanner_available": True}
        return {"ok": True, "returncode": 0, "output": "<nmaprun/>"}

    monkeypatch.setattr(broker, "client_request", request)

    async def run():
        ops = HomelabOperations(
            receipt_store=HomelabReceiptStore(tmp_path / "receipts.jsonl"),
            observation_recorder=lambda _payload: None,
        )
        plan = await ops.execute({"action": "plan_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED"}, owner="alice")
        result = await ops.execute({"action": "execute_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED", "plan_digest": plan["operation_digest"]}, owner="alice")
        assert result["success"] is True
        try:
            await ops.execute({"action": "execute_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED", "plan_digest": plan["operation_digest"]}, owner="alice")
        except HomelabOperationError:
            pass
        else:
            raise AssertionError("completed discovery plan was replayable")
        try:
            await ops.execute({"action": "execute_diagnostic_install", "packages": ["nmap"], "plan_digest": plan["operation_digest"]}, owner="alice")
        except HomelabOperationError:
            pass
        else:
            raise AssertionError("discovery approval digest authorized an unrelated action")

    asyncio.run(run())


def test_network_discovery_persists_candidates_through_canonical_cmdb_writer(tmp_path, monkeypatch):
    import src.privileged_broker as broker

    recorded = []

    def request(payload, timeout=5):
        if payload.get("action") == "status":
            return {"ok": True, "network_scanner_available": True}
        return {
            "ok": True,
            "returncode": 0,
            "output": (
                '<nmaprun><host><status state="up"/>'
                '<address addr="192.168.10.4" addrtype="ipv4"/>'
                '<address addr="AA:BB:CC:DD:EE:FF" addrtype="mac"/>'
                '<hostnames><hostname name="router"/></hostnames></host></nmaprun>'
            ),
        }

    monkeypatch.setattr(broker, "client_request", request)

    async def run():
        ops = HomelabOperations(
            receipt_store=HomelabReceiptStore(tmp_path / "receipts.jsonl"),
            observation_recorder=lambda payload: recorded.append(payload),
        )
        plan = await ops.execute({"action": "plan_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED"}, owner="alice")
        result = await ops.execute(
            {"action": "execute_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED", "plan_digest": plan["operation_digest"]},
            owner="alice",
        )
        assert result["success"] is True
        assert result["observations_recorded"] is True
        assert result["network_map_reconciled"] is True
        assert recorded[0]["hosts"][0]["ip"] == "192.168.10.4"
        assert recorded[0]["hosts"][0]["mac"] == "aa:bb:cc:dd:ee:ff"

    asyncio.run(run())


def test_network_discovery_does_not_claim_success_when_cmdb_persistence_fails(tmp_path, monkeypatch):
    import src.privileged_broker as broker

    def request(payload, timeout=5):
        if payload.get("action") == "status":
            return {"ok": True, "network_scanner_available": True}
        return {"ok": True, "returncode": 0, "output": "<nmaprun/>"}

    monkeypatch.setattr(broker, "client_request", request)

    def failing_recorder(_payload):
        raise RuntimeError("CMDB unavailable")

    async def run():
        ops = HomelabOperations(
            receipt_store=HomelabReceiptStore(tmp_path / "receipts.jsonl"),
            observation_recorder=failing_recorder,
        )
        plan = await ops.execute({"action": "plan_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED"}, owner="alice")
        result = await ops.execute(
            {"action": "execute_network_discovery", "cidr": "192.168.10.0/24", "scope_authorization": "EXPLICITLY_AUTHORIZED", "plan_digest": plan["operation_digest"]},
            owner="alice",
        )
        assert result["success"] is False
        assert result["execution_ambiguous"] is True
        assert result["observations_recorded"] is False

    asyncio.run(run())
