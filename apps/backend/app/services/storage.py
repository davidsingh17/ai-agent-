import os
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

S3_ENDPOINT = os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT") or "http://minio:9000"
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY") or os.getenv("MINIO_ACCESS_KEY") or "minioadmin"
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY") or os.getenv("MINIO_SECRET_KEY") or "minioadmin"
S3_BUCKET     = os.getenv("S3_BUCKET")     or os.getenv("MINIO_BUCKET")     or "ai-agent-dev"
S3_REGION     = os.getenv("S3_REGION") or "us-east-1"

def _s3_client():
    use_ssl = S3_ENDPOINT.strip().lower().startswith("https://")
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        use_ssl=use_ssl,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

def _ensure_bucket(s3, bucket: str):
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError as e:
        code = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if code in (404, 301):
            if S3_REGION == "us-east-1":
                s3.create_bucket(Bucket=bucket)
            else:
                s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": S3_REGION},
                )
        else:
            raise

def upload_bytes(key: str, data: bytes, content_type: Optional[str] = None, bucket: Optional[str] = None):
    s3 = _s3_client()
    bucket = bucket or S3_BUCKET
    try:
        _ensure_bucket(s3, bucket)
        extra = {"ContentType": content_type} if content_type else {}
        s3.put_object(Bucket=bucket, Key=key, Body=data, **extra)
        return {"bucket": bucket, "key": key}
    except Exception as e:
        raise RuntimeError(f"Errore upload su S3/MinIO ({S3_ENDPOINT}): {e}")
