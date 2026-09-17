from pathlib import Path

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential


def read_application_source_file(source_root: Path, relative_path: str) -> str:
    source_root = source_root.resolve()
    source_path = (source_root / relative_path).resolve()
    try:
        source_path.relative_to(source_root)
    except ValueError as error:
        raise ValueError("The requested file must be inside the application source directory") from error

    if source_path.suffix != ".py" or not source_path.is_file():
        raise ValueError("The requested file must be an existing Python source file")
    if source_path.stat().st_size > 100_000:
        raise ValueError("The requested file exceeds the 100 KB read limit")

    return source_path.read_text(encoding="utf-8")


def create_application_performance_investigator_agent(source_root: Path) -> Agent:
    @tool
    def read_source_file(relative_path: str) -> str:
        """Read a Python source file relative to the configured application source directory."""
        return read_application_source_file(source_root, relative_path)

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
            "creation, blocking request paths, unbounded work or concurrency, retries, cache "
            "problems, and resource leaks. Cite the relevant source function or code pattern "
            "for every finding, assign a confidence level, explain the scaling impact, and "
            "recommend the next validation. Distinguish facts from assumptions and unknowns. "
            "Use the read_source_file tool to inspect only the files needed for the investigation. "
            "Return findings for the Investigation Architect, not a user-facing final report."
        ),
        tools=[read_source_file],
    )