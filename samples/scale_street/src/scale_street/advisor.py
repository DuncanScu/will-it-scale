"""Financial advisor implementations."""

import asyncio
from typing import Protocol

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential

from scale_street.config import Settings
from scale_street.models import MarketSnapshot, Portfolio


class AdvisorThrottledError(RuntimeError):
    """Raised when the simulated Foundry quota is exceeded."""


class FinancialAdvisor(Protocol):
    """Interface implemented by financial advisor providers."""

    async def advise(
        self,
        portfolio: Portfolio,
        market: MarketSnapshot,
        concern: str,
    ) -> str:
        """Return a short paper-portfolio recommendation."""


class SimulatedFinancialAdvisor:
    """Deterministic substitute for Foundry during local and load tests."""

    def __init__(self, latency_ms: int, concurrency_limit: int) -> None:
        self._latency_seconds = latency_ms / 1_000
        self._concurrency_limit = concurrency_limit
        self._active_requests = 0
        self._lock = asyncio.Lock()

    async def advise(
        self,
        portfolio: Portfolio,
        market: MarketSnapshot,
        concern: str,
    ) -> str:
        """Simulate model latency and quota throttling."""

        async with self._lock:
            self._active_requests += 1
            active_requests = self._active_requests

        try:
            await asyncio.sleep(
                self._latency_seconds + (market.volatility * 0.08)
            )
            if active_requests > self._concurrency_limit:
                raise AdvisorThrottledError(
                    "The simulated Foundry deployment returned HTTP 429."
                )

            largest_holding = max(
                portfolio.holdings,
                key=lambda holding: holding.allocation,
            )
            return (
                f"Hedgehog reviewed {portfolio.customer_name}'s "
                f"{portfolio.risk_profile.value} portfolio. Reduce concentration "
                f"in {largest_holding.symbol}, preserve liquidity, and reassess "
                f"after the {market.mood.lower()} opening period. Concern reviewed: "
                f"{concern}"
            )
        finally:
            async with self._lock:
                self._active_requests -= 1


class FoundryFinancialAdvisor:
    """Financial advisor backed by Microsoft Agent Framework and Foundry."""

    def __init__(self, project_endpoint: str, model: str) -> None:
        self._credential = DefaultAzureCredential()
        self._client = FoundryChatClient(
            project_endpoint=project_endpoint,
            model=model,
            credential=self._credential,
        )

    async def advise(
        self,
        portfolio: Portfolio,
        market: MarketSnapshot,
        concern: str,
    ) -> str:
        """Run a code-defined Microsoft Agent Framework financial agent."""

        agent = Agent(
            client=self._client,
            name="Hedgehog",
            description="A cautious paper-portfolio analyst for Scale Street.",
            instructions=(
                "You are Hedgehog, a playful but cautious financial-services "
                "demonstration agent. Analyze only the supplied synthetic paper "
                "portfolio. Give a concise recommendation in at most 80 words. "
                "Do not claim to provide real financial advice."
            ),
        )
        prompt = (
            f"Portfolio: {portfolio.model_dump_json()}\n"
            f"Market: {market.model_dump_json()}\n"
            f"Engineer concern: {concern}"
        )
        result = await agent.run(prompt)
        return result.text


def create_financial_advisor(settings: Settings) -> FinancialAdvisor:
    """Create the configured financial advisor."""

    if settings.agent_mode == "foundry":
        if not settings.foundry_project_endpoint:
            message = (
                "FOUNDRY_PROJECT_ENDPOINT is required when "
                "SCALE_STREET_AGENT_MODE=foundry."
            )
            raise ValueError(message)
        return FoundryFinancialAdvisor(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model,
        )

    return SimulatedFinancialAdvisor(
        latency_ms=settings.simulated_agent_latency_ms,
        concurrency_limit=settings.simulated_agent_concurrency_limit,
    )
