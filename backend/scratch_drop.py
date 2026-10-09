from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = "DROP TABLE IF EXISTS ml_dashboard.temp_test"

try:
    rows = athena.run(sql)
    print("Success")
except Exception as e:
    print(e)
