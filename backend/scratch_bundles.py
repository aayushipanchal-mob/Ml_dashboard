import sys
import pickle
import boto3

s3 = boto3.client("s3", region_name="ap-southeast-1")
bucket = "mobavenue-simplismart-aws-s3-apse-sg"
key = "rtb/data/ml/models/20261008_102216/feature_config.pkl"

obj = s3.get_object(Bucket=bucket, Key=key)
fc = pickle.loads(obj["Body"].read())

bundles = fc.get("BUNDLES", [])
print(bundles)
