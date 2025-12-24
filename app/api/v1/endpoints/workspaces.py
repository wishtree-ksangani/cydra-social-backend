from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse

router = APIRouter()

@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user already has a workspace
    if current_user.workspace:
        raise HTTPException(status_code=400, detail="Workspace already exists for this user")
    
    # Create workspace
    new_workspace = Workspace(
        name=workspace_in.name,
        type=workspace_in.type,
        timezone=workspace_in.timezone,
        industry=workspace_in.industry,
        description=workspace_in.description,
        address=workspace_in.address,
        user_id=current_user.id
    )
    db.add(new_workspace)
    await db.commit()
    await db.refresh(new_workspace)
    return new_workspace

@router.get("/", response_model=WorkspaceResponse | None)
async def get_workspace(
    current_user: User = Depends(get_current_user)
):
    # Return None if no workspace exists (200 status with null)
    return current_user.workspace

@router.put("/", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_in: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Update workspace fields
    workspace = current_user.workspace
    update_data = workspace_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workspace, field, value)
    
    await db.commit()
    await db.refresh(workspace)
    return workspace

@router.delete("/", status_code=204)
async def delete_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    await db.delete(current_user.workspace)
    await db.commit()
    return None
