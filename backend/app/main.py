from fastapi import FastAPI

app = FastAPI(
    title="ModelVerse API",
    description="AI-powered Multi-Agent MLOps and Learning Platform",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "message": "Welcome to ModelVerse API 🚀",
        "status": "running"
    }