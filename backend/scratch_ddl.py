from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

sql = f"""
CREATE EXTERNAL TABLE IF NOT EXISTS ml_dashboard.temp_test (
    dummy STRING
)
STORED AS PARQUET
LOCATION 's3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/'
"""

try:
    rows = athena.run(sql)
    print("Success")
except Exception as e:
    print(e)
