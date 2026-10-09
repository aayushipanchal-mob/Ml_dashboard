from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = "SHOW TABLES IN ml_dashboard;"

try:
    rows = athena.run(sql)
    print(f"Tables in ml_dashboard: {rows}")
except Exception as e:
    print(f"Error: {e}")
