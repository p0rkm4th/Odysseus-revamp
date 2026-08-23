from __future__ import annotations

import argparse
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
AUDIT_PATH = Path("/app/data/logs/privileged_broker.log")
MAX_REQUEST = 16384
MAX_RESPONSE = 65536

ALLOWED_PACKAGES = frozenset({
    "nmap", "iproute2", "iputils-ping", "dnsutils", "ethtool",
    "pciutils", "usbutils", "smartmontools", "nvme-cli", "dmidecode",
    "lsof", "procps", "util-linux", "jq",
})
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


def package_manager():
    path = shutil.which("apt-get")
    return ("apt-get", path) if path else (None, None)


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


def handle(req, allowed_pid, allowed_uid):
    action = req.get("action")

    if action == "status":
        manager, path = package_manager()
        return {
            "ok": True,
            "action": "status",
            "broker_uid": os.geteuid(),
            "allowed_pid": allowed_pid,
            "allowed_uid": allowed_uid,
            "package_manager": manager,
            "package_manager_path": path,
            "allowed_packages": sorted(ALLOWED_PACKAGES),
        }

    if action == "install_packages":
        packages = validate_packages(req.get("packages"))
        manager, path = package_manager()
        if manager != "apt-get":
            return {
                "ok": False,
                "error": "supported package manager not available",
            }

        update = run_root([path, "update", "-qq"])
        if update["returncode"] != 0:
            return {"ok": False, "stage": "update", **update}

        install = run_root([
            path,
            "install",
            "-y",
            "--no-install-recommends",
            *packages,
        ])
        return {
            "ok": install["returncode"] == 0,
            "action": action,
            "packages": packages,
            "stage": "install",
            **install,
        }

    return {
        "ok": False,
        "error": f"unsupported privileged action: {action!r}",
    }


def serve(
    socket_path=SOCKET_PATH,
    allowed_pid=1,
    allowed_uid=1000,
    allowed_gid=1000,
):
    if os.geteuid() != 0:
        raise SystemExit("privileged broker must run as root")

    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    os.chown(socket_path, allowed_uid, allowed_gid)
    os.chmod(socket_path, 0o660)
    srv.listen(8)

    audit({
        "event": "broker_start",
        "pid": os.getpid(),
        "allowed_pid": allowed_pid,
        "allowed_uid": allowed_uid,
        "socket": socket_path,
    })

    while True:
        conn, _ = srv.accept()
        with conn:
            pid, uid, gid = peercred(conn)

            if not peer_is_allowed(
                pid,
                uid,
                gid,
                allowed_pid,
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
                    resp = handle(req, allowed_pid, allowed_uid)
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
    args = p.parse_args()

    if args.serve:
        serve(
            args.socket,
            args.allowed_pid,
            args.allowed_uid,
            args.allowed_gid,
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
