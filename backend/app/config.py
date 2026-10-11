from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    app_version: str = "0.3.0"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/vehicle_agent"
    model_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_use_responses_api: bool = True
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = ""
    azure_openai_chat_model: str = ""
    azure_openai_embedding_deployment: str = ""
    azure_openai_embedding_model: str = "text-embedding-3-small"
    azure_openai_use_managed_identity: bool = False
    azure_openai_use_responses_api: bool = False
    frontend_origin: str = "http://localhost:5173"
    mcp_server_url: str = "http://localhost:8001/mcp"
    agent_tool_mode: str = "local"
    mcp_api_key: str = ""
    auto_create_schema: bool = True
    log_level: str = "INFO"
    nhtsa_timeout_seconds: float = 12.0
    max_triage_recursion: int = 12

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
