"""
app/services/cr_service.py
──────────────────────────
Conversion Rate (CR) check service.

The query is a direct translation of the hand-written Athena SQL into a
fully dynamic form.  All hard-coded campaign IDs, bundle IDs, and dates
are replaced with parameters derived from the validated API request.

Key optimisations vs. the original query
─────────────────────────────────────────
• event_date filters are applied as early as possible (inside each CTE)
  to exploit Athena partition pruning.
• The campaign_bundle_mapping CTE contains only the single requested
  campaign + bundle pair – this avoids joining against a static list of
  all campaigns and only scans relevant partitions.
• organic date list extends one extra day beyond end_date to capture
  installs that occur within 24 h of the last click day (matching the
  original query's organic date range).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from app.config.settings import get_settings
from app.services.athena_service import AthenaService

logger = logging.getLogger(__name__)


def _fmt_date(d: date) -> str:
    return d.strftime("%Y%m%d")


def _date_in_list(start: date, end: date) -> str:
    """Return a SQL IN (…) literal for dates from start to end inclusive."""
    dates = []
    cur = start
    while cur <= end:
        dates.append(f"'{_fmt_date(cur)}'")
        cur += timedelta(days=1)
    return ", ".join(dates)


class CRService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._athena = AthenaService()

    def run_cr_check(
        self,
        campaign_id: str,
        bundle_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of daily CR rows:
            event_date, total_clicked_devices, total_organic_installs,
            intersected_devices_24h, conversion_rate_24h
        """
        safe_campaign = campaign_id.replace("'", "''")
        safe_bundle = bundle_id.replace("'", "''")

        click_dates = _date_in_list(start_date, end_date)
        # organic window extends 1 day past end to catch 24-h post-click installs
        organic_end = end_date + timedelta(days=1)
        organic_dates = _date_in_list(start_date, organic_end)

        logger.info(
            "CR query | campaign=%s bundle=%s range=%s→%s",
            campaign_id,
            bundle_id,
            start_date,
            end_date,
        )

        impressions_table = self._settings.impressions_table
        clicks_table = self._settings.clicks_table
        organic_table = self._settings.organic_table

        # ── Step 0: Ensure partitions exist ────────────────────────────────
        # Build raw list of date strings for partition loading
        click_dates_list = []
        cur = start_date
        while cur <= end_date:
            click_dates_list.append(_fmt_date(cur))
            cur += timedelta(days=1)
            
        organic_dates_list = []
        cur = start_date
        while cur <= organic_end:
            organic_dates_list.append(_fmt_date(cur))
            cur += timedelta(days=1)

        self._athena.ensure_partitions(impressions_table, click_dates_list)
        self._athena.ensure_partitions(clicks_table, click_dates_list)
        self._athena.ensure_partitions(organic_table, organic_dates_list)

        sql = f"""
WITH campaign_bundle_mapping AS (
    SELECT '{safe_campaign}' AS campaign_id,
           '{safe_bundle}'   AS bundle_id
),

clicked_devices AS (
    SELECT
        m.bundle_id,
        m.campaign_id,
        c.event_date,
        i.device_id,
        c.timestamp AS click_timestamp
    FROM {impressions_table} i
    INNER JOIN {clicks_table} c
        ON i.auction_id = c.auction_id
       AND c.event_date IN ({click_dates})
    INNER JOIN campaign_bundle_mapping m
        ON c.campaign_id = m.campaign_id
    WHERE c.click = 1
      AND i.event_date IN ({click_dates})
      AND i.campaign_id = m.campaign_id
      AND i.device_id IS NOT NULL
      AND TRIM(i.device_id) <> ''
),

daily_clicks_summary AS (
    SELECT
        bundle_id,
        campaign_id,
        event_date,
        COUNT(DISTINCT device_id) AS total_clicked_devices
    FROM clicked_devices
    GROUP BY bundle_id, campaign_id, event_date
),

daily_organic AS (
    SELECT
        m.bundle_id,
        m.campaign_id,
        o.event_date,
        COUNT(DISTINCT o.device_id) AS total_organic_installs
    FROM {organic_table} o
    INNER JOIN campaign_bundle_mapping m
        ON o.bundle_id = m.bundle_id
    WHERE o.event_type = 'install'
      AND o.event_date IN ({organic_dates})
    GROUP BY m.bundle_id, m.campaign_id, o.event_date
),

daily_24h_intersection AS (
    SELECT
        cd.bundle_id,
        cd.campaign_id,
        cd.event_date,
        COUNT(DISTINCT cd.device_id) AS intersected_devices_24h
    FROM clicked_devices cd
    INNER JOIN {organic_table} o
        ON  cd.device_id = o.device_id
        AND cd.bundle_id = o.bundle_id
    WHERE o.event_type = 'install'
      AND o.timestamp >= cd.click_timestamp
      AND o.timestamp <= (cd.click_timestamp + 86400000)
    GROUP BY cd.bundle_id, cd.campaign_id, cd.event_date
)

SELECT
    COALESCE(dc.bundle_id,   do.bundle_id)   AS bundle_id,
    COALESCE(dc.campaign_id, do.campaign_id) AS campaign_id,
    COALESCE(dc.event_date,  do.event_date)  AS event_date,
    COALESCE(dc.total_clicked_devices,  0)   AS total_clicked_devices,
    COALESCE(do.total_organic_installs, 0)   AS total_organic_installs,
    COALESCE(di.intersected_devices_24h, 0)  AS intersected_devices_24h,
    ROUND(
        (COALESCE(di.intersected_devices_24h, 0) * 100.0)
        / NULLIF(COALESCE(dc.total_clicked_devices, 0), 0),
        2
    ) AS conversion_rate_24h
FROM daily_clicks_summary dc
FULL OUTER JOIN daily_organic do
    ON  dc.bundle_id   = do.bundle_id
    AND dc.campaign_id = do.campaign_id
    AND dc.event_date  = do.event_date
LEFT JOIN daily_24h_intersection di
    ON  dc.bundle_id   = di.bundle_id
    AND dc.campaign_id = di.campaign_id
    AND dc.event_date  = di.event_date
ORDER BY event_date DESC
""".strip()

        rows = self._athena.run(sql)
        logger.info("CR query returned %d rows", len(rows))

        # ── normalise types ────────────────────────────────────────────────
        result = []
        for row in rows:
            result.append(
                {
                    "event_date": row.get("event_date", ""),
                    "total_clicked_devices": int(row.get("total_clicked_devices") or 0),
                    "total_organic_installs": int(row.get("total_organic_installs") or 0),
                    "intersected_devices_24h": int(row.get("intersected_devices_24h") or 0),
                    "conversion_rate_24h": float(row.get("conversion_rate_24h") or 0.0),
                }
            )
        return result
