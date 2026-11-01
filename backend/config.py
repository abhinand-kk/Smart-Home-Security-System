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
    
    # Device authentication key for ESP32 HTTP requests (Rotated secret key)
    API_KEY = os.getenv("ESP32_API_KEY", "smartguard-sec-key-8e9f2a4b1c7d")
    
    # Default physical device identifier
    DEFAULT_DEVICE_ID = os.getenv("DEFAULT_DEVICE_ID", "esp32-pir-01")
    SIMULATION_DEVICE_ID = "dashboard-sim-01"

    # Allowed frontend origins for CORS (Always includes production Vercel & local dev)
    DEFAULT_ALLOWED_ORIGINS = [
        "https://smart-home-security-system-backend.vercel.app",
        "http://localhost:8080",
        "http://localhost:5000",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:3000"
    ]
    raw_cors = os.getenv("CORS_ORIGINS")
    if raw_cors:
        if raw_cors.strip() == "*":
            CORS_ORIGINS = ["*"]
        else:
            parsed = [o.strip() for o in raw_cors.split(",") if o.strip()]
            for orig in DEFAULT_ALLOWED_ORIGINS:
                if orig not in parsed:
                    parsed.append(orig)
            CORS_ORIGINS = parsed
    else:
        CORS_ORIGINS = DEFAULT_ALLOWED_ORIGINS
    
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
