"""Deterministic assessment engine: collect facts, evaluate checks, report findings.

Read-only. Produces findings for human review; recommends, never deploys. Driven by
the `will-it-scale` CLI (see `will_it_scale.__main__`); not a standalone entry point.
"""

from __future__ import annotations

import os

from .checks import FAIL, PASS, WARNING, Finding, evaluate_cluster, evaluate_workloads
from .collectors.k8s import collect_workloads, get_cluster_info
from .findings_store import latest_previous, new_regressions, save_findings, summarize

_STATUS_ORDER = {FAIL: 0, WARNING: 1, PASS: 2}


def run(subscription_id: str, resource_group: str, cluster_name: str, namespace: str) -> list[Finding]:
    cluster_info = get_cluster_info(subscription_id, resource_group, cluster_name)
    facts = collect_workloads(subscription_id, resource_group, cluster_name, namespace)
    return evaluate_cluster(cluster_info) + evaluate_workloads(facts)


def _print_summary(findings: list[Finding]) -> None:
    counts = summarize(findings)
    print(
        f"\nFindings: {counts.get(FAIL, 0)} fail, "
        f"{counts.get(WARNING, 0)} warning, {counts.get(PASS, 0)} pass"
    )
    ordered = sorted(findings, key=lambda f: (_STATUS_ORDER.get(f.status, 9), f.id))
    for f in ordered:
        if f.status == PASS:
            continue
        print(f"  [{f.status.upper():7}] {f.severity:6} {f.id}")
        print(f"            {f.observed}  ->  {f.remediation}")


def report_findings(findings: list[Finding], label: str, *, interpret: bool = False) -> None:
    """Optionally interpret, then print, persist, and diff a set of findings."""
    interpretation = None
    if interpret:
        from .interpret import interpret_findings

        endpoint = os.environ.get(
            "FOUNDRY_ENDPOINT", "https://deploy-assess-foundry.cognitiveservices.azure.com/"
        )
        deployment = os.environ.get("FOUNDRY_DEPLOYMENT", "gpt-4.1")
        interpretation = interpret_findings(findings, endpoint, deployment)

    path = save_findings(label, findings, interpretation)

    _print_summary(findings)

    if interpretation:
        print("\n== Foundry interpretation ==")
        print(interpretation.get("executive_summary", ""))
        for risk in interpretation.get("top_risks", []):
            ids = ", ".join(risk.get("finding_ids", []))
            print(f"  [{risk.get('priority', '?').upper()}] {risk.get('theme')}: {risk.get('why_it_matters')}")
            print(f"        evidence: {ids}")

    previous = latest_previous(label, exclude=path)
    regressions = new_regressions(findings, previous)
    if regressions:
        print(f"\nNew regressions since last run ({len(regressions)}):")
        for f in regressions:
            print(f"  - {f.id}: {f.observed}")

    print(f"\nSaved: {path}")
