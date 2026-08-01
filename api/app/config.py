from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://nexus:nexus@db:5432/nexuscoach"
    jwt_secret: str = "dev-only-change-me"
    openrouter_api_key: str = ""


settings = Settings()
