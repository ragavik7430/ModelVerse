from sqlalchemy import Boolean, Column, Integer, String
from app.models.base import Base

class User(Base):
    """
    Minimal User model to establish the database layer schema.
    """
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
