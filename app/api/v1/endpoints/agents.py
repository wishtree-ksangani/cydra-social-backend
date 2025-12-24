"""Agent CRUD endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent

router = APIRouter()


# ==================== Schemas ====================

class AgentCreate(BaseModel):
    """Create agent request"""
    name: str
    designation: Optional[str] = None
    description: Optional[str] = None


class AgentUpdate(BaseModel):
    """Update agent request"""
    name: Optional[str] = None
    designation: Optional[str] = None
    description: Optional[str] = None


class AgentResponse(BaseModel):
    """Agent response"""
    id: int
    name: str
    designation: Optional[str]
    description: Optional[str]
    created_at: str
    updated_at: Optional[str]


# ==================== Endpoints ====================

@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all agents."""
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()
    
    return [
        AgentResponse(
            id=agent.id,
            name=agent.name,
            designation=agent.designation,
            description=agent.description,
            created_at=agent.created_at.isoformat() if agent.created_at else None,
            updated_at=agent.updated_at.isoformat() if agent.updated_at else None
        )
        for agent in agents
    ]


@router.post("/", response_model=AgentResponse)
async def create_agent(
    request: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new agent."""
    agent = Agent(
        name=request.name,
        designation=request.designation,
        description=request.description
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        designation=agent.designation,
        description=agent.description,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
        updated_at=agent.updated_at.isoformat() if agent.updated_at else None
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific agent by ID."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalars().first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        designation=agent.designation,
        description=agent.description,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
        updated_at=agent.updated_at.isoformat() if agent.updated_at else None
    )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    request: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalars().first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if request.name is not None:
        agent.name = request.name
    if request.designation is not None:
        agent.designation = request.designation
    if request.description is not None:
        agent.description = request.description
    
    await db.commit()
    await db.refresh(agent)
    
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        designation=agent.designation,
        description=agent.description,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
        updated_at=agent.updated_at.isoformat() if agent.updated_at else None
    )


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalars().first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await db.delete(agent)
    await db.commit()
    
    return {"success": True, "message": "Agent deleted successfully"}
