from app.services.athena_service import AthenaService
from app.config.settings import get_settings

settings = get_settings()
athena = AthenaService()

print("IMPRESSIONS:")
try:
    print(athena.run(f"SHOW COLUMNS FROM {settings.impressions_table}"))
except Exception as e:
    print(e)

print("\nCLICKS:")
try:
    print(athena.run(f"SHOW COLUMNS FROM {settings.clicks_table}"))
except Exception as e:
    print(e)
