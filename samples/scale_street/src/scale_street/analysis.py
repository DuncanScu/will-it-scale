"""Deterministic portfolio analysis for the Rumor Mill workflow."""

from datetime import UTC, datetime
from random import Random

from scale_street.models import (
    AnalysisReport,
    AnalysisStage,
    HoldingImpact,
    Portfolio,
    Rumor,
    RumorSeverity,
    RumorStatus,
    ScenarioProjection,
)

ANALYSIS_STAGES = (
    AnalysisStage(
        key="signal",
        specialist="Signal Scout",
        title="Decode the market signal",
    ),
    AnalysisStage(
        key="credibility",
        specialist="Credibility Desk",
        title="Assess uncertainty",
    ),
    AnalysisStage(
        key="exposure",
        specialist="Exposure Mapper",
        title="Map portfolio exposure",
    ),
    AnalysisStage(
        key="scenarios",
        specialist="Scenario Engine",
        title="Model possible outcomes",
    ),
    AnalysisStage(
        key="risk",
        specialist="Risk Analyst",
        title="Evaluate portfolio risk",
    ),
    AnalysisStage(
        key="advisor",
        specialist="Hedgehog Advisor",
        title="Prepare the recommendation",
    ),
)

RUMOR_CATALOG = (
    Rumor(
        id="contoso-acquisition",
        headline="Contoso may announce a major acquisition",
        details=(
            "Trading desks are discussing an acquisition that could expand "
            "Contoso into enterprise logistics."
        ),
        source="Market Chatter",
        severity=RumorSeverity.HIGH,
        time_horizon="Next 30 days",
        sentiment="positive",
        affected_symbols=["CONTOSO", "NORTHWIND"],
    ),
    Rumor(
        id="northwind-contract",
        headline="Northwind reportedly lost a key shipping contract",
        details=(
            "An unverified customer memo suggests a large contract may move "
            "to another logistics provider."
        ),
        source="Supply Chain Wire",
        severity=RumorSeverity.HIGH,
        time_horizon="Next quarter",
        sentiment="negative",
        affected_symbols=["NORTHWIND", "FABRIKAM"],
    ),
    Rumor(
        id="fabrikam-launch",
        headline="Fabrikam is preparing an unexpected product launch",
        details=(
            "Prototype activity and partner briefings point to a launch "
            "earlier than analysts expected."
        ),
        source="Product Pulse",
        severity=RumorSeverity.MEDIUM,
        time_horizon="Next 60 days",
        sentiment="positive",
        affected_symbols=["FABRIKAM", "CONTOSO"],
    ),
    Rumor(
        id="cloud-review",
        headline="Regulators may review the synthetic-cloud sector",
        details=(
            "Policy teams are monitoring a possible review of pricing and "
            "data portability practices."
        ),
        source="Policy Watch",
        severity=RumorSeverity.HIGH,
        time_horizon="Next 90 days",
        sentiment="negative",
        affected_symbols=["MSFT", "AZR"],
    ),
    Rumor(
        id="lseg-data",
        headline="LSEG could expand its real-time data partnership",
        details=(
            "Industry contacts expect a broader distribution agreement for "
            "real-time analytics products."
        ),
        source="Exchange Floor",
        severity=RumorSeverity.MEDIUM,
        time_horizon="Next quarter",
        sentiment="positive",
        affected_symbols=["LSEG", "MSFT"],
    ),
    Rumor(
        id="capacity-guidance",
        headline="Azure Dynamics may significantly increase capacity guidance",
        details=(
            "Supplier activity suggests stronger infrastructure demand, but "
            "no updated guidance has been published."
        ),
        source="Capacity Ledger",
        severity=RumorSeverity.MEDIUM,
        time_horizon="Next earnings call",
        sentiment="mixed",
        affected_symbols=["AZR", "MSFT"],
    ),
)


class RumorGenerator:
    """Generate an endless deterministic stream of fictional market signals."""

    _companies = (
        ("CONTOSO", "Contoso"),
        ("NORTHWIND", "Northwind"),
        ("FABRIKAM", "Fabrikam"),
        ("MSFT", "Microsoft"),
        ("LSEG", "LSEG"),
        ("AZR", "Azure Dynamics"),
    )
    _signals = (
        (
            "may be preparing a strategic partnership",
            "Partner briefings suggest negotiations are active, but neither "
            "company has commented.",
            "positive",
        ),
        (
            "could revise its near-term guidance",
            "Trading desks are comparing supplier activity with the company's "
            "most recent public outlook.",
            "mixed",
        ),
        (
            "is reportedly reviewing a major product line",
            "Channel checks point to a portfolio review that could alter "
            "investment priorities.",
            "negative",
        ),
        (
            "may expand into a new regional market",
            "Local hiring and partner activity suggest an expansion plan is "
            "being evaluated.",
            "positive",
        ),
        (
            "could face an unexpected supplier delay",
            "Fictional logistics data shows longer lead times for a critical "
            "component.",
            "negative",
        ),
    )
    _sources = (
        "Closing Bell Wire",
        "Market Chatter",
        "Sector Signal",
        "Trading Desk Notes",
        "Industry Pulse",
    )

    def __init__(self, seed: int = 5150) -> None:
        self._random = Random(seed)
        self._sequence = 0

    def next_rumor(self) -> Rumor:
        """Return a newly generated fictional market signal."""

        self._sequence += 1
        symbol, company = self._random.choice(self._companies)
        signal, details, sentiment = self._random.choice(self._signals)
        secondary_symbol = self._random.choice(
            [
                candidate_symbol
                for candidate_symbol, _ in self._companies
                if candidate_symbol != symbol
            ]
        )
        return Rumor(
            id=f"live-{self._sequence:05d}",
            headline=f"{company} {signal}",
            details=details,
            source=self._random.choice(self._sources),
            severity=self._random.choice(list(RumorSeverity)),
            time_horizon=self._random.choice(
                ("Next 30 days", "Next quarter", "Next earnings call")
            ),
            sentiment=sentiment,
            affected_symbols=[symbol, secondary_symbol],
        )

    def verify(self, rumor: Rumor) -> Rumor:
        """Create a deterministic confirmation or denial update."""

        self._sequence += 1
        confirmed = self._sequence % 3 != 0
        status = (
            RumorStatus.CONFIRMED if confirmed else RumorStatus.DENIED
        )
        update = (
            "A fictional company statement has now confirmed the core signal."
            if confirmed
            else "A fictional company spokesperson has denied the core claim."
        )
        return rumor.model_copy(
            update={
                "status": status,
                "details": f"{rumor.details} {update}",
                "updated_at": datetime.now(UTC),
            }
        )


class PortfolioAnalysisEngine:
    """Create specialist summaries and a final deterministic report."""

    _severity_weight = {
        RumorSeverity.LOW: 0.25,
        RumorSeverity.MEDIUM: 0.55,
        RumorSeverity.HIGH: 0.85,
    }

    def signal_summary(self, rumor: Rumor) -> str:
        """Summarize the entities and direction implied by a rumor."""

        symbols = ", ".join(rumor.affected_symbols) or "the broader market"
        return (
            f"Detected a {rumor.sentiment} signal affecting {symbols} over "
            f"{rumor.time_horizon.lower()}."
        )

    def credibility_summary(self, rumor: Rumor) -> str:
        """Describe how the verification state affects confidence."""

        if rumor.status == RumorStatus.CONFIRMED:
            return "The signal is confirmed, so the analysis uses high confidence."
        if rumor.status == RumorStatus.DENIED:
            return (
                "The signal has been denied; residual volatility is possible, "
                "but the core claim receives low weight."
            )
        return (
            "The signal is still developing. Recommendations preserve optionality "
            "and avoid treating the claim as established fact."
        )

    def holding_impacts(
        self,
        portfolio: Portfolio,
        rumor: Rumor,
    ) -> list[HoldingImpact]:
        """Estimate holding-level sensitivity to the market signal."""

        severity = self._severity_weight[rumor.severity]
        affected = set(rumor.affected_symbols)
        impacts: list[HoldingImpact] = []
        for holding in portfolio.holdings:
            directly_affected = holding.symbol in affected
            impact_score = round(
                min(
                    100,
                    (
                        severity
                        * (0.75 if directly_affected else 0.18)
                        * (0.55 + holding.allocation)
                        * 100
                    ),
                )
            )
            if not directly_affected:
                direction = "limited"
                rationale = (
                    "No direct link was detected; monitor for broader market "
                    "or sector spillover."
                )
            else:
                direction = {
                    "positive": "upside",
                    "negative": "downside",
                    "mixed": "volatile",
                }[rumor.sentiment]
                rationale = (
                    f"{holding.symbol} is named in the signal and represents "
                    f"{holding.allocation:.0%} of the portfolio."
                )
            impacts.append(
                HoldingImpact(
                    symbol=holding.symbol,
                    allocation=holding.allocation,
                    direction=direction,
                    impact_score=impact_score,
                    rationale=rationale,
                )
            )
        return sorted(
            impacts,
            key=lambda impact: impact.impact_score,
            reverse=True,
        )

    def exposure_summary(
        self,
        portfolio: Portfolio,
        rumor: Rumor,
    ) -> str:
        """Summarize directly affected portfolio allocation."""

        affected = set(rumor.affected_symbols)
        allocation = sum(
            holding.allocation
            for holding in portfolio.holdings
            if holding.symbol in affected
        )
        if allocation == 0:
            return "No holdings are directly named; exposure is limited to spillover."
        return f"{allocation:.0%} of the portfolio is directly connected to the signal."

    def scenario_summary(self, rumor: Rumor) -> str:
        """Describe the scenario set being modeled."""

        return (
            f"Built bull, base, and bear outcomes for a {rumor.severity.value} "
            f"severity event over {rumor.time_horizon.lower()}."
        )

    def risk_summary(self, portfolio: Portfolio, rumor: Rumor) -> str:
        """Summarize concentration and event sensitivity."""

        largest = max(portfolio.holdings, key=lambda holding: holding.allocation)
        return (
            f"The largest position is {largest.symbol} at "
            f"{largest.allocation:.0%}; the portfolio is assessed against the "
            f"{rumor.severity.value} severity signal."
        )

    def build_report(
        self,
        portfolio: Portfolio,
        rumor: Rumor,
        recommendation: str,
    ) -> AnalysisReport:
        """Assemble the final portfolio analysis report."""

        impacts = self.holding_impacts(portfolio, rumor)
        affected = set(rumor.affected_symbols)
        affected_allocation = sum(
            holding.allocation
            for holding in portfolio.holdings
            if holding.symbol in affected
        )
        largest_allocation = max(
            holding.allocation for holding in portfolio.holdings
        )
        severity = self._severity_weight[rumor.severity]
        status_factor = {
            RumorStatus.DEVELOPING: 0.65,
            RumorStatus.CONFIRMED: 1.0,
            RumorStatus.DENIED: 0.2,
        }[rumor.status]
        risk_score = round(
            min(
                100,
                18
                + largest_allocation * 36
                + severity * 26
                + affected_allocation * status_factor * 30,
            )
        )
        diversification_score = round(
            max(0, min(100, (1 - largest_allocation) * 125))
        )
        confidence = {
            RumorStatus.DEVELOPING: 58,
            RumorStatus.CONFIRMED: 88,
            RumorStatus.DENIED: 76,
        }[rumor.status]
        effect = round(severity * max(affected_allocation, 0.15) * 12, 1)
        direction = -1 if rumor.sentiment == "negative" else 1
        if rumor.sentiment == "mixed":
            direction = 0
        base_effect = effect * direction
        scenarios = [
            ScenarioProjection(
                name="Bull",
                portfolio_effect=f"{max(0.6, effect):+.1f}%",
                probability=25,
                narrative=(
                    "The signal resolves favorably and directly affected holdings "
                    "benefit while diversification limits volatility."
                ),
            ),
            ScenarioProjection(
                name="Base",
                portfolio_effect=f"{base_effect:+.1f}%",
                probability=50,
                narrative=(
                    "The market partially prices the signal while awaiting "
                    "verification and clearer company guidance."
                ),
            ),
            ScenarioProjection(
                name="Bear",
                portfolio_effect=f"{-max(0.8, effect * 1.25):+.1f}%",
                probability=25,
                narrative=(
                    "The adverse interpretation dominates and concentrated "
                    "positions amplify the portfolio response."
                ),
            ),
        ]
        top_impact = impacts[0]
        executive_summary = (
            f"{rumor.headline} creates the strongest modeled sensitivity in "
            f"{top_impact.symbol}. {affected_allocation:.0%} of "
            f"{portfolio.customer_name}'s portfolio is directly connected to "
            "the signal."
        )
        return AnalysisReport(
            executive_summary=executive_summary,
            confidence=confidence,
            risk_score=risk_score,
            diversification_score=diversification_score,
            affected_allocation=affected_allocation,
            holding_impacts=impacts,
            scenarios=scenarios,
            recommendation=recommendation,
        )
