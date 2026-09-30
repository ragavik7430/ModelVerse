# ModelVerse

An AI-powered Multi-Agent MLOps and Learning Platform.

## Architecture (Phase 1)
- **Frontend**: Next.js 16 (React 19, Tailwind CSS v4)
- **Backend**: FastAPI (Python 3)
- **Database**: PostgreSQL (SQLAlchemy + Alembic)
- **Containerization**: Docker Compose for local infrastructure

## Local Setup

### 1. Database Configuration
ModelVerse uses PostgreSQL. For local development, start the database using Docker:
```bash
docker-compose up -d db
```

### 2. Environment Variables
Copy the example environment files:
- `.env.example` -> `.env`
- `frontend/.env.example` -> `frontend/.env.local`

### 3. Backend Setup
Create a virtual environment, install dependencies, and run migrations:
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate # or .venv/bin/activate on Mac/Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:3000`.

## Testing
To run backend tests:
```bash
cd backend
pytest
```
