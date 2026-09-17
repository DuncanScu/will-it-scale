from pathlib import Path

from will_it_scale.checks import WARNING, evaluate_workloads
from will_it_scale.collectors.manifest import load_workload_facts

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "test_data/sample_service/kubernetes/deployment.yaml"
)


def only(findings, suffix):
    matches = [f for f in findings if f.id.endswith(suffix)]
    assert len(matches) == 1, f"expected 1 finding ending '{suffix}', got {len(matches)}"
    return matches[0]


def test_manifest_parses_fixture():
    facts = load_workload_facts(FIXTURE, namespace="demo")
    assert [d["name"] for d in facts.deployments] == ["order-service"]
    assert facts.hpas[0]["min_replicas"] == 1
    assert facts.hpas[0]["max_replicas"] == 1
    assert facts.pdbs[0]["name"] == "order-service"


def test_manifest_findings_flag_fixture_risks():
    facts = load_workload_facts(FIXTURE, namespace="demo")
    findings = evaluate_workloads(facts)
    assert only(findings, ".replicas").status == WARNING  # single replica
    assert only(findings, ".resources").status == WARNING  # requests set, no limits
    assert only(findings, ".probes").status == WARNING  # no liveness probe
    assert only(findings, ".hpa").status == WARNING  # pinned min == max
