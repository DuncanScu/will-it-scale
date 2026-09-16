"""FastAPI entry point for Scale Street."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from scale_street.advisor import AdvisorThrottledError, create_financial_advisor
from scale_street.config import Settings, get_settings
from scale_street.market import MarketSimulator
from scale_street.models import (
    AdviceRequest,
    AdviceResponse,
    MarketOpenRequest,
    MarketOpenResponse,
    MarketSnapshot,
    Portfolio,
    PortfolioAnalysis,
    PortfolioAnalysisRequest,
    Rumor,
    ServiceStats,
)
from scale_street.service import ScaleStreetService

STATIC_DIRECTORY = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Scale Street application."""

    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = ScaleStreetService(
            settings=app_settings,
            market=MarketSimulator(),
            advisor=create_financial_advisor(app_settings),
        )
        await app.state.service.start()
        try:
            yield
        finally:
            await app.state.service.shutdown()

    application = FastAPI(
        title=app_settings.app_name,
        description="Can financial agents survive the opening bell?",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.mount(
        "/static",
        StaticFiles(directory=STATIC_DIRECTORY),
        name="static",
    )

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIRECTORY / "index.html")

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @application.get("/ready")
    async def ready(request: Request) -> dict[str, str]:
        service = get_service(request)
        snapshot = service.market.snapshot()
        return {"status": "ready", "market": snapshot.status}

    @application.get("/api/market", response_model=MarketSnapshot)
    async def market(request: Request) -> MarketSnapshot:
        return get_service(request).market.snapshot()

    @application.get(
        "/api/portfolios/{customer_id}",
        response_model=Portfolio,
    )
    async def portfolio(customer_id: str, request: Request) -> Portfolio:
        return get_service(request).market.portfolio(customer_id)

    @application.post(
        "/api/portfolios/{customer_id}/advise",
        response_model=AdviceResponse,
    )
    async def advise(
        customer_id: str,
        payload: AdviceRequest,
        request: Request,
    ) -> AdviceResponse:
        try:
            return await get_service(request).request_advice(
                customer_id=customer_id,
                concern=payload.concern,
            )
        except AdvisorThrottledError as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(error),
            ) from error

    @application.post(
        "/api/market/open",
        response_model=MarketOpenResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def open_market(
        payload: MarketOpenRequest,
        request: Request,
    ) -> MarketOpenResponse:
        service = get_service(request)
        if not service.start_market_burst(
            customers=payload.customers,
            concurrency=payload.concurrency,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An opening-bell simulation is already running.",
            )
        return MarketOpenResponse(
            status="accepted",
            customers=payload.customers,
            concurrency=payload.concurrency,
        )

    @application.post("/api/market/reset", status_code=status.HTTP_204_NO_CONTENT)
    async def reset_market(request: Request) -> None:
        await get_service(request).reset()

    @application.get("/api/stats", response_model=ServiceStats)
    async def stats(request: Request) -> ServiceStats:
        return await get_service(request).stats()

    @application.get("/api/rumors", response_model=list[Rumor])
    async def rumors(request: Request) -> list[Rumor]:
        return await get_service(request).rumors()

    @application.get("/api/rumors/stream")
    async def rumor_stream(request: Request) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            async for event in get_service(request).rumor_events():
                if await request.is_disconnected():
                    break
                yield f"event: rumor\ndata: {json.dumps(event)}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @application.post(
        "/api/analyses",
        response_model=PortfolioAnalysis,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_analysis(
        payload: PortfolioAnalysisRequest,
        request: Request,
    ) -> PortfolioAnalysis:
        return await get_service(request).start_analysis(payload)

    @application.get(
        "/api/analyses",
        response_model=list[PortfolioAnalysis],
    )
    async def analyses(request: Request) -> list[PortfolioAnalysis]:
        return await get_service(request).analyses()

    @application.get(
        "/api/analyses/{analysis_id}",
        response_model=PortfolioAnalysis,
    )
    async def analysis(
        analysis_id: str,
        request: Request,
    ) -> PortfolioAnalysis:
        result = await get_service(request).analysis(analysis_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found.",
            )
        return result

    return application


def get_service(request: Request) -> ScaleStreetService:
    """Return the application service from FastAPI state."""

    return request.app.state.service


app = create_app()
