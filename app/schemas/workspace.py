from pydantic import BaseModel

class WorkspaceBase(BaseModel):
    business_name: str | None = None
    industry: str | None = None
    default_tone: str | None = None
    timezone: str | None = None

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceUpdate(WorkspaceBase):
    pass

class WorkspaceResponse(WorkspaceBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True
