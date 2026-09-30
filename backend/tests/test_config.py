from backend.app.core.config import Settings, get_settings


def test_default_settings():
    settings = get_settings()
    assert settings.APP_NAME == "AI-Driven Intelligent UFDR Analysis System"
    assert settings.API_PREFIX == "/api/v1"
    assert isinstance(settings.CORS_ORIGINS, list)
    assert len(settings.CORS_ORIGINS) > 0


def test_cors_origins_validator_string():
    settings = Settings(CORS_ORIGINS="http://localhost:3000,http://localhost:5173")
    assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]


def test_cors_origins_validator_list():
    origins = ["http://forensic.local:3000", "http://forensic.local:5173"]
    settings = Settings(CORS_ORIGINS=origins)
    assert settings.CORS_ORIGINS == origins
