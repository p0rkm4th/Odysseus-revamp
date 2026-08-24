from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.economic_mandates import BudgetUsage, EconomicRuntimeControls, evaluate_economic_action
from core.telegram_models import TelegramApprovalCallback, TelegramConnection, TelegramPairingCode
from src.economic_mandates import EconomicAction
from src.osint_policy import OsintPolicyError, build_plan, validate_request
from src.telegram_store import TelegramStore, TelegramStoreError
from src.homelab_operations import HomelabOperationError, HomelabOperations, HomelabReceiptStore, _parse_nmap_xml
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
        planned = await ops.execute({"action": "plan_network_discovery", "cidr": "192.168.10.0/24"}, owner="alice")
        assert planned["target"] == "192.168.10.0/24"
        assert "asset_draft_candidates" not in planned
        try:
            await ops.execute({"action": "plan_network_discovery", "cidr": "8.8.8.0/24"}, owner="alice")
        except HomelabOperationError:
            pass
        else:
            raise AssertionError("public discovery scope was accepted")

    asyncio.run(run())
    xml = '<nmaprun><host><status state="up"/><address addr="192.168.10.4" addrtype="ipv4"/><address addr="AA:BB:CC:DD:EE:FF" addrtype="mac"/><hostnames><hostname name="switch"/></hostnames></host></nmaprun>'
    candidates = _parse_nmap_xml(xml, cidr="192.168.10.0/24")
    assert candidates[0]["ip_addresses"] == ["192.168.10.4"]
    assert candidates[0]["hostname"] == "switch"


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


def test_discovery_plan_is_single_use_and_unrelated_homelab_actions_fail(tmp_path, monkeypatch):
    import src.privileged_broker as broker

    def request(payload, timeout=5):
        if payload.get("action") == "status":
            return {"ok": True, "network_scanner_available": True}
        return {"ok": True, "returncode": 0, "output": "<nmaprun/>"}

    monkeypatch.setattr(broker, "client_request", request)

    async def run():
        ops = HomelabOperations(receipt_store=HomelabReceiptStore(tmp_path / "receipts.jsonl"))
        plan = await ops.execute({"action": "plan_network_discovery", "cidr": "192.168.10.0/24"}, owner="alice")
        result = await ops.execute({"action": "execute_network_discovery", "cidr": "192.168.10.0/24", "plan_digest": plan["operation_digest"]}, owner="alice")
        assert result["success"] is True
        try:
            await ops.execute({"action": "execute_network_discovery", "cidr": "192.168.10.0/24", "plan_digest": plan["operation_digest"]}, owner="alice")
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
