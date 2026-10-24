import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_SECRET = "a" * 32


def production_settings(**overrides):
    values = {
        "environment": "production",
        "jwt_secret": STRONG_SECRET,
        "ticket_secret": STRONG_SECRET,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        production_settings(jwt_secret="short")


def test_production_rejects_sample_jwt_secret():
    with pytest.raises(ValidationError):
        production_settings(
            jwt_secret="please-change-me-in-production-use-32-bytes-min"
        )


def test_production_rejects_short_ticket_secret():
    with pytest.raises(ValidationError):
        production_settings(ticket_secret="short")


def test_production_rejects_sample_ticket_secret():
    with pytest.raises(ValidationError):
        production_settings(ticket_secret="please-change-me-ticket-secret")


def test_production_rejects_mock_login():
    with pytest.raises(ValidationError):
        production_settings(wechat_mock_login=True)


def test_mock_login_requires_debug():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="development",
            debug=False,
            wechat_mock_login=True,
        )


def test_production_accepts_strong_secrets():
    settings = production_settings()
    assert settings.environment == "production"
    assert settings.jwt_secret == STRONG_SECRET
    assert settings.ticket_secret == STRONG_SECRET


def test_development_allows_default_secret():
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.jwt_secret
    assert settings.ticket_secret
