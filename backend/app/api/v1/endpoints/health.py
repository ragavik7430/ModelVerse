from fastapi import APIRouter

router = APIRouter()

@router.get("/health", response_model=dict)
def health_check():
    """
    Health check endpoint for the ModelVerse API.
    """
    return {
        "status": "healthy",
        "service": "modelverse_api",
        "version": "1.0.0"
    }
