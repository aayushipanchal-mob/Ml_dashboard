from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = f"""
SELECT COUNT(*) AS suppressed_devices
FROM ml_dashboard.payload i
WHERE i.event_date = '20261003'
  AND i.campaignid = '6765'
  AND i.deviceid IS NOT NULL
  AND TRIM(i.deviceid) <> ''
  AND EXISTS (
      SELECT 1
      FROM ml_dashboard.organic90 o
      WHERE o.bundle_id = 'com.grofers.customerapp'
        AND o.event_date < '20261003'
        AND o.event_date >= '20260705'
        AND o.device_id IS NOT NULL
        AND TRIM(o.device_id) = TRIM(i.deviceid)
  )
"""

try:
    rows = athena.run(sql)
    print("SUCCESS EXISTS:", rows)
except Exception as e:
    print("ERROR EXISTS:", e)
