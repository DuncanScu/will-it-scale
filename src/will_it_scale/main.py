import asyncio

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential


def main() -> None:
    asyncio.run(run_agent())


async def run_agent() -> None:
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint="https://will-it-scale-hack-resource.services.ai.azure.com/api/projects/will-it-scale-hack",
            model="claude-sonnet-4-6",
            credential=DefaultAzureCredential(),
        ),
        name="HelloAgent",
        instructions="You are a friendly assistant. Keep your answers brief.",
    )

    result = await agent.run("What is the largest city in France?")
    print(f"Agent: {result}")
