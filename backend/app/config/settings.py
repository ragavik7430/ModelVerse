import json
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    cors_env = os.getenv("BACKEND_CORS_ORIGINS", '["http://localhost:3000"]')
    try:
        BACKEND_CORS_ORIGINS = json.loads(cors_env)
    except Exception:
        BACKEND_CORS_ORIGINS = []

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://modelverse_user:modelverse_password@localhost:5432/modelverse_db",
    )


settings = Settings()
