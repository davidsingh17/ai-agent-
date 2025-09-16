from fastapi import APIRouter
import os
from typing import Dict, Any

# DB
from app.services.db import execute

# S3/MinIO
import boto3
from botocore.client import Config

# Redis
import redis

router = APIRouter(prefix="/health", tags=["health"])


def _s3_client():
    endpoint = (
        os.getenv("S3_ENDPOINT")
        or os.getenv("MINIO_ENDPOINT")
        or "http://minio:9000"
    )
    access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("MINIO_ACCESS_KEY") or "minioadmin"
    secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("MINIO_SECRET_KEY") or "minioadmin"
    region = os.getenv("S3_REGION") or "us-east-1"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _ok(data: Dict[str, Any] = None):
    return {"status": "up", **(data or {})}


def _down(error: str):
    return {"status": "down", "error": error}


@router.get("")
def health_root():
    """Panoramica veloce: DB, S3 e Redis."""
    out = {}

    # DB
    try:
        execute("SELECT 1;")
        out["db"] = _ok()
    except Exception as e:
        out["db"] = _down(str(e))

    # S3/MinIO
    try:
        s3 = _s3_client()
        # list_buckets come "ping"
        s3.list_buckets()
        out["s3"] = _ok({"endpoint": os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT")})
    except Exception as e:
        out["s3"] = _down(str(e))

    # Redis
    try:
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        r.ping()
        out["redis"] = _ok()
    except Exception as e:
        out["redis"] = _down(str(e))

    # overall
    overall = "up" if all(v.get("status") == "up" for v in out.values()) else "down"
    return {"status": overall, **out}


@router.get("/db")
def health_db():
    try:
        execute("SELECT 1;")
        return _ok()
    except Exception as e:
        return _down(str(e))


@router.get("/s3")
def health_s3():
    try:
        s3 = _s3_client()
        s3.list_buckets()
        return _ok({"endpoint": os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT")})
    except Exception as e:
        return _down(str(e))


@router.get("/redis")
def health_redis():
    try:
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        r.ping()
        return _ok()
    except Exception as e:
        return _down(str(e))
