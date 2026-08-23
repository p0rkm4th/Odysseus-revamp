"""Privacy-preserving hardware metadata for reproducible Jarvis runs."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any, Callable


def _memory_bytes() -> int | None:
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return pages * page_size if pages > 0 and page_size > 0 else None
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _nvidia_gpus(
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    binary = which("nvidia-smi")
    if not binary:
        return []
    try:
        result = run(
            [
                binary,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    devices = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3 or not parts[0]:
            continue
        try:
            memory_mib = int(parts[1])
        except ValueError:
            continue
        devices.append({
            "vendor": "nvidia",
            "name": parts[0][:160],
            "vram_mib": memory_mib,
            "driver": parts[2][:80],
        })
    return devices


def probe_hardware() -> dict[str, Any]:
    """Return stable benchmark metadata without hostnames, users, or IDs."""
    memory = _memory_bytes()
    gpus = _nvidia_gpus()
    return {
        "schema_version": 1,
        "os": platform.system().casefold() or "unknown",
        "architecture": platform.machine().casefold() or "unknown",
        "cpu_logical_count": os.cpu_count(),
        "memory_mib": memory // (1024 * 1024) if memory is not None else None,
        "accelerators": gpus,
        "nvidia_available": bool(gpus),
    }
