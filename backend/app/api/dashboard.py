"""
app/api/dashboard.py
─────────────────────
Routes:
  GET  /api/dashboard         – combined dashboard via query parameters
  POST /api/dashboard/check   – same but accepts a JSON request body
                                (useful for Postman / programmatic callers)

Both routes call DashboardService which orchestrates all four sub-services
and returns a single combined response.
"""

from __future__ import annotations

import logging
from datetime import date

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.dashboard import DashboardResponse
from app.models.requests import DashboardRequest
from app.services.dashboard_service import DashboardService
from app.services.athena_service import AthenaQueryError, AthenaTimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()
_service = DashboardService()


# ─────────────────────────────────────────────────────────────────────────────
# Shared handler — called by both routes below
# ─────────────────────────────────────────────────────────────────────────────

def _run_dashboard(params: DashboardRequest) -> DashboardResponse:
    logger.info(
        "Dashboard check | campaign=%s bundle=%s input_date=%s "
        "training=%s→%s validation=%s→%s",
        params.campaign_id,
        params.bundle_id,
        params.input_date,
        params.training_start_date,
        params.training_end_date,
        params.validation_start_date,
        params.validation_end_date,
        params.model_timestamp,
    )
    try:
        return _service.get_dashboard(
            campaign_id=params.campaign_id,
            bundle_id=params.bundle_id,
            input_date=params.input_date,
            training_start_date=params.training_start_date,
            training_end_date=params.training_end_date,
            validation_start_date=params.validation_start_date,
            validation_end_date=params.validation_end_date,
            model_timestamp=params.model_timestamp,
        )
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout in dashboard: %s", exc)
        raise HTTPException(
            status_code=504,
            detail="One or more Athena queries timed out. Try a shorter date range.",
        )
    except AthenaQueryError as exc:
        logger.error("Athena error in dashboard: %s", exc)
        raise HTTPException(status_code=500, detail=f"Athena query failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected error in dashboard: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/dashboard
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Combined dashboard check (GET)",
    description=(
        "Runs all checks (training size, validation size, suppression, CR) "
        "for the given campaign, bundle, and date ranges in a single call. "
        "Results are cached for the configured TTL (default 5 minutes). "
        "Use POST /api/dashboard/check if you prefer sending a JSON body."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "input": {
                            "campaign_id": "6765",
                            "bundle_id": "com.grofers.customerapp",
                            "input_date": "2026-09-29",
                        },
                        "training": {"size": 125430, "start_date": "2026-09-01", "end_date": "2026-09-25"},
                        "validation": {"size": 31250, "start_date": "2026-09-26", "end_date": "2026-09-29"},
                        "suppression": {
                            "total_payload_devices": 25000,
                            "suppressed_devices": 1250,
                            "suppression_rate": 5.0,
                            "status": "PASS",
                            "formula": {
                                "name": "Suppression Rate",
                                "expression": "(suppressed_devices / total_payload_devices) * 100",
                                "numerator": "suppressed_devices",
                                "denominator": "total_payload_devices",
                                "numerator_value": 1250.0,
                                "denominator_value": 25000.0,
                            },
                        },
                        "cr": {
                            "total_clicked_devices": 31500,
                            "total_organic_installs": 420,
                            "intersected_devices_24h": 123,
                            "conversion_rate_24h": 0.39,
                            "daily_trend": [],
                            "formula": {
                                "name": "24-Hour Conversion Rate",
                                "expression": "(intersected_devices_24h / total_clicked_devices) * 100",
                                "numerator": "intersected_devices_24h",
                                "denominator": "total_clicked_devices",
                            },
                        },
                    }
                }
            }
        },
        422: {"description": "Validation error"},
        504: {"description": "Athena query timed out"},
        500: {"description": "Server or Athena error"},
    },
)
def get_dashboard(
    campaign_id: str = Query(..., description="Campaign ID, e.g. 6765"),
    bundle_id: str = Query(..., description="Bundle ID, e.g. com.grofers.customerapp"),
    input_date: date = Query(..., description="Check/input date in YYYY-MM-DD format"),
    training_start_date: Optional[date] = Query(None, description="Training data start date"),
    training_end_date: Optional[date] = Query(None, description="Training data end date"),
    validation_start_date: Optional[date] = Query(None, description="Validation data start date"),
    validation_end_date: Optional[date] = Query(None, description="Validation data end date"),
    model_timestamp: str = Query(None, description="Optional specific model timestamp"),
) -> DashboardResponse:
    try:
        params = DashboardRequest(
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            input_date=input_date,
            training_start_date=training_start_date,
            training_end_date=training_end_date,
            validation_start_date=validation_start_date,
            validation_end_date=validation_end_date,
            model_timestamp=model_timestamp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return _run_dashboard(params)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/dashboard/check  (JSON body alternative)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/dashboard/check",
    response_model=DashboardResponse,
    summary="Combined dashboard check (POST with JSON body)",
    description=(
        "Same as GET /api/dashboard but accepts all parameters in a JSON request body. "
        "Useful when calling from scripts or Postman where a body is preferred over query strings."
    ),
)
def post_dashboard_check(params: DashboardRequest) -> DashboardResponse:
    return _run_dashboard(params)
