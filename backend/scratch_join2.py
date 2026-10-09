from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = f"""
SELECT COUNT(*) AS suppressed_devices
FROM ml_dashboard.payload i
JOIN (
    SELECT DISTINCT TRIM(device_id) AS device_id
    FROM ml_dashboard.organic90
    WHERE bundle_id = 'com.grofers.customerapp'
      AND event_date < '20261003'
      AND event_date >= '20260705'
      AND device_id IS NOT NULL
) o
  ON TRIM(i.deviceid) = o.device_id
WHERE i.event_date = '20261003'
  AND i.campaignid = '6765'
  AND i.deviceid IS NOT NULL
  AND TRIM(i.deviceid) <> ''
"""

try:
    rows = athena.run(sql)
    print("SUCCESS:", rows)
except Exception as e:
    print("ERROR:", e)
