from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://nexus:nexus@db:5432/nexuscoach"
    jwt_secret: str = "dev-only-change-me"
    # Fernet key (base64, 32 bytes) for secrets users store via the settings page.
    # Left blank it is derived from JWT_SECRET — fine for dev, set it in production.
    secrets_key: str = ""
    openrouter_api_key: str = ""
    # OpenRouter model slug. Opus 5 is the most capable; swap for a cheaper slug if the
    # coaching bill matters more than answer quality.
    openrouter_model: str = "anthropic/claude-opus-5"
    # Comma-separated origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3000"

    # Nightly sync. Hour is UTC; disable in a second replica so it runs once.
    run_scheduler: bool = True
    nightly_hour: int = 3

    withings_client_id: str = ""
    withings_client_secret: str = ""
    withings_redirect_uri: str = "http://localhost:8000/integrations/withings/callback"


settings = Settings()
