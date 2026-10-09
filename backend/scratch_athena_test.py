import sys
import os

# Add the backend dir to sys.path so we can import app
sys.path.append("/Users/shabbirgovernor/Downloads/Aayushi/ML_DASHBOARD/backend")

from app.services.athena_service import AthenaService

athena = AthenaService()
sql = """
SELECT 'profiles_total' AS feed, COUNT(*) AS rows FROM device_profiles_V1.global_device_profiles_V1
UNION ALL SELECT 'delta_upsert',  COUNT(*) FROM device_profiles_V1.global_device_profiles_V1_delta
UNION ALL SELECT 'purge_deletes', COUNT(*) FROM device_profiles_V1.global_device_profiles_V1_purge
UNION ALL SELECT 'upload_audit',  COUNT(*) FROM device_profiles_V1.upload_audit
"""
res = athena.run(sql)
print("Query result:")
print(res)
