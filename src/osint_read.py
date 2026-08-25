"""Owner-scoped read projections over the existing durable research cases."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.constants import DEEP_RESEARCH_DIR

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,128}$")
RESEARCH_DATA_DIR = Path(DEEP_RESEARCH_DIR)


class OsintReadError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OsintReadError("OSINT case store could not be read") from exc
    if not isinstance(value, dict):
        raise OsintReadError("OSINT case store returned an invalid record")
    return value


def _summary(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    sources = [item for item in (data.get("sources") or []) if isinstance(item, dict)]
    return {
        "id": path.stem,
        "query": str(data.get("query") or ""),
        "category": str(data.get("category") or ""),
        "status": str(data.get("status") or "done"),
        "source_count": len(sources),
        "started_at": data.get("started_at", 0),
        "completed_at": data.get("completed_at", 0),
        "archived": bool(data.get("archived")),
        "owner_scope": str(data.get("owner") or ""),
    }


def list_cases(owner: str, *, limit: int = 50, archived: bool = False) -> dict[str, Any]:
    owner = str(owner or "").strip()
    if not owner:
        raise PermissionError("authenticated OSINT owner is required")
    root = RESEARCH_DATA_DIR.resolve()
    if not root.is_dir():
        return {"status": "EMPTY_RESULT", "cases": [], "case_count": 0, "source": "canonical_osint_case_store", "owner_scope": owner}
    cases: list[dict[str, Any]] = []
    try:
        paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        raise OsintReadError("OSINT case store is unavailable") from exc
    for path in paths:
        data = _load(path)
        if data.get("owner") != owner or bool(data.get("archived")) != archived:
            continue
        cases.append(_summary(path, data))
        if len(cases) >= max(1, min(int(limit), 200)):
            break
    return {
        "status": "EMPTY_RESULT" if not cases else "SUCCESS",
        "cases": cases,
        "case_count": len(cases),
        "source": "canonical_osint_case_store",
        "owner_scope": owner,
    }


def get_case(owner: str, case_id: str) -> dict[str, Any]:
    owner = str(owner or "").strip()
    case_id = str(case_id or "").strip()
    if not owner:
        raise PermissionError("authenticated OSINT owner is required")
    if not _SESSION_ID_RE.fullmatch(case_id):
        raise ValueError("invalid OSINT case reference")
    root = RESEARCH_DATA_DIR.resolve()
    path = (root / f"{case_id}.json").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("invalid OSINT case reference") from exc
    if not path.is_file():
        raise KeyError("OSINT case not found")
    data = _load(path)
    if data.get("owner") != owner:
        raise KeyError("OSINT case not found")
    sources = [item for item in (data.get("sources") or []) if isinstance(item, dict)]
    questions = list(data.get("open_questions") or data.get("questions") or [])
    report = str(data.get("report") or data.get("summary") or "")
    return {
        "status": "SUCCESS",
        "case": {
            **_summary(path, data),
            "sources": sources[:200],
            "open_questions": questions[:200],
            "report_excerpt": report[:4000],
            "external_content_tainted": True,
        },
        "source": "canonical_osint_case_store",
        "owner_scope": owner,
    }
