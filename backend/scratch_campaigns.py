import sys
import os

sys.path.append("/Users/shabbirgovernor/Downloads/Aayushi/ML_DASHBOARD/backend")

from app.services.athena_service import AthenaService
from datetime import date, timedelta

athena = AthenaService()
end_date = date.today()
start_date = end_date - timedelta(days=2)
dates_raw = []
cur = start_date
while cur <= end_date:
    dates_raw.append(cur.strftime("%Y%m%d"))
    cur += timedelta(days=1)
    
dates_sql = ", ".join([f"'{d}'" for d in dates_raw])
sql = f"""
SELECT DISTINCT campaign_id, advertiser_bundle AS bundle_id
FROM ml_dashboard.impressions
WHERE event_date IN ({dates_sql})
  AND campaign_id IS NOT NULL 
  AND advertiser_bundle IS NOT NULL
  AND TRIM(campaign_id) <> ''
  AND TRIM(advertiser_bundle) <> ''
"""

rows = athena.run(sql)
print("Campaigns in Athena:")
for row in rows:
    print(f"campaign_id: {row.get('campaign_id')}, bundle_id: {row.get('bundle_id')}")
