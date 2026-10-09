"""
app/api/dataset_counts.py
──────────────────────────
Route: GET /api/dataset-counts

Returns the number of rows in train_final and val_final Parquet datasets
stored in S3, for every bundle that the latest (or specified) model was
trained on.

Flow
────
1. Load model's bundle list from feature_config.pkl on S3
   (same call used by /api/bundles — cached for 5 min)
2. For each bundle, run Athena COUNT(*) against the S3 Parquet files
3. Return per-bundle and grand total counts

S3 path pattern:
  s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/
      {bundle_name}/train_final/
      {bundle_name}/val_final/

No data is downloaded — Athena reads Parquet metadata in-place.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.dashboard import BundleDataCountResponse, DatasetCountsResponse
from app.services.model_artifacts_service import ModelArtifactsService
from app.services.training_data_service import (
    TrainingDataService,
    S3_BUCKET,
    TRAINING_DATA_PREFIX,
)
from app.services.athena_service import AthenaQueryError, AthenaTimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()

_model_svc = ModelArtifactsService()
_data_svc = TrainingDataService()


@router.get(
    "/dataset-counts",
    response_model=DatasetCountsResponse,
    summary="Training & validation row counts per bundle (from S3 Parquet)",
    description=(
        "Counts rows in `train_final/` and `val_final/` Parquet datasets stored in S3 "
        "for every bundle the model was trained on. "
        "Bundle list is fetched live from the model's `feature_config.pkl`. "
        "Optionally pass `timestamp` to query a specific model version. "
        "No data is downloaded — Athena queries the S3 Parquet files directly."
    ),
    tags=["Dataset Counts"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "model_timestamp": "20260919_070055",
                        "total_bundles": 3,
                        "total_train_rows": 387000,
                        "total_val_rows": 96750,
                        "bundles": [
                            {
                                "bundle_name": "meesho",
                                "train_rows": 125430,
                                "val_rows": 31250,
                                "train_s3_path": "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/meesho/train_final/",
                                "val_s3_path":   "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/meesho/val_final/",
                            },
                            {
                                "bundle_name": "grofers",
                                "train_rows": 98200,
                                "val_rows": 24550,
                                "train_s3_path": "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/grofers/train_final/",
                                "val_s3_path":   "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/grofers/val_final/",
                            },
                        ],
                    }
                }
            }
        },
        500: {"description": "S3 or Athena error"},
        504: {"description": "Athena query timed out"},
    },
)
def get_dataset_counts(
    timestamp: Optional[str] = Query(
        default=None,
        description=(
            "Optional model timestamp to use for bundle discovery "
            "(e.g. 20260919_070055). Defaults to the latest model."
        ),
    )
) -> DatasetCountsResponse:
    logger.info("GET /api/dataset-counts | timestamp=%s", timestamp or "latest")

    # ── Step 1: Get bundle names from model artifacts ──────────────────────
    try:
        if timestamp:
            model_info = _model_svc._load_model_info(timestamp)
        else:
            model_info = _model_svc.get_latest_model_info()
    except Exception as exc:
        logger.error("Failed to load model info: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not load model artifact from S3: {exc}",
        )

    if not model_info.bundle_ids:
        raise HTTPException(
            status_code=404,
            detail=f"No bundles found in model timestamp {model_info.timestamp}",
        )

    # bundle_ids from feature_config look like:  "meesho", "grofers", etc.
    # (the same short names used in the S3 path)
    bundle_names = model_info.bundle_ids

    logger.info(
        "Counting datasets for model=%s bundles=%s",
        model_info.timestamp,
        bundle_names,
    )

    # ── Step 2: Count rows via Athena ──────────────────────────────────────
    try:
        result = _data_svc.get_counts_for_model(
            model_timestamp=model_info.timestamp,
            bundle_names=bundle_names,
        )
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout for dataset counts: %s", exc)
        raise HTTPException(
            status_code=504,
            detail="Athena query timed out counting dataset rows.",
        )
    except AthenaQueryError as exc:
        logger.error("Athena error for dataset counts: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Athena query failed: {exc}",
        )
    except Exception as exc:
        logger.error("Unexpected error for dataset counts: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # ── Step 3: Build response ─────────────────────────────────────────────
    bundle_responses = [
        BundleDataCountResponse(
            bundle_name=b.bundle_name,
            train_rows=b.train_rows,
            val_rows=b.val_rows,
            train_start_date=b.train_stats.min_date,
            train_end_date=b.train_stats.max_date,
            val_start_date=b.val_stats.min_date,
            val_end_date=b.val_stats.max_date,
            train_label_1_count=b.train_stats.label_1_count,
            train_label_0_count=b.train_stats.label_0_count,
            val_label_1_count=b.val_stats.label_1_count,
            val_label_0_count=b.val_stats.label_0_count,
            train_s3_path=(
                f"s3://{S3_BUCKET}/{TRAINING_DATA_PREFIX}/"
                f"{b.bundle_name}/train_final/"
            ),
            val_s3_path=(
                f"s3://{S3_BUCKET}/{TRAINING_DATA_PREFIX}/"
                f"{b.bundle_name}/val_final/"
            ),
        )
        for b in result.bundles
    ]

    return DatasetCountsResponse(
        model_timestamp=result.model_timestamp,
        bundles=bundle_responses,
        total_train_rows=result.total_train_rows,
        total_val_rows=result.total_val_rows,
        total_bundles=len(bundle_responses),
    )
