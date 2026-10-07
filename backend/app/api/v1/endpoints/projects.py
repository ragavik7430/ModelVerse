import os
from typing import List
from google import genai

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents import execute_agent_graph
from app.database.connection import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.dataset import Dataset
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.recommendation import RecommendationResponse
from app.services.dataset_service import analyze_csv_file

router = APIRouter()


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(
        user_id=current_user.id,
        name=payload.name.strip(),
        problem_statement=payload.problem_statement.strip(),
        objective=payload.objective.strip(),
        mode=payload.mode,
        status="Created",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    db.delete(project)
    db.commit()
    return {"deleted": True, "project_id": project_id}


@router.post("/{project_id}/recommend", response_model=RecommendationResponse)
def recommend_project_pipeline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    dataset = (
        db.query(Dataset)
        .filter(Dataset.project_id == project_id)
        .order_by(Dataset.uploaded_at.desc())
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no dataset.")
    if not dataset.file_path or not dataset.file_path.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dataset state.")

    try:
        dataset_summary = analyze_csv_file(dataset.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dataset state.") from exc

    try:
        initial_state = {
            "project_id": project.id,
            "project_name": project.name,
            "problem_statement": project.problem_statement,
            "objective": project.objective,
            "dataset_id": dataset.id,
            "dataset_summary": dataset_summary,
            "problem_type": "unknown",
            "target_candidate": None,
            "feature_candidates": list(dataset_summary.get("columns") or []),
            "dataset_characteristics": {},
            "recommended_pipeline": "",
            "candidate_algorithms": [],
            "preprocessing_steps": [],
            "rationale": "",
            "confidence": 0.0,
            "warnings": [],
            "explanation": "",
            "errors": [],
        }
        result = execute_agent_graph(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Graph execution failed.") from exc

    recommendation = RecommendationResponse(
        project_id=project.id,
        dataset_id=dataset.id,
        project_name=project.name,
        problem_statement=project.problem_statement,
        objective=project.objective,
        problem_type=result.get("problem_type", "unknown"),
        target_candidate=result.get("target_candidate"),
        feature_candidates=result.get("feature_candidates") or [],
        dataset_summary=dataset_summary,
        dataset_characteristics=result.get("dataset_characteristics") or {},
        recommended_pipeline=result.get("recommended_pipeline") or "More information is required before choosing a pipeline.",
        candidate_algorithms=result.get("candidate_algorithms") or [],
        preprocessing_steps=result.get("preprocessing_steps") or [],
        rationale=result.get("rationale") or "No rationale available.",
        confidence=float(result.get("confidence") or 0.0),
        warnings=result.get("warnings") or [],
        explanation=result.get("explanation") or "No explanation available.",
        errors=result.get("errors") or [],
    )
    return recommendation


class ChatMessage(BaseModel):
    message: str

@router.post("/{project_id}/chat")
def project_chat(
    project_id: int,
    payload: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.mode != "learning":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is only available in learning mode.")

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required.")

    try:
        from app.services.rag_service import retrieve_context
        rag_context_docs = retrieve_context(project.id, message, top_k=5)
    except Exception as e:
        rag_context_docs = []

    context = f"Project Name: {project.name}\n"
    if rag_context_docs:
        context += "Relevant RAG Context:\n"
        for doc in rag_context_docs:
            context += f"- [{doc.get('source_type', 'unknown')}] {doc.get('title', 'Untitled')}: {doc.get('text', '')}\n"
    else:
        context += "No additional context found in the RAG store.\n"

    prompt = f"Context:\n{context}\n\nUser Question:\n{message}\n\nPlease answer the user's question, explaining machine learning concepts using the retrieved context when relevant. Do not expose internal IDs."

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GEMINI_API_KEY is not configured.")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"reply": response.text}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Chat failed: {str(exc)}")
