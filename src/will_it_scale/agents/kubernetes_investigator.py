from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential


def create_kubernetes_investigator_agent() -> Agent:
    return Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="gpt-4.1-mini",
            credential=DefaultAzureCredential(),
        ),
        name="KubernetesInvestigator",
        instructions=(
            "You are the Kubernetes Investigator for a scalability assessment. Analyze the "
            "Kubernetes manifests provided to you and report evidence-backed findings. Check "
            "replicas, HPA bounds and metrics, CPU and memory requests and limits, scheduling "
            "constraints, readiness and liveness probes, rollout settings, pod disruption "
            "budgets, service routing, and dependency capacity implications. Distinguish facts "
            "from assumptions and unknowns. Cite the manifest and relevant field for every "
            "finding, assign a confidence level, explain the scaling or availability impact, "
            "and recommend the next validation. Return findings for the Investigation Architect, "
            "not a user-facing final report."
        ),
    )