from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Financial Document Intelligence API"
    database_url: str = "sqlite:///./document_intelligence.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    paddleocr_lang: str = "en"
    paddleocr_device: str = "cpu"
    max_file_size_mb: int = Field(default=10, gt=0, le=50)
    max_page_count: int = Field(default=3, gt=0, le=3)
    financial_abs_tolerance: float = Field(default=0.01, ge=0)
    financial_rel_tolerance: float = Field(default=0.0001, ge=0)
    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"

    @property
    def max_file_bytes(self):
        return self.max_file_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self):
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings():
    return Settings()
