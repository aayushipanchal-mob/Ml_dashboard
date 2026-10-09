"""
app/services/model_artifacts_service.py
────────────────────────────────────────
Reads model artifacts directly from S3 to discover:
  1. The latest model timestamp (most recently created folder under the models prefix)
  2. Bundle IDs (from feature_config.pkl → BUNDLES key)
  3. Full model metadata (bundles, temperature, feature names)

This replaces the static campaigns.json approach for bundle_id population.
The bundle_id list is always in sync with what the model was actually trained on.

S3 path structure:
  s3://<bucket>/rtb/data/ml/models/<YYYYMMDD_HHMMSS>/feature_config.pkl
  s3://<bucket>/rtb/data/ml/models/<YYYYMMDD_HHMMSS>/temperature.npy
  ...

Usage:
  svc = ModelArtifactsService()
  info = svc.get_latest_model_info()
  # info.bundle_ids → ["com.grofers.customerapp", "com.licious", ...]
"""

from __future__ import annotations

import io
import logging
import pickle
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3
import numpy as np
from botocore.exceptions import BotoCoreError, ClientError

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Cache duration in seconds (re-reads S3 at most once per window)
_CACHE_TTL = 300  # 5 minutes


@dataclass
class ModelInfo:
    """Metadata extracted from a model's artifact files."""
    timestamp: str
    bundle_ids: List[str]
    temperature: Optional[float] = None
    user_cat_features: List[str] = field(default_factory=list)
    user_num_features: List[str] = field(default_factory=list)
    s3_prefix: str = ""


class ModelArtifactsService:
    """
    Reads model metadata from S3 without downloading the full model.

    Only downloads:
      - feature_config.pkl   (~small, contains BUNDLES, USER_CAT, USER_NUM)
      - temperature.npy      (~tiny, single float)

    The heavy files (user_tower.keras, embeddings) are NOT downloaded here.
    """

    S3_BUCKET = "mobavenue-simplismart-aws-s3-apse-sg"
    MODELS_PREFIX = "rtb/data/ml/models/"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._s3 = self._build_s3_client()
        # Simple in-process cache
        self._cached_info: Optional[ModelInfo] = None
        self._cache_time: float = 0.0

    def _build_s3_client(self):
        kwargs: Dict[str, Any] = {"region_name": self._settings.aws_region}
        if self._settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = self._settings.aws_access_key_id
        if self._settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = self._settings.aws_secret_access_key
        if self._settings.aws_session_token:
            kwargs["aws_session_token"] = self._settings.aws_session_token
        return boto3.client("s3", **kwargs)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_latest_model_info(self) -> ModelInfo:
        """
        Returns metadata for the latest model.
        Result is cached for CACHE_TTL seconds to avoid hammering S3.
        """
        now = time.monotonic()
        if self._cached_info and (now - self._cache_time) < _CACHE_TTL:
            logger.debug(
                "ModelArtifactsService cache HIT | timestamp=%s",
                self._cached_info.timestamp,
            )
            return self._cached_info

        logger.info("ModelArtifactsService cache MISS – reading from S3")
        timestamp = self._get_latest_timestamp()
        info = self._load_model_info(timestamp)
        self._cached_info = info
        self._cache_time = now
        logger.info(
            "Loaded model info | timestamp=%s bundles=%s",
            timestamp,
            info.bundle_ids,
        )
        return info

    def list_all_timestamps(self) -> List[str]:
        """Return all model timestamps available in S3, sorted newest first."""
        try:
            paginator = self._s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self.S3_BUCKET,
                Prefix=self.MODELS_PREFIX,
                Delimiter="/",
            )
            timestamps = []
            for page in pages:
                for prefix in page.get("CommonPrefixes", []):
                    # prefix looks like  rtb/data/ml/models/20260919_070055/
                    folder = prefix["Prefix"].rstrip("/").split("/")[-1]
                    if folder:
                        timestamps.append(folder)
            timestamps.sort(reverse=True)
            logger.info("Found %d model timestamps in S3", len(timestamps))
            return timestamps
        except (BotoCoreError, ClientError) as exc:
            logger.error("Failed to list model timestamps from S3: %s", exc)
            raise

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_latest_timestamp(self) -> str:
        timestamps = self.list_all_timestamps()
        if not timestamps:
            raise RuntimeError(
                f"No model folders found at s3://{self.S3_BUCKET}/{self.MODELS_PREFIX}"
            )
        latest = timestamps[0]
        logger.info("Latest model timestamp: %s", latest)
        return latest

    def _load_model_info(self, timestamp: str) -> ModelInfo:
        prefix = f"{self.MODELS_PREFIX}{timestamp}/"
        s3_prefix_full = f"s3://{self.S3_BUCKET}/{prefix}"

        # ── feature_config.pkl ────────────────────────────────────────────────
        fc_key = f"{prefix}feature_config.pkl"
        logger.info("Downloading s3://%s/%s", self.S3_BUCKET, fc_key)
        try:
            obj = self._s3.get_object(Bucket=self.S3_BUCKET, Key=fc_key)
            fc: Dict[str, Any] = pickle.loads(obj["Body"].read())
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                f"Could not download feature_config.pkl for timestamp {timestamp}: {exc}"
            ) from exc

        bundles: List[Dict] = fc.get("BUNDLES", [])
        # BUNDLES is a list of dicts: [{"name": "com.grofers.customerapp", ...}, ...]
        bundle_ids = [b["name"] for b in bundles if isinstance(b, dict) and "name" in b]

        user_cat: List[str] = fc.get("USER_CAT", [])
        user_num: List[str] = fc.get("USER_NUM", [])

        # ── temperature.npy (optional — best-effort) ──────────────────────────
        temperature: Optional[float] = None
        temp_key = f"{prefix}temperature.npy"
        try:
            obj = self._s3.get_object(Bucket=self.S3_BUCKET, Key=temp_key)
            temp_arr = np.load(io.BytesIO(obj["Body"].read()))
            temperature = float(temp_arr[0])
        except Exception as exc:
            logger.warning("Could not load temperature.npy: %s", exc)

        return ModelInfo(
            timestamp=timestamp,
            bundle_ids=bundle_ids,
            temperature=temperature,
            user_cat_features=user_cat,
            user_num_features=user_num,
            s3_prefix=s3_prefix_full,
        )
