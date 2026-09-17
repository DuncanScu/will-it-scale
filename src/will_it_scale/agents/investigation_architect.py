from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from will_it_scale.config import FOUNDRY_MODEL, FOUNDRY_PROJECT_ENDPOINT


def create_investigation_architect_agent() -> Agent:
    return Agent(
        client=FoundryChatClient(
            project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
            model=FOUNDRY_MODEL,
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