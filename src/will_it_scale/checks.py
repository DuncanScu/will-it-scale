"""Deterministic checks: turn collected facts into findings.

No LLM here. Each finding is a factual comparison of observed state against a
declared rule, matching the check schema in notes.md
(id, status, evidence, confidence, severity, remediation).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .collectors.k8s import WorkloadFacts

# Status values.
PASS = "pass"
WARNING = "warning"
FAIL = "fail"
UNKNOWN = "unknown"

# Severity values.
LOW = "low"
MEDIUM = "medium"
HIGH = "high"

# Deterministic checks are certain about what they observed.
DETERMINISTIC_CONFIDENCE = 1.0

# Availability baseline: a workload should run more than one replica.
MIN_REPLICAS = 2


@dataclass
class Finding:
    id: str
    category: str
    resource: str
    status: str
    description: str
    desired: str
    observed: str
    severity: str
    remediation: str
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = DETERMINISTIC_CONFIDENCE
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has(resource_map: dict[str, str] | None, *keys: str) -> bool:
    return bool(resource_map) and all(k in resource_map for k in keys)


def evaluate_cluster(cluster_info: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    for pool in cluster_info.get("node_pools", []):
        autoscaling_on = pool.get("min_count") is not None and pool.get("max_count") is not None
        findings.append(
            Finding(
                id=f"aks.nodepool.{pool['name']}.autoscaling",
                category="capacity",
                resource=f"nodepool/{pool['name']}",
                status=PASS if autoscaling_on else WARNING,
                description="Node pool has cluster autoscaler bounds configured.",
                desired="min_count and max_count set",
                observed=f"min={pool.get('min_count')} max={pool.get('max_count')}",
                severity=MEDIUM,
                remediation="Enable the cluster autoscaler on the node pool with sensible min/max counts.",
                evidence={"vm_size": pool.get("vm_size"), "count": pool.get("count")},
            )
        )

    return findings


def evaluate_workloads(facts: WorkloadFacts) -> list[Finding]:
    findings: list[Finding] = []
    hpa_by_target = {h["target"]: h for h in facts.hpas}
    multi_replica = [d for d in facts.deployments if (d.get("replicas") or 0) > 1]

    for d in facts.deployments:
        name = d["name"]
        ns = facts.namespace
        replicas = d.get("replicas") or 0
        base = f"{ns}/{name}"

        findings.append(
            Finding(
                id=f"k8s.deploy.{ns}.{name}.replicas",
                category="reliability",
                resource=f"deployment/{base}",
                status=PASS if replicas >= MIN_REPLICAS else WARNING,
                description="Workload runs at least the minimum replica count.",
                desired=f">= {MIN_REPLICAS} replicas",
                observed=f"{replicas} replicas",
                severity=MEDIUM,
                remediation="Increase replicas (or set HPA minReplicas) so a single pod failure is not an outage.",
                evidence={"replicas": replicas},
            )
        )

        hpa = hpa_by_target.get(name)
        if hpa is None:
            hpa_status, hpa_observed = WARNING, "no HPA"
            hpa_remediation = "Add an HPA with sensible min/max replicas for the expected load."
        elif hpa.get("min_replicas") == hpa.get("max_replicas"):
            hpa_status = WARNING
            hpa_observed = f"HPA pinned at {hpa.get('min_replicas')} (min == max)"
            hpa_remediation = "Set maxReplicas above minReplicas so the HPA can actually scale out."
        else:
            hpa_status = PASS
            hpa_observed = f"HPA {hpa.get('min_replicas')}-{hpa.get('max_replicas')} replicas"
            hpa_remediation = "Keep min/max replicas sized for the expected load."

        findings.append(
            Finding(
                id=f"k8s.deploy.{ns}.{name}.hpa",
                category="capacity",
                resource=f"deployment/{base}",
                status=hpa_status,
                description="Workload has a Horizontal Pod Autoscaler that can scale.",
                desired="HPA targeting the workload with maxReplicas > minReplicas",
                observed=hpa_observed,
                severity=LOW,
                remediation=hpa_remediation,
                evidence={"hpa": hpa},
            )
        )

        # Runtime health: only present when facts came from a live cluster.
        if "pods" in d:
            desired = d.get("replicas") or 0
            ready = d.get("ready_replicas") or 0
            pods = d.get("pods") or []
            unready = [p for p in pods if not p.get("ready")]
            reasons = sorted({p["reason"] for p in unready if p.get("reason")})
            healthy = ready >= desired and not unready
            detail = f"; {', '.join(reasons)}" if reasons else ""
            findings.append(
                Finding(
                    id=f"k8s.deploy.{ns}.{name}.rollout",
                    category="runtime health",
                    resource=f"deployment/{base}",
                    status=PASS if healthy else (FAIL if ready == 0 and desired > 0 else WARNING),
                    description="Deployment has its desired number of ready pods.",
                    desired=f"{desired}/{desired} pods ready",
                    observed=f"{ready}/{desired} pods ready{detail}",
                    severity=LOW if healthy else (HIGH if ready == 0 and desired > 0 else MEDIUM),
                    remediation="Investigate pods that are not Ready (scheduling, image pull, crash loop, or resource limits).",
                    evidence={
                        "ready_replicas": ready,
                        "available_replicas": d.get("available_replicas"),
                        "pods": pods,
                    },
                )
            )

        for c in d.get("containers", []):
            cname = c["name"]
            cbase = f"{base}/{cname}"

            requests_ok = _has(c.get("requests"), "cpu", "memory")
            limits_ok = _has(c.get("limits"), "cpu", "memory")
            findings.append(
                Finding(
                    id=f"k8s.container.{ns}.{name}.{cname}.resources",
                    category="resources",
                    resource=f"container/{cbase}",
                    status=PASS if (requests_ok and limits_ok) else FAIL if not requests_ok else WARNING,
                    description="Container declares CPU/memory requests and limits.",
                    desired="cpu+memory requests and limits set",
                    observed=f"requests={'set' if requests_ok else 'missing'}, limits={'set' if limits_ok else 'missing'}",
                    severity=MEDIUM,
                    remediation="Set both requests and limits for CPU and memory to keep the pod schedulable and bounded.",
                    evidence={"requests": c.get("requests"), "limits": c.get("limits")},
                )
            )

            probes_ok = c.get("has_readiness_probe") and c.get("has_liveness_probe")
            findings.append(
                Finding(
                    id=f"k8s.container.{ns}.{name}.{cname}.probes",
                    category="reliability",
                    resource=f"container/{cbase}",
                    status=PASS if probes_ok else WARNING,
                    description="Container defines readiness and liveness probes.",
                    desired="readiness and liveness probes set",
                    observed=f"readiness={c.get('has_readiness_probe')}, liveness={c.get('has_liveness_probe')}",
                    severity=MEDIUM,
                    remediation="Add readiness and liveness probes so Kubernetes can route and restart correctly.",
                    evidence={
                        "readiness": c.get("has_readiness_probe"),
                        "liveness": c.get("has_liveness_probe"),
                    },
                )
            )

    findings.append(
        Finding(
            id=f"k8s.namespace.{facts.namespace}.pdb_coverage",
            category="reliability",
            resource=f"namespace/{facts.namespace}",
            status=PASS if (not multi_replica or facts.pdbs) else WARNING,
            description="Multi-replica workloads are protected by a Pod Disruption Budget.",
            desired="at least one PDB when multi-replica workloads exist",
            observed=f"{len(multi_replica)} multi-replica deploys, {len(facts.pdbs)} PDBs",
            severity=MEDIUM,
            remediation="Add PodDisruptionBudgets so voluntary disruptions cannot take all replicas down at once.",
            evidence={"pdbs": [p["name"] for p in facts.pdbs]},
        )
    )

    return findings
