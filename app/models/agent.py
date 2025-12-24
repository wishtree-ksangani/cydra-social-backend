"""Agent model - AI agents with personas"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class Agent(Base):
    """
    Agent model - Represents AI agents with specific personas
    """
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Agent name
    designation = Column(String(255), nullable=True)  # Role/title
    description = Column(Text, nullable=True)  # Agent description/persona
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
