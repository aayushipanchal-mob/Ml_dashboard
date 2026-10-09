import pyarrow.parquet as pq
import s3fs

s3 = s3fs.S3FileSystem()
path = 's3://mobavenue-simplismart-aws-s3-apse-sg/rtb/data/training_data/meesho/train_final/20260918_045928_00169_iaxxw_09b9ecd7-c873-43d0-af19-5af42e7c43bd'
schema = pq.read_schema(path, filesystem=s3)
print(schema.names)
