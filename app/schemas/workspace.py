from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WorkspaceBase(BaseModel):
    name: Optional[str] = None  # Workspace/business name
    type: Optional[str] = None  # Business type (Startup, Agency, etc.)
    timezone: Optional[str] = None  # e.g., "Asia/Kolkata"
    industry: Optional[str] = None  # Industry category
    description: Optional[str] = None  # Description of the business
    address: Optional[str] = None  # Business address


class WorkspaceCreate(BaseModel):
    name: str  # Required on create
    type: Optional[str] = None
    timezone: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None


class WorkspaceUpdate(WorkspaceBase):
    pass


class WorkspaceResponse(WorkspaceBase):
    id: int
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
