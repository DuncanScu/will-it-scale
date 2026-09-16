import asyncio

from will_it_scale.agents.hello import create_hello_agent


def main() -> None:
    asyncio.run(run_agent())


async def run_agent() -> None:
    agent = create_hello_agent()

    result = await agent.run("What is the largest city in France?")
    print(f"Agent: {result}")


if __name__ == "__main__":
    main()