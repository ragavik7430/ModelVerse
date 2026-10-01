# ModelVerse

An AI-powered Multi-Agent MLOps and Learning Platform.

## Architecture (Phase 2)
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
Copy the example environment files and set the required auth values:
- `.env.example` -> `.env`
- `frontend/.env.local` (or create it from the frontend defaults)

Required backend values include:
- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `BACKEND_CORS_ORIGINS`

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

## Authentication Flow
ModelVerse now includes real authentication and authenticated project workspaces:
- Register a user at `POST /api/v1/auth/register`
- Log in at `POST /api/v1/auth/login`
- Fetch the current user at `GET /api/v1/auth/me`
- Sign out from the client by clearing stored auth tokens
- Access protected project endpoints with `Authorization: Bearer <token>`

## API Endpoints
### Authentication
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### Projects
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`

## Project Workspace
Phase 2 implements real user-owned project records with:
- project name, problem statement, objective, mode, and status
- ownership enforcement at the backend layer
- engineering and learning mode persistence
- protected access for all project routes

## Testing
Run backend tests:
```bash
cd backend
python -m pytest tests -q
```

Run frontend checks:
```bash
cd frontend
npm run lint
npm run build
```

## Known Limitations
- Docker/PostgreSQL verification is blocked in this environment because the Docker daemon is unavailable.
- Future lifecycle features such as dataset intelligence, pipeline execution, and deployment flows are not implemented in Phase 2.
- The project navigation sections marked as “Coming soon” are placeholders only and are not functional yet.
