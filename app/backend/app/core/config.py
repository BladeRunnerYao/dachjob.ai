from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "dachjob.ai"
    secret_key: str = "change-me-in-local-dev"
    default_tenant_slug: str = "dachjob-local"

    database_url: str = "postgresql+psycopg://dachjob:dachjob@localhost:5432/dachjob"
    database_user: str = "postgres"
    database_password: str = ""
    database_name: str = "dachjob"
    cloud_sql_connection_name: str = ""
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    google_cloud_project: str = ""

    llm_provider: str = "vertex_ai"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model_fast: str = "gemini-3.1-flash-lite"
    gemini_model_quality: str = "gemini-3.5-flash"
    gemini_model_reasoning: str = "gemini-2.5-pro"

    vertex_ai_project_id: str = ""
    vertex_ai_location: str = "global"
    vertex_ai_model_fast: str = "google/gemini-3.1-flash-lite"
    vertex_ai_model_quality: str = "google/gemini-3.5-flash"
    vertex_ai_model_reasoning: str = "google/gemini-3.1-pro-preview"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_fast: str = "deepseek-v4-flash"
    deepseek_model_quality: str = "deepseek-v4-pro"
    deepseek_model_reasoning: str = "deepseek-v4-pro"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_fast: str = "deepseek/deepseek-v4-flash"
    openrouter_model_quality: str = "deepseek/deepseek-v4-pro"
    openrouter_model_reasoning: str = "deepseek/deepseek-v4-pro"

    storage_provider: str = ""
    storage_bucket_name: str = "dachjob-artifacts"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"

    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = ""

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_model_fast: str = "gpt-4o-mini"
    azure_openai_model_quality: str = "gpt-4o"
    azure_openai_model_reasoning: str = "o1-mini"

    llm_log_prompts: bool = False

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    google_client_id: str = ""
    google_client_secret: str = ""

    cors_origins: str = ""

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@dachjob.ai"
    smtp_use_tls: bool = True

    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"

    password_reset_token_minutes: int = 60

    model_config = {"env_file": ".env", "extra": "allow"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
