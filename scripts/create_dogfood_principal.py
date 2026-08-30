#!/usr/bin/env python3
"""Create a persistent, non-privileged user for an isolated dogfood lane."""
from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

from core.auth import AuthManager, DEFAULT_AUTH_PATH, PASSWORD_MIN_LENGTH


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-path", default=str(DEFAULT_AUTH_PATH))
    parser.add_argument("--credential-file", default="/tmp/hades-owner-dogfood/credentials.json")
    parser.add_argument("--username", default="hades-dogfood")
    args = parser.parse_args()
    username = str(args.username).strip().lower()
    if not username or username in {"admin", "root", "owner", "hades-acceptance"}:
        raise SystemExit("refusing reserved or acceptance username")
    password = secrets.token_urlsafe(32)
    if len(password) < PASSWORD_MIN_LENGTH:
        raise SystemExit("generated password did not meet minimum length")
    manager = AuthManager(args.auth_path)
    if username in manager.users:
        raise SystemExit(f"user already exists: {username}")
    if not manager.create_user(username, password, is_admin=False):
        raise SystemExit("could not create dogfood user")
    destination = Path(args.credential_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"username": username, "password": password}
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(destination, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        fd = -1
    finally:
        if fd >= 0:
            os.close(fd)
    print(json.dumps({"principal": username, "credential_file": str(destination)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
