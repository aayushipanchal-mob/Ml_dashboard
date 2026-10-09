"""
app/api/cr.py
──────────────
Route: GET /api/cr

Runs the 24-hour Conversion Rate check for a campaign/bundle over a date range.

Returns daily rows with:
  - total_clicked_devices
  - total_organic_installs
  - intersected_devices_24h  (clicked AND installed within 24h of click)
  - conversion_rate_24h      (as a percentage)

Also returns formula metadata so the UI can render the "Show Formula" toggle.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.models.dashboard import CRResponse
from app.models.requests import CRRequest
from app.services.cr_service import CRService
from app.services.athena_service import AthenaQueryError, AthenaTimeoutError
from app.utils.formulas import cr_formula

logger = logging.getLogger(__name__)
router = APIRouter()
_service = CRService()


@router.get(
    "/cr",
    response_model=CRResponse,
    summary="Run 24-hour Conversion Rate check",
    description=(
        "Calculates the daily 24-hour Conversion Rate for a campaign and bundle "
        "over the specified date range. "
        "CR = (devices that clicked AND installed within 24h) / total clicked devices × 100. "
        "Returns daily rows and formula metadata for the UI toggle."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "campaign_id": "6765",
                        "bundle_id": "com.grofers.customerapp",
                        "start_date": "2026-09-27",
                        "end_date": "2026-09-29",
                        "data": [
                            {
                                "event_date": "20260929",
                                "total_clicked_devices": 31500,
                                "total_organic_installs": 420,
                                "intersected_devices_24h": 123,
                                "conversion_rate_24h": 0.39,
                            }
                        ],
                        "formula": {
                            "name": "24-Hour Conversion Rate",
                            "expression": "(intersected_devices_24h / total_clicked_devices) * 100",
                            "numerator": "intersected_devices_24h",
                            "denominator": "total_clicked_devices",
                        },
                    }
                }
            }
        },
        404: {"description": "No data found for the given parameters"},
        504: {"description": "Athena query timed out"},
        500: {"description": "Athena or server error"},
    },
)
def run_cr_check(
    campaign_id: str = Query(..., description="Campaign ID, e.g. 6765"),
    bundle_id: str = Query(..., description="Bundle ID, e.g. com.grofers.customerapp"),
    start_date: date = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: date = Query(..., description="End date in YYYY-MM-DD format"),
) -> CRResponse:
    logger.info(
        "GET /api/cr | campaign=%s bundle=%s range=%s→%s",
        campaign_id,
        bundle_id,
        start_date,
        end_date,
    )

    try:
        params = CRRequest(
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        rows_raw = _service.run_cr_check(
            campaign_id=params.campaign_id,
            bundle_id=params.bundle_id,
            start_date=params.start_date,
            end_date=params.end_date,
        )
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout for CR check: %s", exc)
        raise HTTPException(status_code=504, detail="Athena query timed out. Try a shorter date range.")
    except AthenaQueryError as exc:
        logger.error("Athena error for CR check: %s", exc)
        raise HTTPException(status_code=500, detail=f"Athena query failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected error for CR check: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if not rows_raw:
        raise HTTPException(
            status_code=404,
            detail="No CR data found for the selected campaign, bundle, and date range.",
        )

    # Aggregate totals for the formula metadata (use overall totals across all days)
    total_clicks = sum(r["total_clicked_devices"] for r in rows_raw)
    total_intersected = sum(r["intersected_devices_24h"] for r in rows_raw)

    return CRResponse(
        campaign_id=params.campaign_id,
        bundle_id=params.bundle_id,
        start_date=params.start_date,
        end_date=params.end_date,
        data=rows_raw,
        formula=cr_formula(total_intersected, total_clicks),
    )
