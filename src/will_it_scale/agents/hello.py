from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential


def create_hello_agent() -> Agent:
    return Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="claude-sonnet-4-6",
            credential=DefaultAzureCredential(),
        ),
        name="HelloAgent",
        instructions="You are a friendly assistant. Keep your answers brief.",
    )