from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json

class Settings(BaseSettings):
    PROJECT_NAME: str = "NexDesk AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    
    # AI Configurations
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    
    # Security
    JWT_SECRET: str = "development_secret_key_minimum_32_characters_long_12345"
    
    # Databases
    DATABASE_URL: str = "sqlite:///./nexdesk.db"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"

    # Knowledge / RAG Storage
    KNOWLEDGE_UPLOAD_DIR: str = "./uploads/knowledge"
    MAX_UPLOAD_SIZE_MB: int = 15
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 75
    RAG_TOP_K: int = 5
    RAG_RELEVANCE_THRESHOLD: float = 0.28
    RAG_MAX_CONTEXT_CHARS: int = 6000

    # Email & Notification Configuration (Module 9A & 12B)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "balaji.poet2312s@gmail.com"
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "balaji.poet2312s@gmail.com"
    SMTP_FROM_NAME: str = "NexDesk AI – IT Service Desk"
    SMTP_USE_TLS: bool = True
    SMTP_STARTTLS: bool = True
    SMTP_MAX_RETRIES: int = 2
    SMTP_TIMEOUT_SECONDS: int = 10
    ADMIN_NOTIFICATION_EMAIL: str = "balaji.poet2312s@gmail.com"
    ADMIN_EMAIL: str = "balaji.poet2312s@gmail.com"
    ADMIN_SEED_EMAIL: str = ""
    ADMIN_SEED_PASSWORD: str = ""
    SEED_DEMO_ACCOUNTS: bool = True
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    FRONTEND_URL: str = ""
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""
    BREVO_API_KEY: str = ""
    ALLOW_RESERVED_EMAIL_DOMAINS: bool = False
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    def get_frontend_base_url(self) -> str:
        """
        Resolve the active frontend base URL for verification and ticket links without allowing
        localhost defaults to leak into production links.
        """
        is_prod = self.ENVIRONMENT.lower() == "production"
        explicit_url = (self.FRONTEND_URL or "").strip().rstrip("/")
        base_url = (self.FRONTEND_BASE_URL or "").strip().rstrip("/")

        def _is_local(url: str) -> bool:
            lowered = url.lower()
            return "localhost" in lowered or "127.0.0.1" in lowered

        if explicit_url and not (is_prod and _is_local(explicit_url) and base_url and not _is_local(base_url)):
            return explicit_url
        if base_url and not (is_prod and _is_local(base_url)):
            return base_url
        if is_prod and isinstance(self.CORS_ORIGINS, list):
            for origin in self.CORS_ORIGINS:
                clean = (origin or "").strip().rstrip("/")
                if clean and clean.startswith("http") and not _is_local(clean):
                    return clean
        return base_url or explicit_url or "http://localhost:5173"

    def validate_runtime_settings(self) -> list[str]:
        """Validate critical production configuration without raising on dev/test."""
        warnings: list[str] = []
        is_prod = self.ENVIRONMENT.lower() == "production"
        if is_prod:
            if not self.JWT_SECRET or "development_secret_key" in self.JWT_SECRET or len(self.JWT_SECRET) < 32:
                warnings.append("JWT_SECRET must be replaced with a strong random >=32-char secret in production.")
            if "sqlite" in self.DATABASE_URL.lower():
                warnings.append("SQLite DATABASE_URL detected in production; persistent managed PostgreSQL is strongly recommended.")
            if not self.GROQ_API_KEY:
                warnings.append("GROQ_API_KEY is not configured; AI assistant/classification will use deterministic fallbacks.")
            if not self.SMTP_PASSWORD and not self.RESEND_API_KEY and not self.BREVO_API_KEY:
                warnings.append("Neither HTTPS Email API nor SMTP_PASSWORD is configured; outbound emails will log as skipped_unconfigured while in-app alerts remain active.")
            if any("localhost" in o or "127.0.0.1" in o for o in self.CORS_ORIGINS):
                warnings.append("CORS_ORIGINS still contains localhost/127.0.0.1 in production mode.")
        return warnings

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
