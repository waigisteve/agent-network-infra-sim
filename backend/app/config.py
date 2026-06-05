from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agent Network Platform"
    environment: str = "local"
    database_url: str = "sqlite:///./agent_network.db"
    database_migration_url: str = ""
    database_ssl_mode: str = ""
    database_ssl_root_cert: str = ""
    database_ssl_cert: str = ""
    database_ssl_key: str = ""
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_enabled: bool = False
    jwt_secret_key: str = "local-dev-only-not-a-production-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    kyc_storage_backend: str = "local"
    kyc_storage_path: str = "storage/kyc"
    kyc_max_upload_bytes: int = 5_000_000
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "kyc-documents"
    minio_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
