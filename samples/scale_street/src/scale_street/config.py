"""Application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SCALE_STREET_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Scale Street"
    agent_mode: Literal["simulated", "foundry"] = "simulated"
    scale_profile: Literal["constrained", "improved"] = "constrained"
    foundry_project_endpoint: str | None = Field(
        default=None,
        validation_alias="FOUNDRY_PROJECT_ENDPOINT",
    )
    foundry_model: str = Field(
        default="gpt-5-mini",
        validation_alias="FOUNDRY_MODEL",
    )
    simulated_agent_latency_ms: int = 180
    simulated_agent_concurrency_limit: int = 8
    analysis_stage_latency_ms: int = 420
    rumor_update_interval_seconds: float = 4.5
    recommendation_history_limit: int = 500
    market_burst_size: int = 120
    market_burst_concurrency: int = 24


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
