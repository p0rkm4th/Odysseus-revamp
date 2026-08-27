from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import time

SOCKET_PATH = "/run/odysseus-privd.sock"
HOST_NETWORK_SOCKET_PATH = "/run/odysseus-host-broker/network.sock"
AUDIT_PATH = Path(os.getenv("ODYSSEUS_BROKER_AUDIT_PATH", "/app/data/logs/privileged_broker.log"))
MAX_REQUEST = 16384
MAX_RESPONSE = 65536

ALLOWED_PACKAGES = frozenset({
    "nmap", "iproute2", "iputils-ping", "dnsutils", "bind", "bind9", "ethtool",
    "pciutils", "usbutils", "smartmontools", "nvme-cli", "dmidecode", "traceroute",
    "lsof", "procps", "util-linux", "jq", "cmake", "build-essential", "g++",
    "gcc", "git", "tmux", "make",
})
ALLOWED_EXECUTABLES = frozenset({"ip", "ss", "nmap", "dig", "host", "nslookup", "traceroute"})
PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:-]{0,79}$")


def audit(event):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), **event}
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def peercred(conn):
    raw = conn.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )
    return struct.unpack("3i", raw)


def peer_is_allowed(pid, uid, gid, allowed_pid, allowed_uid, allowed_gid):
    """Return whether a connecting peer matches the broker's sealed identity."""
    return (
        pid == allowed_pid
        and uid == allowed_uid
        and gid == allowed_gid
    )


def compose_service_pid(project: str, service: str) -> int | None:
    """Resolve the exact live init PID for one Compose service on the host."""
    if not project or not service:
        return None
    try:
        cp = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project}",
             "--filter", f"label=com.docker.compose.service={service}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=3, check=False,
        )
        container_ids = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
        if cp.returncode != 0 or len(container_ids) != 1:
            return None
        inspected = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Pid}}", container_ids[0]],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=3, check=False,
        )
        value = int(inspected.stdout.strip()) if inspected.returncode == 0 else 0
        return value if value > 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def package_manager():
    """Return the host package manager from a bounded supported set."""
    for name in ("pacman", "apt-get"):
        path = shutil.which(name)
        if path:
            return name, path
    return None, None


def validate_packages(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise ValueError("packages must be a list of 1..16 names")
    out = []
    for item in value:
        if not isinstance(item, str) or not PKG_RE.fullmatch(item):
            raise ValueError(f"invalid package name: {item!r}")
        if item not in ALLOWED_PACKAGES:
            raise ValueError(f"package not in diagnostic allowlist: {item}")
        if item not in out:
            out.append(item)
    return out


def run_root(argv, timeout=300):
    env = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "DEBIAN_FRONTEND": "noninteractive",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    cp = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
        cwd="/",
        env=env,
    )
    return {
        "returncode": cp.returncode,
        "output": (cp.stdout or "")[-20000:],
    }


def _private_discovery_cidr(value):
    """Validate the broker's only network operation scope."""
    if "/" not in str(value):
        raise ValueError("discovery scope must be an explicit IPv4 CIDR")
    try:
        network = ipaddress.ip_network(str(value), strict=False)
    except ValueError as exc:
        raise ValueError("discovery scope must be a valid IPv4 CIDR") from exc
    if network.version != 4 or not network.is_private or network.num_addresses > 256:
        raise ValueError("discovery scope must be private IPv4 and contain at most 256 addresses")
    return str(network)


def _private_targets(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        raise ValueError("service enumeration requires 1..256 private IPv4 targets")
    targets = []
    for item in value:
        address = ipaddress.ip_address(str(item).strip())
        if not isinstance(address, ipaddress.IPv4Address) or not address.is_private:
            raise ValueError("service enumeration targets must be private IPv4 addresses")
        if str(address) not in targets:
            targets.append(str(address))
    return targets


def _network_namespace_id():
    try:
        return str(os.stat("/proc/self/ns/net").st_ino)
    except OSError:
        return None


def handle(req, allowed_pid, allowed_uid, *, execution_location="APPLICATION_RUNTIME", read_only=False):
    action = req.get("action")

    if action == "status":
        manager, path = package_manager()
        nmap = shutil.which("nmap")
        return {
            "ok": True,
            "action": "status",
            "broker_uid": os.geteuid(),
            "allowed_pid": allowed_pid,
            "allowed_uid": allowed_uid,
            "package_manager": manager,
            "package_manager_path": path,
            "network_scanner_available": bool(nmap),
            "allowed_packages": sorted(ALLOWED_PACKAGES),
            "execution_location": execution_location,
            "network_namespace_id": _network_namespace_id(),
            "read_only": bool(read_only),
        }

    if action == "read_network_context":
        addresses = run_root(["ip", "-j", "addr"], timeout=10)
        routes = run_root(["ip", "-j", "route"], timeout=10)
        return {
            "ok": addresses["returncode"] == 0 and routes["returncode"] == 0,
            "action": action,
            "addresses": addresses["output"],
            "routes": routes["output"],
            "exit_code": max(addresses["returncode"], routes["returncode"]),
            "execution_location": execution_location,
            "network_namespace_id": _network_namespace_id(),
        }

    if read_only:
        return {"ok": False, "error": "host network broker is read-only"}

    if action == "run_network_discovery":
        try:
            cidr = _private_discovery_cidr(req.get("cidr"))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        nmap = shutil.which("nmap")
        if not nmap:
            return {"ok": False, "error": "nmap is not available on the host"}
        result = run_root([
            nmap, "-sn", "-n", "--max-retries", "1", "--host-timeout", "5s",
            "-oX", "-", cidr,
        ], timeout=60)
        return {
            "ok": result["returncode"] == 0,
            "action": action,
            "cidr": cidr,
            "scanner": "nmap_ping_scan",
            **result,
        }

    if action == "run_network_service_enumeration":
        try:
            targets = _private_targets(req.get("targets"))
        except (TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        nmap = shutil.which("nmap")
        if not nmap:
            return {"ok": False, "error": "nmap is not available on the host"}
        result = run_root([
            nmap, "-sV", "--version-light", "-Pn", "-n", "--max-retries", "1",
            "--host-timeout", "10s", "-p", "1-1024", "-oX", "-", *targets,
        ], timeout=90)
        return {
            "ok": result["returncode"] == 0,
            "action": action, "targets": targets,
            "scanner": "nmap_safe_service_version_observation", **result,
        }

    if action == "install_packages":
        packages = validate_packages(req.get("packages"))
        manager, path = package_manager()
        if manager not in {"apt-get", "pacman"}:
            return {
                "ok": False,
                "error": "supported package manager not available",
            }
        if manager == "pacman":
            # Do not refresh repositories implicitly. Package installation is
            # still exact-approval gated and limited to ALLOWED_PACKAGES.
            install = run_root([path, "-S", "--needed", "--noconfirm", *packages])
        else:
            update = run_root([path, "update", "-qq"])
            if update["returncode"] != 0:
                return {"ok": False, "stage": "update", **update}
            install = run_root([
                path, "install", "-y", "--no-install-recommends", *packages,
            ])
        return {
            "ok": install["returncode"] == 0,
            "action": action,
            "package_manager": manager,
            "packages": packages,
            "stage": "install",
            **install,
        }

    if action == "verify_executables":
        executables = req.get("executables")
        if not isinstance(executables, list) or not 1 <= len(executables) <= 16:
            return {"ok": False, "error": "executables must be a list of 1..16 names"}
        if any(not isinstance(name, str) or name not in ALLOWED_EXECUTABLES for name in executables):
            return {"ok": False, "error": "executable is not in the prerequisite allowlist"}
        paths = {name: shutil.which(name) for name in executables}
        return {"ok": all(paths.values()), "action": action, "executables": paths}

    return {
        "ok": False,
        "error": f"unsupported privileged action: {action!r}",
    }


def serve(
    socket_path=SOCKET_PATH,
    allowed_pid=1,
    allowed_uid=1000,
    allowed_gid=1000,
    execution_location="APPLICATION_RUNTIME",
    read_only=False,
    compose_project=None,
    compose_service=None,
):
    if os.geteuid() != 0 and not read_only:
        raise SystemExit("privileged broker must run as root")

    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    if os.geteuid() == 0:
        os.chown(socket_path, allowed_uid, allowed_gid)
    os.chmod(socket_path, 0o660)
    srv.listen(8)

    audit({
        "event": "broker_start",
        "pid": os.getpid(),
        "allowed_pid": allowed_pid,
        "allowed_uid": allowed_uid,
        "socket": socket_path,
        "execution_location": execution_location,
        "network_namespace_id": _network_namespace_id(),
        "read_only": bool(read_only),
    })

    while True:
        conn, _ = srv.accept()
        with conn:
            pid, uid, gid = peercred(conn)

            expected_pid = (
                compose_service_pid(compose_project, compose_service)
                if compose_project and compose_service else allowed_pid
            )
            if expected_pid is None or not peer_is_allowed(
                pid,
                uid,
                gid,
                expected_pid,
                allowed_uid,
                allowed_gid,
            ):
                resp = {
                    "ok": False,
                    "error": "peer denied",
                    "peer": {"pid": pid, "uid": uid, "gid": gid},
                }
                audit({
                    "event": "peer_denied",
                    "pid": pid,
                    "uid": uid,
                    "gid": gid,
                    "expected_pid": expected_pid,
                })
                conn.sendall((json.dumps(resp) + "\n").encode())
                continue

            data = b""
            while b"\n" not in data and len(data) <= MAX_REQUEST:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            req = None
            if len(data) > MAX_REQUEST:
                resp = {"ok": False, "error": "request too large"}
            else:
                try:
                    req = json.loads(
                        data.split(b"\n", 1)[0].decode("utf-8")
                    )
                    resp = handle(
                        req, expected_pid, allowed_uid,
                        execution_location=execution_location,
                        read_only=read_only,
                    )
                except Exception as exc:
                    resp = {"ok": False, "error": str(exc)}

            audit({
                "event": "request",
                "peer_pid": pid,
                "peer_uid": uid,
                "action": req.get("action") if isinstance(req, dict) else None,
                "ok": bool(resp.get("ok")),
                "error": resp.get("error"),
            })

            payload = (
                json.dumps(resp, sort_keys=True) + "\n"
            ).encode()
            conn.sendall(payload[:MAX_RESPONSE])


def client_request(
    req,
    socket_path=SOCKET_PATH,
    timeout=310,
):
    if not isinstance(req, dict):
        raise ValueError("privileged request must be an object")

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(socket_path)
        s.sendall(
            (json.dumps(req, sort_keys=True) + "\n").encode()
        )
        data = b""
        while b"\n" not in data and len(data) <= MAX_RESPONSE:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()

    if not data:
        raise RuntimeError("privileged broker returned no data")

    return json.loads(
        data.split(b"\n", 1)[0].decode("utf-8")
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--serve", action="store_true")
    p.add_argument("--socket", default=SOCKET_PATH)
    p.add_argument("--allowed-pid", type=int, default=1)
    p.add_argument("--allowed-uid", type=int, default=1000)
    p.add_argument("--allowed-gid", type=int, default=1000)
    p.add_argument("--execution-location", choices=("HOST", "APPLICATION_RUNTIME", "SANDBOX", "REMOTE_NODE"), default="APPLICATION_RUNTIME")
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--compose-project")
    p.add_argument("--compose-service")
    args = p.parse_args()

    if args.serve:
        serve(
            args.socket,
            args.allowed_pid,
            args.allowed_uid,
            args.allowed_gid,
            args.execution_location,
            args.read_only,
            args.compose_project,
            args.compose_service,
        )
        return 0

    print(json.dumps(
        client_request({"action": "status"}, args.socket),
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
