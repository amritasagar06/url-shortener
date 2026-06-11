import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Zenith Links Production Engine"
    
    # Infrastructure Connections (aligned with docker-compose.yml values)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgrespassword@db:5432/url_shortener"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # Environment Mode (production disables verbose database query echoing, saving CPU cycles)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    
    # Security Configurations 
    # Updated default to your newly generated secure SHA-256 production hash!
    API_KEY_HASH: str = os.getenv(
        "API_KEY_HASH", 
        "ced619f334f772034a79ad81993cb1558581d22a419679984e7c548b502308cd"
    )
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1")
    
    # SSRF Protection Blocklist
    BLOCKED_DOMAINS: set[str] = {"malicious-domain.com", "phishing-link.net", "test-block.com"}

    # Pydantic Settings Configuration (v2 compatible)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()