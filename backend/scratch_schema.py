from app.config.settings import get_settings
from app.services.athena_service import AthenaService

settings = get_settings()
athena = AthenaService()

s3_path = 's3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/meesho/train_final/'
table_name = 'tmp_ml_dash_meesho_train_final'
database = settings.athena_database

create_sql = f"""
CREATE EXTERNAL TABLE IF NOT EXISTS `{database}`.`{table_name}` (
    first_seen_date STRING,
    last_seen_date STRING,
    last_updated_date STRING,
    label INT
)
STORED AS PARQUET
LOCATION '{s3_path}'
"""

athena.run(f'DROP TABLE IF EXISTS `{database}`.`{table_name}`')
athena.run(create_sql)

query = f"""
SELECT 
    MIN(first_seen_date) as min_first,
    MAX(first_seen_date) as max_first,
    MIN(last_seen_date) as min_last,
    MAX(last_seen_date) as max_last,
    MIN(last_updated_date) as min_upd,
    MAX(last_updated_date) as max_upd,
    SUM(label) as ones_count,
    COUNT(*) as total_rows
FROM `{database}`.`{table_name}`
"""

try:
    rows = athena.run(query)
    print("SUCCESS:", rows)
except Exception as e:
    print("ERROR:", e)

athena.run(f'DROP TABLE IF EXISTS `{database}`.`{table_name}`')
