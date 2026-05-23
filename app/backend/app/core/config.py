from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "dachjob.ai"
    secret_key: str = "change-me-in-local-dev"
    default_tenant_slug: str = "dachjob-local"

    database_url: str = "postgresql+psycopg://dachjob:dachjob@localhost:5432/dachjob"
    redis_url: str = "redis://localhost:6379/0"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_fast: str = "deepseek-v4-flash"
    deepseek_model_reasoning: str = "deepseek-v4-pro"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "dachjob-artifacts"

    llm_log_prompts: bool = False

    model_config = {"env_file": ".env", "extra": "allow"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
