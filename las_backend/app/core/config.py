from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Database
    DATABASE_FILE: Optional[str] = None
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/las_db"
    AUTO_CREATE_TABLES: bool = False
    MODEL_CARD_EMBEDDING_DIMENSIONS: int = 64
    
    # JWT
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    LOGIN_RATE_LIMIT_BLOCK_SECONDS: int = 600
    
    # LLM - OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # LLM - Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    
    # Default LLM Provider
    DEFAULT_LLM_PROVIDER: str = "openai"
    LLM_REQUEST_TIMEOUT_SECONDS: int = 25
    LEARNING_PATH_TIMEOUT_SECONDS: int = 8
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]

    @property
    def effective_database_url(self) -> str:
        if self.DATABASE_FILE:
            return f"sqlite+aiosqlite:///{self.DATABASE_FILE}"
        return self.DATABASE_URL

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"production", "prod", "staging"}

    def validate_runtime_settings(self) -> None:
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 16:
            raise ValueError("SECRET_KEY must be set and at least 16 characters long")
        if self.is_production and self.SECRET_KEY == "dev-secret-key-change-in-production":
            raise ValueError("Production APP_ENV requires a non-default SECRET_KEY")
    
@lru_cache()
def get_settings() -> Settings:
    return Settings()
