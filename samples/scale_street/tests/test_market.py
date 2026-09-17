"""Domain tests for the synthetic market."""

from scale_street.market import MarketSimulator


def test_customer_portfolios_are_repeatable() -> None:
    market = MarketSimulator()

    first = market.portfolio("CUST-5150")
    second = market.portfolio("CUST-5150")

    assert first == second
    assert sum(holding.allocation for holding in first.holdings) == 1


def test_open_market_changes_market_conditions() -> None:
    market = MarketSimulator()

    market.open_market()
    snapshot = market.snapshot()

    assert snapshot.status == "OPEN"
    assert snapshot.mood == "VOLATILE"
