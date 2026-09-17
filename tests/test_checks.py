from will_it_scale.checks import (
    FAIL,
    PASS,
    WARNING,
    evaluate_cluster,
    evaluate_workloads,
)
from will_it_scale.collectors.k8s import WorkloadFacts

FULL_REQUESTS = {"cpu": "100m", "memory": "128Mi"}
FULL_LIMITS = {"cpu": "200m", "memory": "256Mi"}


def container(name="c", requests=None, limits=None, readiness=True, liveness=True):
    return {
        "name": name,
        "requests": requests,
        "limits": limits,
        "has_readiness_probe": readiness,
        "has_liveness_probe": liveness,
    }


def deployment(name="app", replicas=2, containers=None):
    return {"name": name, "replicas": replicas, "containers": containers or [container()]}


def hpa(target, min_replicas, max_replicas):
    return {
        "name": target,
        "min_replicas": min_replicas,
        "max_replicas": max_replicas,
        "target": target,
    }


def node_pool(name="system", min_count=None, max_count=None):
    return {
        "name": name,
        "vm_size": "Standard_D2s_v3",
        "count": 1,
        "min_count": min_count,
        "max_count": max_count,
        "mode": "System",
    }


def facts(deployments=None, hpas=None, pdbs=None, namespace="default"):
    return WorkloadFacts(
        namespace=namespace,
        deployments=deployments or [],
        hpas=hpas or [],
        pdbs=pdbs or [],
    )


def only(findings, suffix):
    matches = [f for f in findings if f.id.endswith(suffix)]
    assert len(matches) == 1, f"expected 1 finding ending '{suffix}', got {len(matches)}"
    return matches[0]


# --- replicas ---------------------------------------------------------------


def test_replicas_below_minimum_warns():
    result = evaluate_workloads(facts(deployments=[deployment(replicas=1)]))
    assert only(result, ".replicas").status == WARNING


def test_replicas_meets_minimum_passes():
    result = evaluate_workloads(facts(deployments=[deployment(replicas=2)]))
    assert only(result, ".replicas").status == PASS


# --- requests / limits ------------------------------------------------------


def test_resources_complete_passes():
    d = deployment(containers=[container(requests=FULL_REQUESTS, limits=FULL_LIMITS)])
    assert only(evaluate_workloads(facts(deployments=[d])), ".resources").status == PASS


def test_resources_missing_limits_warns():
    d = deployment(containers=[container(requests=FULL_REQUESTS, limits=None)])
    assert only(evaluate_workloads(facts(deployments=[d])), ".resources").status == WARNING


def test_resources_missing_requests_fails():
    d = deployment(containers=[container(requests=None, limits=None)])
    assert only(evaluate_workloads(facts(deployments=[d])), ".resources").status == FAIL


# --- probes -----------------------------------------------------------------


def test_probes_complete_passes():
    d = deployment(containers=[container(readiness=True, liveness=True)])
    assert only(evaluate_workloads(facts(deployments=[d])), ".probes").status == PASS


def test_probes_missing_liveness_warns():
    d = deployment(containers=[container(readiness=True, liveness=False)])
    assert only(evaluate_workloads(facts(deployments=[d])), ".probes").status == WARNING


# --- HPA --------------------------------------------------------------------


def test_hpa_absent_warns():
    result = evaluate_workloads(facts(deployments=[deployment(name="app")]))
    assert only(result, ".hpa").status == WARNING


def test_hpa_pinned_warns():
    result = evaluate_workloads(
        facts(deployments=[deployment(name="app")], hpas=[hpa("app", 1, 1)])
    )
    finding = only(result, ".hpa")
    assert finding.status == WARNING
    assert "pinned" in finding.observed


def test_hpa_healthy_passes():
    result = evaluate_workloads(
        facts(deployments=[deployment(name="app")], hpas=[hpa("app", 2, 5)])
    )
    assert only(result, ".hpa").status == PASS


# --- PDB coverage -----------------------------------------------------------


def test_pdb_coverage_multi_replica_without_pdb_warns():
    result = evaluate_workloads(facts(deployments=[deployment(replicas=3)], pdbs=[]))
    assert only(result, ".pdb_coverage").status == WARNING


def test_pdb_coverage_multi_replica_with_pdb_passes():
    pdb = {"name": "p", "min_available": "1", "max_unavailable": None}
    result = evaluate_workloads(facts(deployments=[deployment(replicas=3)], pdbs=[pdb]))
    assert only(result, ".pdb_coverage").status == PASS


def test_pdb_coverage_single_replica_passes():
    result = evaluate_workloads(facts(deployments=[deployment(replicas=1)], pdbs=[]))
    assert only(result, ".pdb_coverage").status == PASS


# --- cluster node pools -----------------------------------------------------


def test_cluster_autoscaling_absent_warns():
    result = evaluate_cluster({"node_pools": [node_pool(min_count=None, max_count=None)]})
    assert only(result, ".autoscaling").status == WARNING


def test_cluster_autoscaling_configured_passes():
    result = evaluate_cluster({"node_pools": [node_pool(min_count=1, max_count=5)]})
    assert only(result, ".autoscaling").status == PASS


# --- runtime health (live pod status) ---------------------------------------


def live_deployment(name="app", replicas=1, ready=1, pods=None):
    return {
        "name": name,
        "replicas": replicas,
        "ready_replicas": ready,
        "available_replicas": ready,
        "containers": [container()],
        "pods": pods if pods is not None else [],
    }


def test_rollout_unschedulable_fails():
    d = live_deployment(
        replicas=1,
        ready=0,
        pods=[{"name": "p1", "phase": "Pending", "ready": False, "reason": "Unschedulable: insufficient cpu"}],
    )
    finding = only(evaluate_workloads(facts(deployments=[d])), ".rollout")
    assert finding.status == FAIL
    assert "0/1" in finding.observed
    assert "Unschedulable" in finding.observed


def test_rollout_healthy_passes():
    d = live_deployment(
        replicas=2,
        ready=2,
        pods=[
            {"name": "a", "phase": "Running", "ready": True, "reason": None},
            {"name": "b", "phase": "Running", "ready": True, "reason": None},
        ],
    )
    assert only(evaluate_workloads(facts(deployments=[d])), ".rollout").status == PASS


def test_no_rollout_finding_without_pod_data():
    # Manifest-shaped deployment (no runtime pod data) -> no rollout finding.
    ids = [f.id for f in evaluate_workloads(facts(deployments=[deployment(replicas=1)]))]
    assert not any(i.endswith(".rollout") for i in ids)


# --- fixture scenario (mirrors test_data/sample_service) --------------------


def test_fixture_order_service_flags_expected_risks():
    order_service = deployment(
        name="order-service",
        replicas=1,
        containers=[
            container(
                name="order-service",
                requests={"cpu": "8", "memory": "32Gi"},
                limits=None,
                readiness=True,
                liveness=False,
            )
        ],
    )
    result = evaluate_workloads(
        facts(
            deployments=[order_service],
            hpas=[hpa("order-service", 1, 1)],
            pdbs=[{"name": "order-service", "min_available": "1", "max_unavailable": None}],
        )
    )
    assert only(result, ".replicas").status == WARNING
    assert only(result, ".resources").status == WARNING  # requests but no limits
    assert only(result, ".probes").status == WARNING  # no liveness probe
    assert only(result, ".hpa").status == WARNING  # pinned min == max
