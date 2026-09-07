"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # IBM Granite / watsonx
    granite_api_key: str = ""
    granite_url: str = "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation"
    granite_model_id: str = "ibm/granite-4-h-small"
    granite_api_version: str = "2023-05-29"
    ibm_project_id: str = ""

    # App
    app_name: str = "LearnMate AI"
    debug: bool = False
    database_url: str = "sqlite:///./learnmate.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def granite_configured(self) -> bool:
        return bool(self.granite_api_key and self.ibm_project_id)

    @property
    def cors_origins_list(self):
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
