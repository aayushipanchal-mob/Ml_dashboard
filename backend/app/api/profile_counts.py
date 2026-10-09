import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.athena_service import AthenaService, AthenaQueryError, AthenaTimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()
_athena_svc = AthenaService()

from typing import Optional

class RegionCounts(BaseModel):
    total: int = 0
    delta: int = 0
    purge: int = 0
    upload_audit: int = 0

class ProfileCountResponse(BaseModel):
    country: str
    india: Optional[RegionCounts] = None
    usa: Optional[RegionCounts] = None

def parse_region_counts(rows) -> RegionCounts:
    rc = RegionCounts()
    if not rows:
        return rc
    for row in rows:
        feed = row.get("feed")
        val = int(row.get("rows", row.get("_col1", 0)))
        if feed == "profiles_total":
            rc.total = val
        elif feed == "delta_upsert":
            rc.delta = val
        elif feed == "purge_deletes":
            rc.purge = val
        elif feed == "upload_audit":
            rc.upload_audit = val
    return rc

@router.get("/profile-counts", response_model=ProfileCountResponse, tags=["Profile Counts"])
def get_profile_counts(
    country: str = Query("india", description="Country for profile counts (india, usa, or both)")
) -> ProfileCountResponse:
    country = country.lower()
    
    india_sql = """
        SELECT 'profiles_total' AS feed, COUNT(*) AS rows FROM device_profiles_V1.global_device_profiles_V1
        UNION ALL SELECT 'delta_upsert',  COUNT(*) FROM device_profiles_V1.global_device_profiles_V1_delta
        UNION ALL SELECT 'purge_deletes', COUNT(*) FROM device_profiles_V1.global_device_profiles_V1_purge
        UNION ALL SELECT 'upload_audit',  COUNT(*) FROM device_profiles_V1.upload_audit
    """
    
    usa_sql = """
        SELECT 'profiles_total' AS feed, COUNT(*) AS rows FROM device_profiles_USA.global_device_profiles_USA
        UNION ALL SELECT 'delta_upsert',  COUNT(*) FROM device_profiles_USA.global_device_profiles_USA_delta
        UNION ALL SELECT 'purge_deletes', COUNT(*) FROM device_profiles_USA.global_device_profiles_USA_purge
        UNION ALL SELECT 'upload_audit',  COUNT(*) FROM device_profiles_USA.upload_audit
    """
    
    both_sql = """
        SELECT 'india' as region, 'profiles_total' AS feed, COUNT(*) AS rows FROM device_profiles_V1.global_device_profiles_V1
        UNION ALL SELECT 'india', 'delta_upsert',  COUNT(*) FROM device_profiles_V1.global_device_profiles_V1_delta
        UNION ALL SELECT 'india', 'purge_deletes', COUNT(*) FROM device_profiles_V1.global_device_profiles_V1_purge
        UNION ALL SELECT 'india', 'upload_audit',  COUNT(*) FROM device_profiles_V1.upload_audit
        UNION ALL SELECT 'usa', 'profiles_total', COUNT(*) FROM device_profiles_USA.global_device_profiles_USA
        UNION ALL SELECT 'usa', 'delta_upsert',  COUNT(*) FROM device_profiles_USA.global_device_profiles_USA_delta
        UNION ALL SELECT 'usa', 'purge_deletes', COUNT(*) FROM device_profiles_USA.global_device_profiles_USA_purge
        UNION ALL SELECT 'usa', 'upload_audit',  COUNT(*) FROM device_profiles_USA.upload_audit
    """
    
    try:
        resp = ProfileCountResponse(country=country)
        if country == "india":
            rows = _athena_svc.run(india_sql)
            resp.india = parse_region_counts(rows)
        elif country == "usa":
            rows = _athena_svc.run(usa_sql)
            resp.usa = parse_region_counts(rows)
        elif country == "both":
            rows = _athena_svc.run(both_sql)
            resp.india = parse_region_counts([r for r in rows if r.get('region') == 'india'])
            resp.usa = parse_region_counts([r for r in rows if r.get('region') == 'usa'])
        else:
            raise HTTPException(status_code=400, detail="Invalid country. Must be 'india', 'usa', or 'both'.")
            
        return resp
    except AthenaTimeoutError as exc:
        logger.error("Athena timeout: %s", exc)
        raise HTTPException(status_code=504, detail="Athena query timed out.")
    except AthenaQueryError as exc:
        logger.error("Athena error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")
