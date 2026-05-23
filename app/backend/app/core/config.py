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

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_fast: str = "deepseek/deepseek-v4-flash"
    openrouter_model_reasoning: str = "deepseek/deepseek-v4-flash"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "dachjob-artifacts"

    llm_log_prompts: bool = False

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = {"env_file": ".env", "extra": "allow"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
