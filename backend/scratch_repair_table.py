from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = "MSCK REPAIR TABLE ml_dashboard.payload;"

try:
    print("Repairing table...")
    rows = athena.run(sql)
    print("Repair complete.")
    for r in rows:
        print(r)
except Exception as e:
    print(f"Error: {e}")
