# ML Data Quality Dashboard — Backend

A clean, scalable FastAPI backend for monitoring ML training/validation data quality
and campaign-level conversion rate (CR) metrics.

---

## Project Structure

```
backend/
├── .env                          ← AWS/Athena config (do NOT commit to git)
├── campaigns.json                ← Editable campaign → bundle mappings
├── requirements.txt              ← Python dependencies
└── app/
    ├── main.py                   ← FastAPI app entry point
    ├── config/
    │   └── settings.py           ← All settings loaded from .env
    ├── models/
    │   ├── requests.py           ← Input validation models (Pydantic)
    │   └── dashboard.py          ← Response models (Pydantic)
    ├── utils/
    │   └── formulas.py           ← Formula metadata factory functions
    ├── services/
    │   ├── athena_service.py     ← AWS Athena query execution (reusable)
    │   ├── campaigns_service.py  ← Loads campaign/bundle mappings
    │   ├── data_size_service.py  ← Counts training/validation rows
    │   ├── suppression_service.py← Suppression intersection check
    │   ├── cr_service.py         ← Conversion rate Athena query
    │   └── dashboard_service.py  ← Orchestrates all services + caching
    └── api/
        ├── campaigns.py          ← GET /api/campaigns
        ├── data_size.py          ← GET /api/training-data-size & /validation-data-size
        ├── suppression.py        ← GET /api/suppression
        ├── cr.py                 ← GET /api/cr
        └── dashboard.py          ← GET /api/dashboard  |  POST /api/dashboard/check
```

---

## Setup

### 1. Create a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env` and fill in your real values:

```bash
cp .env .env.local   # optional, or edit .env directly
```

Key variables:

| Variable | Description | Example |
|---|---|---|
| `AWS_REGION` | AWS region for Athena | `ap-southeast-1` |
| `ATHENA_DATABASE` | Athena database name | `ml_dashboard` |
| `ATHENA_OUTPUT_LOCATION` | S3 path for query results | `s3://my-bucket/athena/` |
| `IMPRESSIONS_TABLE` | Full Athena table for impressions | `ml_dashboard.impressions` |
| `CLICKS_TABLE` | Full Athena table for clicks | `ml_dashboard.clicks` |
| `ORGANIC_TABLE` | Full Athena table for organic events | `ml_dashboard.organic` |
| `ORGANIC90_TABLE` | Full Athena table for organic90 | `ml_dashboard.organic90` |
| `TRAINING_TABLE` | Full Athena table for training data | `ml_dashboard.training_data` |
| `VALIDATION_TABLE` | Full Athena table for validation data | `ml_dashboard.validation_data` |
| `CACHE_TTL_SECONDS` | Dashboard result cache duration | `300` (5 minutes) |

> **AWS credentials**: Do NOT hardcode them. Leave `AWS_ACCESS_KEY_ID` and
> `AWS_SECRET_ACCESS_KEY` blank to use IAM role / instance-profile credentials
> (recommended for EC2/ECS deployments).

### 4. Configure campaigns

Edit `campaigns.json` to add or remove campaign → bundle mappings:

```json
[
  {"campaign_id": "6765", "bundle_id": "com.grofers.customerapp"},
  {"campaign_id": "7895", "bundle_id": "com.meesho.supply"}
]
```

No code change or restart is needed — the file is read on every request.

---

## Running Locally

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/campaigns` | List all campaign → bundle mappings |
| GET | `/api/training-data-size` | Row count for training dataset |
| GET | `/api/validation-data-size` | Row count for validation dataset |
| GET | `/api/suppression` | Suppression check (impression ∩ organic90) |
| GET | `/api/cr` | Daily 24h Conversion Rate check |
| GET | `/api/dashboard` | All checks combined (GET with query params) |
| POST | `/api/dashboard/check` | All checks combined (POST with JSON body) |

### Swagger UI

Once the server is running, open:

```
http://localhost:8000/docs
```

All endpoints have full documentation, parameter descriptions, and example responses.

---

## Example Requests

### Health check
```
GET http://localhost:8000/health
```

### Campaigns list
```
GET http://localhost:8000/api/campaigns
```

### Training data size
```
GET http://localhost:8000/api/training-data-size
    ?campaign_id=6765
    &bundle_id=com.grofers.customerapp
    &start_date=2026-09-01
    &end_date=2026-09-25
```

### Suppression check
```
GET http://localhost:8000/api/suppression
    ?campaign_id=6765
    &bundle_id=com.grofers.customerapp
    &date=2026-09-29
```

### CR check
```
GET http://localhost:8000/api/cr
    ?campaign_id=6765
    &bundle_id=com.grofers.customerapp
    &start_date=2026-09-27
    &end_date=2026-09-29
```

### Full dashboard (GET)
```
GET http://localhost:8000/api/dashboard
    ?campaign_id=6765
    &bundle_id=com.grofers.customerapp
    &input_date=2026-09-29
    &training_start_date=2026-09-01
    &training_end_date=2026-09-25
    &validation_start_date=2026-09-26
    &validation_end_date=2026-09-29
```

### Full dashboard (POST)
```http
POST http://localhost:8000/api/dashboard/check
Content-Type: application/json

{
  "campaign_id": "6765",
  "bundle_id": "com.grofers.customerapp",
  "input_date": "2026-09-29",
  "training_start_date": "2026-09-01",
  "training_end_date": "2026-09-25",
  "validation_start_date": "2026-09-26",
  "validation_end_date": "2026-09-29"
}
```

---

## Error Responses

All errors return JSON with a `detail` field:

```json
{"detail": "No impression devices found for the selected campaign and date."}
{"detail": "Athena query timed out. Try a shorter date range."}
{"detail": "training_start_date must be on or before training_end_date"}
```

HTTP status codes used:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 404 | No data found |
| 422 | Validation error (bad parameters) |
| 500 | Athena / server error |
| 504 | Athena query timeout |

---

## Design Principles

- **No hardcoded campaigns/dates**: everything is driven by API request parameters.
- **No business logic in the frontend**: the backend calculates all metrics and returns formula metadata.
- **No SQL in route handlers**: all SQL lives inside service classes.
- **No duplicated Athena code**: all queries go through `AthenaService`.
- **Safe SQL construction**: all user-supplied values are Pydantic-validated Python types before being formatted into SQL.
- **Caching**: dashboard responses are cached (default 5 min) to avoid redundant Athena queries.
- **Structured logging**: every request, query, and error is logged with context. No device IDs are ever logged.
