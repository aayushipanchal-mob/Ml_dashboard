from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = f"""
SELECT SUM(i.payload_count * o.organic_count) AS suppressed_devices
FROM (
    SELECT TRIM(deviceid) AS join_id, COUNT(1) AS payload_count
    FROM ml_dashboard.payload
    WHERE event_date = '20261003'
      AND campaignid = '6765'
      AND deviceid IS NOT NULL
      AND TRIM(deviceid) <> ''
    GROUP BY TRIM(deviceid)
) i
JOIN (
    SELECT TRIM(device_id) AS join_id, COUNT(1) AS organic_count
    FROM ml_dashboard.organic90
    WHERE bundle_id = 'com.grofers.customerapp'
      AND event_date < '20261003'
      AND event_date >= '20260705'
      AND device_id IS NOT NULL
    GROUP BY TRIM(device_id)
) o
  ON i.join_id = o.join_id
"""

try:
    rows = athena.run(sql)
    print("SUCCESS GROUPBY:", rows)
except Exception as e:
    print("ERROR GROUPBY:", e)
