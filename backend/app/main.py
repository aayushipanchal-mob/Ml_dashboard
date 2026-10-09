"""
app/main.py
────────────
FastAPI application entry point.

Responsibilities
────────────────
  1. Create the FastAPI app instance with metadata for Swagger UI.
  2. Configure structured logging for the entire application.
  3. Register all API routers with their URL prefixes.
  4. Expose the /health endpoint.
  5. Add CORS middleware so the dashboard frontend can call the API
     from a browser (origins configurable via APP_ENV).

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import logging.config
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import campaigns, cr, dashboard, data_size, dataset_counts, models, suppression, profile_counts
from app.config.settings import get_settings
from app.models.dashboard import HealthResponse

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

settings = get_settings()

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
            }
        },
        "root": {
            "handlers": ["console"],
            "level": settings.log_level.upper(),
        },
    }
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown hooks)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "ML Dashboard API starting | env=%s athena_db=%s",
        settings.app_env,
        settings.athena_database,
    )
    yield
    logger.info("ML Dashboard API shutting down")


# ─────────────────────────────────────────────────────────────────────────────
# App instance
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ML Data Quality Dashboard API",
    description=(
        "Backend API for monitoring ML training/validation data quality "
        "and campaign-level conversion rate metrics. "
        "All parameters (campaign, bundle, dates) are configurable per request. "
        "Formula metadata is returned alongside every calculated metric so the "
        "frontend can render 'Show Formula' toggles without any business logic."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────────────────────

# In production, replace "*" with the actual dashboard origin URL.
_CORS_ORIGINS = (
    ["*"]
    if settings.app_env == "development"
    else ["https://your-dashboard-domain.com"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request timing middleware
# ─────────────────────────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s → %d  (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Root redirect  →  /docs
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect the bare root URL to Swagger UI for convenience."""
    return RedirectResponse(url="/docs")


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Returns the application status and configuration summary.",
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        athena_database=settings.athena_database,
    )


# ─────────────────────────────────────────────────────────────────────────────
# API routers
# ─────────────────────────────────────────────────────────────────────────────

PREFIX = "/api"

app.include_router(models.router,         prefix=PREFIX, tags=["Model Artifacts"])
app.include_router(dataset_counts.router, prefix=PREFIX, tags=["Dataset Counts"])
app.include_router(campaigns.router,      prefix=PREFIX, tags=["Campaigns"])
app.include_router(suppression.router,    prefix=PREFIX, tags=["Suppression"])
app.include_router(cr.router,             prefix=PREFIX, tags=["Conversion Rate"])
app.include_router(dashboard.router,      prefix=PREFIX, tags=["Dashboard"])
app.include_router(profile_counts.router, prefix=PREFIX, tags=["Profile Counts"])
