"""Read-only Kubernetes collector for the deployment assessment agent.

Authenticates with an Azure AD token (works with the collector managed identity
in production or `az login` locally), reads declared workload state from AKS, and
proves the grant is read-only. No kubelogin required because the target cluster
has Azure RBAC for Kubernetes enabled.
"""

from __future__ import annotations

import base64
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

import yaml
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerservice import ContainerServiceClient
from kubernetes import client as k8s_client

# Well-known AKS AAD server application ID; token audience for the Kube API.
AKS_AAD_SERVER_SCOPE = "6dae42f8-4368-4678-94ff-3960e28e3630/.default"


@dataclass
class WorkloadFacts:
    """Normalized declared state the assessment checks consume."""

    namespace: str
    deployments: list[dict[str, Any]] = field(default_factory=list)
    hpas: list[dict[str, Any]] = field(default_factory=list)
    pdbs: list[dict[str, Any]] = field(default_factory=list)


def _credential() -> DefaultAzureCredential:
    # AZURE_CLIENT_ID pins DefaultAzureCredential to a specific user-assigned
    # managed identity when several are attached to the host.
    return DefaultAzureCredential()


def get_cluster_info(subscription_id: str, resource_group: str, cluster_name: str) -> dict[str, Any]:
    """Control-plane read: version, node pools, network. Proves ARM Reader access."""
    cred = _credential()
    cs = ContainerServiceClient(cred, subscription_id)
    cluster = cs.managed_clusters.get(resource_group, cluster_name)
    return {
        "name": cluster.name,
        "kubernetes_version": cluster.kubernetes_version,
        "power_state": getattr(cluster.power_state, "code", None),
        "node_pools": [
            {
                "name": p.name,
                "vm_size": p.vm_size,
                "count": p.count,
                "min_count": p.min_count,
                "max_count": p.max_count,
                "mode": p.mode,
            }
            for p in (cluster.agent_pool_profiles or [])
        ],
        "azure_rbac_enabled": bool(
            getattr(getattr(cluster, "aad_profile", None), "enable_azure_rbac", False)
        ),
    }


def _kube_api(subscription_id: str, resource_group: str, cluster_name: str) -> k8s_client.ApiClient:
    """Build a Kube API client from the user kubeconfig + an AAD bearer token."""
    cred = _credential()
    cs = ContainerServiceClient(cred, subscription_id)
    creds = cs.managed_clusters.list_cluster_user_credentials(resource_group, cluster_name)
    # The SDK returns the kubeconfig as raw bytes (already decoded), not base64.
    kubeconfig = yaml.safe_load(creds.kubeconfigs[0].value)

    cluster_cfg = kubeconfig["clusters"][0]["cluster"]
    ca_data = base64.b64decode(cluster_cfg["certificate-authority-data"])
    ca_file = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
    ca_file.write(ca_data)
    ca_file.close()

    token = cred.get_token(AKS_AAD_SERVER_SCOPE).token

    cfg = k8s_client.Configuration()
    cfg.host = cluster_cfg["server"]
    cfg.ssl_ca_cert = ca_file.name
    cfg.api_key = {"authorization": f"Bearer {token}"}
    return k8s_client.ApiClient(cfg)


def collect_workloads(
    subscription_id: str, resource_group: str, cluster_name: str, namespace: str
) -> WorkloadFacts:
    """Data-plane read: Deployments, HPAs, PDBs in a namespace."""
    api = _kube_api(subscription_id, resource_group, cluster_name)
    apps = k8s_client.AppsV1Api(api)
    autoscaling = k8s_client.AutoscalingV2Api(api)
    policy = k8s_client.PolicyV1Api(api)

    facts = WorkloadFacts(namespace=namespace)

    for d in apps.list_namespaced_deployment(namespace).items:
        containers = d.spec.template.spec.containers or []
        facts.deployments.append(
            {
                "name": d.metadata.name,
                "replicas": d.spec.replicas,
                "containers": [
                    {
                        "name": c.name,
                        "requests": (c.resources.requests if c.resources else None),
                        "limits": (c.resources.limits if c.resources else None),
                        "has_readiness_probe": c.readiness_probe is not None,
                        "has_liveness_probe": c.liveness_probe is not None,
                    }
                    for c in containers
                ],
            }
        )

    for h in autoscaling.list_namespaced_horizontal_pod_autoscaler(namespace).items:
        facts.hpas.append(
            {
                "name": h.metadata.name,
                "min_replicas": h.spec.min_replicas,
                "max_replicas": h.spec.max_replicas,
                "target": h.spec.scale_target_ref.name,
            }
        )

    for p in policy.list_namespaced_pod_disruption_budget(namespace).items:
        facts.pdbs.append(
            {
                "name": p.metadata.name,
                "min_available": str(p.spec.min_available) if p.spec.min_available is not None else None,
                "max_unavailable": str(p.spec.max_unavailable) if p.spec.max_unavailable is not None else None,
            }
        )

    return facts


def verify_read_only(
    subscription_id: str, resource_group: str, cluster_name: str, namespace: str
) -> bool:
    """Confirm a write is denied, proving the grant is read-only."""
    from kubernetes.client.rest import ApiException

    api = _kube_api(subscription_id, resource_group, cluster_name)
    core = k8s_client.CoreV1Api(api)
    body = k8s_client.V1ConfigMap(
        metadata=k8s_client.V1ObjectMeta(name="assessment-agent-write-probe"),
        data={"probe": "should-be-denied"},
    )
    try:
        core.create_namespaced_config_map(namespace, body)
        # If this succeeds the identity has write access — that's a failure here.
        core.delete_namespaced_config_map("assessment-agent-write-probe", namespace)
        return False
    except ApiException as exc:
        return exc.status in (401, 403)


def main() -> None:
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID", "a0aabca8-6bd7-45f3-9b88-c425f646d07b")
    rg = os.environ.get("TARGET_RG", "deploy-assess-rg")
    cluster = os.environ.get("TARGET_CLUSTER", "deploy-assess-aks")
    namespace = os.environ.get("TARGET_NAMESPACE", "kube-system")

    print(f"== Control plane (ARM) read: {cluster} ==")
    info = get_cluster_info(sub, rg, cluster)
    print(f"  version={info['kubernetes_version']} azure_rbac={info['azure_rbac_enabled']}")
    for pool in info["node_pools"]:
        print(f"  pool {pool['name']}: {pool['vm_size']} count={pool['count']} mode={pool['mode']}")

    print(f"\n== Data plane read: namespace/{namespace} ==")
    facts = collect_workloads(sub, rg, cluster, namespace)
    print(f"  deployments={len(facts.deployments)} hpas={len(facts.hpas)} pdbs={len(facts.pdbs)}")
    for d in facts.deployments[:5]:
        print(f"    deploy {d['name']} replicas={d['replicas']} containers={len(d['containers'])}")

    print("\n== Read-only guardrail (write must be denied) ==")
    denied = verify_read_only(sub, rg, cluster, namespace)
    print(f"  write denied: {denied}")


if __name__ == "__main__":
    main()
