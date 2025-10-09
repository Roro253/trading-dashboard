from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )

    node_env: str = Field(default="development", alias="NODE_ENV")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="trading_dashboard", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")

    redis_url: AnyUrl = Field(alias="REDIS_URL")

    api_cors_origins: List[AnyHttpUrl] = Field(default_factory=list, alias="API_CORS_ORIGINS")
    polygon_api_key: str = Field(default="", alias="POLYGON_API_KEY")

    next_public_api_base_url: AnyHttpUrl = Field(alias="NEXT_PUBLIC_API_BASE_URL")

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | List[str] | None) -> List[str] | None:
        if value is None:
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()
