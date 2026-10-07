from fastapi import APIRouter
from app.api.v1.endpoints import auth, datasets, experiments, health, models, projects

api_router = APIRouter()
api_router.include_router(health.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(datasets.router, tags=["datasets"])
api_router.include_router(experiments.router, tags=["experiments"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
