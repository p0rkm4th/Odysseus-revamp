"""Regression coverage for co-hosted Hades/Odysseus browser sessions."""

import os
import subprocess
import sys
from pathlib import Path


def _session_cookie(env_value=None):
    env = os.environ.copy()
    if env_value is None:
        env.pop("SESSION_COOKIE_NAME", None)
    else:
        env["SESSION_COOKIE_NAME"] = env_value
    root = Path(__file__).resolve().parent.parent
    return subprocess.check_output(
        [sys.executable, "-c", "from routes.auth_routes import SESSION_COOKIE; print(SESSION_COOKIE)"],
        cwd=root,
        env=env,
        text=True,
    ).strip()


def test_session_cookie_name_defaults_for_legacy_deployments():
    assert _session_cookie() == "odysseus_session"


def test_session_cookie_name_can_separate_cohosted_instances():
    assert _session_cookie("hades_session") == "hades_session"
