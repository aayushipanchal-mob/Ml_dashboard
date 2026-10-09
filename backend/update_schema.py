from app.services.athena_service import AthenaService

athena = AthenaService()

drop_sql = "DROP TABLE IF EXISTS ml_dashboard.payload;"

create_sql = """
CREATE EXTERNAL TABLE IF NOT EXISTS ml_dashboard.payload (
  exchangeId STRING,
  campaignId STRING,
  pubBundle STRING,
  adSlotId STRING,
  creativeType STRING,
  isRewarded STRING,
  advCategory STRING,
  advBundle STRING,
  cpiScore DOUBLE,
  bidFloor DOUBLE,
  advCost DOUBLE,
  campCurrSpend DOUBLE,
  deviceId STRING,
  modelTimestamp STRING,
  pincode STRING,
  timestamp STRING,
  calculatedBidPrice DOUBLE,
  userTerm DOUBLE,
  hourEffect DOUBLE,
  maxEcpm DOUBLE,
  rawBid DOUBLE,
  hourlyImp DOUBLE,
  invRev DOUBLE,
  invRoas DOUBLE,
  invScore DOUBLE,
  dailyMultiplier DOUBLE,
  lo DOUBLE,
  hi DOUBLE,
  bidFlag STRING
)
PARTITIONED BY (event_date STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://mobavenue-simplismart-aws-s3-apse-sg/rtb/payload/'
TBLPROPERTIES (
  "skip.header.line.count"="1"
);
"""

try:
    print("Dropping old table...")
    athena.run(drop_sql)
    print("Old table dropped.")
    
    print("Creating new table...")
    athena.run(create_sql)
    print("New table created successfully!")
except Exception as e:
    print(f"Error: {e}")
