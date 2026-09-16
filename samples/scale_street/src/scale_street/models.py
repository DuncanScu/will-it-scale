"""Domain and API models for Scale Street."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class RiskProfile(StrEnum):
    """Supported investor risk profiles."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    GROWTH = "growth"


class Holding(BaseModel):
    """A paper portfolio holding."""

    symbol: str
    allocation: float = Field(ge=0, le=1)


class Portfolio(BaseModel):
    """A simulated customer portfolio."""

    customer_id: str
    customer_name: str
    risk_profile: RiskProfile
    holdings: list[Holding]


class MarketSnapshot(BaseModel):
    """Current synthetic market conditions."""

    status: str
    mood: str
    volatility: float = Field(ge=0)
    event: str
    updated_at: datetime


class AdviceRequest(BaseModel):
    """Request for portfolio advice."""

    concern: str = "Can this portfolio withstand the opening bell?"


class AdviceResponse(BaseModel):
    """Financial-agent advice response."""

    customer_id: str
    agent_name: str
    recommendation: str
    latency_ms: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MarketOpenRequest(BaseModel):
    """Configuration for a synthetic opening-bell burst."""

    customers: int = Field(default=120, ge=1, le=2_000)
    concurrency: int = Field(default=24, ge=1, le=200)


class MarketOpenResponse(BaseModel):
    """Accepted opening-bell simulation."""

    status: str
    customers: int
    concurrency: int


class ServiceStats(BaseModel):
    """Current runtime statistics for the dashboard."""

    market_status: str
    market_mood: str
    requests_total: int
    successful_requests: int
    failed_requests: int
    active_requests: int
    throttled_requests: int
    p50_latency_ms: float
    p95_latency_ms: float
    recommendations_in_memory: int
    burst_running: bool


class RumorSeverity(StrEnum):
    """Relative potential impact of a market rumor."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RumorStatus(StrEnum):
    """Current verification state of a fictional rumor."""

    DEVELOPING = "developing"
    CONFIRMED = "confirmed"
    DENIED = "denied"


class Rumor(BaseModel):
    """A fictional market signal submitted for analysis."""

    id: str
    headline: str = Field(min_length=3, max_length=240)
    details: str = Field(default="", max_length=1_000)
    source: str = Field(default="Rumor Mill", max_length=80)
    severity: RumorSeverity = RumorSeverity.MEDIUM
    time_horizon: str = Field(default="Next 30 days", max_length=80)
    status: RumorStatus = RumorStatus.DEVELOPING
    sentiment: Literal["positive", "negative", "mixed"] = "mixed"
    affected_symbols: list[str] = Field(default_factory=list, max_length=12)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnalysisState(StrEnum):
    """Lifecycle state shared by analysis jobs and stages."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStage(BaseModel):
    """Progress and output from one analysis specialist."""

    key: str
    specialist: str
    title: str
    status: AnalysisState = AnalysisState.QUEUED
    summary: str | None = None


class HoldingImpact(BaseModel):
    """Estimated impact of a rumor on one portfolio holding."""

    symbol: str
    allocation: float
    direction: Literal["upside", "downside", "volatile", "limited"]
    impact_score: int = Field(ge=0, le=100)
    rationale: str


class ScenarioProjection(BaseModel):
    """One possible outcome for the submitted market signal."""

    name: Literal["Bull", "Base", "Bear"]
    portfolio_effect: str
    probability: int = Field(ge=0, le=100)
    narrative: str


class AnalysisReport(BaseModel):
    """Completed portfolio impact report."""

    executive_summary: str
    confidence: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    diversification_score: int = Field(ge=0, le=100)
    affected_allocation: float = Field(ge=0, le=1)
    holding_impacts: list[HoldingImpact]
    scenarios: list[ScenarioProjection]
    recommendation: str


class PortfolioAnalysisRequest(BaseModel):
    """Request to investigate a rumor against a paper portfolio."""

    portfolio: Portfolio
    rumor: Rumor


class PortfolioAnalysis(BaseModel):
    """A progressively assembled portfolio analysis."""

    id: str
    status: AnalysisState = AnalysisState.QUEUED
    portfolio: Portfolio
    rumor: Rumor
    stages: list[AnalysisStage]
    report: AnalysisReport | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
