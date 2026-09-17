from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential


def create_application_performance_investigator_agent() -> Agent:
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
            "Return findings for the Investigation Architect, not a user-facing final report."
        ),
    )