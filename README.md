# ModelVerse

An AI-powered Multi-Agent MLOps and Learning Platform.

## Architecture
- **Frontend**: Next.js 16 (React 19, Tailwind CSS v4)
- **Backend**: FastAPI (Python 3)
- **Database**: PostgreSQL (SQLAlchemy + Alembic)
- **ML training**: scikit-learn pipelines with local MLflow tracking and optional Optuna optimization
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

## ML Training & Experimentation
Phase 5 consumes the current Phase 4 recommendation and requires an explicitly confirmed target for supervised training. The backend offers the recommended models it supports, fits reusable numeric/categorical preprocessing on the training split only, evaluates separate training/validation/test splits, and selects the best candidate deterministically using validation metrics.

Experiment and candidate metadata are stored in PostgreSQL. Model files and the default local MLflow file store are written under ignored `backend/data/` directories; `MODEL_ARTIFACT_STORAGE_PATH`, `MLFLOW_ARTIFACT_STORAGE_PATH`, and `MLFLOW_TRACKING_URI` can configure those locations. Optional Optuna tuning uses a bounded trial count (`OPTUNA_N_TRIALS`, default 10, maximum 20) and timeout (`OPTUNA_TIMEOUT_SECONDS`, default 60, maximum 600). Tuning is opt-in.

Phase 5 endpoints include:
- `POST /api/v1/projects/{project_id}/experiments`
- `POST /api/v1/experiments/{experiment_id}/train`
- `POST /api/v1/experiments/{experiment_id}/optimize`
- `GET /api/v1/projects/{project_id}/experiments`
- `GET /api/v1/experiments/{experiment_id}`
- `GET /api/v1/experiments/{experiment_id}/comparison`

The initial algorithm registry covers the Phase 4 classification and regression candidates and K-Means. Hierarchical clustering is not offered because it has no out-of-sample prediction path for the held-out evaluation contract. Recommendations remain on-demand; experiment history is persisted.

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
- Hierarchical clustering is not in the initial training registry because it has no out-of-sample prediction path for held-out evaluation.
- Explainability, deployment, monitoring, and other later lifecycle capabilities remain future phases.
- Some workspace navigation sections remain placeholders for those later phases.
