from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True)
    problem_type = Column(String(32), nullable=False)
    target_column = Column(String(255), nullable=True)
    experiment_name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    random_state = Column(Integer, nullable=False, default=42)
    test_size = Column(Float, nullable=False)
    configuration = Column(JSON, nullable=False, default=dict)
    best_model_id = Column(Integer, nullable=True)
    comparison_policy = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project = relationship("Project", back_populates="experiments")
    dataset = relationship("Dataset", back_populates="experiments")
    models = relationship("TrainedModel", back_populates="experiment", cascade="all, delete-orphan")


class TrainedModel(Base):
    __tablename__ = "experiment_models"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    algorithm = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    parameters = Column(JSON, nullable=False, default=dict)
    metrics = Column(JSON, nullable=False, default=dict)
    preprocessing = Column(JSON, nullable=False, default=dict)
    artifact_key = Column(String(500), nullable=True)
    mlflow_run_id = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    experiment = relationship("Experiment", back_populates="models")
    explanation = relationship("Explanation", back_populates="model", uselist=False, cascade="all, delete-orphan")
