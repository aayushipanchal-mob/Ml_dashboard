"""
app/models/dashboard.py
───────────────────────
Pydantic response models for every public endpoint.
The frontend only needs to know these shapes – it never reconstructs formulas.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Common formula representation
# ─────────────────────────────────────────────────────────────────────────────

class Formula(BaseModel):
    """
    Carries everything the frontend needs to render a "Show Formula" toggle.
    numerator / denominator are optional for non-ratio metrics.
    """
    name: str
    expression: str
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    numerator_value: Optional[float] = None
    denominator_value: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# /api/campaigns
# ─────────────────────────────────────────────────────────────────────────────

class CampaignMapping(BaseModel):
    campaign_id: str
    bundle_id: str


class CampaignsResponse(BaseModel):
    campaigns: List[CampaignMapping]


# ─────────────────────────────────────────────────────────────────────────────
# /api/training-data-size
# ─────────────────────────────────────────────────────────────────────────────

class DataSizeResponse(BaseModel):
    campaign_id: str
    bundle_id: str
    size: int
    start_date: date
    end_date: date


# ─────────────────────────────────────────────────────────────────────────────
# /api/suppression
# ─────────────────────────────────────────────────────────────────────────────

class SuppressionResponse(BaseModel):
    campaign_id: str
    bundle_id: str
    check_date: date
    total_payload_devices: int
    suppressed_devices: int
    suppression_rate: float = Field(
        description="(suppressed_devices / total_payload_devices) * 100"
    )
    status: str = Field(description="PASS or FAIL")
    formula: Formula


# ─────────────────────────────────────────────────────────────────────────────
# /api/cr
# ─────────────────────────────────────────────────────────────────────────────

class CRDayRow(BaseModel):
    event_date: str
    total_clicked_devices: int
    total_organic_installs: int
    intersected_devices_24h: int
    conversion_rate_24h: float


class CRResponse(BaseModel):
    campaign_id: str
    bundle_id: str
    start_date: date
    end_date: date
    data: List[CRDayRow]
    formula: Formula


# ─────────────────────────────────────────────────────────────────────────────
# /api/dashboard  (combined)
# ─────────────────────────────────────────────────────────────────────────────

class DashboardInput(BaseModel):
    campaign_id: str
    bundle_id: str
    input_date: date


class DashboardTraining(BaseModel):
    size: int
    start_date: str
    end_date: str
    label_1_count: int = 0
    label_0_count: int = 0


class DashboardValidation(BaseModel):
    size: int
    start_date: str
    end_date: str
    label_1_count: int = 0
    label_0_count: int = 0


class DashboardSuppression(BaseModel):
    total_payload_devices: int
    suppressed_devices: int
    suppression_rate: float
    status: str
    formula: Formula


class DashboardCR(BaseModel):
    total_clicked_devices: int
    total_organic_installs: int
    intersected_devices_24h: int
    conversion_rate_24h: float
    daily_trend: List[CRDayRow]
    formula: Formula


class DashboardResponse(BaseModel):
    input: DashboardInput
    training: DashboardTraining
    validation: DashboardValidation
    suppression: Optional[DashboardSuppression] = None
    cr: Optional[DashboardCR] = None


# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    athena_database: str


# ─────────────────────────────────────────────────────────────────────────────
# /api/bundles  – bundle IDs from the live model artifact
# ─────────────────────────────────────────────────────────────────────────────

class BundlesResponse(BaseModel):
    """
    Bundle IDs fetched from the latest model's feature_config.pkl on S3.
    This is the source of truth for which bundles the model was trained on.
    """
    model_timestamp: str
    bundle_ids: List[str]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# /api/model-info  – full model metadata
# ─────────────────────────────────────────────────────────────────────────────

class ModelInfoResponse(BaseModel):
    """
    Full metadata about a model artifact loaded from S3.
    Includes bundles, temperature, and feature column names.
    """
    model_timestamp: str
    s3_prefix: str
    bundle_ids: List[str]
    total_bundles: int
    temperature: Optional[float] = None
    user_cat_features: List[str]
    user_num_features: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# /api/models  – list all available model timestamps
# ─────────────────────────────────────────────────────────────────────────────

class ModelTimestampItem(BaseModel):
    timestamp: str
    s3_path: str


class ModelsListResponse(BaseModel):
    """All model timestamps available in S3, newest first."""
    total: int
    models: List[ModelTimestampItem]


# ─────────────────────────────────────────────────────────────────────────────
# /api/dataset-counts  – training + validation row counts per bundle from S3
# ─────────────────────────────────────────────────────────────────────────────

class BundleDataCountResponse(BaseModel):
    """Row counts for a single bundle's train and validation datasets."""
    bundle_name: str = Field(description="Short bundle name used in S3 path (e.g. 'meesho')")
    train_rows: int = Field(description="Number of rows in train_final/")
    val_rows: int = Field(description="Number of rows in val_final/")
    train_start_date: str = Field(default="")
    train_end_date: str = Field(default="")
    val_start_date: str = Field(default="")
    val_end_date: str = Field(default="")
    train_label_1_count: int = Field(default=0)
    train_label_0_count: int = Field(default=0)
    val_label_1_count: int = Field(default=0)
    val_label_0_count: int = Field(default=0)
    train_s3_path: str = Field(description="S3 path for this bundle's training data")
    val_s3_path: str = Field(description="S3 path for this bundle's validation data")


class DatasetCountsResponse(BaseModel):
    """
    Training and validation row counts for all bundles in the model.
    Bundle list is sourced from the model's feature_config.pkl (not hardcoded).
    """
    model_timestamp: str
    bundles: List[BundleDataCountResponse]
    total_train_rows: int
    total_val_rows: int
    total_bundles: int


