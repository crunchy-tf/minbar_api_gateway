# api_gateway_service/app/config.py
from typing import Optional, List, Union, Any # Added Union, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl, field_validator # Added field_validator
from loguru import logger # Added logger for validators
import json # Added json for validators

class Settings(BaseSettings):
    SERVICE_NAME: str = "Minbar API Gateway"
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    SERVICE_PORT: int = Field(default=8080, validation_alias="SERVICE_PORT")

    API_GATEWAY_USER: str = Field(validation_alias="API_GATEWAY_USER")
    API_GATEWAY_PASSWORD: str = Field(validation_alias="API_GATEWAY_PASSWORD")

    RATE_LIMIT_REQUESTS: int = Field(default=100, validation_alias="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")
    DEFAULT_CACHE_TTL_SECONDS: int = Field(default=300, validation_alias="DEFAULT_CACHE_TTL_SECONDS")

    # Default parameters for analysis (matching Time Series Analysis service for consistency)
    DEFAULT_MOVING_AVERAGE_WINDOW: int = Field(default=7, validation_alias="DEFAULT_MOVING_AVERAGE_WINDOW")
    DEFAULT_ROC_PERIOD: int = Field(default=1, validation_alias="DEFAULT_ROC_PERIOD")
    DEFAULT_ZSCORE_ROLLING_WINDOW: Optional[int] = Field(default=None, validation_alias="DEFAULT_ZSCORE_ROLLING_WINDOW")
    DEFAULT_STL_PERIOD: Optional[int] = Field(default=None, validation_alias="DEFAULT_STL_PERIOD")

    # Healthcare sentiment labels (matching Signal Extraction for consistency if used)
    HEALTHCARE_SENTIMENT_LABELS: List[str] = Field(
        default_factory=lambda: ["Satisfied", "Grateful", "Concerned", "Anxious", "Confused", "Angry", "Neutral"]
    )


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

    # Validator for optional integer fields from env
    @field_validator('DEFAULT_ZSCORE_ROLLING_WINDOW', 'DEFAULT_STL_PERIOD', mode='before')
    @classmethod
    def parse_optional_int_from_env(cls, v: Any) -> Optional[int]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped: # Handles empty string like DEFAULT_ZSCORE_ROLLING_WINDOW=
                return None
            try:
                return int(v_stripped)
            except ValueError:
                raise ValueError(f"Invalid integer string for Optional[int]: '{v_stripped}'")
        if v is None:
            return None
        if isinstance(v, int):
            return v
        raise ValueError(f"Invalid type for Optional[int]: {type(v)}")

    # Validator for list of strings from env (if you ever need to configure HEALTHCARE_SENTIMENT_LABELS via .env)
    @field_validator("HEALTHCARE_SENTIMENT_LABELS", mode='before')
    @classmethod
    def parse_string_list_from_env(cls, v: Union[str, List[str]]) -> List[str]:
        default_labels = ["Satisfied", "Grateful", "Concerned", "Anxious", "Confused", "Angry", "Neutral"]
        if isinstance(v, list):
            if all(isinstance(item, str) for item in v):
                return v
            else:
                logger.warning("HEALTHCARE_SENTIMENT_LABELS list from env contains non-string items. Using default.")
                return default_labels
        if isinstance(v, str):
            if not v.strip():
                return default_labels
            try:
                parsed_list = json.loads(v)
                if isinstance(parsed_list, list) and all(isinstance(item, str) for item in parsed_list):
                    return parsed_list
                else:
                    logger.warning("HEALTHCARE_SENTIMENT_LABELS from env not a valid JSON list of strings. Using default.")
                    return default_labels
            except json.JSONDecodeError:
                logger.warning(f"Could not parse HEALTHCARE_SENTIMENT_LABELS JSON from env: '{v}'. Using default.")
                return default_labels
        logger.debug("HEALTHCARE_SENTIMENT_LABELS not explicitly set or invalid type in env. Using default.")
        return default_labels


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()