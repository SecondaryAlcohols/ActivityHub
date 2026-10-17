from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_JWT_SECRET = "dev-secret-change-me-please-use-32-bytes-min"
INSECURE_JWT_SECRETS = {
    DEFAULT_JWT_SECRET,
    "change-me-in-production",
    "please-change-me-in-production-use-32-bytes-min",
    "change-me-to-a-random-string-at-least-32-bytes",
}


class Settings(BaseSettings):
    app_name: str = "活动报名与签到管理系统"
    environment: str = "development"
    debug: bool = True
    database_url: str = (
        f"sqlite+aiosqlite:///{(BASE_DIR / 'event_system.db').as_posix()}"
    )
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    login_max_attempts: int = 5
    login_window_minutes: int = 15
    login_lock_minutes: int = 15
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment.lower() == "production":
            if (
                self.jwt_secret in INSECURE_JWT_SECRETS
                or len(self.jwt_secret) < 32
            ):
                raise ValueError(
                    "生产环境必须通过环境变量设置至少 32 位的随机 JWT_SECRET"
                )
        return self


settings = Settings()
