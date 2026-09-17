"""API tests for Scale Street."""

import time

from fastapi.testclient import TestClient

from scale_street.config import Settings
from scale_street.main import create_app


def test_health_and_initial_stats() -> None:
    app = create_app(Settings())

    with TestClient(app) as client:
        health = client.get("/health")
        stats = client.get("/api/stats")

    assert health.status_code == 200
    assert health.json() == {"status": "healthy"}
    assert stats.status_code == 200
    assert stats.json()["market_status"] == "PRE-MARKET"
    assert stats.json()["requests_total"] == 0


def test_portfolio_advice_is_recorded() -> None:
    app = create_app(
        Settings(
            simulated_agent_latency_ms=1,
            simulated_agent_concurrency_limit=2,
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/portfolios/CUST-00001/advise",
            json={"concern": "Can this survive the opening bell?"},
        )
        stats = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json()["agent_name"] == "Hedgehog"
    assert stats.json()["successful_requests"] == 1
    assert stats.json()["recommendations_in_memory"] == 1


def test_reset_clears_runtime_state() -> None:
    app = create_app(Settings(simulated_agent_latency_ms=1))

    with TestClient(app) as client:
        client.post(
            "/api/portfolios/CUST-00001/advise",
            json={"concern": "Test concern"},
        )
        response = client.post("/api/market/reset")
        stats = client.get("/api/stats")

    assert response.status_code == 204
    assert stats.json()["requests_total"] == 0


def test_live_rumor_feed_publishes_updates() -> None:
    app = create_app(Settings(rumor_update_interval_seconds=0.01))

    with TestClient(app) as client:
        initial = client.get("/api/rumors")
        time.sleep(0.025)
        updated = client.get("/api/rumors")

    assert initial.status_code == 200
    assert len(initial.json()) == 3
    assert updated.status_code == 200
    assert len(updated.json()) > len(initial.json())
    assert updated.json()[0]["updated_at"]


def test_portfolio_analysis_completes_in_background() -> None:
    app = create_app(
        Settings(
            analysis_stage_latency_ms=1,
            simulated_agent_latency_ms=1,
        )
    )
    payload = {
        "portfolio": {
            "customer_id": "LAB-1",
            "customer_name": "Test Portfolio",
            "risk_profile": "balanced",
            "holdings": [
                {"symbol": "CONTOSO", "allocation": 0.5},
                {"symbol": "MSFT", "allocation": 0.3},
                {"symbol": "LSEG", "allocation": 0.2},
            ],
        },
        "rumor": {
            "id": "test-rumor",
            "headline": "Contoso may acquire a logistics company",
            "details": "A fictional signal for an API test.",
            "source": "Test Desk",
            "severity": "high",
            "time_horizon": "Next 30 days",
            "status": "developing",
            "sentiment": "positive",
            "affected_symbols": ["CONTOSO"],
        },
    }

    with TestClient(app) as client:
        created = client.post("/api/analyses", json=payload)
        analysis_id = created.json()["id"]

        analysis = created.json()
        for _ in range(50):
            if analysis["status"] == "completed":
                break
            time.sleep(0.01)
            analysis = client.get(f"/api/analyses/{analysis_id}").json()

        history = client.get("/api/analyses")

    assert created.status_code == 202
    assert analysis["status"] == "completed"
    assert analysis["report"]["affected_allocation"] == 0.5
    assert analysis["report"]["holding_impacts"][0]["symbol"] == "CONTOSO"
    assert all(stage["status"] == "completed" for stage in analysis["stages"])
    assert history.json()[0]["id"] == analysis_id


def test_completed_analysis_history_is_bounded() -> None:
    app = create_app(
        Settings(
            analysis_stage_latency_ms=0,
            simulated_agent_latency_ms=0,
        )
    )
    payload = {
        "portfolio": {
            "customer_id": "LAB-BOUND",
            "customer_name": "Bounded Portfolio",
            "risk_profile": "balanced",
            "holdings": [
                {"symbol": "CONTOSO", "allocation": 0.6},
                {"symbol": "MSFT", "allocation": 0.4},
            ],
        },
        "rumor": {
            "id": "bounded-rumor",
            "headline": "Contoso capacity test",
            "details": "A fictional signal for retention testing.",
            "source": "Test Desk",
            "severity": "medium",
            "time_horizon": "Next 30 days",
            "status": "developing",
            "sentiment": "mixed",
            "affected_symbols": ["CONTOSO"],
        },
    }

    with TestClient(app) as client:
        created_ids = [
            client.post("/api/analyses", json=payload).json()["id"]
            for _ in range(51)
        ]

        history = []
        for _ in range(100):
            time.sleep(0.01)
            history = client.get("/api/analyses").json()
            if len(history) == 50 and all(
                analysis["status"] == "completed" for analysis in history
            ):
                break

        oldest = client.get(f"/api/analyses/{created_ids[0]}")

    assert len(history) == 50
    assert oldest.status_code == 404
