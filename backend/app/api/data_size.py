"""
app/api/data_size.py
─────────────────────
Routes:
  GET /api/training-data-size    – count rows in the training table
  GET /api/validation-data-size  – count rows in the validation table

Both endpoints accept the same parameters:
  campaign_id, bundle_id, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.dashboard import DataSizeResponse
from app.models.requests import DataSizeRequest
from app.services.data_size_service import DataSizeService
from app.services.athena_service import AthenaQueryError, AthenaTimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()
_service = DataSizeService()


def _parse_data_size_params(
    campaign_id: str = Query(..., description="Campaign ID, e.g. 6765"),
    bundle_id: str = Query(..., description="Bundle ID, e.g. com.grofers.customerapp"),
    start_date: date = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: date = Query(..., description="End date in YYYY-MM-DD format"),
) -> DataSizeRequest:
    """Dependency: parse and validate all query parameters in one step."""
    try:
        return DataSizeRequest(
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/training-data-size",
    response_model=DataSizeResponse,
    summary="Get training dataset row count",
    description=(
        "Returns the number of rows in the training dataset table for the given "
        "campaign, bundle, and date range. Used to display 'Training Data: X rows' "
        "on the dashboard."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "campaign_id": "6765",
                        "bundle_id": "com.grofers.customerapp",
                        "size": 125430,
                        "start_date": "2026-09-01",
                        "end_date": "2026-09-25",
                    }
                }
            }
        },
        400: {"description": "Invalid date range"},
        500: {"description": "Athena query error"},
    },
)
def get_training_data_size(params: DataSizeRequest = Depends(_parse_data_size_params)) -> DataSizeResponse:
    logger.info(
        "GET /api/training-data-size | campaign=%s bundle=%s range=%s→%s",
        params.campaign_id,
        params.bundle_id,
        params.start_date,
        params.end_date,
    )
    try:
        size = _service.get_training_size(
            campaign_id=params.campaign_id,
            bundle_id=params.bundle_id,
            start_date=params.start_date,
            end_date=params.end_date,
        )
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout for training size: %s", exc)
        raise HTTPException(status_code=504, detail="Athena query timed out. Try a shorter date range.")
    except AthenaQueryError as exc:
        logger.error("Athena error for training size: %s", exc)
        raise HTTPException(status_code=500, detail=f"Athena query failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected error for training size: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return DataSizeResponse(
        campaign_id=params.campaign_id,
        bundle_id=params.bundle_id,
        size=size,
        start_date=params.start_date,
        end_date=params.end_date,
    )


@router.get(
    "/validation-data-size",
    response_model=DataSizeResponse,
    summary="Get validation dataset row count",
    description=(
        "Returns the number of rows in the validation dataset table for the given "
        "campaign, bundle, and date range. Used to display 'Validation Data: X rows' "
        "on the dashboard."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "campaign_id": "6765",
                        "bundle_id": "com.grofers.customerapp",
                        "size": 31250,
                        "start_date": "2026-09-26",
                        "end_date": "2026-09-29",
                    }
                }
            }
        },
        400: {"description": "Invalid date range"},
        500: {"description": "Athena query error"},
    },
)
def get_validation_data_size(params: DataSizeRequest = Depends(_parse_data_size_params)) -> DataSizeResponse:
    logger.info(
        "GET /api/validation-data-size | campaign=%s bundle=%s range=%s→%s",
        params.campaign_id,
        params.bundle_id,
        params.start_date,
        params.end_date,
    )
    try:
        size = _service.get_validation_size(
            campaign_id=params.campaign_id,
            bundle_id=params.bundle_id,
            start_date=params.start_date,
            end_date=params.end_date,
        )
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout for validation size: %s", exc)
        raise HTTPException(status_code=504, detail="Athena query timed out. Try a shorter date range.")
    except AthenaQueryError as exc:
        logger.error("Athena error for validation size: %s", exc)
        raise HTTPException(status_code=500, detail=f"Athena query failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected error for validation size: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return DataSizeResponse(
        campaign_id=params.campaign_id,
        bundle_id=params.bundle_id,
        size=size,
        start_date=params.start_date,
        end_date=params.end_date,
    )
