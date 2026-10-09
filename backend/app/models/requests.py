"""
app/models/requests.py
──────────────────────
Pydantic request / query-parameter models with full validation.
Every public endpoint accepts one of these validated models so that
business logic and SQL layers never receive raw unvalidated strings.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _nonempty(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field} must not be empty")
    return value.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Individual endpoint models
# ─────────────────────────────────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    """Query params for /api/suppression and /api/cr (single campaign)."""

    campaign_id: str
    bundle_id: str

    @field_validator("campaign_id")
    @classmethod
    def campaign_id_nonempty(cls, v: str) -> str:
        return _nonempty(v, "campaign_id")

    @field_validator("bundle_id")
    @classmethod
    def bundle_id_nonempty(cls, v: str) -> str:
        return _nonempty(v, "bundle_id")


class SuppressionRequest(CampaignRequest):
    """
    GET /api/suppression?campaign_id=…&bundle_id=…&date=YYYY-MM-DD
    """

    date: date


class DataSizeRequest(BaseModel):
    """
    GET /api/training-data-size  or  /api/validation-data-size
        ?campaign_id=…&bundle_id=…&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """

    campaign_id: str
    bundle_id: str
    start_date: date
    end_date: date

    @field_validator("campaign_id")
    @classmethod
    def campaign_id_nonempty(cls, v: str) -> str:
        return _nonempty(v, "campaign_id")

    @field_validator("bundle_id")
    @classmethod
    def bundle_id_nonempty(cls, v: str) -> str:
        return _nonempty(v, "bundle_id")

    @model_validator(mode="after")
    def start_before_end(self) -> "DataSizeRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class CRRequest(CampaignRequest):
    """
    GET /api/cr?campaign_id=…&bundle_id=…&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def start_before_end(self) -> "CRRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class DashboardRequest(BaseModel):
    """
    POST /api/dashboard/check  –  body model
    GET  /api/dashboard        –  all params forwarded as query params
    """

    campaign_id: str
    bundle_id: str
    input_date: date

    training_start_date: Optional[date] = None
    training_end_date: Optional[date] = None

    validation_start_date: Optional[date] = None
    validation_end_date: Optional[date] = None

    model_timestamp: Optional[str] = None

    include_suppression: bool = False
    include_cr: bool = False

    @field_validator("campaign_id")
    @classmethod
    def campaign_id_nonempty(cls, v: str) -> str:
        return _nonempty(v, "campaign_id")

    @field_validator("bundle_id")
    @classmethod
    def bundle_id_nonempty(cls, v: str) -> str:
        return _nonempty(v, "bundle_id")

    @model_validator(mode="after")
    def validate_date_ranges(self) -> "DashboardRequest":
        if self.training_start_date and self.training_end_date:
            if self.training_start_date > self.training_end_date:
                raise ValueError(
                    "training_start_date must be on or before training_end_date"
                )
        if self.validation_start_date and self.validation_end_date:
            if self.validation_start_date > self.validation_end_date:
                raise ValueError(
                    "validation_start_date must be on or before validation_end_date"
                )
        return self
