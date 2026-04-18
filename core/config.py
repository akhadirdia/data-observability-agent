from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ANTHROPIC_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./data.db"
    SLACK_WEBHOOK_URL: str = ""
    ALERT_EMAIL: str = ""
    ENV: str = "development"
    CHECK_INTERVAL_MINUTES: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
