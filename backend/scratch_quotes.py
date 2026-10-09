from app.config.settings import get_settings
from app.services.athena_service import AthenaService
settings = get_settings()
athena = AthenaService()

database = "ml_dashboard"
table_name = "tmp_test_shabbir"
s3_path = "s3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/grofers/train_final/"

athena.run(f"CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{table_name} (dummy STRING) STORED AS PARQUET LOCATION '{s3_path}'")
print("Table created")

try:
    rows = athena.run(f'SELECT COUNT(*) FROM "{database}"."{table_name}"')
    print("COUNT with double quotes:", rows)
except Exception as e:
    print("Double quotes failed:", e)

try:
    rows = athena.run(f'SELECT COUNT(*) FROM `{database}`.`{table_name}`')
    print("COUNT with backticks:", rows)
except Exception as e:
    print("Backticks failed:", e)

athena.run(f"DROP TABLE {database}.{table_name}")
print("Table dropped")
