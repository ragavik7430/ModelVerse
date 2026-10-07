from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class Explanation(Base):
    __tablename__ = "explanations"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("experiment_models.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    method = Column(String(32), nullable=False)
    feature_importances = Column(JSON, nullable=True)
    natural_language_explanation = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="completed")

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    model = relationship("TrainedModel", back_populates="explanation")
