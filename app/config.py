from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    qdrant_url: str = Field(..., alias="QDRANT_URL")
    qdrant_collection_name: str = Field("svet_memory", alias="QDRANT_COLLECTION_NAME")

    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")

    # Google AI Studio (Gemini) — OpenAI-compatible endpoint; used for vision & long context when routing=auto
    google_ai_api_key: str | None = Field(None, alias="GOOGLE_AI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_openai_base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        alias="GEMINI_OPENAI_BASE_URL",
    )

    # Cerebras Inference (OpenAI-compatible) — used for short / low-context steps when routing=auto
    cerebras_api_key: str | None = Field(None, alias="CEREBRAS_API_KEY")
    cerebras_model: str = Field("llama3.1-8b", alias="CEREBRAS_MODEL")
    cerebras_openai_base_url: str = Field("https://api.cerebras.ai/v1/", alias="CEREBRAS_OPENAI_BASE_URL")

    # Estimated input tokens (heuristic: ~4 chars/token); above this → Gemini when provider=auto
    llm_long_context_threshold_tokens: int = Field(8000, alias="LLM_LONG_CONTEXT_THRESHOLD_TOKENS")

    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    default_llm_provider: str = Field("auto", alias="DEFAULT_LLM_PROVIDER")

    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")
    environment: str = Field("dev", alias="ENVIRONMENT")

    serpapi_key: str | None = Field(None, alias="SERPAPI_KEY")

    agent_files_root: str = Field("/tmp/svet_agent_files", alias="AGENT_FILES_ROOT")

    smtp_host: str | None = Field(None, alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str | None = Field(None, alias="SMTP_USER")
    smtp_password: str | None = Field(None, alias="SMTP_PASSWORD")
    smtp_from: str = Field("noreply@localhost", alias="SMTP_FROM")
    imap_host: str | None = Field(None, alias="IMAP_HOST")
    imap_port: int = Field(993, alias="IMAP_PORT")
    imap_user: str | None = Field(None, alias="IMAP_USER")
    imap_password: str | None = Field(None, alias="IMAP_PASSWORD")

    max_prompt_chars: int = Field(12000, alias="MAX_PROMPT_CHARS")
    max_tool_input_chars: int = Field(6000, alias="MAX_TOOL_INPUT_CHARS")
    rate_limit_per_minute: int = Field(60, alias="RATE_LIMIT_PER_MINUTE")

    cors_origins: str = Field("*", alias="CORS_ORIGINS")
    google_calendar_access_token: str | None = Field(None, alias="GOOGLE_CALENDAR_ACCESS_TOKEN")
    google_calendar_id: str = Field("primary", alias="GOOGLE_CALENDAR_ID")


@lru_cache
def get_settings() -> Settings:
    return Settings()
