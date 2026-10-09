from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

date_str = '20261003'
try:
    print(f"Ensuring partition for {date_str}...")
    athena.ensure_partitions('ml_dashboard.payload', [date_str])
    print("Querying table...")
    rows = athena.run(f"SELECT COUNT(*) as c FROM ml_dashboard.payload WHERE event_date='{date_str}'")
    print(f"Count: {rows[0]}")
except Exception as e:
    print(f"Error: {e}")
