"""Structured, local-only homelab operations with durable plan receipts."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import shutil
import threading
from typing import Any, Awaitable, Callable
import xml.etree.ElementTree as ET

from src.constants import DATA_DIR
from src.execution_profiles import active_execution_profile
from src.capability_dependencies import capability_health, remediation_handoff


class HomelabOperationError(ValueError):
    pass


_SERVICE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@:-]{0,127}$")
_ACTIONS = frozenset({
    "inspect_host", "service_status", "plan_service_restart", "execute_service_restart",
    "discovery_status", "plan_network_discovery", "execute_network_discovery",
    "plan_diagnostic_install", "execute_diagnostic_install",
})
_PROTECTED_RESTART_UNITS = frozenset({"odysseus.service"})
_receipt_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _service(value: Any) -> str:
    service = str(value or "").strip()
    if not _SERVICE.fullmatch(service):
        raise HomelabOperationError("service must be a systemd unit name")
    return service


def _public(receipt: dict[str, Any]) -> dict[str, Any]:
    """Keep the authenticated owner in the private ledger, not model output."""
    return {key: value for key, value in receipt.items() if key != "owner"}


def _private_network(value: Any) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(str(value or "").strip(), strict=True)
    except ValueError as exc:
        raise HomelabOperationError("cidr must be a canonical private IPv4 network") from exc
    if not isinstance(network, ipaddress.IPv4Network) or not network.is_private:
        raise HomelabOperationError("discovery is limited to private IPv4 networks")
    if network.num_addresses > 256:
        raise HomelabOperationError("discovery is limited to at most 256 addresses per approval")
    return network


def _parse_nmap_xml(raw: str, *, cidr: str) -> list[dict[str, Any]]:
    if len(raw.encode("utf-8")) > 2_000_000:
        raise HomelabOperationError("scanner output exceeded the safety limit")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise HomelabOperationError("scanner returned invalid structured output") from exc
    candidates = []
    for host in root.findall("host")[:256]:
        status_node = host.find("status")
        if status_node is None or status_node.get("state") != "up":
            continue
        addresses = {
            node.get("addrtype"): node.get("addr")
            for node in host.findall("address") if node.get("addr")
        }
        ip = addresses.get("ipv4")
        if not ip:
            continue
        hostname_node = host.find("hostnames/hostname")
        hostname = hostname_node.get("name") if hostname_node is not None else None
        mac_node = next((node for node in host.findall("address") if node.get("addrtype") == "mac"), None)
        candidate = {
            "action": "add", "domain": "it", "category": "network_device",
            "name": hostname or f"Discovered device {ip}", "ip_addresses": [ip],
            "quantity": "1", "unit": "each",
            "notes": f"Discovered by an approved host-discovery scan of {cidr}; verify identity before confirmation.",
        }
        if hostname:
            candidate["hostname"] = hostname
        if mac_node is not None and mac_node.get("addr"):
            candidate["mac_addresses"] = [mac_node.get("addr")]
            if mac_node.get("vendor"):
                candidate["manufacturer"] = mac_node.get("vendor")
        candidates.append(candidate)
    return candidates


class HomelabReceiptStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or Path(DATA_DIR) / "homelab" / "receipts.jsonl")

    def append(self, receipt: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
        with _receipt_lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, encoded.encode())
                os.fsync(fd)
            finally:
                os.close(fd)
            os.chmod(self.path, 0o600)

    def valid_plan(self, *, owner: str, digest: str, now: datetime | None = None) -> bool:
        if not self.path.is_file():
            return False
        current = now or _now()
        with _receipt_lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines[-1000:]):
            try:
                receipt = json.loads(line)
                created = datetime.fromisoformat(receipt["created_at"])
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
            if receipt.get("kind") == "plan" and receipt.get("owner") == owner and receipt.get("operation_digest") == digest:
                return current <= created + timedelta(minutes=10)
        return False


async def _default_runner(argv: list[str], timeout: float = 30) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        cwd="/", env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return 124, "operation timed out"
    return int(process.returncode or 0), output.decode("utf-8", errors="replace")[:12000]


class HomelabOperations:
    def __init__(
        self, *, receipt_store: HomelabReceiptStore | None = None,
        runner: Callable[[list[str], float], Awaitable[tuple[int, str]]] = _default_runner,
    ) -> None:
        self.receipts = receipt_store or HomelabReceiptStore()
        self.runner = runner

    async def execute(self, request: dict[str, Any], *, owner: str) -> dict[str, Any]:
        owner = str(owner or "").strip()
        if not owner:
            raise HomelabOperationError("an authenticated owner is required")
        action = str(request.get("action") or "").strip()
        if action not in _ACTIONS:
            raise HomelabOperationError("unsupported homelab action")
        if action == "inspect_host":
            return await self._read(owner, action, ["uptime"])
        if action == "discovery_status":
            health = capability_health("network_discovery")
            broker_scanner = False
            try:
                from src.privileged_broker import client_request
                broker_scanner = bool((await asyncio.to_thread(client_request, {"action": "status"}, timeout=5)).get("network_scanner_available"))
            except Exception:
                pass
            return {
                "kind": "capability", "action": action,
                "available": health["status"] == "available" or broker_scanner,
                "scanner": "nmap", "install_required": bool(health["missing_executables"]),
                "broker_scanner_available": broker_scanner,
                "capability_health": health, "exit_code": 0,
            }
        if action in {"plan_diagnostic_install", "execute_diagnostic_install"}:
            return await self._diagnostic_install(request, owner=owner, action=action)
        if action in {"plan_network_discovery", "execute_network_discovery"}:
            return await self._network_discovery(request, owner=owner, action=action)
        service = _service(request.get("service"))
        if action == "service_status":
            return await self._read(owner, action, [
                "systemctl", "--user", "show", "--no-pager",
                "--property=Id,LoadState,ActiveState,SubState,UnitFileState", service,
            ], target=service)
        plan = {
            "action": "execute_service_restart", "target_kind": "local_user_systemd_unit",
            "target": service,
        }
        digest = _digest(plan)
        if action == "plan_service_restart":
            code, output = await self.runner([
                "systemctl", "--user", "show", "--no-pager",
                "--property=Id,LoadState,ActiveState,SubState,UnitFileState", service,
            ], 30)
            if code != 0 or "LoadState=not-found" in output:
                return {
                    "kind": "preflight", "operation_digest": digest,
                    **plan, "success": False, "exit_code": code or 1,
                    "output": output, "untrusted_content": True,
                }
            receipt = {
                "kind": "plan", "owner": owner, "created_at": _now().isoformat(),
                "operation_digest": digest, **plan,
                "preflight": "Restart only this exact local user systemd unit as the Odysseus service account.",
                "recovery": "Inspect unit status and logs; restore its prior configuration outside this adapter if needed.",
            }
            await asyncio.to_thread(self.receipts.append, receipt)
            return {**_public(receipt), "exit_code": 0, "current_state": output, "untrusted_content": True}
        supplied = str(request.get("plan_digest") or "")
        if supplied != digest or not await asyncio.to_thread(
            self.receipts.valid_plan, owner=owner, digest=supplied,
        ):
            raise HomelabOperationError("a current owner-bound preflight plan is required")
        if active_execution_profile().name != "privileged_host":
            raise HomelabOperationError("execution requires privileged host operator mode and exact approval")
        if service in _PROTECTED_RESTART_UNITS:
            raise HomelabOperationError("this adapter cannot restart its own Odysseus unit")
        code, output = await self.runner(["systemctl", "--user", "restart", service], 30)
        verify_code, verify_output = await self.runner(
            ["systemctl", "--user", "is-active", service], 30,
        )
        success = code == 0 and verify_code == 0 and verify_output.strip() == "active"
        receipt = {
            "kind": "execution", "owner": owner, "created_at": _now().isoformat(),
            "operation_digest": digest, **plan, "success": success,
            "exit_code": code,
            "verification_exit_code": verify_code,
            "recovery": "Inspect systemctl status and journal logs; correct the unit and restart again if required.",
        }
        await asyncio.to_thread(self.receipts.append, receipt)
        return {
            **_public(receipt), "output": output,
            "verification_output": verify_output, "untrusted_content": True,
        }

    async def _network_discovery(
        self, request: dict[str, Any], *, owner: str, action: str,
    ) -> dict[str, Any]:
        network = _private_network(request.get("cidr"))
        cidr = str(network)
        operation = {
            "action": "execute_network_discovery", "target_kind": "private_ipv4_network",
            "target": cidr, "scanner": "nmap_ping_scan",
        }
        digest = _digest(operation)
        scanner = shutil.which("nmap")
        broker_scanner = False
        if not scanner:
            try:
                from src.privileged_broker import client_request
                broker_scanner = bool((await asyncio.to_thread(client_request, {"action": "status"}, timeout=5)).get("network_scanner_available"))
            except Exception:
                pass
        health = capability_health("network_discovery", available=(["nmap"] if scanner or broker_scanner else []))
        if action == "plan_network_discovery":
            receipt = {
                "kind": "plan", "owner": owner, "created_at": _now().isoformat(),
                "operation_digest": digest, **operation,
                "scanner_available": bool(scanner or broker_scanner),
                "broker_scanner_available": broker_scanner,
                "capability_health": health,
                "required_packages": health.get("packages", []),
                "preflight": f"Probe only {cidr} for live hosts; open ports and services are not enumerated.",
                "recovery": "Discovery is read-only; discard any unwanted draft candidates.",
            }
            await asyncio.to_thread(self.receipts.append, receipt)
            return {**_public(receipt), "exit_code": 0}
        supplied = str(request.get("plan_digest") or "")
        if supplied != digest or not await asyncio.to_thread(
            self.receipts.valid_plan, owner=owner, digest=supplied,
        ):
            raise HomelabOperationError("a current owner-bound discovery plan is required")
        if active_execution_profile().name != "privileged_host":
            raise HomelabOperationError("network discovery requires privileged host operator mode and exact approval")
        if not scanner and not broker_scanner:
            # Never ask the model to guess a distro package name. Return a
            # deterministic remediation handoff to the existing exact-
            # approval diagnostic-install action; the caller can preserve the
            # same Work Run/RunAction while that prerequisite is installed.
            handoff = None
            if request.get("run_id") and request.get("action_id"):
                try:
                    handoff = remediation_handoff(
                        "network_discovery", run_id=str(request["run_id"]),
                        action_id=str(request["action_id"]),
                        approval_reference=request.get("approval_reference"),
                    )
                except ValueError:
                    handoff = None
            return {
                "kind": "prerequisite_missing", "action": action,
                "capability": "network_discovery", "capability_health": health,
                "required_packages": health.get("packages", []),
                "remediation_action": "plan_diagnostic_install",
                "operation_digest": digest, "handoff": handoff,
                "untrusted_content": False,
            }
        if scanner:
            code, output = await self.runner([
                scanner, "-sn", "-n", "--max-retries", "1", "--host-timeout", "5s",
                "-oX", "-", cidr,
            ], 60)
        else:
            from src.privileged_broker import client_request
            broker_result = await asyncio.to_thread(
                client_request, {"action": "run_network_discovery", "cidr": cidr}, timeout=70,
            )
            code = int(broker_result.get("returncode", 1)) if broker_result.get("ok") else 1
            output = str(broker_result.get("output") or broker_result.get("error") or "")
        candidates = _parse_nmap_xml(output, cidr=cidr) if code == 0 else []
        receipt = {
            "kind": "discovery", "owner": owner, "created_at": _now().isoformat(),
            "operation_digest": digest, **operation, "success": code == 0,
            "exit_code": code, "candidate_count": len(candidates),
        }
        await asyncio.to_thread(self.receipts.append, receipt)
        return {
            **_public(receipt), "asset_draft_candidates": candidates,
            "requires_explicit_inventory_review": True, "untrusted_content": True,
        }

    async def _diagnostic_install(
        self, request: dict[str, Any], *, owner: str, action: str,
    ) -> dict[str, Any]:
        from src.privileged_broker import ALLOWED_PACKAGES, client_request, validate_packages

        try:
            capability = str(request.get("capability") or "").strip()
            dependency = capability_health(capability, available=[]) if capability else None
            if capability:
                if not dependency.get("remediation_available"):
                    raise ValueError("capability has no deterministic approved prerequisite remediation")
                packages = validate_packages(dependency.get("packages"))
                verify_executables = dependency.get("executables", [])
            else:
                packages = validate_packages(request.get("packages"))
                verify_executables = [str(x) for x in request.get("verify_executables", []) if isinstance(x, str)]
        except ValueError as exc:
            raise HomelabOperationError(str(exc)) from exc
        operation = {
            "action": "execute_diagnostic_install", "target_kind": "local_diagnostic_packages",
            "packages": packages, "capability": capability or None,
        }
        handoff = None
        if capability and request.get("run_id") and request.get("action_id"):
            try:
                handoff = remediation_handoff(
                    capability, run_id=str(request["run_id"]),
                    action_id=str(request["action_id"]),
                    approval_reference=request.get("approval_reference"),
                )
            except ValueError:
                handoff = None
        digest = _digest(operation)
        if action == "plan_diagnostic_install":
            try:
                broker = await asyncio.to_thread(client_request, {"action": "status"}, timeout=5)
                broker_available = bool(broker.get("ok"))
            except Exception:
                broker_available = False
            receipt = {
                "kind": "plan", "owner": owner, "created_at": _now().isoformat(),
                "operation_digest": digest, **operation,
                "broker_available": broker_available,
                "allowlisted_packages": sorted(ALLOWED_PACKAGES),
                "capability_health": dependency,
                "verify_executables": verify_executables,
                "preflight": "Install only the exact allowlisted diagnostic packages through the separately deployed peer-checked broker.",
                "recovery": "Remove packages using the host package manager if the operator chooses to roll back.",
                "handoff": handoff,
            }
            await asyncio.to_thread(self.receipts.append, receipt)
            return {**_public(receipt), "exit_code": 0}
        supplied = str(request.get("plan_digest") or "")
        if supplied != digest or not await asyncio.to_thread(
            self.receipts.valid_plan, owner=owner, digest=supplied,
        ):
            raise HomelabOperationError("a current owner-bound diagnostic-install plan is required")
        if active_execution_profile().name != "privileged_host":
            raise HomelabOperationError("diagnostic installation requires privileged host operator mode and exact approval")
        try:
            result = await asyncio.to_thread(
                client_request, {"action": "install_packages", "packages": packages}, timeout=310,
            )
        except Exception as exc:
            result = {"ok": False, "error": "privileged diagnostic broker unavailable"}
            logger.info("diagnostic broker request failed: %s", type(exc).__name__)
        receipt = {
            "kind": "diagnostic_install", "owner": owner, "created_at": _now().isoformat(),
            "operation_digest": digest, **operation, "success": bool(result.get("ok")),
            "exit_code": 0 if result.get("ok") else 1,
        }
        await asyncio.to_thread(self.receipts.append, receipt)
        verification = None
        if result.get("ok") and verify_executables:
            try:
                verification = await asyncio.to_thread(
                    client_request,
                    {"action": "verify_executables", "executables": verify_executables},
                    timeout=30,
                )
            except Exception:
                verification = {"ok": False, "error": "prerequisite verification unavailable"}
            result = dict(result)
            result["verification"] = verification
            receipt["verified"] = bool(verification.get("ok"))
            receipt["success"] = bool(result.get("ok")) and bool(verification.get("ok"))
        verified = bool(receipt.get("success"))
        return {
            **_public(receipt), "broker_result": result,
            "verified_prerequisites": verified,
            "resume_same_run": bool(verified and handoff),
            "resume_same_action": bool(verified and handoff),
            "handoff": handoff, "untrusted_content": True,
        }

    async def _read(
        self, owner: str, action: str, argv: list[str], *, target: str = "local_host",
    ) -> dict[str, Any]:
        code, output = await self.runner(argv, 30)
        receipt = {
            "kind": "read", "owner": owner, "created_at": _now().isoformat(),
            "action": action, "target": target, "command_digest": _digest({"argv": argv}),
            "success": code == 0, "exit_code": code,
        }
        await asyncio.to_thread(self.receipts.append, receipt)
        return {**_public(receipt), "output": output, "untrusted_content": True}
