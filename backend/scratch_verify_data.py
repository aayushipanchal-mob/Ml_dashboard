from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql2 = "SELECT * FROM ml_dashboard.payload LIMIT 5;"
try:
    rows = athena.run(sql2)
    print(f"Rows in payload: {len(rows)}")
    for r in rows:
        print(r)
except Exception as e:
    print(f"Error: {e}")
