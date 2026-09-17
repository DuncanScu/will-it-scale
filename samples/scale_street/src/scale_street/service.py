"""Application service and runtime statistics."""

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from scale_street.advisor import AdvisorThrottledError, FinancialAdvisor
from scale_street.analysis import (
    ANALYSIS_STAGES,
    RUMOR_CATALOG,
    PortfolioAnalysisEngine,
    RumorGenerator,
)
from scale_street.config import Settings
from scale_street.market import MarketSimulator
from scale_street.models import (
    AdviceResponse,
    AnalysisState,
    PortfolioAnalysis,
    PortfolioAnalysisRequest,
    Rumor,
    ServiceStats,
)


class ScaleStreetService:
    """Coordinate market activity, advice, and demo telemetry."""

    def __init__(
        self,
        settings: Settings,
        market: MarketSimulator,
        advisor: FinancialAdvisor,
    ) -> None:
        self._settings = settings
        self._market = market
        self._advisor = advisor
        self._analysis_engine = PortfolioAnalysisEngine()
        self._rumor_generator = RumorGenerator()
        self._latencies: deque[float] = deque(maxlen=2_000)
        self._recommendations: list[AdviceResponse] = []
        self._rumors: deque[Rumor] = deque(
            (
                rumor.model_copy(deep=True)
                for rumor in RUMOR_CATALOG[:3]
            ),
            maxlen=12,
        )
        self._rumor_catalog_cursor = 3
        self._rumor_subscribers: set[asyncio.Queue[dict[str, object]]] = set()
        self._rumor_task: asyncio.Task[None] | None = None
        self._analyses: dict[str, PortfolioAnalysis] = {}
        self._analysis_order: deque[str] = deque()
        self._analysis_history_limit = 50
        self._analysis_tasks: dict[str, asyncio.Task[None]] = {}
        self._requests_total = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._throttled_requests = 0
        self._active_requests = 0
        self._burst_task: asyncio.Task[None] | None = None
        self._stats_lock = asyncio.Lock()

    @property
    def market(self) -> MarketSimulator:
        """Expose the synthetic market."""

        return self._market

    async def start(self) -> None:
        """Start lifecycle-managed background services."""

        if self._rumor_task and not self._rumor_task.done():
            return
        self._rumor_task = asyncio.create_task(
            self._run_rumor_feed(),
            name="scale-street-rumor-feed",
        )

    async def shutdown(self) -> None:
        """Stop background services and clear runtime state."""

        if self._rumor_task and not self._rumor_task.done():
            self._rumor_task.cancel()
            try:
                await self._rumor_task
            except asyncio.CancelledError:
                pass
        self._rumor_task = None
        await self.reset()

    async def rumors(self) -> list[Rumor]:
        """Return the current live rumor feed, newest first."""

        async with self._stats_lock:
            return [rumor.model_copy(deep=True) for rumor in self._rumors]

    async def rumor_events(self) -> AsyncIterator[dict[str, object]]:
        """Yield live rumor events for one browser session."""

        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=12)
        self._rumor_subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._rumor_subscribers.discard(queue)

    async def _run_rumor_feed(self) -> None:
        """Publish new signals and verification updates on a timer."""

        while True:
            await asyncio.sleep(self._settings.rumor_update_interval_seconds)
            event = await self._next_rumor_event()
            for subscriber in tuple(self._rumor_subscribers):
                if subscriber.full():
                    subscriber.get_nowait()
                subscriber.put_nowait(event)

    async def _next_rumor_event(self) -> dict[str, object]:
        async with self._stats_lock:
            if self._rumor_catalog_cursor < len(RUMOR_CATALOG):
                rumor = RUMOR_CATALOG[self._rumor_catalog_cursor].model_copy(
                    update={"updated_at": datetime.now(UTC)},
                    deep=True,
                )
                self._rumor_catalog_cursor += 1
                self._rumors.appendleft(rumor)
                kind = "created"
            else:
                developing_index = next(
                    (
                        index
                        for index, candidate in enumerate(self._rumors)
                        if candidate.status.value == "developing"
                    ),
                    None,
                )
                if developing_index is None:
                    rumor = self._rumor_generator.next_rumor()
                    self._rumors.appendleft(rumor)
                    kind = "created"
                else:
                    rumor = self._rumor_generator.verify(
                        self._rumors[developing_index]
                    )
                    self._rumors[developing_index] = rumor
                    kind = "updated"
            return {
                "kind": kind,
                "rumor": rumor.model_dump(mode="json"),
            }

    async def request_advice(
        self,
        customer_id: str,
        concern: str,
    ) -> AdviceResponse:
        """Request and record paper-portfolio advice."""

        started = perf_counter()
        async with self._stats_lock:
            self._requests_total += 1
            self._active_requests += 1

        try:
            portfolio = self._market.portfolio(customer_id)
            recommendation = await self._advisor.advise(
                portfolio=portfolio,
                market=self._market.snapshot(),
                concern=concern,
            )
            latency_ms = (perf_counter() - started) * 1_000
            response = AdviceResponse(
                customer_id=customer_id,
                agent_name="Hedgehog",
                recommendation=recommendation,
                latency_ms=round(latency_ms, 2),
            )
            async with self._stats_lock:
                self._successful_requests += 1
                self._latencies.append(latency_ms)
                self._store_recommendation(response)
            return response
        except AdvisorThrottledError:
            async with self._stats_lock:
                self._failed_requests += 1
                self._throttled_requests += 1
            raise
        except Exception:
            async with self._stats_lock:
                self._failed_requests += 1
            raise
        finally:
            async with self._stats_lock:
                self._active_requests -= 1

    def _store_recommendation(self, response: AdviceResponse) -> None:
        """Store recommendation history according to the selected profile."""

        self._recommendations.append(response)
        if self._settings.scale_profile == "improved":
            excess = (
                len(self._recommendations)
                - self._settings.recommendation_history_limit
            )
            if excess > 0:
                del self._recommendations[:excess]

    def start_market_burst(self, customers: int, concurrency: int) -> bool:
        """Start a background opening-bell load burst."""

        if self._burst_task and not self._burst_task.done():
            return False
        self._market.open_market()
        self._burst_task = asyncio.create_task(
            self._run_market_burst(customers, concurrency),
            name="scale-street-opening-bell",
        )
        return True

    async def start_analysis(
        self,
        request: PortfolioAnalysisRequest,
    ) -> PortfolioAnalysis:
        """Create a portfolio analysis and start its background workflow."""

        analysis_id = str(uuid4())
        analysis = PortfolioAnalysis(
            id=analysis_id,
            portfolio=request.portfolio,
            rumor=request.rumor,
            stages=[stage.model_copy(deep=True) for stage in ANALYSIS_STAGES],
        )
        async with self._stats_lock:
            self._analyses[analysis_id] = analysis
            self._analysis_order.appendleft(analysis_id)
        self._analysis_tasks[analysis_id] = asyncio.create_task(
            self._run_analysis(analysis_id),
            name=f"scale-street-analysis-{analysis_id}",
        )
        return analysis.model_copy(deep=True)

    async def analysis(self, analysis_id: str) -> PortfolioAnalysis | None:
        """Return one portfolio analysis."""

        async with self._stats_lock:
            analysis = self._analyses.get(analysis_id)
            return analysis.model_copy(deep=True) if analysis else None

    async def analyses(self) -> list[PortfolioAnalysis]:
        """Return recent portfolio analyses, newest first."""

        async with self._stats_lock:
            return [
                self._analyses[analysis_id].model_copy(deep=True)
                for analysis_id in self._analysis_order
                if analysis_id in self._analyses
            ]

    async def _run_analysis(self, analysis_id: str) -> None:
        """Run specialist analysis stages and assemble the final report."""

        try:
            async with self._stats_lock:
                analysis = self._analyses[analysis_id]
                analysis.status = AnalysisState.RUNNING
                portfolio = analysis.portfolio.model_copy(deep=True)
                rumor = analysis.rumor.model_copy(deep=True)

            await self._complete_analysis_stage(
                analysis_id,
                "signal",
                self._analysis_engine.signal_summary(rumor),
            )
            await self._complete_analysis_stage(
                analysis_id,
                "credibility",
                self._analysis_engine.credibility_summary(rumor),
            )
            await self._complete_analysis_stage(
                analysis_id,
                "exposure",
                self._analysis_engine.exposure_summary(portfolio, rumor),
            )
            await self._complete_analysis_stage(
                analysis_id,
                "scenarios",
                self._analysis_engine.scenario_summary(rumor),
            )
            await self._complete_analysis_stage(
                analysis_id,
                "risk",
                self._analysis_engine.risk_summary(portfolio, rumor),
            )
            await self._set_stage_status(
                analysis_id,
                "advisor",
                AnalysisState.RUNNING,
            )
            recommendation = await self._advisor.advise(
                portfolio=portfolio,
                market=self._market.snapshot(),
                concern=(
                    "Assess this fictional market signal without treating it as "
                    f"verified fact: {rumor.headline}. {rumor.details}"
                ),
            )
            report = self._analysis_engine.build_report(
                portfolio=portfolio,
                rumor=rumor,
                recommendation=recommendation,
            )
            async with self._stats_lock:
                analysis = self._analyses[analysis_id]
                advisor_stage = self._stage(analysis, "advisor")
                advisor_stage.summary = (
                    "Combined the specialist findings into a portfolio recommendation."
                )
                advisor_stage.status = AnalysisState.COMPLETED
                analysis.report = report
                analysis.status = AnalysisState.COMPLETED
                analysis.completed_at = datetime.now(UTC)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            async with self._stats_lock:
                analysis = self._analyses[analysis_id]
                analysis.status = AnalysisState.FAILED
                analysis.error = str(error)
                for stage in analysis.stages:
                    if stage.status == AnalysisState.RUNNING:
                        stage.status = AnalysisState.FAILED
                        break
        finally:
            async with self._stats_lock:
                self._analysis_tasks.pop(analysis_id, None)
                self._evict_completed_analyses()

    def _evict_completed_analyses(self) -> None:
        """Remove completed analyses beyond the bounded history limit."""

        while len(self._analysis_order) > self._analysis_history_limit:
            oldest_id = self._analysis_order[-1]
            if oldest_id in self._analysis_tasks:
                return
            self._analysis_order.pop()
            self._analyses.pop(oldest_id, None)

    async def _complete_analysis_stage(
        self,
        analysis_id: str,
        stage_key: str,
        summary: str,
    ) -> None:
        """Run one visible background stage."""

        await self._set_stage_status(
            analysis_id,
            stage_key,
            AnalysisState.RUNNING,
        )
        await asyncio.sleep(self._settings.analysis_stage_latency_ms / 1_000)
        async with self._stats_lock:
            stage = self._stage(self._analyses[analysis_id], stage_key)
            stage.summary = summary
            stage.status = AnalysisState.COMPLETED

    async def _set_stage_status(
        self,
        analysis_id: str,
        stage_key: str,
        state: AnalysisState,
    ) -> None:
        async with self._stats_lock:
            self._stage(self._analyses[analysis_id], stage_key).status = state

    @staticmethod
    def _stage(
        analysis: PortfolioAnalysis,
        stage_key: str,
    ):
        return next(stage for stage in analysis.stages if stage.key == stage_key)

    async def _run_market_burst(self, customers: int, concurrency: int) -> None:
        semaphore = asyncio.Semaphore(concurrency)

        async def request(customer_number: int) -> None:
            async with semaphore:
                try:
                    await self.request_advice(
                        customer_id=f"CUST-{customer_number:05d}",
                        concern="Will advice complete during the opening bell?",
                    )
                except Exception:
                    return

        await asyncio.gather(
            *(request(customer_number) for customer_number in range(customers))
        )

    async def reset(self) -> None:
        """Reset the simulation and counters."""

        if self._burst_task and not self._burst_task.done():
            self._burst_task.cancel()
            try:
                await self._burst_task
            except asyncio.CancelledError:
                pass
        self._burst_task = None
        analysis_tasks = list(self._analysis_tasks.values())
        for task in analysis_tasks:
            task.cancel()
        if analysis_tasks:
            await asyncio.gather(*analysis_tasks, return_exceptions=True)
        self._analysis_tasks.clear()
        self._market.reset()
        async with self._stats_lock:
            self._latencies.clear()
            self._recommendations.clear()
            self._requests_total = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._throttled_requests = 0
            self._active_requests = 0
            self._analyses.clear()
            self._analysis_order.clear()

    async def stats(self) -> ServiceStats:
        """Return current service statistics."""

        async with self._stats_lock:
            latencies = sorted(self._latencies)
            snapshot = self._market.snapshot()
            return ServiceStats(
                market_status=snapshot.status,
                market_mood=snapshot.mood,
                requests_total=self._requests_total,
                successful_requests=self._successful_requests,
                failed_requests=self._failed_requests,
                active_requests=self._active_requests,
                throttled_requests=self._throttled_requests,
                p50_latency_ms=self._percentile(latencies, 0.50),
                p95_latency_ms=self._percentile(latencies, 0.95),
                recommendations_in_memory=len(self._recommendations),
                burst_running=bool(
                    self._burst_task and not self._burst_task.done()
                ),
            )

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0
        index = min(round((len(values) - 1) * percentile), len(values) - 1)
        return round(values[index], 2)
