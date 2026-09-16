from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential


def create_investigation_architect_agent() -> Agent:
    return Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="claude-sonnet-4-6",
            credential=DefaultAzureCredential(),
        ),
        name="InvestigationArchitect",
        instructions=(
            "You are the Investigation Architect. Help teams assess whether an application "
            "can support its target workload. Ask focused questions, reason from evidence, "
            "identify scaling risks, and clearly distinguish facts, assumptions, and unknowns. "
            "Keep your answers concise and explain your confidence."
        ),
    )