"""
app/services/campaigns_service.py
──────────────────────────────────
Campaign → Bundle mapping service.

SOURCE OF TRUTH:
  1. Bundle IDs (short names) are fetched live from the latest model's 
     feature_config.pkl on S3.
  2. Campaign IDs and Full Bundle IDs are automatically extracted by scanning 
     the last 3 days of data in the Athena `impressions` table.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional

from cachetools import TTLCache, cached

from app.config.settings import get_settings
from app.models.dashboard import CampaignMapping
from app.services.athena_service import AthenaService

logger = logging.getLogger(__name__)

# Cache the campaign list for 1 hour to avoid repeated Athena queries
_campaigns_cache = TTLCache(maxsize=1, ttl=3600)


class CampaignsService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._athena = AthenaService()

    def list_campaigns(self, timestamp: Optional[str] = None) -> List[CampaignMapping]:
        """
        Returns the active campaign_id → bundle_id mappings.
        Uses the S3 model bundles as the base, and finds their matching
        Campaign IDs directly from recent Athena impressions data.
        """
        live_bundle_ids = self._try_get_live_bundles(timestamp)
        if not live_bundle_ids:
            logger.warning("No live bundles found in S3. Returning empty list.")
            return []

        return self._merge_with_athena_mappings(live_bundle_ids)

    def _try_get_live_bundles(self, timestamp: Optional[str]) -> Optional[List[str]]:
        try:
            from app.services.model_artifacts_service import ModelArtifactsService
            svc = ModelArtifactsService()
            if timestamp:
                info = svc._load_model_info(timestamp)
            else:
                info = svc.get_latest_model_info()
            logger.info("Live model bundles loaded | count=%d", len(info.bundle_ids))
            return info.bundle_ids
        except Exception as exc:
            logger.warning("Could not load live model bundles from S3: %s", exc)
            return None

    @cached(cache=_campaigns_cache)
    def _get_raw_athena_mappings(self) -> List[dict]:
        end_date = date.today()
        start_date = end_date - timedelta(days=2)
        
        dates_raw = []
        cur = start_date
        while cur <= end_date:
            dates_raw.append(cur.strftime("%Y%m%d"))
            cur += timedelta(days=1)
            
        self._athena.ensure_partitions(self._settings.impressions_table, dates_raw)
        
        dates_sql = ", ".join([f"'{d}'" for d in dates_raw])
        sql = f"""
        SELECT DISTINCT campaign_id, advertiser_bundle AS bundle_id
        FROM {self._settings.impressions_table}
        WHERE event_date IN ({dates_sql})
          AND campaign_id IS NOT NULL 
          AND advertiser_bundle IS NOT NULL
          AND TRIM(campaign_id) <> ''
          AND TRIM(advertiser_bundle) <> ''
        """
        
        logger.info("Fetching active campaign mappings from Athena over last 3 days...")
        return self._athena.run(sql)

    def _merge_with_athena_mappings(self, short_bundle_names: List[str]) -> List[CampaignMapping]:
        rows = self._get_raw_athena_mappings()
        
        mappings = []
        for short_name in short_bundle_names:
            matched_campaign = "unknown"
            matched_full_bundle = short_name
            
            for row in rows:
                full_b = str(row.get("bundle_id", ""))
                if short_name.lower() in full_b.lower():
                    matched_campaign = str(row.get("campaign_id", "unknown"))
                    matched_full_bundle = full_b
                    break
                    
            mappings.append(
                CampaignMapping(campaign_id=matched_campaign, bundle_id=matched_full_bundle)
            )

        logger.info(
            "Built %d campaign mappings (%d matched campaign IDs from Athena)",
            len(mappings),
            sum(1 for m in mappings if m.campaign_id != "unknown"),
        )
        return mappings
