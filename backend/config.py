import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from root or backend directory if present
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

if (ROOT_DIR / ".env").exists():
    load_dotenv(ROOT_DIR / ".env")
elif (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")

class Config:
    """Application Configuration supporting both PostgreSQL and SQLite fallback."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Device authentication key for ESP32 HTTP requests
    API_KEY = os.getenv("ESP32_API_KEY", "smartguard-esp32-secret-key-2026")
    
    # Allowed frontend origins for CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Seconds before a device without incoming events/heartbeats is marked "Offline"
    HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "45"))
    
    # Database Configuration (PostgreSQL in Docker, SQLite fallback for local test)
    raw_db_url = os.getenv("DATABASE_URL")
    if raw_db_url:
        # Compatibility fix for cloud providers that still emit postgres:// instead of postgresql://
        if raw_db_url.startswith("postgres://"):
            raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
        # Ensure sslmode=require for Neon PostgreSQL
        if "neon.tech" in raw_db_url and "sslmode=" not in raw_db_url:
            separator = "&" if "?" in raw_db_url else "?"
            raw_db_url = f"{raw_db_url}{separator}sslmode=require"
        SQLALCHEMY_DATABASE_URI = raw_db_url
        DB_TYPE = "PostgreSQL"
    else:
        # SQLite database stored inside backend folder
        sqlite_path = BASE_DIR / "smartguard.db"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{sqlite_path.as_posix()}"
        DB_TYPE = "SQLite"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
