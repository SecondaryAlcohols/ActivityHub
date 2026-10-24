"""应用配置：全部通过环境变量注入，带生产环境安全护栏。"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SECRET = "dev-only-insecure-secret-please-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 运行环境 ----
    app_name: str = "ActivityHub API"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # ---- 数据库 ----
    database_url: str = "postgresql+asyncpg://activityhub:activityhub@127.0.0.1:5432/activityhub"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ---- 安全 ----
    secret_key: str = DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 30
    ticket_secret: str | None = None
    face_encryption_key: str | None = None

    # ---- 人脸识别 ----
    face_provider: Literal["stub", "http"] = "stub"
    face_provider_url: str | None = None
    face_provider_token: str | None = None

    # ---- 限流（单实例进程内）----
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 300
    ip_login_rate_limit: int = 30
    register_rate_limit: int = 10
    register_rate_window_seconds: int = 3600

    # ---- 考勤策略默认值 ----
    qr_default_rotation_seconds: int = 10
    max_checkin_failures: int = 5
    checkin_failure_window_minutes: int = 10
    same_ip_window_minutes: int = 15

    # ---- 网络 ----
    trusted_proxy_headers: bool = False
    cors_origins: Annotated[list[str], NoDecode] = ["*"]
    campus_cidrs: Annotated[list[str], NoDecode] = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]

    @field_validator("cors_origins", "campus_cidrs", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        if self.environment != "production":
            return self

        if self.secret_key == DEFAULT_SECRET or len(self.secret_key) < 32:
            raise ValueError("生产环境 SECRET_KEY 必须是长度不少于 32 位的随机字符串")
        if self.face_provider == "stub":
            raise ValueError("生产环境禁止使用 stub 人脸识别实现，请配置 FACE_PROVIDER=http")
        if self.debug:
            raise ValueError("生产环境必须关闭 DEBUG")
        if "*" in self.cors_origins:
            raise ValueError("生产环境 CORS_ORIGINS 不允许配置为 *")
        return self

    # ---- 派生配置 ----
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """Alembic / 脚本使用的同步驱动连接串。"""
        return self.database_url.replace("+asyncpg", "")

    @property
    def resolved_ticket_secret(self) -> bytes:
        return (self.ticket_secret or self.secret_key).encode()

    @property
    def resolved_face_key(self) -> bytes:
        """返回 32 字节 urlsafe base64 的 Fernet 密钥。"""
        if self.face_encryption_key:
            return self.face_encryption_key.encode()
        digest = hashlib.sha256(f"face:{self.secret_key}".encode()).digest()
        return base64.urlsafe_b64encode(digest)


@lru_cache
def get_settings() -> Settings:
    return Settings()
