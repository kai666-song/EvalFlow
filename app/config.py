from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """从环境变量或.env文件读取项目配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: SecretStr = Field(
        validation_alias="DASHSCOPE_API_KEY",
    )

    llm_base_url: str = Field(
        validation_alias="LLM_BASE_URL",
    )

    llm_model: str = Field(
        default="qwen3.7-flash",
        validation_alias="LLM_MODEL",
    )

    llm_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias="LLM_TIMEOUT_SECONDS",
    )

@lru_cache
def get_settings() -> Settings:
    """读取并缓存配置。"""

    return Settings()
