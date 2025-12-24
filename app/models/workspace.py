from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Business details
    name = Column(String(255), nullable=False)  # Workspace/business name
    type = Column(String(100), nullable=True)  # Business type (e.g., "Startup", "Agency", "Enterprise")
    timezone = Column(String(100), nullable=True)  # e.g., "Asia/Kolkata"
    industry = Column(String(255), nullable=True)  # Industry category
    description = Column(Text, nullable=True)  # Description of the business
    address = Column(Text, nullable=True)  # Business address
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="workspace")

