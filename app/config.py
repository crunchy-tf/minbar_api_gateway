from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl

class Settings(BaseSettings):
    SERVICE_NAME: str = "Minbar API Gateway"
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    SERVICE_PORT: int = Field(default=8080, validation_alias="SERVICE_PORT")

    API_GATEWAY_USER: str = Field(validation_alias="API_GATEWAY_USER")
    API_GATEWAY_PASSWORD: str = Field(validation_alias="API_GATEWAY_PASSWORD")

    RATE_LIMIT_REQUESTS: int = Field(default=100, validation_alias="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")
    DEFAULT_CACHE_TTL_SECONDS: int = Field(default=300, validation_alias="DEFAULT_CACHE_TTL_SECONDS")

    TIMESCALEDB_USER: str = Field(validation_alias="TIMESCALEDB_USER")
    TIMESCALEDB_PASSWORD: str = Field(validation_alias="TIMESCALEDB_PASSWORD")
    TIMESCALEDB_HOST: str = Field(validation_alias="TIMESCALEDB_HOST")
    TIMESCALEDB_PORT: int = Field(default=5432, validation_alias="TIMESCALEDB_PORT")
    TIMESCALEDB_DB: str = Field(validation_alias="TIMESCALEDB_DB")

    SOURCE_SIGNALS_TABLE_PREFIX: str = Field(default="agg_signals", validation_alias="SOURCE_SIGNALS_TABLE_PREFIX")
    ANALYSIS_RESULTS_TABLE_PREFIX: str = Field(default="analysis_results", validation_alias="ANALYSIS_RESULTS_TABLE_PREFIX")

    KEYWORD_MANAGER_API_URL: AnyHttpUrl = Field(validation_alias="KEYWORD_MANAGER_API_URL")

    @property
    def timescaledb_dsn_asyncpg(self) -> str:
        return f"postgresql://{self.TIMESCALEDB_USER}:{self.TIMESCALEDB_PASSWORD}@{self.TIMESCALEDB_HOST}:{self.TIMESCALEDB_PORT}/{self.TIMESCALEDB_DB}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()