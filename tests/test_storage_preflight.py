"""Release guard regressions for the narrow, non-destructive build preflight."""

from pathlib import Path
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "storage_preflight.sh"


pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="Docker is required to exercise the release storage guard",
)


def _run(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.run(
        [str(PREFLIGHT)], cwd=ROOT, env=env,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )


def test_storage_preflight_fails_closed_before_insufficient_headroom_build():
    result = _run({
        "ODYSSEUS_MIN_FREE_GIB": "999999",
        "ODYSSEUS_MAX_ROOT_USED_PERCENT": "100",
        "ODYSSEUS_EMERGENCY_RESERVE_GIB": "999999",
    })
    assert result.returncode == 2
    assert "STORAGE_PREFLIGHT_BLOCKED" in result.stdout
    assert "projected_free_gib=" in result.stdout
    assert "candidate_tags=" in result.stdout
    assert "rollback_tags=" in result.stdout


def test_storage_preflight_can_report_without_blocking_when_thresholds_are_safe():
    result = _run({"ODYSSEUS_MIN_FREE_GIB": "0", "ODYSSEUS_MAX_ROOT_USED_PERCENT": "100"})
    assert result.returncode == 0
    assert "STORAGE_PREFLIGHT root_free_gib=" in result.stdout
    assert "obsolete_unreferenced_candidates=" in result.stdout


def test_storage_preflight_labels_preferred_green_zone():
    result = _run({
        "ODYSSEUS_MIN_FREE_GIB": "0",
        "ODYSSEUS_MAX_ROOT_USED_PERCENT": "100",
        "ODYSSEUS_BUILD_PEAK_GIB": "0",
        "ODYSSEUS_EMERGENCY_RESERVE_GIB": "0",
    })
    assert result.returncode == 0
    assert "zone=GREEN" in result.stdout


def test_storage_preflight_allows_caution_with_projected_headroom():
    result = _run({
        "ODYSSEUS_MIN_FREE_GIB": "999999",
        "ODYSSEUS_MAX_ROOT_USED_PERCENT": "100",
        "ODYSSEUS_BUILD_PEAK_GIB": "1",
        "ODYSSEUS_EMERGENCY_RESERVE_GIB": "1",
    })
    assert result.returncode == 0
    assert "zone=CAUTION" in result.stdout
    assert "projected_free_gib=" in result.stdout


def test_storage_preflight_blocks_caution_without_projected_headroom():
    result = _run({
        "ODYSSEUS_MIN_FREE_GIB": "999999",
        "ODYSSEUS_MAX_ROOT_USED_PERCENT": "100",
        "ODYSSEUS_BUILD_PEAK_GIB": "1",
        "ODYSSEUS_EMERGENCY_RESERVE_GIB": "999999",
    })
    assert result.returncode == 2
    assert "projected candidate build" in result.stdout


def test_storage_preflight_blocks_hard_free_space_threshold():
    result = _run({
        "ODYSSEUS_MIN_FREE_GIB": "0",
        "ODYSSEUS_MAX_ROOT_USED_PERCENT": "100",
        "ODYSSEUS_HARD_MIN_FREE_GIB": "999999",
    })
    assert result.returncode == 2
    assert "hard filesystem threshold" in result.stdout
