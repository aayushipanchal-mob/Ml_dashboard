"""
app/services/data_size_service.py
──────────────────────────────────
Queries Athena for training / validation dataset row counts.

SQL uses partition pruning on event_date (formatted as YYYYMMDD strings
to match the partition scheme used in existing Athena tables).
No raw user input is ever concatenated into SQL; Pydantic validated
date / string objects are formatted here.
"""

from __future__ import annotations

import logging
from datetime import date

from app.config.settings import get_settings
from app.services.athena_service import AthenaService

logger = logging.getLogger(__name__)


def _fmt_date(d: date) -> str:
    """Return a date as YYYYMMDD string for Athena partition filters."""
    return d.strftime("%Y%m%d")


def _generate_date_list(start: date, end: date) -> list[str]:
    """
    Build the list of YYYYMMDD strings between start and end (inclusive).
    This is used in SQL IN (…) clauses to exploit partition pruning.
    """
    from datetime import timedelta

    result = []
    current = start
    while current <= end:
        result.append(f"'{_fmt_date(current)}'")
        current += timedelta(days=1)
    return result


class DataSizeService:
    """
    Returns the number of rows in the training or validation table
    within a given date range for a specific campaign + bundle.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._athena = AthenaService()

    def get_training_size(
        self,
        campaign_id: str,
        bundle_id: str,
        start_date: date,
        end_date: date,
    ) -> int:
        logger.info(
            "Training size query | campaign=%s bundle=%s range=%s→%s",
            campaign_id,
            bundle_id,
            start_date,
            end_date,
        )
        return self._count_rows(
            table=self._settings.training_table,
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_validation_size(
        self,
        campaign_id: str,
        bundle_id: str,
        start_date: date,
        end_date: date,
    ) -> int:
        logger.info(
            "Validation size query | campaign=%s bundle=%s range=%s→%s",
            campaign_id,
            bundle_id,
            start_date,
            end_date,
        )
        return self._count_rows(
            table=self._settings.validation_table,
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            start_date=start_date,
            end_date=end_date,
        )

    def _count_rows(
        self,
        table: str,
        campaign_id: str,
        bundle_id: str,
        start_date: date,
        end_date: date,
    ) -> int:
        raw_dates = [d.strip("'") for d in _generate_date_list(start_date, end_date)]
        self._athena.ensure_partitions(table, raw_dates)

        date_list = ", ".join(_generate_date_list(start_date, end_date))
        # campaign_id and bundle_id are already validated non-empty strings
        # by Pydantic; we further escape single quotes to prevent injection.
        safe_campaign = campaign_id.replace("'", "''")
        safe_bundle = bundle_id.replace("'", "''")

        sql = f"""
SELECT COUNT(*) AS row_count
FROM {table}
WHERE event_date IN ({date_list})
  AND campaign_id = '{safe_campaign}'
  AND bundle_id   = '{safe_bundle}'
"""
        rows = self._athena.run(sql.strip())
        if not rows:
            return 0
        try:
            return int(rows[0].get("row_count", 0) or 0)
        except (ValueError, TypeError):
            return 0
