from collections.abc import Callable
from pathlib import Path

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from will_it_scale.tools.application_source import read_application_source_file


def create_application_performance_investigator_agent(
    source_root: Path,
    on_file_read: Callable[[str], None] | None = None,
) -> Agent:
    @tool
    def read_source_file(relative_path: str) -> str:
        """Read a Python source file relative to the configured application source directory."""
        content = read_application_source_file(source_root, relative_path)
        if on_file_read is not None:
            on_file_read(relative_path)
        return content

    return Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="gpt-4.1-mini",
            credential=DefaultAzureCredential(),
        ),
        name="ApplicationPerformanceInvestigator",
        instructions=(
            "You are the Application Performance Investigator for a scalability assessment. "
            "Analyze the application source supplied to you and report evidence-backed findings "
            "for the Investigation Architect. Identify inefficient algorithmic complexity, N+1 "
            "database or downstream calls, connection-pool misuse, per-request connection "
            "creation, blocking request paths, unbounded work or concurrency, missing "
            "timeouts or retries, queue and back-pressure gaps, process-local state, cache "
            "problems, background-task behavior, telemetry gaps, and resource leaks. Cite the relevant source function or code pattern "
            "for every finding, assign a confidence level, explain the scaling impact, and "
            "recommend the next validation. Distinguish facts from assumptions and unknowns. "
            "Use the read_source_file tool to inspect only the files needed for the investigation. "
            "Return findings for the Investigation Architect, not a user-facing final report."
        ),
        tools=[read_source_file],
    )