"""Synthetic market and portfolio data."""

from datetime import UTC, datetime
from random import Random

from scale_street.models import Holding, MarketSnapshot, Portfolio, RiskProfile


class MarketSimulator:
    """Provide deterministic market conditions and paper portfolios."""

    _symbols = ("MSFT", "LSEG", "AZR", "CONTOSO", "FABRIKAM", "NORTHWIND")
    _first_names = ("Ada", "Grace", "Linus", "Margaret", "Satya", "Katherine")
    _last_names = ("Bull", "Bear", "Hedge", "Ticker", "Ledger", "Quants")

    def __init__(self, seed: int = 5150) -> None:
        self._random = Random(seed)
        self._is_open = False
        self._event = "Pre-market systems are warming up."

    def open_market(self) -> None:
        """Move the simulator into the opening-bell state."""

        self._is_open = True
        self._event = "Opening bell: portfolio advice demand is surging."

    def reset(self) -> None:
        """Reset the market to a stable pre-market state."""

        self._is_open = False
        self._event = "Pre-market systems are warming up."

    def snapshot(self) -> MarketSnapshot:
        """Return the current market state."""

        return MarketSnapshot(
            status="OPEN" if self._is_open else "PRE-MARKET",
            mood="VOLATILE" if self._is_open else "CAUTIOUSLY OPTIMISTIC",
            volatility=0.82 if self._is_open else 0.18,
            event=self._event,
            updated_at=datetime.now(UTC),
        )

    def portfolio(self, customer_id: str) -> Portfolio:
        """Create a repeatable paper portfolio for a customer."""

        customer_seed = sum(ord(character) for character in customer_id)
        random = Random(customer_seed)
        symbols = random.sample(self._symbols, 3)
        first = random.choice(self._first_names)
        last = random.choice(self._last_names)
        risk_profile = random.choice(list(RiskProfile))
        allocations = (0.5, 0.3, 0.2)
        holdings = [
            Holding(symbol=symbol, allocation=allocation)
            for symbol, allocation in zip(symbols, allocations, strict=True)
        ]
        return Portfolio(
            customer_id=customer_id,
            customer_name=f"{first} {last}",
            risk_profile=risk_profile,
            holdings=holdings,
        )
