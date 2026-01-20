import boto3

# Obtener info de RDS
rds = boto3.client('rds', region_name='us-east-2')
resp = rds.describe_db_instances(DBInstanceIdentifier='eki-database')
db = resp['DBInstances'][0]
print(f"Endpoint: {db['Endpoint']['Address']}")
print(f"Puerto: {db['Endpoint']['Port']}")

# Obtener info de S3
s3 = boto3.client('s3', region_name='us-east-2')
buckets = s3.list_buckets()
print("\nBuckets S3:")
for bucket in buckets['Buckets']:
    print(f"  - {bucket['Name']}")
