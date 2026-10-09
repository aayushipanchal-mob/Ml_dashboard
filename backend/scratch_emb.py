import pickle
import boto3

s3 = boto3.client('s3', region_name='ap-southeast-1')
bucket = 'mobavenue-simplismart-aws-s3-apse-sg'
key = 'rtb/data/ml/models/20261008_102216/embedding_lookup.pkl'

obj = s3.get_object(Bucket=bucket, Key=key)
emb = pickle.loads(obj['Body'].read())

print(emb.keys())
