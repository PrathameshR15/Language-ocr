import os
from pydantic import BaseModel
from typing import List

# Simple pure python .env loader
def load_dotenv(dotenv_path=".env"):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")

load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "AI Multilingual Document Translation & Intelligence System")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    TRANSLATED_DIR: str = os.getenv("TRANSLATED_DIR", "./translated")
    LOG_DIR: str = os.getenv("LOG_DIR", "./logs")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./gov_doc_translation.db")
    
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "png", "jpeg", "jpg", "tiff", "docx", "zip", "txt"]
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

settings = Settings()

# Ensure required directories exist
for path in [settings.UPLOAD_DIR, settings.TRANSLATED_DIR, settings.LOG_DIR]:
    os.makedirs(path, exist_ok=True)
