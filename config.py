from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mode: str = "DEV"
    docs_user: str = "docs"
    docs_password: str = "secret"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    database_path: str = "app.db"

    @field_validator("mode")
    @classmethod
    def normalize_mode(cls, v: str) -> str:
        m = v.strip().upper()
        if m not in ("DEV", "PROD"):
            raise ValueError(f"Invalid MODE: {v!r}. Use DEV or PROD.")
        return m

    @field_validator("database_path", mode="before")
    @classmethod
    def strip_sqlite_url(cls, v: object) -> object:
        if isinstance(v, str) and v.startswith("sqlite:///"):
            return v.replace("sqlite:///", "", 1).lstrip("/") or "app.db"
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
