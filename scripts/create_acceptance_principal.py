#!/usr/bin/env python3
"""Create or remove the explicitly enabled Hades live-test principal.

This is a local operator utility. It uses AuthManager's normal password
hashing/session store and never exposes a network authentication bypass.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import time
from pathlib import Path

from core.auth import (
    ACCEPTANCE_USERNAME,
    AuthManager,
    DEFAULT_AUTH_PATH,
    PASSWORD_MIN_LENGTH,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-path", default=str(DEFAULT_AUTH_PATH))
    parser.add_argument("--credential-file", default="/tmp/hades-acceptance-credentials.json")
    parser.add_argument("--ttl", type=int, default=600)
    parser.add_argument(
        "--allow-research", action="store_true",
        help="enable research only for this explicitly disposable acceptance account",
    )
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    manager = AuthManager(args.auth_path)
    if args.revoke:
        removed = manager.delete_acceptance_principal()
        print(json.dumps({"principal": ACCEPTANCE_USERNAME, "removed": removed}))
        return 0
    if not manager.acceptance_principal_enabled():
        raise SystemExit("acceptance principal disabled; set HADES_ACCEPTANCE_PRINCIPAL_ENABLED=true explicitly")
    if not 1 <= args.ttl <= 900:
        raise SystemExit("--ttl must be between 1 and 900 seconds")
    password = secrets.token_urlsafe(32)
    account_expiry = time.time() + args.ttl
    if not manager.create_acceptance_principal(
        password, expires_at=account_expiry, allow_research=args.allow_research,
    ):
        raise SystemExit("could not create acceptance principal")
    destination = Path(args.credential_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"username": ACCEPTANCE_USERNAME, "password": password, "expires_at": account_expiry}
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(destination, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        fd = -1
    finally:
        if fd >= 0:
            os.close(fd)
    print(json.dumps({"principal": ACCEPTANCE_USERNAME, "credential_file": str(destination), "expires_at": account_expiry}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
