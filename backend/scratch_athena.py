from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()
print(f"Training Table: {settings.training_table}")
try:
    rows = athena.run(f"SELECT * FROM {settings.training_table} LIMIT 5")
    print(rows)
except Exception as e:
    print(e)
