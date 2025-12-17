from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.social_account import SocialAccount
from app.schemas.social_account import SocialAccountResponse

router = APIRouter()


@router.get("/", response_model=List[SocialAccountResponse])
async def list_social_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all connected social media accounts for the current user.
    """
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == current_user.id,
            SocialAccount.is_active == True
        ).order_by(SocialAccount.created_at.desc())
    )
    accounts = result.scalars().all()
    
    return accounts


@router.get("/{account_id}", response_model=SocialAccountResponse)
async def get_social_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a specific social media account.
    """
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    account = result.scalars().first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    return account
