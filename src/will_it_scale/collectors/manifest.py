"""Parse Kubernetes manifests into WorkloadFacts for the deterministic checks.

This lets the same checks run on a static manifest file (shift-left, pre-deploy)
exactly as they run on a live cluster -- no cluster access required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .k8s import WorkloadFacts


def load_workload_facts(path: str | Path, namespace: str = "manifest") -> WorkloadFacts:
    docs = list(yaml.safe_load_all(Path(path).read_text(encoding="utf-8")))
    return facts_from_docs([d for d in docs if d], namespace)


def facts_from_docs(docs: list[dict[str, Any]], namespace: str = "manifest") -> WorkloadFacts:
    facts = WorkloadFacts(namespace=namespace)
    for doc in docs:
        kind = doc.get("kind")
        if kind == "Deployment":
            facts.deployments.append(_deployment(doc))
        elif kind == "HorizontalPodAutoscaler":
            facts.hpas.append(_hpa(doc))
        elif kind == "PodDisruptionBudget":
            facts.pdbs.append(_pdb(doc))
    return facts


def _deployment(doc: dict[str, Any]) -> dict[str, Any]:
    spec = doc.get("spec") or {}
    pod_spec = (spec.get("template") or {}).get("spec") or {}
    containers = []
    for c in pod_spec.get("containers") or []:
        resources = c.get("resources") or {}
        containers.append(
            {
                "name": c.get("name"),
                "requests": resources.get("requests"),
                "limits": resources.get("limits"),
                "has_readiness_probe": "readinessProbe" in c,
                "has_liveness_probe": "livenessProbe" in c,
            }
        )
    replicas = spec.get("replicas")
    return {
        "name": (doc.get("metadata") or {}).get("name"),
        # Kubernetes defaults an unset replica count to 1.
        "replicas": 1 if replicas is None else replicas,
        "containers": containers,
    }


def _hpa(doc: dict[str, Any]) -> dict[str, Any]:
    spec = doc.get("spec") or {}
    return {
        "name": (doc.get("metadata") or {}).get("name"),
        "min_replicas": spec.get("minReplicas"),
        "max_replicas": spec.get("maxReplicas"),
        "target": (spec.get("scaleTargetRef") or {}).get("name"),
    }


def _pdb(doc: dict[str, Any]) -> dict[str, Any]:
    spec = doc.get("spec") or {}
    min_available = spec.get("minAvailable")
    max_unavailable = spec.get("maxUnavailable")
    return {
        "name": (doc.get("metadata") or {}).get("name"),
        "min_available": None if min_available is None else str(min_available),
        "max_unavailable": None if max_unavailable is None else str(max_unavailable),
    }
