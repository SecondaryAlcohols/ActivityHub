import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", jwt_secret="short")


def test_production_rejects_sample_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="please-change-me-in-production-use-32-bytes-min",
        )


def test_production_accepts_strong_secret():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="a" * 32,
    )
    assert settings.environment == "production"


def test_development_allows_default_secret():
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.jwt_secret
