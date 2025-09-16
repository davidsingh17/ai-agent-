from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    env: str = "dev"

    # CORS (può essere una lista separata da virgola, default *)
    cors_origins: str = "*"  

    # DB
    postgres_db: str = "ai_agent"
    postgres_user: str = "ai_agent"
    postgres_password: str = "ai_agent_pw"
    postgres_port: int = 5432
    postgres_host: str = "db"

    # S3
    s3_endpoint: str = "http://minio:9000"
    s3_region: str = "eu-south-1"
    s3_bucket: str = "ai-agent-dev"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"

    # Utility: ritorna origins come lista
    @property
    def cors_origin_list(self) -> List[str]:
        if not self.cors_origins:
            return []
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
