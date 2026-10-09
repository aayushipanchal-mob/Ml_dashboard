"""
app/services/dashboard_service.py
──────────────────────────────────
Orchestrates the four sub-services to build the combined dashboard response.

Also implements a short-lived TTL cache keyed on the request parameters so
that re-running the same check within the configured window returns instantly
without re-querying Athena.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date
from typing import Optional

from cachetools import TTLCache

from app.config.settings import get_settings
from app.models.dashboard import (
    DashboardCR,
    DashboardInput,
    DashboardResponse,
    DashboardSuppression,
    DashboardTraining,
    DashboardValidation,
    CRDayRow,
)
from app.services.cr_service import CRService
from app.services.data_size_service import DataSizeService
from app.services.suppression_service import SuppressionService
from app.utils.formulas import cr_formula, suppression_rate_formula

logger = logging.getLogger(__name__)

# Maximum items in cache (each item ≈ one dashboard response)
_CACHE_MAX_SIZE = 128


class DashboardService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._data_size_svc = DataSizeService()
        self._suppression_svc = SuppressionService()
        self._cr_svc = CRService()

        self._cache: TTLCache = TTLCache(
            maxsize=_CACHE_MAX_SIZE,
            ttl=self._settings.cache_ttl_seconds or 1,  # 1s minimum so cache is always valid
        )

    def _cache_key(self, **kwargs) -> str:
        raw = json.dumps(kwargs, default=str, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get_dashboard(
        self,
        *,
        campaign_id: str,
        bundle_id: str,
        input_date: date,
        training_start_date: Optional[date] = None,
        training_end_date: Optional[date] = None,
        validation_start_date: Optional[date] = None,
        validation_end_date: Optional[date] = None,
        model_timestamp: Optional[str] = None,
        include_suppression: bool = False,
        include_cr: bool = False,
    ) -> DashboardResponse:
        cache_key = self._cache_key(
            campaign_id=campaign_id,
            bundle_id=bundle_id,
            input_date=str(input_date),
            training_start_date=str(training_start_date),
            training_end_date=str(training_end_date),
            validation_start_date=str(validation_start_date),
            validation_end_date=str(validation_end_date),
            model_timestamp=model_timestamp,
            include_suppression=include_suppression,
            include_cr=include_cr,
        )

        if self._settings.cache_ttl_seconds > 0 and cache_key in self._cache:
            logger.info(
                "Dashboard cache HIT | campaign=%s bundle=%s input_date=%s",
                campaign_id,
                bundle_id,
                input_date,
            )
            return self._cache[cache_key]

        logger.info(
            "Dashboard cache MISS – running checks | campaign=%s bundle=%s input_date=%s",
            campaign_id,
            bundle_id,
            input_date,
        )

        t0 = time.monotonic()

        import concurrent.futures

        # ── Run all heavy Athena/S3 checks concurrently ──────────────────────
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_training = executor.submit(
                self._fetch_training_counts,
                bundle_id,
                model_timestamp
            )
            
            future_sup = None
            if include_suppression:
                future_sup = executor.submit(
                    self._suppression_svc.run_suppression_check,
                    campaign_id=campaign_id,
                    bundle_id=bundle_id,
                    check_date=input_date,
                )
            
            future_cr = None
            if include_cr:
                future_cr = executor.submit(
                    self._cr_svc.run_cr_check,
                    campaign_id=campaign_id,
                    bundle_id=bundle_id,
                    start_date=validation_start_date,
                    end_date=input_date,
                )

            # Wait for tasks to complete
            train_stats, val_stats = future_training.result()
            
            dashboard_sup = None
            if future_sup:
                sup_data = future_sup.result()
                total_imp = sup_data["total_payload_devices"]
                sup_count = sup_data["suppressed_devices"]
                sup_rate = (
                    round((sup_count / total_imp) * 100, 4) if total_imp > 0 else 0.0
                )
                sup_status = "PASS" if sup_rate < 10.0 else "FAIL"
                dashboard_sup = DashboardSuppression(
                    total_payload_devices=total_imp,
                    suppressed_devices=sup_count,
                    suppression_rate=sup_rate,
                    status=sup_status,
                    formula=suppression_rate_formula(sup_count, total_imp),
                )

            dashboard_cr = None
            if future_cr:
                cr_rows_raw = future_cr.result()
                cr_rows = [CRDayRow(**r) for r in cr_rows_raw]
                total_clicks = sum(r.total_clicked_devices for r in cr_rows)
                total_installs = sum(r.total_organic_installs for r in cr_rows)
                total_intersected = sum(r.intersected_devices_24h for r in cr_rows)
                agg_cr = (
                    round((total_intersected / total_clicks) * 100, 2)
                    if total_clicks > 0
                    else 0.0
                )
                dashboard_cr = DashboardCR(
                    total_clicked_devices=total_clicks,
                    total_organic_installs=total_installs,
                    intersected_devices_24h=total_intersected,
                    conversion_rate_24h=agg_cr,
                    daily_trend=cr_rows,
                    formula=cr_formula(total_intersected, total_clicks),
                )

        elapsed = time.monotonic() - t0
        logger.info(
            "Dashboard assembled in %.2fs | training=%d validation=%d",
            elapsed,
            train_stats.row_count if train_stats else 0,
            val_stats.row_count if val_stats else 0,
        )

        response = DashboardResponse(
            input=DashboardInput(
                campaign_id=campaign_id,
                bundle_id=bundle_id,
                input_date=input_date,
            ),
            training=DashboardTraining(
                size=train_stats.row_count if train_stats else 0,
                start_date=train_stats.min_date if train_stats and train_stats.min_date else str(training_start_date or ""),
                end_date=train_stats.max_date if train_stats and train_stats.max_date else str(training_end_date or ""),
                label_1_count=train_stats.label_1_count if train_stats else 0,
                label_0_count=train_stats.label_0_count if train_stats else 0,
            ),
            validation=DashboardValidation(
                size=val_stats.row_count if val_stats else 0,
                start_date=val_stats.min_date if val_stats and val_stats.min_date else str(validation_start_date or ""),
                end_date=val_stats.max_date if val_stats and val_stats.max_date else str(validation_end_date or ""),
                label_1_count=val_stats.label_1_count if val_stats else 0,
                label_0_count=val_stats.label_0_count if val_stats else 0,
            ),
            suppression=dashboard_sup,
            cr=dashboard_cr,
        )

        if self._settings.cache_ttl_seconds > 0:
            self._cache[cache_key] = response

        return response

    def _fetch_training_counts(self, bundle_id: str, model_timestamp: Optional[str] = None):
        from app.services.model_artifacts_service import ModelArtifactsService
        from app.services.training_data_service import TrainingDataService

        model_svc = ModelArtifactsService()
        training_svc = TrainingDataService()
        
        try:
            if model_timestamp:
                model_info = model_svc._load_model_info(model_timestamp)
            else:
                model_info = model_svc.get_latest_model_info()
            # Find the short name (e.g. 'grofers') for the requested full bundle_id (e.g. 'com.grofers...')
            short_bundle = next(
                (b for b in model_info.bundle_ids if b.lower() in bundle_id.lower()), 
                None
            )
            
            if short_bundle:
                # Query S3 directly for this specific bundle
                counts = training_svc.get_counts_for_model(
                    model_timestamp=model_info.timestamp, 
                    bundle_names=[short_bundle]
                )
                if counts.bundles:
                    return counts.bundles[0].train_stats, counts.bundles[0].val_stats
            else:
                logger.warning("Could not map full bundle %s to a short name from the model", bundle_id)
                
        except Exception as e:
            logger.error("Failed to fetch training data sizes from S3: %s", e)
            
        return None, None
