from collections.abc import Callable
from pathlib import Path

from agent_framework import Agent, MCPStdioTool, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from will_it_scale.tools.application_source import read_source_file
from will_it_scale.tools.azure_mcp import create_azure_mcp_tool

PROJECT_FILE_SUFFIXES = frozenset(
    {
        ".bicep",
        ".bicepparam",
        ".dockerfile",
        ".hcl",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".tf",
        ".tfvars",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
        "",
    }
)


class AzureScaleInvestigator:
    """Native Azure investigator with a scoped local reader and Azure MCP tools."""

    def __init__(self, agent: Agent, mcp_tool: MCPStdioTool) -> None:
        self._agent = agent
        self._mcp_tool = mcp_tool

    async def run(self, prompt: str):
        async with self._mcp_tool:
            return await self._agent.run(prompt)


def create_azure_scale_investigator_agent(
    project_root: Path,
    on_file_read: Callable[[str], None] | None = None,
) -> AzureScaleInvestigator:
    """Create the read-only Azure scale investigator for a project."""

    @tool
    def read_project_file(relative_path: str) -> str:
        """Read a non-secret project file relative to the current project."""
        path = Path(relative_path)
        lowered_name = path.name.lower()
        if path.name.startswith(".") or any(
            marker in lowered_name
            for marker in ("secret", "credential", "password", "token", ".env")
        ):
            raise ValueError("Secret and hidden files are not available to this agent")
        content = read_source_file(project_root, relative_path, PROJECT_FILE_SUFFIXES)
        if on_file_read is not None:
            on_file_read(relative_path)
        return content

    azure_mcp = create_azure_mcp_tool()
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="gpt-4.1-mini",
            credential=DefaultAzureCredential(),
        ),
        name="AzureScaleInvestigator",
        instructions=(
            "You are the Azure Scale Investigator for a scalability assessment. "
            "Work read-only and return concise, evidence-backed findings for the "
            "Investigation Architect, not a user-facing report. Begin with local "
            "project evidence before reasoning about Azure. Inspect relevant Bicep, "
            "ARM, Terraform, Kubernetes, deployment, Docker, architecture, and "
            "telemetry files through read_project_file. Never read secrets, hidden "
            "files, credentials, connection strings, or tokens. Create an expected-"
            "resource view and identify Azure scope, resource groups, managed "
            "identities, compute, model endpoints, data stores, messaging, networking, "
            "registries, and monitoring. Evaluate capacity, elasticity, resilience, "
            "state, concurrency, quotas, dependencies, and observability. Pay special "
            "attention to AKS node and pod capacity, replicas, HPA and PDB settings, "
            "synchronous Foundry dependencies, model quotas, and whether application "
            "scale-out increases downstream pressure. Flag missing live Azure properties "
            "or telemetry as Unknown rather than assuming health. Label every finding "
            "Configured, Observed, Inferred, or Unknown, cite the file and relevant "
            "field, explain scale impact, and recommend the next validation. Do not "
            "execute commands or mutate files or Azure resources. Use the Azure MCP "
            "tools only for discovered scopes and resources. Issue Azure MCP calls "
            "serially, never in parallel, and do not repeat failed calls in a loop. "
            "Use metric definitions to correct unsupported metric requests, label "
            "live Azure evidence Observed, and record unavailable evidence as Unknown."
        ),
        tools=[read_project_file, azure_mcp],
    )
    return AzureScaleInvestigator(agent, azure_mcp)
