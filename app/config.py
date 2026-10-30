import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    ai_api_key: str = os.getenv("AI_API_KEY", "").strip()
    ai_model: str = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")
    ai_fallback_model: str = os.getenv("AI_FALLBACK_MODEL", "gemini-3.6-flash")
    ai_embedding_model: str = os.getenv("AI_EMBEDDING_MODEL", "gemini-embedding-001")
    ai_timeout: float = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file: str = os.getenv("LOG_FILE", "logs/app.log")
    seed_on_start: bool = os.getenv("SEED_ON_START", "true").lower() == "true"
    auth_secret: str = os.getenv("AUTH_SECRET", "")
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"

    def __init__(self):
        # Keep the URL compatible with the psycopg2 driver in requirements.txt.
        # SQLAlchemy 2.1 otherwise defaults postgresql:// to psycopg (v3).
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)


settings = Settings()
