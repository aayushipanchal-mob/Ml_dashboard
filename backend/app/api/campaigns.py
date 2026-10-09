"""
app/api/campaigns.py
─────────────────────
Route: GET /api/campaigns

Returns the list of campaign_id → bundle_id mappings.
The frontend uses this to populate the Campaign ID and Bundle ID dropdowns.
"""

from __future__ import annotations

import logging

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.dashboard import CampaignsResponse
from app.services.campaigns_service import CampaignsService

logger = logging.getLogger(__name__)
router = APIRouter()
_service = CampaignsService()


@router.get(
    "/campaigns",
    response_model=CampaignsResponse,
    summary="List all campaign → bundle mappings",
    description=(
        "Returns all configured campaign ID to bundle ID mappings. "
        "Use this to populate the Campaign ID and Bundle ID dropdowns in the dashboard. "
        "To add/remove campaigns, edit the `campaigns.json` file — no code change needed."
    ),
    responses={
        200: {
            "description": "List of campaign mappings",
            "content": {
                "application/json": {
                    "example": {
                        "campaigns": [
                            {"campaign_id": "6765", "bundle_id": "com.grofers.customerapp"},
                            {"campaign_id": "7661", "bundle_id": "com.licious"},
                        ]
                    }
                }
            },
        }
    },
)
def list_campaigns(
    timestamp: Optional[str] = Query(None, description="Optional model timestamp")
) -> CampaignsResponse:
    logger.info("GET /api/campaigns – request received")
    try:
        mappings = _service.list_campaigns(timestamp)
    except Exception as exc:
        logger.error("Failed to load campaigns: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to load campaigns: {exc}")
    return CampaignsResponse(campaigns=mappings)
