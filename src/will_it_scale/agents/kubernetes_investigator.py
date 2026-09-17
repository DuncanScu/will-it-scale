from collections.abc import Callable
from pathlib import Path

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from will_it_scale.tools.application_source import read_source_file


def create_kubernetes_investigator_agent(
    manifest_root: Path,
    on_file_read: Callable[[str], None] | None = None,
) -> Agent:
    @tool
    def read_manifest_file(relative_path: str) -> str:
        """Read a Kubernetes YAML manifest relative to the configured manifest directory."""
        content = read_source_file(
            manifest_root, relative_path, frozenset({".yaml", ".yml"})
        )
        if on_file_read is not None:
            on_file_read(relative_path)
        return content

    return Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="gpt-4.1-mini",
            credential=DefaultAzureCredential(),
        ),
        name="KubernetesInvestigator",
        instructions=(
            "You are the Kubernetes Investigator for a scalability assessment. Analyze the "
            "Kubernetes manifests available through the read_manifest_file tool and report "
            "evidence-backed findings. Check "
            "replicas, HPA bounds and metrics, CPU and memory requests and limits, scheduling "
            "constraints, readiness and liveness probes, rollout settings, pod disruption "
            "budgets, service routing, and dependency capacity implications. Distinguish facts "
            "from assumptions and unknowns. Cite the manifest and relevant field for every "
            "finding, assign a confidence level, explain the scaling or availability impact, "
            "and recommend the next validation. Return findings for the Investigation Architect, "
            "not a user-facing final report. Use the tool to inspect only the manifests needed."
        ),
        tools=[read_manifest_file],
    )