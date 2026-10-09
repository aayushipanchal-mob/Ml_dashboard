"""
app/config/settings.py
─────────────────────
Centralised application settings loaded from environment variables / .env file.
All downstream code imports from here – nothing reads os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── AWS ──────────────────────────────────────────────────────────────────
    aws_region: str = Field(default="ap-southeast-1", alias="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: Optional[str] = Field(default=None, alias="AWS_SESSION_TOKEN")

    # ── Athena ────────────────────────────────────────────────────────────────
    athena_database: str = Field(default="ml_dashboard", alias="ATHENA_DATABASE")
    athena_output_location: str = Field(
        default="s3://your-athena-results-bucket/ml-dashboard/",
        alias="ATHENA_OUTPUT_LOCATION",
    )
    athena_query_timeout: int = Field(default=120, alias="ATHENA_QUERY_TIMEOUT")

    # ── Table names ───────────────────────────────────────────────────────────
    impressions_table: str = Field(default="ml_dashboard.impressions", alias="IMPRESSIONS_TABLE")
    clicks_table: str = Field(default="ml_dashboard.clicks", alias="CLICKS_TABLE")
    organic_table: str = Field(default="ml_dashboard.organic", alias="ORGANIC_TABLE")
    organic90_table: str = Field(default="ml_dashboard.organic90", alias="ORGANIC90_TABLE")
    training_table: str = Field(default="ml_dashboard.training_data", alias="TRAINING_TABLE")
    validation_table: str = Field(default="ml_dashboard.validation_data", alias="VALIDATION_TABLE")

    # ── S3 Data Source ────────────────────────────────────────────────────────
    s3_data_prefix: str = Field(
        default="s3://mobavenue-simplismart-aws-s3-apse-sg/rtb",
        alias="S3_DATA_PREFIX",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")

    @field_validator("athena_output_location")
    @classmethod
    def _output_must_be_s3(cls, v: str) -> str:
        if not v.startswith("s3://"):
            raise ValueError("ATHENA_OUTPUT_LOCATION must start with 's3://'")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
