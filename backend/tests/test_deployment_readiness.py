"""Tests for Module 13: Production Deployment Readiness, Health & Security Validation."""
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_subsystems_without_secrets():
    """GET /api/health must verify DB connectivity and hide secrets/credentials."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"
    assert "vector_store" in data
    raw = resp.text.lower()
    for sensitive in ("smtp_password", "groq_api_key", "jwt_secret", "database_url", "password"):
        assert sensitive not in raw


def test_production_settings_validation_catches_insecure_defaults():
    """Settings.validate_runtime_settings warns on insecure dev defaults in production."""
    prod_insecure = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="development_secret_key_minimum_32_characters_long_12345",
        DATABASE_URL="sqlite:///./nexdesk.db",
        GROQ_API_KEY="",
        SMTP_PASSWORD="",
        CORS_ORIGINS=["http://localhost:5173"],
    )
    warnings = prod_insecure.validate_runtime_settings()
    assert len(warnings) == 5
    joined = " ".join(warnings).lower()
    assert "jwt_secret" in joined
    assert "sqlite" in joined
    assert "groq_api_key" in joined
    assert "smtp_password" in joined
    assert "cors_origins" in joined


def test_production_settings_validation_passes_when_hardened():
    """Settings.validate_runtime_settings returns 0 warnings when fully hardened."""
    prod_secure = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="a_very_strong_random_production_secret_key_over_32_chars_long!",
        DATABASE_URL="postgresql://user:pass@db.example.com:5432/nexdesk",
        GROQ_API_KEY="gsk_test_production_key",
        SMTP_PASSWORD="app_password_16_chars",
        CORS_ORIGINS=["https://nexdesk.vercel.app"],
    )
    warnings = prod_secure.validate_runtime_settings()
    assert warnings == []
