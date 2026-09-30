import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

    # Parse CORS origins
    cors_env = os.getenv("BACKEND_CORS_ORIGINS", '["http://localhost:3000"]')
    try:
        BACKEND_CORS_ORIGINS = json.loads(cors_env)
    except Exception:
        BACKEND_CORS_ORIGINS = []

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://modelverse_user:modelverse_password@localhost:5432/modelverse_db"
    )

settings = Settings()
