"""
app/api/suppression.py
───────────────────────
Route: GET /api/suppression

Performs the suppression check:
  Find devices that received an impression for a campaign on a given date
  AND also appeared in organic90 for the selected bundle before that date.

The result includes:
  - total_payload_devices
  - suppressed_devices
  - suppression_rate  (as a percentage)
  - status            (PASS / FAIL)
  - formula           (for the "Show Formula" toggle in the UI)
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.models.dashboard import SuppressionResponse
from app.models.requests import SuppressionRequest
from app.services.suppression_service import SuppressionService
from app.services.athena_service import AthenaQueryError, AthenaTimeoutError
from app.utils.formulas import suppression_rate_formula

logger = logging.getLogger(__name__)
router = APIRouter()
_service = SuppressionService()


@router.get(
    "/suppression",
    response_model=SuppressionResponse,
    summary="Run suppression check for a campaign on a given date",
    description=(
        "Finds devices that: (1) received an impression for the campaign on `date`, "
        "AND (2) appeared in organic90 for the bundle before `date`. "
        "Returns suppressed device count, total payload devices, suppression rate, "
        "PASS/FAIL status, and formula metadata for the UI toggle."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "campaign_id": "6765",
                        "bundle_id": "com.grofers.customerapp",
                        "check_date": "2026-09-29",
                        "total_payload_devices": 25000,
                        "suppressed_devices": 1250,
                        "suppression_rate": 5.0,
                        "status": "PASS",
                        "formula": {
                            "name": "Suppression Rate",
                            "expression": "(suppressed_devices / total_payload_devices) * 100",
                            "numerator": "suppressed_devices",
                            "denominator": "total_payload_devices",
                            "numerator_value": 1250,
                            "denominator_value": 25000,
                        },
                    }
                }
            }
        },
        422: {"description": "Validation error – missing or invalid parameters"},
        504: {"description": "Athena query timed out"},
        500: {"description": "Athena or server error"},
    },
)
def run_suppression_check(
    campaign_id: str = Query(..., description="Campaign ID, e.g. 6765"),
    bundle_id: str = Query(..., description="Bundle ID, e.g. com.grofers.customerapp"),
    date: date = Query(..., description="Check date in YYYY-MM-DD format"),
) -> SuppressionResponse:
    logger.info(
        "GET /api/suppression | campaign=%s bundle=%s date=%s",
        campaign_id,
        bundle_id,
        date,
    )

    # Validate via Pydantic model
    try:
        params = SuppressionRequest(
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            date=date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        result = _service.run_suppression_check(
            campaign_id=params.campaign_id,
            bundle_id=params.bundle_id,
            check_date=params.date,
        )
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout for suppression check: %s", exc)
        raise HTTPException(status_code=504, detail="Athena query timed out.")
    except AthenaQueryError as exc:
        logger.error("Athena error for suppression check: %s", exc)
        raise HTTPException(status_code=500, detail=f"Athena query failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected error for suppression check: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    total = result["total_payload_devices"]
    suppressed = result["suppressed_devices"]
    rate = round((suppressed / total) * 100, 4) if total > 0 else 0.0
    status = "PASS" if rate < 10.0 else "FAIL"

    if total == 0:
        raise HTTPException(
            status_code=404,
            detail="No payload devices found for the selected campaign and date.",
        )

    return SuppressionResponse(
        campaign_id=params.campaign_id,
        bundle_id=params.bundle_id,
        check_date=params.date,
        total_payload_devices=total,
        suppressed_devices=suppressed,
        suppression_rate=rate,
        status=status,
        formula=suppression_rate_formula(suppressed, total),
    )
