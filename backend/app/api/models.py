"""
app/api/models.py
──────────────────
Routes for model artifact discovery:

  GET /api/models          – list all model timestamps in S3 (newest first)
  GET /api/model-info      – full metadata for the latest (or a specific) model
  GET /api/bundles         – just the bundle IDs from the latest model (for dropdowns)

These endpoints read directly from S3 model artifacts (feature_config.pkl)
so the dashboard always shows the bundles the model was actually trained on.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.dashboard import (
    BundlesResponse,
    ModelInfoResponse,
    ModelsListResponse,
    ModelTimestampItem,
)
from app.services.model_artifacts_service import ModelArtifactsService

logger = logging.getLogger(__name__)
router = APIRouter()
_service = ModelArtifactsService()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/bundles
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/bundles",
    response_model=BundlesResponse,
    summary="Get bundle IDs from the latest trained model",
    description=(
        "Fetches the list of bundle IDs directly from the latest model's "
        "`feature_config.pkl` artifact stored in S3. "
        "This is the source of truth for which apps the model was trained on. "
        "Use this to populate the Bundle ID dropdown in the dashboard."
    ),
    tags=["Model Artifacts"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "model_timestamp": "20260919_070055",
                        "bundle_ids": [
                            "com.grofers.customerapp",
                            "com.licious",
                            "com.pantaloons",
                            "com.meesho.supply",
                            "com.coindcx.btc",
                            "com.blinkit.bistro",
                        ],
                        "total": 6,
                    }
                }
            }
        },
        500: {"description": "Failed to read from S3"},
    },
)
def get_bundles() -> BundlesResponse:
    logger.info("GET /api/bundles – request received")
    try:
        info = _service.get_latest_model_info()
    except Exception as exc:
        logger.error("Failed to fetch bundles from S3: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not load bundle list from model artifacts: {exc}",
        )
    return BundlesResponse(
        model_timestamp=info.timestamp,
        bundle_ids=info.bundle_ids,
        total=len(info.bundle_ids),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/model-info
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Get full metadata for the latest model",
    description=(
        "Returns full metadata about the latest model artifact from S3: "
        "bundle IDs, model temperature, user categorical features, "
        "user numerical features, and the S3 prefix location. "
        "Optionally pass `timestamp` to query a specific model version."
    ),
    tags=["Model Artifacts"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "model_timestamp": "20260919_070055",
                        "s3_prefix": "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/ml/models/20260919_070055/",
                        "bundle_ids": ["com.grofers.customerapp", "com.licious"],
                        "total_bundles": 2,
                        "temperature": 0.07,
                        "user_cat_features": ["os", "city", "device_brand"],
                        "user_num_features": ["hour", "day_of_week", "install_rate_7d"],
                    }
                }
            }
        },
        500: {"description": "Failed to read from S3"},
    },
)
def get_model_info(
    timestamp: Optional[str] = Query(
        default=None,
        description="Optional model timestamp (e.g. 20260919_070055). Defaults to latest.",
    )
) -> ModelInfoResponse:
    logger.info("GET /api/model-info | timestamp=%s", timestamp or "latest")
    try:
        if timestamp:
            # Load a specific model version
            info = _service._load_model_info(timestamp)
        else:
            info = _service.get_latest_model_info()
    except Exception as exc:
        logger.error("Failed to load model info: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not load model info from S3: {exc}",
        )
    return ModelInfoResponse(
        model_timestamp=info.timestamp,
        s3_prefix=info.s3_prefix,
        bundle_ids=info.bundle_ids,
        total_bundles=len(info.bundle_ids),
        temperature=info.temperature,
        user_cat_features=info.user_cat_features,
        user_num_features=info.user_num_features,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/models
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List all available model versions in S3",
    description=(
        "Lists all model timestamp folders available in S3 at "
        "`s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/ml/models/`. "
        "Results are sorted newest first. "
        "Use this to let the user select a specific model version to inspect."
    ),
    tags=["Model Artifacts"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "total": 2,
                        "models": [
                            {
                                "timestamp": "20260919_070055",
                                "s3_path": "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/ml/models/20260919_070055/",
                            },
                            {
                                "timestamp": "20260819_050323",
                                "s3_path": "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/ml/models/20260819_050323/",
                            },
                        ],
                    }
                }
            }
        },
        500: {"description": "Failed to list models from S3"},
    },
)
def list_models() -> ModelsListResponse:
    logger.info("GET /api/models – request received")
    try:
        timestamps = _service.list_all_timestamps()
    except Exception as exc:
        logger.error("Failed to list models from S3: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not list model versions from S3: {exc}",
        )
    bucket = _service.S3_BUCKET
    prefix = _service.MODELS_PREFIX
    items = [
        ModelTimestampItem(
            timestamp=ts,
            s3_path=f"s3://{bucket}/{prefix}{ts}/",
        )
        for ts in timestamps
    ]
    return ModelsListResponse(total=len(items), models=items)
