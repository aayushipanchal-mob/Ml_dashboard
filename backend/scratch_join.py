from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = f"""
WITH payload_filtered AS (
    SELECT TRIM(deviceid) AS join_id
    FROM ml_dashboard.payload
    WHERE event_date = '20261003'
      AND campaignid = '6765'
      AND deviceid IS NOT NULL
      AND TRIM(deviceid) <> ''
),
organic_filtered AS (
    SELECT TRIM(device_id) AS join_id
    FROM ml_dashboard.organic90
    WHERE bundle_id = 'com.grofers.customerapp'
      AND event_date < '20261003'
      AND event_date >= '20260705'
)
SELECT COUNT(*) AS suppressed_devices
FROM payload_filtered p
JOIN organic_filtered o
  ON p.join_id = o.join_id
"""

try:
    rows = athena.run(sql)
    print("SUCCESS:", rows)
except Exception as e:
    print("ERROR:", e)
