"""Persist findings to timestamped JSON so runs can be reviewed and compared."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .checks import FAIL, WARNING, Finding

FINDINGS_ROOT = Path("findings")


def save_findings(cluster: str, findings: list[Finding], interpretation: dict[str, Any] | None = None) -> Path:
    """Write a run to findings/<cluster>/<timestamp>.json and return its path."""
    run_dir = FINDINGS_ROOT / cluster
    run_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = run_dir / f"{stamp}.json"

    payload: dict[str, Any] = {
        "cluster": cluster,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize(findings),
        "interpretation": interpretation,
        "findings": [f.to_dict() for f in findings],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def latest_previous(cluster: str, exclude: Path) -> dict[str, Any] | None:
    """Return the most recent prior run for regression comparison, if any."""
    run_dir = FINDINGS_ROOT / cluster
    if not run_dir.exists():
        return None
    runs = sorted(p for p in run_dir.glob("*.json") if p != exclude)
    if not runs:
        return None
    return json.loads(runs[-1].read_text())


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.status] = counts.get(f.status, 0) + 1
    return counts


def new_regressions(current: list[Finding], previous: dict[str, Any] | None) -> list[Finding]:
    """Findings that are failing/warning now but were passing (or absent) before."""
    if not previous:
        return []
    prior_bad = {
        f["id"] for f in previous.get("findings", []) if f["status"] in (FAIL, WARNING)
    }
    return [f for f in current if f.status in (FAIL, WARNING) and f.id not in prior_bad]
