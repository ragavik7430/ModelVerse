from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.config.settings import settings

app = FastAPI(
    title="ModelVerse API",
    description="AI-powered Multi-Agent MLOps and Learning Platform",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "message": "Welcome to ModelVerse API 🚀",
        "status": "running"
    }