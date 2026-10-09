"""
app/services/training_data_service.py
──────────────────────────────────────
Counts rows in training (train_final) and validation (val_final) Parquet
datasets stored in S3, using Athena as the query engine.

S3 Path Structure
─────────────────
  s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/
      {bundle_name}/
          train_final/    ← Parquet files (training set)
          val_final/      ← Parquet files (validation set)

bundle_name is the SHORT name from the model's BUNDLES list
(e.g. "meesho", not "com.meesho.supply").

Approach
─────────
For each bundle in the model's BUNDLES list:
  1. Create (or REPLACE) a temporary Athena external table pointing to the S3 path
  2. Run  SELECT COUNT(*) FROM <temp_table>
  3. Drop the temporary table
  4. Return row count per bundle + grand total

This avoids downloading any Parquet data — Athena reads directly from S3.
Results are cached per model_timestamp for CACHE_TTL seconds.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config.settings import get_settings
from app.services.athena_service import AthenaService

logger = logging.getLogger(__name__)

# ─── S3 constants ─────────────────────────────────────────────────────────────
S3_BUCKET = "mobavenue-simplismart-aws-s3-apse-sg"
TRAINING_DATA_PREFIX = "rtb/data/training_data"

# Cache TTL in seconds
_CACHE_TTL = 300


@dataclass
class SplitStats:
    row_count: int = 0
    min_date: str = ""
    max_date: str = ""
    label_1_count: int = 0
    label_0_count: int = 0

@dataclass
class BundleDataCount:
    bundle_name: str          # short name, e.g. "meesho"
    train_rows: int
    val_rows: int
    train_stats: SplitStats = field(default_factory=SplitStats)
    val_stats: SplitStats = field(default_factory=SplitStats)


@dataclass
class DatasetCounts:
    model_timestamp: str
    bundles: List[BundleDataCount] = field(default_factory=list)
    total_train_rows: int = 0
    total_val_rows: int = 0


class TrainingDataService:
    """
    Queries row counts for train_final and val_final Parquet datasets
    on S3 using Athena external tables.

    One Athena query per bundle per split (train / val).
    Results are cached to avoid redundant queries.
    """

    # Athena database to use for temp tables (must exist)
    _TEMP_DB = "default"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._athena = AthenaService()
        # Cache: key = (model_timestamp, bundle_name, split) → row count
        self._cache: Dict[str, int] = {}
        self._cache_time: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def get_counts_for_model(
        self,
        model_timestamp: str,
        bundle_names: List[str],
    ) -> DatasetCounts:
        """
        Returns train + val row counts for every bundle in bundle_names.

        Parameters
        ──────────
        model_timestamp : str
            Model timestamp string, e.g. "20260919_070055".
            Used for cache keying only (S3 path does NOT include timestamp).
        bundle_names : list[str]
            Short bundle names from feature_config.pkl BUNDLES list,
            e.g. ["meesho", "grofers", "licious"].

        Returns
        ───────
        DatasetCounts with per-bundle and grand total counts.
        """
        now = time.monotonic()
        cache_key_prefix = model_timestamp

        # Check if we have a fully cached result for this timestamp
        cache_meta_key = f"{cache_key_prefix}::meta"
        if cache_meta_key in self._cache and (now - self._cache_time) < _CACHE_TTL:
            logger.info("TrainingDataService cache HIT | timestamp=%s", model_timestamp)
            return self._build_result_from_cache(model_timestamp, bundle_names, cache_key_prefix)

        logger.info(
            "TrainingDataService | Counting rows for %d bundles | timestamp=%s",
            len(bundle_names),
            model_timestamp,
        )

        bundle_counts: List[BundleDataCount] = []
        for bundle_name in bundle_names:
            train_stats = self._count_rows(
                bundle_name=bundle_name,
                split="train_final",
                cache_prefix=cache_key_prefix,
            )
            val_stats = self._count_rows(
                bundle_name=bundle_name,
                split="val_final",
                cache_prefix=cache_key_prefix,
            )
            bundle_counts.append(
                BundleDataCount(
                    bundle_name=bundle_name,
                    train_rows=train_stats.row_count,
                    val_rows=val_stats.row_count,
                    train_stats=train_stats,
                    val_stats=val_stats,
                )
            )
            logger.info(
                "  bundle=%s  train=%d  val=%d", bundle_name, train_stats.row_count, val_stats.row_count
            )

        self._cache[cache_meta_key] = 1
        self._cache_time = now

        total_train = sum(b.train_rows for b in bundle_counts)
        total_val = sum(b.val_rows for b in bundle_counts)

        logger.info(
            "TrainingDataService DONE | total_train=%d total_val=%d",
            total_train,
            total_val,
        )

        return DatasetCounts(
            model_timestamp=model_timestamp,
            bundles=bundle_counts,
            total_train_rows=total_train,
            total_val_rows=total_val,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _s3_path(self, bundle_name: str, split: str) -> str:
        """Return the S3 URI for a bundle/split folder."""
        return f"s3://{S3_BUCKET}/{TRAINING_DATA_PREFIX}/{bundle_name}/{split}/"

    def _table_name(self, bundle_name: str, split: str) -> str:
        """Return a safe Athena table name for a bundle/split combo."""
        safe = bundle_name.replace(".", "_").replace("-", "_").lower()
        return f"tmp_ml_dash_{safe}_{split}"

    def _count_rows(
        self,
        bundle_name: str,
        split: str,   # "train_final" or "val_final"
        cache_prefix: str,
    ) -> SplitStats:
        cache_key = f"{cache_prefix}::{bundle_name}::{split}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        s3_path = self._s3_path(bundle_name, split)
        table_name = self._table_name(bundle_name, split)
        database = self._settings.athena_database

        # ── Step 1: Create external table pointing to S3 Parquet ─────────
        create_sql = f"""
CREATE EXTERNAL TABLE IF NOT EXISTS `{database}`.`{table_name}` (
    last_seen_date STRING,
    label INT
)
STORED AS PARQUET
LOCATION '{s3_path}'
""".strip()

        # ── Step 2: Count rows ────────────────────────────────────────────
        count_sql = f'SELECT COUNT(*) AS row_count, MIN(last_seen_date) as min_date, MAX(last_seen_date) as max_date, CAST(SUM(label) AS INTEGER) as label_sum FROM "{database}"."{table_name}"'

        # ── Step 3: Drop temp table (best effort) ─────────────────────────
        drop_sql = f'DROP TABLE IF EXISTS "{database}"."{table_name}"'

        logger.info(
            "Counting rows | bundle=%s split=%s s3=%s",
            bundle_name,
            split,
            s3_path,
        )

        stats = SplitStats()
        try:
            self._athena.run(create_sql)
            rows = self._athena.run(count_sql)
            if rows:
                stats.row_count = int(rows[0].get("row_count", 0) or 0)
                stats.min_date = str(rows[0].get("min_date", ""))
                stats.max_date = str(rows[0].get("max_date", ""))
                stats.label_1_count = int(rows[0].get("label_sum", 0) or 0)
                stats.label_0_count = stats.row_count - stats.label_1_count
        except Exception as exc:
            logger.error(
                "Failed to count rows for bundle=%s split=%s: %s",
                bundle_name,
                split,
                exc,
            )
        finally:
            try:
                self._athena.run(drop_sql)
            except Exception:
                pass  # best-effort cleanup

        self._cache[cache_key] = stats
        return stats

    def _build_result_from_cache(
        self,
        model_timestamp: str,
        bundle_names: List[str],
        cache_prefix: str,
    ) -> DatasetCounts:
        bundle_counts = []
        for bundle_name in bundle_names:
            train_key = f"{cache_prefix}::{bundle_name}::train_final"
            val_key = f"{cache_prefix}::{bundle_name}::val_final"
            train_stats = self._cache.get(train_key, SplitStats())
            val_stats = self._cache.get(val_key, SplitStats())
            bundle_counts.append(
                BundleDataCount(
                    bundle_name=bundle_name,
                    train_rows=train_stats.row_count,
                    val_rows=val_stats.row_count,
                    train_stats=train_stats,
                    val_stats=val_stats,
                )
            )
        return DatasetCounts(
            model_timestamp=model_timestamp,
            bundles=bundle_counts,
            total_train_rows=sum(b.train_rows for b in bundle_counts),
            total_val_rows=sum(b.val_rows for b in bundle_counts),
        )
