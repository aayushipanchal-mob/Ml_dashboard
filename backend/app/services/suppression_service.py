"""
app/services/suppression_service.py
────────────────────────────────────
Suppression check logic.

Logic
─────
Find devices that:
  1. Received an impression for the selected campaign on the selected date.
  2. Also appeared in organic90 for the selected bundle BEFORE the selected date.

This is the set intersection:
    impression_devices  ∩  previously_organic_devices

The query is split into three separate Athena calls so each one can
individually exploit its partition column (event_date):

  Q1 – Count of distinct impression devices (total impression devices)
  Q2 – The INTERSECT query to count suppressed devices

Both queries are partition-pruned using event_date IN (…).
"""

from __future__ import annotations

import logging
import csv
import codecs
import boto3
from datetime import date, timedelta
from typing import Dict, Set

from app.config.settings import get_settings
from app.services.athena_service import AthenaService

logger = logging.getLogger(__name__)

# Global In-Memory Cache for Organic Devices
# Structure: { bundle_id: { event_date_str: set(device_ids) } }
# This eliminates redundant 90-day Athena scans across consecutive dashboard checks!
_ORGANIC_CACHE: Dict[str, Dict[str, Set[str]]] = {}


def _fmt_date(d: date) -> str:
    return d.strftime("%Y%m%d")


class SuppressionService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._athena = AthenaService()

    def _load_missing_organic_dates(self, safe_bundle: str, missing_dates: list[str]):
        if not missing_dates:
            return
            
        logger.info("Downloading %d missing organic dates into local cache...", len(missing_dates))
        dates_sql = ", ".join(f"'{d}'" for d in missing_dates)
        sql = f"""
            SELECT event_date, TRIM(device_id) as device_id
            FROM {self._settings.organic90_table}
            WHERE bundle_id = '{safe_bundle}'
              AND event_date IN ({dates_sql})
              AND event_type = 'install'
              AND device_id IS NOT NULL
        """
        
        exec_id = self._athena.execute_and_wait(sql)
        output_loc = self._athena.get_output_location(exec_id)
        
        if not output_loc.startswith("s3://"):
            logger.warning("Query %s did not return an S3 URI.", exec_id)
            return
            
        parts = output_loc[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1]
        
        s3 = boto3.client('s3', region_name=self._settings.aws_region)
        resp = s3.get_object(Bucket=bucket, Key=key)
        
        bundle_cache = _ORGANIC_CACHE.setdefault(safe_bundle, {})
        for d in missing_dates:
            bundle_cache[d] = set()
            
        reader = csv.DictReader(codecs.getreader("utf-8")(resp['Body']))
        count = 0
        for row in reader:
            d = row.get('event_date')
            did = row.get('device_id')
            if d and did:
                bundle_cache[d].add(did)
                count += 1
        logger.info("Loaded %d organic devices into local cache.", count)

    def run_suppression_check(
        self,
        campaign_id: str,
        bundle_id: str,
        check_date: date,
    ) -> dict:
        """
        Returns a dict with:
            total_payload_devices     – int
            suppressed_devices        – int
        """
        safe_campaign = campaign_id.replace("'", "''")
        safe_bundle = bundle_id.replace("'", "''")
        date_str = _fmt_date(check_date)

        logger.info(
            "Suppression check | campaign=%s bundle=%s date=%s",
            campaign_id,
            bundle_id,
            date_str,
        )

        # ── Step 1: Fetch payload devices for the specific check_date ──
        self._athena.ensure_partitions('ml_dashboard.payload', [date_str])
        
        payload_sql = f"""
            SELECT DISTINCT TRIM(deviceid) as device_id
            FROM ml_dashboard.payload
            WHERE event_date = '{date_str}'
              AND campaignid = '{safe_campaign}'
              AND deviceid IS NOT NULL
              AND TRIM(deviceid) <> ''
        """
        payload_rows = self._athena.run(payload_sql)
        payload_devices = {r['device_id'] for r in payload_rows if r.get('device_id')}
        total_payload = len(payload_devices)
        
        if total_payload == 0:
            return {"total_payload_devices": 0, "suppressed_devices": 0}

        # ── Step 2: Ensure 90-day organic devices are locally cached ──
        organic_dates = [
            _fmt_date(check_date - timedelta(days=i)) for i in range(1, 91)
        ]
        
        bundle_cache = _ORGANIC_CACHE.get(safe_bundle, {})
        missing_dates = [d for d in organic_dates if d not in bundle_cache]
        
        if missing_dates:
            self._athena.ensure_partitions(self._settings.organic90_table, missing_dates)
            self._load_missing_organic_dates(safe_bundle, missing_dates)
            bundle_cache = _ORGANIC_CACHE[safe_bundle]

        # ── Step 3: Fast Local Intersection ──
        organic_devices = set()
        for d in organic_dates:
            organic_devices.update(bundle_cache.get(d, set()))
            
        suppressed_devices = payload_devices.intersection(organic_devices)
        suppressed = len(suppressed_devices)

        logger.info(
            "Suppression result | total=%d suppressed=%d", total_payload, suppressed
        )
        return {
            "total_payload_devices": total_payload,
            "suppressed_devices": suppressed,
        }
