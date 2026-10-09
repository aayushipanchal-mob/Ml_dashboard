from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()
try:
    rows = athena.run("SHOW TABLES IN ml_dashboard")
    print("Tables in ml_dashboard:")
    for row in rows:
        print(row)
except Exception as e:
    print(e)
