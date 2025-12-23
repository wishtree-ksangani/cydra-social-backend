"""Page management endpoints for Facebook Pages and Instagram accounts"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.core.encryption import decrypt_token
from app.models.user import User
from app.models.social_account import SocialAccount
from app.models.page_account import PageAccount
from app.schemas.page_account import (
    PageAccountResponse,
    PageListResponse,
    PageAccountSummary
)
from app.services.facebook import FacebookPagesService

router = APIRouter()


@router.get("/{social_account_id}/pages", response_model=PageListResponse)
async def list_pages(
    social_account_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all Facebook Pages and Instagram accounts for a social account.
    """
    # Verify social account belongs to user
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == social_account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    social_account = result.scalars().first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    if social_account.platform != "facebook":
        raise HTTPException(
            status_code=400,
            detail="This endpoint is only for Facebook accounts"
        )
    
    # Get all pages for this account
    result = await db.execute(
        select(PageAccount).where(
            PageAccount.social_account_id == social_account_id,
            PageAccount.is_active == True
        ).order_by(PageAccount.created_at)
    )
    pages = result.scalars().all()
    
    # Calculate summary
    total_pages = len(pages)
    pages_with_instagram = sum(1 for p in pages if p.can_post_to_instagram)
    pages_without_instagram = total_pages - pages_with_instagram
    
    selected_facebook = next((p for p in pages if p.is_selected_for_facebook), None)
    selected_instagram = next((p for p in pages if p.is_selected_for_instagram), None)
    
    summary = PageAccountSummary(
        total_pages=total_pages,
        pages_with_instagram=pages_with_instagram,
        pages_without_instagram=pages_without_instagram,
        selected_facebook_page=selected_facebook,
        selected_instagram_page=selected_instagram
    )
    
    return PageListResponse(
        pages=[PageAccountResponse.from_orm(p) for p in pages],
        summary=summary
    )


@router.post("/{social_account_id}/pages/refresh", response_model=PageListResponse)
async def refresh_pages(
    social_account_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Re-fetch pages from Facebook and update database.
    """
    # Verify social account belongs to user
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == social_account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    social_account = result.scalars().first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    if social_account.platform != "facebook":
        raise HTTPException(
            status_code=400,
            detail="This endpoint is only for Facebook accounts"
        )
    
    if not social_account.is_active:
        raise HTTPException(
            status_code=400,
            detail="Social account is disconnected. Please reconnect."
        )
    
    # Decrypt user token
    user_token = decrypt_token(social_account.access_token)
    
    # Fetch and save pages
    try:
        await FacebookPagesService.fetch_and_save_pages(
            db=db,
            social_account_id=social_account_id,
            user_access_token=user_token
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch pages: {str(e)}"
        )
    
    # Return updated list
    return await list_pages(social_account_id, current_user, db)


@router.post("/{social_account_id}/pages/{page_id}/select")
async def select_page(
    social_account_id: int,
    page_id: int,
    platform: str,  # "facebook" or "instagram"
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Select a page as the default for posting to Facebook or Instagram.
    """
    # Verify social account belongs to user
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == social_account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    social_account = result.scalars().first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    # Get the page
    result = await db.execute(
        select(PageAccount).where(
            PageAccount.id == page_id,
            PageAccount.social_account_id == social_account_id
        )
    )
    page = result.scalars().first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Validate platform
    if platform not in ["facebook", "instagram"]:
        raise HTTPException(
            status_code=400,
            detail="Platform must be 'facebook' or 'instagram'"
        )
    
    # Check if page supports the platform
    if platform == "instagram" and not page.can_post_to_instagram:
        raise HTTPException(
            status_code=400,
            detail="This page doesn't have Instagram linked"
        )
    
    # Unselect all other pages for this platform
    result = await db.execute(
        select(PageAccount).where(
            PageAccount.social_account_id == social_account_id
        )
    )
    all_pages = result.scalars().all()
    
    for p in all_pages:
        if platform == "facebook":
            p.is_selected_for_facebook = (p.id == page_id)
        else:  # instagram
            p.is_selected_for_instagram = (p.id == page_id)
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Page selected for {platform} posting",
        "page_id": page_id,
        "page_name": page.page_name
    }


@router.get("/{social_account_id}/pages/{page_id}/validate")
async def validate_page(
    social_account_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate if a page's access token is still valid.
    """
    # Verify ownership
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == social_account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    social_account = result.scalars().first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    # Get the page
    result = await db.execute(
        select(PageAccount).where(
            PageAccount.id == page_id,
            PageAccount.social_account_id == social_account_id
        )
    )
    page = result.scalars().first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Decrypt and validate token
    page_token = decrypt_token(page.page_access_token)
    is_valid = await FacebookPagesService.validate_page_token(page_token)
    
    if not is_valid:
        page.is_active = False
        await db.commit()
    
    return {
        "is_valid": is_valid,
        "page_id": page_id,
        "page_name": page.page_name,
        "message": "Token is valid" if is_valid else "Token is invalid or expired"
    }
