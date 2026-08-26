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
    "discovery_status", "read_network_context", "read_network_observations", "list_unidentified_hosts", "infer_role_hypotheses",
    "plan_network_discovery", "execute_network_discovery",
    "plan_network_service_enumeration", "execute_network_service_enumeration",
    "plan_diagnostic_install", "execute_diagnostic_install",
})
_PROTECTED_RESTART_UNITS = frozenset({"odysseus.service"})
# Retained for compatibility with historical fixtures and migration data. It
# is never selected as a current scope by the agent loop.
DEFAULT_PRIVATE_DISCOVERY_CIDR = "192.168.10.0/24"
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


def _private_targets(value: Any) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        raise HomelabOperationError("service enumeration requires 1..256 discovered private hosts")
    targets = []
    for item in value:
        try:
            address = ipaddress.ip_address(str(item).strip())
        except ValueError as exc:
            raise HomelabOperationError("service enumeration targets must be IPv4 addresses") from exc
        if not isinstance(address, ipaddress.IPv4Address) or not address.is_private:
            raise HomelabOperationError("service enumeration is limited to discovered private IPv4 hosts")
        text = str(address)
        if text not in targets:
            targets.append(text)
    return targets


def _parse_nmap_services(raw: str, *, targets: list[str]) -> list[dict[str, Any]]:
    if len(raw.encode("utf-8")) > 4_000_000:
        raise HomelabOperationError("service scanner output exceeded the safety limit")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise HomelabOperationError("service scanner returned invalid structured output") from exc
    allowed = set(targets)
    observations = []
    for host in root.findall("host")[:256]:
        address = next((n.get("addr") for n in host.findall("address") if n.get("addrtype") == "ipv4"), None)
        if address not in allowed:
            continue
        services = []
        for port in host.findall("ports/port")[:256]:
            state = port.find("state")
            service = port.find("service")
            if state is None or state.get("state") != "open":
                continue
            services.append({
                "port": int(port.get("portid")) if str(port.get("portid") or "").isdigit() else port.get("portid"),
                "protocol": port.get("protocol"),
                "service": service.get("name") if service is not None else None,
                "product": service.get("product") if service is not None else None,
                "version": service.get("version") if service is not None else None,
                "evidence": "nmap_service_version_observation",
            })
        observations.append({"ip": address, "services": services, "observation_kind": "observed"})
    return observations


def _role_hypotheses(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produce bounded, explicitly inferred role hypotheses from observations."""
    hypotheses = []
    for observation in observations[:256]:
        services = observation.get("services") or []
        names = {str(item.get("service") or "").lower() for item in services if isinstance(item, dict)}
        ports = {item.get("port") for item in services if isinstance(item, dict)}
        candidates = []
        if {"http", "https"} & names or {80, 443} & ports:
            candidates.append(("web_server_or_appliance", 0.55, "HTTP(S) service observation"))
        if {"ssh", "sftp"} & names or 22 in ports:
            candidates.append(("unix_like_server_or_network_appliance", 0.45, "SSH service observation"))
        if {"smb", "microsoft-ds", "netbios-ssn"} & names or {139, 445} & ports:
            candidates.append(("file_server_or_windows_host", 0.55, "SMB/NetBIOS service observation"))
        for label, confidence, evidence in candidates[:4]:
            hypothesis = {
                "ip": observation.get("ip"),
                "role": label,
                "classification": "INFERRED",
                "confidence": confidence,
                "evidence": [evidence],
                "canonical_identity_updated": False,
            }
            for key in ("canonical_ref", "freshness"):
                if observation.get(key) is not None:
                    hypothesis[key] = observation[key]
            hypotheses.append(hypothesis)
    return hypotheses


def _projected_service_observations(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize persisted network evidence for the shared role classifier."""
    observations = []
    for node in nodes[:256]:
        services = []
        latest_observed_at = None
        for raw in node.get("observations") or []:
            if not isinstance(raw, dict):
                continue
            latest_observed_at = latest_observed_at or raw.get("observed_at")
            try:
                data = json.loads(raw.get("data_json") or "{}")
            except (TypeError, ValueError):
                data = {}
            if not isinstance(data, dict):
                continue
            for service in data.get("services") or []:
                if isinstance(service, dict):
                    services.append(service)
            ports = data.get("open_ports") or []
            meanings = data.get("port_meanings") or []
            if isinstance(ports, list):
                for index, port in enumerate(ports):
                    service = meanings[index] if index < len(meanings) else None
                    services.append({"port": port, "service": service})
        if services:
            attributes = node.get("attributes") or {}
            observations.append({
                "ip": attributes.get("observed_ip") or attributes.get("ip") or node.get("ip"),
                "services": services,
                "canonical_ref": node.get("id"),
                "freshness": latest_observed_at,
            })
    return observations


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
            # A plan is single-use for discovery. Repeating the exact payload
            # must require a fresh plan and fresh approval, even while the
            # original plan's TTL has not elapsed.
            if receipt.get("kind") == "discovery" and receipt.get("owner") == owner and receipt.get("operation_digest") == digest:
                return False
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
        observation_recorder: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.receipts = receipt_store or HomelabReceiptStore()
        self.runner = runner
        # The CMDB writer is injectable for deterministic tests, but the
        # production default remains the existing canonical asset-inventory
        # persistence primitive.  Discovery must not grow a second store.
        self.observation_recorder = observation_recorder

    def _record_network_observations(self, candidates: list[dict[str, Any]], *, owner: str) -> dict[str, Any]:
        hosts = []
        for candidate in candidates[:256]:
            ips = candidate.get("ip_addresses") or []
            ip = str(ips[0]).strip() if ips else ""
            if not ip:
                continue
            macs = candidate.get("mac_addresses") or []
            hosts.append({
                "ip": ip,
                "mac": str(macs[0]).strip().lower() if macs else None,
                "open_ports": [],
                "evidence": ["nmap_host_discovery"],
                "hostname": candidate.get("hostname"),
            })
        recorder = self.observation_recorder
        if recorder is None:
            from src.asset_inventory import record_net
            recorder = lambda payload: record_net(payload, owner=owner)
        recorder({"hosts": hosts})
        return {
            "observations_recorded": True,
            "observation_count": len(hosts),
            # Network projection reads this same canonical CMDB store.  No
            # separate Network database or inferred asset identity is made.
            "network_map_reconciled": True,
        }

    def _record_network_service_observations(self, observations: list[dict[str, Any]], *, owner: str) -> dict[str, Any]:
        """Persist service evidence through the existing canonical CMDB writer."""
        hosts = []
        for observation in observations[:256]:
            ip = str(observation.get("ip") or "").strip()
            if not ip:
                continue
            hosts.append({
                "ip": ip,
                "mac": None,
                "open_ports": observation.get("services") or [],
                "evidence": ["nmap_service_version_observation"],
                "kind": "network_service",
                "source": "network_service_enumeration",
                "confidence": 0.7,
            })
        recorder = self.observation_recorder
        if recorder is None:
            from src.asset_inventory import record_net
            recorder = lambda payload: record_net(payload, owner=owner)
        recorder({"hosts": hosts})
        return {
            "observations_recorded": True,
            "observation_count": len(hosts),
            "network_map_reconciled": True,
        }

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
        if action == "read_network_context":
            from src.privileged_broker import HOST_NETWORK_SOCKET_PATH, client_request
            host_socket = os.getenv("ODYSSEUS_HOST_NETWORK_BROKER_SOCKET", HOST_NETWORK_SOCKET_PATH)
            try:
                raw = await asyncio.to_thread(client_request, {"action": action}, socket_path=host_socket, timeout=15)
            except Exception as exc:
                return {"status": "UNAVAILABLE", "error_code": "HOST_NETWORK_CONTEXT_UNAVAILABLE", "action": action, "error": str(exc), "source": "host_network_broker", "observation_location": "HOST"}
            if not raw.get("ok") or raw.get("execution_location") != "HOST":
                return {"status": "UNAVAILABLE", "error_code": "HOST_NETWORK_CONTEXT_UNAVAILABLE", "action": action, "error": raw.get("error") or "trusted host network context unavailable", "source": "host_network_broker", "observation_location": raw.get("execution_location") or "UNKNOWN"}
            try:
                addresses = json.loads(raw.get("addresses") or "[]")
                routes = json.loads(raw.get("routes") or "[]")
            except (TypeError, ValueError) as exc:
                return {"status": "INVALID_RESULT", "error_code": "RESULT_INVALID", "action": action, "error": f"host network context was not structured: {exc}", "source": "host_network_broker", "observation_location": "HOST"}
            interfaces = []
            for item in addresses if isinstance(addresses, list) else []:
                name = str(item.get("ifname") or "").strip()
                if not name:
                    continue
                flags = {str(flag).upper() for flag in (item.get("flags") or [])}
                link_type = str(item.get("link_type") or "").lower()
                kind = (
                    "VPN" if re.search(r"(?:^|[-_.])(?:tun|tap|wg|vpn|proton|tailscale|zerotier)|(?:vpn)", name, re.I)
                    or ("POINTOPOINT" in flags and link_type in {"none", "ipip", "sit"})
                    else "DOCKER_BRIDGE" if re.search(r"^(docker|br-|veth)", name, re.I)
                    else "APPLICATION_RUNTIME" if re.search(r"^(cni|virbr)", name, re.I)
                    else "PHYSICAL_LAN" if re.search(r"^(wl|en|eth)", name, re.I)
                    else "HOST_LOCAL"
                )
                entries = [{"address": info["local"], "prefix_length": info.get("prefixlen"), "family": info.get("family")} for info in (item.get("addr_info") or []) if isinstance(info, dict) and info.get("local")]
                interfaces.append({"name": name, "kind": kind, "addresses": entries, "up": bool(item.get("operstate") in {"UP", "UNKNOWN"}), "flags": sorted(flags), "link_type": link_type or None})
            default_routes = [route for route in routes if isinstance(route, dict) and route.get("dst") == "default"] if isinstance(routes, list) else []
            vpn = any(item["kind"] == "VPN" for item in interfaces)
            scopes = []
            runtime_scopes = []
            user_scopes = []
            for item in interfaces:
                for addr in item["addresses"]:
                    if addr.get("family") == "inet" and item["name"] != "lo":
                        try:
                            cidr = str(ipaddress.ip_interface(f"{addr['address']}/{addr.get('prefix_length')}").network)
                            runtime_internal = item["kind"] in {"APPLICATION_RUNTIME", "DOCKER_BRIDGE", "SANDBOX_INTERNAL"}
                            ownership = (
                                "RUNTIME_INTERNAL" if runtime_internal
                                else "VPN/CORPORATE_OR_UNKNOWN" if vpn
                                else "UNKNOWN"
                            )
                            scope = {"interface": item["name"], "cidr": cidr, "ownership": ownership, "context_kind": item["kind"]}
                            scopes.append(scope)
                            (runtime_scopes if runtime_internal else user_scopes).append(scope)
                        except ValueError:
                            pass
            context_id = hashlib.sha256(json.dumps({"interfaces": interfaces, "routes": default_routes}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
            return {
                "status": "SUCCESS_WITH_DATA" if interfaces else "SUCCESS_EMPTY", "action": action,
                "interfaces": interfaces, "default_routes": default_routes,
                "candidate_scopes": scopes, "user_network_scopes": user_scopes,
                "runtime_scopes": runtime_scopes, "vpn_present": vpn,
                "source": "host_network_broker", "context_id": context_id,
                "observation_location": "HOST",
                "network_namespace_id": raw.get("network_namespace_id"),
                "context_kinds": sorted({item["kind"] for item in interfaces}),
            }
        if action == "read_network_observations":
            from src.network_projection import map_projection
            projection = map_projection(owner=owner)
            if projection.get("warning"):
                return {
                    "status": "UNAVAILABLE",
                    "action": action,
                    "error": projection["warning"],
                    "source": "canonical_cmdb",
                    "exit_code": 1,
                }
            nodes = projection.get("nodes") or []
            return {
                "status": "EMPTY_RESULT" if not nodes else "SUCCESS",
                "action": action,
                "nodes": nodes,
                "edges": projection.get("edges") or [],
                "node_count": len(nodes),
                "edge_count": len(projection.get("edges") or []),
                "source": "canonical_cmdb",
                "owner_scope": owner,
                "observation_kind": "HISTORICAL_DISCOVERY",
                "freshness": "historical_until_matched_to_current_context",
                "exit_code": 0,
            }
        if action in {"list_unidentified_hosts", "infer_role_hypotheses"}:
            from src.network_projection import map_projection
            projection = map_projection(owner=owner)
            if projection.get("warning"):
                return {
                    "status": "UNAVAILABLE",
                    "action": action,
                    "error": projection["warning"],
                    "source": "canonical_cmdb",
                    "owner_scope": owner,
                    "exit_code": 1,
                }
            nodes = projection.get("nodes") or []
            if action == "list_unidentified_hosts":
                hosts = [
                    node for node in nodes
                    if node.get("resolution_state") == "unidentified" or node.get("canonical") is False
                ]
                return {
                    "status": "EMPTY_RESULT" if not hosts else "SUCCESS",
                    "action": action,
                    "hosts": hosts,
                    "host_count": len(hosts),
                    "source": "canonical_cmdb",
                    "owner_scope": owner,
                    "identity_rule": projection.get("identity_rule"),
                    "exit_code": 0,
                }
            hypotheses = _role_hypotheses(_projected_service_observations(nodes))
            return {
                "status": "EMPTY_RESULT" if not hypotheses else "SUCCESS",
                "action": action,
                "hypotheses": hypotheses,
                "hypothesis_count": len(hypotheses),
                "source": "canonical_cmdb",
                "owner_scope": owner,
                "inference_policy": "inferred_only; canonical identity is not overwritten",
                "exit_code": 0,
            }
        if action in {"plan_diagnostic_install", "execute_diagnostic_install"}:
            return await self._diagnostic_install(request, owner=owner, action=action)
        if action in {"plan_network_discovery", "execute_network_discovery"}:
            return await self._network_discovery(request, owner=owner, action=action)
        if action in {"plan_network_service_enumeration", "execute_network_service_enumeration"}:
            return await self._network_service_enumeration(request, owner=owner, action=action)
        if action == "service_status":
            raw_service = str(request.get("service") or "").strip()
            if not raw_service:
                return await self._read(owner, action, [
                    "systemctl", "--user", "list-units", "--type=service", "--all", "--no-pager",
                ], target="user-services")
            service = _service(raw_service)
            return await self._read(owner, action, [
                "systemctl", "--user", "show", "--no-pager",
                "--property=Id,LoadState,ActiveState,SubState,UnitFileState", service,
            ], target=service)
        service = _service(request.get("service"))
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
        if not str(request.get("cidr") or "").strip():
            raise HomelabOperationError("current network context or an explicitly authorized CIDR is required; historical scope is not reused")
        network = _private_network(request.get("cidr"))
        cidr = str(network)
        authorization = str(request.get("scope_authorization") or "").strip().upper()
        if authorization not in {"USER_MANAGED", "EXPLICITLY_AUTHORIZED"}:
            raise HomelabOperationError(
                "active discovery requires USER_MANAGED or EXPLICITLY_AUTHORIZED scope; "
                "private addressing alone is not authorization"
            )
        operation = {
            "action": "execute_network_discovery", "target_kind": "private_ipv4_network",
            "target": cidr, "scanner": "nmap_ping_scan",
            "scope_authorization": authorization,
        }
        digest = _digest(operation)
        # LAN discovery is never executed in the Hades application runtime.
        # The host broker is canonical even when an nmap binary happens to be
        # present in the container image.
        scanner = None
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
        # The broker is the execution boundary for discovery.  Do not require
        # the Hades application request itself to be in a host-networked or
        # privileged process profile: the persisted exact approval gates the
        # ActionSpec, and the broker authenticates the caller and runs Nmap on
        # the host.  This is what allows approval continuation to resume the
        # same RunAction without falling back to container-local reasoning.
        if not broker_scanner:
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
        from src.privileged_broker import client_request
        broker_result = await asyncio.to_thread(
            client_request, {"action": "run_network_discovery", "cidr": cidr}, timeout=70,
        )
        code = int(broker_result.get("returncode", 1)) if broker_result.get("ok") else 1
        output = str(broker_result.get("output") or broker_result.get("error") or "")
        candidates = _parse_nmap_xml(output, cidr=cidr) if code == 0 else []
        persistence_error = None
        persistence = {"observations_recorded": False, "network_map_reconciled": False}
        if code == 0:
            try:
                persistence = self._record_network_observations(candidates, owner=owner)
            except Exception as exc:
                # The broker may have completed while the durable observation
                # projection failed. Preserve that distinction for the Run;
                # callers must not report a verified discovery in this state.
                persistence_error = str(exc)[:500]
        receipt = {
            "kind": "discovery", "owner": owner, "created_at": _now().isoformat(),
            "operation_digest": digest, **operation, "success": code == 0,
            "exit_code": code, "candidate_count": len(candidates), **persistence,
        }
        if persistence_error:
            receipt["success"] = False
            receipt["persistence_error"] = persistence_error
        await asyncio.to_thread(self.receipts.append, receipt)
        result = {
            **_public(receipt), "asset_draft_candidates": candidates,
            "requires_explicit_inventory_review": True, "untrusted_content": True,
        }
        if persistence_error:
            result.update({
                "error": "network discovery completed but CMDB observation persistence failed",
                "execution_ambiguous": True,
                "persistence_error": persistence_error,
            })
        return result

    async def _network_service_enumeration(
        self, request: dict[str, Any], *, owner: str, action: str,
    ) -> dict[str, Any]:
        targets = _private_targets(request.get("targets"))
        operation = {
            "action": "execute_network_service_enumeration",
            "target_kind": "discovered_private_ipv4_hosts",
            "targets": targets,
            "scanner": "nmap_safe_service_version_observation",
        }
        digest = _digest(operation)
        if action == "plan_network_service_enumeration":
            receipt = {
                "kind": "plan", "owner": owner, "created_at": _now().isoformat(),
                "operation_digest": digest, **operation,
                "preflight": "Observe services and versions only on the exact discovered private hosts; no OS fingerprinting, credentials, or exploitation.",
                "recovery": "Service observations are evidence and do not confirm inferred device roles.",
            }
            await asyncio.to_thread(self.receipts.append, receipt)
            return {**_public(receipt), "exit_code": 0}
        supplied = str(request.get("plan_digest") or "")
        if supplied != digest or not await asyncio.to_thread(self.receipts.valid_plan, owner=owner, digest=supplied):
            raise HomelabOperationError("a current owner-bound service enumeration plan is required")
        from src.privileged_broker import client_request
        broker_result = await asyncio.to_thread(
            client_request, {"action": "run_network_service_enumeration", "targets": targets}, timeout=90,
        )
        code = int(broker_result.get("returncode", 1)) if broker_result.get("ok") else 1
        output = str(broker_result.get("output") or broker_result.get("error") or "")
        observations = _parse_nmap_services(output, targets=targets) if code == 0 else []
        persistence_error = None
        persistence = {"observations_recorded": False, "network_map_reconciled": False}
        if code == 0:
            try:
                persistence = self._record_network_service_observations(observations, owner=owner)
            except Exception as exc:
                persistence_error = str(exc)[:500]
        receipt = {
            "kind": "service_enumeration", "owner": owner, "created_at": _now().isoformat(),
            "operation_digest": digest, **operation, "success": code == 0,
            "exit_code": code, "observation_count": len(observations), **persistence,
        }
        if persistence_error:
            receipt.update({"success": False, "persistence_error": persistence_error})
        await asyncio.to_thread(self.receipts.append, receipt)
        result = {
            **_public(receipt),
            "service_observations": observations,
            "role_hypotheses": _role_hypotheses(observations),
            "role_hypothesis_policy": "inferred_only_requires_reconciliation_before_canonical_identity",
            "untrusted_content": True,
        }
        if persistence_error:
            result.update({
                "error": "service enumeration completed but CMDB observation persistence failed",
                "execution_ambiguous": True,
                "persistence_error": persistence_error,
            })
        return result

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
